"""Module O2 — Question Interpreter.

Nhận câu hỏi tự do của người dùng (tiếng Việt) + DataProfile từ O1,
sinh ra một AnalysisGoal có cấu trúc (danh sách AnalysisTask) để O3 có
thể sinh mã phân tích tương ứng.

BẮT BUỘC gọi API LLM (Claude) — đây là bài toán hiểu ngôn ngữ tự do,
không thể phủ hết bằng luật/regex. Áp dụng kỹ thuật few-shot prompting
tương tự GOAL EXPLORER của LIDA (Dibia, 2023): yêu cầu LLM sinh kèm lý
do (rationale) để giảm hallucination và tăng độ liên kết với tên cột
thực tế trong dữ liệu.

Cài đặt dự kiến ở Tuần 3 — xem docs/SRS.md (FR-04) và
docs/ARCHITECTURE.md (đặc tả interface O2).
"""
from __future__ import annotations

from ..schemas import AnalysisGoal, DataProfile


def interpret(question: str, profile: DataProfile) -> AnalysisGoal:
    """Phân rã câu hỏi tự do thành mục tiêu phân tích có cấu trúc.

    Args:
        question: câu hỏi người dùng nhập, ví dụ "Phân tích xu hướng
            doanh thu 12 tháng gần nhất và cho biết chi nhánh nào giảm
            mạnh nhất."
        profile: DataProfile do module O1 sinh ra (cung cấp tên cột
            thời gian/nhóm/số thực tế để LLM tránh hallucination).

    Returns:
        AnalysisGoal — mục tiêu phân tích có cấu trúc.

    Raises:
        NotImplementedError: chưa cài đặt (dự kiến Tuần 3).
    """
    raise NotImplementedError(
        "Question Interpreter se duoc cai dat o Tuan 3 - can thiet ke "
        "prompt few-shot va tich hop Claude API (xem docs/SRS.md FR-04)."
    )
