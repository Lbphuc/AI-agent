"""Tests for Module O4 — Chart Generator.

Kiem thu theo dung ke hoach Tuan 5 (muc 5 trong proposal):
- 3 loai task (trend/comparison/growth_rate) -> dung chart_type
- growth_rate voi find="min" -> highlight_x dung ten chi nhanh
- Task co execution.success=False -> bi bo qua, khong raise
- Task thieu key mong doi trong results -> bi bo qua (None)
- Test tich hop voi du lieu y het doanh_thu.csv: 2 TaskResult
  (trend + growth_rate) -> 2 ChartSpec, chart thu 2 co highlight_x == "Da Nang"

Tuan 8 (Tier 1) bo sung:
- chart_hint tests: pie fallback, growth_rate safety, area, dem diem, nhan dai
- Test tich hop xac nhan hanh vi goc KHONG DOI sau khi them co che moi
"""
from __future__ import annotations

import pytest

from backend.app.modules.chart_generator import generate_charts, _build_chart, _pick_chart_type
from backend.app.schemas import (
    AnalysisTask,
    ChartSpec,
    ExecutionResult,
    TaskResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_result(
    task_type: str,
    results: dict,
    success: bool = True,
    metric: str = "Doanh_thu_trieu_vnd",
    group_by: str | None = "Chi_nhanh",
    find: str | None = None,
    chart_hint: str | None = None,
) -> TaskResult:
    task = AnalysisTask(
        type=task_type, metric=metric, group_by=group_by,
        find=find, chart_hint=chart_hint,
    )
    execution = ExecutionResult(success=success, results=results)
    return TaskResult(task=task, execution=execution)


# ---------------------------------------------------------------------------
# Kiem thu anh xa task.type -> chart_type (HOI QUY: hanh vi Tuan 5 khong doi)
# ---------------------------------------------------------------------------

class TestChartTypeMapping:
    def test_trend_returns_line_chart(self):
        tr = _make_task_result(
            "trend",
            {"trend": {"2025-09": 3600.0, "2025-10": 3620.0, "2025-11": 3640.0,
                       "2025-12": 3660.0, "2026-01": 3680.0}},  # 5 diem
            group_by=None,
        )
        charts = generate_charts([tr])
        assert len(charts) == 1
        assert charts[0].chart_type == "line"

    def test_comparison_returns_bar_chart(self):
        tr = _make_task_result(
            "comparison",
            {"comparison": {"Ha Noi": 15000.0, "TP.HCM": 22000.0}},
        )
        charts = generate_charts([tr])
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"

    def test_growth_rate_returns_bar_chart(self):
        tr = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83, "Da Nang": -35.56}, "target": "Da Nang"},
            find="min",
        )
        charts = generate_charts([tr])
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"


# ---------------------------------------------------------------------------
# Kiem thu highlight_x
# ---------------------------------------------------------------------------

class TestHighlightX:
    def test_growth_rate_min_sets_highlight_x(self):
        tr = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83, "Da Nang": -35.56}, "target": "Da Nang"},
            find="min",
        )
        charts = generate_charts([tr])
        assert charts[0].highlight_x == "Da Nang"

    def test_growth_rate_max_sets_highlight_x(self):
        tr = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83, "Da Nang": -35.56}, "target": "Ha Noi"},
            find="max",
        )
        charts = generate_charts([tr])
        assert charts[0].highlight_x == "Ha Noi"

    def test_trend_has_no_highlight_x(self):
        tr = _make_task_result(
            "trend",
            {"trend": {"2025-09": 3600.0, "2025-10": 3620.0, "2025-11": 3640.0,
                       "2025-12": 3660.0, "2026-01": 3680.0}},
            group_by=None,
        )
        charts = generate_charts([tr])
        assert charts[0].highlight_x is None

    def test_comparison_has_no_highlight_x(self):
        tr = _make_task_result(
            "comparison",
            {"comparison": {"Ha Noi": 15000.0}},
        )
        charts = generate_charts([tr])
        assert charts[0].highlight_x is None


# ---------------------------------------------------------------------------
# Kiem thu xu ly loi tung phan (partial failure)
# ---------------------------------------------------------------------------

class TestPartialFailure:
    def test_failed_execution_is_skipped(self):
        """Task co success=False bi bo qua, khong raise loi."""
        tr_fail = _make_task_result("trend", {}, success=False, group_by=None)
        charts = generate_charts([tr_fail])
        assert charts == []

    def test_failed_task_does_not_block_other_tasks(self):
        """1 task loi khong lam hong bieu do cua task khac trong cung danh sach."""
        tr_fail = _make_task_result("trend", {}, success=False, group_by=None)
        tr_ok = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83, "Da Nang": -35.56}, "target": "Da Nang"},
            find="min",
        )
        charts = generate_charts([tr_fail, tr_ok])
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"

    def test_missing_expected_key_returns_no_chart(self):
        """Task thieu key mong doi trong results bi bo qua, khong raise."""
        tr = _make_task_result(
            "growth_rate",
            {"wrong_key": {"Ha Noi": 20.83}},  # thieu "growth_rate"
            find="min",
        )
        charts = generate_charts([tr])
        assert charts == []

    def test_empty_results_dict_returns_no_chart(self):
        """results rong ({}) -> khong tao bieu do."""
        tr = _make_task_result("comparison", {"comparison": {}})
        charts = generate_charts([tr])
        assert charts == []

    def test_all_failed_returns_empty_list(self):
        """Tat ca task deu loi -> tra list rong."""
        trs = [
            _make_task_result("trend", {}, success=False, group_by=None),
            _make_task_result("comparison", {}, success=False),
        ]
        charts = generate_charts(trs)
        assert charts == []


# ---------------------------------------------------------------------------
# Kiem thu noi dung ChartSpec (x, series, title)
# ---------------------------------------------------------------------------

class TestChartSpecContent:
    def test_trend_x_and_series_correct(self):
        data = {
            "2025-09": 3600.0, "2025-10": 3620.0, "2025-11": 3640.0,
            "2025-12": 3660.0, "2026-01": 3680.0,
        }
        tr = _make_task_result("trend", {"trend": data}, group_by=None)
        charts = generate_charts([tr])
        assert charts[0].x == list(data.keys())
        assert charts[0].series["Doanh_thu_trieu_vnd"] == list(data.values())

    def test_comparison_series_key_is_metric_name(self):
        tr = _make_task_result(
            "comparison",
            {"comparison": {"Ha Noi": 15000.0, "TP.HCM": 22000.0}},
        )
        charts = generate_charts([tr])
        assert "Doanh_thu_trieu_vnd" in charts[0].series

    def test_growth_rate_title_contains_giam_for_min(self):
        tr = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83}, "target": "Ha Noi"},
            find="min",
        )
        charts = generate_charts([tr])
        assert any(w in charts[0].title.lower() for w in ("giảm", "giam"))

    def test_growth_rate_title_contains_tang_for_max(self):
        tr = _make_task_result(
            "growth_rate",
            {"growth_rate": {"Ha Noi": 20.83}, "target": "Ha Noi"},
            find="max",
        )
        charts = generate_charts([tr])
        assert any(w in charts[0].title.lower() for w in ("tăng", "tang"))


# ---------------------------------------------------------------------------
# Kiem thu chart_hint + luat tat dinh (Tuan 8 — Tier 1)
# ---------------------------------------------------------------------------

class TestChartHint:
    """Test kich ban theo bang ke hoach trong proposal."""

    def test_no_hint_uses_default_mapping(self):
        """Khong co chart_hint -> dung bang mac dinh nhu cu (hoi quy)."""
        task = AnalysisTask(
            type="comparison", metric="Doanh_thu_trieu_vnd", group_by="Chi_nhanh"
        )
        x = ["Ha Noi", "TP.HCM", "Da Nang"]
        assert _pick_chart_type(task, x) == "bar"

    def test_comparison_pie_hint_with_few_categories(self):
        """comparison + chart_hint='pie' + <=6 danh muc -> pie."""
        task = AnalysisTask(
            type="comparison", metric="Doanh_thu_trieu_vnd",
            group_by="Chi_nhanh", chart_hint="pie",
        )
        x = ["Ha Noi", "TP.HCM", "Da Nang", "Can Tho"]  # 4 <= 6
        assert _pick_chart_type(task, x) == "pie"

    def test_comparison_pie_hint_with_too_many_categories(self):
        """comparison + chart_hint='pie' + >6 danh muc -> fallback bar."""
        task = AnalysisTask(
            type="comparison", metric="Doanh_thu_trieu_vnd",
            group_by="Chi_nhanh", chart_hint="pie",
        )
        x = ["A", "B", "C", "D", "E", "F", "G"]  # 7 > _MAX_PIE_SLICES=6
        assert _pick_chart_type(task, x) == "bar"

    def test_growth_rate_pie_hint_always_falls_back_to_bar(self):
        """growth_rate + chart_hint='pie' (LLM lo goi y sai) -> LUON fallback bar,
        bat ke so luong danh muc.
        """
        task = AnalysisTask(
            type="growth_rate", metric="Doanh_thu_trieu_vnd",
            group_by="Chi_nhanh", chart_hint="pie",
        )
        x = ["Ha Noi", "Da Nang"]  # chi 2 muc, nhung growth_rate + pie = vo nghia
        result = _pick_chart_type(task, x)
        assert result == "bar", f"Mong doi 'bar', nhan duoc '{result}'"

    def test_trend_area_hint_with_enough_points(self):
        """trend + chart_hint='area' + >=5 diem -> area."""
        task = AnalysisTask(
            type="trend", metric="Doanh_thu_trieu_vnd",
            group_by=None, chart_hint="area",
        )
        x = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01"]  # 5 diem
        assert _pick_chart_type(task, x) == "area"

    def test_trend_area_hint_with_too_few_points(self):
        """trend + chart_hint='area' nhung chi 3 diem -> fallback bar
        (luat dem diem thang luat hint khi diem < 5).
        """
        task = AnalysisTask(
            type="trend", metric="Doanh_thu_trieu_vnd",
            group_by=None, chart_hint="area",
        )
        x = ["2025-09", "2025-10", "2025-11"]  # 3 < _MIN_POINTS_FOR_LINE=5
        assert _pick_chart_type(task, x) == "bar"

    def test_comparison_no_hint_long_labels_gives_bar_horizontal(self):
        """comparison khong hint, ten danh muc dai (>12 ky tu) -> bar_horizontal."""
        task = AnalysisTask(
            type="comparison", metric="Doanh_thu_trieu_vnd", group_by="San_pham"
        )
        x = ["San pham A rat dai ten", "San pham B cung the"]  # >12 ky tu
        assert _pick_chart_type(task, x) == "bar_horizontal"

    def test_comparison_short_labels_keeps_bar(self):
        """comparison, ten ngan -> bar binh thuong (khong chuyen ngang)."""
        task = AnalysisTask(
            type="comparison", metric="Doanh_thu_trieu_vnd", group_by="Chi_nhanh"
        )
        x = ["Ha Noi", "TP.HCM"]  # <= 12 ky tu
        assert _pick_chart_type(task, x) == "bar"

    def test_trend_no_hint_few_points_gives_bar(self):
        """trend khong hint, qua it diem thoi gian -> bar (line trong yeu)."""
        task = AnalysisTask(
            type="trend", metric="Doanh_thu_trieu_vnd", group_by=None
        )
        x = ["2026-Q1", "2026-Q2", "2026-Q3"]  # 3 < 5
        assert _pick_chart_type(task, x) == "bar"


# ---------------------------------------------------------------------------
# Test tich hop: dung du lieu y het doanh_thu.csv (vi du xuyen suot du an)
# Xac nhan hanh vi goc KHONG DOI sau khi them toan bo co che moi
# ---------------------------------------------------------------------------

class TestIntegrationDoanhThuCSV:
    """Test tich hop voi du lieu y het doanh_thu.csv dung trong Tuan 1-4.

    2 TaskResult (trend + growth_rate) -> 2 ChartSpec.
    Chart growth_rate phai co highlight_x == "Da Nang" (chi nhanh giam manh nhat).
    Khong co chart_hint -> hanh vi y nhu Tuan 5, xac nhan khong phai loi hoi quy.
    """

    # Ket qua tinh toan thuc te tu O3 voi doanh_thu.csv
    _TREND_DATA = {
        "2025-09": 4450.0,
        "2025-10": 4420.0,
        "2025-11": 4460.0,
        "2025-12": 4485.0,
        "2026-01": 4410.0,
        "2026-02": 4435.0,
        "2026-03": 4460.0,
        "2026-04": 4405.0,
        "2026-05": 4430.0,
        "2026-06": 4465.0,
        "2026-07": 4370.0,
        "2026-08": 4480.0,
    }

    _GROWTH_DATA = {
        "Can Tho": 12.0,
        "Da Nang": -35.56,
        "Ha Noi": 20.83,
        "TP.HCM": 2.16,
    }

    def _make_trend_tr(self) -> TaskResult:
        task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None)
        execution = ExecutionResult(
            success=True,
            results={"trend": self._TREND_DATA},
        )
        return TaskResult(task=task, execution=execution)

    def _make_growth_tr(self) -> TaskResult:
        task = AnalysisTask(
            type="growth_rate",
            metric="Doanh_thu_trieu_vnd",
            group_by="Chi_nhanh",
            find="min",
        )
        execution = ExecutionResult(
            success=True,
            results={"growth_rate": self._GROWTH_DATA, "target": "Da Nang"},
        )
        return TaskResult(task=task, execution=execution)

    def test_two_task_results_produce_two_charts(self):
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert len(charts) == 2

    def test_first_chart_is_line_for_trend(self):
        """12 diem thoi gian >= _MIN_POINTS_FOR_LINE=5 -> line (khong chuyen bar)."""
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert charts[0].chart_type == "line"

    def test_second_chart_is_bar_for_growth_rate(self):
        """growth_rate khong co hint -> bar (mac dinh)."""
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert charts[1].chart_type == "bar"

    def test_highlight_x_is_da_nang(self):
        """Dieu kien nghiem thu chinh: chi nhanh giam manh nhat phai la Da Nang."""
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert charts[1].highlight_x == "Da Nang"

    def test_trend_x_has_12_months(self):
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert len(charts[0].x) == 12

    def test_growth_x_has_4_branches(self):
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        assert len(charts[1].x) == 4

    def test_da_nang_value_is_negative_in_series(self):
        """Gia tri Da Nang trong series phai am (giam doanh thu)."""
        charts = generate_charts([self._make_trend_tr(), self._make_growth_tr()])
        series = charts[1].series["Doanh_thu_trieu_vnd"]
        x_labels = charts[1].x
        da_nang_idx = x_labels.index("Da Nang")
        assert series[da_nang_idx] < 0
