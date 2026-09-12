"""AI Agent - Phân tích & Trực quan hóa Dữ liệu Kinh doanh.

Điểm khởi đầu ứng dụng FastAPI. Ở Tuần 1-2, chỉ có endpoint /health và
/profile (chạy module O1). Endpoint /analyze (ghép đủ 5 module) sẽ
hoàn thiện dần từ Tuần 3 đến Tuần 6 — xem kế hoạch chi tiết tại
docs/SRS.md (mục 3, danh sách FR) và docs/ARCHITECTURE.md (mục 6,
bảng trạng thái từng module).
"""
from __future__ import annotations

import io

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .modules import data_profiler
from .schemas import DataProfile

app = FastAPI(
    title="AI Agent Phan Tich Du Lieu Kinh Doanh",
    description="Dua tren kien truc pipeline lay cam hung tu LIDA (Dibia, 2023).",
    version="0.1.0",
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/profile", response_model=DataProfile)
async def profile_csv(file: UploadFile = File(...)) -> DataProfile:
    """Endpoint tạm thời: chỉ chạy Data Profiler (O1) trên file CSV tải lên.

    Dùng để kiểm thử/demo module O1 độc lập trước khi pipeline đầy đủ
    (O2-O5) sẵn sàng.

    Raises:
        HTTPException(400): file rỗng, không phải CSV hợp lệ, hoặc
            pandas không đọc được — trả thông báo lỗi gọn cho client
            thay vì để lộ traceback thô (NFR-04).
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File rong hoac khong doc duoc.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        # Day la tang bien (API boundary) xu ly input tu nguoi dung ben
        # ngoai - CO CHU DICH bat rong (khac voi enrich() o tang logic
        # noi bo, noi bat rong co the che giau bug that). pandas co the
        # nem nhieu loai loi khac nhau tuy noi dung file loi (ParserError,
        # EmptyDataError, UnicodeDecodeError, ValueError...) - muc tieu
        # o day la KHONG BAO GIO de traceback tho lot ra ngoai cho client.
        raise HTTPException(
            status_code=400,
            detail=f"Khong the doc file CSV: {exc.__class__.__name__}. "
            "Vui long kiem tra dinh dang file (dau phay, ma hoa UTF-8).",
        ) from exc

    if df.empty:
        raise HTTPException(
            status_code=400, detail="File CSV khong co du lieu (chi co header)."
        )

    return data_profiler.profile(df)


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), question: str = Form(...)) -> dict:
    """Endpoint chính của hệ thống (FR-01 đến FR-09).

    TODO (Tuần 3-6): ghép nối đủ 5 module theo đúng luồng mô tả trong
    docs/ARCHITECTURE.md:
        1. data_profiler.profile(df)          -> DataProfile
        2. question_interpreter.interpret(...) -> AnalysisGoal
        3. code_generator.generate(...)        -> CodeGenResult
        4. sandbox_executor.execute(...)       -> ExecutionResult
        5. chart_generator.generate_charts(...) -> list[ChartSpec]
        6. insight_generator.generate_insight(...) -> InsightResult
    Hiện tại trả về placeholder để frontend (Tuần 7) có thể tích hợp
    và kiểm thử giao diện trước khi backend hoàn thiện.
    """
    return {
        "status": "not_implemented",
        "message": "Pipeline day du (O2-O5) se duoc trien khai tu Tuan 3.",
        "question": question,
        "filename": file.filename,
    }
