"""Module Chart Rules — Luat danh gia, canh bao, chan va tu dong chon bieu do.

Thong nhat giua che do Tu dong (auto_pick tu thay the) va che do Chon tay (check_chart_choice canh bao/chan).
Moi luat tra ve ma ly do (code), muc do (block, confirm, info), thong diep tieng Viet va goi y thay the.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Literal, Optional

import pandas as pd

from ..schemas import (
    AnalysisLevel,
    AnalysisTask,
    ChartOption,
    ChartType,
    ChartVerdict,
    DataProfile,
    Reason,
    TaskResult,
)
from .chart_fitness import (
    CHART_DATA_SHAPE,
    CHART_DISPLAY_NAMES,
    CHART_ICONS,
    CHART_STATUS,
    FITNESS_MATRIX,
    get_fitness,
)

logger = logging.getLogger(__name__)

LEVEL_NAMES: dict[AnalysisLevel, str] = {
    "descriptive": "Tổng quan",
    "diagnostic": "Tìm nguyên nhân",
    "forecast": "Dự đoán tương lai",
    "prescriptive": "Gợi ý chiến lược",
}


@dataclass
class ChartContext:
    """Ngu canh du lieu de danh gia tinh hop ly cua bieu do."""

    n_categories: int = 0
    n_points: int = 0
    n_series: int = 1
    has_negative: bool = False
    n_numeric_cols: int = 1
    n_group_cols: int = 0
    has_time: bool = False
    n_periods: int = 0
    additivity: Literal["yes", "no", "unknown"] = "yes"
    max_label_len: int = 0
    n_obs_per_group: int = 0
    task_type: Optional[str] = None
    metric: Optional[str] = None
    group_by: Optional[str] = None


def _check_additivity(metric_name: str | None) -> Literal["yes", "no", "unknown"]:
    """Kiem tra xem chi so co the cong don duoc khong dua vao ten cot."""
    if not metric_name:
        return "yes"
    name_lower = metric_name.lower()
    non_additive_patterns = (
        "ty_le", "rate", "pct", "percent", "ratio",
        "diem", "score", "rating", "rank",
        "gia", "price", "margin", "bien"
    )
    if any(p in name_lower for p in non_additive_patterns):
        return "no"
    return "yes"


def extract_chart_context(
    profile: DataProfile,
    task: Optional[AnalysisTask] = None,
    x: Optional[list[str]] = None,
    series: Optional[dict[str, list[Optional[float]]]] = None,
    df: Optional[pd.DataFrame] = None,
) -> ChartContext:
    """Trich xuat ChartContext tu profile va du lieu da tinh."""
    n_numeric = len(profile.numeric_columns or [])
    n_groups = len(profile.group_columns or [])
    has_time = bool(profile.time_column) or (task.type == "trend" if task else False)
    n_periods = profile.n_periods or 0

    metric = task.metric if task else (profile.numeric_columns[0] if profile.numeric_columns else None)
    group_by = task.group_by if task else (profile.group_columns[0] if profile.group_columns else None)
    task_type = task.type if task else None

    additivity = _check_additivity(metric)

    n_cats = len(x) if x is not None else (int(df[group_by].nunique()) if (df is not None and group_by and group_by in df.columns) else 0)
    n_pts = len(x) if x is not None else (int(df[profile.time_column].nunique()) if (df is not None and profile.time_column and profile.time_column in df.columns) else n_periods)
    max_len = max((len(str(lbl)) for lbl in x), default=0) if x is not None else (int(df[group_by].astype(str).str.len().max()) if (df is not None and group_by and group_by in df.columns and not df[group_by].empty) else 0)
    n_ser = len(series) if series else 1

    has_neg = False
    if series:
        for vals in series.values():
            if any(v is not None and v < 0 for v in vals):
                has_neg = True
                break
    elif df is not None and metric and metric in df.columns and pd.api.types.is_numeric_dtype(df[metric]):
        has_neg = bool((df[metric] < 0).any())

    n_obs_per_group = 0
    if df is not None and group_by and group_by in df.columns:
        counts = df[group_by].value_counts()
        n_obs_per_group = int(counts.min()) if not counts.empty else 0

    return ChartContext(
        n_categories=n_cats,
        n_points=n_pts,
        n_series=n_ser,
        has_negative=has_neg,
        n_numeric_cols=n_numeric,
        n_group_cols=n_groups,
        has_time=has_time,
        n_periods=n_periods,
        additivity=additivity,
        max_label_len=max_len,
        n_obs_per_group=n_obs_per_group,
        task_type=task_type,
        metric=metric,
        group_by=group_by,
    )


# ---------------------------------------------------------------------------
# Tap luat danh gia bieu do
# ---------------------------------------------------------------------------

def evaluate_rules(
    level: AnalysisLevel,
    chart_type: ChartType,
    ctx: ChartContext,
) -> list[Reason]:
    """Danh gia tat ca cac luat du lieu va muc phu hop chien luoc."""
    reasons: list[Reason] = []
    level_name = LEVEL_NAMES.get(level, str(level))
    fitness = get_fitness(level, chart_type)

    # 1. Bieu do chua duoc ho tro trong phien ban nay (status = soon)
    if CHART_STATUS.get(chart_type) == "soon":
        reasons.append(
            Reason(
                code="UNSUPPORTED_YET",
                severity="block",
                message=f"Biểu đồ {CHART_DISPLAY_NAMES.get(chart_type, chart_type)} đang trong lộ trình phát triển (sắp có).",
                suggest=["bar", "line"],
            )
        )

    # 2. Ma tran: Khong ap dung (blocked)
    if fitness == "blocked":
        suggests: list[ChartType] = [
            t for t, fit in FITNESS_MATRIX.get(level, {}).items()
            if fit == "recommended" and CHART_STATUS.get(t) == "ready"
        ]
        reasons.append(
            Reason(
                code="NOT_APPLICABLE",
                severity="block",
                message=f"Biểu đồ {CHART_DISPLAY_NAMES.get(chart_type, chart_type)} không thể áp dụng cho chế độ '{level_name}'.",
                suggest=suggests or ["bar", "line"],
            )
        )

    # 3. Yeu cau it nhat 2 cot so (Scatter)
    if chart_type == "scatter" and ctx.n_numeric_cols < 2:
        reasons.append(
            Reason(
                code="NEEDS_TWO_MEASURES",
                severity="block",
                message="Biểu đồ phân tán cần ít nhất 2 cột số liệu để so sánh; dữ liệu của bạn chỉ có 1.",
                suggest=["bar", "line"],
            )
        )

    # 4. Yeu cau cot thoi gian (Line, Area, Waterfall thoi gian)
    if chart_type in ("line", "area") and not ctx.has_time:
        reasons.append(
            Reason(
                code="NEEDS_TIME",
                severity="block",
                message="Biểu đồ này cần một cột thời gian để thể hiện diễn biến.",
                suggest=["bar"],
            )
        )

    # 5. Yeu cau cot phan nhom (Stacked bar, Heatmap, Box)
    if chart_type in ("stacked_bar", "heatmap", "box") and ctx.n_group_cols < 1:
        reasons.append(
            Reason(
                code="NEEDS_GROUP",
                severity="block",
                message="Biểu đồ này cần ít nhất một cột phân nhóm (ví dụ chi nhánh, sản phẩm).",
                suggest=["bar"],
            )
        )

    # 6. Gia tri am (Pie, Stacked bar ty trong)
    if chart_type == "pie" and (ctx.has_negative or ctx.task_type == "growth_rate"):
        reasons.append(
            Reason(
                code="NEGATIVE_VALUES",
                severity="block",
                message="Dữ liệu có giá trị âm hoặc biến động tăng trưởng nên biểu đồ tròn không thể hiện đúng tỷ trọng.",
                suggest=["bar", "bar_horizontal"],
            )
        )

    # 7. Chi so khong cong don duoc (Not additive)
    if chart_type in ("pie", "stacked_bar") and ctx.additivity == "no":
        reasons.append(
            Reason(
                code="NOT_ADDITIVE",
                severity="block",
                message="Chỉ số này (tỷ lệ, điểm số, đơn giá) không cộng dồn được nên thể hiện tỷ trọng sẽ gây hiểu sai.",
                suggest=["bar", "bar_horizontal"],
            )
        )

    # 8. Du lieu qua it (Insufficient data)
    if chart_type == "box" and ctx.n_obs_per_group > 0 and ctx.n_obs_per_group < 5:
        reasons.append(
            Reason(
                code="INSUFFICIENT_DATA",
                severity="block",
                message=f"Chưa đủ dữ liệu để vẽ biểu đồ hộp (mỗi nhóm cần ≥ 5 quan sát, hiện có {ctx.n_obs_per_group}).",
                suggest=["bar"],
            )
        )
    if chart_type == "histogram" and ctx.n_points > 0 and ctx.n_points < 20:
        reasons.append(
            Reason(
                code="INSUFFICIENT_DATA",
                severity="block",
                message=f"Chưa đủ dữ liệu để vẽ biểu đồ tần suất (cần ≥ 20 giá trị, hiện có {ctx.n_points}).",
                suggest=["bar"],
            )
        )

    # --- CAC LUAT MUC CONFIRM (Can xac nhan) ---

    # 9. Ma tran: It phu hop voi chien luoc (STRATEGY_UNUSUAL)
    if fitness == "confirm":
        if chart_type == "pie" and level == "diagnostic":
            reasons.append(
                Reason(
                    code="STRATEGY_UNUSUAL",
                    severity="confirm",
                    message="Biểu đồ tròn thường dùng để xem cơ cấu tại một thời điểm, ít phù hợp để tìm lý do thay đổi. Biểu đồ thác nước hoặc cột phù hợp hơn.",
                    suggest=["waterfall", "bar"],
                )
            )
        elif chart_type in ("scatter", "box", "histogram") and level == "descriptive":
            reasons.append(
                Reason(
                    code="STRATEGY_UNUSUAL",
                    severity="confirm",
                    message="Biểu đồ phân tán/hộp/tần suất dùng để khám phá phân phối và quan hệ, ít phù hợp để tóm tắt tổng quan. Biểu đồ cột hoặc đường dễ đọc hơn.",
                    suggest=["bar", "line"],
                )
            )
        elif chart_type == "bar_horizontal" and level == "forecast":
            reasons.append(
                Reason(
                    code="STRATEGY_UNUSUAL",
                    severity="confirm",
                    message="Biểu đồ cột ngang ít trực quan cho diễn biến tương lai. Biểu đồ đường thường phù hợp hơn.",
                    suggest=["line", "area"],
                )
            )
        else:
            reasons.append(
                Reason(
                    code="STRATEGY_UNUSUAL",
                    severity="confirm",
                    message=f"Biểu đồ {CHART_DISPLAY_NAMES.get(chart_type, chart_type)} ít phù hợp với mục tiêu '{level_name}'.",
                    suggest=["bar", "line"],
                )
            )

    # 10. Bieu do tron qua nhieu lat (> 6)
    if chart_type == "pie" and ctx.n_categories > 6:
        reasons.append(
            Reason(
                code="TOO_MANY_SLICES",
                severity="confirm",
                message=f"Biểu đồ tròn có {ctx.n_categories} phần, rất khó so sánh. Biểu đồ cột hoặc cột ngang rõ ràng hơn.",
                suggest=["bar", "bar_horizontal"],
            )
        )

    # 11. Bieu do duong qua it diem (< 5)
    if chart_type in ("line", "area") and 0 < ctx.n_points < 5:
        reasons.append(
            Reason(
                code="TOO_FEW_POINTS",
                severity="confirm",
                message=f"Chỉ có {ctx.n_points} mốc thời gian nên đường nối nhìn rất thưa; biểu đồ cột dễ đọc hơn.",
                suggest=["bar"],
            )
        )

    # 12. Qua nhieu danh muc (> 20)
    if chart_type in ("bar", "stacked_bar") and ctx.n_categories > 20:
        reasons.append(
            Reason(
                code="TOO_MANY_CATEGORIES",
                severity="confirm",
                message=f"Có {ctx.n_categories} nhóm nên biểu đồ sẽ dày đặc; nên hiển thị nhóm nổi bật hoặc dùng cột ngang cuộn được.",
                suggest=["bar_horizontal"],
            )
        )

    # --- CAC LUAT MUC INFO (Luu y khong can hop thoai) ---

    # 13. Nhan dai tren cot dung
    if chart_type == "bar" and ctx.max_label_len > 12:
        reasons.append(
            Reason(
                code="LONG_LABELS",
                severity="info",
                message="Tên nhóm khá dài; có thể chuyển sang biểu đồ cột ngang để dễ đọc hơn.",
                suggest=["bar_horizontal"],
            )
        )

    # 14. Lay mau diem phan tan
    if chart_type == "scatter" and ctx.n_points > 500:
        reasons.append(
            Reason(
                code="SAMPLED",
                severity="info",
                message=f"Đã lấy mẫu 500 điểm ngẫu nhiên trong tổng số {ctx.n_points} điểm để tối ưu hiển thị.",
                suggest=[],
            )
        )

    return reasons


def check_chart_choice(
    level: AnalysisLevel,
    chart_type: ChartType,
    ctx: ChartContext,
    ack: set[str] | list[str] | None = None,
) -> ChartVerdict:
    """Tham dinh lua chon bieu do tu nguoi dung theo ma tran va luat du lieu.

    Tra ve:
    - blocked: Neu co bat ky ly do severity='block' nao (khong the ack de vuot qua).
    - confirm: Neu co ly do severity='confirm' ma chua duoc acknowledge trong `ack`.
    - ok: Neu hop le hoac moi ly do confirm deu da duoc nguoi dung ack.
    """
    ack_set = set(ack) if ack else set()
    reasons = evaluate_rules(level, chart_type, ctx)

    blocks = [r for r in reasons if r.severity == "block"]
    confirms = [r for r in reasons if r.severity == "confirm"]

    # Tap hop bieu do thay the khuyen nghi
    alts: list[ChartType] = []
    for r in reasons:
        for s in r.suggest:
            if s != chart_type and s not in alts and CHART_STATUS.get(s) == "ready":
                alts.append(s)

    if not alts:
        # Lay cac bieu do recommended tu ma tran
        for t, fit in FITNESS_MATRIX.get(level, {}).items():
            if fit == "recommended" and t != chart_type and CHART_STATUS.get(t) == "ready":
                alts.append(t)

    # 1. Kiem tra cac luat muc "blocked" (khong ap dung -> can xac nhan 2 lan)
    unforced_blocks = [r for r in blocks if f"force:{r.code}" not in ack_set and "force:all" not in ack_set]
    if unforced_blocks:
        step1_done = all(r.code in ack_set for r in unforced_blocks)
        confirm_step = 2 if step1_done else 1
        return ChartVerdict(
            status="blocked",
            chart_type=chart_type,
            reasons=reasons,
            alternatives=alts,
            requires_double_confirm=True,
            confirm_step=confirm_step,
        )

    # 2. Kiem tra cac luat muc "confirm" (it phu hop -> chi can xac nhan 1 lan)
    unacked_confirms = [r for r in confirms if r.code not in ack_set and "force:all" not in ack_set]
    if unacked_confirms:
        return ChartVerdict(
            status="confirm",
            chart_type=chart_type,
            reasons=reasons,
            alternatives=alts,
            requires_double_confirm=False,
            confirm_step=1,
        )

    return ChartVerdict(
        status="ok",
        chart_type=chart_type,
        reasons=reasons,
        alternatives=alts,
        requires_double_confirm=False,
        confirm_step=0,
    )


# ---------------------------------------------------------------------------
# Tu dong chon bieu do (Dung chung tap luat)
# ---------------------------------------------------------------------------

_DEFAULT_TASK_CHART: dict[str, ChartType] = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}


def auto_pick(
    level: AnalysisLevel,
    task: AnalysisTask,
    ctx: ChartContext,
) -> ChartType:
    """Chon loai bieu do toi uu o che do Tu dong.

    Thay the _pick_chart_type cua O4, dung chung 100% luat voi che do chon tay.
    Thu tu uu tien:
    1. chart_hint tu O2 (neu hop le).
    2. Loai bieu do mac dinh theo task.type.
    3. Ap dung cac luat sua loi tat dinh:
       - Pie bi blocked hoac confirm (growth_rate am, >6 lat, non-additive) -> fallback bar.
       - Trend qua it diem (< 5) -> bar.
       - Bar nhan dai (> 12 ky tu) -> bar_horizontal.
    """
    initial: ChartType = task.chart_hint or _DEFAULT_TASK_CHART.get(task.type, "bar")  # type: ignore[assignment]
    candidate: ChartType = initial

    # Kiem tra xem candidate co bi chan hay can xac nhan khong
    reasons = evaluate_rules(level, candidate, ctx)
    is_blocked_or_confirm = any(r.severity in ("block", "confirm") for r in reasons)

    if is_blocked_or_confirm:
        # Fallback an toan
        if task.type == "trend":
            candidate = "bar" if ctx.n_points < 5 else "line"
        else:
            candidate = "bar"

    # Luat sua tat dinh ve bieu dien hinh hoc
    if candidate == "bar" and ctx.max_label_len > 12:
        candidate = "bar_horizontal"

    return candidate


def list_options(
    level: AnalysisLevel,
    current: ChartType,
    ctx: ChartContext,
) -> list[ChartOption]:
    """Danh sach tat ca lua chon bieu do de hien thi trong menu the bieu do (menu ⋯)."""
    options: list[ChartOption] = []
    current_shape = CHART_DATA_SHAPE.get(current, "category_series")

    for chart_type in FITNESS_MATRIX.get(level, {}).keys():
        verdict_obj = check_chart_choice(level, chart_type, ctx, ack=None)
        fit = get_fitness(level, chart_type)

        v_label: Literal["recommended", "ok", "confirm", "blocked"] = "ok"
        if verdict_obj.status == "blocked":
            v_label = "blocked"
        elif verdict_obj.status == "confirm":
            v_label = "confirm"
        elif fit == "recommended":
            v_label = "recommended"

        shape = CHART_DATA_SHAPE.get(chart_type, "category_series")
        requires_fetch = shape != current_shape

        options.append(
            ChartOption(
                chart_type=chart_type,
                verdict=v_label,
                reasons=verdict_obj.reasons,
                requires_fetch=requires_fetch,
            )
        )

    return options


def build_chart_catalog(profile: DataProfile) -> dict[str, list[dict]]:
    """Xay dung chart_catalog cho endpoint /profile de frontend to mau picker ngay khi load file."""
    ctx = extract_chart_context(profile)
    catalog: dict[str, list[dict]] = {}

    for lvl in ("descriptive", "diagnostic", "forecast", "prescriptive"):
        level_opts: list[dict] = []
        for chart_type in FITNESS_MATRIX.get(lvl, {}).keys():
            verdict_obj = check_chart_choice(lvl, chart_type, ctx, ack=None)  # type: ignore[arg-type]
            fit = get_fitness(lvl, chart_type)  # type: ignore[arg-type]

            level_opts.append({
                "chart_type": chart_type,
                "display_name": CHART_DISPLAY_NAMES.get(chart_type, chart_type),
                "icon": CHART_ICONS.get(chart_type, "bar-chart"),
                "status": CHART_STATUS.get(chart_type, "ready"),
                "fitness": fit,
                "verdict": verdict_obj.status,
                "requires_double_confirm": verdict_obj.requires_double_confirm,
                "reasons": [r.model_dump() for r in verdict_obj.reasons],
                "data_shape": CHART_DATA_SHAPE.get(chart_type, "category_series"),
            })
        catalog[lvl] = level_opts

    return catalog
