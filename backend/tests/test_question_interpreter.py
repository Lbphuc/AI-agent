"""Kiểm thử module O2 (Question Interpreter).

Dùng client LLM GIẢ LẬP (không gọi mạng thật) để kiểm thử logic phân
rã + validate một cách xác định, không tốn API call — cùng nguyên tắc
đã áp dụng cho test_enrichment.py (O1 Stage 2).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.app.modules import data_profiler
from backend.app.modules import question_interpreter as qi

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


@pytest.fixture()
def doanh_thu_profile():
    df = pd.read_csv(SAMPLES_DIR / "doanh_thu.csv")
    return data_profiler.profile(df)


class FakeLLM:
    """Client giả lập trả về dict cố định (không gọi mạng)."""

    def __init__(self, response: dict):
        self._response = response

    def complete_json(self, prompt: str) -> dict:
        return self._response


def test_interpret_combined_question_matches_running_example(doanh_thu_profile):
    """Đúng kịch bản xuyên suốt đồ án: 'xu hướng 12 tháng + chi nhánh
    giảm mạnh nhất'. time_start/time_end phải khớp chính xác khoảng
    thời gian thật có trong doanh_thu.csv (2025-09 -> 2026-08)."""
    llm = FakeLLM({
        "time_scope": "last_12_months",
        "tasks": [
            {"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": None, "find": None},
            {"type": "growth_rate", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": "min"},
        ],
    })
    goal = qi.interpret(
        "Phân tích xu hướng doanh thu 12 tháng gần nhất và cho biết chi nhánh nào giảm mạnh nhất.",
        doanh_thu_profile,
        llm=llm,
    )

    assert goal.time_scope == "last_12_months"
    assert goal.time_start == "2025-09-01"
    assert goal.time_end == "2026-08-01"
    assert len(goal.tasks) == 2
    assert goal.tasks[0].type == "trend"
    assert goal.tasks[1].type == "growth_rate"
    assert goal.tasks[1].group_by == "Chi_nhanh"
    assert goal.tasks[1].find == "min"


def test_interpret_last_3_months_resolves_correct_window(doanh_thu_profile):
    llm = FakeLLM({
        "time_scope": "last_3_months",
        "tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh", "find": None}],
    })
    goal = qi.interpret("So sánh 3 tháng gần đây", doanh_thu_profile, llm=llm)

    assert goal.time_start == "2026-06-01"
    assert goal.time_end == "2026-08-01"


def test_interpret_custom_time_scope_passes_through(doanh_thu_profile):
    llm = FakeLLM({
        "time_scope": "custom",
        "custom_start": "2026-01-01",
        "custom_end": "2026-06-30",
        "tasks": [{"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": None, "find": None}],
    })
    goal = qi.interpret("Doanh thu từ tháng 1 đến tháng 6 năm nay", doanh_thu_profile, llm=llm)

    assert goal.time_start == "2026-01-01"
    assert goal.time_end == "2026-06-30"


def test_interpret_defaults_to_last_12_months_when_missing(doanh_thu_profile):
    """FR-11: câu hỏi không nói rõ thời gian -> mặc định 12 tháng gần nhất."""
    llm = FakeLLM({
        "tasks": [{"type": "trend", "metric": "Doanh_thu_trieu_vnd", "group_by": None, "find": None}],
    })
    goal = qi.interpret("Doanh thu thế nào?", doanh_thu_profile, llm=llm)

    assert goal.time_scope == "last_12_months"


def test_interpret_rejects_hallucinated_column(doanh_thu_profile):
    """Grounding check: LLM bịa cột không tồn tại -> phải raise lỗi rõ
    ràng, KHÔNG được để lọt xuống O3."""
    llm = FakeLLM({
        "time_scope": "all",
        "tasks": [{"type": "trend", "metric": "Loi_nhuan_khong_ton_tai", "group_by": None, "find": None}],
    })
    with pytest.raises(qi.QuestionInterpretationError, match="không phải cột số hợp lệ"):
        qi.interpret("Lợi nhuận thế nào?", doanh_thu_profile, llm=llm)


def test_interpret_rejects_comparison_without_group_by(doanh_thu_profile):
    llm = FakeLLM({
        "time_scope": "all",
        "tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": None, "find": None}],
    })
    with pytest.raises(qi.QuestionInterpretationError, match="comparison"):
        qi.interpret("So sánh gì đó", doanh_thu_profile, llm=llm)


def test_interpret_rejects_invalid_task_type(doanh_thu_profile):
    llm = FakeLLM({
        "time_scope": "all",
        "tasks": [{"type": "seasonal_forecast", "metric": "Doanh_thu_trieu_vnd", "group_by": None, "find": None}],
    })
    with pytest.raises(qi.QuestionInterpretationError, match="không hợp lệ"):
        qi.interpret("Dự báo mùa vụ", doanh_thu_profile, llm=llm)


def test_interpret_rejects_empty_tasks(doanh_thu_profile):
    llm = FakeLLM({"time_scope": "all", "tasks": []})
    with pytest.raises(qi.QuestionInterpretationError):
        qi.interpret("Câu hỏi mơ hồ không liên quan gì đến dữ liệu", doanh_thu_profile, llm=llm)


def test_interpret_rejects_non_dict_response(doanh_thu_profile):
    class NonDictLLM:
        def complete_json(self, prompt):
            return ["không phải dict"]

    with pytest.raises(qi.QuestionInterpretationError):
        qi.interpret("Câu hỏi bất kỳ", doanh_thu_profile, llm=NonDictLLM())


def test_interpret_logs_warning_on_failure(doanh_thu_profile, caplog):
    llm = FakeLLM({"time_scope": "all", "tasks": []})
    with caplog.at_level("WARNING"):
        with pytest.raises(qi.QuestionInterpretationError):
            qi.interpret("Câu hỏi mơ hồ", doanh_thu_profile, llm=llm)

    assert any("thất bại" in rec.message for rec in caplog.records)
