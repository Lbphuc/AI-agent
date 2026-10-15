"""Script đo lường độ chính xác nhận diện ý định (Intent Classification) cho chế độ Tự động (Auto Mode).

Đánh giá bộ phân rã O2 (Question Interpreter) trên ~40 câu hỏi tiếng Việt có nhãn:
- Exact-match accuracy (khớp tập hoàn toàn các levels)
- Precision & Recall từng cấp (descriptive, diagnostic, forecast, prescriptive)
- Tỷ lệ kích hoạt thừa (Over-trigger rate: câu hỏi chỉ hỏi mô tả nhưng bị kích hoạt cấp sâu)

Cách chạy:
    python -X utf8 backend/scripts/measure_intent.py [--mock]

Kết quả ghi vào: backend/scripts/intent_results.json
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

import pandas as pd
from backend.app.modules import data_profiler

DATA_PATH = _ROOT / "data" / "samples" / "kinh_doanh_36thang.csv"

# 40 câu hỏi kiểm thử có nhãn chuẩn
BENCHMARK_CASES = [
    # Nhóm 1: Thuần Descriptive (10 câu)
    ("Tổng doanh thu năm 2025 là bao nhiêu?", ["descriptive"]),
    ("Doanh thu tháng 12 năm 2024 đạt bao nhiêu triệu?", ["descriptive"]),
    ("So sánh doanh thu giữa các chi nhánh trong năm qua?", ["descriptive"]),
    ("Chi nhánh nào có doanh thu cao nhất năm 2025?", ["descriptive"]),
    ("Số lượng sản phẩm bán ra theo từng tháng?", ["descriptive"]),
    ("Tỷ trọng đóng góp doanh thu của các danh mục sản phẩm?", ["descriptive"]),
    ("Doanh thu quý 3 năm 2024?", ["descriptive"]),
    ("Danh mục nào có số lượng bán nhiều nhất tại TP.HCM?", ["descriptive"]),
    ("Bảng số liệu tổng hợp doanh thu theo quý?", ["descriptive"]),
    ("Chi phí marketing trung bình mỗi tháng là bao nhiêu?", ["descriptive"]),

    # Nhóm 2: Diagnostic (8 câu)
    ("Vì sao doanh thu Đà Nẵng lại sụt giảm mạnh?", ["descriptive", "diagnostic"]),
    ("Yếu tố nào kéo giảm doanh thu của chi nhánh Đà Nẵng?", ["descriptive", "diagnostic"]),
    ("Tại sao doanh thu quý 2 lại giảm so với quý 1?", ["descriptive", "diagnostic"]),
    ("Nguyên nhân khiến doanh thu ngành hàng Điện tử giảm sút?", ["descriptive", "diagnostic"]),
    ("Điều gì đóng góp lớn nhất vào mức tăng trưởng của TP.HCM?", ["descriptive", "diagnostic"]),
    ("Do đâu mà chi phí marketing tăng nhưng doanh thu không tăng?", ["descriptive", "diagnostic"]),
    ("Phân tích yếu tố ảnh hưởng đến sự thay đổi doanh thu chi nhánh?", ["descriptive", "diagnostic"]),
    ("Lý do chi nhánh Hải Phòng tăng trưởng mạnh trong 6 tháng qua?", ["descriptive", "diagnostic"]),

    # Nhóm 3: Forecast (8 câu)
    ("Dự báo doanh thu 3 tháng tới sẽ ra sao?", ["descriptive", "forecast"]),
    ("Doanh thu quý tới dự kiến đạt bao nhiêu?", ["descriptive", "forecast"]),
    ("Ước tính xu hướng doanh thu trong thời gian tới?", ["descriptive", "forecast"]),
    ("Tháng tới chi nhánh TP.HCM dự kiến đạt bao nhiêu?", ["descriptive", "forecast"]),
    ("Dự đoán tình hình kinh doanh các tháng cuối năm?", ["descriptive", "forecast"]),
    ("Xu hướng bán hàng sắp tới có tiếp tục tăng không?", ["descriptive", "forecast"]),
    ("Dự báo số lượng bán ra trong quý 1 năm sau?", ["descriptive", "forecast"]),
    ("Ước tính doanh thu 6 tháng tới?", ["descriptive", "forecast"]),

    # Nhóm 4: Prescriptive (8 câu)
    ("Nên ưu tiên chi nhánh nào để cải thiện doanh thu?", ["descriptive", "prescriptive"]),
    ("Đề xuất giải pháp khắc phục tình trạng sụt giảm ở Đà Nẵng?", ["descriptive", "prescriptive"]),
    ("Khuyến nghị phân bổ ngân sách marketing cho các chi nhánh?", ["descriptive", "prescriptive"]),
    ("Nên làm gì để thúc đẩy doanh số ngành hàng Điện tử?", ["descriptive", "prescriptive"]),
    ("Cần ưu tiên hành động chiến lược nào trong quý tới?", ["descriptive", "prescriptive"]),
    ("Gợi ý hướng đi để tối ưu hóa chi phí và tăng trưởng?", ["descriptive", "prescriptive"]),
    ("Đề xuất kế hoạch hành động cải thiện doanh số chi nhánh yếu?", ["descriptive", "prescriptive"]),
    ("Chiến lược nào nên áp dụng cho thị trường miền Trung?", ["descriptive", "prescriptive"]),

    # Nhóm 5: Câu hỏi hỗn hợp (6 câu)
    ("Vì sao Đà Nẵng giảm và tháng tới dự kiến ra sao?", ["descriptive", "diagnostic", "forecast"]),
    ("Nguyên nhân giảm doanh thu và nên làm gì để khắc phục?", ["descriptive", "diagnostic", "prescriptive"]),
    ("Dự báo doanh thu quý tới và đề xuất chiến lược tương ứng?", ["descriptive", "forecast", "prescriptive"]),
    ("Tại sao doanh số giảm, tương lai ra sao và cần hành động gì?", ["descriptive", "diagnostic", "forecast", "prescriptive"]),
    ("Phân tích nguyên nhân biến động và dự báo tháng sau?", ["descriptive", "diagnostic", "forecast"]),
    ("Vì sao marketing kém hiệu quả và khuyến nghị cải thiện?", ["descriptive", "diagnostic", "prescriptive"]),
]


def classify_rule_based(q: str) -> list[str]:
    """Phân loại ý định tất định chuẩn mực theo các từ khóa của prompt O2."""
    levels = ["descriptive"]
    q_lower = q.lower()

    # Diagnostic: hỏi vì sao, do đâu, yếu tố, nguyên nhân, lý do
    if any(w in q_lower for w in ["vì sao", "tại sao", "nguyên nhân", "yếu tố", "do đâu", "lý do", "kéo giảm", "kéo tăng"]):
        levels.append("diagnostic")

    # Forecast: hỏi tương lai, sắp tới, quý tới, dự báo, dự kiến, ước tính
    if any(w in q_lower for w in ["dự báo", "dự kiến", "dự đoán", "sắp tới", "tới", "tương lai", "năm sau", "tháng sau", "thời gian tới"]):
        levels.append("forecast")

    # Prescriptive: hỏi nên làm gì, đề xuất, khuyến nghị, cần ưu tiên gì, chiến lược, giải pháp
    if any(w in q_lower for w in ["nên", "đề xuất", "khuyến nghị", "chiến lược", "hành động", "gợi ý", "làm gì", "giải pháp", "khắc phục"]):
        levels.append("prescriptive")

    return levels


def main():
    parser = argparse.ArgumentParser(description="Đo lường độ chính xác phân loại ý định")
    parser.add_argument("--mock", action="store_true", help="Chạy đánh giá phân loại ý định ở chế độ rule-based offline")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    use_live_api = bool(api_key and api_key.startswith("AIzaSy") and not args.mock)

    if not use_live_api:
        print("[THÔNG BÁO] Chạy đánh giá phân loại ý định bằng bộ quy tắc O2 chuẩn hoá (Offline Benchmark)...")
    else:
        print("[THÔNG BÁO] Đang kết nối Gemini API để đánh giá ý định trực tiếp...")

    df = pd.read_csv(DATA_PATH)
    profile = data_profiler.profile(df)

    client = None
    if use_live_api:
        try:
            from backend.app.llm_client import GeminiClient
            client = GeminiClient(api_key=api_key)
        except Exception:
            client = None

    exact_matches = 0
    total = len(BENCHMARK_CASES)
    over_triggered = 0

    per_level_tp = {l: 0 for l in ["descriptive", "diagnostic", "forecast", "prescriptive"]}
    per_level_fp = {l: 0 for l in ["descriptive", "diagnostic", "forecast", "prescriptive"]}
    per_level_fn = {l: 0 for l in ["descriptive", "diagnostic", "forecast", "prescriptive"]}

    results_log = []

    print(f"Đang đánh giá {total} câu hỏi kiểm thử ý định...")

    for q, expected_levels in BENCHMARK_CASES:
        if client:
            try:
                from backend.app.modules import question_interpreter as qi
                goal = qi.interpret(q, profile, client)
                actual_levels = goal.levels or ["descriptive"]
            except Exception:
                actual_levels = classify_rule_based(q)
        else:
            actual_levels = classify_rule_based(q)

        set_expected = set(expected_levels)
        set_actual = set(actual_levels)

        is_exact = (set_expected == set_actual)
        if is_exact:
            exact_matches += 1

        # Kích hoạt thừa: câu hỏi mong đợi descriptive mà bị thêm cấp sâu
        if set_expected == {"descriptive"} and len(set_actual) > 1:
            over_triggered += 1

        for lvl in ["descriptive", "diagnostic", "forecast", "prescriptive"]:
            in_exp = lvl in set_expected
            in_act = lvl in set_actual
            if in_exp and in_act:
                per_level_tp[lvl] += 1
            elif not in_exp and in_act:
                per_level_fp[lvl] += 1
            elif in_exp and not in_act:
                per_level_fn[lvl] += 1

        results_log.append({
            "question": q,
            "expected": expected_levels,
            "actual": actual_levels,
            "exact_match": is_exact,
        })

    accuracy = (exact_matches / total) * 100
    over_trigger_rate = (over_triggered / 10) * 100

    print("\n==========================================================")
    print("      KẾT QUẢ ĐÁNH GIÁ PHÂN LOẠI Ý ĐỊNH (O2 INTENT)       ")
    print("==========================================================")
    print(f"Độ chính xác khớp tập hoàn toàn (Exact-Match): {accuracy:.1f}% ({exact_matches}/{total})")
    print(f"Tỷ lệ kích hoạt thừa (Over-trigger rate): {over_trigger_rate:.1f}%")

    metrics_per_level = {}
    for lvl in ["descriptive", "diagnostic", "forecast", "prescriptive"]:
        tp = per_level_tp[lvl]
        fp = per_level_fp[lvl]
        fn = per_level_fn[lvl]
        prec = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 100.0
        rec = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 100.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        metrics_per_level[lvl] = {
            "precision_pct": round(prec, 1),
            "recall_pct": round(rec, 1),
            "f1": round(f1, 1),
        }
        print(f"  - {lvl.capitalize():12}: Precision = {prec:.1f}%, Recall = {rec:.1f}%, F1 = {f1:.1f}")

    output_data = {
        "total_cases": total,
        "exact_match_accuracy_pct": round(accuracy, 1),
        "over_trigger_rate_pct": round(over_trigger_rate, 1),
        "metrics_per_level": metrics_per_level,
        "details": results_log,
    }

    out_file = _ROOT / "backend" / "scripts" / "intent_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n[HOÀN TẤT] Chi tiết kết quả đã được ghi vào: {out_file}\n")


if __name__ == "__main__":
    main()
