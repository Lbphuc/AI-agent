"""LLM client dùng chung cho các module cần gọi Claude / Gemini API.

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
    """Interface tối giản cho một LLM client."""

    def complete_json(self, prompt: str) -> dict:
        """Gui prompt, tra ve dict da parse san tu JSON do LLM sinh ra."""
        ...

    def complete_text(self, prompt: str) -> str:
        """Gui prompt, tra ve plain text (khong ep JSON)."""
        ...

    @property
    def model_name(self) -> str:
        """Ten model dang duoc su dung."""
        ...


class ClaudeClient:
    """Cài đặt LLMClient dùng Claude API (Anthropic SDK)."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

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

    Ưu tiên các model Gemini chính thức tốc độ cao, hỗ trợ JSON ổn định.
    Fallback models được thử theo thứ tự nếu model chính bị 503/429/404.
    `api_key=None`: SDK tự đọc biến môi trường GEMINI_API_KEY.
    """

    _FALLBACK_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=key)
        self._model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def model_name(self) -> str:
        return self._model

    def complete_json(self, prompt: str) -> dict:
        import logging
        import re
        import time
        from google.genai import types

        _logger = logging.getLogger(__name__)

        models_to_try = [self._model] + [
            m for m in self._FALLBACK_MODELS if m != self._model
        ]
        last_exc: Exception | None = None

        for model in models_to_try:
            for attempt in range(2):
                try:
                    _logger.info("Đang gọi Gemini model: %s (lần %d)", model, attempt + 1)
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )

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
                            self._model = model
                            return json.loads(text)

                    text = response.text
                    if text is None:
                        raise json.JSONDecodeError("Gemini trả về response rỗng (text=None)", "", 0)

                    self._model = model
                    return json.loads(text)

                except Exception as exc:
                    err_str = str(exc).lower()
                    last_exc = exc
                    transient_errors = ("503", "unavailable", "overloaded", "disconnect", "remoteprotocolerror", "connection", "timeout", "reset")
                    if any(code in err_str for code in transient_errors) and attempt == 0:
                        _logger.warning("Model %s gặp lỗi tạm thời (%s). Đợi 1.0s thử lại...", model, str(exc)[:80])
                        time.sleep(1.0)
                        continue

                    skip_codes = ("503", "unavailable", "overloaded", "404", "not_found", "429", "rate", "resource_exhausted", "quota", "disconnect", "remoteprotocolerror", "connection", "timeout", "reset")
                    if any(code in err_str for code in skip_codes):
                        _logger.warning("Model %s lỗi %s, chuyển sang model tiếp theo...", model, str(exc)[:80])
                        time.sleep(0.2)
                        break
                    raise

        raise Exception(
            f"Tat ca Gemini models deu khong kha dung (503/429/Network). "
            f"Loi cuoi: {last_exc}"
        )

    def complete_text(self, prompt: str) -> str:
        """Gui prompt, tra ve plain text (khong ep JSON MIME)."""
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
                    self._model = model
                    return text.strip()
                except Exception as exc:
                    err_str = str(exc).lower()
                    last_exc = exc
                    transient_errors = ("503", "unavailable", "overloaded", "disconnect", "remoteprotocolerror", "connection", "timeout", "reset")
                    if any(c in err_str for c in transient_errors) and attempt == 0:
                        _logger.warning("complete_text: model %s gap loi tam thoi (%s), doi 1.0s...", model, str(exc)[:80])
                        time.sleep(1.0)
                        continue
                    skip_codes = ("503", "unavailable", "overloaded", "404", "not_found", "429", "rate", "resource_exhausted", "quota", "disconnect", "remoteprotocolerror", "connection", "timeout", "reset")
                    if any(c in err_str for c in skip_codes):
                        _logger.warning("complete_text: model %s loi, thu model khac...", model)
                        time.sleep(0.2)
                        break
                    raise

        raise Exception(
            f"complete_text: tat ca models khong kha dung. Loi cuoi: {last_exc}"
        )
