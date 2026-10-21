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
from ..schemas import (
    AnalysisGoal,
    AnalysisLevel,
    AnalysisTask,
    ChartHint,
    DataProfile,
    FindMode,
    TaskType,
    TimeScope,
)

logger = logging.getLogger(__name__)

# Lấy đúng tập giá trị hợp lệ từ chính Literal đã khai báo trong
# schemas.py (KHÔNG liệt kê lại thủ công ở đây) - tránh 2 nơi lệch nhau
# khi sau này có ai đó sửa schemas.py mà quên sửa chỗ này.
ALLOWED_TASK_TYPES: set[str] = set(typing.get_args(TaskType))
ALLOWED_FIND: set[str] = set(typing.get_args(FindMode))
ALLOWED_TIME_SCOPES: set[str] = set(typing.get_args(TimeScope))
ALLOWED_CHART_HINTS: set[str] = set(typing.get_args(ChartHint))

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
JSON: {"objective": "overview", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": null, "find": null}
]}

Ví dụ 2 (xác định đóng góp vào mức thay đổi tổng thể):
Câu hỏi: "Yếu tố nào đóng góp lớn nhất vào thay đổi Sales?"
JSON: {"objective": "contribution_to_change", "time_scope": "last_12_months", "levels": ["diagnostic", "descriptive"], "tasks": [
  {"type": "comparison", "metric": "Sales", "group_by": "Category", "find": null}
]}

Ví dụ 3 (tìm nhóm tăng trưởng mạnh nhất):
Câu hỏi: "Category nào tăng trưởng mạnh nhất?"
JSON: {"objective": "top_growers", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "growth_rate", "metric": "Sales", "group_by": "Category", "find": "max"}
]}

Ví dụ 4 (tìm nhóm làm giảm nhiều nhất / sụt giảm mạnh nhất):
Câu hỏi: "Category nào làm giảm Sales nhiều nhất?"
JSON: {"objective": "top_decliners", "time_scope": "last_12_months", "levels": ["descriptive", "diagnostic"], "tasks": [
  {"type": "growth_rate", "metric": "Sales", "group_by": "Category", "find": "min"}
]}

Ví dụ 5 (so sánh quy mô lớn nhất / cao nhất):
Câu hỏi: "Ship Mode nào có doanh thu cao nhất?"
JSON: {"objective": "comparison", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "comparison", "metric": "Sales", "group_by": "Ship_Mode", "find": "max"}
]}

Ví dụ 6 (đề xuất hành động / ưu tiên chiến lược):
Câu hỏi: "Nên ưu tiên Ship Mode nào để cải thiện Sales?"
JSON: {"objective": "prescriptive_action", "time_scope": "last_12_months", "levels": ["descriptive", "diagnostic", "prescriptive"], "tasks": [
  {"type": "comparison", "metric": "Sales", "group_by": "Ship_Mode", "find": null}
]}

Ví dụ 7 (dự báo tương lai kèm số kỳ):
Câu hỏi: "Xu hướng Sales trong ba kỳ tiếp theo ra sao?"
JSON: {"objective": "forecast", "time_scope": "last_12_months", "forecast_horizon": 3, "levels": ["descriptive", "forecast"], "tasks": [
  {"type": "trend", "metric": "Sales", "group_by": null, "find": null}
]}

Ví dụ 8 (khoảng thời gian tùy chỉnh):
Câu hỏi: "Doanh thu từ tháng 1 đến tháng 6 năm nay thế nào?"
JSON: {"objective": "overview", "time_scope": "custom", "custom_start": "2026-01", "custom_end": "2026-06", "levels": ["descriptive"], "tasks": [
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

Chỉ có 3 loại phân tích ("type") hợp lệ trong tasks:
- "trend": xu hướng một chỉ số theo thời gian (không cần group_by)
- "comparison": so sánh một chỉ số giữa các nhóm (BẮT BUỘC có group_by)
- "growth_rate": tính % tăng/giảm theo nhóm; dùng "find":"min" để tìm
  nhóm giảm/tăng ít nhất, "find":"max" để tìm nhóm tăng nhiều nhất

Trường "objective" (mục tiêu cốt lõi):
- "overview": tổng quan tình hình chung
- "comparison": so sánh quy mô giữa các nhóm
- "top_growers": tìm nhóm tăng trưởng mạnh nhất
- "top_decliners": tìm nhóm giảm sút nhiều nhất / làm giảm nhiều nhất
- "contribution_to_change": xác định mức đóng góp vào thay đổi tổng thể
- "forecast": dự báo xu hướng tương lai
- "prescriptive_action": đề xuất hành động / nên ưu tiên gì để cải thiện

Chỉ có 5 giá trị "time_scope" hợp lệ: "all", "last_3_months",
"last_6_months", "last_12_months", "custom". CHỈ chọn NHÃN, KHÔNG tự
tính ngày cụ thể. Nếu chọn "custom", thêm 2 trường "custom_start" và
"custom_end" dạng "YYYY-MM". Nếu câu hỏi không nói rõ khoảng thời
gian, dùng "last_12_months".

Trường "levels": danh sách các mức phân tích mà câu hỏi đang hỏi (luôn gồm "descriptive"):
- "diagnostic": hỏi VÌ SAO / do đâu / điều gì kéo tăng–giảm / yếu tố đóng góp / nguyên nhân
- "forecast": hỏi TƯƠNG LAI: sắp tới, quý tới, dự báo, dự kiến, các kỳ tiếp theo
- "prescriptive": hỏi NÊN LÀM GÌ / đề xuất / khuyến nghị / cần ưu tiên gì để cải thiện
Chỉ thêm khi câu hỏi nói rõ.

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

    # chart_hint: chi la goi y tham khao tham my, KHONG bat buoc dung (fail em)
    # Neu LLM tra gia tri la, bo qua thay vi raise loi lam hong ca cau tra loi
    chart_hint = task_dict.get("chart_hint")
    if chart_hint is not None and chart_hint not in ALLOWED_CHART_HINTS:
        logger.warning(
            "chart_hint khong hop le: %r -> bo qua (chi chap nhan: %s)",
            chart_hint, sorted(ALLOWED_CHART_HINTS),
        )
        chart_hint = None

    return AnalysisTask(type=task_type, metric=metric, group_by=group_by, find=find, chart_hint=chart_hint)


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

    # Phan rã levels
    raw_levels = raw.get("levels")
    parsed_levels: list[AnalysisLevel] = ["descriptive"]
    if isinstance(raw_levels, list):
        for lvl in raw_levels:
            if lvl in ("diagnostic", "forecast", "prescriptive") and lvl not in parsed_levels:
                parsed_levels.append(lvl)

    # Heuristic bo sung neu LLM quen kem levels theo tu khoa ro rang
    q_lower = question.lower()
    if any(w in q_lower for w in ["vì sao", "tai sao", "tại sao", "nguyên nhân", "do đâu", "ly do", "lý do", "đóng góp"]):
        if "diagnostic" not in parsed_levels:
            parsed_levels.append("diagnostic")
    if any(w in q_lower for w in ["dự báo", "du bao", "dự đoán", "du doan", "quý tới", "tháng tới", "sắp tới", "tương lai", "kỳ tới", "tiếp theo"]):
        if "forecast" not in parsed_levels:
            parsed_levels.append("forecast")
    if any(w in q_lower for w in ["nên làm gì", "đề xuất", "de xuat", "khuyến nghị", "khuyen nghi", "chiến lược", "chien luoc", "ưu tiên", "để cải thiện"]):
        if "prescriptive" not in parsed_levels:
            parsed_levels.append("prescriptive")

    # Xác định objective cốt lõi theo mục 4.3 & 4.4 của writing-block (1).md
    raw_objective = raw.get("objective")
    objective = None
    if raw_objective in ("overview", "comparison", "top_growers", "top_decliners", "contribution_to_change", "forecast", "prescriptive_action"):
        objective = raw_objective
    else:
        if any(w in q_lower for w in ["đóng góp", "dong gop", "thay đổi tổng", "thay doi tong", "đóng góp lớn nhất"]):
            objective = "contribution_to_change"
        elif any(w in q_lower for w in ["giảm nhiều nhất", "giam nhieu nhat", "giảm mạnh nhất", "giam manh nhat", "làm giảm", "lam giam"]):
            objective = "top_decliners"
        elif any(w in q_lower for w in ["tăng trưởng mạnh nhất", "tang truong manh nhat", "tăng mạnh nhất", "tang manh nhat", "tăng nhiều nhất"]):
            objective = "top_growers"
        elif any(w in q_lower for w in ["nên ưu tiên", "nen uu tien", "đề xuất", "de xuat", "khuyến nghị", "khuyen nghi", "để cải thiện"]):
            objective = "prescriptive_action"
        elif any(w in q_lower for w in ["dự báo", "du bao", "sắp tới", "sap toi", "quý tới", "quy toi", "kỳ tới", "tiếp theo"]):
            objective = "forecast"
        elif any(w in q_lower for w in ["cao nhất", "lớn nhất", "nhiều nhất", "so sánh"]):
            objective = "comparison"
        else:
            objective = "overview"

    # Bảo toàn mục tiêu: Đồng bộ tasks và levels theo objective (đưa level trọng tâm lên đầu)
    if objective == "contribution_to_change":
        if "diagnostic" not in parsed_levels:
            parsed_levels.append("diagnostic")
        parsed_levels = ["diagnostic"] + [lvl for lvl in parsed_levels if lvl != "diagnostic"]
    elif objective == "top_decliners":
        if tasks and tasks[0].find != "min":
            tasks[0].find = "min"
        if "diagnostic" not in parsed_levels:
            parsed_levels.append("diagnostic")
        parsed_levels = ["diagnostic"] + [lvl for lvl in parsed_levels if lvl != "diagnostic"]
    elif objective == "top_growers":
        if tasks and tasks[0].find != "max":
            tasks[0].find = "max"
    elif objective == "prescriptive_action":
        if "diagnostic" not in parsed_levels:
            parsed_levels.append("diagnostic")
        if "prescriptive" not in parsed_levels:
            parsed_levels.append("prescriptive")
        parsed_levels = ["prescriptive"] + [lvl for lvl in parsed_levels if lvl != "prescriptive"]
    elif objective == "forecast":
        if "forecast" not in parsed_levels:
            parsed_levels.append("forecast")
        parsed_levels = ["forecast"] + [lvl for lvl in parsed_levels if lvl != "forecast"]

    primary_metric = tasks[0].metric if tasks else None
    primary_dimension = tasks[0].group_by if tasks else None

    # Tự động trích xuất forecast_horizon nếu có
    forecast_horizon = raw.get("forecast_horizon")
    if not forecast_horizon:
        if any(w in q_lower for w in ["ba kỳ", "3 kỳ", "3 thang", "3 tháng", "quý tới"]):
            forecast_horizon = 3
        elif any(w in q_lower for w in ["sáu kỳ", "6 kỳ", "6 thang", "6 tháng"]):
            forecast_horizon = 6
        elif "forecast" in parsed_levels:
            forecast_horizon = 3

    return AnalysisGoal(
        question=question,
        time_scope=time_scope,
        time_start=time_start,
        time_end=time_end,
        tasks=tasks,
        levels=parsed_levels,
        objective=objective,
        metric=primary_metric,
        dimension=primary_dimension,
        forecast_horizon=forecast_horizon,
        analysis_methods=parsed_levels,
    )


def revalidate_goal(goal_input: AnalysisGoal | dict, profile: DataProfile) -> AnalysisGoal:
    """Validate lại toàn bộ AnalysisGoal gửi từ client với DataProfile mới.
    Đảm bảo mọi metric, group_by đều có thật, chặn inject cột lạ hoặc task lạ.
    """
    if isinstance(goal_input, AnalysisGoal):
        data = goal_input.model_dump()
    elif isinstance(goal_input, dict):
        data = goal_input
    else:
        raise ValueError("goal phải là AnalysisGoal hoặc dict.")

    question = str(data.get("question", ""))
    return _parse_and_validate(question, data, profile)


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
    except Exception as exc:
        # Bắt mọi lỗi API (503 UNAVAILABLE, network error, ...) — tránh 500
        logger.error("Lỗi khi gọi LLM API: %s", exc, exc_info=True)
        raise QuestionInterpretationError(f"Lỗi khi gọi LLM API: {exc}") from exc

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
