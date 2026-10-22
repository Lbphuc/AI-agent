"""Module analytics/diagnostic.py.

Cap 1 — Chan doan (Diagnostic Analytics).
Thuan Python tat dinh:
1. Dong gop theo nhom qua window_compare().
2. Drill-down tim nguoi dan dat thay doi (driver) va boc tach ben trong driver.
3. Tuong quan trong tung chuoi (khu hieu ung quy mo bang z-score theo nhom).
4. Sinh FactSheet (F1, F2...) lam nguon su that duy nhat cho LLM dien giai.
5. Sinh ChartSpec chan doan (dong gop, drill-down, tuong quan) da enrich options.
"""
from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd

from ...llm_client import LLMClient
from ...schemas import AnalysisGoal, ChartSpec, DataProfile, Fact, InsightResult, Section
from ..business_terms import resolve_column_display
from ..chart_generator import enrich_chart_spec
from .series import window_compare

logger = logging.getLogger(__name__)


def _fmt_num(val: float, decimals: int = 1, force_sign: bool = False) -> str:
    """Format so tieng Viet (dau cham ngan cach phan nghin, dau phay thap phan)."""
    sign = "+" if force_sign and val > 0 else ("−" if val < 0 else "")
    abs_v = abs(val)
    if decimals == 0 or abs_v == int(abs_v):
        int_str = f"{int(round(abs_v)):,}".replace(",", ".")
        return f"{sign}{int_str}"
    parts = f"{abs_v:.{decimals}f}".split(".")
    int_str = f"{int(parts[0]):,}".replace(",", ".")
    return f"{sign}{int_str},{parts[1]}"


def _pick_diagnostic_group_col(goal: AnalysisGoal, profile: DataProfile, df: pd.DataFrame) -> Optional[str]:
    """Chon cot phan nhom phu hop nhat cho chan doan (uu tien Category/Chi nhanh/Region hon Ship Mode)."""
    primary_task = goal.tasks[0] if goal.tasks else None
    if primary_task and primary_task.group_by and primary_task.group_by in df.columns:
        return primary_task.group_by
    if not profile.group_columns:
        return None
    high_kw = ("category", "danh_muc", "chi_nhanh", "branch", "region", "khu_vuc", "segment", "phan_khuc", "san_pham")
    for c in profile.group_columns:
        if any(k in c.lower() for k in high_kw) and "sub" not in c.lower():
            return c
    return profile.group_columns[0]


def _drill_col_priority(col_name: str, parent_group_col: Optional[str], n_uniq: int) -> tuple[int, int]:
    """Xếp hạng độ ưu tiên cho cột drill-down thứ 2 bên trong nhóm dẫn dắt (driver):
    - Nếu nhóm cha là Category / Danh_muc -> ưu tiên số 1 cho Sub-Category / San_pham (bóc tách mặt hàng con).
    - Tiếp theo là các chiều kinh doanh cốt lõi: Danh_muc, Category, Region, Khu_vuc, Chi_nhanh, Segment, Phan_khuc.
    - Để các chiều vận chuyển / địa lý hành chính (Ship Mode, Country, State) ở cuối cùng.
    """
    c_low = col_name.lower()
    p_low = (parent_group_col or "").lower()

    if ("category" in p_low or "danh_muc" in p_low) and ("sub" in c_low or "san_pham" in c_low or "product" in c_low):
        tier = 4
    elif any(k in c_low for k in ("danh_muc", "category", "sub-category", "san_pham", "product", "chi_nhanh", "branch", "region", "khu_vuc", "segment", "phan_khuc")):
        tier = 3
    elif any(k in c_low for k in ("ship", "country", "postal", "state", "city")):
        tier = 1
    else:
        tier = 2

    # Ưu tiên số lượng nhóm con từ 3 đến 10 để biểu đồ drill-down trực quan, không quá thưa hoặc quá dày
    ideal_count_score = 15 - abs(n_uniq - 6)
    return (tier, ideal_count_score)


def run_diagnostic(
    df: pd.DataFrame,
    profile: DataProfile,
    goal: AnalysisGoal,
    llm: Optional[LLMClient] = None,
) -> tuple[Section, list[Fact]]:
    """Thuc hien chan doan tat dinh va tao FactSheet."""
    facts: list[Fact] = []
    charts: list[ChartSpec] = []
    warnings: list[str] = []

    primary_task = goal.tasks[0] if goal.tasks else None
    metric = primary_task.metric if primary_task else profile.numeric_columns[0]
    time_col = profile.time_column or ""
    group_col = _pick_diagnostic_group_col(goal, profile, df)

    metric_disp, metric_unit = resolve_column_display(metric)
    unit_str = f" {metric_unit}" if metric_unit else ""

    n_window = 12
    if goal.time_scope == "last_3_months":
        n_window = 3
    elif goal.time_scope == "last_6_months":
        n_window = 6

    comp_df = window_compare(df, group_col, metric, time_col, n=n_window)
    if comp_df.empty:
        warnings.append("Không đủ dữ liệu thời gian để so sánh cửa sổ kỳ.")
        return Section(level="diagnostic", charts=[], warnings=warnings), []

    tot_delta = float(comp_df["delta"].sum())
    tot_prev = float(comp_df["prev_val"].sum())
    tot_curr = float(comp_df["curr_val"].sum())
    tot_abs_sum = float(comp_df["delta"].abs().sum())
    tot_pct = (tot_delta / tot_prev * 100.0) if abs(tot_prev) > 1e-6 else 0.0
    is_offsetting = abs(tot_delta) <= 1.0 and tot_abs_sum > 2.0

    action_word = "tăng" if tot_delta >= 0 else "giảm"
    if is_offsetting:
        f1_text = (
            f"Tổng {metric_disp} {n_window} kỳ gần nhất biến động không đáng kể ({_fmt_num(tot_delta, force_sign=True)}{unit_str}) "
            f"do các nhóm bù trừ lẫn nhau ({_fmt_num(tot_curr)} vs {_fmt_num(tot_prev)}), "
            f"nhưng có sự chuyển dịch nội bộ đáng chú ý."
        )
    else:
        f1_text = (
            f"Tổng {metric_disp} {n_window} kỳ gần nhất {action_word} {_fmt_num(abs(tot_delta))}{unit_str} "
            f"({_fmt_num(tot_pct, 1, force_sign=True)}%) so với {n_window} kỳ trước "
            f"({_fmt_num(tot_curr)} vs {_fmt_num(tot_prev)})."
        )
    facts.append(
        Fact(
            id="F1",
            kind="total",
            metric=metric_disp,
            value=tot_delta,
            unit=metric_unit,
            period=f"{n_window} kỳ gần nhất",
            text=f1_text,
        )
    )

    q_lower = goal.question.lower()
    obj = goal.objective or ""
    if obj == "top_decliners" or any(w in q_lower for w in ["giảm nhiều nhất", "làm giảm", "sụt giảm", "kéo giảm"]):
        comp_df = comp_df.sort_values(by="delta", ascending=True)
    elif obj == "top_growers" or any(w in q_lower for w in ["tăng trưởng mạnh nhất", "tăng nhiều nhất"]):
        comp_df = comp_df.sort_values(by="delta", ascending=False)
    else:
        comp_df["abs_delta"] = comp_df["delta"].abs()
        comp_df = comp_df.sort_values(by="abs_delta", ascending=False)

    fact_counter = 2
    for _, row in comp_df.iterrows():
        ent = str(row["entity"])
        d = float(row["delta"])
        pct = float(row["delta_pct"])
        status = row.get("status", "existing")

        if status == "new":
            txt = f"{ent}: Nhóm mới xuất hiện trong kỳ, đóng góp +{_fmt_num(d)}{unit_str} vào tăng trưởng."
        elif status == "discontinued":
            txt = f"{ent}: Ngưng phát sinh trong kỳ này, kéo giảm {_fmt_num(d, force_sign=True)}{unit_str}."
        else:
            act = "đóng góp tăng" if d >= 0 else "kéo giảm"
            txt = f"{ent}: {act} {_fmt_num(d, force_sign=True)}{unit_str} ({_fmt_num(pct, 1, force_sign=True)}% so với kỳ trước)."

        facts.append(
            Fact(
                id=f"F{fact_counter}",
                kind="contribution",
                entity=ent,
                metric=metric_disp,
                value=d,
                unit=metric_unit,
                period=f"{n_window} kỳ gần nhất",
                text=txt,
            )
        )
        fact_counter += 1

    x_contrib = comp_df["entity"].tolist()
    y_contrib = [float(v) for v in comp_df["delta"].tolist()]
    group_disp, _ = resolve_column_display(group_col or "Nhóm")
    contrib_chart = ChartSpec(
        chart_type="bar",
        title=f"Đóng góp vào thay đổi {metric_disp} theo {group_disp}",
        x=x_contrib,
        series={f"Thay đổi {metric_disp}": y_contrib},
        caption=f"Mức thay đổi {n_window} kỳ gần nhất so với {n_window} kỳ liền trước.",
        display_name=f"Thay đổi {metric_disp}",
        unit=metric_unit,
        perspective="contribution_to_change",
        role="primary",
    )
    charts.append(enrich_chart_spec(contrib_chart))

    # 2. Drill-down: Tim nhom dan dat thay doi
    driver_row = None
    target_kw = getattr(goal, "target", None)
    if target_kw:
        match_t = comp_df[comp_df["entity"].str.lower() == str(target_kw).lower()]
        if not match_t.empty:
            driver_row = match_t.iloc[0]

    if driver_row is None:
        for ent in comp_df["entity"]:
            if str(ent).lower() in q_lower:
                match_ent = comp_df[comp_df["entity"] == ent]
                if not match_ent.empty:
                    driver_row = match_ent.iloc[0]
                    break

    if driver_row is None:
        find_mode = primary_task.find if primary_task else None
        if find_mode == "min" or obj == "top_decliners" or any(w in q_lower for w in ["giảm", "sụt", "tụt", "kéo giảm"]):
            driver_row = comp_df.sort_values(by="delta", ascending=True).iloc[0]
        elif find_mode == "max" or obj == "top_growers" or "tăng" in q_lower:
            driver_row = comp_df.sort_values(by="delta", ascending=False).iloc[0]
        else:
            if "abs_delta" not in comp_df.columns:
                comp_df["abs_delta"] = comp_df["delta"].abs()
            driver_row = comp_df.sort_values(by="abs_delta", ascending=False).iloc[0]

    driver_entity = str(driver_row["entity"])
    driver_delta = float(driver_row["delta"])

    # Sắp xếp các cột nhóm ứng viên để drill-down theo đúng thứ bậc nghiệp vụ (ví dụ Category -> Sub-Category / Region, không lấy Ship Mode trước)
    candidate_drill_cols = []
    for c in profile.group_columns:
        if c != group_col and c in df.columns:
            n_u = int(df[c].nunique())
            if 2 <= n_u <= 20:
                prio = _drill_col_priority(c, group_col, n_u)
                candidate_drill_cols.append((prio, c))
    candidate_drill_cols.sort(key=lambda item: item[0], reverse=True)
    other_group_cols = [c for _, c in candidate_drill_cols]

    best_drill_col = None
    best_drill_df = None

    if other_group_cols and group_col:
        sub_df = df[df[group_col] == driver_entity]
        for c2 in other_group_cols:
            drill_res = window_compare(sub_df, c2, metric, time_col, n=n_window)
            if not drill_res.empty and len(drill_res) >= 2:
                best_drill_col = c2
                best_drill_df = drill_res
                break

    if best_drill_df is not None and not best_drill_df.empty:
        if driver_delta < 0:
            sub_leader = best_drill_df.sort_values(by="delta", ascending=True).iloc[0]
        else:
            sub_leader = best_drill_df.sort_values(by="delta", ascending=False).iloc[0]
        sub_leader_name = str(sub_leader["entity"])
        sub_leader_delta = float(sub_leader["delta"])

        other_sub_sum = float(best_drill_df[best_drill_df["entity"] != sub_leader_name]["delta"].sum())
        other_sign = f"+{_fmt_num(other_sub_sum)}" if other_sub_sum >= 0 else _fmt_num(other_sub_sum)

        act_word = "kéo giảm" if sub_leader_delta < 0 else "đóng góp tăng"
        other_word = (
            "bù lại" if (sub_leader_delta < 0 and other_sub_sum >= 0)
            else ("cũng sụt giảm" if (sub_leader_delta < 0 and other_sub_sum < 0)
            else ("kéo giảm lại" if other_sub_sum < 0 else "cũng tăng thêm"))
        )
        sub_driver_text = (
            f"Bên trong {driver_entity}: {best_drill_col} '{sub_leader_name}' "
            f"{act_word} {_fmt_num(abs(sub_leader_delta))}{unit_str} ({_fmt_num(sub_leader_delta, force_sign=True)}{unit_str}); "
            f"các danh mục khác {other_word} {other_sign}{unit_str}."
        )
        facts.append(
            Fact(
                id=f"F{fact_counter}",
                kind="driver",
                entity=f"{driver_entity} × {sub_leader_name}",
                metric=metric_disp,
                value=sub_leader_delta,
                unit=metric_unit,
                period=f"{n_window} kỳ gần nhất",
                text=sub_driver_text,
            )
        )
        fact_counter += 1

        # Nếu có quá nhiều nhóm con (> 8, ví dụ Sub-Category có 9-12 mục), lấy 8 mục biến động lớn nhất và vẽ cột ngang cho dễ đọc
        plot_drill_df = best_drill_df.copy()
        if len(plot_drill_df) > 8:
            plot_drill_df["_abs_d"] = plot_drill_df["delta"].abs()
            plot_drill_df = plot_drill_df.sort_values(by="_abs_d", ascending=False).head(8).sort_values(by="delta", ascending=True)
        drill_disp, _ = resolve_column_display(best_drill_col)
        drill_chart_type = "bar_horizontal" if len(plot_drill_df) > 6 else "bar"
        drill_chart = ChartSpec(
            chart_type=drill_chart_type,
            title=f"Bóc tách thay đổi bên trong {driver_entity} theo {drill_disp}",
            x=plot_drill_df["entity"].tolist(),
            series={f"Thay đổi {metric_disp}": [float(v) for v in plot_drill_df["delta"].tolist()]},
            caption=f"{sub_leader_name} là yếu tố tác động mạnh nhất trong {driver_entity}.",
            display_name=f"Thay đổi {metric_disp}",
            unit=metric_unit,
            perspective="contribution_to_change",
            role="supplementary",
        )
        charts.append(enrich_chart_spec(drill_chart))

    # 3. Tuong quan: chuan hoa z-score trong tung chuoi de khu confounding quy mo
    num_cols = [c for c in profile.numeric_columns if c != metric]
    if len(num_cols) >= 1 and group_col and len(df) >= 30:
        correlations = []
        series_group_cols = [c for c in profile.group_columns if df[c].nunique() >= 2]
        group_keys = series_group_cols if series_group_cols else [group_col]

        for other_num in num_cols:
            r_vals = []
            weights = []
            for _, grp in df.groupby(group_keys):
                if len(grp) >= 6:
                    s1 = grp[metric].astype(float)
                    s2 = grp[other_num].astype(float)
                    if s1.std() > 1e-6 and s2.std() > 1e-6:
                        z1 = (s1 - s1.mean()) / s1.std()
                        z2 = (s2 - s2.mean()) / s2.std()
                        r = float(np.corrcoef(z1, z2)[0, 1])
                        if not np.isnan(r):
                            r_vals.append(r)
                            weights.append(len(grp))
            if r_vals:
                w_avg_r = float(np.average(r_vals, weights=weights))
                correlations.append((other_num, w_avg_r))

        if correlations:
            correlations.sort(key=lambda x: abs(x[1]), reverse=True)
            top_corr = correlations[:5]

            for other_col, r_val in top_corr[:3]:
                corr_disp, _ = resolve_column_display(other_col)
                strength = "mạnh" if abs(r_val) > 0.6 else ("vừa" if abs(r_val) >= 0.3 else "yếu")
                corr_text = (
                    f"Tương quan trong từng chuỗi giữa {corr_disp} và {metric_disp}: r = {r_val:.2f} "
                    f"({strength}, n={len(df)}). Lưu ý: Tương quan đồng biến/nghịch biến, không chứng minh quan hệ nhân quả."
                )
                facts.append(
                    Fact(
                        id=f"F{fact_counter}",
                        kind="correlation",
                        entity=corr_disp,
                        metric=metric_disp,
                        value=round(r_val, 2),
                        text=corr_text,
                    )
                )
                fact_counter += 1

            corr_chart = ChartSpec(
                chart_type="bar_horizontal",
                title=f"Hệ số tương quan trong từng chuỗi với {metric_disp}",
                x=[resolve_column_display(c)[0] for c, _ in top_corr],
                series={"Hệ số tương quan (r)": [round(r, 2) for _, r in top_corr]},
                caption="Tính sau khi chuẩn hóa z-score theo nhóm; tương quan không đồng nghĩa với nhân quả.",
                unit="r",
                role="supplementary",
            )
            charts.append(enrich_chart_spec(corr_chart))
    elif len(num_cols) < 1:
        warnings.append("Dữ liệu chỉ có 1 cột số; bỏ qua bước phân tích tương quan.")

    narrative_text = _generate_diagnostic_narrative(facts, llm)
    narrative = InsightResult(insight_text=narrative_text, confidence_score=0.92)

    return Section(level="diagnostic", charts=charts, narrative=narrative, warnings=warnings), facts


def _generate_diagnostic_narrative(facts: list[Fact], llm: Optional[LLMClient]) -> str:
    """Tao loi dien giai bang LLM dua DUY NHAT tren danh sach Facts; fallback neu loi."""
    if not facts:
        return "Không có đủ dữ kiện để đưa ra chẩn đoán."

    fallback_text = "\n\n".join(f"• {f.text}" for f in facts)

    if not llm:
        return fallback_text

    prompt = (
        "Bạn là chuyên viên phân tích kinh doanh. Dưới đây là DANH SÁCH SỰ THẬT ĐÃ TÍNH TOÁN CHÍNH XÁC:\n"
        + "\n".join(f"[{f.id}] {f.text}" for f in facts)
        + "\n\n"
        "Yêu cầu:\n"
        "- Viết một đoạn nhận xét chẩn đoán ngắn gọn (3–5 câu) bằng văn bản thuần túy (KHÔNG dùng dấu ** hay markdown) giải thích yếu tố nào đóng góp chính vào thay đổi.\n"
        "- BẮT BUỘC chỉ dùng các con số và đối tượng có trong danh sách sự thật trên.\n"
        "- KHÔNG tự bịa con số mới.\n"
        "- CẤM dùng từ khẳng định nguyên nhân tuyệt đối ('chắc chắn do', 'nguyên nhân chính là'); "
        "dùng cách diễn đạt trung thực: 'yếu tố kéo giảm/tăng nhiều nhất là', 'có liên quan thuận chiều với'.\n"
        "Nhận xét:"
    )

    try:
        text = llm.complete_text(prompt).strip().replace("**", "")
        return text if text else fallback_text
    except Exception as exc:
        logger.warning("LLM dien giai chan doan loi, dung fallback tat dinh: %s", exc)
        return fallback_text