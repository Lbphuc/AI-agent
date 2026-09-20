"""LLM client dùng chung cho các module cần gọi Claude API.

Tách ra file riêng từ Tuần 3 vì lúc đầu (Tuần 1-2) chỉ O1 (Stage 2 làm
giàu) cần đến LLMClient/ClaudeClient. Từ Tuần 3, O2 (Question
Interpreter) cũng cần — nếu tiếp tục định nghĩa riêng trong từng file
sẽ trùng lặp code và dễ lệch nhau khi sửa (ví dụ đổi model mặc định).
Các module khác cần LLM sau này (O3a, O5) cũng import từ đây.
"""
from __future__ import annotations

import json
from typing import Protocol


class LLMClient(Protocol):
    """Interface tối giản cho một LLM client.

    Định nghĩa dưới dạng Protocol (không phải lớp cụ thể) để:
      1. Logic nghiệp vụ (enrich, interpret, ...) không phụ thuộc trực
         tiếp vào SDK của Anthropic -> dễ kiểm thử bằng client giả lập
         (xem backend/tests), không tốn API call khi chạy CI.
      2. Có thể thay bằng client khác (model rẻ hơn, hoặc nhà cung cấp
         khác) mà không phải sửa logic các module gọi nó.
    """

    def complete_json(self, prompt: str) -> dict:
        """Gửi prompt, trả về dict đã parse sẵn từ JSON do LLM sinh ra.

        Cài đặt cụ thể (ClaudeClient bên dưới) chịu trách nhiệm parse
        JSON; code gọi nó chỉ làm việc với dict thuần Python.
        """
        ...


class ClaudeClient:
    """Cài đặt LLMClient dùng Claude API (Anthropic SDK).

    Model mặc định: claude-sonnet-5 — cân bằng chất lượng suy luận và
    chi phí, phù hợp cho các tác vụ cần suy luận (hiểu câu hỏi, mô tả
    ngữ nghĩa dữ liệu). Với tác vụ đơn giản hơn, có thể cân nhắc
    claude-haiku-4-5-20251001 để giảm chi phí/độ trễ.

    `api_key=None` (mặc định) để SDK tự đọc biến môi trường
    `ANTHROPIC_API_KEY` — không hardcode key trong code.
    """

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        import anthropic  # import cục bộ - tránh bắt buộc cài đặt SDK khi chỉ dùng module khác

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete_json(self, prompt: str) -> dict:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return json.loads(text)
