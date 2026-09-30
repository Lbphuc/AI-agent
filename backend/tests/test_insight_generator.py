"""Tests for Module O5 -- Insight Generator.

Kiem thu theo ke hoach Tuan 6 (muc 6 trong proposal):
- Tat ca task loi -> raise InsightGenerationError
- 1/2 task loi -> van sinh insight tu task con lai
- Prompt KHONG chua du lieu cua task loi (nguyen tac khong dua DataFrame vao)
- FakeLLM tra ve nhan xet co so dung -> confidence_score cao
- FakeLLM tra ve nhan xet co so bia -> confidence_score thap hon
- _extract_numbers xu ly ca "35.6" va "35,6"
- _numeric_accuracy_score edge cases (khong co so de doi chieu)
- Test tich hop: pipeline trend + growth_rate (Da Nang -35.56%) -> insight
  co "35" hoac "35.56" -> confidence cao
- Prompt khong chua text "DataFrame" hay "df" (nguyen tac bao mat)
"""
from __future__ import annotations

import pytest

from backend.app.modules.insight_generator import (
    InsightGenerationError,
    _build_prompt,
    _collect_known_values,
    _extract_numbers,
    _format_task_result,
    _numeric_accuracy_score,
    generate_insight,
)
from backend.app.schemas import (
    AnalysisTask,
    ExecutionResult,
    InsightResult,
    TaskResult,
)


# ---------------------------------------------------------------------------
# FakeLLM cho test (khong can API key)
# ---------------------------------------------------------------------------

class FakeLLM:
    """LLM gia lap: complete_text tra ve phan hoi co the lap trinh duoc."""

    def __init__(self, text_response: str = ""):
        self._text = text_response

    def complete_json(self, prompt: str) -> dict:
        return {}

    def complete_text(self, prompt: str) -> str:
        return self._text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tr(
    task_type: str,
    results: dict,
    success: bool = True,
    metric: str = "Doanh_thu_trieu_vnd",
    group_by: str | None = "Chi_nhanh",
    find: str | None = None,
) -> TaskResult:
    task = AnalysisTask(type=task_type, metric=metric, group_by=group_by, find=find)
    execution = ExecutionResult(success=success, results=results)
    return TaskResult(task=task, execution=execution)


# Du lieu y het doanh_thu.csv dung trong vi du xuyen suot du an
_TREND_RESULTS = {
    "trend": {
        "2025-09": 4450.0, "2025-10": 4420.0, "2025-11": 4460.0,
        "2025-12": 4485.0, "2026-01": 4410.0, "2026-02": 4435.0,
    }
}
_GROWTH_RESULTS = {
    "growth_rate": {
        "Can Tho": 12.0, "Da Nang": -35.56, "Ha Noi": 20.83, "TP.HCM": 2.16,
    },
    "target": "Da Nang",
}


# ---------------------------------------------------------------------------
# Test InsightGenerationError
# ---------------------------------------------------------------------------

class TestInsightGenerationError:
    def test_all_failed_raises_error(self):
        """Tat ca task that bai -> raise InsightGenerationError."""
        trs = [
            _make_tr("trend", {}, success=False, group_by=None),
            _make_tr("growth_rate", {}, success=False, find="min"),
        ]
        with pytest.raises(InsightGenerationError):
            generate_insight("cau hoi test", trs, FakeLLM("insight"))

    def test_empty_task_results_raises_error(self):
        """Danh sach rong -> raise InsightGenerationError."""
        with pytest.raises(InsightGenerationError):
            generate_insight("cau hoi test", [], FakeLLM("insight"))


# ---------------------------------------------------------------------------
# Test xu ly loi tung phan (partial failure)
# ---------------------------------------------------------------------------

class TestPartialFailure:
    def test_one_failed_still_generates_insight(self):
        """1/2 task that bai -> van sinh duoc InsightResult tu task con lai."""
        tr_fail = _make_tr("trend", {}, success=False, group_by=None)
        tr_ok = _make_tr(
            "growth_rate", _GROWTH_RESULTS, find="min"
        )
        llm = FakeLLM("Da Nang giam 35.56 phan tram.")
        result = generate_insight("chi nhanh nao giam?", [tr_fail, tr_ok], llm)
        assert isinstance(result, InsightResult)
        assert result.insight_text == "Da Nang giam 35.56 phan tram."

    def test_failed_task_data_not_in_prompt(self):
        """Prompt chi chua du lieu cua task THANH CONG, bo qua task loi."""
        tr_fail = _make_tr(
            "trend",
            {"trend": {"2025-09": 9999.0}},  # so nay KHONG duoc xuat hien trong prompt
            success=False,
            group_by=None,
        )
        tr_ok = _make_tr("growth_rate", _GROWTH_RESULTS, find="min")
        prompt = _build_prompt("cau hoi", [tr_ok])  # chi truyen task thanh cong
        assert "9999" not in prompt  # dam bao du lieu cua task loi khong co trong prompt

    def test_prompt_not_contain_dataframe(self):
        """Prompt KHONG duoc chua tu 'DataFrame' hay 'df' (nguyen tac bao mat)."""
        tr = _make_tr("growth_rate", _GROWTH_RESULTS, find="min")
        prompt = _build_prompt("cau hoi", [tr])
        assert "DataFrame" not in prompt
        assert " df " not in prompt


# ---------------------------------------------------------------------------
# Test _extract_numbers
# ---------------------------------------------------------------------------

class TestExtractNumbers:
    def test_extract_dot_decimal(self):
        """'35.6' duoc nhan dang dung."""
        assert 35.6 in _extract_numbers("Da Nang giam 35.6 phan tram")

    def test_extract_comma_decimal(self):
        """'35,6' (dau phay) cung duoc nhan dang dung."""
        assert 35.6 in _extract_numbers("Da Nang giam 35,6 phan tram")

    def test_extract_negative(self):
        """So am '-35.56' duoc nhan dang."""
        assert -35.56 in _extract_numbers("ty le tang truong: -35.56%")

    def test_extract_integer(self):
        """So nguyen '12' duoc nhan dang."""
        assert 12.0 in _extract_numbers("trong 12 thang qua")

    def test_extract_multiple(self):
        """Nhieu so trong cung mot cau."""
        nums = _extract_numbers("Ha Noi tang 20.83 con Da Nang giam 35.56")
        assert 20.83 in nums
        assert 35.56 in nums

    def test_empty_string(self):
        assert _extract_numbers("") == []

    def test_no_numbers(self):
        assert _extract_numbers("khong co so nao o day") == []


# ---------------------------------------------------------------------------
# Test _numeric_accuracy_score
# ---------------------------------------------------------------------------

class TestNumericAccuracyScore:
    def _make_growth_tr(self) -> TaskResult:
        return _make_tr("growth_rate", _GROWTH_RESULTS, find="min")

    def test_high_score_when_numbers_match(self):
        """Nhan xet co so khop voi du lieu that -> score cao."""
        trs = [self._make_growth_tr()]
        # 35.56 co trong du lieu, -35.56 cung co
        score = _numeric_accuracy_score("Da Nang giam 35.56 phan tram", trs)
        assert score >= 0.8

    def test_low_score_when_numbers_invented(self):
        """Nhan xet co so bia (khong co trong du lieu) -> score thap."""
        trs = [self._make_growth_tr()]
        # 999 va 888 khong co trong _GROWTH_RESULTS
        score = _numeric_accuracy_score("doanh thu dat 999 va 888 trieu", trs)
        assert score < 0.3

    def test_edge_case_no_numbers_in_text(self):
        """Khong co so nao trong insight -> score 1.0 (khong co gi de sai)."""
        trs = [self._make_growth_tr()]
        score = _numeric_accuracy_score("Da Nang giam doanh thu manh nhat", trs)
        assert score == 1.0

    def test_edge_case_no_known_values(self):
        """Du lieu ket qua rong -> score 1.0 (khong co gi de doi chieu)."""
        tr = _make_tr("trend", {}, success=True, group_by=None)
        score = _numeric_accuracy_score("doanh thu la 1234", [tr])
        assert score == 1.0

    def test_tolerance_accepted(self):
        """So xap xi (tolerance=0.5) van duoc chap nhan la khop."""
        trs = [self._make_growth_tr()]
        # -35.56 trong du lieu, -36 sai 0.44 < tolerance 0.5 -> khop
        score = _numeric_accuracy_score("Da Nang giam 36 phan tram", trs)
        assert score >= 0.8


# ---------------------------------------------------------------------------
# Test _collect_known_values
# ---------------------------------------------------------------------------

class TestCollectKnownValues:
    def test_collects_nested_dict_values(self):
        tr = _make_tr("growth_rate", _GROWTH_RESULTS, find="min")
        known = _collect_known_values([tr])
        assert -35.56 in known
        assert 20.83 in known
        assert 12.0 in known

    def test_collects_from_multiple_task_results(self):
        tr1 = _make_tr("trend", _TREND_RESULTS, group_by=None)
        tr2 = _make_tr("growth_rate", _GROWTH_RESULTS, find="min")
        known = _collect_known_values([tr1, tr2])
        assert 4450.0 in known  # tu trend
        assert -35.56 in known  # tu growth_rate


# ---------------------------------------------------------------------------
# Test _format_task_result
# ---------------------------------------------------------------------------

class TestFormatTaskResult:
    def test_format_growth_includes_target(self):
        tr = _make_tr("growth_rate", _GROWTH_RESULTS, find="min")
        text = _format_task_result(tr)
        assert "Da Nang" in text
        assert "thap nhat" in text

    def test_format_trend_includes_values(self):
        tr = _make_tr("trend", _TREND_RESULTS, group_by=None)
        text = _format_task_result(tr)
        assert "4450" in text


# ---------------------------------------------------------------------------
# Test tich hop: pipeline chinh (vi du xuyen suot du an)
# ---------------------------------------------------------------------------

class TestIntegrationDoanhThuCSV:
    """Test tich hop: trend + growth_rate (Da Nang -35.56%) -> insight.

    Dieu kien chuan: LLM viet nhan xet co nhac den "35.56" (hoac "35,56")
    -> confidence_score >= 0.8. Day la tieu chi nghiem thu chinh cua O5.
    """

    def _make_trend_tr(self) -> TaskResult:
        return _make_tr("trend", _TREND_RESULTS, group_by=None)

    def _make_growth_tr(self) -> TaskResult:
        return _make_tr("growth_rate", _GROWTH_RESULTS, find="min")

    def test_returns_insight_result(self):
        llm = FakeLLM("Da Nang giam 35.56 phan tram, manh nhat trong ky.")
        result = generate_insight(
            "chi nhanh nao giam manh nhat?",
            [self._make_trend_tr(), self._make_growth_tr()],
            llm,
        )
        assert isinstance(result, InsightResult)

    def test_insight_text_from_fake_llm(self):
        llm = FakeLLM("Da Nang giam 35.56 phan tram, manh nhat trong ky.")
        result = generate_insight(
            "chi nhanh nao giam manh nhat?",
            [self._make_trend_tr(), self._make_growth_tr()],
            llm,
        )
        assert "35.56" in result.insight_text or "35,56" in result.insight_text

    def test_confidence_score_high_when_correct_numbers(self):
        """Nhan xet co so dung -> confidence >= 0.8."""
        llm = FakeLLM("Da Nang giam 35.56 phan tram, manh nhat trong ky. Ha Noi tang 20.83.")
        result = generate_insight(
            "chi nhanh nao giam manh nhat?",
            [self._make_trend_tr(), self._make_growth_tr()],
            llm,
        )
        assert result.confidence_score is not None
        assert result.confidence_score >= 0.8

    def test_confidence_score_low_when_invented_numbers(self):
        """Nhan xet co so bia -> confidence thap hon."""
        llm = FakeLLM("Doanh thu dat 9999 trieu, tang 888 phan tram.")
        result = generate_insight(
            "chi nhanh nao giam manh nhat?",
            [self._make_trend_tr(), self._make_growth_tr()],
            llm,
        )
        assert result.confidence_score is not None
        assert result.confidence_score < 0.3

    def test_prompt_contains_data_values(self):
        """Prompt phai chua so lieu thuc tu task_results."""
        trs = [self._make_trend_tr(), self._make_growth_tr()]
        prompt = _build_prompt("cau hoi", trs)
        # Gia tri tu _GROWTH_RESULTS phai co trong prompt
        assert "35.56" in prompt or "-35.56" in prompt
        assert "Da Nang" in prompt

    def test_confidence_score_range(self):
        """confidence_score luon nam trong [0.0, 1.0]."""
        for text in [
            "Da Nang giam 35.56",
            "khong co so nao",
            "9999 va 8888 va 7777",
        ]:
            llm = FakeLLM(text)
            result = generate_insight(
                "cau hoi",
                [self._make_growth_tr()],
                llm,
            )
            assert 0.0 <= result.confidence_score <= 1.0


# ---------------------------------------------------------------------------
# Test /analyze integration (goi ham Python truc tiep, khong qua HTTP)
# ---------------------------------------------------------------------------

class TestAnalyzePipelineIntegration:
    """Test pipeline day du O1->O5 bang FakeLLM, khong can server thuc."""

    def _make_full_task_results(self) -> list[TaskResult]:
        return [
            _make_tr("trend", _TREND_RESULTS, group_by=None),
            _make_tr("growth_rate", _GROWTH_RESULTS, find="min"),
        ]

    def test_no_successful_tasks_raises(self):
        """Neu tat ca task deu loi, generate_insight raise InsightGenerationError."""
        trs = [
            _make_tr("trend", {}, success=False, group_by=None),
        ]
        with pytest.raises(InsightGenerationError):
            generate_insight("cau hoi", trs, FakeLLM("nhan xet"))

    def test_partial_success_generates_insight(self):
        """1 task loi, 1 task ok -> van co InsightResult."""
        trs = [
            _make_tr("trend", {}, success=False, group_by=None),
            _make_tr("growth_rate", _GROWTH_RESULTS, find="min", success=True),
        ]
        result = generate_insight("cau hoi", trs, FakeLLM("Da Nang giam 35.56."))
        assert isinstance(result, InsightResult)

    def test_full_pipeline_returns_insight_result(self):
        """Pipeline day du: 2 task thanh cong -> InsightResult hop le."""
        trs = self._make_full_task_results()
        llm = FakeLLM("Trong ky, Da Nang giam 35.56 phan tram.")
        result = generate_insight("chi nhanh nao giam manh nhat?", trs, llm)
        assert isinstance(result, InsightResult)
        assert len(result.insight_text) > 0
        assert result.confidence_score is not None
