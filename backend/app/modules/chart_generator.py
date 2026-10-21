"""Module O4 — Chart Generator.

Chuyen ket qua tinh toan (ExecutionResult, tu O3b) thanh ChartSpec de
frontend render bang Recharts.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional
import pandas as pd

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

_DEFAULT_CHART: dict[str, ChartType] = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}

_MAX_PIE_SLICES = 6
_MIN_POINTS_FOR_LINE = 5
_LONG_LABEL_THRESHOLD = 12


def _pick_chart_type(
    task: AnalysisTask,
    x: list[str],
    level: AnalysisLevel = "descriptive",
) -> ChartType:
    """Ket hop goi y ngu nghia tu LLM (chart_hint) voi cac luat tat dinh thong qua auto_pick."""
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


def _build_title(task: AnalysisTask, series_vals: list[float] | None = None) -> str:
    """Sinh tiêu đề biểu đồ từ task.type, tên cột đã Việt hóa và dữ liệu thực tế."""
    metric_disp, _ = resolve_column_display(task.metric)
    group_disp, _ = resolve_column_display(task.group_by) if task.group_by else ("", None)
    agg = getattr(task, "agg", None)
    agg_prefix = "Trung bình " if agg == "mean" else ""

    if task.type == "trend":
        return f"Xu hướng {agg_prefix.lower()}{metric_disp} theo thời gian"
    if task.type == "comparison":
        if task.chart_hint == "pie":
            return f"Tỷ trọng {metric_disp} theo {group_disp}"
        return f"So sánh {agg_prefix.lower()}{metric_disp} theo {group_disp}"
    if task.type == "growth_rate":
        prefix = f"{group_disp} " if group_disp else ""
        if series_vals and len(series_vals) > 0:
            all_neg = max(series_vals) < 0
            all_pos = min(series_vals) > 0
            if all_neg:
                verb = "giảm mạnh nhất" if task.find == "min" else "suy giảm ít nhất"
            elif all_pos:
                verb = "tăng trưởng chậm nhất (giảm/ít tăng nhất)" if task.find == "min" else "tăng trưởng mạnh nhất"
            else:
                verb = "giảm mạnh nhất" if task.find == "min" else "tăng mạnh nhất"
        else:
            verb = "giảm mạnh nhất" if task.find == "min" else "tăng mạnh nhất"
        return f"{prefix}{verb} — {metric_disp} (%)"
    return metric_disp


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
    dựa vào x và series nếu chart chưa có các trường này, và gắn danh sách options.
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

    if not chart.options:
        is_forecast = bool(chart.forecast_from or chart.band)
        lvl: AnalysisLevel = "forecast" if is_forecast else "descriptive"
        ctx = ChartContext(
            n_categories=len(x_labels),
            n_points=len(x_labels),
            has_negative=any(v < 0 for v in series_vals),
            n_group_cols=1,
            has_time=is_forecast or any(w in (chart.title or "").lower() for w in ("thời gian", "kỳ", "tháng", "năm", "ngày", "xu hướng", "diễn biến")),
            n_periods=len(x_labels),
            additivity="yes" if chart.unit != "%" else "no",
            max_label_len=max((len(str(lbl)) for lbl in x_labels), default=0),
            metric=metric_disp,
        )
        chart.options = list_options(lvl, chart.chart_type, ctx)

    return chart


def _build_chart(
    task: AnalysisTask,
    execution: ExecutionResult,
    chart_pref: ChartType | None = None,
    level: AnalysisLevel = "descriptive",
    profile: DataProfile | None = None,
    notes: list[str] | None = None,
) -> ChartSpec | None:
    """Xay ChartSpec tu 1 (task, execution) da thanh cong."""
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

    if task.type == "trend" and len(data) >= 2:
        try:
            parsed_dates = pd.to_datetime(list(data.keys()), errors="coerce")
            if not parsed_dates.isna().any():
                s = pd.Series(series_vals, index=parsed_dates).sort_index()
                time_span_days = (s.index.max() - s.index.min()).days
                if time_span_days > 60 and len(s) > 35:
                    agg_fn = "mean" if ("tỷ lệ" in str(task.metric).lower() or "rate" in str(task.metric).lower()) else "sum"
                    s_monthly = s.resample("MS").agg(agg_fn)
                    x = [d.strftime("%Y-%m") for d in s_monthly.index]
                    series_vals = [round(float(v), 2) for v in s_monthly.values]
                else:
                    x = [d.strftime("%Y-%m") if (d.day == 1 and time_span_days > 60) else d.strftime("%Y-%m-%d") for d in s.index]
                    series_vals = [round(float(v), 2) for v in s.values]
        except Exception as exc:
            logger.warning("Không thể chuẩn hóa chuỗi thời gian cho task trend: %s", exc)

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

    chart_unit = "%" if task.type == "growth_rate" else unit
    # Giữ khóa series là task.metric để tương thích ngược với các bài kiểm thử,
    # đồng thời đặt display_name rõ ràng để giao diện hiển thị "% Thay đổi <Metric>"
    series_key = task.metric
    if task.type == "growth_rate":
        disp_name = f"% Thay đổi {metric_disp}"
    else:
        disp_name = metric_disp

    return ChartSpec(
        chart_type=chart_type,
        title=_build_title(task, series_vals),
        x=x,
        series={series_key: final_series_vals},
        highlight_x=highlight_x,
        display_name=disp_name,
        unit=chart_unit,
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


def generate_charts(
    task_results: list[TaskResult],
    chart_pref: Optional[ChartType] = None,
    chart_prefs: Optional[list[ChartType]] = None,
    level: AnalysisLevel = "descriptive",
    profile: Optional[DataProfile] = None,
    confirmed_notes: Optional[list[str]] = None,
    confirmed_notes_by_pref: Optional[dict[str, list[str]]] = None,
) -> list[ChartSpec]:
    """Sinh danh sach ChartSpec tu tat ca TaskResult thanh cong."""
    charts: list[ChartSpec] = []

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

    return charts
