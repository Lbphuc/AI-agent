"""Module analytics/forecast.py.

Cap 2 — Du bao (Forecast Analytics).
Thuan numpy tat dinh, khong goi LLM de tinh toan:
1. Guard nghiem ngat: tu choi neu < 15 ky hoac thieu > 20%.
2. 5 mo hinh ung vien: naive, seasonal_naive, linear, holt, seasonal_decomp.
3. Rolling-origin backtest (h=3) chon mo hinh MAPE thap nhat va tinh dai bat dinh 80%.
4. Dai bat dinh conformal tu phan vi sai so backtest thuc te.
5. Danh gia do tin cay: cao (MAPE < 5%), trung binh (< 12%), thap.
6. Sinh FactSheet du bao (estimate=True) va ChartSpec voi series, band, forecast_from.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional
import numpy as np
import pandas as pd

from ...llm_client import LLMClient
from ...schemas import AnalysisGoal, ChartSpec, DataProfile, Fact, InsightResult, Section
from ..business_terms import resolve_column_display
from .series import infer_frequency, prepare_regular_series

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cac mo hinh ung vien (~15 dong moi cai, chi dung numpy)
# ---------------------------------------------------------------------------

def _model_naive(y_train: np.ndarray, h: int, m: int = 1) -> np.ndarray:
    """Naive: lay gia tri quan sat cuoi cung."""
    last_val = y_train[-1] if len(y_train) > 0 else 0.0
    return np.full(h, last_val, dtype=float)


def _model_seasonal_naive(y_train: np.ndarray, h: int, m: int = 12) -> np.ndarray:
    """Seasonal Naive: lay lai chu ky truoc do y[t - m]."""
    if len(y_train) < m:
        return _model_naive(y_train, h, m)
    preds = []
    for step in range(1, h + 1):
        idx = -m + ((step - 1) % m)
        preds.append(float(y_train[idx]))
    return np.array(preds, dtype=float)


def _model_linear(y_train: np.ndarray, h: int, m: int = 1) -> np.ndarray:
    """Linear Trend: hoi quy tuyen tinh OLS y = a + b * t."""
    n = len(y_train)
    if n < 2:
        return _model_naive(y_train, h, m)
    t = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(t, y_train, 1)
    future_t = np.arange(n, n + h, dtype=float)
    preds = intercept + slope * future_t
    return preds


def _model_holt(y_train: np.ndarray, h: int, m: int = 1, alpha: float = 0.3, beta: float = 0.1) -> np.ndarray:
    """Holt's Linear Exponential Smoothing (xu huong cong)."""
    n = len(y_train)
    if n < 3:
        return _model_linear(y_train, h, m)

    level = y_train[0]
    trend = (y_train[1] - y_train[0])

    for i in range(1, n):
        val = y_train[i]
        last_level = level
        level = alpha * val + (1.0 - alpha) * (last_level + trend)
        trend = beta * (level - last_level) + (1.0 - beta) * trend

    future_steps = np.arange(1, h + 1, dtype=float)
    preds = level + future_steps * trend
    return preds


def _model_seasonal_decomp(y_train: np.ndarray, h: int, m: int = 12) -> np.ndarray:
    """Seasonal Decomposition: Chi so mua nhan * xu huong tuyen tinh tren chuoi bo mua."""
    n = len(y_train)
    if n < 2 * m:
        return _model_holt(y_train, h, m)

    # Tinh chi so mua vu trung binh cho tung thang/ky trong chu ky
    n_full_cycles = n // m
    usable_y = y_train[: n_full_cycles * m]
    cycle_reshaped = usable_y.reshape(n_full_cycles, m)
    cycle_means = cycle_reshaped.mean(axis=1, keepdims=True)
    cycle_means = np.where(cycle_means <= 1e-6, 1.0, cycle_means)

    seasonal_indices = (cycle_reshaped / cycle_means).mean(axis=0)
    # Chuan hoa de trung binh chi so mua = 1.0
    seasonal_indices = seasonal_indices / seasonal_indices.mean()

    # Bo mua vu tren toan bo y_train
    rep_indices = np.tile(seasonal_indices, int(np.ceil(n / m)))[:n]
    deseas_y = y_train / np.where(rep_indices <= 1e-4, 1.0, rep_indices)

    # Fit xu huong tuyen tinh tren chuoi da bo mua
    t = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(t, deseas_y, 1)

    future_t = np.arange(n, n + h, dtype=float)
    trend_preds = intercept + slope * future_t

    # Nhan lai chi so mua tuong ung voi cac buoc tuong lai
    future_season_idx = [(n + step) % m for step in range(h)]
    future_seasonal = seasonal_indices[future_season_idx]

    preds = trend_preds * future_seasonal
    return preds


MODEL_REGISTRY: dict[str, tuple[Callable, str, bool]] = {
    "seasonal_decomp": (_model_seasonal_decomp, "Mùa vụ × Xu hướng", True),
    "seasonal_naive": (_model_seasonal_naive, "Seasonal-Naive (Cơ sở)", True),
    "holt": (_model_holt, "Xu hướng Holt", False),
    "linear": (_model_linear, "Tuyến tính OLS", False),
    "naive": (_model_naive, "Naive (Giá trị cuối)", False),
}


# ---------------------------------------------------------------------------
# Rolling-Origin Backtest
# ---------------------------------------------------------------------------

def run_backtest(
    y: np.ndarray,
    model_fn: Callable,
    h: int,
    cycle: int,
    min_train: int = 10,
) -> tuple[float, list[list[float]]]:
    """Rolling-origin backtest danh gia do chinh xac va sai so theo tung buoc."""
    n = len(y)
    if n < min_train + h:
        return 999.0, [[0.0] * h]

    errors_by_step: list[list[float]] = [[] for _ in range(h)]
    mape_list = []

    # Cat moc goc tu min_train den n-h
    for origin in range(min_train, n - h + 1):
        y_train = y[:origin]
        y_test = y[origin : origin + h]

        try:
            preds = model_fn(y_train, h, cycle)
        except Exception:
            continue

        abs_errs = np.abs(y_test - preds)
        for step in range(h):
            errors_by_step[step].append(float(abs_errs[step]))

        nonzero_mask = np.abs(y_test) > 1e-4
        if np.any(nonzero_mask):
            iter_mape = float(np.mean(abs_errs[nonzero_mask] / np.abs(y_test[nonzero_mask])) * 100.0)
            mape_list.append(iter_mape)

    avg_mape = float(np.mean(mape_list)) if mape_list else 999.0
    return avg_mape, errors_by_step


# ---------------------------------------------------------------------------
# Diem vao chinh: run_forecast
# ---------------------------------------------------------------------------

def run_forecast(
    df: pd.DataFrame,
    profile: DataProfile,
    goal: AnalysisGoal,
    h: int = 3,
    llm: Optional[LLMClient] = None,
) -> tuple[Section, list[Fact]]:
    """Chay du bao thuan Python tat dinh va sinh Section + Facts."""
    facts: list[Fact] = []
    charts: list[ChartSpec] = []
    warnings: list[str] = []

    primary_task = goal.tasks[0] if goal.tasks else None
    metric = primary_task.metric if primary_task else profile.numeric_columns[0]
    time_col = profile.time_column or ""
    group_col = primary_task.group_by if primary_task and primary_task.group_by else (profile.group_columns[0] if profile.group_columns else None)

    metric_disp, metric_unit = resolve_column_display(metric)
    unit_str = f" {metric_unit}" if metric_unit else ""

    # 1. Kiem tra Guard
    _, cycle_len = infer_frequency(df, time_col)
    series_df, prep_warns = prepare_regular_series(df, time_col, metric, group_col=None)
    warnings.extend(prep_warns)

    # Tối ưu chuỗi thời gian: nếu chuỗi dạng ngày nhưng kéo dài nhiều tháng (> 90 ngày và > 45 điểm),
    # tự động gom nhóm theo Tháng (Monthly Resampling) để dự báo mang ý nghĩa chu kỳ tháng/quý
    is_monthly = False
    if len(series_df) > 45 and pd.api.types.is_datetime64_any_dtype(series_df.index):
        span_days = (series_df.index.max() - series_df.index.min()).days
        if span_days > 90:
            monthly_agg = series_df.resample("MS").sum()
            if len(monthly_agg) >= 15:
                series_df = monthly_agg
                cycle_len = 12
                is_monthly = True

    n_points = len(series_df)
    if n_points < 15:
        reason = f"Dữ liệu có {n_points} kỳ, cần ít nhất 15 kỳ để chia mẫu huấn luyện và kiểm định sai số dự báo."
        warnings.append(reason)
        return Section(level="forecast", charts=[], warnings=warnings), []

    y_total = series_df[metric].to_numpy(dtype=float)
    x_total_dates = [pd.Timestamp(t).strftime("%Y-%m") for t in series_df.index]

    # 2. Chon mo hinh tot nhat qua Backtest
    min_train = max(8, n_points - 10)
    has_seasonality_data = (n_points >= 2 * cycle_len) and (cycle_len > 1)

    best_model_name = "linear"
    best_model_display = "Tuyến tính"
    best_mape = 999.0
    best_errors_by_step: list[list[float]] = []

    baseline_mape = 999.0

    for name, (fn, disp_name, req_season) in MODEL_REGISTRY.items():
        if req_season and not has_seasonality_data:
            continue
        mape, err_steps = run_backtest(y_total, fn, h, cycle_len, min_train=min_train)
        if name in ("seasonal_naive", "naive"):
            baseline_mape = min(baseline_mape, mape)

        if mape < best_mape:
            best_mape = mape
            best_model_name = name
            best_model_display = disp_name
            best_errors_by_step = err_steps

    # Du bao tren toan bo chuoi
    best_fn = MODEL_REGISTRY[best_model_name][0]
    forecast_vals = best_fn(y_total, h, cycle_len)

    # 3. Dai bat dinh 80% conformal tu sai so backtest
    q80_bands = []
    for step in range(h):
        step_errs = best_errors_by_step[step] if step < len(best_errors_by_step) else []
        if len(step_errs) >= 4:
            q80 = float(np.quantile(step_errs, 0.80))
        else:
            q80 = float(forecast_vals[step] * 0.10)
        q80_bands.append(q80)

    # Xac dinh do tin cay
    n_trials = len(best_errors_by_step[0]) if best_errors_by_step else 0
    beats_baseline = (best_mape <= baseline_mape) or (baseline_mape >= 999.0)

    if best_mape < 5.0 and n_trials >= 6 and beats_baseline:
        confidence_level = "cao"
    elif best_mape < 12.0 and beats_baseline:
        confidence_level = "trung bình"
    else:
        confidence_level = "thấp"
        if not beats_baseline:
            warnings.append("Mô hình không vượt được đường cơ sở naive; độ tin cậy được hạ xuống mức thấp.")

    # Sinh nhan thoi gian tuong lai
    last_dt = pd.Timestamp(series_df.index[-1])
    future_dates = []
    for step in range(1, h + 1):
        if cycle_len == 12 or is_monthly:
            next_dt = last_dt + pd.DateOffset(months=step)
            future_dates.append(next_dt.strftime("%Y-%m"))
        elif cycle_len == 7:
            next_dt = last_dt + pd.DateOffset(days=step)
            future_dates.append(next_dt.strftime("%Y-%m-%d"))
        else:
            future_dates.append(f"Kỳ +{step}")

    forecast_start_date = future_dates[0]

    # 4. Tao ChartSpec voi ComposedChart data (Lich su + Du bao + Dai bat dinh)
    x_all = x_total_dates + future_dates
    y_hist_with_nulls: list[Optional[float]] = [float(v) for v in y_total] + [None] * h

    # Du bao noi tiep tu diem cuoi cung cua lich su
    y_fc_with_nulls: list[Optional[float]] = [None] * (len(y_total) - 1) + [float(y_total[-1])] + [round(float(v), 1) for v in forecast_vals]

    lower_with_nulls: list[Optional[float]] = [None] * (len(y_total) - 1) + [float(y_total[-1])]
    upper_with_nulls: list[Optional[float]] = [None] * (len(y_total) - 1) + [float(y_total[-1])]

    for step in range(h):
        fc_v = float(forecast_vals[step])
        q80_v = q80_bands[step]
        low_v = max(0.0, fc_v - q80_v)
        up_v = fc_v + q80_v
        lower_with_nulls.append(round(low_v, 1))
        upper_with_nulls.append(round(up_v, 1))

    period_unit_name = "tháng" if is_monthly else ("ngày" if cycle_len == 7 else "kỳ")
    caption = (
        f"Mô hình: {best_model_display} (MAPE backtest: {best_mape:.1f}%, độ tin cậy: {confidence_level.title()}). "
        f"Dải bất định 80% phản ánh sai số kiểm định thực tế."
    )

    charts.append(
        ChartSpec(
            chart_type="line",
            title=f"Dự báo xu hướng {metric_disp} ({h} {period_unit_name} tới)",
            x=x_all,
            series={
                "Thực tế": y_hist_with_nulls,
                "Dự báo": y_fc_with_nulls,
            },
            band={
                "lower": lower_with_nulls,
                "upper": upper_with_nulls,
            },
            forecast_from=forecast_start_date,
            caption=caption,
            display_name=metric_disp,
            unit=metric_unit,
            role="primary",
        )
    )

    # 5. Sinh Facts du bao
    facts.append(
        Fact(
            id="F_FC_MODEL",
            kind="forecast",
            metric=metric_disp,
            value=round(best_mape, 1),
            unit="%",
            text=(
                f"Mô hình được chọn: {best_model_display} với sai số backtest MAPE = {best_mape:.1f}% "
                f"({n_trials} lần kiểm thử cuốn chiếu), độ tin cậy {confidence_level}."
            ),
        )
    )

    for step in range(h):
        fc_v = round(float(forecast_vals[step]), 1)
        low_v = round(float(lower_with_nulls[-h + step]), 1)
        up_v = round(float(upper_with_nulls[-h + step]), 1)
        dt_label = future_dates[step]

        fact_text = (
            f"(ƯỚC TÍNH) {metric_disp} kỳ {dt_label} dự kiến đạt {fc_v:,}{unit_str} "
            f"(khoảng tin cậy 80%: {low_v:,} – {up_v:,})."
        ).replace(",", ".")

        facts.append(
            Fact(
                id=f"F_FC_{step+1}",
                kind="forecast",
                metric=metric_disp,
                value=fc_v,
                unit=metric_unit,
                period=dt_label,
                estimate=True,
                text=fact_text,
            )
        )

    # 6. Dien giai LLM tren FactSheet du bao
    narrative_text = _generate_forecast_narrative(facts, confidence_level, llm)
    narrative = InsightResult(
        insight_text=narrative_text,
        confidence_score=0.90 if confidence_level == "cao" else (0.75 if confidence_level == "trung bình" else 0.55),
    )

    return Section(level="forecast", charts=charts, narrative=narrative, warnings=warnings), facts


def _generate_forecast_narrative(facts: list[Fact], confidence: str, llm: Optional[LLMClient]) -> str:
    """Sinh nhan xet du bao bang LLM chi tu FactSheet, fallback tat dinh neu can."""
    fallback_text = "\n\n".join(f"• {f.text}" for f in facts)
    if not llm:
        return fallback_text

    prompt = (
        "Bạn là chuyên gia phân tích dự báo. Dưới đây là CÁC SỰ THẬT DỰ BÁO ĐÃ TÍNH TOÁN:\n"
        + "\n".join(f"[{f.id}] {f.text}" for f in facts)
        + f"\n\nĐộ tin cậy mô hình: {confidence.upper()}.\n"
        "Yêu cầu:\n"
        "- Viết nhận xét dự báo ngắn gọn (3–4 câu).\n"
        "- Mọi số liệu dự báo BẮT BUỘC kèm chữ 'ước tính' hoặc 'dự kiến'.\n"
        "- Nêu rõ mức tin cậy và sai số MAPE.\n"
        "- KHÔNG dùng từ chắc chắn tuyệt đối ('chắc chắn sẽ', 'nhất định'); dùng 'có xu hướng', 'dự kiến dao động trong khoảng'.\n"
        "- BẮT BUỘC chỉ nhắc các con số có trong danh sách trên.\n"
        "Nhận xét:"
    )

    try:
        text = llm.complete_text(prompt).strip()
        return text if text else fallback_text
    except Exception as exc:
        logger.warning("Loi khi sinh dien giai du bao bang LLM: %s", exc)
        return fallback_text
