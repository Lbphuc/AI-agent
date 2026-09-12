"""Kiểm thử Stage 2 (làm giàu bằng LLM) của module O1.

Dùng client LLM GIẢ LẬP (không gọi API thật) để kiểm thử logic ghép
nối (merge) một cách xác định (deterministic), không phụ thuộc mạng
hay chi phí API — đúng nguyên tắc tách rời "logic nghiệp vụ" và "lệnh
gọi LLM thật" đã nêu trong docs/ARCHITECTURE.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.app.modules import data_profiler

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


class FakeLLMClient:
    """Trả về JSON cố định, dùng để test logic merge mà không gọi mạng."""

    def complete_json(self, prompt: str) -> dict:
        assert "Chi_nhanh" in prompt  # xác nhận prompt chứa đúng tên cột
        return {
            "dataset_description": "Du lieu doanh thu theo thang va chi nhanh.",
            "columns": [
                {
                    "name": "Thang",
                    "description": "Thang ghi nhan doanh thu",
                    "semantic_type": "thoi_gian",
                },
                {
                    "name": "Chi_nhanh",
                    "description": "Ten chi nhanh",
                    "semantic_type": "chi_nhanh",
                },
                {
                    "name": "Doanh_thu_trieu_vnd",
                    "description": "Doanh thu (trieu VND)",
                    "semantic_type": "doanh_thu",
                },
            ],
        }


class BrokenLLMClient:
    """Mô phỏng LLM trả lỗi/JSON hỏng — enrich() phải fallback êm, không crash."""

    def complete_json(self, prompt: str) -> dict:
        raise ValueError("gia lap loi parse JSON tu LLM")


class NonDictLLMClient:
    """Mô phỏng LLM trả JSON hợp lệ nhưng SAI CẤU TRÚC (list thay vì
    object) — bug thực tế phát hiện khi review Tuần 1-2: nếu không
    chặn trước, `raw.get(...)` sẽ raise AttributeError không bị bắt."""

    def complete_json(self, prompt: str) -> dict:
        return ["day la mot list, khong phai dict"]  # type: ignore[return-value]


@pytest.fixture()
def base_profile():
    df = pd.read_csv(SAMPLES_DIR / "doanh_thu.csv")
    return data_profiler.profile(df)


def test_enrich_without_llm_returns_unchanged(base_profile):
    result = data_profiler.enrich(base_profile, llm=None)
    assert result.dataset_description is None


def test_enrich_with_valid_llm_merges_correctly(base_profile):
    result = data_profiler.enrich(base_profile, llm=FakeLLMClient())

    assert result.dataset_description == "Du lieu doanh thu theo thang va chi nhanh."
    chi_nhanh_col = next(c for c in result.columns if c.name == "Chi_nhanh")
    assert chi_nhanh_col.semantic_type == "chi_nhanh"
    assert chi_nhanh_col.description == "Ten chi nhanh"

    # profile GỐC không bị sửa đổi (bất biến / immutable)
    assert base_profile.dataset_description is None


def test_enrich_with_broken_llm_falls_back_gracefully(base_profile, caplog):
    """Lỗi LLM ở bước tùy chọn không được phép làm sập pipeline, VÀ
    phải được ghi log (trước bản sửa Tuần 2, lỗi bị nuốt hoàn toàn im
    lặng — mâu thuẫn với FR-10)."""
    with caplog.at_level("WARNING"):
        result = data_profiler.enrich(base_profile, llm=BrokenLLMClient())

    assert result.dataset_description is None
    assert any("that bai" in rec.message for rec in caplog.records)


def test_enrich_with_non_dict_response_does_not_crash(base_profile):
    """Trước bản sửa: raw.get(...) trên một list sẽ raise AttributeError
    không nằm trong except -> crash. Test này khóa lại hành vi đúng."""
    result = data_profiler.enrich(base_profile, llm=NonDictLLMClient())
    assert result.dataset_description is None
