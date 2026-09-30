"""Kiểm thử module O3a (Code Generator).

Dùng FakeLLM — không gọi mạng thật, không tốn API call.
Kiểm tra:
1. Scaffold đúng loại cho từng task.type.
2. previous_error được chèn vào prompt khi có.
3. CodeGenerationError khi LLM trả về nội dung không hợp lệ.
4. expected_outputs khớp với task.type.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.app.modules import code_generator as cg
from backend.app.modules import data_profiler
from backend.app.schemas import AnalysisTask, DataProfile

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def doanh_thu_profile() -> DataProfile:
    df = pd.read_csv(SAMPLES_DIR / "doanh_thu.csv")
    return data_profiler.profile(df)


class FakeLLM:
    """Client giả lập trả về code Python định sẵn."""

    def __init__(self, code: str = "def analyze(df):\n    return {'trend': df}"):
        self._code = code
        self.last_prompt: str = ""

    def complete_json(self, prompt: str) -> dict:
        self.last_prompt = prompt
        return {"code": self._code}


# ---------------------------------------------------------------------------
# Test scaffold đúng loại
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_type,expected_output", [
    ("trend", ["trend"]),
    ("comparison", ["comparison"]),
    ("growth_rate", ["growth_rate", "target"]),
])
def test_generate_returns_correct_expected_outputs(task_type, expected_output, doanh_thu_profile):
    """expected_outputs phải khớp task.type."""
    task = AnalysisTask(
        type=task_type,
        metric="Doanh_thu_trieu_vnd",
        group_by="Chi_nhanh" if task_type != "trend" else None,
        find="min" if task_type == "growth_rate" else None,
    )
    fake_code = f"def analyze(df):\n    return {{'{task_type}': None}}"
    llm = FakeLLM(code=fake_code)
    result = cg.generate(task, doanh_thu_profile, llm)
    assert result.expected_outputs == expected_output


def test_generate_prompt_contains_scaffold_for_trend(doanh_thu_profile):
    """Prompt cho trend phải chứa từ khóa 'trend' và metric thật."""
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)
    llm = FakeLLM()
    cg.generate(task, doanh_thu_profile, llm)
    assert "trend" in llm.last_prompt
    assert "Doanh_thu_trieu_vnd" in llm.last_prompt


def test_generate_prompt_contains_scaffold_for_comparison(doanh_thu_profile):
    """Prompt cho comparison phải chứa tên nhóm thật."""
    task = AnalysisTask(type="comparison", metric="Doanh_thu_trieu_vnd", group_by="Chi_nhanh", find=None)
    llm = FakeLLM(code="def analyze(df):\n    return {'comparison': None}")
    cg.generate(task, doanh_thu_profile, llm)
    assert "comparison" in llm.last_prompt
    assert "Chi_nhanh" in llm.last_prompt


def test_generate_prompt_contains_scaffold_for_growth_rate(doanh_thu_profile):
    """Prompt cho growth_rate phải đề cập find."""
    task = AnalysisTask(type="growth_rate", metric="Doanh_thu_trieu_vnd", group_by="Chi_nhanh", find="min")
    llm = FakeLLM(code="def analyze(df):\n    return {'growth_rate': None, 'target': 'A'}")
    cg.generate(task, doanh_thu_profile, llm)
    assert "growth_rate" in llm.last_prompt
    assert "min" in llm.last_prompt


# ---------------------------------------------------------------------------
# Test previous_error được chèn vào prompt
# ---------------------------------------------------------------------------

def test_generate_injects_previous_error_into_prompt(doanh_thu_profile):
    """Khi có previous_error, prompt phải chứa nội dung lỗi đó."""
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)
    llm = FakeLLM()
    error_msg = "NameError: name 'unknown_col' is not defined"
    cg.generate(task, doanh_thu_profile, llm, previous_error=error_msg)
    assert error_msg in llm.last_prompt


def test_generate_no_previous_error_prompt_clean(doanh_thu_profile):
    """Khi không có previous_error, prompt không chứa phần thông báo lỗi."""
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)
    llm = FakeLLM()
    cg.generate(task, doanh_thu_profile, llm, previous_error=None)
    assert "THÔNG BÁO LỖI LẦN TRƯỚC" not in llm.last_prompt


# ---------------------------------------------------------------------------
# Test CodeGenerationError
# ---------------------------------------------------------------------------

def test_generate_raises_when_llm_returns_no_analyze_function(doanh_thu_profile):
    """Nếu LLM trả code không có hàm analyze() → CodeGenerationError."""
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)
    llm = FakeLLM(code="x = 1 + 1")  # Không có def analyze
    with pytest.raises(cg.CodeGenerationError, match="analyze"):
        cg.generate(task, doanh_thu_profile, llm)


def test_generate_raises_for_unknown_task_type(doanh_thu_profile):
    """task.type không hợp lệ → CodeGenerationError ngay lập tức."""
    task = AnalysisTask.__new__(AnalysisTask)
    object.__setattr__(task, "type", "unknown_type")
    object.__setattr__(task, "metric", "Doanh_thu_trieu_vnd")
    object.__setattr__(task, "group_by", None)
    object.__setattr__(task, "find", None)
    llm = FakeLLM()
    with pytest.raises(cg.CodeGenerationError, match="scaffold"):
        cg.generate(task, doanh_thu_profile, llm)


def test_generate_extracts_code_from_markdown_block(doanh_thu_profile):
    """Code trong markdown code block phải được trích ra đúng."""
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)
    markdown_code = "```python\ndef analyze(df):\n    return {'trend': df}\n```"
    llm = FakeLLM(code=markdown_code)
    result = cg.generate(task, doanh_thu_profile, llm)
    assert "```" not in result.code
    assert "def analyze" in result.code
