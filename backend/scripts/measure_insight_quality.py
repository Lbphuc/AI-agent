"""Script do chat luong Insight Generator (O5) -- offline, khong chay real-time.

Muc dich: do luong Insight Relevance (SRS muc 8) tren bo cau hoi mau,
tinh diem trung binh confidence_score (heuristic doi chieu so lieu) va
tuy chon chay LLM-based SEVQ scoring (chon diem 1-10 co giai thich).

Tai sao la script rieng (khong phai test tu dong)?
  - Tong hop duoc, chi goi LLM khi can (tiet kiem API, tranh lam cham CI).
  - Script benchmark va test tu dong la 2 muc tieu khac nhau:
      * CI test: kiem tra logic dung sai, dung FakeLLM, chay nhanh.
      * Script nay: do chat luong thuc te, tong hop ket qua, ghi CSV de bao cao.
  - Tinh than giong measure_aer.py (Tuan 4) da ap dung cho O3.

Cach chay:
    python backend/scripts/measure_insight_quality.py --csv data/doanh_thu.csv
    python backend/scripts/measure_insight_quality.py --csv data/doanh_thu.csv --sevq

Yeu cau: GEMINI_API_KEY trong .env (goi LLM that), hoac ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

# Them goc du an vao sys.path (chay truc tiep bang python, khong phai pytest)
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bo cau hoi mau -- du lieu doanh_thu.csv (vi du xuyen suot du an)
# ---------------------------------------------------------------------------

SAMPLE_QUESTIONS = [
    "Chi nhanh nao giam doanh thu manh nhat trong 12 thang gan nhat?",
    "Xu huong doanh thu toan he thong thay doi the nao?",
    "So sanh doanh thu giua cac chi nhanh trong nam qua.",
    "Chi nhanh nao tang truong tot nhat?",
    "Tong doanh thu cua toan he thong trong 6 thang gan nhat la bao nhieu?",
]

SEVQ_PROMPT_TEMPLATE = """Ban la chuyen gia danh gia chat luong van ban phan tich du lieu.

Cau hoi nguoi dung: "{question}"

Nhan xet do AI sinh ra: "{insight}"

So lieu thuc te (cac con so chinh xac):
{data_summary}

Hay cham diem nhan xet tren theo thang 1-10 theo 3 tieu chi:
1. Do chinh xac (cac con so co trong nhan xet co khop voi so lieu thuc te?)
2. Do lien quan (nhan xet co tra loi dung cau hoi?)
3. Do ro rang (van phong co de hieu, tu nhien?)

Tra ve JSON nhu sau:
{{"score": <1-10>, "accuracy": <1-10>, "relevance": <1-10>, "clarity": <1-10>, "rationale": "<giai thich ngan>"}}"""


# ---------------------------------------------------------------------------
# Ham chay 1 cau hoi qua pipeline day du
# ---------------------------------------------------------------------------

def run_one(
    question: str,
    df: pd.DataFrame,
    llm,  # GeminiClient hoac ClaudeClient
    use_sevq: bool = False,
) -> dict:
    """Chay pipeline O1->O5 cho 1 cau hoi, tra ve dict ket qua."""
    from backend.app.modules import (
        analysis_runner,
        chart_generator,
        data_profiler,
        question_interpreter,
    )
    from backend.app.modules.insight_generator import (
        InsightGenerationError,
        _collect_known_values,
        _format_task_result,
        generate_insight,
    )
    from backend.app.schemas import TaskResult

    logger.info("--- Cau hoi: %s", question)

    # O1
    profile = data_profiler.profile(df)

    # O2
    try:
        goal = question_interpreter.interpret(question, profile, llm)
    except question_interpreter.QuestionInterpretationError as exc:
        logger.warning("O2 that bai: %s", exc)
        return {"question": question, "status": "O2_FAILED", "error": str(exc)}

    # O3
    task_results: list[TaskResult] = []
    for task in goal.tasks:
        exec_result = analysis_runner.run_task(task, goal, profile, df, llm)
        task_results.append(TaskResult(task=task, execution=exec_result))

    # O5
    try:
        insight_result = generate_insight(question, task_results, llm)
    except InsightGenerationError as exc:
        logger.warning("O5 that bai: %s", exc)
        return {
            "question": question,
            "status": "O5_FAILED",
            "error": str(exc),
            "n_tasks": len(task_results),
            "n_success": sum(1 for t in task_results if t.execution.success),
        }

    # Chuan bi data_summary de hien thi / dung trong SEVQ prompt
    data_lines = []
    for tr in task_results:
        if tr.execution.success:
            data_lines.append(_format_task_result(tr))
    data_summary = "\n\n".join(data_lines)

    result = {
        "question": question,
        "status": "OK",
        "insight_text": insight_result.insight_text,
        "confidence_score": insight_result.confidence_score,
        "n_tasks": len(task_results),
        "n_success": sum(1 for t in task_results if t.execution.success),
    }

    # SEVQ scoring (tuy chon, ton them 1 LLM call)
    if use_sevq:
        sevq_prompt = SEVQ_PROMPT_TEMPLATE.format(
            question=question,
            insight=insight_result.insight_text,
            data_summary=data_summary,
        )
        try:
            sevq_raw = llm.complete_json(sevq_prompt)
            result["sevq_score"] = sevq_raw.get("score")
            result["sevq_accuracy"] = sevq_raw.get("accuracy")
            result["sevq_relevance"] = sevq_raw.get("relevance")
            result["sevq_clarity"] = sevq_raw.get("clarity")
            result["sevq_rationale"] = sevq_raw.get("rationale", "")
            logger.info("SEVQ score=%s/10 | accuracy=%s relevance=%s clarity=%s",
                        sevq_raw.get("score"), sevq_raw.get("accuracy"),
                        sevq_raw.get("relevance"), sevq_raw.get("clarity"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("SEVQ loi: %s", exc)
            result["sevq_error"] = str(exc)

    logger.info(
        "confidence_score=%.2f | insight: %s...",
        insight_result.confidence_score or 0,
        insight_result.insight_text[:80],
    )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Do chat luong Insight Generator (O5) tren bo cau hoi mau."
    )
    parser.add_argument("--csv", required=True, help="Duong dan toi file CSV (vi du: data/doanh_thu.csv)")
    parser.add_argument("--sevq", action="store_true", help="Chay SEVQ scoring (them 1 LLM call moi cau hoi)")
    parser.add_argument("--out", default=None, help="Luu ket qua ra file CSV (tuy chon)")
    parser.add_argument("--llm", choices=["gemini", "claude"], default="gemini", help="LLM client su dung")
    args = parser.parse_args()

    # Nap du lieu
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error("File khong ton tai: %s", csv_path)
        sys.exit(1)

    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin-1")

    logger.info("Nap du lieu: %d dong x %d cot", len(df), len(df.columns))

    # Khoi tao LLM client
    if args.llm == "gemini":
        from backend.app.llm_client import GeminiClient
        llm = GeminiClient()
    else:
        from backend.app.llm_client import ClaudeClient
        llm = ClaudeClient()

    # Chay tren bo cau hoi mau
    results = []
    for question in SAMPLE_QUESTIONS:
        try:
            r = run_one(question, df, llm, use_sevq=args.sevq)
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            logger.error("Loi khong mong doi cho cau hoi '%s': %s", question, exc)
            results.append({"question": question, "status": "UNEXPECTED_ERROR", "error": str(exc)})

    # Tong hop
    ok_results = [r for r in results if r.get("status") == "OK"]
    avg_confidence = (
        sum(r.get("confidence_score", 0) or 0 for r in ok_results) / len(ok_results)
        if ok_results else 0
    )

    print("\n" + "=" * 60)
    print("KET QUA DO CHAT LUONG INSIGHT GENERATOR (O5)")
    print("=" * 60)
    print(f"Tong so cau hoi: {len(results)}")
    print(f"Thanh cong: {len(ok_results)}/{len(results)}")
    print(f"confidence_score trung binh: {avg_confidence:.2f} / 1.00")
    if args.sevq:
        sevq_scores = [r["sevq_score"] for r in ok_results if r.get("sevq_score") is not None]
        if sevq_scores:
            avg_sevq = sum(sevq_scores) / len(sevq_scores)
            print(f"SEVQ score trung binh: {avg_sevq:.1f} / 10")
            print(f"  (Nguong chap nhan SRS muc 8: >= 7/10)")
    print("=" * 60)

    for r in results:
        status = r.get("status", "?")
        q = r.get("question", "?")[:55]
        conf = r.get("confidence_score")
        conf_str = f"{conf:.2f}" if conf is not None else "N/A"
        sevq_str = ""
        if args.sevq and r.get("sevq_score"):
            sevq_str = f" | SEVQ={r['sevq_score']}/10"
        print(f"  [{status}] conf={conf_str}{sevq_str} | {q}...")

    # Luu CSV neu co yeu cau
    if args.out:
        out_path = Path(args.out)
        if results:
            keys = list(results[0].keys())
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)
        logger.info("Da luu ket qua ra: %s", out_path)


if __name__ == "__main__":
    main()
