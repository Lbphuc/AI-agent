"""Kiểm thử module Orchestrator (analysis_runner).

Dùng FakeLLM — không gọi mạng thật.
Kiểm tra:
1. _filter_by_time_range lọc đúng theo time_start/time_end.
2. run_task() thành công ngay lần 1.
3. run_task() retry: lỗi lần 1, đúng lần 2 → attempts=2.
4. run_task() thất bại hẳn sau max_attempts → success=False, không lặp vô hạn.
5. previous_error được truyền sang lần sinh mã tiếp theo.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.app.modules import data_profiler
from backend.app.modules.analysis_runner import _filter_by_time_range, run_task
from backend.app.schemas import AnalysisGoal, AnalysisTask, DataProfile

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def doanh_thu_df() -> pd.DataFrame:
    return pd.read_csv(SAMPLES_DIR / "doanh_thu.csv")


@pytest.fixture()
def doanh_thu_profile(doanh_thu_df) -> DataProfile:
    return data_profiler.profile(doanh_thu_df)


@pytest.fixture()
def sample_goal() -> AnalysisGoal:
    return AnalysisGoal(
        question="Chi nhánh nào giảm mạnh nhất?",
        time_scope="last_12_months",
        time_start="2025-09-01",
        time_end="2026-08-01",
        tasks=[
            AnalysisTask(
                type="growth_rate",
                metric="Doanh_thu_trieu_vnd",
                group_by="Chi_nhanh",
                find="min",
            )
        ],
    )


@pytest.fixture()
def growth_rate_task(sample_goal) -> AnalysisTask:
    return sample_goal.tasks[0]


# ---------------------------------------------------------------------------
# FakeLLM helpers
# ---------------------------------------------------------------------------

VALID_GROWTH_RATE_CODE = """\
def analyze(df):
    df_s = df.sort_values("Thang")
    first = df_s.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].first()
    last = df_s.groupby("Chi_nhanh")["Doanh_thu_trieu_vnd"].last()
    growth = ((last - first) / first * 100).round(2)
    target = growth.idxmin()
    return {"growth_rate": growth.to_dict(), "target": target}
"""

INVALID_CODE_RUNTIME_ERROR = """\
def analyze(df):
    raise RuntimeError("Lỗi giả lập lần đầu")
"""

SAFE_CODE_NO_ANALYZE = "x = 42  # không có hàm analyze()"


class FakeLLMAlwaysSuccess:
    """Luôn trả code hợp lệ."""
    def complete_json(self, prompt: str) -> dict:
        return {"code": VALID_GROWTH_RATE_CODE}


class FakeLLMFailThenSucceed:
    """Lần 1 trả code lỗi runtime, lần 2 trả code đúng."""
    def __init__(self):
        self.call_count = 0
        self.prompts: list[str] = []

    def complete_json(self, prompt: str) -> dict:
        self.call_count += 1
        self.prompts.append(prompt)
        if self.call_count == 1:
            return {"code": INVALID_CODE_RUNTIME_ERROR}
        return {"code": VALID_GROWTH_RATE_CODE}


class FakeLLMAlwaysFail:
    """Luôn trả code lỗi runtime."""
    def __init__(self):
        self.call_count = 0

    def complete_json(self, prompt: str) -> dict:
        self.call_count += 1
        return {"code": INVALID_CODE_RUNTIME_ERROR}


# ---------------------------------------------------------------------------
# Test _filter_by_time_range
# ---------------------------------------------------------------------------

class TestFilterByTimeRange:
    def test_filters_rows_within_range(self, doanh_thu_df, doanh_thu_profile):
        """Chỉ giữ lại dòng trong khoảng time_start đến time_end."""
        filtered = _filter_by_time_range(
            doanh_thu_df, doanh_thu_profile,
            time_start="2026-01-01", time_end="2026-03-01",
        )
        assert len(filtered) < len(doanh_thu_df)
        times = pd.to_datetime(filtered["Thang"])
        assert times.min() >= pd.Timestamp("2026-01-01")
        assert times.max() <= pd.Timestamp("2026-03-01")

    def test_no_filter_when_time_start_and_end_both_none(self, doanh_thu_df, doanh_thu_profile):
        """Không lọc gì nếu time_start và time_end đều None."""
        filtered = _filter_by_time_range(doanh_thu_df, doanh_thu_profile, None, None)
        assert len(filtered) == len(doanh_thu_df)

    def test_no_filter_when_no_time_column(self, doanh_thu_df):
        """Nếu profile không có cột thời gian → trả df gốc."""
        profile_no_time = DataProfile(
            row_count=len(doanh_thu_df),
            columns=[],
            time_column=None,
        )
        filtered = _filter_by_time_range(doanh_thu_df, profile_no_time, "2026-01-01", "2026-06-01")
        assert len(filtered) == len(doanh_thu_df)

    def test_filters_only_start(self, doanh_thu_df, doanh_thu_profile):
        """Chỉ có time_start (time_end=None) → lọc từ time_start trở đi."""
        filtered = _filter_by_time_range(
            doanh_thu_df, doanh_thu_profile,
            time_start="2026-06-01", time_end=None,
        )
        times = pd.to_datetime(filtered["Thang"])
        assert times.min() >= pd.Timestamp("2026-06-01")


# ---------------------------------------------------------------------------
# Test run_task — retry logic
# ---------------------------------------------------------------------------

class TestRunTask:
    def test_success_on_first_attempt(self, growth_rate_task, sample_goal, doanh_thu_profile, doanh_thu_df):
        """Code đúng ngay lần 1 → success=True, attempts=1."""
        result = run_task(
            task=growth_rate_task,
            goal=sample_goal,
            profile=doanh_thu_profile,
            df=doanh_thu_df,
            llm=FakeLLMAlwaysSuccess(),
            max_attempts=3,
        )
        assert result.success is True
        assert result.attempts == 1
        assert "growth_rate" in result.results
        assert "target" in result.results

    def test_success_on_second_attempt_with_error_feedback(
        self, growth_rate_task, sample_goal, doanh_thu_profile, doanh_thu_df
    ):
        """Lần 1 lỗi runtime, lần 2 đúng → success=True, attempts=2.
        Prompt lần 2 phải chứa thông báo lỗi của lần 1 (error feedback).
        """
        llm = FakeLLMFailThenSucceed()
        result = run_task(
            task=growth_rate_task,
            goal=sample_goal,
            profile=doanh_thu_profile,
            df=doanh_thu_df,
            llm=llm,
            max_attempts=3,
        )
        assert result.success is True
        assert result.attempts == 2
        assert llm.call_count == 2
        # Lần 2 phải có error feedback từ lần 1 trong prompt
        assert "RuntimeError" in llm.prompts[1] or "Lỗi" in llm.prompts[1]

    def test_fails_after_max_attempts(
        self, growth_rate_task, sample_goal, doanh_thu_profile, doanh_thu_df
    ):
        """Luôn lỗi → thất bại hẳn sau đúng max_attempts lần, không lặp vô hạn."""
        llm = FakeLLMAlwaysFail()
        result = run_task(
            task=growth_rate_task,
            goal=sample_goal,
            profile=doanh_thu_profile,
            df=doanh_thu_df,
            llm=llm,
            max_attempts=3,
        )
        assert result.success is False
        assert result.attempts == 3
        assert llm.call_count == 3  # đúng 3 lần, không hơn

    def test_run_task_df_filtered_before_execute(
        self, sample_goal, doanh_thu_profile, doanh_thu_df
    ):
        """df đưa vào sandbox đã được lọc đúng theo time_start/time_end."""
        received_lengths: list[int] = []

        class RecordingLLM:
            def complete_json(self, prompt: str) -> dict:
                # Code ghi lại số dòng df nhận được
                # Sandbox có __builtins__={} nên không có int/len, dùng df.shape[0] trực tiếp
                return {
                    "code": (
                        "def analyze(df):\n"
                        "    n = df.shape[0]  # numpy int64, không cần int()\n"
                        "    return {'trend': {'len': n}}\n"
                    )
                }

        # Lọc chỉ lấy tháng 2026-01 và 2026-02
        goal_narrow = AnalysisGoal(
            question="Test",
            time_scope="custom",
            time_start="2026-01-01",
            time_end="2026-02-01",
            tasks=sample_goal.tasks,
        )
        task = AnalysisTask(type="trend", metric="Doanh_thu_trieu_vnd", group_by=None, find=None)

        result = run_task(
            task=task,
            goal=goal_narrow,
            profile=doanh_thu_profile,
            df=doanh_thu_df,
            llm=RecordingLLM(),
            max_attempts=1,
        )
        assert result.success is True
        # df đã lọc → số dòng phải ít hơn tổng 48 dòng
        received_len = result.results.get("trend", {}).get("len", len(doanh_thu_df))
        assert received_len < len(doanh_thu_df)
