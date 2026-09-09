"""Module O5 — Insight Generator.

Nhận câu hỏi gốc + số liệu ĐÃ TÍNH SẴN (ExecutionResult, từ O3b), viết
nhận xét (insight) bằng ngôn ngữ tự nhiên tiếng Việt, trả lời trực
tiếp câu hỏi người dùng.

BẮT BUỘC gọi API LLM (Claude) — đây thuần là bài toán sinh ngôn ngữ tự
nhiên (NLG), không thể viết bằng luật cố định.

NGUYÊN TẮC QUAN TRỌNG (để giảm hallucination số liệu): chỉ đưa SỐ LIỆU
ĐÃ TÍNH (dict kết quả từ O3b) vào prompt, KHÔNG đưa dữ liệu thô
(DataFrame) — LLM chỉ được diễn giải số liệu có sẵn, không được tự suy
luận hoặc tính toán số mới.

Sau khi sinh, nên tự chấm điểm chất lượng nhận xét (confidence_score)
theo tinh thần SEVQ của LIDA (Dibia, 2023) trước khi trả về người dùng
— xem docs/SRS.md, tiêu chí nghiệm thu "Insight Relevance".

Cài đặt dự kiến ở Tuần 6 — xem docs/SRS.md (FR-08).
"""
from __future__ import annotations

from ..schemas import ExecutionResult, InsightResult


def generate_insight(question: str, execution: ExecutionResult) -> InsightResult:
    """Sinh nhận xét ngôn ngữ tự nhiên từ số liệu đã tính.

    Raises:
        NotImplementedError: chưa cài đặt (dự kiến Tuần 6).
    """
    raise NotImplementedError(
        "Insight Generator se duoc cai dat o Tuan 6 - can thiet ke "
        "prompt + co che tu danh gia chat luong (xem docs/SRS.md FR-08)."
    )
