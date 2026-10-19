"""Tests for Chart Fitness Matrix, Data Rules, Arbitration & API Endpoints.

Kiem thu toan dien theo muc 8 trong proposal 'Chon bieu do tuy y theo chien luoc phan tich'.
"""
from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.chart_fitness import (
    CHART_DATA_SHAPE,
    CHART_DISPLAY_NAMES,
    CHART_STATUS,
    FITNESS_MATRIX,
    get_fitness,
)
from backend.app.modules.chart_rules import (
    ChartContext,
    auto_pick,
    check_chart_choice,
    evaluate_rules,
    list_options,
    build_chart_catalog,
)
from backend.app.schemas import (
    AnalysisLevel,
    AnalysisTask,
    ChartType,
    DataProfile,
    ColumnProfile,
    ExecutionResult,
    TaskResult,
)
from backend.app.modules import chart_generator


# ---------------------------------------------------------------------------
# 1. Kiem thu Ma tran muc phu hop
# ---------------------------------------------------------------------------
class TestFitnessMatrix:
    def test_all_12_charts_and_4_levels_have_values(self):
        """Moi o trong ma tran (12 bieu do x 4 chien luoc = 48 o) phai co gia tri hop le."""
        all_charts: list[ChartType] = [
            "kpi", "bar", "bar_horizontal", "line", "area", "pie",
            "stacked_bar", "waterfall", "scatter", "heatmap", "box", "histogram",
        ]
        all_levels: list[AnalysisLevel] = [
            "descriptive", "diagnostic", "forecast", "prescriptive"
        ]

        assert len(FITNESS_MATRIX) == 4
        for lvl in all_levels:
            assert lvl in FITNESS_MATRIX
            lvl_dict = FITNESS_MATRIX[lvl]
            for ct in all_charts:
                assert ct in lvl_dict, f"Thieu {ct} trong level {lvl}"
                fitness = get_fitness(lvl, ct)
                assert fitness in ("recommended", "ok", "confirm", "blocked")

    def test_all_recommended_cells_are_ready_or_soon(self):
        """Moi o recommended (★) deu phai co status ready hoac soon."""
        for lvl, charts in FITNESS_MATRIX.items():
            for ct, fit in charts.items():
                if fit == "recommended":
                    status = CHART_STATUS.get(ct)
                    assert status in ("ready", "soon"), f"{ct} o level {lvl} co status {status}"


# ---------------------------------------------------------------------------
# 2. Kiem thu check_chart_choice (bang luat)
# ---------------------------------------------------------------------------
class TestCheckChartChoice:
    def test_pie_too_many_slices_triggers_confirm(self):
        """Tron + 8 lat -> confirm / TOO_MANY_SLICES, goi y bar."""
        ctx = ChartContext(n_categories=8, n_points=8, has_negative=False, additivity="yes")
        verdict = check_chart_choice("descriptive", "pie", ctx)
        assert verdict.status == "confirm"
        codes = [r.code for r in verdict.reasons]
        assert "TOO_MANY_SLICES" in codes
        assert "bar" in verdict.alternatives or any("bar" in r.suggest for r in verdict.reasons)

    def test_pie_negative_values_is_blocked(self):
        """Tron + co gia tri am -> blocked / NEGATIVE_VALUES."""
        ctx = ChartContext(n_categories=4, n_points=4, has_negative=True, additivity="yes")
        verdict = check_chart_choice("descriptive", "pie", ctx)
        assert verdict.status == "blocked"
        codes = [r.code for r in verdict.reasons]
        assert "NEGATIVE_VALUES" in codes

    def test_scatter_one_numeric_column_is_blocked(self):
        """Phan tan + 1 cot so -> blocked / NEEDS_TWO_MEASURES (va status='soon' bi chan)."""
        ctx = ChartContext(n_numeric_cols=1)
        verdict = check_chart_choice("diagnostic", "scatter", ctx)
        assert verdict.status == "blocked"
        codes = [r.code for r in verdict.reasons]
        assert "NEEDS_TWO_MEASURES" in codes or "UNSUPPORTED_YET" in codes

    def test_line_too_few_points_triggers_confirm(self):
        """Duong + 3 diem -> confirm / TOO_FEW_POINTS."""
        ctx = ChartContext(n_points=3, has_time=True, task_type="trend")
        verdict = check_chart_choice("descriptive", "line", ctx)
        assert verdict.status == "confirm"
        codes = [r.code for r in verdict.reasons]
        assert "TOO_FEW_POINTS" in codes

    def test_box_insufficient_data_is_blocked(self):
        """Hop + 4 quan sat/nhom -> blocked / INSUFFICIENT_DATA."""
        ctx = ChartContext(n_group_cols=1, n_obs_per_group=4)
        verdict = check_chart_choice("diagnostic", "box", ctx)
        assert verdict.status == "blocked"
        codes = [r.code for r in verdict.reasons]
        assert "INSUFFICIENT_DATA" in codes

    def test_pie_in_diagnostic_triggers_strategy_unusual(self):
        """Tron x Tim nguyen nhan -> confirm / STRATEGY_UNUSUAL."""
        ctx = ChartContext(n_categories=4, n_points=4, has_negative=False, additivity="yes")
        verdict = check_chart_choice("diagnostic", "pie", ctx)
        assert verdict.status == "confirm"
        codes = [r.code for r in verdict.reasons]
        assert "STRATEGY_UNUSUAL" in codes

    def test_waterfall_in_forecast_is_blocked_not_applicable(self):
        """Thac nuoc x Du doan -> blocked / NOT_APPLICABLE."""
        ctx = ChartContext(has_time=True)
        verdict = check_chart_choice("forecast", "waterfall", ctx)
        assert verdict.status == "blocked"
        codes = [r.code for r in verdict.reasons]
        assert "NOT_APPLICABLE" in codes


# ---------------------------------------------------------------------------
# 3. Kiem thu co che xac nhan (ack)
# ---------------------------------------------------------------------------
class TestAckConfirmation:
    def test_ack_with_exact_codes_passes(self):
        """ack dung ma ly do can xac nhan -> verdict chuyen thanh ok."""
        ctx = ChartContext(n_categories=8, n_points=8, has_negative=False, additivity="yes")
        # Chua ack -> confirm
        v1 = check_chart_choice("descriptive", "pie", ctx, ack=None)
        assert v1.status == "confirm"

        # Ack dung ma TOO_MANY_SLICES -> ok
        v2 = check_chart_choice("descriptive", "pie", ctx, ack={"TOO_MANY_SLICES"})
        assert v2.status == "ok"

    def test_ack_missing_one_code_still_confirms(self):
        """ack thieu mot ma -> van confirm."""
        ctx = ChartContext(n_categories=8, n_points=8, has_negative=False, additivity="yes")
        # Giai su level la diagnostic (co 2 confirm: STRATEGY_UNUSUAL va TOO_MANY_SLICES)
        v = check_chart_choice("diagnostic", "pie", ctx, ack={"TOO_MANY_SLICES"})
        assert v.status == "confirm"
        codes = [r.code for r in v.reasons if r.severity == "confirm"]
        assert "STRATEGY_UNUSUAL" in codes

    def test_ack_cannot_bypass_blocked_status(self):
        """ack voi ma muc chan (NEGATIVE_VALUES, NOT_APPLICABLE) khong co tac dung -> van blocked."""
        ctx = ChartContext(n_categories=4, n_points=4, has_negative=True)
        v = check_chart_choice("descriptive", "pie", ctx, ack={"NEGATIVE_VALUES"})
        assert v.status == "blocked"


# ---------------------------------------------------------------------------
# 4. Kiem thu Nguyen tac Khong thay tham (No silent mutation)
# ---------------------------------------------------------------------------
class TestNoSilentMutation:
    def test_user_chosen_pie_stays_pie_when_acked(self):
        """Nguoi dung tu chon pie voi 8 lat + ack -> van la pie (selection='user'),
        khong bi he thong tu dong doi sang bar.
        """
        task = AnalysisTask(type="comparison", metric="Doanh_thu", group_by="Chi_nhanh")
        results = {
            "comparison": {f"Chi_nhanh_{i}": 100.0 * i for i in range(1, 9)}
        }
        tr = TaskResult(task=task, execution=ExecutionResult(success=True, results=results))

        charts = chart_generator.generate_charts(
            [tr],
            chart_pref="pie",
            level="descriptive",
            confirmed_notes=["Đã xác nhận nhiều lát cắt"],
        )
        assert len(charts) == 1
        assert charts[0].chart_type == "pie"
        assert charts[0].selection == "user"
        assert any("nhiều lát cắt" in n for n in charts[0].notes)

    def test_auto_mode_with_same_data_silently_picks_bar(self):
        """Che do Tu dong cung tap du lieu do -> tu dong chuyen sang bar."""
        task = AnalysisTask(type="comparison", metric="Doanh_thu", group_by="Chi_nhanh")
        results = {
            "comparison": {f"Chi_nhanh_{i}": 100.0 * i for i in range(1, 9)}
        }
        tr = TaskResult(task=task, execution=ExecutionResult(success=True, results=results))

        charts = chart_generator.generate_charts(
            [tr],
            chart_pref=None,  # auto mode
            level="descriptive",
        )
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"
        assert charts[0].selection == "auto"


# ---------------------------------------------------------------------------
# 5. Kiem thu Hop nhat luat (auto_pick vs check_chart_choice)
# ---------------------------------------------------------------------------
class TestRuleUnification:
    def test_auto_pick_and_check_chart_choice_are_consistent(self):
        """auto_pick va check_chart_choice nhat quan tren cung ngu canh:
        Neu check_chart_choice bao blocked/confirm cho pie thi auto_pick cung phai fallback khoi pie.
        """
        task = AnalysisTask(type="comparison", metric="Doanh_thu", group_by="Chi_nhanh", chart_hint="pie")
        ctx = ChartContext(n_categories=8, n_points=8, has_negative=False, additivity="yes")

        verdict = check_chart_choice("descriptive", "pie", ctx)
        assert verdict.status == "confirm"

        picked = auto_pick("descriptive", task, ctx)
        assert picked != "pie"
        assert picked == "bar"


# ---------------------------------------------------------------------------
# 6. Kiem thu options list tren the bieu do
# ---------------------------------------------------------------------------
class TestChartOptions:
    def test_options_list_populates_fetch_flag(self):
        """Cung data_shape -> requires_fetch=False; khac data_shape -> True."""
        ctx = ChartContext(n_categories=4, n_points=4, has_time=True)
        opts = list_options("descriptive", current="bar", ctx=ctx)
        assert len(opts) == 12

        for opt in opts:
            shape = CHART_DATA_SHAPE.get(opt.chart_type)
            if shape == "category_series":
                assert opt.requires_fetch is False
            else:
                assert opt.requires_fetch is True


# ---------------------------------------------------------------------------
# 7. Kiem thu API Endpoints (409 / 422 / 200)
# ---------------------------------------------------------------------------
class TestArbitrationAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_llm(self, monkeypatch):
        class MockGeminiClient:
            model_name = "Mock Gemini"

            def complete_json(self, prompt: str) -> dict:
                if "analyze(df)" in prompt or "hàm analyze" in prompt:
                    return {
                        "code": "def analyze(df):\n    res = df.groupby('Chi_nhanh')['Doanh_thu_trieu_vnd'].sum().to_dict()\n    return {'comparison': res}"
                    }
                return {
                    "time_scope": "all",
                    "tasks": [
                        {"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}
                    ],
                }

            def complete(self, prompt: str) -> str:
                return "Mock insight"

        monkeypatch.setattr("backend.app.main.GeminiClient", MockGeminiClient)

    @pytest.fixture
    def sample_csv(self):
        # 8 chi nhanh x 2 thang = 16 dong -> Chi_nhanh nunique/n = 8/16 = 0.5 <= 0.5 (group_column hop le)
        rows = ["Thang,Chi_nhanh,Doanh_thu_trieu_vnd"]
        for m in ["2025-01", "2025-02"]:
            for i in range(1, 9):
                rows.append(f"{m},Chi_nhanh_{i},{100 * i}")
        return "\n".join(rows).encode("utf-8")

    def test_profile_returns_chart_catalog(self, client, sample_csv):
        """Endpoint /profile tra ve chart_catalog cho ca 4 levels."""
        resp = client.post(
            "/profile",
            files={"file": ("test.csv", sample_csv, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "chart_catalog" in data
        catalog = data["chart_catalog"]
        assert "descriptive" in catalog
        assert "diagnostic" in catalog
        assert "forecast" in catalog
        assert "prescriptive" in catalog
        assert len(catalog["descriptive"]) == 12

    def test_interpret_with_chart_pref_returns_chart_check(self, client, sample_csv):
        """Endpoint /interpret tra ve chart_check khi co chart_pref."""
        resp = client.post(
            "/interpret",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={"question": "So sánh doanh thu theo chi nhánh", "chart_pref": "pie"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "chart_check" in data
        assert data["chart_check"] is not None
        assert data["chart_check"]["chart_type"] == "pie"

    def test_analyze_confirm_chart_without_ack_returns_409(self, client, sample_csv):
        """/analyze voi chart can xac nhan (pie > 6 slices) ma khong ack -> HTTP 409."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/analyze",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "question": "So sánh doanh thu",
                "goal": goal_json,
                "chart_pref": "pie",
            },
        )
        assert resp.status_code == 409
        data = resp.json()
        assert "verdict" in data["detail"]
        assert data["detail"]["verdict"]["status"] == "confirm"

    def test_analyze_confirm_chart_with_ack_returns_200(self, client, sample_csv):
        """/analyze voi chart co ack -> HTTP 200, ve dung chart da chon."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/analyze",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "question": "So sánh doanh thu",
                "goal": goal_json,
                "chart_pref": "pie",
                "ack": '["TOO_MANY_SLICES"]',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["charts"]) >= 1
        primary = data["charts"][0]
        assert primary["chart_type"] == "pie"
        assert primary["selection"] == "user"

    def test_analyze_blocked_chart_returns_422_even_with_ack(self, client, sample_csv):
        """/analyze voi bieu do bi chan (vi du scatter tren 1 cot so) -> 422."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/analyze",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "question": "So sánh doanh thu",
                "goal": goal_json,
                "chart_pref": "scatter",  # chi co 1 cot so -> blocked
                "ack": '["NEEDS_TWO_MEASURES", "UNSUPPORTED_YET"]',
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "verdict" in data["detail"]
        assert data["detail"]["verdict"]["status"] == "blocked"

    def test_render_endpoint(self, client, sample_csv):
        """Endpoint /render tao ChartSpec moi cho loai bieu do duoc yeu cau."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/render",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "goal": goal_json,
                "level": "descriptive",
                "chart_type": "waterfall",
            },
        )
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["chart_type"] == "waterfall"
        assert spec["data_shape"] == "waterfall"
        assert spec["waterfall_steps"] is not None
        assert len(spec["waterfall_steps"]) > 0

    def test_analyze_blocked_chart_with_double_ack_returns_200(self, client, sample_csv):
        """/analyze voi bieu do 'khong ap dung' nhung nguoi dung da xac nhan 2 lan (force:) -> 200 OK."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/analyze",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "question": "So sánh doanh thu",
                "goal": goal_json,
                "chart_pref": "scatter",
                "ack": '["STRATEGY_UNUSUAL", "NEEDS_TWO_MEASURES", "UNSUPPORTED_YET", "force:NEEDS_TWO_MEASURES", "force:UNSUPPORTED_YET"]',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["charts"]) >= 1
        assert data["charts"][0]["chart_type"] == "scatter"
        assert data["charts"][0]["selection"] == "user"

    def test_analyze_multi_charts_selection_returns_multiple_charts(self, client, sample_csv):
        """/analyze cho phep nguoi dung chon nhieu loai bieu do trong 1 luot phan tich."""
        goal_json = (
            '{"question": "So sánh doanh thu theo chi nhánh", '
            '"tasks": [{"type": "comparison", "metric": "Doanh_thu_trieu_vnd", "group_by": "Chi_nhanh"}]}'
        )
        resp = client.post(
            "/analyze",
            files={"file": ("test.csv", sample_csv, "text/csv")},
            data={
                "question": "So sánh doanh thu",
                "goal": goal_json,
                "chart_prefs": '["bar", "bar_horizontal"]',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        chart_types = [c["chart_type"] for c in data["charts"]]
        assert "bar" in chart_types
        assert "bar_horizontal" in chart_types
        assert len(data["charts"]) >= 2

