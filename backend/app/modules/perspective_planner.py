"""Module Perspective Planner (Dashboard đa góc nhìn — 1 câu hỏi, nhiều biểu đồ).

Thêm các biểu đồ BỔ SUNG (role='supplementary') quanh câu trả lời chính,
hoàn toàn TẤT ĐỊNH (pandas thuần / tính từ TaskResult có sẵn), KHÔNG thêm
bất kỳ lệnh gọi LLM nào, không cần sandbox, giữ nguyên độ trễ (NFR-01 <= 15s).

Các góc nhìn được đăng ký theo độ ưu tiên:
1. (90) trend_by_group        - Line nhiều chuỗi theo nhóm
2. (70) share_of_total        - Pie tỷ trọng theo nhóm
3. (60) period_change         - Bar % thay đổi so với kỳ trước từ trend
4. (50) contribution_to_change- Bar đóng góp thay đổi (cuối - đầu) theo nhóm
5. (30) cumulative            - Area lũy kế theo thời gian
6. (20) moving_average        - Line 2 chuỗi (gốc + MA3) làm mượt xu hướng
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..schemas import AnalysisGoal, ChartSpec, DataProfile, TaskResult
from .analytics.series import aggregation_policy
from .business_terms import resolve_column_display

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Định dạng số kiểu Việt Nam (dùng chung cho mọi caption)
# ---------------------------------------------------------------------------
def _fmt_vn(val: float, decimals: int = 1, force_sign: bool = False) -> str:
    """Định dạng số theo quy ước Việt Nam: dấu phẩy thập phân, dấu chấm ngăn nghìn.

    Ví dụ:
        _fmt_vn(41.9) -> '41,9'
        _fmt_vn(1250.0) -> '1.250'
        _fmt_vn(-320.0, force_sign=True) -> '-320'
        _fmt_vn(250.0, force_sign=True) -> '+250'
        _fmt_vn(1.13, decimals=2, force_sign=True) -> '+1,13'
    """
    is_neg = val < 0
    abs_val = abs(val)

    if decimals > 0:
        formatted = f"{abs_val:,.{decimals}f}"
        # Loại bỏ số 0 vô nghĩa ở phần thập phân nếu số nguyên (vd: 1250.0 -> 1250)
        if formatted.endswith(".0" * (decimals // 1)):
            formatted = f"{int(round(abs_val)):,}"
    else:
        formatted = f"{int(round(abs_val)):,}"

    # Hoán đổi dấu: tiếng Anh (1,250.5) -> tiếng Việt (1.250,5)
    vn_formatted = formatted.replace(",", "TEMP_DOT").replace(".", ",").replace("TEMP_DOT", ".")

    if is_neg:
        return f"-{vn_formatted}"
    if force_sign and val > 0:
        return f"+{vn_formatted}"
    return vn_formatted


# ---------------------------------------------------------------------------
# Kiểm tra chỉ số cộng dồn được (Addable / Summable Metric)
# ---------------------------------------------------------------------------
_NON_ADDABLE_KEYWORDS = (
    "ton_kho", "ton", "diem", "rating", "danh_gia", "inventory",
    "score", "rate", "percent", "pct", "ty_le", "phan_tram", "avg", "mean", "tuoi", "age",
)
_ADDABLE_KEYWORDS = (
    "doanh_thu", "so_luong", "chi_phi", "sales", "revenue",
    "cost", "quantity", "amount", "loi_nhuan", "profit", "tien",
)


def _is_addable_metric(metric: str, profile: DataProfile) -> bool:
    """Kiểm tra chỉ số có thể cộng dồn/tính tỷ trọng hay không.

    Quy tắc tất định:
    1. Dùng semantic_type từ O1 Stage 2 nếu có.
    2. Nếu không có, đối chiếu tên cột với danh sách từ khóa an toàn.
    3. Mặc định nếu không chắc chắn -> False (bỏ sót an toàn hơn hiển thị sai).
    """
    col_profile = next((c for c in profile.columns if c.name == metric), None)
    if col_profile and col_profile.semantic_type:
        st = col_profile.semantic_type.lower()
        if any(kw in st for kw in ("doanh_thu", "so_luong", "chi_phi", "sales", "revenue", "cost", "quantity")):
            return True
        if any(kw in st for kw in ("ton_kho", "diem", "danh_gia", "rate", "ty_le")):
            return False

    m_lower = metric.lower()
    # Kiểm tra từ khóa không cộng dồn trước (ví dụ So_luong_ton chứa 'ton' -> False)
    if any(kw in m_lower for kw in _NON_ADDABLE_KEYWORDS):
        return False
    if any(kw in m_lower for kw in _ADDABLE_KEYWORDS):
        return True
    return False


# ---------------------------------------------------------------------------
# Ngữ cảnh thực thi cho các perspective
# ---------------------------------------------------------------------------
@dataclass
class PerspectiveContext:
    goal: AnalysisGoal
    profile: DataProfile
    df_filtered: pd.DataFrame
    task_results: list[TaskResult]
    primary_metric: str
    target: str | None
    group_col: str | None
    time_col: str | None
    primary_chart_types: set[str]
    trend_data: dict[str, float] | None


def _resolve_context(
    goal: AnalysisGoal,
    profile: DataProfile,
    df_filtered: pd.DataFrame,
    task_results: list[TaskResult],
) -> PerspectiveContext:
    """Chuẩn bị ngữ cảnh dùng chung cho mọi perspective."""
    # 1. Chọn metric chính
    primary_metric = ""
    for tr in task_results:
        if tr.task.metric:
            primary_metric = tr.task.metric
            break
    if not primary_metric and goal.tasks:
        primary_metric = goal.tasks[0].metric
    if not primary_metric and profile.numeric_columns:
        primary_metric = profile.numeric_columns[0]

    # 2. Tìm target (nếu có từ task growth_rate)
    target = None
    for tr in task_results:
        if tr.task.type == "growth_rate" and tr.execution.success:
            tgt = tr.execution.results.get("target")
            if tgt:
                target = str(tgt)
                break

    # 3. Chọn cột nhóm theo luật mục 3.2
    group_col = None
    # Ưu tiên cột group_by đã xuất hiện trong task của goal
    for t in goal.tasks:
        if t.group_by and t.group_by in df_filtered.columns:
            group_col = t.group_by
            break
    # Nếu chưa có: lấy cột trong profile.group_columns có n_unique trong khoảng 2-8, chọn cột nhiều giá trị nhất
    if group_col is None:
        candidates = []
        for col_name in profile.group_columns:
            if col_name in df_filtered.columns:
                n_uniq = int(df_filtered[col_name].nunique())
                if 2 <= n_uniq <= 8:
                    candidates.append((n_uniq, col_name))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            group_col = candidates[0][1]

    # 4. Cột thời gian
    time_col = profile.time_column if profile.time_column in df_filtered.columns else None

    # 5. Các loại biểu đồ chính đã có (để tránh trùng lặp)
    primary_chart_types = set()
    for tr in task_results:
        if tr.execution.success:
            primary_chart_types.add(tr.task.type)

    # 6. Dữ liệu trend từ task chính (nếu có)
    trend_data = None
    for tr in task_results:
        if tr.task.type == "trend" and tr.execution.success:
            raw = tr.execution.results.get("trend")
            if isinstance(raw, dict) and raw:
                trend_data = {str(k): float(v) for k, v in raw.items()}
                break

    return PerspectiveContext(
        goal=goal,
        profile=profile,
        df_filtered=df_filtered,
        task_results=task_results,
        primary_metric=primary_metric,
        target=target,
        group_col=group_col,
        time_col=time_col,
        primary_chart_types=primary_chart_types,
        trend_data=trend_data,
    )


# ---------------------------------------------------------------------------
# Danh mục Perspective
# ---------------------------------------------------------------------------

def perspective_trend_by_group(ctx: PerspectiveContext) -> ChartSpec | None:
    """(B) trend_by_group: Xu hướng chỉ số theo từng nhóm qua thời gian."""
    if not ctx.time_col or not ctx.group_col or not ctx.primary_metric:
        return None
    if ctx.primary_metric not in ctx.df_filtered.columns:
        return None

    # Điều kiện: số nhóm trong khoảng 2–8
    n_groups = int(ctx.df_filtered[ctx.group_col].nunique())
    if not (2 <= n_groups <= 8):
        return None

    try:
        df_work = ctx.df_filtered.copy()
        df_work["_dt"] = pd.to_datetime(df_work[ctx.time_col], errors="coerce")
        df_work = df_work.dropna(subset=["_dt", ctx.primary_metric])

        if len(df_work) < 2:
            return None

        # Sắp xếp theo đúng trình tự thời gian (tránh lỗi sắp xếp bảng chữ cái khiến tháng 10 nhảy trước tháng 3)
        time_span_days = (df_work["_dt"].max() - df_work["_dt"].min()).days if len(df_work) > 1 else 0
        n_unique_dates = df_work["_dt"].nunique()

        agg_func, _ = aggregation_policy(ctx.primary_metric)

        # Nếu dữ liệu trải dài nhiều tháng (> 60 ngày) và nhiều mốc đơn lẻ (> 35), tự động gom nhóm theo Tháng
        if time_span_days > 60 and n_unique_dates > 35:
            df_work["_period"] = df_work["_dt"].dt.to_period("M").dt.to_timestamp()
            grouped = (
                df_work
                .groupby(["_period", ctx.group_col])[ctx.primary_metric]
                .agg(agg_func)
                .unstack()
                .sort_index()
            )
            x = [pd.Timestamp(t).strftime("%Y-%m") for t in grouped.index]
        else:
            grouped = (
                df_work
                .groupby(["_dt", ctx.group_col])[ctx.primary_metric]
                .agg(agg_func)
                .unstack()
                .sort_index()
            )
            x = [pd.Timestamp(t).strftime("%Y-%m-%d") for t in grouped.index]
    except Exception as exc:
        logger.warning("Lỗi groupby trend_by_group: %s", exc)
        return None

    if len(grouped) < 2:
        return None
    series = {
        str(col): [float(v) if pd.notna(v) else 0.0 for v in grouped[col]]
        for col in grouped.columns
    }

    # Tính thay đổi kỳ cuối - kỳ đầu để sinh caption có ý nghĩa
    first_row = grouped.iloc[0]
    last_row = grouped.iloc[-1]
    diffs = (last_row - first_row).dropna()

    caption = None
    if not diffs.empty:
        max_group = diffs.idxmax()
        min_group = diffs.idxmin()
        max_val = float(diffs[max_group])
        min_val = float(diffs[min_group])

        if ctx.target and ctx.target in diffs:
            tgt_val = float(diffs[ctx.target])
            action = "tăng" if tgt_val >= 0 else "giảm"
            caption = f"{ctx.target} {action} {_fmt_vn(abs(tgt_val), 1)} trong kỳ; {max_group} tăng mạnh nhất ({_fmt_vn(max_val, 1, force_sign=True)})."
        elif min_val < 0 and max_val > 0:
            caption = f"{max_group} tăng mạnh nhất ({_fmt_vn(max_val, 1, force_sign=True)}); {min_group} giảm mạnh nhất ({_fmt_vn(min_val, 1, force_sign=True)})."
        else:
            caption = f"{max_group} có mức thay đổi cao nhất ({_fmt_vn(max_val, 1, force_sign=True)})."

    highlight_series = ctx.target if ctx.target in series else None

    metric_disp, metric_unit = resolve_column_display(ctx.primary_metric)
    group_disp, _ = resolve_column_display(ctx.group_col)

    return ChartSpec(
        chart_type="line",
        title=f"Diễn biến {metric_disp} theo {group_disp}",
        x=x,
        series=series,
        role="supplementary",
        perspective="trend_by_group",
        caption=caption,
        highlight_series=highlight_series,
        display_name=metric_disp,
        unit=metric_unit,
    )


def perspective_share_of_total(ctx: PerspectiveContext) -> ChartSpec | None:
    """(B) share_of_total: Tỷ trọng theo nhóm (Pie Chart)."""
    if not ctx.group_col or not ctx.primary_metric:
        return None
    if ctx.primary_metric not in ctx.df_filtered.columns:
        return None
    if not _is_addable_metric(ctx.primary_metric, ctx.profile):
        return None

    # Không sinh nếu câu hỏi chính đã có pie hoặc comparison tương đương
    if "comparison" in ctx.primary_chart_types and len(ctx.primary_chart_types) == 1:
        # Nếu task chính duy nhất đã là so sánh cột này thì xem xét
        pass

    try:
        sums = ctx.df_filtered.groupby(ctx.group_col)[ctx.primary_metric].sum()
    except Exception as exc:
        logger.warning("Lỗi groupby share_of_total: %s", exc)
        return None

    # Điều kiện: số nhóm 2–6 (chuẩn pie chart)
    if not (2 <= len(sums) <= 6):
        return None

    # Mọi giá trị >= 0 và tổng > 0
    if (sums < 0).any() or sums.sum() <= 0:
        return None

    total = float(sums.sum())
    # Sắp xếp giảm dần theo tỷ trọng
    sums = sums.sort_values(ascending=False)

    x = [str(k) for k in sums.index]
    # Series dùng giá trị phần trăm để pie hiển thị chuẩn xác
    pct_series = [round(float(v) / total * 100, 1) for v in sums.values]
    metric_disp, _ = resolve_column_display(ctx.primary_metric)
    group_disp, _ = resolve_column_display(ctx.group_col)
    series = {f"Tỷ trọng {metric_disp} (%)": pct_series}

    top_name = x[0]
    top_pct = pct_series[0]
    bot_name = x[-1]
    bot_pct = pct_series[-1]
    caption = f"{top_name} chiếm tỷ trọng lớn nhất ({_fmt_vn(top_pct)}%); {bot_name} nhỏ nhất ({_fmt_vn(bot_pct)}%)."

    return ChartSpec(
        chart_type="pie",
        title=f"Tỷ trọng {metric_disp} theo {group_disp}",
        x=x,
        series=series,
        role="supplementary",
        perspective="share_of_total",
        caption=caption,
        display_name=metric_disp,
        unit="%",
    )


def perspective_period_change(ctx: PerspectiveContext) -> ChartSpec | None:
    """(A) period_change: % thay đổi so với kỳ trước từ task trend."""
    if not ctx.trend_data or len(ctx.trend_data) < 3:
        return None

    times = list(ctx.trend_data.keys())
    values = list(ctx.trend_data.values())

    # Kiểm tra giá trị đầu = 0 để tránh chia cho 0
    if values[0] == 0:
        return None

    x_out: list[str] = []
    pct_changes: list[float] = []

    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev == 0:
            return None
        pct = round((curr - prev) / prev * 100, 2)
        x_out.append(times[i])
        pct_changes.append(pct)

    if not pct_changes:
        return None

    min_val = min(pct_changes)
    max_val = max(pct_changes)
    min_idx = pct_changes.index(min_val)
    max_idx = pct_changes.index(max_val)

    caption = (
        f"Giảm mạnh nhất: {x_out[min_idx]} ({_fmt_vn(min_val, 2, force_sign=True)}%); "
        f"tăng mạnh nhất: {x_out[max_idx]} ({_fmt_vn(max_val, 2, force_sign=True)}%)."
    )

    metric_disp, _ = resolve_column_display(ctx.primary_metric)

    return ChartSpec(
        chart_type="bar",
        title=f"Biến động {metric_disp} so với kỳ trước (%)",
        x=x_out,
        series={"% Thay đổi": pct_changes},
        role="supplementary",
        perspective="period_change",
        caption=caption,
        display_name="% Thay đổi",
        unit="%",
    )


def perspective_contribution_to_change(ctx: PerspectiveContext) -> ChartSpec | None:
    """(B) contribution_to_change: Đóng góp tuyệt đối vào thay đổi tổng (kỳ cuối - kỳ đầu)."""
    if not ctx.time_col or not ctx.group_col or not ctx.primary_metric:
        return None
    if ctx.primary_metric not in ctx.df_filtered.columns:
        return None

    n_groups = int(ctx.df_filtered[ctx.group_col].nunique())
    if n_groups < 2:
        return None

    try:
        agg_func, _ = aggregation_policy(ctx.primary_metric)
        df_c = ctx.df_filtered.copy()
        df_c["_dt"] = pd.to_datetime(df_c[ctx.time_col], errors="coerce")
        df_c = df_c.dropna(subset=["_dt", ctx.primary_metric])
        grouped = (
            df_c
            .groupby(["_dt", ctx.group_col])[ctx.primary_metric]
            .agg(agg_func)
            .unstack()
            .sort_index()
        )
    except Exception as exc:
        logger.warning("Lỗi groupby contribution_to_change: %s", exc)
        return None

    if len(grouped) < 2:
        return None

    first_row = grouped.iloc[0]
    last_row = grouped.iloc[-1]
    diffs = (last_row - first_row).dropna()

    if diffs.empty:
        return None

    # Sắp xếp tăng dần theo thay đổi
    diffs = diffs.sort_values()
    x = [str(k) for k in diffs.index]
    vals = [float(v) for v in diffs.values]

    # Caption mô tả rõ bên kéo giảm và bên bù lại
    min_name = x[0]
    min_val = vals[0]
    max_name = x[-1]
    max_val = vals[-1]

    if min_val < 0 and max_val > 0:
        caption = f"{min_name} kéo giảm {_fmt_vn(abs(min_val))}; {max_name} bù lại {_fmt_vn(max_val, force_sign=True)}."
    elif min_val < 0:
        caption = f"{min_name} kéo giảm mạnh nhất ({_fmt_vn(min_val, force_sign=True)})."
    else:
        caption = f"{max_name} đóng góp tăng nhiều nhất ({_fmt_vn(max_val, force_sign=True)})."

    highlight_x = ctx.target if ctx.target in x else None
    metric_disp, metric_unit = resolve_column_display(ctx.primary_metric)
    group_disp, _ = resolve_column_display(ctx.group_col)

    return ChartSpec(
        chart_type="bar",
        title=f"Đóng góp vào thay đổi {metric_disp} theo {group_disp}",
        x=x,
        series={f"Thay đổi {metric_disp}": vals},
        highlight_x=highlight_x,
        role="supplementary",
        perspective="contribution_to_change",
        caption=caption,
        display_name=f"Thay đổi {metric_disp}",
        unit=metric_unit,
    )


def perspective_cumulative(ctx: PerspectiveContext) -> ChartSpec | None:
    """(A) cumulative: Lũy kế theo thời gian (Area Chart)."""
    if not _is_addable_metric(ctx.primary_metric, ctx.profile):
        return None
    if not ctx.trend_data or len(ctx.trend_data) < 3:
        return None

    times = list(ctx.trend_data.keys())
    values = list(ctx.trend_data.values())

    # Chỉ lũy kế khi mọi giá trị >= 0
    if any(v < 0 for v in values):
        return None

    cum_vals: list[float] = []
    current_sum = 0.0
    for v in values:
        current_sum += v
        cum_vals.append(round(current_sum, 2))

    total_str = _fmt_vn(cum_vals[-1], 1)
    caption = f"Tổng lũy kế đến kỳ cuối đạt {total_str}."
    metric_disp, metric_unit = resolve_column_display(ctx.primary_metric)

    return ChartSpec(
        chart_type="area",
        title=f"Tổng lũy kế {metric_disp} theo thời gian",
        x=times,
        series={f"Lũy kế {metric_disp}": cum_vals},
        role="supplementary",
        perspective="cumulative",
        caption=caption,
        display_name=metric_disp,
        unit=metric_unit,
    )


def perspective_moving_average(ctx: PerspectiveContext) -> ChartSpec | None:
    """(A) moving_average: Làm mượt xu hướng bằng đường MA3."""
    if not ctx.trend_data or len(ctx.trend_data) < 6:
        return None

    times = list(ctx.trend_data.keys())
    orig_vals = [round(v, 2) for v in ctx.trend_data.values()]

    ma3_vals: list[float] = []
    for i in range(len(orig_vals)):
        window = orig_vals[max(0, i - 2): i + 1]
        ma3_vals.append(round(sum(window) / len(window), 2))

    caption = "Đường trung bình trượt 3 kỳ (MA3) giúp làm mượt biến động ngắn hạn để nhận diện xu hướng nền."
    metric_disp, metric_unit = resolve_column_display(ctx.primary_metric)

    return ChartSpec(
        chart_type="line",
        title=f"Đường xu hướng mượt (MA3) — {metric_disp}",
        x=times,
        series={
            metric_disp: orig_vals,
            "Trung bình trượt (MA3)": ma3_vals,
        },
        role="supplementary",
        perspective="moving_average",
        caption=caption,
        display_name=metric_disp,
        unit=metric_unit,
    )


# ---------------------------------------------------------------------------
# Danh sách đăng ký các perspective theo thứ tự ưu tiên
# ---------------------------------------------------------------------------
_PERSPECTIVES: list[tuple[int, Callable[[PerspectiveContext], ChartSpec | None]]] = [
    (90, perspective_trend_by_group),
    (70, perspective_share_of_total),
    (60, perspective_period_change),
    (50, perspective_contribution_to_change),
    (30, perspective_cumulative),
    (20, perspective_moving_average),
]


# ---------------------------------------------------------------------------
# Hàm API chính của module
# ---------------------------------------------------------------------------
def expand(
    goal: AnalysisGoal,
    profile: DataProfile,
    df_filtered: pd.DataFrame,
    task_results: list[TaskResult],
    max_supplementary: int = 3,
) -> list[ChartSpec]:
    """Chạy các perspective đã đăng ký, bỏ qua cái không đủ điều kiện (trả None),
    sắp xếp theo priority, và cắt còn tối đa max_supplementary.

    Thiết kế an toàn:
    - Bọc try/except cho từng perspective — lỗi ở 1 góc nhìn không bao giờ
      làm hỏng các góc nhìn khác hay pipeline chính.
    - Không trùng lặp góc nhìn với biểu đồ chính.
    """
    if df_filtered.empty or not task_results:
        return []

    try:
        ctx = _resolve_context(goal, profile, df_filtered, task_results)
    except Exception as exc:
        logger.warning("Lỗi khởi tạo PerspectiveContext: %s", exc)
        return []

    candidates: list[tuple[int, ChartSpec]] = []
    q_lower = goal.question.lower()
    obj = goal.objective or ""

    for base_priority, func in _PERSPECTIVES:
        priority = base_priority

        # Điều chỉnh độ ưu tiên động dựa theo mục tiêu câu hỏi (writing-block (1).md Mục 4.3 & 10.2)
        if func == perspective_contribution_to_change:
            if obj == "contribution_to_change" or any(w in q_lower for w in ["đóng góp", "dong gop", "thay đổi tổng", "thay doi tong"]):
                priority = 150
        elif func == perspective_period_change:
            if obj in ("top_growers", "top_decliners") or any(w in q_lower for w in ["tăng trưởng", "kỳ trước", "biến động"]):
                priority = 140
        elif func == perspective_share_of_total:
            if any(w in q_lower for w in ["cơ cấu", "tỷ trọng", "phần trăm", "chiếm"]):
                priority = 130
        elif func in (perspective_moving_average, perspective_cumulative):
            # Nếu câu hỏi cụ thể về đóng góp hoặc tăng giảm, không sinh các biểu đồ phụ ít liên quan
            if obj in ("contribution_to_change", "top_decliners", "top_growers"):
                priority = -10

        if priority < 0:
            continue

        try:
            spec = func(ctx)
            if spec is not None:
                candidates.append((priority, spec))
        except Exception as exc:
            logger.warning("Lỗi khi thực hiện perspective '%s': %s", func.__name__, exc)
            continue

    # Sắp xếp theo priority giảm dần
    candidates.sort(key=lambda item: item[0], reverse=True)

    # Cắt tối đa max_supplementary biểu đồ
    selected = [spec for _, spec in candidates[:max_supplementary]]
    return selected
