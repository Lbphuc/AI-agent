"""Hợp đồng dữ liệu (I/O contract) giữa các module trong pipeline.

Mỗi model tương ứng với đầu vào/đầu ra của một module được mô tả trong
docs/SRS.md (mục 6) và docs/ARCHITECTURE.md. Việc định nghĩa tường minh
các schema này ngay từ Tuần 1 giúp các module (O1-O5) có thể được phát
triển và kiểm thử độc lập trong các tuần tiếp theo, đúng tinh thần
"flexible / modular" mà LIDA (Dibia, 2023) đề xuất.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# O1 - Data Profiler
# ---------------------------------------------------------------------------
class ColumnProfile(BaseModel):
    """Thông tin hồ sơ của một cột dữ liệu."""

    name: str
    dtype: str
    n_unique: int
    n_missing: int
    samples: list[str] = Field(default_factory=list)
    min: Optional[str] = None
    max: Optional[str] = None
    # --- Stage 2 (tùy chọn, làm giàu bằng LLM) ---
    description: Optional[str] = None
    semantic_type: Optional[str] = None


class DataProfile(BaseModel):
    """Đầu ra của module Data Profiler (O1).

    Stage 1 (các trường phía trên `dataset_description`) hoàn toàn dựa
    trên luật (pandas), không gọi LLM. Trong đó `time_min`/`time_max`
    là khoảng thời gian thực tế của `time_column` (nếu có) — cần thiết
    để module O2 (Question Interpreter) giải nghĩa các biểu thức thời
    gian tương đối (vd: "12 tháng gần nhất") mà KHÔNG phải đọc lại
    DataFrame thô, giữ đúng ranh giới module (NFR-05).

    Stage 2 (`dataset_description`, và `description`/`semantic_type`
    trong từng ColumnProfile) là TÙY CHỌN, được điền bởi hàm
    `enrich()` — tương ứng 2 giai đoạn của SUMMARIZER trong LIDA
    (Dibia, 2023).
    """

    row_count: int
    columns: list[ColumnProfile]
    time_column: Optional[str] = None
    time_min: Optional[str] = None
    time_max: Optional[str] = None
    group_columns: list[str] = Field(default_factory=list)
    numeric_columns: list[str] = Field(default_factory=list)
    # --- Stage 2 (tùy chọn, làm giàu bằng LLM) ---
    dataset_description: Optional[str] = None


# ---------------------------------------------------------------------------
# O2 - Question Interpreter
# ---------------------------------------------------------------------------
# Tuần 1-2: type/find từng là str tự do (cố tình chưa chốt Literal, xem
# README "Cố tình CHƯA sửa"). Tuần 3 cài đặt O2 thật -> chốt lại đúng 3
# loại phân tích nêu trong kế hoạch 8 tuần (SRS mục 3, ghi chú Tuần 3):
# xu hướng (trend), so sánh (comparison), tăng/giảm (growth_rate).
TaskType = Literal["trend", "comparison", "growth_rate"]
FindMode = Literal["min", "max"]
# 4 pham vi thoi gian "chuan hoa" ma LLM duoc phep chon - CHỈ chọn nhãn,
# KHÔNG tự tính ngày tháng cụ thể. Việc tính time_start/time_end thật
# (dua tren DataProfile.time_max) la logic Python tat dinh trong
# question_interpreter._resolve_time_range(), khong giao cho LLM - dung
# nguyen tac da ap dung cho O3 (tach LLM suy luan khoi tinh toan chinh
# xac).
TimeScope = Literal["all", "last_3_months", "last_6_months", "last_12_months", "custom"]


class AnalysisTask(BaseModel):
    """Một tác vụ phân tích con được suy ra từ câu hỏi người dùng."""

    type: TaskType
    metric: str  # tên cột số cần tính, ví dụ "Doanh_thu_trieu_vnd"
    group_by: Optional[str] = None  # tên cột nhóm, ví dụ "Chi_nhanh"
    find: Optional[FindMode] = None  # dùng cho growth_rate (chi nhánh min/max)


class AnalysisGoal(BaseModel):
    """Đầu ra của module Question Interpreter (O2).

    `time_scope` là nhãn LLM chọn; `time_start`/`time_end` là ngày cụ
    thể do Python tính ra (không phải LLM) dựa trên `time_scope` và
    `DataProfile.time_max` — xem question_interpreter._resolve_time_range.
    """

    question: str
    time_scope: TimeScope = "last_12_months"  # mac dinh theo FR-11
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    tasks: list[AnalysisTask]


# ---------------------------------------------------------------------------
# O3 - Code Generator + Sandbox Executor
# ---------------------------------------------------------------------------
class CodeGenResult(BaseModel):
    """Đầu ra của bước sinh mã (LLM, fill-in-the-middle)."""

    code: str
    expected_outputs: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    """Đầu ra của Sandbox Executor sau khi thực thi mã."""

    success: bool
    results: dict = Field(default_factory=dict)
    error: Optional[str] = None
    attempts: int = 1


# ---------------------------------------------------------------------------
# O4 - Chart Generator
# ---------------------------------------------------------------------------
class ChartSpec(BaseModel):
    """Đặc tả một biểu đồ để frontend render (Plotly/Recharts)."""

    chart_type: str  # "line" | "bar"
    title: str
    x: list[str]
    series: dict[str, list[float]]  # {ten_chuoi: [gia_tri...]}


# ---------------------------------------------------------------------------
# O5 - Insight Generator
# ---------------------------------------------------------------------------
class InsightResult(BaseModel):
    """Đầu ra của module Insight Generator."""

    insight_text: str
    confidence_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Kết quả tổng hợp trả về cho client (FR-09)
# ---------------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    goal: AnalysisGoal
    execution: ExecutionResult
    charts: list[ChartSpec] = Field(default_factory=list)
    insight: Optional[InsightResult] = None
