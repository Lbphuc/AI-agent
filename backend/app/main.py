"""AI Agent - Phân tích & Trực quan hóa Dữ liệu Kinh doanh.

Điểm khởi đầu ứng dụng FastAPI. Tuần 1-2: /health, /profile (chạy O1).
Tuần 3: thêm /interpret (chạy O1 + O2), /profile-many (nhiều file).
Tuần 3 (bổ sung): hỗ trợ Excel (.xlsx) + fallback encoding CSV + Stage 0
làm sạch dữ liệu trong O1 (xem FR-12, ARCHITECTURE.md mục 6).
Endpoint /analyze (ghép đủ 5 module) sẽ hoàn thiện dần đến Tuần 6 —
xem kế hoạch chi tiết tại docs/SRS.md (mục 3) và docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Optional

# Dam bao terminal Windows khong bi loi charmap khi in log/ky tu dac biet
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .llm_client import GeminiClient
from .modules import (
    analysis_runner,
    analytics,
    chart_generator,
    data_profiler,
    excel_exporter,
    insight_generator,
    perspective_planner,
    question_interpreter,
    chart_rules,
    chart_fitness,
)
from .modules.business_terms import resolve_column_display
from .schemas import (
    AnalysisGoal,
    AnalysisLevel,
    AnalysisMode,
    AnalyzeResponse,
    ChartSpec,
    ChartType,
    ChartVerdict,
    DataProfile,
    DeepenResponse,
    ExportXlsxRequest,
    InterpretResponse,
    ModeAvailability,
    Reason,
    ReportMeta,
    TaskResult,
)

logger = logging.getLogger(__name__)


def _parse_ack(ack_input: str | None) -> set[str]:
    """Parse chuoi ack tu client thanh tap hop cac ma ly do da xac nhan."""
    if not ack_input:
        return set()
    s = ack_input.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            items = json.loads(s)
            return {str(x) for x in items}
        except Exception:
            pass
    return {x.strip() for x in s.split(",") if x.strip()}


def _parse_chart_prefs(chart_pref: Optional[ChartType], chart_prefs: Optional[str]) -> list[ChartType]:
    """Parse ca chart_pref don le va chart_prefs danh sach tu client."""
    res: list[ChartType] = []
    if chart_prefs:
        s = chart_prefs.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                items = json.loads(s)
                if isinstance(items, list):
                    for x in items:
                        if x in chart_fitness.CHART_DISPLAY_NAMES and x not in res:
                            res.append(x)
            except Exception:
                pass
        if not res:
            for item in s.split(","):
                item_s = item.strip()
                if item_s in chart_fitness.CHART_DISPLAY_NAMES and item_s not in res:
                    res.append(item_s)  # type: ignore[arg-type]
    if chart_pref and chart_pref in chart_fitness.CHART_DISPLAY_NAMES and chart_pref not in res:
        res.insert(0, chart_pref)
    return res


FEATURE_DEEPEN: set[str] = {
    s.strip()
    for s in os.environ.get("FEATURE_DEEPEN", "diagnostic,forecast,prescriptive").split(",")
    if s.strip()
}

app = FastAPI(
    title="AI Agent Phan Tich Du Lieu Kinh Doanh",
    description="Dua tren kien truc pipeline lay cam hung tu LIDA (Dibia, 2023).",
    version="0.1.0",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    """Bắt mọi ngoại lệ chưa được xử lý để trả về JSON chi tiết thay vì 500 câm."""
    logger.exception("Lỗi không mong muốn trong server: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Lỗi hệ thống ({type(exc).__name__}): {str(exc)}"},
    )


# Them som tu Tuan 2 de tranh chan tich hop frontend (React) o Tuan 7.
# TODO (truoc khi trien khai that): gioi han allow_origins ve dung domain
# frontend thuc te thay vi "*" - hien tai de rong cho tien phat trien/demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phuc vu static assets cua React frontend khi da build (trong Docker hoac npm run build)
_dist_assets = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "assets"
if _dist_assets.exists():
    app.mount("/assets", StaticFiles(directory=_dist_assets), name="assets")

# Danh sach encoding thu theo thu tu uu tien cao→thap (FR-12).
# utf-8-sig: UTF-8 kem BOM (Excel Windows thuong xuat dinh dang nay).
# cp1258: code page Viet Nam Windows, pho bien voi file CSV xuat tu
#   phan mem ke toan/ERP noi dia.
# windows-1252: Western European Windows / Excel CSV.
# latin-1: fallback cuoi cung - doc duoc moi byte, nhung co the hien sai
#   dau tieng Viet; doi voi file khong co dau, ket qua giong UTF-8.
_CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp1258", "windows-1252", "latin-1"]


def _read_excel(content: bytes, ext: str) -> pd.DataFrame:
    """Doc file Excel (.xlsx/.xls), raise HTTPException(400) neu loi.

    Luu y: .xls (dinh dang cu, truoc Excel 2007) can them thu vien
    xlrd>=2.0. Hien tai chi ho tro .xlsx (openpyxl). Neu gap .xls,
    HTTPException se bao ro de nguoi dung chuyen doi sang .xlsx.
    """
    try:
        return pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        msg = (
            f"Khong doc duoc file Excel ({exc.__class__.__name__}). "
        )
        if ext == ".xls":
            msg += (
                "Dinh dang .xls (Excel 97-2003) chua duoc ho tro. "
                "Vui long mo file trong Excel va luu lai dang .xlsx."
            )
        else:
            msg += "Kiem tra file co bi hong hoac dat mat khau khong."
        raise HTTPException(status_code=400, detail=msg) from exc


def _read_csv_with_fallback(content: bytes) -> pd.DataFrame:
    """Doc CSV voi fallback qua nhieu encoding va tu phat hien dau phan cach.

    Uu tien C engine mac dinh de doc file sieu nhanh. Neu gap loi phan
    cach (vi du file dung dau cham phay ';' hoac tab), fallback qua
    Python engine voi sep=None de tu phat hien.
    """
    # 1. Thu nhanh bang C engine mac dinh (sep=',')
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=encoding)
        except Exception:
            continue

    # 2. Fallback qua Python engine de tu dong do dau phan cach (; hoac tab)
    last_error: Exception | None = None
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(
                io.BytesIO(content),
                encoding=encoding,
                sep=None,
                engine="python",
            )
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_error = exc
            continue
    raise HTTPException(
        status_code=400,
        detail=(
            "Khong doc duoc file CSV voi cac bang ma pho bien "
            "(UTF-8, cp1258, latin-1). "
            "Vui long luu lai file dang CSV UTF-8 hoac doi sang .xlsx."
        ),
    ) from last_error


async def _read_uploaded_file(file: UploadFile) -> pd.DataFrame:
    """Doc file CSV hoac Excel tai len, tra HTTPException(400) neu loi.

    Doi ten tu _read_csv_upload (Tuan 1-2) sang _read_uploaded_file
    (Tuan 3 bo sung) vi gio ho tro nhieu dinh dang: .csv, .xlsx, .xls.
    Ca /profile, /interpret, /profile-many deu dung ham nay — sua 1
    cho, ca he thong duoc loi (DRY).

    Phan loai theo duoi file:
    - .xlsx / .xls  → _read_excel()
    - Con lai (ke ca .csv, .txt, .tsv) → _read_csv_with_fallback()
      (khong chan cung theo duoi de tranh bi loi voi file dat ten sai
      chinh ta nhung noi dung van la CSV hop le)

    Raises:
        HTTPException(400): file rong, khong doc duoc, hoac DataFrame
            rong sau khi doc thanh cong.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File rong hoac khong doc duoc.")

    ext = Path(file.filename or "").suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = _read_excel(content, ext)
    else:
        df = _read_csv_with_fallback(content)

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="File khong co du lieu (chi co header hoac toan o trong).",
        )
    # Áp dụng làm sạch Stage 0 cho toàn bộ pipeline
    df = data_profiler._clean(df)
    return df


@app.get("/", include_in_schema=False, response_model=None)
def root() -> Response:
    """Tra ve React frontend neu da build (dist), hoac Web Demo preview_charts.html."""
    dist_index = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index, media_type="text/html")
    html_path = Path(__file__).resolve().parent.parent.parent / "tools" / "preview_charts.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return RedirectResponse(url="/docs")


@app.get("/demo", include_in_schema=False, response_class=FileResponse)
def demo() -> FileResponse:
    """Endpoint Web Demo truc quan: http://localhost:8000/demo."""
    html_path = Path(__file__).resolve().parent.parent.parent / "tools" / "preview_charts.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Khong tim thay file tools/preview_charts.html")
    return FileResponse(html_path, media_type="text/html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/debug-llm")
def debug_llm() -> dict:
    """Kiểm tra API key và thử gọi LLM — dùng để debug khi /interpret bị lỗi."""
    import os
    key = os.environ.get("GEMINI_API_KEY", "")
    result = {
        "key_loaded": bool(key),
        "key_prefix": key[:12] + "..." if key else "(trống)",
        "models_tried": [],
    }
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        for model in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.6-flash"]:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents="Say OK",
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                result["models_tried"].append({"model": model, "status": "OK", "text": str(resp.text)[:30]})
                result["working_model"] = model
                break
            except Exception as e:
                result["models_tried"].append({"model": model, "status": "ERROR", "error": str(e)[:80]})
    except Exception as e:
        result["init_error"] = str(e)
    return result


@app.post("/profile", response_model=DataProfile)
@app.post("/api/profile", response_model=DataProfile, include_in_schema=False)
async def profile_csv(file: UploadFile = File(...)) -> DataProfile:
    """Chay Data Profiler (O1 — Stage 1 + Stage 0 lam sach) tren file tai len.

    Ho tro: .csv (UTF-8, cp1258, dau phay/cham phay), .xlsx.
    Dung de kiem thu/demo module O1 doc lap truoc khi pipeline day du
    (O2-O5) san sang.
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)
    avail, freq, n_per = analytics.compute_availability(df, profile)
    profile.availability = avail
    profile.frequency = freq
    profile.n_periods = n_per
    profile.chart_catalog = chart_rules.build_chart_catalog(profile)
    return profile


@app.post("/profile-many")
async def profile_many(files: list[UploadFile] = File(...)) -> dict[str, DataProfile]:
    """Tra ve DataProfile RIENG BIET cho tung file — KHONG join/lien ket
    gi giua cac file.

    Muc dich: cho phep nguoi dung xem truoc schema cua nhieu file truoc
    khi chon file nao de dat cau hoi phan tich. Viec phan tich cheo
    nhieu bang (join) nam ngoai pham vi MVP — xem docs/SRS.md muc 4
    (Ngoai pham vi).

    Raises:
        HTTPException(400): danh sach file rong.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Can upload it nhat 1 file.")

    result: dict[str, DataProfile] = {}
    for f in files:
        df = await _read_uploaded_file(f)
        prof = data_profiler.profile(df)
        avail, freq, n_per = analytics.compute_availability(df, prof)
        prof.availability = avail
        prof.frequency = freq
        prof.n_periods = n_per
        prof.chart_catalog = chart_rules.build_chart_catalog(prof)
        result[f.filename or "unnamed"] = prof
    return result


@app.post("/interpret", response_model=InterpretResponse)
@app.post("/api/interpret", response_model=InterpretResponse, include_in_schema=False)
async def interpret_question(
    file: UploadFile = File(...),
    question: str = Form(...),
    mode: AnalysisMode = Form("auto"),
    chart_pref: Optional[ChartType] = Form(None),
    chart_prefs: Optional[str] = Form(None),
    ack: Optional[str] = Form(None),
) -> InterpretResponse:
    """Endpoint Tuan 3 + Mode Pills: chay O1 + O2 va hop nhat levels theo che do phan tich."""
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)
    avail, freq, n_per = analytics.compute_availability(df, profile)
    profile.availability = avail
    profile.frequency = freq
    profile.n_periods = n_per

    try:
        llm = GeminiClient()
        goal = await run_in_threadpool(
            question_interpreter.interpret, question, profile, llm
        )
    except question_interpreter.QuestionInterpretationError as exc:
        err_msg = str(exc)
        # Phân biệt lỗi hạ tầng (503/network) vs lỗi logic (câu hỏi sai)
        if "503" in err_msg or "UNAVAILABLE" in err_msg or "LLM API" in err_msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Dịch vụ LLM đang quá tải hoặc không khả dụng: {err_msg}. "
                    "Vui lòng thử lại sau vài giây."
                ),
            ) from exc
        raise HTTPException(
            status_code=422,
            detail=(
                f"Không hiểu được câu hỏi: {err_msg} "
                "Vui lòng thử đặt câu hỏi rõ ràng hơn, hoặc nêu rõ "
                "chi nhánh/cột dữ liệu bạn muốn phân tích."
            ),
        ) from exc

    final_levels, notices = analytics.resolve_levels(mode, goal.levels, avail)
    goal_summary = _generate_goal_summary(goal)

    chart_check: Optional[ChartVerdict] = None
    all_prefs = _parse_chart_prefs(chart_pref, chart_prefs)
    if all_prefs:
        # Bieu do do nguoi dung chon duoc ap dung o /analyze (cap descriptive)
        # va o /deepen cua cap trung voi mode da chon -> phai tham dinh ca hai cap
        # de mot lan xac nhan bao phu toan bo luot phan tich.
        check_levels: list[str] = ["descriptive"]
        if mode != "auto" and mode != "descriptive":
            check_levels.append(mode)
        ctx = chart_rules.extract_chart_context(
            profile,
            task=goal.tasks[0] if goal.tasks else None,
            df=df,
        )
        ack_set = _parse_ack(ack)

        merged_reasons: dict[str, Reason] = {}
        merged_alts: list[ChartType] = []
        first_bad: Optional[ChartType] = None
        any_blocked = False
        for lvl in check_levels:
            for p in all_prefs:
                verdict = chart_rules.check_chart_choice(lvl, p, ctx, ack=ack_set)  # type: ignore[arg-type]
                if verdict.status == "ok":
                    continue
                first_bad = first_bad or p
                any_blocked = any_blocked or verdict.status == "blocked"
                for r in verdict.reasons:
                    if r.severity in ("block", "confirm") and r.code not in merged_reasons:
                        merged_reasons[r.code] = r
                for a in verdict.alternatives:
                    if a not in merged_alts and a not in all_prefs:
                        merged_alts.append(a)

        if first_bad is not None:
            chart_check = ChartVerdict(
                status="blocked" if any_blocked else "confirm",
                chart_type=first_bad,
                reasons=list(merged_reasons.values()),
                alternatives=merged_alts,
                requires_double_confirm=any_blocked,
                confirm_step=1,
            )

    return InterpretResponse(
        goal=goal,
        levels=final_levels,
        notices=notices,
        goal_summary=goal_summary,
        chart_check=chart_check,
    )


@app.post("/chart-preview", response_model=list[ChartSpec])
async def chart_preview(
    file: UploadFile = File(...), question: str = Form(...)
) -> list[ChartSpec]:
    """Endpoint demo Tuan 5: chay O1 -> O2 -> O3 -> O4 va tra list[ChartSpec].

    Giu lai sau Tuan 6 de debug tung buoc (khong can insight).
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)
    try:
        llm = GeminiClient()
        goal = await run_in_threadpool(
            question_interpreter.interpret, question, profile, llm
        )
    except question_interpreter.QuestionInterpretationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    task_results: list[TaskResult] = []
    for task in goal.tasks:
        exec_result = await run_in_threadpool(
            analysis_runner.run_task, task, goal, profile, df, llm
        )
        task_results.append(TaskResult(task=task, execution=exec_result))

    charts = chart_generator.generate_charts(task_results)
    return charts


@app.post("/analyze", response_model=AnalyzeResponse)
@app.post("/api/analyze", response_model=AnalyzeResponse, include_in_schema=False)
async def analyze(
    file: UploadFile = File(...),
    question: str = Form(...),
    expand_views: bool = Form(True),
    goal: str | None = Form(None),
    chart_pref: Optional[ChartType] = Form(None),
    chart_prefs: Optional[str] = Form(None),
    ack: Optional[str] = Form(None),
) -> AnalyzeResponse:
    """Endpoint chinh cua he thong (FR-01 den FR-09) — Pipeline end-to-end.

    Nhan them goal tuy chon: neu client da co goal tu /interpret thi kiem tra lai
    va bo qua O2, giam 1 lan goi LLM va do tre.
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)

    # Kiem tra so: khong co cot so -> cham som, tranh O2 xu ly vo nghia
    if not profile.numeric_columns:
        raise HTTPException(
            status_code=422,
            detail="File khong co cot so nao de phan tich.",
        )

    llm = GeminiClient()

    # Neu goal duoc truyen vao -> validate lai voi profile (khong tin tuong mu quang)
    if goal:
        try:
            goal_dict = json.loads(goal) if isinstance(goal, str) else goal
            analysis_goal = question_interpreter.revalidate_goal(goal_dict, profile)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Mục tiêu phân tích (goal) không hợp lệ hoặc tham chiếu cột lạ: {exc}",
            ) from exc
    else:
        try:
            analysis_goal = await run_in_threadpool(
                question_interpreter.interpret, question, profile, llm
            )
        except question_interpreter.QuestionInterpretationError as exc:
            err_msg = str(exc)
            if any(w in err_msg.lower() for w in ("503", "unavailable", "llm api", "429", "resource_exhausted", "quota")):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Dịch vụ AI đang quá tải hoặc tạm thời hết quota: {err_msg}. "
                        "Vui lòng thử lại sau vài giây."
                    ),
                ) from exc
            raise HTTPException(
                status_code=422, detail=f"Không hiểu được câu hỏi: {exc}"
            ) from exc

    # Kiem tra bieu do tuy chon tu nguoi dung (Chart Arbitration)
    confirmed_notes: list[str] = []
    notes_by_pref: dict[str, list[str]] = {}
    all_prefs = _parse_chart_prefs(chart_pref, chart_prefs)
    if all_prefs:
        ctx = chart_rules.extract_chart_context(
            profile,
            task=analysis_goal.tasks[0] if analysis_goal.tasks else None,
            df=df,
        )
        ack_set = _parse_ack(ack)
        for p in all_prefs:
            verdict = chart_rules.check_chart_choice("descriptive", p, ctx, ack=ack_set)
            if verdict.status == "blocked":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(p, p)} cần xác nhận lần 2 trước khi tiếp tục.",
                        "verdict": verdict.model_dump(),
                    },
                )
            if verdict.status == "confirm":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(p, p)} cần xác nhận trước khi tiếp tục.",
                        "verdict": verdict.model_dump(),
                    },
                )
            p_notes = [r.message for r in verdict.reasons if r.severity in ("confirm", "info")]
            if p_notes:
                notes_by_pref[p] = p_notes
                confirmed_notes.extend(p_notes)

    print(f"\n🚀 [1/3] Bắt đầu phân tích: \"{question}\" | Số tác vụ: {len(analysis_goal.tasks)}", flush=True)

    # O3: chay tung task, loi tung phan khong chan nhau
    task_results: list[TaskResult] = []
    for idx, task in enumerate(analysis_goal.tasks, start=1):
        print(f"⚙️ [2/3] O3: Đang sinh mã và chạy sandbox cho task {idx}/{len(analysis_goal.tasks)} ({task.type})...", flush=True)
        exec_result = await run_in_threadpool(
            analysis_runner.run_task, task, analysis_goal, profile, df, llm
        )
        task_results.append(TaskResult(task=task, execution=exec_result))

    # O4: sinh ChartSpec chinh (tat dinh, khong LLM)
    primary_charts = await run_in_threadpool(
        chart_generator.generate_charts,
        task_results,
        chart_prefs=all_prefs,
        level="descriptive",
        profile=profile,
        confirmed_notes=confirmed_notes,
        confirmed_notes_by_pref=notes_by_pref,
    )

    # Perspective Planner: sinh cac goc nhin bo sung (tat dinh, khong LLM)
    supplementary_charts: list[ChartSpec] = []
    if expand_views:
        try:
            df_filtered = analysis_runner.filter_by_time_range(
                df, profile, analysis_goal.time_start, analysis_goal.time_end
            )
            supplementary_charts = await run_in_threadpool(
                perspective_planner.expand,
                analysis_goal,
                profile,
                df_filtered,
                task_results,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Loi khi sinh goc nhin bo sung: %s", exc)

    # Khử trùng lặp giữa primary_charts và supplementary_charts (tránh vẽ lặp 2 lần)
    import re
    seen_titles: set[str] = set()
    primary_has_pie = any(c.chart_type == "pie" for c in primary_charts)
    primary_has_trend = any(
        c.chart_type in ("line", "area") and any(w in c.title.lower() for w in ("diễn biến", "xu hướng"))
        for c in primary_charts
    )
    primary_has_contrib = any(
        "đóng góp" in c.title.lower() or c.perspective == "contribution_to_change"
        for c in primary_charts
    )

    def _clean_title(t: str) -> str:
        return re.sub(r"\s*\(.*?\)\s*$", "", t).strip().lower()

    for c in primary_charts:
        seen_titles.add(_clean_title(c.title))
        seen_titles.add(c.title.strip().lower())

    filtered_supplementary: list[ChartSpec] = []
    for sc in supplementary_charts:
        raw_t = sc.title.strip().lower()
        clean_t = _clean_title(sc.title)
        if raw_t in seen_titles or clean_t in seen_titles:
            continue
        if sc.perspective == "share_of_total" and primary_has_pie:
            continue
        if sc.perspective == "trend_by_group" and primary_has_trend:
            continue
        if sc.perspective == "contribution_to_change" and primary_has_contrib:
            continue
        seen_titles.add(raw_t)
        seen_titles.add(clean_t)
        filtered_supplementary.append(sc)

    charts = primary_charts + filtered_supplementary
    print(f"📊 [3/3] O4: Đã tạo {len(charts)} biểu đồ. Đang viết nhận xét AI (O5)...", flush=True)

    # O5: sinh insight (goi LLM), loi khong chan toan bo response
    insight_result = None
    try:
        insight_result = await run_in_threadpool(
            insight_generator.generate_insight, question, task_results, llm, analysis_goal
        )
    except insight_generator.InsightGenerationError as exc:
        logger.warning("Khong sinh duoc insight: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Loi bat ngo khi sinh insight: %s", exc)

    print("✅ Hoàn tất toàn bộ pipeline mô tả (/analyze)", flush=True)

    # Neu ca charts lan insight deu rong -> khong co gi tra ve -> 422
    if not charts and insight_result is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Khong tinh toan duoc gi tu cau hoi nay. "
                "Kiem tra log server de biet chi tiet loi."
            ),
        )

    rows_total = len(df)
    rows_used = len(df_filtered) if "df_filtered" in locals() and df_filtered is not None else rows_total

    avail_map, _, _ = analytics.compute_availability(df, profile)

    report_notes: list[str] = list(confirmed_notes)
    report_meta = ReportMeta(
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_name=getattr(llm, "model_name", "AI Model"),
        rows_total=rows_total,
        rows_used=rows_used,
        goal_summary=_generate_goal_summary(analysis_goal),
        notes=report_notes,
        deepen=avail_map,
    )

    return AnalyzeResponse(
        goal=analysis_goal,
        task_results=task_results,
        charts=charts,
        insight=insight_result,
        meta=report_meta,
    )


@app.post("/deepen", response_model=DeepenResponse)
@app.post("/api/deepen", response_model=DeepenResponse, include_in_schema=False)
async def deepen_analysis(
    file: UploadFile = File(...),
    goal: str = Form(...),
    level: AnalysisLevel = Form(...),
    chart_pref: Optional[ChartType] = Form(None),
    chart_prefs: Optional[str] = Form(None),
    ack: Optional[str] = Form(None),
) -> DeepenResponse:
    """Endpoint chay phan tich sau theo tung cap: diagnostic | forecast | prescriptive.

    Thuan Python tat dinh, tinh toan nhanh, LLM chi dien giai tren FactSheet.
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)

    try:
        goal_dict = json.loads(goal) if isinstance(goal, str) else goal
        validated_goal = question_interpreter.revalidate_goal(goal_dict, profile)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Mục tiêu phân tích (goal) không hợp lệ hoặc tham chiếu cột lạ: {exc}",
        ) from exc

    if level not in FEATURE_DEEPEN:
        return DeepenResponse(
            level=level,
            sections=[],
            warnings=[f"Cấp phân tích '{level}' đang tạm thời bị vô hiệu hóa."],
        )

    avail_map, _, _ = analytics.compute_availability(df, profile)
    if not avail_map.get(level, ModeAvailability(available=False)).available:
        reason = avail_map.get(level).reason if avail_map.get(level) else "Dữ liệu chưa đủ điều kiện."
        return DeepenResponse(
            level=level,
            sections=[],
            warnings=[reason],
        )

    # Kiem tra chart_prefs cho cap phan tich sau
    confirmed_notes: list[str] = []
    notes_by_pref: dict[str, list[str]] = {}
    all_prefs = _parse_chart_prefs(chart_pref, chart_prefs)
    if all_prefs:
        ctx = chart_rules.extract_chart_context(
            profile,
            task=validated_goal.tasks[0] if validated_goal.tasks else None,
            df=df,
        )
        ack_set = _parse_ack(ack)
        for p in all_prefs:
            verdict = chart_rules.check_chart_choice(level, p, ctx, ack=ack_set)
            if verdict.status == "blocked":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(p, p)} cần xác nhận lần 2 trước khi áp dụng cho cấp {level}.",
                        "verdict": verdict.model_dump(),
                    },
                )
            if verdict.status == "confirm":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(p, p)} cần xác nhận trước khi tiếp tục.",
                        "verdict": verdict.model_dump(),
                    },
                )
            p_notes = [r.message for r in verdict.reasons if r.severity in ("confirm", "info")]
            if p_notes:
                notes_by_pref[p] = p_notes
                confirmed_notes.extend(p_notes)

    print(f"📈 [DEEPEN] Đang tính toán chuyên sâu cấp: {level.upper()}...", flush=True)
    llm = GeminiClient()
    try:
        if level == "diagnostic":
            section, facts = await run_in_threadpool(
                analytics.run_diagnostic, df, profile, validated_goal, llm
            )
            if all_prefs and section.charts:
                base_chart = section.charts[0]
                new_charts = []
                for p in all_prefs:
                    c = base_chart.model_copy(deep=True)
                    c.chart_type = p
                    c.selection = "user"
                    c.data_shape = chart_fitness.CHART_DATA_SHAPE.get(p, "category_series")
                    if len(all_prefs) > 1:
                        c.title = f"{c.title} ({chart_fitness.CHART_DISPLAY_NAMES.get(p, p)})"
                    
                    # Chỉ gán ghi chú liên quan đến biểu đồ này
                    p_notes = notes_by_pref.get(p, [])
                    for n in p_notes:
                        if n not in c.notes:
                            c.notes.append(n)
                    
                    disp = chart_fitness.CHART_DISPLAY_NAMES.get(p, p)
                    if not any(f"Biểu đồ do bạn chọn: {disp}" in n for n in c.notes):
                        c.notes.insert(0, f"Biểu đồ do bạn chọn: {disp}")

                    # Bổ sung cấu trúc dữ liệu đặc thù (heatmap_matrix, box_data, ...)
                    c = chart_generator.enrich_chart_spec(c)
                    new_charts.append(c)
                section.charts = new_charts
            print("✅ [DEEPEN] Hoàn tất chẩn đoán (Diagnostic)", flush=True)
            return DeepenResponse(
                level="diagnostic",
                sections=[section],
                facts=facts,
                warnings=section.warnings,
            )
        elif level == "forecast":
            section, facts = await run_in_threadpool(
                analytics.run_forecast, df, profile, validated_goal, 3, llm
            )
            if all_prefs and section.charts:
                base_chart = section.charts[0]
                new_charts = []
                for p in all_prefs:
                    c = base_chart.model_copy(deep=True)
                    c.chart_type = p
                    c.selection = "user"
                    c.data_shape = chart_fitness.CHART_DATA_SHAPE.get(p, "category_series")
                    if len(all_prefs) > 1:
                        c.title = f"{c.title} ({chart_fitness.CHART_DISPLAY_NAMES.get(p, p)})"
                    
                    p_notes = notes_by_pref.get(p, [])
                    for n in p_notes:
                        if n not in c.notes:
                            c.notes.append(n)
                    
                    disp = chart_fitness.CHART_DISPLAY_NAMES.get(p, p)
                    if not any(f"Biểu đồ do bạn chọn: {disp}" in n for n in c.notes):
                        c.notes.insert(0, f"Biểu đồ do bạn chọn: {disp}")

                    c = chart_generator.enrich_chart_spec(c)
                    new_charts.append(c)
                section.charts = new_charts
            print("✅ [DEEPEN] Hoàn tất dự báo (Forecast)", flush=True)
            return DeepenResponse(
                level="forecast",
                sections=[section],
                facts=facts,
                warnings=section.warnings,
            )
        elif level == "prescriptive":
            resp = await run_in_threadpool(
                analytics.run_prescriptive, df, profile, validated_goal, llm
            )
            print("✅ [DEEPEN] Hoàn tất đề xuất (Prescriptive)", flush=True)
            return resp
        else:
            raise HTTPException(status_code=400, detail=f"Cấp phân tích không hỗ trợ: {level}")
    except Exception as exc:
        logger.exception("Lỗi khi chạy deepen level=%s: %s", level, exc)
        return DeepenResponse(
            level=level,
            sections=[],
            warnings=[f"Đã xảy ra lỗi khi phân tích ({type(exc).__name__}): {exc}"],
        )


@app.post("/render", response_model=ChartSpec)
@app.post("/api/render", response_model=ChartSpec, include_in_schema=False)
async def render_chart(
    file: UploadFile = File(...),
    goal: str = Form(...),
    level: AnalysisLevel = Form("descriptive"),
    chart_type: ChartType = Form(...),
    ack: Optional[str] = Form(None),
) -> ChartSpec:
    """Chuyen doi bieu do sang loai bieu do khac (tat dinh, stateless, khong LLM).

    Dung khi nguoi dung chon doi bieu do khac data_shape tren the bieu do (menu ⋯).
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)

    try:
        goal_dict = json.loads(goal) if isinstance(goal, str) else goal
        validated_goal = question_interpreter.revalidate_goal(goal_dict, profile)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Goal khong hop le: {exc}") from exc

    if not validated_goal.tasks:
        raise HTTPException(status_code=422, detail="Goal khong co task nao.")

    task = validated_goal.tasks[0]
    ctx = chart_rules.extract_chart_context(profile, task=task, df=df)
    ack_set = _parse_ack(ack)
    verdict = chart_rules.check_chart_choice(level, chart_type, ctx, ack=ack_set)

    if verdict.status == "blocked":
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(chart_type, chart_type)} bị chặn cho dữ liệu hoặc chiến lược này.",
                "verdict": verdict.model_dump(),
            },
        )
    if verdict.status == "confirm":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Biểu đồ {chart_fitness.CHART_DISPLAY_NAMES.get(chart_type, chart_type)} cần xác nhận trước khi tiếp tục.",
                "verdict": verdict.model_dump(),
            },
        )

    llm = GeminiClient()
    exec_result = await run_in_threadpool(
        analysis_runner.run_task, task, validated_goal, profile, df, llm
    )
    tr = TaskResult(task=task, execution=exec_result)

    confirmed_notes = [r.message for r in verdict.reasons if r.severity in ("confirm", "info")]
    charts = chart_generator.generate_charts(
        [tr],
        chart_pref=chart_type,
        level=level,
        profile=profile,
        confirmed_notes=confirmed_notes,
    )
    if not charts:
        raise HTTPException(status_code=422, detail="Không thể tạo biểu đồ cho loại đã chọn.")

    return charts[0]


def _generate_goal_summary(goal: AnalysisGoal) -> str:
    """Tạo câu tóm tắt mục tiêu ngắn gọn, tự nhiên cho người dùng.
    Ví dụ: 'So sánh doanh thu giữa các chi nhánh, từ 01/2026 đến 08/2026.'
    """
    first_task = goal.tasks[0] if goal.tasks else None
    metric_raw = first_task.metric if first_task else None
    group_raw = first_task.group_by if first_task else None
    metric_disp, _ = resolve_column_display(metric_raw) if metric_raw else ("", "")
    group_disp, _ = resolve_column_display(group_raw) if group_raw else ("", "")

    parts: list[str] = []
    objective = getattr(goal, "objective", None)
    if objective == "contribution_to_change":
        action = f"Phân tích yếu tố đóng góp lớn nhất vào thay đổi {metric_disp.lower()}"
        if group_disp:
            action += f" theo {group_disp.lower()}"
        parts.append(action)
    elif objective == "top_decliners":
        action = f"Tìm {group_disp.lower() or 'nhóm'} làm giảm / sụt giảm {metric_disp.lower()} nhiều nhất"
        parts.append(action)
    elif objective == "top_growers":
        action = f"Tìm {group_disp.lower() or 'nhóm'} tăng trưởng {metric_disp.lower()} mạnh nhất"
        parts.append(action)
    elif objective == "prescriptive_action":
        action = f"Đề xuất phương án ưu tiên {group_disp.lower() if group_disp else 'nhóm'} để cải thiện {metric_disp.lower()}"
        parts.append(action)
    elif objective == "forecast":
        horizon = getattr(goal, "forecast_horizon", None) or 3
        action = f"Dự báo xu hướng {metric_disp.lower()} trong {horizon} kỳ tiếp theo"
        parts.append(action)
    else:
        task_types = [t.type for t in goal.tasks]
        if "comparison" in task_types:
            action = f"So sánh {metric_disp.lower()}"
            if group_disp:
                action += f" giữa các {group_disp.lower()}"
            parts.append(action)
        elif "trend" in task_types:
            action = f"Theo dõi xu hướng {metric_disp.lower()} theo thời gian"
            if group_disp:
                action += f" của các {group_disp.lower()}"
            parts.append(action)
        elif "growth_rate" in task_types:
            find_mode = "giảm" if (first_task and first_task.find == "min") else "tăng"
            action = f"Tìm {group_disp.lower() or 'nhóm'} {find_mode} mạnh nhất theo {metric_disp.lower()}"
            parts.append(action)
        else:
            parts.append(f"Phân tích {metric_disp.lower()}")

    target = getattr(goal, "target", None)
    if target:
        parts.append(f"tập trung vào {target}")

    if goal.time_start and goal.time_end:
        parts.append(f"từ {goal.time_start} đến {goal.time_end}")
    elif goal.time_start:
        parts.append(f"từ {goal.time_start}")
    elif goal.time_end:
        parts.append(f"đến {goal.time_end}")

    return ", ".join(parts) + "."


@app.post("/export/xlsx")
@app.post("/api/export/xlsx", include_in_schema=False)
async def export_xlsx(request: ExportXlsxRequest) -> Response:
    """Xuất kết quả phân tích sang file Excel (.xlsx) với biểu đồ gốc.
    Nhận AnalyzeResponse + options, trả file đính kèm dưới dạng streaming bytes.
    """
    try:
        xlsx_bytes = await run_in_threadpool(excel_exporter.generate_excel_report, request)
    except Exception as exc:
        logger.error("Lỗi khi sinh file Excel: %s", exc)
        raise HTTPException(status_code=500, detail=f"Không thể tạo file Excel: {exc}") from exc

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"BaoCao_PhanTich_{date_str}"
    quoted_name = quote(f"{base_name}.xlsx")

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{base_name}.xlsx\"; filename*=UTF-8''{quoted_name}"
        },
    )

