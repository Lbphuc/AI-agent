"""Module O3a — Analysis Code Generator.

Sinh mã pandas cho DUY NHẤT MỘT AnalysisTask theo kỹ thuật "fill-in-the-middle":
LLM chỉ điền phần thân hàm analyze(df), khung scaffold cố định theo task.type.

Thiết kế tuân thủ 3 nguyên tắc xuyên suốt đồ án:
1. Sinh mã theo từng task — không gộp nhiều task vào 1 lần gọi LLM.
   Mỗi đoạn mã nhỏ hơn, dễ validate; nếu 1 task lỗi không kéo theo các task khác.
2. Scaffold riêng biệt cho từng task.type — LLM không cần biết về các loại task khác,
   prompt ngắn hơn, ít cơ hội "thoát khỏi scaffold".
3. KHÔNG để LLM lọc thời gian — time_start/time_end đã được O2 tính tất định;
   việc lọc df theo thời gian thuộc trách nhiệm orchestrator (analysis_runner.py),
   TRƯỚC khi df được đưa vào sandbox. Đây là nguyên tắc "tách suy luận LLM khỏi
   tính toán chính xác" được áp dụng xuyên suốt từ O2.

Tham chiếu: VISGENERATOR trong LIDA (Dibia, 2023) — kỹ thuật fill-in-the-middle
để giới hạn phạm vi LLM sinh mã, từ đó giảm bề mặt rủi ro cho sandbox.
"""
from __future__ import annotations

import json
import logging
import re

from ..llm_client import LLMClient
from ..schemas import AnalysisTask, CodeGenResult, DataProfile

logger = logging.getLogger(__name__)


# Scaffold cố định — 3 loại, tương ứng 3 TaskType trong schemas.py

_SCAFFOLDS: dict[str, str] = {
    "trend": """\
def analyze(df):
    \"\"\"Tính xu hướng metric theo thời gian.
    Trả về: dict với key "trend" là pd.Series (index = nhóm thời gian, values = metric).
    \"\"\"
    # TODO: điền logic tính toán vào đây
    pass
""",
    "comparison": """\
def analyze(df):
    \"\"\"So sánh metric giữa các nhóm.
    Trả về: dict với key "comparison" là pd.Series (index = tên nhóm, values = metric).
    \"\"\"
    # TODO: điền logic tính toán vào đây
    pass
""",
    "growth_rate": """\
def analyze(df):
    \"\"\"Tính % tăng/giảm của metric theo nhóm.
    Trả về: dict với 2 key:
      - "growth_rate": pd.Series (index = tên nhóm, values = % thay đổi, làm tròn 2 chữ số).
      - "target": str — tên nhóm tăng/giảm nhiều nhất theo find (min/max).
    \"\"\"
    # TODO: điền logic tính toán vào đây
    pass
""",
}

# Tên output key mỗi loại task cần trả về — dùng để set expected_outputs trong CodeGenResult
_EXPECTED_OUTPUTS: dict[str, list[str]] = {
    "trend": ["trend"],
    "comparison": ["comparison"],
    "growth_rate": ["growth_rate", "target"],
}

# ---------------------------------------------------------------------------
# Few-shot examples — 1 ví dụ/loại, đặt trong prompt ĐÚNG loại đó
# (không chứa cả 3 loại trong 1 prompt — không cần thiết vì task đã phân loại)
# ---------------------------------------------------------------------------
_FEW_SHOTS: dict[str, str] = {
    "trend": """\
Ví dụ (trend — doanh thu theo từng tháng):
Metric: "Doanh_thu_trieu_vnd", Cột thời gian: "Thang"
```python
def analyze(df):
    trend = df.groupby("Thang")["Doanh_thu_trieu_vnd"].sum()
    return {"trend": trend}
```""",

    "comparison": """\
Ví dụ (comparison — so sánh tổng doanh thu giữa các chi nhánh):
Metric: "Doanh_thu_trieu_vnd", Nhóm: "Chi_nhanh"
```python
def analyze(df):
    comparison = df.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].sum().sort_values(ascending=False)
    return {"comparison": comparison}
```""",

    "growth_rate": """\
Ví dụ (growth_rate — chi nhánh giảm doanh thu nhiều nhất, find="min"):
Metric: "Doanh_thu_trieu_vnd", Nhóm: "Chi_nhanh", Cột thời gian: "Thang", find: "min"
```python
def analyze(df):
    # Sắp xếp theo thời gian để lấy đúng tháng đầu và tháng cuối
    df_sorted = df.sort_values("Thang")
    first = df_sorted.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].first()
    last = df_sorted.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].last()
    growth = ((last - first) / first * 100).round(2)
    target = growth.idxmin()  # find="min" -> giảm mạnh nhất
    return {"growth_rate": growth, "target": target}
```""",
}


def _build_prompt(
    task: AnalysisTask,
    profile: DataProfile,
    previous_error: str | None,
) -> str:
    """Xây prompt fill-in-the-middle cho đúng task.type.

    Prompt bao gồm:
    - Thông tin cột thật (grounded) từ DataProfile — LLM chỉ dùng tên cột này
    - Few-shot ví dụ ĐÚNG loại task (không lẫn lộn 3 loại)
    - Scaffold cố định cần điền
    - Thông báo lỗi lần trước (nếu có) — kỹ thuật error feedback của LIDA
    """
    scaffold = _SCAFFOLDS[task.type]
    few_shot = _FEW_SHOTS[task.type]

    time_col_info = (
        f'"{profile.time_column}"'
        if profile.time_column
        else "(không có cột thời gian)"
    )
    group_col_info = (
        f'"{task.group_by}"' if task.group_by else "(không có nhóm)"
    )
    find_info = (
        f'find="{task.find}" (idxmin nếu "min", idxmax nếu "max")'
        if task.find
        else "(không cần tìm min/max)"
    )

    error_section = ""
    if previous_error:
        error_section = f"""\

THÔNG BÁO LỖI LẦN TRƯỚC (bắt buộc phải sửa):
{previous_error}

"""

    return f"""Bạn là lập trình viên Python chuyên pandas. Nhiệm vụ: điền phần thân hàm analyze(df).
BẮT BUỘC: CHỈ dùng đúng tên cột liệt kê dưới, KHÔNG import thư viện, KHÔNG tự thêm lọc thời gian.

Thông tin dataset:
- Cột metric cần tính: "{task.metric}" (kiểu số)
- Cột thời gian: {time_col_info}
- Cột nhóm (group_by): {group_col_info}
- Loại phân tích: "{task.type}"
- Hướng tìm kiếm: {find_info}
- df đã được LỌC theo khoảng thời gian bởi orchestrator — KHÔNG cần lọc thêm.
{error_section}
{few_shot}

Bây giờ hãy điền vào scaffold sau. CHỈ trả về code Python hoàn chỉnh của hàm analyze(df), không kèm markdown hay giải thích:

{scaffold}"""


def _extract_code(raw: str | dict) -> str:
    """Trích code từ response LLM (có thể là string hoặc JSON dict).

    LLM có thể trả:
    - string thuần (code trực tiếp)
    - JSON {"code": "..."} (nếu dùng response_mime_type=application/json)
    - string có chứa markdown code block ```python ... ```
    """
    if isinstance(raw, dict):
        raw = raw.get("code", "")

    if not isinstance(raw, str):
        raw = str(raw)

    # Trích khỏi markdown code block nếu có
    match = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()

    return raw.strip()


def generate(
    task: AnalysisTask,
    profile: DataProfile,
    llm: LLMClient,
    previous_error: str | None = None,
) -> CodeGenResult:
    """Sinh mã pandas cho DUY NHẤT MỘT AnalysisTask.

    Args:
        task: AnalysisTask đã được grounding-check bởi O2.
        profile: DataProfile từ O1 — cung cấp tên cột thật để ground prompt.
        llm: LLMClient (GeminiClient hoặc FakeLLM trong test).
        previous_error: thông báo lỗi từ lần thực thi trước (nếu có).
            Khi truyền vào, prompt sẽ kèm yêu cầu "sửa lỗi này" —
            kỹ thuật error feedback của LIDA (Dibia, 2023).

    Returns:
        CodeGenResult với code hoàn chỉnh (scaffold đã được điền) và
        expected_outputs tương ứng task.type.

    Raises:
        CodeGenerationError: khi LLM trả về nội dung không thể dùng được.
    """
    if task.type not in _SCAFFOLDS:
        raise CodeGenerationError(
            f"Loại task '{task.type}' không có scaffold tương ứng. "
            f"Chỉ hỗ trợ: {sorted(_SCAFFOLDS)}"
        )

    prompt = _build_prompt(task, profile, previous_error)
    logger.info("Đang sinh mã cho task.type=%r, metric=%r", task.type, task.metric)

    try:
        raw = llm.complete_json(prompt)
    except Exception as exc:
        # Nếu LLM dùng response_mime_type=text thay vì json, thử dùng complete() fallback
        # Ở đây raise lỗi rõ ràng để orchestrator xử lý
        raise CodeGenerationError(f"Lỗi khi gọi LLM: {exc}") from exc

    code = _extract_code(raw)

    if not code or "def analyze" not in code:
        raise CodeGenerationError(
            f"LLM không sinh ra hàm analyze(df) hợp lệ. "
            f"Nội dung nhận được: {str(raw)[:200]}"
        )

    return CodeGenResult(
        code=code,
        expected_outputs=_EXPECTED_OUTPUTS.get(task.type, [task.type]),
    )


class CodeGenerationError(Exception):
    """Raised khi không thể sinh mã hợp lệ từ LLM.

    Orchestrator (analysis_runner.py) bắt lỗi này và đếm vào số lần thử.
    """
