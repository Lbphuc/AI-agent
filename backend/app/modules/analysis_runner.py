"""Orchestrator — ghép O3a (Code Generator) + O3b (Sandbox Executor).

analysis_runner.py là điểm nối giữa các module:
1. Lọc DataFrame theo time_start/time_end (tất định, KHÔNG qua LLM).
   Đây là bước tách biệt quan trọng: O2 tính time_start/time_end bằng Python,
   O3a chỉ nhận df đã lọc — LLM không bao giờ thấy toàn bộ dữ liệu thô.
2. Vòng lặp sinh mã (O3a) → thực thi (O3b) → retry nếu lỗi, tối đa max_attempts.
3. Truyền previous_error vào lần sinh lại tiếp theo — kỹ thuật error feedback
   của LIDA (Dibia, 2023): lỗi cụ thể giúp LLM sửa đúng chỗ hơn là thử lại mù.
4. Điền attempts vào ExecutionResult — execute() không tự đếm, đây là trách nhiệm
   của orchestrator để giữ execute() đơn giản (chỉ 1 lần/lần gọi).
"""
from __future__ import annotations

import logging

import pandas as pd

from ..llm_client import LLMClient
from ..schemas import AnalysisGoal, AnalysisTask, DataProfile, ExecutionResult
from . import code_generator, sandbox_executor
from .code_generator import CodeGenerationError
from .sandbox_executor import UnsafeCodeError

logger = logging.getLogger(__name__)


def _filter_by_time_range(
    df: pd.DataFrame,
    profile: DataProfile,
    time_start: str | None,
    time_end: str | None,
) -> pd.DataFrame:
    """Lọc df theo khoảng thời gian — TUYỆT ĐỐI không giao cho LLM.

    Nguyên tắc: time_start/time_end đã được O2 tính tất định dựa trên
    DataProfile.time_max. Lọc df ở đây (TRƯỚC khi đưa vào sandbox) đảm bảo
    LLM chỉ "nhìn thấy" dữ liệu trong khoảng thời gian đã xác định, không cần
    viết thêm bất kỳ logic lọc nào trong mã phân tích.

    Nếu không có cột thời gian hoặc không có time_start/time_end: trả về df gốc.
    Nếu chuyển đổi datetime thất bại: ghi cảnh báo, trả về df gốc (fail safe).
    """
    if profile.time_column is None or (time_start is None and time_end is None):
        return df

    time_col = profile.time_column
    if time_col not in df.columns:
        logger.warning("Cột thời gian '%s' không tồn tại trong df — bỏ qua lọc.", time_col)
        return df

    try:
        times = pd.to_datetime(df[time_col], errors="coerce")
        mask = pd.Series(True, index=df.index)
        if time_start:
            mask &= times >= pd.Timestamp(time_start)
        if time_end:
            mask &= times <= pd.Timestamp(time_end)
        filtered = df[mask].reset_index(drop=True)
        logger.info(
            "Lọc thời gian: %d → %d dòng (%s đến %s)",
            len(df), len(filtered), time_start, time_end,
        )
        return filtered
    except Exception as exc:
        logger.warning("Lỗi khi lọc thời gian: %s — dùng df gốc.", exc)
        return df


def run_task(
    task: AnalysisTask,
    goal: AnalysisGoal,
    profile: DataProfile,
    df: pd.DataFrame,
    llm: LLMClient,
    max_attempts: int = 3,
) -> ExecutionResult:
    """Lọc dữ liệu theo thời gian rồi sinh mã + thực thi, tối đa max_attempts lần.

    Vòng lặp retry:
    - Lần 1: sinh mã bình thường (previous_error=None).
    - Lần 2+: sinh mã với thông báo lỗi của lần trước (error feedback).
    - Nếu mã vi phạm sandbox (UnsafeCodeError): đếm vào attempts, sinh lại.
    - Nếu mã lỗi runtime: đếm vào attempts, sinh lại kèm traceback.
    - Nếu thành công: trả về ngay với attempts đã điền.
    - Sau max_attempts lần: trả về ExecutionResult(success=False).

    Args:
        task: một AnalysisTask đơn lẻ (không phải cả AnalysisGoal).
        goal: AnalysisGoal chứa time_start/time_end để lọc.
        profile: DataProfile từ O1 — cần để sinh mã và lọc thời gian.
        df: DataFrame gốc (chưa lọc) — sẽ được lọc tại đây.
        llm: LLMClient để sinh mã.
        max_attempts: số lần thử tối đa (mặc định 3, theo SRS).

    Returns:
        ExecutionResult với attempts đã điền bởi orchestrator này.
    """
    df_filtered = _filter_by_time_range(df, profile, goal.time_start, goal.time_end)

    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "run_task: task.type=%r, attempt=%d/%d",
            task.type, attempt, max_attempts,
        )

        # --- Sinh mã ---
        try:
            code_result = code_generator.generate(
                task=task,
                profile=profile,
                llm=llm,
                previous_error=last_error,
            )
        except CodeGenerationError as exc:
            last_error = f"Lỗi sinh mã (lần {attempt}): {exc}"
            logger.warning(last_error)
            continue

        # --- Thực thi ---
        try:
            exec_result = sandbox_executor.execute(code_result.code, df_filtered)
        except UnsafeCodeError as exc:
            last_error = f"Mã vi phạm sandbox (lần {attempt}): {exc}"
            logger.warning(last_error)
            continue

        if exec_result.success:
            exec_result.attempts = attempt
            exec_result.code = code_result.code
            return exec_result

        last_error = exec_result.error
        logger.warning(
            "Thực thi thất bại (lần %d/%d): %s",
            attempt, max_attempts, last_error,
        )

    logger.error(
        "run_task thất bại sau %d lần cho task.type=%r. Lỗi cuối: %s",
        max_attempts, task.type, last_error,
    )
    return ExecutionResult(
        success=False,
        error=last_error or "Thất bại sau tất cả các lần thử.",
        attempts=max_attempts,
    )
