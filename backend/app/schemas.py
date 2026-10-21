"""Hop dong du lieu (I/O contract) giua cac module trong pipeline.

Moi model tuong ung voi dau vao/dau ra cua mot module duoc mo ta trong
docs/SRS.md (muc 6) va docs/ARCHITECTURE.md. Viec dinh nghia tuong minh
cac schema nay ngay tu Tuan 1 giup cac module (O1-O5) co the duoc phat
trien va kiem thu doc lap trong cac tuan tiep theo, dung tinh than
"flexible / modular" ma LIDA (Dibia, 2023) de xuat.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    """Dau ra cua module Data Profiler (O1).

    Stage 1 (cac truong phia tren dataset_description) hoan toan dua
    tren luat (pandas), khong goi LLM. Trong do time_min/time_max la
    khoang thoi gian thuc te cua time_column (neu co) — can thiet de
    module O2 (Question Interpreter) giai nghia cac bieu thuc thoi gian
    tuong doi (vd: "12 thang gan nhat") ma KHONG phai doc lai DataFrame
    tho, giu dung ranh gioi module (NFR-05).

    Stage 2 (dataset_description, va description/semantic_type trong
    tung ColumnProfile) la TUY CHON, duoc dien boi ham enrich() —
    tuong ung 2 giai doan cua SUMMARIZER trong LIDA (Dibia, 2023).
    """

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
# Tuan 1-2: type/find tung la str tu do (co tinh chua chot Literal, xem
# README "Co tinh CHUA sua"). Tuan 3 cai dat O2 that -> chot lai dung 3
# loai phan tich neu trong ke hoach 8 tuan (SRS muc 3, ghi chu Tuan 3):
# xu huong (trend), so sanh (comparison), tang/giam (growth_rate).
TaskType = Literal["trend", "comparison", "growth_rate"]
FindMode = Literal["min", "max"]
# 4 pham vi thoi gian "chuan hoa" ma LLM duoc phep chon - CHI chon nhan,
# KHONG tu tinh ngay thang cu the. Viec tinh time_start/time_end that
# (dua tren DataProfile.time_max) la logic Python tat dinh trong
# question_interpreter._resolve_time_range(), khong giao cho LLM - dung
# nguyen tac da ap dung cho O3 (tach LLM suy luan khoi tinh toan chinh xac).
TimeScope = Literal["all", "last_3_months", "last_6_months", "last_12_months", "custom"]
# Goi y bieu do LLM (O2) co the dua ra TRUOC khi co du lieu that.
# Chi 2 gia tri mang tinh NGU NGHIA THUAT SU (language signal):
#   - "pie": cau hoi ngu y TY TRONG/CO CAU ("chiem bao nhieu phan tram")
#   - "area": cau hoi nhan manh KHOI LUONG TICH LUY theo thoi gian
# Moi quyet dinh khac (bar_horizontal, bar thay line khi it diem) deu
# la luat TAT DINH o O4 — chi biet SAU KHI O3 chay va co du lieu that.
ChartHint = Literal["area", "pie"]


class AnalysisTask(BaseModel):
    """Mot tac vu phan tich con duoc suy ra tu cau hoi nguoi dung."""

    type: TaskType
    metric: str  # ten cot so can tinh, vi du "Doanh_thu_trieu_vnd"
    group_by: Optional[str] = None  # ten cot nhom, vi du "Chi_nhanh"
    find: Optional[FindMode] = None  # dung cho growth_rate (chi nhanh min/max)
    chart_hint: Optional[ChartHint] = None  # goi y bieu do ngu nghia tu LLM (O2); chi la GHI CHU tham khao, O4 co the bo qua


class AnalysisGoal(BaseModel):
    """Dau ra cua module Question Interpreter (O2) dong thoi la AnalysisPlan chuan hoa.

    time_scope la nhan LLM chon; time_start/time_end la ngay cu the
    do Python tinh ra (khong phai LLM) dua tren time_scope va
    DataProfile.time_max — xem question_interpreter._resolve_time_range.
    """

    question: str
    time_scope: TimeScope = "last_12_months"  # mac dinh theo FR-11
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    tasks: list[AnalysisTask]
    levels: list[AnalysisLevel] = Field(default_factory=lambda: ["descriptive"])

    # Cac truong Analysis Plan chuan hoa theo tai lieu writing-block (1).md
    objective: Optional[str] = None  # overview, comparison, top_growers, top_decliners, contribution_to_change, forecast, prescriptive_action
    metric: Optional[str] = None
    dimension: Optional[str] = None
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

# Mo rong 12 loai bieu do theo ma tran muc phu hop
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
    requires_double_confirm: bool = False  # True neu la bieu do "khong ap dung" can xac nhan 2 lan
    confirm_step: int = 1  # 1 neu chua xac nhan buoc nao, 2 neu da xac nhan buoc 1 dang can buoc 2


class ChartOption(BaseModel):
    """Tuy chon bieu do co the chuyen doi tren the bieu do (menu ⋯)."""

    chart_type: ChartType
    verdict: Literal["recommended", "ok", "confirm", "blocked"]
    reasons: list[Reason] = Field(default_factory=list)
    requires_fetch: bool = False  # khac data_shape -> can goi /render


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
    """Dac ta mot bieu do de frontend render (Plotly/Recharts/Chart.js).

    highlight_x: ten category can to mau noi bat, vi du chi nhanh giam
    manh nhat trong task growth_rate. Frontend Tuan 7 dung field nay de
    render mau khac; O4 chi can dien dung ten, khong tu to mau.
    """

    chart_type: ChartType
    title: str
    x: list[str] = Field(default_factory=list)
    series: dict[str, list[Optional[float]]] = Field(default_factory=dict)  # {ten_chuoi: [gia_tri...]}
    highlight_x: Optional[str] = None  # category can to noi bat (neu co)
    # --- Mo rong tu De xuat Dashboard da goc nhin (deu optional -> khong pha test cu) ---
    role: Literal["primary", "supplementary"] = "primary"
    perspective: Perspective = "primary"
    caption: Optional[str] = None          # nhan xet ngan tat dinh
    highlight_series: Optional[str] = None # to dam 1 DUONG trong chart nhieu chuoi
    # --- Thong tin hien thi tieng Viet (Phan A6 de xuat) ---
    display_name: Optional[str] = None
    unit: Optional[str] = None
    # --- Mo rong cho du bao (Forecast) ---
    band: Optional[dict[str, list[Optional[float]]]] = None  # {"lower": [...], "upper": [...]}
    forecast_from: Optional[str] = None  # nhan x noi bat dau du bao
    # --- Mo rong cho lua chon bieu do tuy y (Chart Arbitration) ---
    data_shape: DataShape = "category_series"
    selection: Literal["auto", "user"] = "auto"
    notes: list[str] = Field(default_factory=list)
    options: list[ChartOption] = Field(default_factory=list)
    # --- Du lieu rieng cho hinh dang dac thu (kpi, waterfall, points, matrix, boxes, bins) ---
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
    """Ghep 1 AnalysisTask voi ExecutionResult tuong ung.

    Dung lam input cho O4 (Chart Generator) va O5 (Insight Generator,
    Tuan 6), vi ca 2 module deu can biet "task nay loai gi" + "ket qua
    tinh duoc la gi" cung luc.

    Ly do tach rieng thay vi dung chu ky cu (tasks, execution):
    Orchestrator chay tung AnalysisTask rieng le (run_task()), moi task
    co ExecutionResult doc lap. AnalysisGoal co the co nhieu task nen
    viec ghep 1-1 (task, execution) la cach duy nhat dam bao O4 biet
    ket qua nao thuoc ve task nao.
    """

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

    generated_at: str            # ISO 8601
    model_name: str              # Model AI dang dung
    rows_total: int              # Tong so dong trong file
    rows_used: int               # So dong thuc su duoc loc va su dung
    goal_summary: str            # Cau tom tat "He thong hieu cau hoi cua ban la..."
    notes: list[str] = Field(default_factory=list)  # Cac luu y tinh toan, fallback...
    deepen: dict[str, ModeAvailability] = Field(default_factory=dict)  # Kha nang dung cac cap deepen


# ---------------------------------------------------------------------------
# Ket qua tong hop tra ve cho client (FR-09)
# ---------------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    goal: AnalysisGoal
    task_results: list[TaskResult] = Field(default_factory=list)  # thay execution don le
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

    id: str                                  # "F1", "F2"... on dinh trong 1 lan chay
    kind: Literal["total", "contribution", "driver", "correlation", "forecast", "share"]
    entity: Optional[str] = None             # ten nhom GIU NGUYEN nhu trong du lieu
    metric: str                              # ten hien thi (Viet hoa)
    value: float
    unit: Optional[str] = None
    period: Optional[str] = None
    estimate: bool = False                   # True voi moi so du bao
    text: str                                # cau mo ta tat dinh


class Recommendation(BaseModel):
    """Mot khuyen nghi hanh dong duoc kiem chung bang trich dan fact_ids."""

    title: str
    action: str
    rationale: str
    fact_ids: list[str]
    priority: Literal["cao", "trung bình", "thấp"]
    caveat: str                              # bat buoc: dieu can kiem chung


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

    level: AnalysisLevel                         # cap duoc yeu cau
    sections: list[Section] = Field(default_factory=list)  # prescriptive: co the tra them diagnostic, forecast lam can cu
    recommendations: list[Recommendation] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InterpretResponse(BaseModel):
    """Phan hoi tu POST /interpret (O1 + O2 + resolve_levels)."""

    goal: AnalysisGoal
    levels: list[AnalysisLevel]        # SAU khi hop nhat mode + goal.levels + kha dung
    notices: list[Notice] = Field(default_factory=list)
    goal_summary: str                  # cau "He thong hieu cau hoi cua ban la..."
    chart_check: Optional[ChartVerdict] = None  # ket qua tham dinh bieu do tuy y (neu co chart_pref)
