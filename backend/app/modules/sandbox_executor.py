"""Module O3b — Sandbox Executor.

Thực thi mã do O3a sinh ra trong môi trường hạn chế, bảo vệ qua 3 lớp:

Lớp 1 — Kiểm tra tĩnh AST (TRƯỚC khi chạy):
    Chặn import, gọi hàm nguy hiểm (eval/exec/open...), truy cập dunder attribute.
    Đây là lớp chặn nhanh, tất định — không có false negative với mã do LLM sinh
    theo scaffold hẹp (vì scaffold không cần import gì cả).

Lớp 2 — Chạy trong tiến trình con riêng (multiprocessing "spawn"):
    - Dùng get_context("spawn") thay vì fork mặc định trên Linux, vì FastAPI/uvicorn
      chạy đa luồng và fork từ tiến trình đa luồng có thể gây deadlock trong child
      (nếu thread khác đang giữ lock lúc fork xảy ra). Spawn tạo Python interpreter
      mới hoàn toàn — nhất quán trên Windows/Linux/Mac, tránh bug fork+thread.
    - process.join(timeout) + terminate() chặn vòng lặp vô hạn ở tầng OS —
      terminate() không cần "sự hợp tác" của code đang chạy, hoạt động trên cả 3 hệ.
    - KHÔNG dùng resource.setrlimit để giới hạn bộ nhớ vì module resource không có
      trên Windows. Thay thế: giới hạn RAM đặt ở tầng Docker khi deploy thật
      (docker run --memory=512m). Xem docs/ARCHITECTURE.md mục "Giới hạn sandbox".

Lớp 3 — exec() với __builtins__ rỗng (phòng thủ theo chiều sâu):
    Namespace exec chỉ có {"pd": pandas, "df": df} — không có built-ins Python mặc định.
    Lớp này KHÔNG đủ tự nó (có cách bypass đã biết công khai), nhưng kết hợp với
    Lớp 1 (AST đã lọc phần lớn nội dung nguy hiểm), nó tăng thêm độ khó cho tấn công
    không chủ ý (lỗi do LLM sinh ra).

Giới hạn rõ ràng (ghi vào báo cáo):
    Sandbox này đủ để chống lỗi/code kém chất lượng do LLM sinh KHÔNG CHỦ Ý.
    KHÔNG cam kết chống tấn công CHỦ Ý vì người dùng cuối không tự viết code —
    đây là điểm mà hội đồng chấm thường hỏi, cần chủ động nêu trước.

Không gọi LLM — đây là logic kỹ thuật thuần túy.
"""
from __future__ import annotations

import ast
import logging
import multiprocessing
import pickle
import traceback
from typing import Any

import pandas as pd

from ..schemas import ExecutionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lớp 1 — Kiểm tra tĩnh AST
# ---------------------------------------------------------------------------
_FORBIDDEN_NODES = (ast.Import, ast.ImportFrom)

_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "open", "__import__", "compile",
    "globals", "locals", "vars", "breakpoint", "input",
    "memoryview", "bytearray",
})


class UnsafeCodeError(Exception):
    """Mã không vượt qua kiểm tra tĩnh (Lớp 1) — không được thực thi.

    Raise trước khi tiến trình con được tạo, nên không tốn overhead
    của multiprocessing khi code rõ ràng vi phạm.
    """


def _static_safety_check(code: str) -> None:
    """Phân tích AST, raise UnsafeCodeError nếu có cấu trúc bị cấm.

    Kiểm tra:
    - Import statement (import os, from sys import ...)
    - Gọi hàm nguy hiểm (eval, exec, open, __import__, ...)
    - Truy cập dunder attribute (obj.__class__, obj.__globals__, ...)

    Raises:
        SyntaxError: nếu code không parse được (cú pháp sai).
        UnsafeCodeError: nếu vi phạm quy tắc an toàn.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        # Cú pháp sai → không phải lỗi bảo mật, để execute() xử lý riêng
        raise SyntaxError(f"Cú pháp Python không hợp lệ: {exc}") from exc

    for node in ast.walk(tree):
        # Chặn import
        if isinstance(node, _FORBIDDEN_NODES):
            lineno = getattr(node, "lineno", "?")
            names = (
                [alias.name for alias in node.names]
                if hasattr(node, "names")
                else []
            )
            raise UnsafeCodeError(
                f"Không được phép import tại dòng {lineno}: {names}"
            )

        # Chặn gọi hàm nguy hiểm (Name node — vd: eval(...))
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            lineno = getattr(node, "lineno", "?")
            raise UnsafeCodeError(
                f"Không được phép gọi '{node.id}' tại dòng {lineno}"
            )

        # Chặn truy cập dunder attribute (vd: obj.__class__, obj.__globals__)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            lineno = getattr(node, "lineno", "?")
            raise UnsafeCodeError(
                f"Không được phép truy cập '{node.attr}' tại dòng {lineno}"
            )


# ---------------------------------------------------------------------------
# Lớp 2 — Worker chạy trong tiến trình con (spawn)
# Phải là hàm top-level (không lồng) để pickle được khi dùng spawn context.
# ---------------------------------------------------------------------------

# Giới hạn bộ nhớ tùy điều kiện: chỉ có trên Linux/Mac
try:
    import resource as _resource
    _HAS_RESOURCE = True
except ImportError:  # Windows
    _HAS_RESOURCE = False


def _apply_resource_limits() -> None:
    """Đặt giới hạn bộ nhớ (512 MB) trong tiến trình con nếu OS hỗ trợ.

    Chỉ hoạt động trên Linux/Mac (module resource). Trên Windows, giới hạn
    bộ nhớ phải đặt ở tầng Docker khi deploy thật (--memory=512m).
    """
    if _HAS_RESOURCE:
        limit = 512 * 1024 * 1024  # 512 MB
        try:
            _resource.setrlimit(_resource.RLIMIT_AS, (limit, limit))
        except Exception:
            pass  # Một số hệ thống không hỗ trợ RLIMIT_AS — bỏ qua


def _sandbox_worker(
    code: str,
    df_pickled: bytes,
    result_queue: "multiprocessing.Queue[dict[str, Any]]",
) -> None:
    """Hàm chạy trong tiến trình con (spawn).

    Trình tự:
    1. Áp dụng giới hạn tài nguyên nếu OS hỗ trợ.
    2. Deserialize DataFrame từ bytes (pickle).
    3. exec(code) trong namespace giới hạn (Lớp 3).
    4. Gọi analyze(df) và đưa kết quả vào queue.

    Mọi exception đều được bắt và đưa vào queue — không để
    exception thô truyền ra ngoài tiến trình.
    """
    _apply_resource_limits()

    try:
        df: pd.DataFrame = pickle.loads(df_pickled)
    except Exception as exc:
        result_queue.put({"success": False, "error": f"Lỗi deserialize DataFrame: {exc}"})
        return

    # Lớp 3: exec với __builtins__ rỗng
    namespace: dict[str, Any] = {"pd": pd, "df": df, "__builtins__": {}}
    try:
        exec(code, namespace)  # noqa: S102
    except Exception as exc:
        result_queue.put({
            "success": False,
            "error": f"Lỗi khi exec mã: {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        })
        return

    analyze = namespace.get("analyze")
    if not callable(analyze):
        result_queue.put({"success": False, "error": "Hàm analyze() không được định nghĩa trong mã."})
        return

    try:
        result = analyze(df)
    except Exception as exc:
        result_queue.put({
            "success": False,
            "error": f"Lỗi khi chạy analyze(df): {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        })
        return

    if not isinstance(result, dict):
        result_queue.put({
            "success": False,
            "error": f"analyze(df) phải trả về dict, nhận được {type(result).__name__}.",
        })
        return

    # Chuyển Series/DataFrame thành dict để có thể truyền qua queue
    serializable: dict[str, Any] = {}
    for key, val in result.items():
        if hasattr(val, "to_dict"):
            serializable[key] = val.to_dict()
        else:
            serializable[key] = val

    result_queue.put({"success": True, "results": serializable})


# ---------------------------------------------------------------------------
# API công khai — hàm execute()
# ---------------------------------------------------------------------------

def execute(code: str, df: pd.DataFrame, timeout: int = 10) -> ExecutionResult:
    """Thực thi 1 lần mã phân tích trong sandbox có giới hạn.

    execute() chỉ chạy đúng 1 lần — retry là trách nhiệm của orchestrator
    (analysis_runner.py). Trường attempts trong ExecutionResult được điền
    bởi orchestrator, không phải ở đây.

    Trình tự:
    1. Lớp 1: kiểm tra AST — nếu vi phạm raise UnsafeCodeError ngay.
    2. Lớp 2: serialize df, tạo tiến trình con (spawn), join(timeout).
       Nếu quá giờ, terminate() + join() để tránh zombie process.
    3. Đọc kết quả từ queue và trả về ExecutionResult.

    Args:
        code: mã Python do O3a sinh ra (đã qua grounding check của O2).
        df: DataFrame đã được lọc theo time_start/time_end bởi orchestrator.
        timeout: thời gian tối đa (giây) cho phép tiến trình con chạy.

    Returns:
        ExecutionResult — luôn trả về, không bao giờ để exception thô thoát.

    Raises:
        UnsafeCodeError: nếu code vi phạm Lớp 1 (trước khi tiến trình được tạo).
    """
    # --- Lớp 1: AST check ---
    try:
        _static_safety_check(code)
    except UnsafeCodeError:
        raise  # Để orchestrator bắt và đếm vào attempts
    except SyntaxError as exc:
        return ExecutionResult(success=False, error=str(exc))

    # --- Lớp 2: multiprocessing spawn ---
    try:
        df_pickled = pickle.dumps(df)
    except Exception as exc:
        return ExecutionResult(success=False, error=f"Không thể serialize DataFrame: {exc}")

    ctx = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue = ctx.Queue()

    p = ctx.Process(
        target=_sandbox_worker,
        args=(code, df_pickled, result_queue),
        daemon=True,
    )
    p.start()
    p.join(timeout=timeout)

    if p.is_alive():
        p.terminate()
        p.join()  # chờ tiến trình thực sự kết thúc, tránh zombie process
        logger.warning("Sandbox timeout sau %ds — tiến trình đã bị terminate()", timeout)
        return ExecutionResult(
            success=False,
            error=f"Mã vượt quá thời gian cho phép ({timeout}s). "
                  "Có thể có vòng lặp vô hạn hoặc tính toán quá nặng.",
        )

    # Đọc kết quả từ queue
    if result_queue.empty():
        return ExecutionResult(
            success=False,
            error="Tiến trình con kết thúc mà không trả về kết quả (có thể bị crash).",
        )

    payload = result_queue.get_nowait()
    if payload.get("success"):
        return ExecutionResult(success=True, results=payload.get("results", {}))

    return ExecutionResult(success=False, error=payload.get("error", "Lỗi không xác định."))
