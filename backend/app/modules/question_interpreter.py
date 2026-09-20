"""Module O2 — Question Interpreter.

Nhận câu hỏi tự do của người dùng (tiếng Việt) + DataProfile từ O1,
sinh ra một AnalysisGoal có cấu trúc để O3 (Tuần 4) sinh mã phân tích
tương ứng.

BẮT BUỘC gọi API LLM (Claude) — đây là bài toán hiểu ngôn ngữ tự do,
không thể phủ hết bằng luật/regex. Áp dụng kỹ thuật few-shot prompting
tương tự GOAL EXPLORER của LIDA (Dibia, 2023): các ví dụ few-shot liên
kết trực tiếp câu hỏi với TÊN CỘT THẬT, giúp giảm hallucination.

Hai nguyên tắc thiết kế quan trọng, khác với O1.enrich():

1. **"Grounding check" bắt buộc**: mọi `metric`/`group_by` do LLM chọn
   đều được đối chiếu lại với DataProfile bằng code tất định (không
   tin tưởng mù quáng output của LLM) trước khi coi là hợp lệ.
2. **Fail LOUD, không fail êm**: khác O1.enrich() (module tùy chọn,
   lỗi thì âm thầm trả về profile gốc), O2 nằm trên đường găng
   (FR-04, ưu tiên Cao) — AnalysisGoal sai/rỗng sẽ khiến O3 sinh mã
   sai mà không ai biết tại sao. Nên mọi lỗi ở đây đều RAISE
   QuestionInterpretationError để lộ ra sớm và rõ ràng.

Việc tính TOÁN NGÀY THÁNG cụ thể (time_start/time_end) luôn do Python
đảm nhận (`_resolve_time_range`), KHÔNG giao cho LLM — LLM chỉ chọn
một nhãn `time_scope` cố định — cùng nguyên tắc "tách suy luận LLM
khỏi tính toán chính xác" đã áp dụng cho O3 (xem docs/ARCHITECTURE.md
mục 5).
"""
from __future__ import annotations

import json
import logging
import typing

import pandas as pd

from ..llm_client import LLMClient
from ..schemas import AnalysisGoal, AnalysisTask, DataProfile, FindMode, TaskType, TimeScope

logger = logging.getLogger(__name__)

# Lấy đúng tập giá trị hợp lệ từ chính Literal đã khai báo trong
# schemas.py (KHÔNG liệt kê lại thủ công ở đây) - tránh 2 nơi lệch nhau
# khi sau này có ai đó sửa schemas.py mà quên sửa chỗ này.
ALLOWED_TASK_TYPES: set[str] = set(typing.get_args(TaskType))
ALLOWED_FIND: set[str] = set(typing.get_args(FindMode))
ALLOWED_TIME_SCOPES: set[str] = set(typing.get_args(TimeScope))

_MONTHS_BY_SCOPE = {"last_3_months": 3, "last_6_months": 6, "last_12_months": 12}

_DEFAULT_TIME_SCOPE = "last_12_months"  # theo FR-11 (giá trị mặc định hợp lý)


class QuestionInterpretationError(Exception):
    """Raised khi không thể phân rã câu hỏi thành AnalysisGoal hợp lệ.

    API layer (main.py) bắt lỗi này và trả về thông báo thân thiện,
    gợi ý người dùng đặt lại câu hỏi rõ ràng hơn — thay vì để traceback
    thô lọt ra ngoài (cùng nguyên tắc đã áp dụng cho endpoint /profile
    ở Tuần 2).
    """


FEW_SHOT_EXAMPLES = """Ví dụ 1 (xu hướng theo thời gian):
Câu hỏi: "Doanh thu thay đổi thế nào theo từng tháng?"
JSON: {"time_scope": "last_12_months", "tasks": [
  {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": null, "find": null}
]}

Ví dụ 2 (so sánh giữa các nhóm):
Câu hỏi: "So sánh doanh thu giữa các chi nhánh trong 3 tháng gần đây"
JSON: {"time_scope": "last_3_months", "tasks": [
  {"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": null}
]}

Ví dụ 3 (tăng/giảm theo nhóm):
Câu hỏi: "Chi nhánh nào giảm doanh thu mạnh nhất trong năm qua?"
JSON: {"time_scope": "last_12_months", "tasks": [
  {"type": "growth_rate", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": "min"}
]}

Ví dụ 4 (kết hợp nhiều mục tiêu trong một câu hỏi):
Câu hỏi: "Phân tích xu hướng doanh thu 12 tháng gần nhất và cho biết chi nhánh nào giảm mạnh nhất."
JSON: {"time_scope": "last_12_months", "tasks": [
  {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": null, "find": null},
  {"type": "growth_rate", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": "min"}
]}

Ví dụ 5 (khoảng thời gian tùy chỉnh):
Câu hỏi: "Doanh thu từ tháng 1 đến tháng 6 năm nay thế nào?"
JSON: {"time_scope": "custom", "custom_start": "2026-01", "custom_end": "2026-06", "tasks": [
  {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": null, "find": null}
]}"""


def _build_prompt(question: str, profile: DataProfile) -> str:
    """Xây prompt few-shot, gắn chặt (ground) vào tên cột THẬT của
    dataset hiện tại — bắt buộc LLM chỉ được chọn trong danh sách này."""
    numeric_list = ", ".join(f'"{c}"' for c in profile.numeric_columns) or "(không có)"
    group_list = ", ".join(f'"{c}"' for c in profile.group_columns) or "(không có)"
    time_info = (
        f'"{profile.time_column}" (dữ liệu có từ {profile.time_min} đến {profile.time_max})'
        if profile.time_column
        else "(dữ liệu này không có cột thời gian)"
    )

    return f"""Bạn là một chuyên gia phân tích dữ liệu kinh doanh. Nhiệm vụ: đọc một
câu hỏi tiếng Việt và chuyển thành kế hoạch phân tích có cấu trúc.
BẮT BUỘC chỉ dùng đúng tên cột liệt kê dưới đây — TUYỆT ĐỐI KHÔNG bịa
thêm cột không tồn tại.

Cột thời gian: {time_info}
Cột nhóm (dùng cho "group_by"): {group_list}
Cột số (dùng cho "metric"): {numeric_list}

Chỉ có 3 loại phân tích ("type") hợp lệ:
- "trend": xu hướng một chỉ số theo thời gian (không cần group_by)
- "comparison": so sánh một chỉ số giữa các nhóm (BẮT BUỘC có group_by)
- "growth_rate": tính % tăng/giảm theo nhóm; dùng "find":"min" để tìm
  nhóm giảm/tăng ít nhất, "find":"max" để tìm nhóm tăng nhiều nhất

Chỉ có 5 giá trị "time_scope" hợp lệ: "all", "last_3_months",
"last_6_months", "last_12_months", "custom". CHỈ chọn NHÃN, KHÔNG tự
tính ngày cụ thể. Nếu chọn "custom", thêm 2 trường "custom_start" và
"custom_end" dạng "YYYY-MM". Nếu câu hỏi không nói rõ khoảng thời
gian, dùng "last_12_months".

{FEW_SHOT_EXAMPLES}

Bây giờ hãy phân tích câu hỏi thật sau. CHỈ trả về một JSON object duy
nhất đúng định dạng như các ví dụ trên, không kèm giải thích hay
markdown:

Câu hỏi: "{question}"
JSON:"""


def _resolve_time_range(
    time_scope: str,
    profile: DataProfile,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> tuple[str | None, str | None]:
    """Tính time_start/time_end THẬT bằng Python — KHÔNG giao cho LLM.

    LLM chỉ chọn nhãn (time_scope); toán ngày tháng cụ thể luôn do
    Python đảm nhận để tránh LLM tính sai số học ngày tháng.
    """
    if time_scope == "custom":
        return custom_start, custom_end

    if time_scope == "all" or profile.time_max is None:
        return profile.time_min, profile.time_max

    months = _MONTHS_BY_SCOPE.get(time_scope)
    if months is None:
        return profile.time_min, profile.time_max

    end = pd.Timestamp(profile.time_max)
    # months - 1 de tinh CA thang cuoi cung (vd "12 thang gan nhat" tinh
    # tu thang hien tai lui ve 11 thang truoc = du 12 thang).
    start = end - pd.DateOffset(months=months - 1)
    if profile.time_min is not None:
        start = max(start, pd.Timestamp(profile.time_min))

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _validate_task(task_dict: dict, profile: DataProfile) -> AnalysisTask:
    """Kiểm tra 1 task do LLM sinh ra có tham chiếu đúng cột THẬT không.

    Đây là bước "grounding check" quan trọng nhất của O2 — nếu không
    chặn ở đây, cột hallucinate sẽ trôi xuống O3, gây lỗi muộn hơn và
    khó truy vết hơn nhiều.
    """
    task_type = task_dict.get("type")
    if task_type not in ALLOWED_TASK_TYPES:
        raise ValueError(
            f"Loại phân tích '{task_type}' không hợp lệ. "
            f"Chỉ chấp nhận: {sorted(ALLOWED_TASK_TYPES)}"
        )

    metric = task_dict.get("metric")
    if metric not in profile.numeric_columns:
        raise ValueError(
            f"Cột '{metric}' không phải cột số hợp lệ trong dữ liệu. "
            f"Các cột số có sẵn: {profile.numeric_columns}"
        )

    group_by = task_dict.get("group_by")
    if group_by is not None and group_by not in profile.group_columns:
        raise ValueError(
            f"Cột nhóm '{group_by}' không hợp lệ trong dữ liệu. "
            f"Các cột nhóm có sẵn: {profile.group_columns}"
        )
    if task_type == "comparison" and group_by is None:
        raise ValueError('Loại phân tích "comparison" bắt buộc phải có group_by.')

    find = task_dict.get("find")
    if find is not None and find not in ALLOWED_FIND:
        raise ValueError(
            f"Giá trị find='{find}' không hợp lệ. Chỉ chấp nhận: {sorted(ALLOWED_FIND)}"
        )

    return AnalysisTask(type=task_type, metric=metric, group_by=group_by, find=find)


def _parse_and_validate(question: str, raw: dict, profile: DataProfile) -> AnalysisGoal:
    """Chuyển dict thô (từ LLM) thành AnalysisGoal đã được validate đầy đủ."""
    time_scope = raw.get("time_scope", _DEFAULT_TIME_SCOPE)
    if time_scope not in ALLOWED_TIME_SCOPES:
        logger.warning(
            "LLM tra ve time_scope khong hop le: %r -> dung mac dinh %r (FR-11)",
            time_scope, _DEFAULT_TIME_SCOPE,
        )
        time_scope = _DEFAULT_TIME_SCOPE

    time_start, time_end = _resolve_time_range(
        time_scope,
        profile,
        custom_start=raw.get("custom_start"),
        custom_end=raw.get("custom_end"),
    )

    raw_tasks = raw.get("tasks")
    if not raw_tasks or not isinstance(raw_tasks, list):
        raise ValueError("LLM không trả về danh sách 'tasks' hợp lệ (rỗng hoặc sai kiểu).")

    tasks = [_validate_task(t, profile) for t in raw_tasks]

    return AnalysisGoal(
        question=question,
        time_scope=time_scope,
        time_start=time_start,
        time_end=time_end,
        tasks=tasks,
    )


def interpret(question: str, profile: DataProfile, llm: LLMClient) -> AnalysisGoal:
    """Phân rã câu hỏi tự do thành mục tiêu phân tích có cấu trúc.

    Args:
        question: câu hỏi tự do của người dùng (tiếng Việt).
        profile: DataProfile do O1 sinh ra — dùng làm ngữ cảnh nền để
            LLM chỉ được chọn tên cột có thật (grounding).
        llm: một LLMClient (ví dụ ClaudeClient()). BẮT BUỘC — khác với
            O1.enrich(), module này không có "chế độ tắt LLM".

    Returns:
        AnalysisGoal đã validate: mọi metric/group_by đều tham chiếu
        đúng cột có thật trong `profile`.

    Raises:
        QuestionInterpretationError: khi LLM trả JSON lỗi, sai cấu
            trúc, hoặc tham chiếu cột không tồn tại.
    """
    prompt = _build_prompt(question, profile)

    try:
        raw = llm.complete_json(prompt)
    except json.JSONDecodeError as exc:
        raise QuestionInterpretationError(f"LLM trả về JSON không hợp lệ: {exc}") from exc

    if not isinstance(raw, dict):
        raise QuestionInterpretationError(
            f"LLM trả về kiểu {type(raw).__name__}, kỳ vọng dict/JSON object"
        )

    try:
        return _parse_and_validate(question, raw, profile)
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Question Interpreter thất bại với câu hỏi: %r. Lỗi: %s",
            question, exc, exc_info=True,
        )
        raise QuestionInterpretationError(str(exc)) from exc


# TODO (mở rộng — không bắt buộc cho MVP Tuần 1-8):
#   - Tự động retry (yêu cầu LLM sửa lại) khi grounding check thất bại,
#     tương tự cơ chế lọc lỗi nhiều tầng ở O3 (Tuần 4) — hiện tại O2
#     chỉ raise lỗi một lần, chưa tự sửa.
#   - Hỗ trợ nhiều "metric" trong một task (hiện chỉ 1 metric/task).
