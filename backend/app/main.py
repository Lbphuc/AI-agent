"""AI Agent - Phân tích & Trực quan hóa Dữ liệu Kinh doanh.

Điểm khởi đầu ứng dụng FastAPI. Ở Tuần 1, chỉ có endpoint /health và
/profile (chạy module O1). Endpoint /analyze (ghép đủ 5 module) sẽ
hoàn thiện dần từ Tuần 3 đến Tuần 6, theo đúng kế hoạch trong
docs/../PROJECT_PROPOSAL (mục 7).
"""
from __future__ import annotations

import io

import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile

from .modules import data_profiler
from .schemas import DataProfile

app = FastAPI(
    title="AI Agent Phan Tich Du Lieu Kinh Doanh",
    description="Dua tren kien truc pipeline lay cam hung tu LIDA (Dibia, 2023).",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/profile", response_model=DataProfile)
async def profile_csv(file: UploadFile = File(...)) -> DataProfile:
    """Endpoint tạm thời: chỉ chạy Data Profiler (O1) trên file CSV tải lên.

    Dùng để kiểm thử/demo module O1 độc lập trước khi pipeline đầy đủ
    (O2-O5) sẵn sàng.
    """
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
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
