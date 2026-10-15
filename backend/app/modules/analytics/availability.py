"""Module analytics/availability.py.

Kiem tra tinh kha dung cua cac che do/cap phan tich (Descriptive, Diagnostic, Forecast, Prescriptive)
va hop nhat y dinh nguoi dung (ModePicker pill) voi cap phan tich suy ra tu cau hoi (O2).
Hoan toan tat dinh, khong goi LLM.
"""
from __future__ import annotations

import logging
from typing import Optional
import pandas as pd

from ...schemas import AnalysisLevel, AnalysisMode, DataProfile, ModeAvailability, Notice

logger = logging.getLogger(__name__)

LEVEL_NAMES_VN = {
    "diagnostic": "nguyên nhân / yếu tố đóng góp",
    "forecast": "dự đoán xu hướng",
    "prescriptive": "gợi ý chiến lược",
}


def compute_availability(
    df: pd.DataFrame, profile: DataProfile
) -> tuple[dict[str, ModeAvailability], Optional[str], Optional[int]]:
    """Xac dinh kha nang su dung cua tung che do phan tich dua tren du lieu.

    Tra ve:
        availability_map: dict[level_or_mode, ModeAvailability]
        frequency: "daily" | "weekly" | "monthly" | "quarterly" | None
        n_periods: so ky thoi gian thuc te phat hien duoc
    """
    availability: dict[str, ModeAvailability] = {}

    has_numeric = len(profile.numeric_columns) > 0
    if not has_numeric:
        no_num = ModeAvailability(available=False, reason="File chưa có cột số liệu.")
        for k in ["auto", "descriptive", "diagnostic", "forecast", "prescriptive"]:
            availability[k] = no_num
        return availability, None, None

    availability["descriptive"] = ModeAvailability(available=True, reason=None)
    availability["auto"] = ModeAvailability(available=True, reason=None)

    # 1. Kiem tra thoi gian va tan suat
    time_col = profile.time_column
    n_periods = 0
    freq_label: Optional[str] = None
    missing_ratio = 0.0

    if time_col and time_col in df.columns:
        try:
            # Chuyen thanh datetime de suy doan
            dt_series = pd.to_datetime(df[time_col], errors="coerce").dropna().sort_values()
            unique_dates = dt_series.drop_duplicates()
            n_periods = len(unique_dates)

            if n_periods >= 3:
                # Do do lech ngay trung vi
                diff_days = unique_dates.diff().dt.total_seconds().dropna() / 86400.0
                med_days = float(diff_days.median()) if not diff_days.empty else 0.0

                if 0.5 <= med_days <= 2.0:
                    freq_label = "daily"
                elif 5.0 <= med_days <= 10.0:
                    freq_label = "weekly"
                elif 25.0 <= med_days <= 35.0:
                    freq_label = "monthly"
                elif 80.0 <= med_days <= 100.0:
                    freq_label = "quarterly"
                else:
                    freq_label = "irregular"

                # Kiem tra do hut ky neu la tan suat deu
                if freq_label in ("daily", "weekly", "monthly", "quarterly"):
                    first_d, last_d = unique_dates.iloc[0], unique_dates.iloc[-1]
                    alias = {"daily": "D", "weekly": "W", "monthly": "MS", "quarterly": "QS"}[freq_label]
                    expected_range = pd.date_range(first_d, last_d, freq=alias)
                    expected_len = len(expected_range)
                    if expected_len > 0 and expected_len >= n_periods:
                        missing_ratio = (expected_len - n_periods) / expected_len
        except Exception as exc:
            logger.warning("Loi khi phan tich tan suat chuoi thoi gian: %s", exc)

    # 2. Diagnostic: can time_col >= 4 ky VA >= 1 group_col
    has_groups = len(profile.group_columns) > 0
    if time_col and n_periods >= 4 and has_groups:
        availability["diagnostic"] = ModeAvailability(available=True, reason=None)
    else:
        if not time_col or n_periods < 4:
            diag_reason = f"Cần cột thời gian (≥ 4 kỳ) và ít nhất một cột phân nhóm (hiện có {n_periods} kỳ)."
        else:
            diag_reason = "Cần ít nhất một cột phân nhóm như chi nhánh/sản phẩm để phân tích đóng góp."
        availability["diagnostic"] = ModeAvailability(available=False, reason=diag_reason)

    # 3. Forecast: can time_col, >= 15 ky, missing <= 20%, suy ra duoc tan suat
    if not time_col or n_periods < 15:
        fc_reason = f"Cần ít nhất 15 kỳ dữ liệu (hiện có {n_periods})."
        availability["forecast"] = ModeAvailability(available=False, reason=fc_reason)
    elif freq_label == "irregular" or freq_label is None:
        availability["forecast"] = ModeAvailability(
            available=False, reason="Cần chuỗi thời gian có tần suất đều đặn (ngày/tuần/tháng)."
        )
    elif missing_ratio > 0.20:
        availability["forecast"] = ModeAvailability(
            available=False, reason=f"Dữ liệu bị gián đoạn {missing_ratio:.0%} (> 20% số kỳ)."
        )
    else:
        availability["forecast"] = ModeAvailability(available=True, reason=None)

    # 4. Prescriptive: Diagnostic HOAC Forecast kha dung
    diag_ok = availability["diagnostic"].available
    fc_ok = availability["forecast"].available
    if diag_ok or fc_ok:
        availability["prescriptive"] = ModeAvailability(available=True, reason=None)
    else:
        availability["prescriptive"] = ModeAvailability(
            available=False,
            reason="Chưa đủ dữ liệu để phân tích yếu tố đóng góp hay dự báo.",
        )

    return availability, freq_label, n_periods


def resolve_levels(
    mode: AnalysisMode,
    goal_levels: list[AnalysisLevel],
    availability: dict[str, ModeAvailability],
) -> tuple[list[AnalysisLevel], list[Notice]]:
    """Hop nhat che do duoc chon (mode), muc tieu tu cau hoi (goal.levels) va do kha dung.

    Nguyen tac:
    - Hop (union), khong bao gio bo phan cau hoi dang hoi.
    - Neu mode la 'prescriptive', tu dong keo theo diagnostic va forecast lam can cu (neu co).
    - Cap khong kha dung -> bo qua kem Notice neu ro ly do.
    """
    mode_to_levels: dict[str, set[AnalysisLevel]] = {
        "auto": set(goal_levels or ["descriptive"]),
        "descriptive": {"descriptive"},
        "diagnostic": {"descriptive", "diagnostic"},
        "forecast": {"descriptive", "forecast"},
        "prescriptive": {"descriptive", "diagnostic", "forecast", "prescriptive"},
    }

    # Tap cac cap muon chay: luon gom descriptive
    wanted = {"descriptive"} | mode_to_levels.get(mode, set(goal_levels)) | set(goal_levels)

    notices: list[Notice] = []

    # Thong bao neu chon 'descriptive' ma cau hoi lai hoi sau hon
    if mode == "descriptive":
        added_from_goal = [lvl for lvl in goal_levels if lvl != "descriptive" and lvl in wanted]
        for lvl in added_from_goal:
            lvl_name = LEVEL_NAMES_VN.get(lvl, lvl)
            notices.append(
                Notice(
                    kind="added",
                    level=lvl,
                    message=f"Câu hỏi của bạn cũng hỏi về {lvl_name} — đã tự động thêm phần này.",
                )
            )

    # Loc theo kha dung
    final_levels: list[AnalysisLevel] = []
    order: list[AnalysisLevel] = ["descriptive", "diagnostic", "forecast", "prescriptive"]

    for lvl in order:
        if lvl not in wanted:
            continue
        if lvl == "descriptive":
            final_levels.append(lvl)
            continue

        avail_info = availability.get(lvl)
        is_avail = avail_info.available if avail_info else False

        if is_avail:
            final_levels.append(lvl)
        else:
            reason = avail_info.reason if avail_info and avail_info.reason else "Dữ liệu chưa đủ điều kiện."
            notices.append(
                Notice(
                    kind="skipped",
                    level=lvl,
                    message=f"Bỏ qua phần {LEVEL_NAMES_VN.get(lvl, lvl)}: {reason}",
                )
            )

    # Rieng prescriptive: can it nhat diagnostic hoac forecast da duoc chay lam can cu
    if "prescriptive" in final_levels:
        has_basis = ("diagnostic" in final_levels) or ("forecast" in final_levels)
        if not has_basis:
            final_levels.remove("prescriptive")
            notices.append(
                Notice(
                    kind="skipped",
                    level="prescriptive",
                    message="Bỏ qua phần gợi ý chiến lược do không có đủ căn cứ chẩn đoán hoặc dự báo.",
                )
            )

    return final_levels, notices
