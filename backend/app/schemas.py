"""Hop dong du lieu (I/O contract) giua cac module trong pipeline.

Moi model tuong ung voi dau vao/dau ra cua mot module duoc mo ta trong
docs/SRS.md (muc 6) va docs/ARCHITECTURE.md.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel as _PydanticBaseModel, Field


class BaseModel(_PydanticBaseModel):
    """Lớp cơ sở tương thích song song cả Pydantic v1 lẫn Pydantic v2."""

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)  # type: ignore[misc]
        return self.dict(*args, **kwargs)

    def model_copy(self, *, update: Optional[dict[str, Any]] = None, deep: bool = False) -> Any:
        if hasattr(super(), "model_copy"):
            return super().model_copy(update=update, deep=deep)  # type: ignore[misc]
        return self.copy(update=update, deep=deep)


# ---------------------------------------------------------------------------
# O1 - Data Profiler
# ---------------------------------------------------------------------------
class ColumnProfile(BaseModel):
    """Thong tin ho so cua mot cot du lieu."""

    name: str
    dtype: str
    n_unique: int
    n_missing: int
    samples: list[str] = Field(default_factory=list)
    min: Optional[str] = None
    max: Optional[str] = None
    # --- Stage 2 (tuy chon, lam giau bang LLM) ---
    description: Optional[str] = None
    semantic_type: Optional[str] = None
    # --- Tu dien Viet hoa (Phan A6 de xuat) ---
    display_name: Optional[str] = None
    unit: Optional[str] = None


class DataProfile(BaseModel):
    """Dau ra cua module Data Profiler (O1)."""

    row_count: int
    columns: list[ColumnProfile]
    time_column: Optional[str] = None
    time_min: Optional[str] = None
    time_max: Optional[str] = None
    group_columns: list[str] = Field(default_factory=list)
    numeric_columns: list[str] = Field(default_factory=list)
    # --- Stage 2 (tuy chon, lam giau bang LLM) ---
    dataset_description: Optional[str] = None
    # --- Thong tin chuoi thoi gian & kha nang dung cac che do phan tich ---
    frequency: Optional[str] = None
    n_periods: Optional[int] = None
    availability: dict[str, ModeAvailability] = Field(default_factory=dict)
    chart_catalog: Optional[dict[str, list[dict]]] = None


# ---------------------------------------------------------------------------
# Che do va Cap do phan tich (Phan tich sau 3 cap)
# ---------------------------------------------------------------------------
AnalysisLevel = Literal["descriptive", "diagnostic", "forecast", "prescriptive"]
AnalysisMode = Literal["auto", "descriptive", "diagnostic", "forecast", "prescriptive"]


class ModeAvailability(BaseModel):
    """Kha nang su dung cua mot che do phan tich dua tren du lieu."""

    available: bool
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# O2 - Question Interpreter
# ---------------------------------------------------------------------------
TaskType = Literal["trend", "comparison", "growth_rate"]
FindMode = Literal["min", "max"]
AggFunc = Literal["sum", "mean", "count", "min", "max"]
TimeScope = Literal["all", "last_3_months", "last_6_months", "last_12_months", "custom"]
ChartHint = Literal["area", "pie"]


class AnalysisTask(BaseModel):
    """Mot tac vu phan tich con duoc suy ra tu cau hoi nguoi dung."""

    type: TaskType
    metric: str  # ten cot so can tinh, vi du "Doanh_thu_trieu_vnd"
    group_by: Optional[str] = None  # ten cot nhom, vi du "Chi_nhanh"
    find: Optional[FindMode] = None  # dung cho growth_rate hoac comparison (min/max)
    chart_hint: Optional[ChartHint] = None  # goi y bieu do ngu nghia tu LLM (O2)
    agg: Optional[AggFunc] = None  # sum | mean | count | min | max
    filters: Optional[dict[str, str]] = None  # bo loc gia tri cu the, vd {"Chi_nhanh": "TP.HCM"}
    top_k: Optional[int] = None  # gioi han Top N nhom neu cau hoi yeu cau


class AnalysisGoal(BaseModel):
    """Dau ra cua module Question Interpreter (O2) dong thoi la AnalysisPlan chuan hoa."""

    question: str
    time_scope: TimeScope = "last_12_months"  # mac dinh theo FR-11
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    custom_start: Optional[str] = None
    custom_end: Optional[str] = None
    tasks: list[AnalysisTask]
    levels: list[AnalysisLevel] = Field(default_factory=lambda: ["descriptive"])

    # Cac truong Analysis Plan chuan hoa
    objective: Optional[str] = None  # overview, comparison, top_growers, top_decliners, contribution_to_change, forecast, prescriptive_action
    metric: Optional[str] = None
    dimension: Optional[str] = None
    target: Optional[str] = None  # thuc the/nhom cu the ma nguoi dung dang hoi (vd: "Đà Nẵng", "TP.HCM")
    filters: Optional[dict[str, str]] = None
    comparison_period: Optional[str] = None
    forecast_horizon: Optional[int] = None
    analysis_methods: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# O3 - Code Generator + Sandbox Executor
# ---------------------------------------------------------------------------
class CodeGenResult(BaseModel):
    """Dau ra cua buoc sinh ma (LLM, fill-in-the-middle)."""

    code: str
    expected_outputs: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    """Dau ra cua Sandbox Executor sau khi thuc thi ma."""

    success: bool
    results: dict = Field(default_factory=dict)
    error: Optional[str] = None
    attempts: int = 1
    code: Optional[str] = None  # Doan ma Python da duoc sinh va thuc thi


# ---------------------------------------------------------------------------
# O4 - Chart Generator & Chart Fitness / Arbitration
# ---------------------------------------------------------------------------
ChartType = Literal[
    "kpi",
    "line",
    "area",
    "bar",
    "bar_horizontal",
    "pie",
    "stacked_bar",
    "waterfall",
    "scatter",
    "heatmap",
    "box",
    "histogram",
]

DataShape = Literal[
    "kpi",
    "category_series",
    "waterfall",
    "points",
    "matrix",
    "boxes",
    "bins",
]


class Reason(BaseModel):
    """Mot ly do ve muc do phu hop cua bieu do voi du lieu / chien luoc."""

    code: str
    severity: Literal["block", "confirm", "info"]
    message: str  # tieng Viet don gian, ro rang
    suggest: list[ChartType] = Field(default_factory=list)  # bieu do thay the de xuat


class ChartVerdict(BaseModel):
    """Ket luan tham dinh lua chon bieu do tu nguoi dung."""

    status: Literal["ok", "confirm", "blocked"]
    chart_type: ChartType
    reasons: list[Reason] = Field(default_factory=list)
    alternatives: list[ChartType] = Field(default_factory=list)
    requires_double_confirm: bool = False
    confirm_step: int = 1


class ChartOption(BaseModel):
    """Tuy chon bieu do co the chuyen doi tren the bieu do (menu ⋯)."""

    chart_type: ChartType
    verdict: Literal["recommended", "ok", "confirm", "blocked"]
    reasons: list[Reason] = Field(default_factory=list)
    requires_fetch: bool = False


Perspective = Literal[
    "primary",
    "period_change",
    "cumulative",
    "moving_average",
    "trend_by_group",
    "share_of_total",
    "contribution_to_change",
]


class ChartSpec(BaseModel):
    """Dac ta mot bieu do de frontend render (Recharts)."""

    chart_type: ChartType
    title: str
    x: list[str] = Field(default_factory=list)
    series: dict[str, list[Optional[float]]] = Field(default_factory=dict)
    highlight_x: Optional[str] = None
    role: Literal["primary", "supplementary"] = "primary"
    perspective: Perspective = "primary"
    caption: Optional[str] = None
    highlight_series: Optional[str] = None
    display_name: Optional[str] = None
    unit: Optional[str] = None
    band: Optional[dict[str, list[Optional[float]]]] = None
    forecast_from: Optional[str] = None
    data_shape: DataShape = "category_series"
    selection: Literal["auto", "user"] = "auto"
    notes: list[str] = Field(default_factory=list)
    options: list[ChartOption] = Field(default_factory=list)
    kpi_value: Optional[float] = None
    kpi_delta: Optional[float] = None
    kpi_delta_pct: Optional[float] = None
    kpi_period: Optional[str] = None
    waterfall_steps: Optional[list[dict]] = None
    scatter_points: Optional[list[dict]] = None
    heatmap_matrix: Optional[dict] = None
    box_data: Optional[list[dict]] = None
    histogram_bins: Optional[list[dict]] = None


class TaskResult(BaseModel):
    """Ghep 1 AnalysisTask voi ExecutionResult tuong ung."""

    task: AnalysisTask
    execution: ExecutionResult


# ---------------------------------------------------------------------------
# O5 - Insight Generator
# ---------------------------------------------------------------------------
class InsightResult(BaseModel):
    """Dau ra cua module Insight Generator."""

    insight_text: str
    confidence_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Metadata bao cao (Phan B2 - Xuat bao cao)
# ---------------------------------------------------------------------------
class ReportMeta(BaseModel):
    """Metadata bao cao ho tro kiem chung so lieu va in an / xuat file."""

    generated_at: str
    model_name: str
    rows_total: int
    rows_used: int
    goal_summary: str
    notes: list[str] = Field(default_factory=list)
    deepen: dict[str, ModeAvailability] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ket qua tong hop tra ve cho client (FR-09)
# ---------------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    goal: AnalysisGoal
    task_results: list[TaskResult] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    insight: Optional[InsightResult] = None
    meta: Optional[ReportMeta] = None


# ---------------------------------------------------------------------------
# Yeu cau xuat Excel (POST /export/xlsx)
# ---------------------------------------------------------------------------
class ExportSections(BaseModel):
    summary: bool = True
    insight: bool = True
    primary_chart: bool = True
    supplementary_charts: bool = True
    data_tables: bool = True
    methodology: bool = True
    calculation_notes: bool = True


class ExportXlsxRequest(BaseModel):
    response: AnalyzeResponse
    filename: str = "data.csv"
    org_name: Optional[str] = None
    sections: ExportSections = Field(default_factory=ExportSections)


# ---------------------------------------------------------------------------
# Phan tich sau 3 cap (Diagnostic, Forecast, Prescriptive) & Mode Pills
# ---------------------------------------------------------------------------
class Fact(BaseModel):
    """Mot su that so lieu duoc tinh tat dinh, co ID de LLM trich dan."""

    id: str
    kind: Literal["total", "contribution", "driver", "correlation", "forecast", "share"]
    entity: Optional[str] = None
    metric: str
    value: float
    unit: Optional[str] = None
    period: Optional[str] = None
    estimate: bool = False
    text: str


class Recommendation(BaseModel):
    """Mot khuyen nghi hanh dong duoc kiem chung bang trich dan fact_ids."""

    title: str
    action: str
    rationale: str
    fact_ids: list[str]
    priority: Literal["cao", "trung bình", "thấp"]
    caveat: str


class Notice(BaseModel):
    """Thong bao ngu canh khi hop nhat mode va goal.levels."""

    kind: Literal["added", "skipped", "info"]
    level: Optional[AnalysisLevel] = None
    message: str


class Section(BaseModel):
    """Mot phan ket qua cua mot cap phan tich."""

    level: AnalysisLevel
    charts: list[ChartSpec] = Field(default_factory=list)
    narrative: Optional[InsightResult] = None
    warnings: list[str] = Field(default_factory=list)


class DeepenResponse(BaseModel):
    """Phan hoi tu POST /deepen."""

    level: AnalysisLevel
    sections: list[Section] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InterpretResponse(BaseModel):
    """Phan hoi tu POST /interpret (O1 + O2 + resolve_levels)."""

    goal: AnalysisGoal
    levels: list[AnalysisLevel]
    notices: list[Notice] = Field(default_factory=list)
    goal_summary: str
    chart_check: Optional[ChartVerdict] = None


DataProfile.update_forward_refs()
