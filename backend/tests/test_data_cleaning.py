"""Kiểm thử Stage 0 (làm sạch dữ liệu) và endpoint /profile-many.

Bao gồm:
- 5 test cho các hàm làm sạch riêng lẻ (_clean, _convert_vn_formatted_numbers, ...)
- 3 test tích hợp qua profile() để đảm bảo Stage 0 không phá hỏng Stage 1
- 2 test cho endpoint /profile-many qua httpx TestClient

Chạy: pytest backend/tests/test_data_cleaning.py -v
"""
from __future__ import annotations

import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.data_profiler import (
    _clean,
    _convert_vn_formatted_numbers,
    _drop_empty_unnamed_columns,
    _strip_string_columns,
    profile,
)

client = TestClient(app)


# =============================================================================
# Test hàm Stage 0 riêng lẻ
# =============================================================================


def test_strip_column_names():
    """Tên cột có khoảng trắng thừa phải được cắt bỏ."""
    df = pd.DataFrame({" Doanh_thu ": [1, 2], " Chi_nhanh ": ["HN", "HCM"]})
    cleaned = _clean(df)
    assert "Doanh_thu" in cleaned.columns
    assert "Chi_nhanh" in cleaned.columns
    assert " Doanh_thu " not in cleaned.columns


def test_drop_unnamed_empty_columns():
    """Cột Unnamed: N hoàn toàn rỗng phải bị xóa."""
    df = pd.DataFrame({
        "A": [1, 2, 3],
        "Unnamed: 1": [None, None, None],
        "Unnamed: 2": [None, None, None],
    })
    cleaned = _drop_empty_unnamed_columns(df)
    assert "Unnamed: 1" not in cleaned.columns
    assert "Unnamed: 2" not in cleaned.columns
    assert "A" in cleaned.columns


def test_keep_unnamed_column_with_data():
    """Cột Unnamed: N CÓ dữ liệu KHÔNG được xóa."""
    df = pd.DataFrame({"Unnamed: 0": [1, 2, 3], "B": ["x", "y", "z"]})
    cleaned = _drop_empty_unnamed_columns(df)
    assert "Unnamed: 0" in cleaned.columns


def test_drop_all_na_rows():
    """Dòng toàn NaN phải bị xóa sau khi _clean."""
    df = pd.DataFrame({
        "A": [1, None, 3],
        "B": ["x", None, "z"],
    })
    cleaned = _clean(df)
    assert len(cleaned) == 2
    assert cleaned["A"].notna().all()


def test_strip_string_values():
    """Giá trị chuỗi có khoảng trắng thừa phải được strip."""
    df = pd.DataFrame({"Ten": ["  Hà Nội  ", " HCM ", "Đà Nẵng"]})
    cleaned = _strip_string_columns(df)
    assert cleaned["Ten"].tolist() == ["Hà Nội", "HCM", "Đà Nẵng"]


def test_convert_vn_number_dot_separator():
    """Số dạng '1.500.000' (dấu chấm ngàn phân) phải thành 1500000.0."""
    df = pd.DataFrame({"Doanh_thu": ["1.500.000", "2.300.000", "750.000"]})
    converted = _convert_vn_formatted_numbers(df)
    assert pd.api.types.is_numeric_dtype(converted["Doanh_thu"])
    assert converted["Doanh_thu"].tolist() == [1_500_000.0, 2_300_000.0, 750_000.0]


def test_convert_vn_number_with_decimal():
    """Số dạng '1.500,50' (chấm ngàn, phẩy thập phân) thành 1500.5."""
    df = pd.DataFrame({"Gia": ["1.500,50", "2.300,00", "750,25"]})
    converted = _convert_vn_formatted_numbers(df)
    assert pytest.approx(converted["Gia"].tolist()) == [1500.5, 2300.0, 750.25]


def test_no_false_conversion_on_text_column():
    """Cột text bình thường (< 80% giống số VN) KHÔNG được coi là số."""
    df = pd.DataFrame({"Ten": ["Hà Nội", "1.500", "HCM", "Đà Nẵng", "Cần Thơ"]})
    converted = _convert_vn_formatted_numbers(df)
    # Chỉ 1/5 = 20% giống pattern số → không chuyen
    assert pd.api.types.is_string_dtype(converted["Ten"])


# =============================================================================
# Test tích hợp: Stage 0 không phá Stage 1
# =============================================================================


def test_profile_with_vn_formatted_numbers():
    """profile() phải đoán đúng cột số sau khi Stage 0 chuyển '1.500.000'."""
    df = pd.DataFrame({
        "Thang": ["2026-01-01", "2026-02-01", "2026-03-01"],
        "Chi_nhanh": ["HN", "HN", "HCM"],
        "Doanh_thu": ["1.500.000", "2.300.000", "750.000"],
    })
    result = profile(df)
    assert "Doanh_thu" in result.numeric_columns
    assert result.time_column == "Thang"


def test_profile_with_unnamed_columns():
    """profile() không bị lỗi và kết quả đúng dù có cột Unnamed rỗng."""
    df = pd.DataFrame({
        "Thang": ["2026-01", "2026-02"],
        "Doanh_thu": [100, 200],
        "Unnamed: 2": [None, None],
    })
    result = profile(df)
    col_names = [c.name for c in result.columns]
    assert "Unnamed: 2" not in col_names
    assert "Doanh_thu" in result.numeric_columns


def test_profile_with_extra_whitespace():
    """profile() chịu được tên cột có khoảng trắng và giá trị chuỗi có trailing space.

    Dùng 6 hàng để tỷ lệ unique/total của Chi_nhanh (2/6 = 0.33) <= 0.5
    — đảm bảo cột được nhận diện là group column theo heuristic của
    _guess_group_columns() (ngưỡng nunique/n <= 0.5).
    """
    df = pd.DataFrame({
        " Thang ": [
            "2026-01-01 ", " 2026-02-01", "2026-03-01",
            "2026-04-01", "2026-05-01", "2026-06-01",
        ],
        " Chi_nhanh ": [" HN ", "HCM ", " HN ", "HCM ", " HN ", "HCM "],
        " Doanh_thu ": [100.0, 200.0, 150.0, 180.0, 120.0, 210.0],
    })
    result = profile(df)
    assert result.time_column == "Thang"
    assert result.group_columns == ["Chi_nhanh"]


# =============================================================================
# Test endpoint /profile-many
# =============================================================================


def _make_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def test_profile_many_two_files():
    """Gửi 2 file CSV → nhận lại 2 profile riêng biệt theo tên file."""
    df1 = pd.DataFrame({
        "Thang": ["2026-01-01", "2026-02-01"],
        "Doanh_thu": [100, 200],
    })
    df2 = pd.DataFrame({
        "San_pham": ["Ao", "Quan"],
        "So_luong": [10, 20],
    })
    files = [
        ("files", ("file_a.csv", _make_csv_bytes(df1), "text/csv")),
        ("files", ("file_b.csv", _make_csv_bytes(df2), "text/csv")),
    ]
    response = client.post("/profile-many", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "file_a.csv" in data
    assert "file_b.csv" in data
    assert data["file_a.csv"]["time_column"] == "Thang"
    assert data["file_b.csv"]["time_column"] is None


def test_profile_many_empty_list_returns_error():
    """Gửi danh sách file rỗng → FastAPI trả lỗi (422 validation error
    vì trường 'files' là bắt buộc theo File(...)).
    """
    response = client.post("/profile-many", files=[])
    # FastAPI tự sinh validation error (422) khi field bắt buộc thiếu
    # — không phải 400 từ code logic của mình.
    assert response.status_code in (400, 422)
