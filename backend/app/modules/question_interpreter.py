"""Module O2 — Question Interpreter.

Nhận câu hỏi tự do của người dùng (tiếng Việt) + DataProfile từ O1,
sinh ra một AnalysisGoal có cấu trúc để O3 (Tuần 4) sinh mã phân tích
tương ứng.
"""
from __future__ import annotations

import json
import logging
import re
import typing

import pandas as pd

from ..llm_client import LLMClient
from ..schemas import (
    AggFunc,
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

ALLOWED_TASK_TYPES: set[str] = set(typing.get_args(TaskType))
ALLOWED_FIND: set[str] = set(typing.get_args(FindMode))
ALLOWED_AGG: set[str] = set(typing.get_args(AggFunc))
ALLOWED_TIME_SCOPES: set[str] = set(typing.get_args(TimeScope))
ALLOWED_CHART_HINTS: set[str] = set(typing.get_args(ChartHint))

_MONTHS_BY_SCOPE = {"last_3_months": 3, "last_6_months": 6, "last_12_months": 12}

_DEFAULT_TIME_SCOPE = "last_12_months"  # theo FR-11 (giá trị mặc định hợp lý)


class QuestionInterpretationError(Exception):
    """Raised khi không thể phân rã câu hỏi thành AnalysisGoal hợp lệ."""


FEW_SHOT_EXAMPLES = """Ví dụ 1 (xu hướng theo thời gian):
Câu hỏi: "Doanh thu thay đổi thế nào theo từng tháng?"
JSON: {"objective": "overview", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": null, "find": null, "agg": "sum"}
]}

Ví dụ 2 (xác định đóng góp vào mức thay đổi tổng thể):
Câu hỏi: "Yếu tố nào đóng góp lớn nhất vào thay đổi Sales?"
JSON: {"objective": "contribution_to_change", "time_scope": "last_12_months", "levels": ["descriptive", "diagnostic"], "tasks": [
  {"type": "comparison", "metric": "Sales", "group_by": "Category", "find": "max", "agg": "sum"}
]}

Ví dụ 3 (tìm nhóm tăng trưởng mạnh nhất):
Câu hỏi: "Category nào tăng trưởng mạnh nhất?"
JSON: {"objective": "top_growers", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "growth_rate", "metric": "Sales", "group_by": "Category", "find": "max", "agg": "sum"}
]}

Ví dụ 4 (tìm nhóm làm giảm nhiều nhất / sụt giảm mạnh nhất):
Câu hỏi: "Category nào làm giảm Sales nhiều nhất?"
JSON: {"objective": "top_decliners", "time_scope": "last_12_months", "levels": ["descriptive", "diagnostic"], "tasks": [
  {"type": "growth_rate", "metric": "Sales", "group_by": "Category", "find": "min", "agg": "sum"}
]}

Ví dụ 5 (so sánh quy mô lớn nhất / cao nhất hoặc có điều kiện lọc):
Câu hỏi: "Danh mục nào có số lượng bán nhiều nhất tại TP.HCM?"
JSON: {"objective": "comparison", "target": "TP.HCM", "time_scope": "last_12_months", "levels": ["descriptive"], "tasks": [
  {"type": "comparison", "metric": "So_luong", "group_by": "Danh_muc", "find": "max", "agg": "sum", "filters": {"Chi_nhanh": "TP.HCM"}}
]}

Ví dụ 6 (đề xuất hành động / ưu tiên chiến lược):
Câu hỏi: "Nên ưu tiên Ship Mode nào để cải thiện Sales?"
JSON: {"objective": "prescriptive_action", "time_scope": "last_12_months", "levels": ["descriptive", "diagnostic", "prescriptive"], "tasks": [
  {"type": "comparison", "metric": "Sales", "group_by": "Ship Mode", "find": null, "agg": "sum"}
]}

Ví dụ 7 (dự báo tương lai kèm số kỳ):
Câu hỏi: "Xu hướng Sales trong ba kỳ tiếp theo ra sao?"
JSON: {"objective": "forecast", "time_scope": "last_12_months", "forecast_horizon": 3, "levels": ["descriptive", "forecast"], "tasks": [
  {"type": "trend", "metric": "Sales", "group_by": null, "find": null, "agg": "sum"}
]}

Ví dụ 8 (khoảng thời gian tùy chỉnh hoặc tính trung bình):
Câu hỏi: "Chi phí marketing trung bình mỗi tháng từ tháng 1 đến tháng 6 năm 2025?"
JSON: {"objective": "overview", "time_scope": "custom", "custom_start": "2025-01", "custom_end": "2025-06", "levels": ["descriptive"], "tasks": [
  {"type": "trend", "metric": "Chi_phi_marketing_trieu_vnd", "group_by": null, "find": null, "agg": "mean"}
]}"""


def _build_prompt(question: str, profile: DataProfile) -> str:
    """Xây prompt few-shot, gắn chặt (ground) vào tên cột THẬT và mẫu giá trị của dataset hiện tại."""
    numeric_list = ", ".join(f'"{c}"' for c in profile.numeric_columns) or "(không có)"
    group_list = ", ".join(f'"{c}"' for c in profile.group_columns) or "(không có)"
    time_info = (
        f'"{profile.time_column}" (dữ liệu có từ {profile.time_min} đến {profile.time_max})'
        if profile.time_column
        else "(dữ liệu này không có cột thời gian)"
    )

    col_samples_lines = []
    for col in profile.columns:
        if col.name in profile.group_columns and col.samples:
            sample_str = ", ".join(f'"{s}"' for s in col.samples[:5])
            col_samples_lines.append(f'  + "{col.name}": ví dụ [{sample_str}]')
    samples_block = "\n".join(col_samples_lines) if col_samples_lines else "  (không có mẫu nhóm)"

    return f"""Bạn là một chuyên gia phân tích dữ liệu kinh doanh. Nhiệm vụ: đọc một
câu hỏi tiếng Việt và chuyển thành kế hoạch phân tích có cấu trúc sát đúng ý định câu hỏi.
BẮT BUỘC chỉ dùng đúng tên cột liệt kê dưới đây — TUYỆT ĐỐI KHÔNG bịa
thêm cột không tồn tại.

Cột thời gian: {time_info}
Cột nhóm (dùng cho "group_by" hoặc "filters"): {group_list}
Giá trị mẫu trong các cột nhóm:
{samples_block}
Cột số (dùng cho "metric"): {numeric_list}

Chỉ có 3 loại phân tích ("type") hợp lệ trong tasks:
- "trend": xu hướng một chỉ số theo thời gian (không cần group_by)
- "comparison": so sánh một chỉ số giữa các nhóm (BẮT BUỘC có group_by). Nếu hỏi "tỷ trọng / cơ cấu / phần trăm đóng góp", thêm "chart_hint": "pie".
- "growth_rate": tính % tăng/giảm theo nhóm giữa đầu kỳ và cuối kỳ; dùng "find":"min" để tìm nhóm giảm mạnh nhất, "find":"max" để tìm nhóm tăng mạnh nhất.

Các trường bổ sung trong mỗi task:
- "agg": hàm tổng hợp ("sum" mặc định cho doanh thu/số lượng/lợi nhuận; "mean" khi câu hỏi nói rõ "trung bình / bình quân"; "max" hoặc "min" hoặc "count" nếu hỏi tương ứng).
- "filters": object lọc theo giá trị cụ thể nếu câu hỏi chỉ định rõ một đối tượng (ví dụ: {{"Chi_nhanh": "TP.HCM"}}). Chỉ lọc trên cột KHÁC với cột "group_by" của task đó (trừ khi câu hỏi chỉ hỏi xu hướng "trend" của riêng 1 nhóm).
- "top_k": số nguyên nếu câu hỏi hỏi "Top 3", "Top 5", "5 nhóm đầu"...

Trường "objective" (mục tiêu cốt lõi của câu hỏi):
- "overview": tổng quan hoặc xu hướng chung theo thời gian
- "comparison": so sánh quy mô / tỷ trọng giữa các nhóm
- "top_growers": tìm nhóm tăng trưởng mạnh nhất
- "top_decliners": tìm nhóm giảm sút nhiều nhất / làm giảm nhiều nhất
- "contribution_to_change": xác định yếu tố đóng góp lớn nhất vào sự thay đổi / biến động tổng thể
- "forecast": dự báo xu hướng tương lai
- "prescriptive_action": đề xuất hành động / nên ưu tiên gì để cải thiện

Chỉ có 5 giá trị "time_scope" hợp lệ: "all", "last_3_months",
"last_6_months", "last_12_months", "custom".
- Nếu câu hỏi nêu năm hoặc khoảng tháng cụ thể (ví dụ "năm 2025", "quý 3 năm 2024", "từ tháng 1 đến tháng 6/2025"), chọn "custom" và điền "custom_start", "custom_end" dạng "YYYY-MM-DD" hoặc "YYYY-MM".
- Nếu câu hỏi không nói rõ khoảng thời gian, dùng "last_12_months".

Trường "levels": danh sách các mức phân tích mà câu hỏi đang hỏi (luôn gồm "descriptive"):
- "diagnostic": CHỈ thêm khi hỏi VÌ SAO / tại sao / do đâu / nguyên nhân / yếu tố nào kéo giảm hoặc đóng góp vào THAY ĐỔI.
- "forecast": CHỈ thêm khi hỏi TƯƠNG LAI: sắp tới, quý tới, tháng tới, dự báo, dự kiến, ước tính các kỳ tiếp theo.
- "prescriptive": CHỈ thêm khi hỏi NÊN LÀM GÌ / đề xuất / khuyến nghị / giải pháp / chiến lược / cần ưu tiên gì.

{FEW_SHOT_EXAMPLES}

Bây giờ hãy phân tích câu hỏi thật sau. CHỈ trả về một JSON object duy
nhất đúng định dạng như các ví dụ trên, không kèm giải thích hay
markdown:

Câu hỏi: "{question}"
JSON:"""


def _extract_explicit_year_or_quarter(question: str, profile: DataProfile) -> tuple[str | None, str | None]:
    """Trích xuất năm hoặc quý cụ thể nếu câu hỏi có nhắc rõ (ví dụ: 'năm 2025', 'quý 3 năm 2024', 'tháng 12 năm 2024')."""
    if not profile.time_column:
        return None, None
    q_lower = question.lower()

    m_month_year = re.search(r"tháng\s*(\d{1,2})\s*(?:năm|/|-)\s*(20\d{2})", q_lower)
    if m_month_year:
        month = int(m_month_year.group(1))
        year = int(m_month_year.group(2))
        if 1 <= month <= 12:
            start_ts = pd.Timestamp(year=year, month=month, day=1)
            end_ts = start_ts + pd.offsets.MonthEnd(1)
            return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")

    m_quarter_year = re.search(r"quý\s*([1-4])\s*(?:năm|/|-)?\s*(20\d{2})", q_lower)
    if m_quarter_year:
        q_num = int(m_quarter_year.group(1))
        year = int(m_quarter_year.group(2))
        start_month = (q_num - 1) * 3 + 1
        end_month = start_month + 2
        start_ts = pd.Timestamp(year=year, month=start_month, day=1)
        end_ts = pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(1)
        return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")

    m_year = re.search(r"năm\s+(20\d{2})\b", q_lower)
    if m_year:
        year = int(m_year.group(1))
        return f"{year}-01-01", f"{year}-12-31"

    return None, None


def _resolve_time_range(
    time_scope: str,
    profile: DataProfile,
    custom_start: str | None = None,
    custom_end: str | None = None,
    question: str = "",
) -> tuple[str | None, str | None]:
    """Tính time_start/time_end THẬT bằng Python — KHÔNG giao cho LLM."""
    if time_scope == "custom":
        if custom_start or custom_end:
            return custom_start, custom_end
        exp_start, exp_end = _extract_explicit_year_or_quarter(question, profile)
        if exp_start or exp_end:
            return exp_start, exp_end
        time_scope = _DEFAULT_TIME_SCOPE

    if time_scope == "all" or profile.time_max is None:
        return profile.time_min, profile.time_max

    months = _MONTHS_BY_SCOPE.get(time_scope)
    if months is None:
        return profile.time_min, profile.time_max

    end = pd.Timestamp(profile.time_max)
    start = end.replace(day=1) - pd.DateOffset(months=months - 1)
    if profile.time_min is not None:
        start = max(start, pd.Timestamp(profile.time_min))

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _validate_task(task_dict: dict, profile: DataProfile, question: str = "") -> AnalysisTask:
    """Kiểm tra 1 task do LLM sinh ra có tham chiếu đúng cột THẬT không."""
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

    chart_hint = task_dict.get("chart_hint")
    if chart_hint is not None and chart_hint not in ALLOWED_CHART_HINTS:
        logger.warning(
            "chart_hint khong hop le: %r -> bo qua (chi chap nhan: %s)",
            chart_hint, sorted(ALLOWED_CHART_HINTS),
        )
        chart_hint = None

    q_lower = question.lower()
    if chart_hint is None and task_type == "comparison":
        if any(w in q_lower for w in ("tỷ trọng", "ty trong", "cơ cấu", "co cau", "chiếm bao nhiêu", "phần trăm")):
            chart_hint = "pie"

    agg = task_dict.get("agg")
    if agg not in ALLOWED_AGG:
        agg = None
    if agg is None and any(w in q_lower for w in ("trung bình", "trung binh", "bình quân", "binh quan")):
        agg = "mean"

    raw_filters = task_dict.get("filters")
    valid_filters: dict[str, str] | None = None
    if isinstance(raw_filters, dict):
        cleaned = {
            str(k): str(v)
            for k, v in raw_filters.items()
            if k in profile.group_columns and v is not None and str(v).strip()
            and (task_type == "trend" or k != group_by)
        }
        if cleaned:
            valid_filters = cleaned

    top_k = task_dict.get("top_k")
    if not isinstance(top_k, int) or top_k <= 0:
        m_top = re.search(r"\btop\s*(\d+)\b", q_lower)
        top_k = int(m_top.group(1)) if m_top else None

    return AnalysisTask(
        type=task_type,
        metric=metric,
        group_by=group_by,
        find=find,
        chart_hint=chart_hint,
        agg=agg,
        filters=valid_filters,
        top_k=top_k,
    )


def _detect_target_from_question(question: str, profile: DataProfile) -> tuple[str | None, dict[str, str] | None]:
    """Dò tìm thực thể cụ thể (ví dụ 'Đà Nẵng', 'TP.HCM', 'Điện tử') được nhắc trực tiếp trong câu hỏi."""
    q_lower = question.lower()
    for col in profile.columns:
        if col.name not in profile.group_columns:
            continue
        for sample in col.samples:
            s_clean = str(sample).strip()
            if len(s_clean) >= 2 and s_clean.lower() in q_lower:
                return s_clean, {col.name: s_clean}
    return None, None


def _parse_and_validate(question: str, raw: dict, profile: DataProfile) -> AnalysisGoal:
    """Chuyển dict thô (từ LLM hoặc client) thành AnalysisGoal đã được validate đầy đủ."""
    time_scope = raw.get("time_scope", _DEFAULT_TIME_SCOPE)
    if time_scope not in ALLOWED_TIME_SCOPES:
        logger.warning(
            "LLM tra ve time_scope khong hop le: %r -> dung mac dinh %r (FR-11)",
            time_scope, _DEFAULT_TIME_SCOPE,
        )
        time_scope = _DEFAULT_TIME_SCOPE

    custom_start = raw.get("custom_start") or (raw.get("time_start") if time_scope == "custom" else None)
    custom_end = raw.get("custom_end") or (raw.get("time_end") if time_scope == "custom" else None)

    time_start, time_end = _resolve_time_range(
        time_scope,
        profile,
        custom_start=custom_start,
        custom_end=custom_end,
        question=question,
    )

    raw_tasks = raw.get("tasks")
    if not raw_tasks or not isinstance(raw_tasks, list):
        raise ValueError("LLM không trả về danh sách 'tasks' hợp lệ (rỗng hoặc sai kiểu).")

    tasks = [_validate_task(t, profile, question=question) for t in raw_tasks]

    raw_levels = raw.get("levels")
    parsed_levels: list[AnalysisLevel] = ["descriptive"]
    if isinstance(raw_levels, list):
        for lvl in raw_levels:
            if lvl in ("diagnostic", "forecast", "prescriptive") and lvl not in parsed_levels:
                parsed_levels.append(lvl)

    q_lower = question.lower()
    is_pure_share_question = any(w in q_lower for w in ["tỷ trọng", "ty trong", "cơ cấu", "co cau", "chiếm bao nhiêu"]) and not any(
        w in q_lower for w in ["vì sao", "tại sao", "nguyên nhân", "thay đổi", "biến động", "giảm", "tăng"]
    )

    if is_pure_share_question:
        parsed_levels = ["descriptive"]
    else:
        diag_keywords = [
            "vì sao", "tai sao", "tại sao", "nguyên nhân", "nguyen nhan",
            "do đâu", "do dau", "ly do", "lý do",
            "kéo giảm", "keo giam", "kéo tăng", "keo tang",
            "yếu tố nào", "yeu to nao", "ảnh hưởng", "anh huong",
            "đóng góp lớn nhất vào", "đóng góp vào thay đổi", "thay đổi tổng",
        ]
        if any(w in q_lower for w in diag_keywords):
            if "diagnostic" not in parsed_levels:
                parsed_levels.append("diagnostic")

    fc_keywords = [
        "dự báo", "du bao", "dự đoán", "du doan", "dự kiến", "du kien",
        "ước tính", "uoc tinh", "quý tới", "tháng tới", "tháng sau", "năm sau",
        "sắp tới", "sap toi", "tương lai", "kỳ tới", "tiếp theo", "thời gian tới",
    ]
    is_prescriptive_only_q = any(w in q_lower for w in ["ưu tiên hành động", "chiến lược nào", "cần ưu tiên"]) and not any(
        w in q_lower for w in ["dự báo", "dự kiến", "dự đoán", "ước tính", "ra sao"]
    )
    if any(w in q_lower for w in fc_keywords) and not is_prescriptive_only_q:
        if "forecast" not in parsed_levels:
            parsed_levels.append("forecast")

    pres_keywords = [
        "nên làm gì", "nên ưu tiên", "nen uu tien", "đề xuất", "de xuat",
        "khuyến nghị", "khuyen nghi", "chiến lược", "chien luoc",
        "ưu tiên", "để cải thiện", "giải pháp", "khắc phục", "gợi ý hướng đi", "thúc đẩy",
    ]
    if any(w in q_lower for w in pres_keywords):
        if "prescriptive" not in parsed_levels:
            parsed_levels.append("prescriptive")

    raw_objective = raw.get("objective")
    objective: str | None = None

    if is_pure_share_question:
        objective = "comparison"
    elif any(
        w in q_lower for w in ["đóng góp lớn nhất", "đóng góp vào thay đổi", "thay đổi tổng", "yếu tố nào đóng góp"]
    ):
        objective = "contribution_to_change"
    elif any(w in q_lower for w in ["giảm nhiều nhất", "giam nhieu nhat", "giảm mạnh nhất", "giam manh nhat", "làm giảm", "lam giam", "kéo giảm", "sụt giảm mạnh"]):
        objective = "top_decliners"
    elif any(w in q_lower for w in ["tăng trưởng mạnh nhất", "tang truong manh nhat", "tăng mạnh nhất", "tang manh nhat", "tăng nhiều nhất"]):
        objective = "top_growers"
    elif any(w in q_lower for w in ["nên ưu tiên", "nen uu tien", "đề xuất", "de xuat", "khuyến nghị", "khuyen nghi", "để cải thiện", "nên làm gì", "giải pháp"]):
        objective = "prescriptive_action"
    elif any(w in q_lower for w in ["dự báo", "du bao", "dự kiến", "dự đoán", "ước tính", "sắp tới", "sap toi", "quý tới", "kỳ tới", "tiếp theo"]) and not is_prescriptive_only_q:
        objective = "forecast"
    elif raw_objective in ("overview", "comparison", "top_growers", "top_decliners", "contribution_to_change", "forecast", "prescriptive_action"):
        objective = raw_objective
    elif any(w in q_lower for w in ["cao nhất", "lớn nhất", "nhiều nhất", "so sánh", "tỷ trọng", "cơ cấu"]):
        objective = "comparison"
    else:
        objective = "overview"

    if objective == "contribution_to_change":
        if "diagnostic" not in parsed_levels:
            parsed_levels.append("diagnostic")
    elif objective == "top_decliners":
        for t in tasks:
            if t.type == "growth_rate" and t.find != "min":
                t.find = "min"
        if len(tasks) == 1 and tasks[0].find != "min":
            tasks[0].find = "min"
    elif objective == "top_growers":
        for t in tasks:
            if t.type == "growth_rate" and t.find != "max":
                t.find = "max"
        if len(tasks) == 1 and tasks[0].find != "max":
            tasks[0].find = "max"
    elif objective == "prescriptive_action":
        if "prescriptive" not in parsed_levels:
            parsed_levels.append("prescriptive")
    elif objective == "forecast":
        if "forecast" not in parsed_levels:
            parsed_levels.append("forecast")

    detected_target, detected_filter = _detect_target_from_question(question, profile)
    target = raw.get("target") or detected_target
    goal_filters = raw.get("filters") if isinstance(raw.get("filters"), dict) else detected_filter

    if goal_filters:
        for t in tasks:
            if not t.filters:
                applicable = {
                    k: v for k, v in goal_filters.items()
                    if k in profile.group_columns and (t.type == "trend" or k != t.group_by)
                }
                if applicable:
                    t.filters = applicable

    primary_metric = tasks[0].metric if tasks else None
    primary_dimension = next((t.group_by for t in tasks if t.group_by), None)

    forecast_horizon = raw.get("forecast_horizon")
    if not forecast_horizon:
        if any(w in q_lower for w in ["sáu kỳ", "6 kỳ", "6 thang", "6 tháng"]):
            forecast_horizon = 6
        elif any(w in q_lower for w in ["ba kỳ", "3 kỳ", "3 thang", "3 tháng", "quý tới"]):
            forecast_horizon = 3
        elif "forecast" in parsed_levels:
            forecast_horizon = 3

    return AnalysisGoal(
        question=question,
        time_scope=time_scope,
        time_start=time_start,
        time_end=time_end,
        custom_start=custom_start,
        custom_end=custom_end,
        tasks=tasks,
        levels=parsed_levels,
        objective=objective,
        metric=primary_metric,
        dimension=primary_dimension,
        target=target,
        filters=goal_filters,
        forecast_horizon=forecast_horizon,
        analysis_methods=parsed_levels,
    )


def revalidate_goal(goal_input: AnalysisGoal | dict, profile: DataProfile) -> AnalysisGoal:
    """Validate lại toàn bộ AnalysisGoal gửi từ client với DataProfile mới."""
    if isinstance(goal_input, AnalysisGoal):
        data = goal_input.model_dump()
    elif isinstance(goal_input, dict):
        data = goal_input
    else:
        raise ValueError("goal phải là AnalysisGoal hoặc dict.")

    question = str(data.get("question", ""))
    return _parse_and_validate(question, data, profile)


def interpret(question: str, profile: DataProfile, llm: LLMClient) -> AnalysisGoal:
    """Phân rã câu hỏi tự do thành mục tiêu phân tích có cấu trúc."""
    prompt = _build_prompt(question, profile)

    try:
        raw = llm.complete_json(prompt)
    except json.JSONDecodeError as exc:
        raise QuestionInterpretationError(f"LLM trả về JSON không hợp lệ: {exc}") from exc
    except Exception as exc:
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
