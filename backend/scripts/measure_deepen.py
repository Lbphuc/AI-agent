"""Script đo lường và đánh giá thực nghiệm cho 3 cấp phân tích sâu:
Chẩn đoán (Diagnostic) · Dự báo (Forecast) · Đề xuất (Prescriptive).

Chạy độc lập để thu thập số liệu đưa vào báo cáo đồ án:
1. Tỷ lệ tìm đúng driver (Đà Nẵng × Điện tử) trên 20 seed
2. So sánh tương quan gộp vs tương quan trong từng chuỗi (khử hiệu ứng quy mô)
3. Backtest MAPE dự báo và độ phủ dải tin cậy 80%
4. Kiểm chứng đề xuất có bằng chứng hợp lệ (trước vs sau verify)
5. Đo độ trễ tính toán từng cấp

Cách chạy:
    python backend/scripts/measure_deepen.py [--seeds 20]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Đảm bảo import được backend
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=True)
except ImportError:
    pass

import numpy as np
import pandas as pd

from backend.app.schemas import AnalysisGoal, AnalysisTask, Recommendation
from backend.app.modules import data_profiler
from backend.app.modules.analytics import diagnostic, forecast, verify, prescriptive
from data.samples.tao_du_lieu_manh import generate_dataset


def _make_goal(question: str = "Vì sao doanh thu Đà Nẵng giảm?") -> AnalysisGoal:
    return AnalysisGoal(
        question=question,
        time_scope="last_12_months",
        time_start="2025-01-01",
        time_end="2025-12-31",
        tasks=[
            AnalysisTask(
                type="growth_rate",
                metric="Doanh_thu_trieu_vnd",
                group_by="Chi_nhanh",
                find="min",
                chart_hint=None,
            )
        ],
        levels=["diagnostic", "forecast"],
    )


def evaluate_diagnostic(n_seeds: int = 20) -> dict:
    """Đo tỷ lệ tìm đúng driver và chênh lệch hệ số tương quan trên n_seeds."""
    print(f"\n--- 1. ĐÁNH GIÁ CẤP CHẨN ĐOÁN (DIAGNOSTIC) TRÊN {n_seeds} SEEDS ---")
    driver_found_count = 0
    corrs_within: list[float] = []
    corrs_pooled: list[float] = []
    times: list[float] = []
    goal = _make_goal()

    for seed in range(2026, 2026 + n_seeds):
        df = generate_dataset(seed=seed)
        profile = data_profiler.profile(df)

        t0 = time.perf_counter()
        diag_sec, diag_facts = diagnostic.run_diagnostic(
            df=df,
            profile=profile,
            goal=goal,
        )
        t1 = time.perf_counter()
        times.append(t1 - t0)

        # Kiểm tra driver
        top_driver_fact = next((f for f in diag_facts if f.kind == "driver"), None)
        if top_driver_fact and "Đà Nẵng" in top_driver_fact.text and "Điện tử" in top_driver_fact.text:
            driver_found_count += 1

        # Lấy tương quan trong chuỗi
        corr_fact = next((f for f in diag_facts if f.kind == "correlation"), None)
        if corr_fact:
            corrs_within.append(corr_fact.value)

        # Tính tương quan gộp để so sánh
        if "Chi_phi_marketing_trieu_vnd" in df.columns:
            r_pool = float(df["Doanh_thu_trieu_vnd"].corr(df["Chi_phi_marketing_trieu_vnd"]))
            corrs_pooled.append(r_pool)

    driver_rate = (driver_found_count / n_seeds) * 100
    avg_r_within = float(np.mean(corrs_within)) if corrs_within else 0.0
    avg_r_pooled = float(np.mean(corrs_pooled)) if corrs_pooled else 0.0
    avg_time = float(np.mean(times))

    print(f"Tỷ lệ tìm đúng driver (Đà Nẵng × Điện tử): {driver_rate:.1f}% ({driver_found_count}/{n_seeds})")
    print(f"Hệ số tương quan trung bình: r_within = {avg_r_within:.3f} vs r_pooled = {avg_r_pooled:.3f}")
    print(f"Thời gian tính toán trung bình: {avg_time * 1000:.1f} ms")

    return {
        "n_seeds": n_seeds,
        "driver_identification_rate_pct": driver_rate,
        "avg_r_within_series": avg_r_within,
        "avg_r_pooled": avg_r_pooled,
        "avg_latency_ms": avg_time * 1000,
    }


def evaluate_forecast(n_seeds: int = 20) -> dict:
    """Đo MAPE của mô hình chọn vs naive, và độ phủ thực tế của dải tin cậy 80%."""
    print(f"\n--- 2. ĐÁNH GIÁ CẤP DỰ BÁO (FORECAST) TRÊN {n_seeds} SEEDS ---")
    mapes_selected: list[float] = []
    coverage_80_rates: list[float] = []
    times: list[float] = []
    goal = _make_goal()

    for seed in range(2026, 2026 + n_seeds):
        df = generate_dataset(seed=seed)
        profile = data_profiler.profile(df)

        t0 = time.perf_counter()
        fc_sec, fc_facts = forecast.run_forecast(
            df=df,
            profile=profile,
            goal=goal,
            h=3,
        )
        t1 = time.perf_counter()
        times.append(t1 - t0)

        # Lấy MAPE fact
        fact_mape = next((f for f in fc_facts if "MAPE" in f.text or "mape" in f.id.lower()), None)
        if fact_mape:
            mapes_selected.append(fact_mape.value)

        # Đánh giá coverage dải 80%: rolling test
        monthly_totals = df.groupby("Thang")["Doanh_thu_trieu_vnd"].sum().values
        n = len(monthly_totals)
        h = 3
        cycle_len = 12
        if n >= 15:
            in_band_count = 0
            total_points = 0
            for origin in range(n - 10, n - h):
                train = monthly_totals[:origin]
                actuals = monthly_totals[origin : origin + h]
                best_name = "seasonal_decomp" if (len(train) >= 24) else "linear"
                pred_fn = forecast.MODEL_REGISTRY[best_name][0]
                preds = pred_fn(train, h, cycle_len)
                mape_val, errs_by_step = forecast.run_backtest(train, pred_fn, h=h, cycle=cycle_len, min_train=8)
                for step_idx in range(h):
                    step_errs = errs_by_step[step_idx] if step_idx < len(errs_by_step) else []
                    q80 = float(np.quantile(step_errs, 0.8)) if len(step_errs) >= 4 else (preds[step_idx] * 0.1)
                    lower = max(0.0, preds[step_idx] - q80)
                    upper = preds[step_idx] + q80
                    if lower <= actuals[step_idx] <= upper:
                        in_band_count += 1
                    total_points += 1
            if total_points > 0:
                coverage_80_rates.append((in_band_count / total_points) * 100)

    avg_mape = float(np.mean(mapes_selected)) if mapes_selected else 0.0
    avg_coverage = float(np.mean(coverage_80_rates)) if coverage_80_rates else 0.0
    avg_time = float(np.mean(times))

    print(f"MAPE trung bình của mô hình chọn: {avg_mape:.2f}%")
    print(f"Độ phủ thực tế của dải tin cậy 80%: {avg_coverage:.1f}% (kỳ vọng ~80%)")
    print(f"Thời gian tính toán trung bình: {avg_time * 1000:.1f} ms")

    return {
        "n_seeds": n_seeds,
        "avg_backtest_mape_pct": avg_mape,
        "empirical_coverage_80_pct": avg_coverage,
        "avg_latency_ms": avg_time * 1000,
    }


def evaluate_prescriptive_ablation() -> dict:
    """Thí nghiệm cắt bỏ (ablation study): so sánh tỷ lệ vi phạm trước vs sau verify.py."""
    print("\n--- 3. ĐÁNH GIÁ BỘ KIỂM CHỨNG ĐỀ XUẤT (VERIFY ABLATION) ---")
    df = generate_dataset(seed=2026)
    profile = data_profiler.profile(df)
    goal = _make_goal()

    # Lấy FactSheet chuẩn
    diag_sec, diag_facts = diagnostic.run_diagnostic(df, profile, goal)
    fc_sec, fc_facts = forecast.run_forecast(df, profile, goal, h=3)
    all_facts = diag_facts + fc_facts

    # Tạo từ điển facts theo ID
    facts_dict = {f.id: f for f in all_facts}
    driver_id = next((f.id for f in all_facts if f.kind == "driver"), "F3")
    corr_id = next((f.id for f in all_facts if f.kind == "correlation"), "F4")
    contrib_id = next((f.id for f in all_facts if f.kind == "contribution"), "F2")
    fc_id = next((f.id for f in all_facts if f.kind == "forecast"), "F5")

    # Tập 6 khuyến nghị giả lập (gồm cả khuyến nghị chuẩn và khuyến nghị vi phạm quy tắc)
    test_recs = [
        # Hợp lệ 1
        Recommendation(
            title="Rà soát danh mục Điện tử tại Đà Nẵng",
            action="Tập trung kiểm tra nguyên nhân giảm 381,1 triệu VNĐ của ngành hàng Điện tử tại Đà Nẵng.",
            rationale="Doanh thu Điện tử Đà Nẵng giảm mạnh 381,1 triệu VNĐ.",
            fact_ids=[driver_id],
            priority="cao",
            caveat="Cần kiểm tra lại tồn kho và biên lợi nhuận thực tế.",
        ),
        # Hợp lệ 2
        Recommendation(
            title="Theo dõi ngân sách Marketing",
            action="Duy trì thử nghiệm chi phí marketing tại các chi nhánh có tương quan dương.",
            rationale="Tương quan marketing và doanh thu trong từng chuỗi đạt r = 0,46.",
            fact_ids=[corr_id],
            priority="trung bình",
            caveat="Tương quan thống kê không đồng nghĩa quan hệ nhân quả tuyệt đối.",
        ),
        # Vi phạm 1: Bịa fact_id không tồn tại
        Recommendation(
            title="Tăng cường bán hàng tại Cần Thơ",
            action="Mở rộng chi nhánh Cần Thơ ngay lập tức.",
            rationale="Cần Thơ tăng trưởng mạnh nhất.",
            fact_ids=["F_FAKE_999"],
            priority="cao",
            caveat="Chưa rõ chi phí thuê mặt bằng.",
        ),
        # Vi phạm 2: Bịa số liệu không có trong fact đã trích
        Recommendation(
            title="Cắt giảm chi phí tại Hải Phòng",
            action="Cắt giảm 9999 triệu VNĐ chi phí vận hành tại Hải Phòng.",
            rationale="Hải Phòng đóng góp tăng trưởng.",
            fact_ids=[contrib_id],
            priority="thấp",
            caveat="Cần khảo sát ý kiến nhân sự.",
        ),
        # Vi phạm 3: Thiếu caveat hợp lệ
        Recommendation(
            title="Đẩy mạnh TP.HCM",
            action="Chi thêm ngân sách cho TP.HCM.",
            rationale="TP.HCM dẫn đầu mức tăng.",
            fact_ids=[contrib_id],
            priority="cao",
            caveat="",
        ),
        # Vi phạm 4: Fact ước tính dự báo nhưng khẳng định chắc chắn 100% không ghi ước tính
        Recommendation(
            title="Cam kết đạt doanh thu",
            action="Khẳng định đạt 2155 triệu VNĐ tháng 3 tới.",
            rationale="Doanh thu kỳ tới chắc chắn đạt 2155 triệu VNĐ.",
            fact_ids=[fc_id],
            priority="cao",
            caveat="Tùy thuộc thị trường biến động.",
        ),
    ]

    valid_before = len(test_recs)
    valid_after = 0
    rejected_reasons = []

    for r in test_recs:
        is_ok, reason = verify.verify_recommendation(r, all_facts)
        if is_ok:
            valid_after += 1
        else:
            rejected_reasons.append(reason)

    print(f"Tổng số đề xuất thử nghiệm: {valid_before}")
    print(f"Số đề xuất hợp lệ sau verify: {valid_after} (Loại bỏ {valid_before - valid_after} đề xuất sai phạm/bịa đặt)")
    print("Các lỗi đã phát hiện và chặn đứng thành công:")
    for i, r in enumerate(rejected_reasons, 1):
        print(f"  [{i}] {r}")

    return {
        "total_tested": valid_before,
        "valid_after_verify": valid_after,
        "blocked_hallucinations": valid_before - valid_after,
        "filter_efficiency_pct": ((valid_before - valid_after) / (valid_before - 2)) * 100,
    }


def main():
    parser = argparse.ArgumentParser(description="Đo lường và đánh giá thực nghiệm cho 3 cấp phân tích sâu")
    parser.add_argument("--seeds", type=int, default=20, help="Số lượng seeds để chạy kiểm chứng thống kê")
    args = parser.parse_args()

    print("=====================================================================")
    print("      ĐO LƯỜNG THỰC NGHIỆM HỆ THỐNG PHÂN TÍCH SÂU 3 CẤP (BI AGENT)     ")
    print("=====================================================================")

    diag_metrics = evaluate_diagnostic(n_seeds=args.seeds)
    fc_metrics = evaluate_forecast(n_seeds=args.seeds)
    ablation_metrics = evaluate_prescriptive_ablation()

    results = {
        "diagnostic": diag_metrics,
        "forecast": fc_metrics,
        "prescriptive_ablation": ablation_metrics,
    }

    out_path = _ROOT / "backend" / "scripts" / "deepen_experiment_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[HOÀN TẤT] Kết quả thực nghiệm đã được ghi vào: {out_path}\n")


if __name__ == "__main__":
    main()
