"""Script tien ich chay nhanh Module 1 (Data Profiler - Stage 1 & Stage 2) tu Terminal.

Ho tro chay tu ca 2 thu muc:
  1) C:\\IT\\Do an
  2) C:\\IT\\Do an\\ai-agent-bi
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Ho tro import backend du dung o C:\IT\Do an hay C:\IT\Do an\ai-agent-bi
if os.path.exists("ai-agent-bi"):
    sys.path.insert(0, os.path.abspath("ai-agent-bi"))
else:
    sys.path.insert(0, os.path.abspath("."))

import pandas as pd
from backend.app.modules.data_profiler import profile, enrich
from backend.app.modules import (
    question_interpreter,
    analysis_runner,
    chart_generator,
    insight_generator,
)
from backend.app.schemas import TaskResult
from backend.app.llm_client import ClaudeClient, GeminiClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chay Module 1 (Data Profiler), Module 2 (Question Interpreter) va Module 3 (Code Generator & Sandbox) tren file CSV/Excel."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="amazon.csv" if os.path.exists("amazon.csv") else "data/samples/doanh_thu.csv",
        help="Duong dan den file CSV hoac Excel (.xlsx)",
    )
    parser.add_argument(
        "--question",
        "-q",
        type=str,
        default=None,
        help="Dat cau hoi phan tich de chay Module 2 (Question Interpreter).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Luu ket qua JSON vao file nay.",
    )
    parser.add_argument(
        "--samples",
        "-n",
        type=int,
        default=3,
        help="So luong mau lay cho moi cot (mac dinh: 3).",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Bat Stage 2 cua Module 1: Lam giau ngu nghia bang LLM.",
    )
    parser.add_argument(
        "--llm",
        choices=["gemini", "claude"],
        default="gemini",
        help="Loai LLM client: gemini (mac dinh) hoac claude.",
    )
    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Bo qua Module 3 (chi dung lai sau khi sinh AnalysisGoal o Module 2).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API Key (neu khong truyen, se tu doc file .env hoac bien moi truong).",
    )

    args = parser.parse_args()

    # Tu dong do duong dan file neu nguoi dung go amazon.csv hoac ..\amazon.csv
    csv_path = args.csv_path
    if not os.path.exists(csv_path):
        candidates = [
            os.path.join("..", csv_path),
            os.path.join("ai-agent-bi", csv_path),
            os.path.join("ai-agent-bi", "data", "samples", csv_path),
        ]
        for c in candidates:
            if os.path.exists(c):
                csv_path = c
                break

    if not os.path.exists(csv_path):
        print(f"[LOI] Khong tim thay file du lieu: {args.csv_path}")
        sys.exit(1)

    print(f"--> Dang doc file: {csv_path} ...")
    ext = os.path.splitext(csv_path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(csv_path)
        else:
            df = None
            last_err = None
            for enc in ["utf-8-sig", "utf-8", "cp1258", "latin-1"]:
                try:
                    df = pd.read_csv(csv_path, encoding=enc, sep=None, engine="python")
                    break
                except Exception as e:
                    last_err = e
            if df is None:
                raise last_err or Exception("Khong doc duoc file CSV.")
    except Exception as exc:
        print(f"[LOI] Khong the doc file: {exc}")
        sys.exit(1)

    print(f"--> Kich thuoc du lieu: {df.shape[0]} dong, {df.shape[1]} cot.")
    print("--> Dang chay Module 1 (Data Profiler - Stage 0 + Stage 1)...")
    profile_result = profile(df, n_samples=args.samples)

    # Khoi tao LLM neu can chay enrich hoac question
    llm = None
    if args.enrich or args.question:
        try:
            if args.llm == "gemini":
                key = args.api_key or os.environ.get("GEMINI_API_KEY")
                if not key:
                    print("[CANH BAO] Chua co GEMINI_API_KEY! Hay truyen qua --api-key hoac kiem tra file .env.")
                llm = GeminiClient(api_key=key)
            else:
                key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
                if not key:
                    print("[CANH BAO] Chua co ANTHROPIC_API_KEY! Hay truyen qua --api-key hoac kiem tra file .env.")
                llm = ClaudeClient(api_key=key)
        except Exception as e:
            print(f"[LOI Khoi tao LLM] {e}")

    if args.enrich and llm:
        print(f"--> Dang chay Module 1 - Stage 2 (Enrichment voi {args.llm.upper()})...")
        try:
            profile_result = enrich(profile_result, llm=llm)
            if profile_result.dataset_description:
                print("--> [THANH CONG] Stage 2 da sinh mo ta ngu nghia!")
            else:
                print("--> [Luu y] Stage 2 khong sinh duoc mo ta. Giu nguyen Stage 1.")
        except Exception as e:
            print(f"[LOI Stage 2] {e}")

    goal_result = None
    if args.question:
        if not llm:
            print("[LOI] Module 2 bat buoc can LLM de hieu cau hoi. Vui long kiem tra API key.")
        else:
            print(f"\n--> Dang chay Module 2 (Question Interpreter) voi {args.llm.upper()}...")
            print(f"    Cau hoi: \"{args.question}\"")
            try:
                goal_result = question_interpreter.interpret(
                    question=args.question,
                    profile=profile_result,
                    llm=llm,
                )
                print("--> [THANH CONG] Module 2 da phan tich cau hoi thanh AnalysisGoal!")
            except question_interpreter.QuestionInterpretationError as e:
                print(f"[LOI Module 2 - Cau hoi khong hop le] {e}")
            except Exception as e:
                print(f"[LOI Module 2] {e}")

    # Chay Module 3 (Code Generator + Sandbox Executor) neu co AnalysisGoal
    task_results = []
    charts = []
    insight_result = None

    if goal_result and llm and not args.skip_execution:
        print("\n--> Dang chay Module 3 (Code Generator + Sandbox Executor)...")
        for idx, task in enumerate(goal_result.tasks, 1):
            print(f"\n[Task {idx}/{len(goal_result.tasks)}] Dang phan tich dang: {task.type} (metric: {task.metric}, group_by: {task.group_by}) ...")
            try:
                exec_res = analysis_runner.run_task(
                    task=task,
                    goal=goal_result,
                    profile=profile_result,
                    df=df,
                    llm=llm,
                )
                task_result = TaskResult(task=task, execution=exec_res)
                task_results.append(task_result)
                if exec_res.success:
                    print(f"--> [THANH CONG] Thuc thi xong trong sandbox sau {exec_res.attempts} lan thu!")
                    if exec_res.code:
                        print("--> Ma nguon Python do LLM sinh ra:")
                        for line in exec_res.code.strip().splitlines():
                            print(f"    {line}")
                    print("--> Ket qua tinh toan:")
                    if isinstance(exec_res.results, list):
                        for row in exec_res.results[:5]:
                            print(f"    {row}")
                        if len(exec_res.results) > 5:
                            print(f"    ... va {len(exec_res.results) - 5} dong khac.")
                    else:
                        print(f"    {exec_res.results}")
                else:
                    print(f"--> [THAT BAI] Sandbox bao loi sau {exec_res.attempts} lan thu: {exec_res.error}")
            except Exception as exc:
                print(f"--> [LOI Module 3] {exc}")

        # Chay Module 4 (Chart Generator - rule-based)
        if task_results:
            print("\n--> Dang chay Module 4 (Chart Generator - rule-based, khong goi LLM)...")
            try:
                charts = chart_generator.generate_charts(task_results)
                print(f"--> [THANH CONG] Da sinh {len(charts)} bieu do:")
                for c in charts:
                    hl = f" | Noi bat: {c.highlight_x}" if c.highlight_x else ""
                    print(f"    - [{c.chart_type.upper()}] \"{c.title}\" ({len(c.x)} diem x, {len(c.series)} series{hl})")
            except Exception as exc:
                print(f"--> [LOI Module 4] {exc}")

        # Chay Module 5 (Insight Generator voi LLM)
        if task_results:
            print(f"\n--> Dang chay Module 5 (Insight Generator voi {args.llm.upper()})...")
            try:
                insight_result = insight_generator.generate_insight(
                    question=args.question,
                    task_results=task_results,
                    llm=llm,
                )
                print(f"--> [THANH CONG] Da sinh Insight (Do tin cay: {insight_result.confidence_score:.2f}):")
                print("----------------------------------------------------------------------")
                print(insight_result.insight_text)
                print("----------------------------------------------------------------------")
            except insight_generator.InsightGenerationError as exc:
                print(f"--> [CANH BAO Module 5] Khong sinh duoc insight: {exc}")
            except Exception as exc:
                print(f"--> [LOI Module 5] {exc}")

    # Chuan bi du lieu xuat ra
    if goal_result:
        output_payload = {
            "module_1_profile": profile_result.model_dump(),
            "module_2_goal": goal_result.model_dump(),
        }
        if task_results:
            output_payload["module_3_task_results"] = [tr.model_dump() for tr in task_results]
        if charts:
            output_payload["module_4_charts"] = [c.model_dump() for c in charts]
        if insight_result:
            output_payload["module_5_insight"] = insight_result.model_dump()
        json_str = json.dumps(output_payload, ensure_ascii=False, indent=2)
    else:
        json_str = profile_result.model_dump_json(indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\n--> [THANH CONG] Da luu ket qua vao: {args.output}")
    else:
        try:
            if goal_result:
                print("\n=== KET QUA MODULE 2 (AnalysisGoal) ===")
                print(goal_result.model_dump_json(indent=2))
                print("\n=== TONG QUAN MODULE 1 (DataProfile) ===")
                print(f"- So dong: {profile_result.row_count}")
                print(f"- Cot thoi gian: {profile_result.time_column} ({profile_result.time_min} den {profile_result.time_max})")
                print(f"- Cot nhom: {profile_result.group_columns}")
                print(f"- Cot so: {profile_result.numeric_columns}")
            else:
                print("\n=== KET QUA PROFILE (JSON) ===")
                print(json_str)
        except UnicodeEncodeError:
            default_out = "profile_output.json"
            with open(default_out, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(
                f"[Luu y] Terminal Windows khong ho tro in truc tiep ky tu dac biet. "
                f"Ket qua da duoc luu vao: {default_out}"
            )


if __name__ == "__main__":
    main()
