"""Kiểm thử module O1 (Data Profiler) trên 3 bộ dữ liệu mẫu thật.

Chạy: pytest -v (từ thư mục gốc repo, cần pandas + pydantic đã cài).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.app.modules import data_profiler

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


def test_profile_doanh_thu():
    df = pd.read_csv(SAMPLES_DIR / "doanh_thu.csv")
    result = data_profiler.profile(df)

    assert result.row_count == len(df) == 48
    assert result.time_column == "Thang"
    assert result.group_columns == ["Chi_nhanh"]
    assert result.numeric_columns == ["Doanh_thu_trieu_vnd"]
    assert len(result.columns) == 3


def test_profile_ban_hang_san_pham():
    df = pd.read_csv(SAMPLES_DIR / "ban_hang_san_pham.csv")
    result = data_profiler.profile(df)

    assert result.time_column == "Ngay"
    assert set(result.group_columns) == {"Danh_muc", "San_pham"}
    assert "So_luong" in result.numeric_columns
    assert "Doanh_thu_trieu_vnd" in result.numeric_columns


def test_profile_chi_phi_van_hanh():
    df = pd.read_csv(SAMPLES_DIR / "chi_phi_van_hanh.csv")
    result = data_profiler.profile(df)

    assert result.time_column == "Thang"
    assert set(result.group_columns) == {"Chi_nhanh", "Loai_chi_phi"}
    assert result.numeric_columns == ["Chi_phi_trieu_vnd"]


def test_profile_handles_no_time_column():
    """Nếu không có cột thời gian nào, time_column phải là None (không lỗi)."""
    df = pd.DataFrame({"A": ["x", "y", "z"], "B": [1, 2, 3]})
    result = data_profiler.profile(df)

    assert result.time_column is None


def test_downstream_modules_raise_not_implemented():
    """O2-O5 là stub ở Tuần 1 - xác nhận chúng báo lỗi rõ ràng thay vì
    âm thầm trả kết quả sai."""
    from backend.app.modules import (
        chart_generator,
        code_generator,
        insight_generator,
        question_interpreter,
        sandbox_executor,
    )

    with pytest.raises(NotImplementedError):
        question_interpreter.interpret("bat ky cau hoi nao", profile=None)
    with pytest.raises(NotImplementedError):
        code_generator.generate(goal=None, profile=None)
    with pytest.raises(NotImplementedError):
        sandbox_executor.execute(code="", df=pd.DataFrame())
    with pytest.raises(NotImplementedError):
        chart_generator.generate_charts(tasks=[], execution=None)
    with pytest.raises(NotImplementedError):
        insight_generator.generate_insight(question="", execution=None)
