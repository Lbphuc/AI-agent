"""Module O4 — Chart Generator.

Chuyển kết quả tính toán (ExecutionResult, từ O3b) thành ChartSpec để
frontend render bằng Plotly/Recharts.

KHÔNG gọi LLM — tại bước này, loại phân tích (trend/comparison/...) đã
được O2 xác định rõ và số liệu đã được O3 tính sẵn, nên chỉ cần một
ánh xạ tất định (deterministic mapping): "trend" -> line chart,
"comparison" -> bar chart... Khác với VISGENERATOR của LIDA (vốn dùng
LLM để hỗ trợ NHIỀU ngữ pháp trực quan hóa bất kỳ), ở đây phạm vi biểu
đồ được giới hạn có chủ đích (2 loại: line, bar) nên rule-based nhanh
hơn, rẻ hơn và không có rủi ro LLM chọn sai loại biểu đồ.

Cài đặt dự kiến ở Tuần 5 — xem docs/SRS.md (FR-07).
"""
from __future__ import annotations

from ..schemas import AnalysisTask, ChartSpec, ExecutionResult

TASK_TYPE_TO_CHART = {
    "trend": "line",
    "comparison": "bar",
    "growth_rate": "bar",
}


def generate_charts(
    tasks: list[AnalysisTask], execution: ExecutionResult
) -> list[ChartSpec]:
    """Sinh danh sách ChartSpec từ kết quả tính toán.

    Raises:
        NotImplementedError: chưa cài đặt (dự kiến Tuần 5).
    """
    raise NotImplementedError(
        "Chart Generator se duoc cai dat o Tuan 5 - can hoan thien "
        "ExecutionResult truoc (xem docs/SRS.md FR-07)."
    )
