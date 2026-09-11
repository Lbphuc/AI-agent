"""Hợp đồng dữ liệu (I/O contract) giữa các module trong pipeline.

Mỗi model tương ứng với đầu vào/đầu ra của một module được mô tả trong
docs/SRS.md (mục 6) và docs/ARCHITECTURE.md. Việc định nghĩa tường minh
các schema này ngay từ Tuần 1 giúp các module (O1-O5) có thể được phát
triển và kiểm thử độc lập trong các tuần tiếp theo, đúng tinh thần
"flexible / modular" mà LIDA (Dibia, 2023) đề xuất.
"""
from __future__ import annotations

from typing import Optional

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
class AnalysisTask(BaseModel):
    """Một tác vụ phân tích con được suy ra từ câu hỏi người dùng."""

    type: str  # "trend" | "comparison" | "growth_rate" | "extremum"
    metric: str  # tên cột số cần tính, ví dụ "Doanh_thu_trieu_vnd"
    group_by: Optional[str] = None  # tên cột nhóm, ví dụ "Chi_nhanh"
    find: Optional[str] = None  # "min" | "max" (dùng cho growth_rate/extremum)


class AnalysisGoal(BaseModel):
    """Đầu ra của module Question Interpreter (O2)."""

    question: str
    time_range: Optional[str] = None  # ví dụ "12 tháng gần nhất"
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
