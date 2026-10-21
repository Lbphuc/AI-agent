"""Orchestrator — ghép O3a (Code Generator) + O3b (Sandbox Executor).

analysis_runner.py là điểm nối giữa các module:
1. Lọc DataFrame theo time_start/time_end và filters thực thể (tất định, KHÔNG qua LLM).
2. Vòng lặp sinh mã (O3a) → thực thi (O3b) → retry nếu lỗi, tối đa max_attempts.
3. Chuẩn hóa kết quả chuỗi thời gian (nếu dữ liệu theo ngày kéo dài > 60 ngày và > 35 mốc
   thì tự động sắp xếp và gộp theo tháng) ngay tại ExecutionResult để O4 (Chart),
   Perspective Planner và O5 (Insight) đọc chung một nguồn số liệu đồng nhất.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

from ..llm_client import LLMClient
from ..schemas import AnalysisGoal, AnalysisTask, DataProfile, ExecutionResult
from . import code_generator, sandbox_executor
from .analytics.series import aggregation_policy
from .code_generator import CodeGenerationError
from .sandbox_executor import UnsafeCodeError

logger = logging.getLogger(__name__)


def filter_by_time_range(
    df: pd.DataFrame,
    profile: DataProfile,
    time_start: str | None,
    time_end: str | None,
) -> pd.DataFrame:
    """Lọc df theo khoảng thời gian — TUYỆT ĐỐI không giao cho LLM."""
    if profile.time_column is None or (time_start is None and time_end is None):
        return df

    time_col = profile.time_column
    if time_col not in df.columns:
        logger.warning("Cột thời gian '%s' không tồn tại trong df — bỏ qua lọc.", time_col)
        return df

    try:
        times = pd.to_datetime(df[time_col], errors="coerce")
        mask = pd.Series(True, index=df.index)
        if time_start:
            mask &= times >= pd.Timestamp(time_start)
        if time_end:
            end_ts = pd.Timestamp(time_end)
            # Nếu time_end có dạng YYYY-MM (không có ngày), mở rộng tới cuối tháng đó
            # để không làm rơi mất các ngày từ 02..31 trong tháng cuối với dữ liệu daily
            if re.match(r"^\d{4}[-/]\d{1,2}$", str(time_end).strip()):
                end_ts = end_ts + pd.offsets.MonthEnd(1)
            mask &= times <= end_ts
        filtered = df[mask].reset_index(drop=True)
        logger.info(
            "Lọc thời gian: %d → %d dòng (%s đến %s)",
            len(df), len(filtered), time_start, time_end,
        )
        return filtered if not filtered.empty else df
    except Exception as exc:
        logger.warning("Lỗi khi lọc thời gian: %s — dùng df gốc.", exc)
        return df


_filter_by_time_range = filter_by_time_range


def filter_by_entities(df: pd.DataFrame, filters: dict[str, str] | None) -> pd.DataFrame:
    """Lọc DataFrame theo các điều kiện thực thể cụ thể (ví dụ {'Chi_nhanh': 'TP.HCM'})."""
    if not filters:
        return df
    df_out = df
    for col, val in filters.items():
        if col in df_out.columns and val:
            sub = df_out[df_out[col].astype(str).str.strip().str.lower() == str(val).strip().lower()]
            if not sub.empty:
                df_out = sub
    return df_out.reset_index(drop=True)


def _normalize_trend_execution_result(
    task: AnalysisTask,
    exec_result: ExecutionResult,
) -> ExecutionResult:
    """Chuẩn hóa kết quả 'trend' trong ExecutionResult:
    - Sắp xếp đúng thứ tự thời gian (tránh thứ tự bảng chữ cái '10/1/2017' đứng trước '2/1/2017').
    - Nếu chuỗi kéo dài > 60 ngày và có > 35 mốc ngày lẻ, tự động gom nhóm theo Tháng ('YYYY-MM')
      để cả O4 (Chart), Perspective Planner (Biến động kỳ trước) và O5 (Nhận xét AI) đồng nhất 100%.
    """
    if task.type != "trend" or not exec_result.success:
        return exec_result

    trend_dict = exec_result.results.get("trend")
    if not isinstance(trend_dict, dict) or len(trend_dict) < 2:
        return exec_result

    try:
        keys = list(trend_dict.keys())
        vals = [float(v) if v is not None else 0.0 for v in trend_dict.values()]
        parsed_dates = pd.to_datetime(keys, errors="coerce")
        if parsed_dates.isna().any():
            return exec_result

        s = pd.Series(vals, index=parsed_dates).sort_index()
        time_span_days = (s.index.max() - s.index.min()).days
        agg_fn = getattr(task, "agg", None)
        if not agg_fn:
            agg_fn, _ = aggregation_policy(str(task.metric))

        if time_span_days > 60 and len(s) > 35:
            s_monthly = s.resample("MS").agg(agg_fn)
            normalized = {
                d.strftime("%Y-%m"): round(float(v), 2)
                for d, v in s_monthly.items()
                if pd.notna(v)
            }
            exec_result.results["trend"] = normalized
        else:
            # Nếu các khóa gốc đã ở dạng YYYY-MM thì giữ nguyên format ngắn gọn
            all_ym = all(re.match(r"^\d{4}-\d{2}$", str(k).strip()) for k in keys)
            if all_ym:
                normalized = {
                    d.strftime("%Y-%m"): round(float(v), 2)
                    for d, v in s.items()
                    if pd.notna(v)
                }
            else:
                normalized = {
                    (d.strftime("%Y-%m") if (d.day == 1 and time_span_days > 60) else d.strftime("%Y-%m-%d")): round(float(v), 2)
                    for d, v in s.items()
                    if pd.notna(v)
                }
            exec_result.results["trend"] = normalized
    except Exception as exc:
        logger.warning("Không thể chuẩn hóa chuỗi trend trong analysis_runner: %s", exc)

    return exec_result


def _normalize_growth_execution_result(
    task: AnalysisTask,
    profile: DataProfile,
    df_filtered: pd.DataFrame,
    exec_result: ExecutionResult,
) -> ExecutionResult:
    """Đảm bảo kết quả growth_rate được tính trên tổng theo kỳ (tháng) thay vì lấy 1 dòng đơn hàng lẻ."""
    if task.type != "growth_rate" or not exec_result.success:
        return exec_result
    if not profile.time_column or not task.group_by:
        return exec_result
    if profile.time_column not in df_filtered.columns or task.group_by not in df_filtered.columns:
        return exec_result

    code_str = exec_result.code or ""
    # Nếu code do LLM sinh ra gọi .first() / .last() trực tiếp trên groupby(group_by)
    # mà dữ liệu có nhiều dòng trong cùng 1 kỳ cho mỗi nhóm -> tính lại chuẩn xác theo kỳ tháng
    n_rows = len(df_filtered)
    n_groups = max(1, int(df_filtered[task.group_by].nunique()))
    n_times = max(1, int(df_filtered[profile.time_column].nunique()))

    needs_recalc = (
        (".first()" in code_str or ".last()" in code_str)
        and ("_p" not in code_str and "to_period" not in code_str and "unstack" not in code_str)
        and (n_rows > n_groups * n_times or not str(df_filtered[profile.time_column].iloc[0])[:4].isdigit())
    )
    if not needs_recalc:
        return exec_result

    try:
        agg_fn = getattr(task, "agg", None)
        if not agg_fn:
            agg_fn, _ = aggregation_policy(str(task.metric))
        dt = pd.to_datetime(df_filtered[profile.time_column], errors="coerce")
        if not dt.isna().all():
            span_days = (dt.max() - dt.min()).days
            period_key = dt.dt.to_period("M") if span_days > 45 else dt
        else:
            period_key = df_filtered[profile.time_column].astype(str)

        grouped = (
            df_filtered.assign(_period=period_key)
            .groupby(["_period", task.group_by])[task.metric]
            .agg(agg_fn)
            .unstack()
            .sort_index()
        )
        if len(grouped) >= 2:
            first_row = grouped.iloc[0]
            last_row = grouped.iloc[-1]
            valid = (first_row.notna()) & (last_row.notna()) & (first_row.abs() > 1e-6)
            if valid.any():
                growth = ((last_row[valid] - first_row[valid]) / first_row[valid] * 100.0).round(2)
                target = str(growth.idxmin() if task.find == "min" else growth.idxmax())
                exec_result.results["growth_rate"] = {str(k): float(v) for k, v in growth.to_dict().items()}
                exec_result.results["target"] = target
    except Exception as exc:
        logger.warning("Không thể chuẩn hóa lại growth_rate theo kỳ: %s", exc)

    return exec_result


def run_task(
    task: AnalysisTask,
    goal: AnalysisGoal,
    profile: DataProfile,
    df: pd.DataFrame,
    llm: LLMClient,
    max_attempts: int = 3,
) -> ExecutionResult:
    """Lọc dữ liệu theo thời gian & thực thể rồi sinh mã + thực thi, tối đa max_attempts lần."""
    df_filtered = _filter_by_time_range(df, profile, goal.time_start, goal.time_end)
    task_filters = getattr(task, "filters", None) or getattr(goal, "filters", None)
    if task_filters:
        # Không lọc trên chính cột group_by của task comparison/growth_rate để tránh chỉ còn 1 cột
        effective_filters = {
            k: v for k, v in task_filters.items()
            if task.type == "trend" or k != task.group_by
        }
        if effective_filters:
            df_filtered = filter_by_entities(df_filtered, effective_filters)

    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "run_task: task.type=%r, attempt=%d/%d",
            task.type, attempt, max_attempts,
        )

        try:
            code_result = code_generator.generate(
                task=task,
                profile=profile,
                llm=llm,
                previous_error=last_error,
                question=goal.question,
            )
        except CodeGenerationError as exc:
            last_error = f"Lỗi sinh mã (lần {attempt}): {exc}"
            logger.warning(last_error)
            continue

        try:
            exec_result = sandbox_executor.execute(code_result.code, df_filtered)
        except UnsafeCodeError as exc:
            last_error = f"Mã vi phạm sandbox (lần {attempt}): {exc}"
            logger.warning(last_error)
            continue

        if exec_result.success:
            exec_result.attempts = attempt
            exec_result.code = code_result.code
            exec_result = _normalize_trend_execution_result(task, exec_result)
            exec_result = _normalize_growth_execution_result(task, profile, df_filtered, exec_result)
            return exec_result

        last_error = exec_result.error
        logger.warning(
            "Thực thi thất bại (lần %d/%d): %s",
            attempt, max_attempts, last_error,
        )

    logger.error(
        "run_task thất bại sau %d lần cho task.type=%r. Lỗi cuối: %s",
        max_attempts, task.type, last_error,
    )
    return ExecutionResult(
        success=False,
        error=last_error or "Thất bại sau tất cả các lần thử.",
        attempts=max_attempts,
    )
