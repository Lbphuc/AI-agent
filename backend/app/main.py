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
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

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
    chart_generator,
    data_profiler,
    excel_exporter,
    insight_generator,
    perspective_planner,
    question_interpreter,
)
from .modules.business_terms import resolve_column_display
from .schemas import (
    AnalysisGoal,
    AnalyzeResponse,
    ChartSpec,
    DataProfile,
    ExportXlsxRequest,
    ReportMeta,
    TaskResult,
)

logger = logging.getLogger(__name__)

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
# latin-1: fallback cuoi cung - doc duoc moi byte, nhung co the hien sai
#   dau tieng Viet; doi voi file khong co dau, ket qua giong UTF-8.
_CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp1258", "latin-1"]


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
    return data_profiler.profile(df)


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
        result[f.filename or "unnamed"] = data_profiler.profile(df)
    return result


@app.post("/interpret", response_model=AnalysisGoal)
@app.post("/api/interpret", response_model=AnalysisGoal, include_in_schema=False)
async def interpret_question(
    file: UploadFile = File(...), question: str = Form(...)
) -> AnalysisGoal:
    """Endpoint Tuan 3: chay O1 + O2 (chua chay O3-O5).

    Dung de kiem thu/demo viec phan ra cau hoi thanh muc tieu phan
    tich co cau truc, truoc khi O3 (sinh + thuc thi ma) san sang o
    Tuan 4.

    LLM: GeminiClient (doc API key tu bien moi truong GEMINI_API_KEY
    hoac file .env — xem backend/app/llm_client.py).

    Raises:
        HTTPException(422): cau hoi khong hieu duoc / tham chieu cot
            khong ton tai — xem question_interpreter.QuestionInterpretationError.
    """
    df = await _read_uploaded_file(file)
    profile = await run_in_threadpool(data_profiler.profile, df)
    try:
        llm = GeminiClient()
        return await run_in_threadpool(
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
) -> AnalyzeResponse:
    """Endpoint chinh cua he thong (FR-01 den FR-09) — Pipeline end-to-end.

    Tuan 6: hoan chinh O1 -> O2 -> O3 -> O4 -> O5.
    Tra AnalyzeResponse day du (goal, task_results, charts, insight).

    Xu ly loi tung phan (partial failure):
    - 1 task O3 loi: task do bi bo qua, cac task khac van chay.
    - Insight loi (InsightGenerationError): van tra charts, insight=None.
    - Ca charts lan insight deu rong: 422 (khong co gi tra ve).
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

    try:
        goal = await run_in_threadpool(
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

    # O3: chay tung task, loi tung phan khong chan nhau
    task_results: list[TaskResult] = []
    for task in goal.tasks:
        exec_result = await run_in_threadpool(
            analysis_runner.run_task, task, goal, profile, df, llm
        )
        task_results.append(TaskResult(task=task, execution=exec_result))

    # O4: sinh ChartSpec chinh (tat dinh, khong LLM)
    primary_charts = await run_in_threadpool(chart_generator.generate_charts, task_results)

    # Perspective Planner: sinh cac goc nhin bo sung (tat dinh, khong LLM)
    supplementary_charts: list[ChartSpec] = []
    if expand_views:
        try:
            df_filtered = analysis_runner.filter_by_time_range(
                df, profile, goal.time_start, goal.time_end
            )
            supplementary_charts = await run_in_threadpool(
                perspective_planner.expand,
                goal,
                profile,
                df_filtered,
                task_results,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Loi khi sinh goc nhin bo sung: %s", exc)

    charts = primary_charts + supplementary_charts

    # O5: sinh insight (goi LLM), loi khong chan toan bo response
    insight_result = None
    try:
        insight_result = await run_in_threadpool(
            insight_generator.generate_insight, question, task_results, llm
        )
    except insight_generator.InsightGenerationError as exc:
        logger.warning("Khong sinh duoc insight: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Loi bat ngo khi sinh insight: %s", exc)

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
    report_meta = ReportMeta(
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_name=getattr(llm, "model_name", "AI Model"),
        rows_total=rows_total,
        rows_used=rows_used,
        goal_summary=_generate_goal_summary(goal),
        notes=[],
    )

    return AnalyzeResponse(
        goal=goal,
        task_results=task_results,
        charts=charts,
        insight=insight_result,
        meta=report_meta,
    )


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

