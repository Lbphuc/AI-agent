"""Kiểm thử module O1 (Data Profiler) trên 5 bộ dữ liệu mẫu thật
(gồm 2 bộ edge-case: văn bản tự do, giá trị thiếu).

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
    assert result.time_min == "2025-09-01"
    assert result.time_max == "2026-08-01"
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


def test_profile_danh_gia_khach_hang():
    """Edge case: cột số nhỏ (điểm 1-5) không được nhầm là cột thời gian;
    cột văn bản tự do (mỗi dòng gần như khác nhau) không được coi là
    cột nhóm. Đây là 2 bug thực tế phát hiện khi kiểm thử Tuần 2."""
    df = pd.read_csv(SAMPLES_DIR / "danh_gia_khach_hang.csv")
    result = data_profiler.profile(df)

    assert result.time_column is None
    assert result.time_min is None
    assert result.time_max is None
    assert result.group_columns == ["San_pham"]
    assert "Khach_hang" not in result.group_columns  # dinh danh, khong phai nhom
    assert "Nhan_xet" not in result.group_columns  # van ban tu do
    assert result.numeric_columns == ["Diem_danh_gia"]


def test_profile_ton_kho_missing_values():
    """Edge case: dữ liệu có giá trị thiếu (NaN) — n_missing phải đếm
    đúng, không được làm profile() lỗi."""
    df = pd.read_csv(SAMPLES_DIR / "ton_kho.csv")
    result = data_profiler.profile(df)

    assert result.time_column == "Thang"
    assert result.time_min == "2026-01-01"
    assert result.time_max == "2026-04-01"
    assert result.group_columns == ["Kho"]
    ton_col = next(c for c in result.columns if c.name == "So_luong_ton")
    assert ton_col.n_missing == 3


def test_downstream_modules_raise_not_implemented():
    """O3-O5 vẫn là stub (chưa tới tuần cài đặt) - xác nhận chúng báo
    lỗi rõ ràng thay vì âm thầm trả kết quả sai. O2 (Question
    Interpreter) đã cài đặt thật từ Tuần 3 -> xem
    backend/tests/test_question_interpreter.py thay vì kiểm tra ở đây."""
    from backend.app.modules import (
        chart_generator,
        code_generator,
        insight_generator,
        sandbox_executor,
    )

    with pytest.raises(NotImplementedError):
        code_generator.generate(goal=None, profile=None)
    with pytest.raises(NotImplementedError):
        sandbox_executor.execute(code="", df=pd.DataFrame())
    with pytest.raises(NotImplementedError):
        chart_generator.generate_charts(tasks=[], execution=None)
    with pytest.raises(NotImplementedError):
        insight_generator.generate_insight(question="", execution=None)
