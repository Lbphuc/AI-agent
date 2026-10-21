"""Module analytics/series.py.

Xu ly chuoi thoi gian tat dinh:
1. Suy dien tan suat va chu ky mua vu (daily, weekly, monthly, quarterly).
2. Chinh sach tong hop (sum vs mean) + warnings neu suy doan.
3. Reindex chuoi day du va kiem tra ty le thieu.
4. window_compare(): So sanh cua so N ky gan nhat vs N ky lien truoc (khong so 2 diem don le).
"""
from __future__ import annotations

import logging
import re
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def infer_frequency(df: pd.DataFrame, time_col: str) -> tuple[str, int]:
    """Suy dien tan suat va chu ky mua vu tu cot thoi gian.

    Tra ve:
        (freq_alias, cycle_length)
        vi du: ("monthly", 12), ("daily", 7), ("weekly", 52), ("quarterly", 4)
    """
    if time_col not in df.columns:
        return "unknown", 1

    dt_series = pd.to_datetime(df[time_col], errors="coerce").dropna().drop_duplicates().sort_values()
    if len(dt_series) < 3:
        return "unknown", 1

    diff_days = dt_series.diff().dt.total_seconds().dropna() / 86400.0
    med = float(diff_days.median())

    if 0.5 <= med <= 2.0:
        return "daily", 7
    if 5.0 <= med <= 10.0:
        return "weekly", 52
    if 25.0 <= med <= 35.0:
        return "monthly", 12
    if 80.0 <= med <= 100.0:
        return "quarterly", 4

    return "irregular", 1


def aggregation_policy(col_name: str) -> tuple[str, list[str]]:
    """Xac dinh ham tong hop (sum vs mean) dua vao ten cot va ban chat nghiep vu."""
    clean = col_name.lower()
    is_mean = bool(re.search(r"(ty_le|rate|pct|diem|rating|gia|price|percent|margin|ratio|tuoi|age|danh_gia)", clean))
    if is_mean:
        return "mean", ["Chỉ số trung bình/tỷ lệ được tổng hợp theo chính sách tính trung bình (mean)."]
    return "sum", ["Chỉ số được tổng hợp theo chính sách cộng dồn (sum)."]


def prepare_regular_series(
    df: pd.DataFrame,
    time_col: str,
    metric_col: str,
    group_col: Optional[str] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Gop du lieu theo thoi gian day du va reindex.

    Tra ve DataFrame da sort theo thoi gian va warnings.
    """
    warnings: list[str] = []
    agg_func, agg_warns = aggregation_policy(metric_col)
    warnings.extend(agg_warns)

    # Chuan hoa cot thoi gian de sort
    df_clean = df.copy()
    df_clean["_dt"] = pd.to_datetime(df_clean[time_col], errors="coerce")
    df_clean = df_clean.dropna(subset=["_dt", metric_col])

    if group_col:
        grouped = (
            df_clean.groupby(["_dt", group_col])[metric_col]
            .agg(agg_func)
            .unstack()
            .sort_index()
        )
    else:
        grouped = (
            df_clean.groupby("_dt")[metric_col]
            .agg(agg_func)
            .to_frame(name=metric_col)
            .sort_index()
        )

    # Reindex neu la tan suat monthly/daily/weekly deu
    freq_alias, _ = infer_frequency(df, time_col)
    date_alias = {"monthly": "MS", "daily": "D", "weekly": "W", "quarterly": "QS"}.get(freq_alias)
    if date_alias and len(grouped) >= 3:
        full_idx = pd.date_range(grouped.index.min(), grouped.index.max(), freq=date_alias)
        n_missing = len(full_idx) - len(grouped)
        if n_missing > 0:
            missing_ratio = n_missing / len(full_idx)
            if missing_ratio > 0.20:
                warnings.append(f"Chuỗi thời gian thiếu {n_missing}/{len(full_idx)} kỳ ({missing_ratio:.0%}).")
            grouped = grouped.reindex(full_idx)

    return grouped, warnings


def window_compare(
    df: pd.DataFrame,
    group_col: Optional[str],
    metric_col: str,
    time_col: str,
    n: int = 12,
) -> pd.DataFrame:
    """So sanh theo cua so: N ky gan nhat so voi N ky lien truoc.

    Tra ve DataFrame cac cot:
        [entity, prev_val, curr_val, delta, delta_pct, share_of_change, status]
    """
    df_clean = df.copy()
    # Chuan hoa thoi gian
    dt_vals = pd.to_datetime(df_clean[time_col], errors="coerce")
    df_clean["_time_key"] = dt_vals.dt.strftime("%Y-%m") if not dt_vals.isna().all() else df_clean[time_col].astype(str)

    unique_times = sorted(df_clean["_time_key"].dropna().unique().tolist())
    total_periods = len(unique_times)

    if total_periods < 2:
        return pd.DataFrame()

    # Neu tong so ky < 2 * n, thu hep cua so xuong n_effective
    n_effective = min(n, total_periods // 2)
    if n_effective < 1:
        n_effective = 1

    curr_periods = set(unique_times[-n_effective:])
    prev_periods = set(unique_times[-2 * n_effective : -n_effective])

    agg_func, _ = aggregation_policy(metric_col)

    results = []

    if group_col and group_col in df_clean.columns:
        entities = df_clean[group_col].dropna().unique().tolist()
    else:
        entities = ["__total__"]

    for ent in entities:
        if ent == "__total__":
            sub_curr = df_clean[df_clean["_time_key"].isin(curr_periods)]
            sub_prev = df_clean[df_clean["_time_key"].isin(prev_periods)]
        else:
            sub_curr = df_clean[(df_clean[group_col] == ent) & (df_clean["_time_key"].isin(curr_periods))]
            sub_prev = df_clean[(df_clean[group_col] == ent) & (df_clean["_time_key"].isin(prev_periods))]

        has_curr = not sub_curr.empty
        has_prev = not sub_prev.empty

        c_val = float(sub_curr[metric_col].agg(agg_func)) if has_curr else 0.0
        p_val = float(sub_prev[metric_col].agg(agg_func)) if has_prev else 0.0
        delta = c_val - p_val

        status = "existing"
        if not has_prev and has_curr:
            status = "new"  # Nhóm mới xuất hiện
            delta_pct = 100.0 if c_val > 0 else 0.0
        elif has_prev and not has_curr:
            status = "discontinued"  # Nhóm ngưng xuất hiện trong kỳ
            delta_pct = -100.0
        elif abs(p_val) > 1e-6:
            delta_pct = delta / p_val * 100.0
        else:
            delta_pct = 0.0

        results.append({
            "entity": ent,
            "prev_val": round(p_val, 1),
            "curr_val": round(c_val, 1),
            "delta": round(delta, 1),
            "delta_pct": round(delta_pct, 1),
            "status": status,
        })

    res_df = pd.DataFrame(results)

    # Tinh share_of_change neu co nhieu nhom
    if len(res_df) > 1 and group_col:
        tot_delta = res_df["delta"].sum()
        if abs(tot_delta) > 1.0:  # Thay doi tong khong qua gan 0
            res_df["share_of_change"] = np.round((res_df["delta"] / tot_delta) * 100.0, 1)
        else:
            # Cac nhom bu tru bien dong cho nhau
            tot_abs = res_df["delta"].abs().sum()
            if tot_abs > 1e-4:
                res_df["share_of_change"] = np.round((res_df["delta"].abs() / tot_abs) * 100.0, 1)
            else:
                res_df["share_of_change"] = 0.0
    else:
        res_df["share_of_change"] = 100.0

    return res_df.sort_values(by="delta", ascending=True)
