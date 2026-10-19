"""Ma tran muc phu hop giua loai bieu do (ChartType) va chien luoc phan tich (AnalysisLevel).

Dua tren de xuat mo hinh 4 cap phan tich (Descriptive, Diagnostic, Forecast, Prescriptive):
- recommended (★): Khuyen nghi tot nhat cho muc tieu phan tich.
- ok (○): Dung duoc, truyen tai duoc thong tin hop ly.
- confirm (⚠): It phu hop (de gay hieu nham hoac lech muc tieu), yeu cau xac nhan.
- blocked (✕): Khong the ap dung cho cap phan tich nay (chan, khong cho phep xac nhan).
"""
from __future__ import annotations

from typing import Literal
from ..schemas import AnalysisLevel, ChartType, DataShape

FitnessLevel = Literal["recommended", "ok", "confirm", "blocked"]
ChartStatus = Literal["ready", "soon"]

# Ma tran danh gia muc phu hop: Level x ChartType -> FitnessLevel
FITNESS_MATRIX: dict[AnalysisLevel, dict[ChartType, FitnessLevel]] = {
    "descriptive": {
        "kpi": "recommended",
        "bar": "recommended",
        "bar_horizontal": "recommended",
        "line": "recommended",
        "area": "ok",
        "pie": "ok",
        "stacked_bar": "recommended",
        "waterfall": "ok",
        "scatter": "confirm",
        "heatmap": "ok",
        "box": "confirm",
        "histogram": "confirm",
    },
    "diagnostic": {
        "kpi": "ok",
        "bar": "ok",
        "bar_horizontal": "ok",
        "line": "ok",
        "area": "ok",
        "pie": "confirm",
        "stacked_bar": "ok",
        "waterfall": "recommended",
        "scatter": "recommended",
        "heatmap": "recommended",
        "box": "recommended",
        "histogram": "recommended",
    },
    "forecast": {
        "kpi": "ok",
        "bar": "ok",
        "bar_horizontal": "confirm",
        "line": "recommended",
        "area": "recommended",
        "pie": "blocked",
        "stacked_bar": "blocked",
        "waterfall": "blocked",
        "scatter": "blocked",
        "heatmap": "blocked",
        "box": "blocked",
        "histogram": "blocked",
    },
    "prescriptive": {
        "kpi": "recommended",
        "bar": "blocked",
        "bar_horizontal": "blocked",
        "line": "blocked",
        "area": "blocked",
        "pie": "blocked",
        "stacked_bar": "blocked",
        "waterfall": "blocked",
        "scatter": "blocked",
        "heatmap": "blocked",
        "box": "blocked",
        "histogram": "blocked",
    },
}

# Trang thai ho tro bieu do trong he thong
CHART_STATUS: dict[ChartType, ChartStatus] = {
    "kpi": "ready",
    "bar": "ready",
    "bar_horizontal": "ready",
    "line": "ready",
    "area": "ready",
    "pie": "ready",
    "stacked_bar": "ready",
    "waterfall": "ready",
    "scatter": "ready",
    "heatmap": "ready",
    "box": "ready",
    "histogram": "ready",
}

# Hinh dang du lieu tuong ung voi tung loai bieu do
CHART_DATA_SHAPE: dict[ChartType, DataShape] = {
    "kpi": "kpi",
    "bar": "category_series",
    "bar_horizontal": "category_series",
    "line": "category_series",
    "area": "category_series",
    "pie": "category_series",
    "stacked_bar": "category_series",
    "waterfall": "waterfall",
    "scatter": "points",
    "heatmap": "matrix",
    "box": "boxes",
    "histogram": "bins",
}

# Ten hien thi tieng Viet than thien
CHART_DISPLAY_NAMES: dict[ChartType, str] = {
    "kpi": "Thẻ chỉ số (KPI)",
    "bar": "Biểu đồ cột",
    "bar_horizontal": "Biểu đồ cột ngang",
    "line": "Biểu đồ đường",
    "area": "Biểu đồ miền (Area)",
    "pie": "Biểu đồ tròn (Pie)",
    "stacked_bar": "Biểu đồ cột chồng",
    "waterfall": "Biểu đồ thác nước (Waterfall)",
    "scatter": "Biểu đồ phân tán (Scatter)",
    "heatmap": "Bản đồ nhiệt (Heatmap)",
    "box": "Biểu đồ hộp (Box Plot)",
    "histogram": "Biểu đồ tần suất (Histogram)",
}

# Bieu tuong icon nhe cho giao dien
CHART_ICONS: dict[ChartType, str] = {
    "kpi": "hash",
    "bar": "bar-chart-2",
    "bar_horizontal": "align-left",
    "line": "trending-up",
    "area": "layers",
    "pie": "pie-chart",
    "stacked_bar": "bar-chart",
    "waterfall": "activity",
    "scatter": "circle",
    "heatmap": "grid",
    "box": "box",
    "histogram": "sliders",
}


def get_fitness(level: AnalysisLevel, chart_type: ChartType) -> FitnessLevel:
    """Tra ve muc phu hop giua level va chart_type."""
    level_dict = FITNESS_MATRIX.get(level, FITNESS_MATRIX["descriptive"])
    return level_dict.get(chart_type, "blocked")
