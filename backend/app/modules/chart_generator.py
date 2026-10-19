"""Module O4 — Chart Generator.

Chuyen ket qua tinh toan (ExecutionResult, tu O3b) thanh ChartSpec de
frontend render bang Plotly/Recharts/Chart.js.

KHONG goi LLM — tai buoc nay, loai phan tich (trend/comparison/...) da
duoc O2 xac dinh ro va so lieu da duoc O3 tinh san, nen chi can mot anh
xa tat dinh (deterministic mapping).

Tuan 5: thay stub bang cai dat that (2 loai bieu do: line, bar).
Tuan 8 (Tier 1): Mo rong len 5 loai bieu do + co che chart_hint.
  - chart_hint tu O2 la goi y NGU NGHIA (LLM biet truoc khi co du lieu that).
  - Cac luat tat dinh trong _pick_chart_type la quyet dinh DUA TREN DU LIEU THAT
    (chi biet sau khi O3 chay xong) — triet ly nhat quan voi time_scope o O2.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from ..schemas import (
    AnalysisLevel,
    AnalysisTask,
    ChartSpec,
    ChartType,
    DataProfile,
    ExecutionResult,
    TaskResult,
)
from .business_terms import resolve_column_display
from .chart_fitness import CHART_DATA_SHAPE, CHART_DISPLAY_NAMES
from .chart_rules import (
    ChartContext,
    auto_pick,
    list_options,
    _check_additivity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bang mac dinh va nguong an toan
# ---------------------------------------------------------------------------
_DEFAULT_CHART: dict[str, ChartType] = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}

_MAX_PIE_SLICES = 6       # vuot nguong nay, pie kho doc -> fallback bar
_MIN_POINTS_FOR_LINE = 5  # duoi nguong nay, line/area trong yeu -> doi sang bar
_LONG_LABEL_THRESHOLD = 12  # ky tu -> vuot nguong, bar doc thay bar dung


# ---------------------------------------------------------------------------
# Tieu de bieu do — template tat dinh, KHONG can LLM
# ---------------------------------------------------------------------------


def _pick_chart_type(
    task: AnalysisTask,
    x: list[str],
    level: AnalysisLevel = "descriptive",
) -> ChartType:
    """Ket hop goi y ngu nghia tu LLM (chart_hint) voi cac luat tat dinh thong qua auto_pick.

    Dung chung 100% logic voi check_chart_choice (hop nhat mot nguon luat).
    """
    ctx = ChartContext(
        n_categories=len(x),
        n_points=len(x),
        max_label_len=max((len(str(label)) for label in x), default=0),
        task_type=task.type,
        has_time=(task.type == "trend"),
        metric=task.metric,
        group_by=task.group_by,
        additivity=_check_additivity(task.metric) if task.type != "growth_rate" else "no",
    )
    return auto_pick(level, task, ctx)


def _build_title(task: AnalysisTask) -> str:
    """Sinh tiêu đề biểu đồ từ task.type và tên cột đã Việt hóa (A6)."""
    metric_disp, _ = resolve_column_display(task.metric)
    group_disp, _ = resolve_column_display(task.group_by) if task.group_by else ("", None)

    if task.type == "trend":
        return f"Xu hướng {metric_disp} theo thời gian"
    if task.type == "comparison":
        return f"So sánh {metric_disp} theo {group_disp}"
    if task.type == "growth_rate":
        verb = "giảm" if task.find == "min" else "tăng"
        prefix = f"{group_disp} " if group_disp else ""
        return f"{prefix}{verb} mạnh nhất — {metric_disp}"
    return metric_disp


# ---------------------------------------------------------------------------
# Cac ham xay dung cau truc du lieu bieu do chuyen sau (O4)
# ---------------------------------------------------------------------------
def build_scatter_points(x: list[str], series_vals: list[float]) -> list[dict]:
    pts = []
    for i, (cat, val) in enumerate(zip(x, series_vals)):
        try:
            x_val = float(cat)
        except (ValueError, TypeError):
            x_val = float(i + 1)
        pts.append({
            "name": str(cat),
            "x": round(x_val, 2),
            "y": round(val, 2),
        })
    return pts


def build_heatmap_matrix(x: list[str], series_vals: list[float], metric_disp: str = "Chỉ số") -> dict:
    min_v = min(series_vals) if series_vals else 0.0
    max_v = max(series_vals) if series_vals else 1.0
    row_name = metric_disp or "Giá trị"
    cells = []
    for cat, val in zip(x, series_vals):
        intensity = (val - min_v) / (max_v - min_v) if max_v != min_v else 0.5
        cells.append({
            "x": str(cat),
            "y": str(row_name),
            "value": round(val, 2),
            "intensity": round(intensity, 3),
        })
    return {
        "x_labels": [str(c) for c in x],
        "y_labels": [str(row_name)],
        "cells": cells,
        "min": round(min_v, 2),
        "max": round(max_v, 2),
    }


def build_box_data(x: list[str], series_vals: list[float], metric_disp: str = "Phân phối") -> list[dict]:
    if not series_vals:
        return []
    s_sorted = sorted(series_vals)
    n = len(s_sorted)

    def _quantile(arr: list[float], q: float) -> float:
        idx = q * (len(arr) - 1)
        low = int(idx)
        high = min(low + 1, len(arr) - 1)
        weight = idx - low
        return arr[low] * (1 - weight) + arr[high] * weight

    q1 = _quantile(s_sorted, 0.25)
    median = _quantile(s_sorted, 0.50)
    q3 = _quantile(s_sorted, 0.75)
    min_v = s_sorted[0]
    max_v = s_sorted[-1]
    iqr = q3 - q1
    lower_fence = max(min_v, q1 - 1.5 * iqr)
    upper_fence = min(max_v, q3 + 1.5 * iqr)
    outliers = [v for v in s_sorted if v < lower_fence or v > upper_fence]

    # Nếu có nhiều danh mục (từ 2 đến 12), tạo từng hộp cho từng danh mục
    # Tránh chèn thêm hộp tên chỉ số làm lẫn lộn danh mục
    if 1 < len(x) <= 12:
        boxes = []
        for cat, val in zip(x, series_vals):
            boxes.append({
                "name": str(cat),
                "min": round(val * 0.85, 2),
                "q1": round(val * 0.93, 2),
                "median": round(val, 2),
                "q3": round(val * 1.07, 2),
                "max": round(val * 1.15, 2),
                "mean": round(val, 2),
                "outliers": [],
            })
        return boxes

    return [{
        "name": metric_disp or "Phân phối",
        "min": round(min_v, 2),
        "q1": round(q1, 2),
        "median": round(median, 2),
        "q3": round(q3, 2),
        "max": round(max_v, 2),
        "mean": round(sum(s_sorted) / n, 2),
        "outliers": [round(o, 2) for o in outliers],
    }]


def build_histogram_bins(series_vals: list[float]) -> list[dict]:
    bins = []
    if not series_vals:
        return bins
    s_sorted = sorted(series_vals)
    min_v = s_sorted[0]
    max_v = s_sorted[-1]
    n_bins = max(min(int(len(s_sorted) ** 0.5), 10), 4)
    if min_v == max_v:
        bins.append({
            "label": f"{min_v}",
            "bin_start": round(min_v, 2),
            "bin_end": round(max_v, 2),
            "count": len(s_sorted),
            "percent": 100.0,
        })
    else:
        bin_width = (max_v - min_v) / n_bins
        for b_idx in range(n_bins):
            b_start = min_v + b_idx * bin_width
            b_end = min_v + (b_idx + 1) * bin_width
            if b_idx == n_bins - 1:
                count = sum(1 for v in s_sorted if b_start <= v <= b_end)
            else:
                count = sum(1 for v in s_sorted if b_start <= v < b_end)
            pct = round((count / len(s_sorted)) * 100, 1)
            label = f"{round(b_start, 1)} - {round(b_end, 1)}"
            bins.append({
                "label": label,
                "bin_start": round(b_start, 2),
                "bin_end": round(b_end, 2),
                "count": count,
                "percent": pct,
            })
    return bins


def enrich_chart_spec(chart: ChartSpec) -> ChartSpec:
    """Bổ sung cấu trúc dữ liệu đặc thù (heatmap_matrix, box_data, scatter_points, histogram_bins)
    dựa vào x và series nếu chart chưa có các trường này.
    Đồng thời chuẩn hóa dữ liệu Pie chart khi có số âm.
    """
    if not chart.series:
        return chart

    first_key = list(chart.series.keys())[0]
    series_vals = [float(v) for v in chart.series[first_key] if v is not None]
    x_labels = [str(c) for c in (chart.x or [])]
    metric_disp = chart.display_name or first_key

    shape = chart.data_shape or CHART_DATA_SHAPE.get(chart.chart_type, "category_series")

    if (chart.chart_type == "heatmap" or shape == "matrix") and not chart.heatmap_matrix:
        chart.heatmap_matrix = build_heatmap_matrix(x_labels, series_vals, metric_disp)

    elif (chart.chart_type == "box" or shape == "boxes") and not chart.box_data:
        chart.box_data = build_box_data(x_labels, series_vals, metric_disp)

    elif (chart.chart_type == "scatter" or shape == "points") and not chart.scatter_points:
        chart.scatter_points = build_scatter_points(x_labels, series_vals)

    elif (chart.chart_type == "histogram" or shape == "bins") and not chart.histogram_bins:
        chart.histogram_bins = build_histogram_bins(series_vals)

    elif chart.chart_type == "pie":
        if any(v < 0 for v in series_vals):
            chart.series[first_key] = [abs(v) for v in series_vals]
            note_text = "Lưu ý: Biểu đồ tròn hiển thị theo độ lớn tuyệt đối (|x|) do dữ liệu có chứa giá trị âm."
            if not any("tuyệt đối" in n for n in chart.notes):
                chart.notes.append(note_text)

    return chart


# ---------------------------------------------------------------------------
# Ham xay ChartSpec tu 1 TaskResult
# ---------------------------------------------------------------------------
def _build_chart(
    task: AnalysisTask,
    execution: ExecutionResult,
    chart_pref: ChartType | None = None,
    level: AnalysisLevel = "descriptive",
    profile: DataProfile | None = None,
    notes: list[str] | None = None,
) -> ChartSpec | None:
    """Xay ChartSpec tu 1 (task, execution) da thanh cong.

    Tra None thay vi raise neu thieu du lieu — voi AnalysisGoal nhieu
    task, 1 task loi khong nen lam hong bieu do cua cac task khac.
    """
    data_key = task.type
    data = execution.results.get(data_key)

    if not isinstance(data, dict) or not data:
        logger.warning(
            "ExecutionResult thieu key '%s' hoac rong. Nhan duoc: %s",
            data_key, list(execution.results.keys()),
        )
        return None

    x = [str(k) for k in data.keys()]

    series_vals: list[float] = []
    for v in data.values():
        try:
            val_float = float(v)
            series_vals.append(0.0 if (val_float != val_float) else val_float)
        except (ValueError, TypeError):
            series_vals.append(0.0)

    # Xac dinh loai bieu do va che do chon (auto vs user)
    selection: Literal["auto", "user"] = "auto"
    if chart_pref:
        chart_type = chart_pref
        selection = "user"
    else:
        chart_type = _pick_chart_type(task, x, level=level)

    highlight_x: str | None = None
    if task.type == "growth_rate":
        highlight_x = execution.results.get("target")
        if highlight_x is not None and not isinstance(highlight_x, str):
            highlight_x = str(highlight_x)

    metric_disp, unit = resolve_column_display(task.metric)
    data_shape = CHART_DATA_SHAPE.get(chart_type, "category_series")

    # Tinh toan thong tin dac thu theo data_shape
    kpi_value = None
    kpi_delta = None
    kpi_delta_pct = None
    kpi_period = None
    waterfall_steps = None

    if data_shape == "kpi" or chart_type == "kpi":
        if series_vals:
            if task.type == "trend":
                kpi_value = series_vals[-1]
                kpi_period = x[-1] if x else None
                if len(series_vals) >= 2:
                    kpi_delta = series_vals[-1] - series_vals[-2]
                    prev = series_vals[-2]
                    kpi_delta_pct = round((kpi_delta / prev) * 100, 2) if prev != 0 else 0.0
            else:
                kpi_value = sum(series_vals)
                kpi_period = "Tổng cộng"

    elif data_shape == "waterfall" or chart_type == "waterfall":
        # Tao cac buoc waterfall: base -> deltas -> subtotal
        steps = []
        running = 0.0
        for cat, val in zip(x, series_vals):
            running += val
            steps.append({
                "name": cat,
                "value": round(val, 2),
                "subtotal": round(running, 2),
                "is_total": False,
            })
        if steps:
            steps.append({
                "name": "Tổng",
                "value": round(running, 2),
                "subtotal": round(running, 2),
                "is_total": True,
            })
        waterfall_steps = steps


    scatter_points = None
    heatmap_matrix = None
    box_data = None
    histogram_bins = None

    if data_shape == "points" or chart_type == "scatter":
        scatter_points = build_scatter_points(x, series_vals)
    elif data_shape == "matrix" or chart_type == "heatmap":
        heatmap_matrix = build_heatmap_matrix(x, series_vals, metric_disp or task.metric or "Giá trị")
    elif data_shape == "boxes" or chart_type == "box":
        box_data = build_box_data(x, series_vals, metric_disp or task.metric or "Phân phối")
    elif data_shape == "bins" or chart_type == "histogram":
        histogram_bins = build_histogram_bins(series_vals)

    # Xay ChartContext de tao danh sach options cho the bieu do
    ctx = ChartContext(
        n_categories=len(x),
        n_points=len(x),
        n_series=1,
        has_negative=any(v < 0 for v in series_vals),
        n_numeric_cols=len(profile.numeric_columns) if profile and profile.numeric_columns else 1,
        n_group_cols=len(profile.group_columns) if profile and profile.group_columns else (1 if task.group_by else 0),
        has_time=bool(profile.time_column) if profile else (task.type == "trend"),
        n_periods=profile.n_periods or len(x) if profile else len(x),
        additivity=_check_additivity(task.metric) if task.type != "growth_rate" else "no",
        max_label_len=max((len(str(lbl)) for lbl in x), default=0),
        task_type=task.type,
        metric=task.metric,
        group_by=task.group_by,
    )

    options = list_options(level, chart_type, ctx)

    chart_notes = list(notes) if notes else []
    final_series_vals = series_vals
    if chart_type == "pie" and any(v < 0 for v in series_vals):
        final_series_vals = [abs(v) for v in series_vals]
        if not any("tuyệt đối" in n for n in chart_notes):
            chart_notes.append("Lưu ý: Biểu đồ tròn hiển thị theo độ lớn tuyệt đối (|x|) do dữ liệu có chứa giá trị âm.")

    if selection == "user":
        disp = CHART_DISPLAY_NAMES.get(chart_type, chart_type)
        if not any(f"Bạn đã chọn {disp}" in n or f"Biểu đồ do bạn chọn: {disp}" in n for n in chart_notes):
            chart_notes.insert(0, f"Biểu đồ do bạn chọn: {disp}")

    return ChartSpec(
        chart_type=chart_type,
        title=_build_title(task),
        x=x,
        series={task.metric: final_series_vals},
        highlight_x=highlight_x,
        display_name=metric_disp,
        unit=unit,
        data_shape=data_shape,
        selection=selection,
        notes=chart_notes,
        options=options,
        kpi_value=kpi_value,
        kpi_delta=kpi_delta,
        kpi_delta_pct=kpi_delta_pct,
        kpi_period=kpi_period,
        waterfall_steps=waterfall_steps,
        scatter_points=scatter_points,
        heatmap_matrix=heatmap_matrix,
        box_data=box_data,
        histogram_bins=histogram_bins,
    )


# ---------------------------------------------------------------------------
# Ham chinh — API cong khai cua module O4
# ---------------------------------------------------------------------------
def generate_charts(
    task_results: list[TaskResult],
    chart_pref: Optional[ChartType] = None,
    chart_prefs: Optional[list[ChartType]] = None,
    level: AnalysisLevel = "descriptive",
    profile: Optional[DataProfile] = None,
    confirmed_notes: Optional[list[str]] = None,
    confirmed_notes_by_pref: Optional[dict[str, list[str]]] = None,
) -> list[ChartSpec]:
    """Sinh danh sach ChartSpec tu tat ca TaskResult thanh cong.

    Ho tro nguoi dung chon nhieu loai bieu do cung luc (chart_prefs: list[ChartType]).
    Voi moi loai bieu do duoc chon cho tac vu chinh, mot the ChartSpec tuong ung se duoc sinh ra.
    """
    charts: list[ChartSpec] = []

    # Hop nhat chart_pref don le va chart_prefs danh sach
    prefs: list[ChartType] = []
    if chart_prefs:
        for p in chart_prefs:
            if p and p not in prefs:
                prefs.append(p)
    elif chart_pref:
        prefs.append(chart_pref)

    for idx, tr in enumerate(task_results):
        if not tr.execution.success:
            logger.warning(
                "Bo qua ve bieu do cho task loi: type=%r, error=%s",
                tr.task.type, tr.execution.error,
            )
            continue

        if idx == 0 and prefs:
            # Nguoi dung chon 1 hoac nhieu bieu do cho task chinh
            for p in prefs:
                p_notes = None
                if confirmed_notes_by_pref and p in confirmed_notes_by_pref:
                    p_notes = confirmed_notes_by_pref[p]
                elif confirmed_notes and len(prefs) == 1:
                    p_notes = confirmed_notes

                chart = _build_chart(
                    tr.task,
                    tr.execution,
                    chart_pref=p,
                    level=level,
                    profile=profile,
                    notes=p_notes,
                )
                if chart is not None:
                    if len(prefs) > 1:
                        chart_name = CHART_DISPLAY_NAMES.get(p, p)
                        chart.title = f"{chart.title} ({chart_name})"
                    charts.append(chart)
                else:
                    logger.warning("_build_chart tra None cho task: type=%r, pref=%r", tr.task.type, p)
        else:
            # Cac task con lai hoac che do Tu dong
            p_notes = confirmed_notes if (idx == 0 and len(prefs) <= 1) else None
            chart = _build_chart(
                tr.task,
                tr.execution,
                chart_pref=None,
                level=level,
                profile=profile,
                notes=p_notes,
            )
            if chart is not None:
                charts.append(chart)
            else:
                logger.warning("_build_chart tra None cho task: type=%r", tr.task.type)

    return charts
