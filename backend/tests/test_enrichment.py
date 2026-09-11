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


def test_enrich_with_broken_llm_falls_back_gracefully(base_profile):
    """Lỗi LLM ở bước tùy chọn không được phép làm sập pipeline."""
    result = data_profiler.enrich(base_profile, llm=BrokenLLMClient())
    assert result.dataset_description is None
