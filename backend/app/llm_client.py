"""LLM client dùng chung cho các module cần gọi Claude API.

Tách ra file riêng từ Tuần 3 vì lúc đầu (Tuần 1-2) chỉ O1 (Stage 2 làm
giàu) cần đến LLMClient/ClaudeClient. Từ Tuần 3, O2 (Question
Interpreter) cũng cần — nếu tiếp tục định nghĩa riêng trong từng file
sẽ trùng lặp code và dễ lệch nhau khi sửa (ví dụ đổi model mặc định).
Các module khác cần LLM sau này (O3a, O5) cũng import từ đây.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

try:
    from dotenv import load_dotenv

    # Luon nap file .env tai goc du an (ai-agent-bi/.env) bat ke terminal dung o dau
    # override=True: luon dung gia tri trong .env, khong bi key cu trong os.environ che
    _project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_project_env, override=True)
    load_dotenv(override=True)
except ImportError:
    pass


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
        """Gui prompt, tra ve dict da parse san tu JSON do LLM sinh ra.

        Cai dat cu the (ClaudeClient ben duoi) chiu trach nhiem parse
        JSON; code goi no chi lam viec voi dict thuan Python.
        """
        ...

    def complete_text(self, prompt: str) -> str:
        """Gui prompt, tra ve plain text (khong ep JSON).

        Dung cho O5 (Insight Generator) — dau ra la van ban nguoi dung
        doc truc tiep, bat LLM boc trong JSON chi them rui ro parse loi
        ma khong duoc loi gi. Cac module can JSON co cau truc van dung
        complete_json().
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

    def complete_text(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()


class GeminiClient:
    """Cài đặt LLMClient dùng Gemini API (Google GenAI SDK).

    Model mặc định: gemini-2.0-flash — ổn định, tốc độ cao, hỗ trợ JSON.
    Fallback models được thử theo thứ tự nếu model chính bị 503.
    `api_key=None`: SDK tự đọc biến môi trường GEMINI_API_KEY.
    """

    # Thử lần lượt các model nếu model trước bị 503/overload.
    # Chỉ liệt kê models có RPD > 0 theo rate limits của key này.
    _FALLBACK_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-3.6-flash",   # thêm vào cuối (Google đề xuất trong log)
    ]

    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: str | None = None,
    ):
        import os
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=key)
        self._model = model


    def complete_json(self, prompt: str) -> dict:
        import logging
        import re
        import time
        from google.genai import types

        _logger = logging.getLogger(__name__)

        # Thử primary model trước, sau đó fallback models nếu gặp 503
        models_to_try = [self._model] + [
            m for m in self._FALLBACK_MODELS if m != self._model
        ]
        last_exc: Exception | None = None

        for model in models_to_try:
            model_succeeded = False
            # Thử tối đa 2 lần cho mỗi model nếu gặp lỗi quá tải tạm thời (503)
            for attempt in range(2):
                try:
                    _logger.info("Đang gọi Gemini model: %s (lần %d)", model, attempt + 1)
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                        ),
                    )

                    # Kiểm tra finish_reason trước khi đọc text
                    if response.candidates:
                        candidate = response.candidates[0]
                        finish_reason = getattr(candidate, "finish_reason", None)
                        if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "1"):
                            _logger.warning("Gemini finish_reason=%s — thử lại không ép JSON MIME", finish_reason)
                            fallback_resp = self._client.models.generate_content(
                                model=model, contents=prompt,
                            )
                            text = getattr(fallback_resp, "text", None) or ""
                            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
                            if match:
                                text = match.group(1)
                            return json.loads(text)

                    text = response.text
                    if text is None:
                        raise json.JSONDecodeError("Gemini trả về response rỗng (text=None)", "", 0)

                    return json.loads(text)

                except Exception as exc:
                    err_str = str(exc)
                    last_exc = exc
                    # Nếu là lỗi quá tải máy chủ Google (503/UNAVAILABLE) và là lần thử đầu: đợi 2s
                    if any(code in err_str for code in ("503", "UNAVAILABLE", "overloaded")) and attempt == 0:
                        _logger.warning("Model %s gặp 503 (quá tải tạm thời). Đợi 2s thử lại...", model)
                        time.sleep(2.0)
                        continue

                    # Bỏ qua model và chuyển model tiếp theo nếu gặp mã lỗi hạ tầng
                    skip_codes = ("503", "UNAVAILABLE", "overloaded", "404", "NOT_FOUND", "429", "RATE")
                    if any(code in err_str for code in skip_codes):
                        _logger.warning("Model %s lỗi %s, chuyển sang model tiếp theo...", model, err_str[:60])
                        time.sleep(1.0)
                        break
                    raise  # Lỗi khác (auth 400, ...) → raise ngay


        # Tat ca models deu 503
        raise Exception(
            f"Tat ca Gemini models deu khong kha dung (503). "
            f"Loi cuoi: {last_exc}"
        )

    def complete_text(self, prompt: str) -> str:
        """Gui prompt, tra ve plain text (khong ep JSON MIME).

        Dung cho O5 — van ban ngan, khong can JSON. Fallback model giong
        complete_json() nhung dung text/plain thay vi application/json.
        """
        import logging
        import time

        _logger = logging.getLogger(__name__)
        models_to_try = [self._model] + [
            m for m in self._FALLBACK_MODELS if m != self._model
        ]
        last_exc: Exception | None = None

        for model in models_to_try:
            for attempt in range(2):
                try:
                    _logger.info("complete_text: Gemini model=%s attempt=%d", model, attempt + 1)
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    text = getattr(response, "text", None)
                    if text is None:
                        raise ValueError("Gemini tra ve text=None")
                    return text.strip()
                except Exception as exc:
                    err_str = str(exc)
                    last_exc = exc
                    if any(c in err_str for c in ("503", "UNAVAILABLE", "overloaded")) and attempt == 0:
                        _logger.warning("complete_text: model %s gap 503, doi 2s...", model)
                        time.sleep(2.0)
                        continue
                    skip_codes = ("503", "UNAVAILABLE", "overloaded", "404", "NOT_FOUND", "429", "RATE")
                    if any(c in err_str for c in skip_codes):
                        _logger.warning("complete_text: model %s loi, thu model khac...", model)
                        time.sleep(1.0)
                        break
                    raise

        raise Exception(
            f"complete_text: tat ca models khong kha dung. Loi cuoi: {last_exc}"
        )

