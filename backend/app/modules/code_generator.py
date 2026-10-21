"""Module O3a — Analysis Code Generator.

Sinh mã pandas cho DUY NHẤT MỘT AnalysisTask theo kỹ thuật "fill-in-the-middle":
LLM chỉ điền phần thân hàm analyze(df), khung scaffold cố định theo task.type.
"""
from __future__ import annotations

import logging
import re

from ..llm_client import LLMClient
from ..schemas import AnalysisTask, CodeGenResult, DataProfile

logger = logging.getLogger(__name__)


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
    \"\"\"Tính % tăng/giảm của metric theo nhóm giữa kỳ đầu và kỳ cuối.
    Trả về: dict với 2 key:
      - "growth_rate": pd.Series (index = tên nhóm, values = % thay đổi, làm tròn 2 chữ số).
      - "target": str — tên nhóm tăng/giảm nhiều nhất theo find (min/max).
    \"\"\"
    # TODO: điền logic tính toán vào đây
    pass
""",
}

_EXPECTED_OUTPUTS: dict[str, list[str]] = {
    "trend": ["trend"],
    "comparison": ["comparison"],
    "growth_rate": ["growth_rate", "target"],
}

_FEW_SHOTS: dict[str, str] = {
    "trend": """\
Ví dụ (trend — doanh thu theo từng kỳ thời gian):
Metric: "Doanh_thu_trieu_vnd", Cột thời gian: "Thang", Hàm tổng hợp: "sum"
```python
def analyze(df):
    trend = df.groupby("Thang")["Doanh_thu_trieu_vnd"].sum()
    return {"trend": trend}
```""",

    "comparison": """\
Ví dụ (comparison — so sánh tổng doanh thu giữa các chi nhánh):
Metric: "Doanh_thu_trieu_vnd", Nhóm: "Chi_nhanh", Hàm tổng hợp: "sum"
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
    # Chuẩn hóa thời gian theo tháng và cộng gộp theo (kỳ, nhóm) trước khi lấy kỳ đầu/cuối
    dt = pd.to_datetime(df["Thang"], errors="coerce")
    period = dt.dt.to_period("M").astype(str) if not dt.isna().all() else df["Thang"].astype(str)
    grouped = df.assign(_p=period).groupby(["_p", "Chi_nhanh"])["Doanh_thu_trieu_vnd"].sum().unstack()
    first = grouped.iloc[0]
    last = grouped.iloc[-1]
    growth = ((last - first) / first * 100).round(2).dropna()
    target = growth.idxmin()  # find="min" -> giảm mạnh nhất
    return {"growth_rate": growth, "target": target}
```""",
}


def _build_prompt(
    task: AnalysisTask,
    profile: DataProfile,
    previous_error: str | None,
    question: str = "",
) -> str:
    """Xây prompt fill-in-the-middle cho đúng task.type, kèm ngữ cảnh câu hỏi gốc."""
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
    agg_info = getattr(task, "agg", None) or "sum"
    top_k = getattr(task, "top_k", None)
    top_k_info = f"Lấy top {top_k} nhóm đầu tiên (.head({top_k}))" if top_k else "(lấy tất cả nhóm)"
    question_line = f'- Câu hỏi gốc của người dùng: "{question}"\n' if question else ""

    error_section = ""
    if previous_error:
        error_section = f"""\

THÔNG BÁO LỖI LẦN TRƯỚC (bắt buộc phải sửa):
{previous_error}

"""

    return f"""Bạn là lập trình viên Python chuyên pandas. Nhiệm vụ: điền phần thân hàm analyze(df).
BẮT BUỘC: CHỈ dùng đúng tên cột liệt kê dưới, KHÔNG import thư viện, KHÔNG tự thêm lọc thời gian.

Thông tin dataset & yêu cầu:
{question_line}- Cột metric cần tính: "{task.metric}" (kiểu số)
- Cột thời gian: {time_col_info}
- Cột nhóm (group_by): {group_col_info}
- Loại phân tích: "{task.type}"
- Hàm tổng hợp (agg): "{agg_info}" (dùng .{agg_info}() khi groupby)
- Hướng tìm kiếm: {find_info}
- Giới hạn kết quả: {top_k_info}
- Lưu ý: Với task "growth_rate", BẮT BUỘC phải chuyển cột thời gian sang kỳ tháng bằng pd.to_datetime(...).dt.to_period("M") và cộng gộp theo (kỳ, nhóm) trước khi lấy dòng đầu (.iloc[0]) và dòng cuối (.iloc[-1]).
- df đã được LỌC theo khoảng thời gian và điều kiện thực thể bởi orchestrator — KHÔNG cần lọc thêm.
{error_section}
{few_shot}

Bây giờ hãy điền vào scaffold sau. CHỈ trả về code Python hoàn chỉnh của hàm analyze(df), không kèm markdown hay giải thích:

{scaffold}"""


def _extract_code(raw: str | dict) -> str:
    """Trích code từ response LLM (có thể là string hoặc JSON dict)."""
    if isinstance(raw, dict):
        raw = raw.get("code", "")

    if not isinstance(raw, str):
        raw = str(raw)

    match = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()

    return raw.strip()


def generate(
    task: AnalysisTask,
    profile: DataProfile,
    llm: LLMClient,
    previous_error: str | None = None,
    question: str = "",
) -> CodeGenResult:
    """Sinh mã pandas cho DUY NHẤT MỘT AnalysisTask."""
    if task.type not in _SCAFFOLDS:
        raise CodeGenerationError(
            f"Loại task '{task.type}' không có scaffold tương ứng. "
            f"Chỉ hỗ trợ: {sorted(_SCAFFOLDS)}"
        )

    prompt = _build_prompt(task, profile, previous_error, question=question)
    logger.info("Đang sinh mã cho task.type=%r, metric=%r", task.type, task.metric)

    try:
        raw = llm.complete_json(prompt)
    except Exception as exc:
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
    """Raised khi không thể sinh mã hợp lệ từ LLM."""
