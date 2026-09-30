"""Script đo AER (Analysis Error Rate) — chạy thủ công, tốn API call thật.

AER = số task thất bại hẳn (sau max_attempts lần) / tổng số task × 100
Ngưỡng chấp nhận: ≤ 10% (theo SRS mục 8, NFR-04).

Cách chạy (cần GEMINI_API_KEY trong .env):
    python3.11.exe backend/scripts/measure_aer.py

Kết quả ghi vào: backend/scripts/aer_results.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Đảm bảo import backend được từ thư mục gốc dự án
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=True)
except ImportError:
    pass

import pandas as pd

from backend.app.llm_client import GeminiClient
from backend.app.modules import data_profiler
from backend.app.modules import question_interpreter as qi
from backend.app.modules.analysis_runner import run_task

# ---------------------------------------------------------------------------
# Bộ câu hỏi mẫu — tái dùng từ test_question_interpreter.py + thêm case mới
# ---------------------------------------------------------------------------
SAMPLES_DIR = _ROOT / "data" / "samples"

_TEST_CASES = [
    # (file, question, task_type)
    ("doanh_thu.csv", "Chi nhánh nào giảm doanh thu mạnh nhất?", "growth_rate"),
    ("doanh_thu.csv", "Xu hướng doanh thu tổng thể 12 tháng gần nhất?", "trend"),
    ("doanh_thu.csv", "So sánh tổng doanh thu giữa các chi nhánh?", "comparison"),
    ("doanh_thu.csv", "Chi nhánh nào tăng trưởng cao nhất?", "growth_rate"),
    ("doanh_thu.csv", "Doanh thu 3 tháng gần nhất thế nào?", "trend"),
]


def _load_df(filename: str) -> pd.DataFrame:
    path = SAMPLES_DIR / filename
    return pd.read_csv(path)


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[LỖI] Cần GEMINI_API_KEY trong .env")
        sys.exit(1)

    llm = GeminiClient(api_key=api_key)

    results = []
    total = len(_TEST_CASES)
    success_first_try = 0
    success_retry = 0
    failed = 0

    print(f"Đang đo AER trên {total} test case...\n")

    for i, (filename, question, expected_type) in enumerate(_TEST_CASES, 1):
        print(f"[{i}/{total}] {filename} | '{question[:50]}...' | type={expected_type}")

        df = _load_df(filename)
        profile = data_profiler.profile(df)

        # Interpret question để lấy goal + task
        try:
            goal = qi.interpret(question, profile, llm=llm)
        except Exception as exc:
            print(f"  ❌ Interpret thất bại: {exc}")
            results.append({
                "case": i, "file": filename, "question": question,
                "stage": "interpret", "success": False, "attempts": 0, "error": str(exc),
            })
            failed += 1
            time.sleep(2)
            continue

        # Lấy task đầu tiên khớp expected_type (hoặc task đầu tiên nếu không có)
        task = next((t for t in goal.tasks if t.type == expected_type), goal.tasks[0])

        exec_result = run_task(
            task=task,
            goal=goal,
            profile=profile,
            df=df,
            llm=llm,
            max_attempts=3,
        )

        case_result = {
            "case": i,
            "file": filename,
            "question": question,
            "task_type": task.type,
            "success": exec_result.success,
            "attempts": exec_result.attempts,
            "error": exec_result.error,
        }
        results.append(case_result)

        if exec_result.success:
            if exec_result.attempts == 1:
                success_first_try += 1
                print(f"  ✅ Thành công ngay lần 1")
            else:
                success_retry += 1
                print(f"  ✅ Thành công sau {exec_result.attempts} lần thử")
        else:
            failed += 1
            print(f"  ❌ Thất bại sau {exec_result.attempts} lần: {exec_result.error[:80]}")

        # Nghỉ giữa các lần gọi để tránh rate limit
        time.sleep(3)

    # Tính AER
    aer = failed / total * 100
    summary = {
        "total": total,
        "success_first_try": success_first_try,
        "success_after_retry": success_retry,
        "failed": failed,
        "aer_percent": round(aer, 1),
        "threshold_percent": 10.0,
        "passed": aer <= 10.0,
        "cases": results,
    }

    output_path = Path(__file__).parent / "aer_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Kết quả AER:")
    print(f"  Tổng test case      : {total}")
    print(f"  Thành công lần 1    : {success_first_try}")
    print(f"  Thành công sau retry: {success_retry}")
    print(f"  Thất bại hẳn        : {failed}")
    print(f"  AER                 : {aer:.1f}% (ngưỡng ≤10%)")
    print(f"  Kết luận            : {'✅ ĐẠT' if aer <= 10.0 else '❌ KHÔNG ĐẠT'}")
    print(f"\nKết quả đã lưu vào: {output_path}")


if __name__ == "__main__":
    main()
