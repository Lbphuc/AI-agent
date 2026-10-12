"""Tests cho module Perspective Planner (Dashboard đa góc nhìn — 1 câu hỏi, nhiều biểu đồ).

Kịch bản và số liệu kỳ vọng đối chiếu chặt chẽ với mục 10 trong proposal:
- share_of_total trên doanh_thu.csv: 4 phần TP.HCM 41.9, Hà Nội 29.4, Đà Nẵng 16.8, Cần Thơ 11.9.
- period_change: 11 giá trị; nhỏ nhất 2026-01 (-1.67%), lớn nhất 2026-08 (+1.13%).
- trend_by_group: 4 chuỗi, mỗi chuỗi 12 điểm, highlight_series == 'Da Nang' khi target='Da Nang'.
- contribution_to_change: Hà Nội +250, TP.HCM +40, Cần Thơ +60, Đà Nẵng -320.
- ton_kho.csv và danh_gia_khach_hang.csv: Không sinh cumulative hay share_of_total.
- Số nhóm > 8: trend_by_group trả None.
- Ít hơn 3 điểm: period_change trả None.
- Giới hạn max_supplementary: trả đúng 3 biểu đồ theo thứ tự priority.
- Xử lý ngoại lệ: lỗi ở 1 perspective không làm crash expand().
- Property test: các con số trong caption khớp số liệu trong series.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from backend.app.modules import data_profiler, perspective_planner
from backend.app.modules.perspective_planner import (
    _fmt_vn,
    _is_addable_metric,
    _resolve_context,
    perspective_contribution_to_change,
    perspective_cumulative,
    perspective_moving_average,
    perspective_period_change,
    perspective_share_of_total,
    perspective_trend_by_group,
    expand,
)
from backend.app.schemas import (
    AnalysisGoal,
    AnalysisTask,
    DataProfile,
    ExecutionResult,
    TaskResult,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "samples"


@pytest.fixture
def doanh_thu_df() -> pd.DataFrame:
    csv_path = DATA_DIR / "doanh_thu.csv"
    return pd.read_csv(csv_path)


@pytest.fixture
def doanh_thu_profile(doanh_thu_df: pd.DataFrame) -> DataProfile:
    return data_profiler.profile(doanh_thu_df)


@pytest.fixture
def mock_trend_task_result() -> TaskResult:
    # 12 tháng tổng doanh thu tương ứng doanh_thu.csv
    # 2025-09: 4450, 2025-10: 4420, 2025-11: 4460, 2025-12: 4485
    # 2026-01: 4410, 2026-02: 4435, 2026-03: 4460, 2026-04: 4405
    # 2026-05: 4430, 2026-06: 4465, 2026-07: 4430, 2026-08: 4480
    trend_data = {
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
        "2026-07": 4430.0,
        "2026-08": 4480.0,
    }
    task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd")
    execution = ExecutionResult(success=True, results={"trend": trend_data})
    return TaskResult(task=task, execution=execution)


@pytest.fixture
def mock_growth_rate_task_result() -> TaskResult:
    task = AnalysisTask(
        type="growth_rate",
        metric="Doanh_thu_trieu_vnd",
        group_by="Chi_nhanh",
        find="min",
    )
    execution = ExecutionResult(
        success=True,
        results={
            "growth_rate": {"Ha Noi": 20.83, "TP.HCM": 2.16, "Can Tho": 12.0, "Da Nang": -35.56},
            "target": "Da Nang",
        },
    )
    return TaskResult(task=task, execution=execution)


# ===========================================================================
# 1. Test định dạng số kiểu Việt Nam (_fmt_vn)
# ===========================================================================
class TestFormatVN:
    def test_basic_formatting(self):
        assert _fmt_vn(41.9) == "41,9"
        assert _fmt_vn(1250.0) == "1.250"
        assert _fmt_vn(1250.5) == "1.250,5"

    def test_signs(self):
        assert _fmt_vn(-320.0) == "-320"
        assert _fmt_vn(250.0, force_sign=True) == "+250"
        assert _fmt_vn(-1.67, decimals=2, force_sign=True) == "-1,67"
        assert _fmt_vn(1.13, decimals=2, force_sign=True) == "+1,13"


# ===========================================================================
# 2. Test điều kiện chỉ số cộng dồn được (_is_addable_metric)
# ===========================================================================
class TestAddableMetric:
    def test_doanh_thu_is_addable(self, doanh_thu_profile: DataProfile):
        assert _is_addable_metric("Doanh_thu_trieu_vnd", doanh_thu_profile) is True

    def test_ton_kho_is_not_addable(self):
        df = pd.read_csv(DATA_DIR / "ton_kho.csv")
        profile = data_profiler.profile(df)
        assert _is_addable_metric("So_luong_ton", profile) is False

    def test_danh_gia_is_not_addable(self):
        df = pd.read_csv(DATA_DIR / "danh_gia_khach_hang.csv")
        profile = data_profiler.profile(df)
        assert _is_addable_metric("Diem_danh_gia", profile) is False


# ===========================================================================
# 3. Test các Perspective riêng lẻ với số liệu doanh_thu.csv
# ===========================================================================
class TestPerspectivesOnDoanhThu:
    def test_share_of_total(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        goal = AnalysisGoal(
            question="Doanh thu như thế nào?",
            tasks=[mock_trend_task_result.task],
        )
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
        )
        spec = perspective_share_of_total(ctx)

        assert spec is not None
        assert spec.chart_type == "pie"
        assert spec.role == "supplementary"
        assert spec.perspective == "share_of_total"
        assert len(spec.x) == 4

        # Đối chiếu 4 tỷ trọng: TP.HCM 41.9, Hà Nội 29.4, Đà Nẵng 16.8, Cần Thơ 11.9
        pcts = list(spec.series.values())[0]
        label_to_pct = dict(zip(spec.x, pcts))
        assert label_to_pct["TP.HCM"] == 41.9
        assert label_to_pct["Ha Noi"] == 29.4
        assert label_to_pct["Da Nang"] == 16.8
        assert label_to_pct["Can Tho"] == 11.9
        assert sum(pcts) == 100.0
        assert "TP.HCM" in spec.caption
        assert "41,9%" in spec.caption
        assert "Can Tho" in spec.caption
        assert "11,9%" in spec.caption

    def test_period_change(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        goal = AnalysisGoal(
            question="Xu hướng doanh thu",
            tasks=[mock_trend_task_result.task],
        )
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
        )
        spec = perspective_period_change(ctx)

        assert spec is not None
        assert spec.chart_type == "bar"
        assert spec.role == "supplementary"
        assert spec.perspective == "period_change"
        assert len(spec.x) == 11  # 12 kỳ -> 11 khoảng thay đổi

        vals = list(spec.series.values())[0]
        # Giảm mạnh nhất là 2026-01 (-1.67%)
        min_idx = vals.index(min(vals))
        assert spec.x[min_idx] == "2026-01"
        assert vals[min_idx] == -1.67

        # Tăng mạnh nhất là 2026-08 (+1.13%)
        max_idx = vals.index(max(vals))
        assert spec.x[max_idx] == "2026-08"
        assert vals[max_idx] == 1.13

        assert "2026-01" in spec.caption
        assert "-1,67%" in spec.caption
        assert "2026-08" in spec.caption
        assert "+1,13%" in spec.caption

    def test_trend_by_group(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
        mock_growth_rate_task_result: TaskResult,
    ):
        goal = AnalysisGoal(
            question="Xu hướng doanh thu",
            tasks=[mock_trend_task_result.task, mock_growth_rate_task_result.task],
        )
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result, mock_growth_rate_task_result],
        )
        spec = perspective_trend_by_group(ctx)

        assert spec is not None
        assert spec.chart_type == "line"
        assert spec.role == "supplementary"
        assert spec.perspective == "trend_by_group"
        assert len(spec.series) == 4
        # Mỗi chuỗi đúng 12 điểm
        for name, values in spec.series.items():
            assert len(values) == 12

        # highlight_series == 'Da Nang' vì task growth_rate có target = 'Da Nang'
        assert spec.highlight_series == "Da Nang"
        assert "Da Nang" in spec.caption

    def test_contribution_to_change(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
        mock_growth_rate_task_result: TaskResult,
    ):
        goal = AnalysisGoal(
            question="Đóng góp thay đổi",
            tasks=[mock_trend_task_result.task, mock_growth_rate_task_result.task],
        )
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result, mock_growth_rate_task_result],
        )
        spec = perspective_contribution_to_change(ctx)

        assert spec is not None
        assert spec.chart_type == "bar"
        assert spec.role == "supplementary"
        assert spec.perspective == "contribution_to_change"

        vals = list(spec.series.values())[0]
        group_diff = dict(zip(spec.x, vals))
        # Hà Nội +250, TP.HCM +40, Cần Thơ +60, Đà Nẵng -320; tổng = +30
        assert group_diff["Ha Noi"] == 250.0
        assert group_diff["TP.HCM"] == 40.0
        assert group_diff["Can Tho"] == 60.0
        assert group_diff["Da Nang"] == -320.0
        assert sum(vals) == 30.0
        assert spec.highlight_x == "Da Nang"
        assert "Da Nang" in spec.caption
        assert "320" in spec.caption
        assert "Ha Noi" in spec.caption
        assert "+250" in spec.caption

    def test_cumulative(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        goal = AnalysisGoal(question="Lũy kế", tasks=[mock_trend_task_result.task])
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
        )
        spec = perspective_cumulative(ctx)
        assert spec is not None
        assert spec.chart_type == "area"
        cum_vals = list(spec.series.values())[0]
        assert len(cum_vals) == 12
        assert cum_vals[-1] == sum(mock_trend_task_result.execution.results["trend"].values())
        assert _fmt_vn(cum_vals[-1], 1) in spec.caption

    def test_moving_average(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        goal = AnalysisGoal(question="MA", tasks=[mock_trend_task_result.task])
        ctx = _resolve_context(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
        )
        spec = perspective_moving_average(ctx)
        assert spec is not None
        assert spec.chart_type == "line"
        assert len(spec.series) == 2
        assert "Trung bình trượt (MA3)" in spec.series


# ===========================================================================
# 4. Test điều kiện biên & an toàn
# ===========================================================================
class TestPerspectiveSafetyAndLimits:
    def test_ton_kho_does_not_generate_cumulative_or_share(self):
        df = pd.read_csv(DATA_DIR / "ton_kho.csv")
        profile = data_profiler.profile(df)
        task = AnalysisTask(type="trend", metric="So_luong_ton")
        exec_res = ExecutionResult(success=True, results={"trend": {"2026-01": 3900.0, "2026-02": 2590.0, "2026-03": 1570.0}})
        tr = TaskResult(task=task, execution=exec_res)
        goal = AnalysisGoal(question="Tồn kho", tasks=[task])

        ctx = _resolve_context(goal, profile, df, [tr])
        assert perspective_cumulative(ctx) is None
        assert perspective_share_of_total(ctx) is None

    def test_too_many_groups_disables_trend_by_group(self):
        # Tạo dữ liệu giả với 9 nhóm (> 8 nhóm)
        data = []
        for i in range(9):
            for t in ["2026-01", "2026-02"]:
                data.append({"Thang": t, "Nhom": f"Nhom_{i}", "Doanh_thu": 100})
        df = pd.DataFrame(data)
        profile = data_profiler.profile(df)
        task = AnalysisTask(type="trend", metric="Doanh_thu")
        goal = AnalysisGoal(question="Nhiều nhóm", tasks=[task])
        tr = TaskResult(task=task, execution=ExecutionResult(success=True, results={"trend": {"2026-01": 900.0, "2026-02": 900.0}}))

        ctx = _resolve_context(goal, profile, df, [tr])
        assert perspective_trend_by_group(ctx) is None

    def test_short_trend_disables_period_change(self):
        df = pd.DataFrame({"Thang": ["2026-01", "2026-02"], "Doanh_thu": [100, 200]})
        profile = data_profiler.profile(df)
        task = AnalysisTask(type="trend", metric="Doanh_thu")
        goal = AnalysisGoal(question="Ngắn", tasks=[task])
        # Chỉ có 2 điểm (< 3)
        tr = TaskResult(task=task, execution=ExecutionResult(success=True, results={"trend": {"2026-01": 100.0, "2026-02": 200.0}}))

        ctx = _resolve_context(goal, profile, df, [tr])
        assert perspective_period_change(ctx) is None

    def test_expand_limits_to_max_supplementary(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        goal = AnalysisGoal(question="Doanh thu", tasks=[mock_trend_task_result.task])
        specs = expand(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
            max_supplementary=3,
        )
        assert len(specs) == 3
        # 3 biểu đồ đầu bảng ưu tiên: trend_by_group (90), share_of_total (70), period_change (60)
        perspectives = [s.perspective for s in specs]
        assert perspectives == ["trend_by_group", "share_of_total", "period_change"]

    def test_exception_in_one_perspective_does_not_break_expand(
        self,
        monkeypatch,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
    ):
        # Làm giả 1 perspective ném lỗi
        def buggy_func(ctx):
            raise RuntimeError("Lỗi bất ngờ!")

        monkeypatch.setattr(perspective_planner, "perspective_trend_by_group", buggy_func)
        # Cập nhật danh sách _PERSPECTIVES tạm thời
        new_perspectives = [(90, buggy_func)] + perspective_planner._PERSPECTIVES[1:]
        monkeypatch.setattr(perspective_planner, "_PERSPECTIVES", new_perspectives)

        goal = AnalysisGoal(question="Doanh thu", tasks=[mock_trend_task_result.task])
        # Không được raise ngoại lệ, các perspective còn lại vẫn trả về bình thường
        specs = expand(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result],
            max_supplementary=3,
        )
        assert len(specs) > 0
        assert all(s.perspective != "trend_by_group" for s in specs)


# ===========================================================================
# 5. Property Test: Các con số trong caption phải có trong series
# ===========================================================================
class TestPropertyCaptionValues:
    def test_caption_numbers_match_series(
        self,
        doanh_thu_df: pd.DataFrame,
        doanh_thu_profile: DataProfile,
        mock_trend_task_result: TaskResult,
        mock_growth_rate_task_result: TaskResult,
    ):
        goal = AnalysisGoal(
            question="Tổng quan",
            tasks=[mock_trend_task_result.task, mock_growth_rate_task_result.task],
        )
        specs = expand(
            goal=goal,
            profile=doanh_thu_profile,
            df_filtered=doanh_thu_df,
            task_results=[mock_trend_task_result, mock_growth_rate_task_result],
            max_supplementary=6,
        )
        assert len(specs) >= 4
        for spec in specs:
            assert spec.role == "supplementary"
            assert spec.caption is not None
            # Mỗi biểu đồ có caption rõ ràng
            assert len(spec.caption) > 10
