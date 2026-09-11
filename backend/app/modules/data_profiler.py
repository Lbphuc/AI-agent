"""Module O1 — Data Profiler.

Trích xuất schema, kiểu dữ liệu, thống kê mô tả, và nhận diện cột thời
gian / cột nhóm (định danh) / cột số từ một DataFrame (Stage 1), cộng
thêm một bước làm giàu ngữ nghĩa tùy chọn bằng LLM (Stage 2).

- **Stage 1** (`profile()`): xử lý THUẦN TÚY BẰNG LUẬT (rule-based) —
  không gọi LLM — tương ứng Stage 1 (base summary generation) của
  SUMMARIZER trong LIDA (Dibia, 2023).
- **Stage 2** (`enrich()`): TÙY CHỌN, gọi LLM một lần duy nhất để sinh
  mô tả tổng quan tập dữ liệu + mô tả/kiểu ngữ nghĩa cho từng cột —
  tương ứng Stage 2 (summary enrichment) của SUMMARIZER trong LIDA.
  Gộp toàn bộ việc làm giàu vào MỘT lệnh gọi (thay vì gọi riêng cho
  từng cột) để giảm chi phí/độ trễ, đúng ghi chú "Prompt Engineering"
  ở Appendix C.1 của LIDA.

Lưu ý kỹ thuật: dùng pd.api.types.is_string_dtype() thay vì so sánh
`dtype == object`, vì từ pandas >= 2.x / 3.x, các cột chuỗi có thể có
dtype "str" hoặc "string" thay vì "object" tùy phiên bản/cấu hình.
"""
from __future__ import annotations

import json
import warnings
from typing import Protocol

import pandas as pd

from ..schemas import ColumnProfile, DataProfile


def _guess_time_column(df: pd.DataFrame) -> str | None:
    """Đoán cột thời gian.

    CHỈ thử ép kiểu datetime trên các cột dạng CHUỖI. Nếu thử trên cả
    cột số, `pd.to_datetime()` có thể "ép" thành công các giá trị số
    nhỏ không liên quan (ví dụ cột điểm đánh giá 1-5) thành mốc thời
    gian sai lệch — đây là lỗi thực tế phát hiện khi kiểm thử với bộ
    dữ liệu `danh_gia_khach_hang.csv` (xem backend/tests).
    """
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        if not pd.api.types.is_string_dtype(df[col]):
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                pd.to_datetime(df[col], errors="raise")
            return col
        except (ValueError, TypeError):
            continue
    return None


def _guess_group_columns(df: pd.DataFrame, time_col: str | None) -> list[str]:
    """Đoán các cột nhóm/định danh (kiểu chuỗi, lặp lại theo danh mục).

    Dùng TỶ LỆ số giá trị duy nhất / tổng số dòng (không chỉ số tuyệt
    đối) để phân biệt cột nhóm thật (ví dụ "Chi nhánh": vài giá trị
    lặp lại nhiều lần) với cột định danh/văn bản tự do (ví dụ "Nhận
    xét" hoặc "Khách hàng": gần như mỗi dòng một giá trị khác nhau).
    Ngưỡng tuyệt đối cũ (chỉ dựa trên `nunique() <= 20`) bị sai với
    tập dữ liệu nhỏ — lỗi thực tế phát hiện khi kiểm thử với
    `danh_gia_khach_hang.csv` (xem backend/tests).
    """
    groups: list[str] = []
    n = len(df)
    if n == 0:
        return groups
    for col in df.columns:
        if col == time_col or not pd.api.types.is_string_dtype(df[col]):
            continue
        nunique = df[col].nunique()
        if nunique / n <= 0.5 and nunique <= 50:
            groups.append(col)
    return groups


def profile(df: pd.DataFrame, n_samples: int = 3) -> DataProfile:
    """Sinh bản tóm tắt (profile) cho một DataFrame.

    Args:
        df: DataFrame đã đọc từ file CSV do người dùng tải lên.
        n_samples: số giá trị mẫu (không null, duy nhất) lấy cho mỗi cột.

    Returns:
        DataProfile — dùng làm ngữ cảnh nền (grounding context) cho
        module Question Interpreter (O2) ở bước tiếp theo.
    """
    time_col = _guess_time_column(df)
    group_cols = _guess_group_columns(df, time_col)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    columns: list[ColumnProfile] = []
    for col in df.columns:
        series = df[col]
        columns.append(
            ColumnProfile(
                name=col,
                dtype=str(series.dtype),
                n_unique=int(series.nunique()),
                n_missing=int(series.isna().sum()),
                samples=[str(v) for v in series.dropna().unique()[:n_samples]],
                min=str(series.min()) if col in numeric_cols else None,
                max=str(series.max()) if col in numeric_cols else None,
            )
        )

    return DataProfile(
        row_count=len(df),
        columns=columns,
        time_column=time_col,
        group_columns=group_cols,
        numeric_columns=numeric_cols,
    )


# =============================================================================
# Stage 2 — Làm giàu ngữ nghĩa bằng LLM (TÙY CHỌN, FR-02 phần mở rộng)
# =============================================================================


class LLMClient(Protocol):
    """Interface tối giản cho một LLM client.

    Định nghĩa dưới dạng Protocol (không phải lớp cụ thể) để:
      1. `enrich()` không phụ thuộc trực tiếp vào SDK của Anthropic
         -> dễ kiểm thử bằng client giả lập (xem backend/tests).
      2. Có thể thay bằng client khác (Haiku rẻ hơn, hoặc mô hình khác)
         mà không phải sửa logic enrich().
    """

    def complete_json(self, prompt: str) -> dict:
        """Gửi prompt, trả về dict đã parse sẵn từ JSON do LLM sinh ra.

        Cài đặt cụ thể (ClaudeClient bên dưới) chịu trách nhiệm parse
        JSON; enrich() chỉ làm việc với dict thuần Python.
        """
        ...


class ClaudeClient:
    """Cài đặt LLMClient dùng Claude API (Anthropic SDK).

    Model mặc định: claude-sonnet-5 — cân bằng chất lượng suy luận và
    chi phí, phù hợp cho tác vụ mô tả ngữ nghĩa dữ liệu. Với tác vụ đơn
    giản hơn (ví dụ chỉ phân loại kiểu cột, không cần mô tả dài), có
    thể cân nhắc claude-haiku-4-5-20251001 để giảm chi phí/độ trễ.
    """

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        import anthropic  # import cục bộ - tránh bắt buộc cài đặt SDK

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


def _build_enrichment_prompt(profile: DataProfile) -> str:
    """Xây prompt yêu cầu LLM trả về DUY NHẤT một JSON object."""
    cols_desc = "\n".join(
        f'- "{c.name}" (kiểu: {c.dtype}, mẫu: {c.samples[:3]})'
        for c in profile.columns
    )
    return f"""Bạn là một chuyên gia phân tích dữ liệu kinh doanh.
Dưới đây là hồ sơ (profile) của một tập dữ liệu dạng bảng:

Số dòng: {profile.row_count}
Danh sách cột:
{cols_desc}

Nhiệm vụ: sinh mô tả ngữ nghĩa cho tập dữ liệu và cho TỪNG cột nêu
trên. CHỈ trả về một JSON object duy nhất, đúng định dạng sau, không
kèm giải thích hay markdown:

{{
  "dataset_description": "<1-2 câu mô tả tập dữ liệu này nói về gì>",
  "columns": [
    {{"name": "<đúng tên cột như trên>", "description": "<mô tả ngắn>",
     "semantic_type": "<ví dụ: thời_gian | chi_nhánh | doanh_thu | số_lượng | danh_mục>"}}
  ]
}}

Bắt buộc: trường "columns" phải có đúng {len(profile.columns)} phần tử,
mỗi phần tử ứng với đúng một cột theo thứ tự đã liệt kê ở trên."""


def _merge_enrichment(profile: DataProfile, raw: dict) -> DataProfile:
    """Gộp kết quả LLM (dict) vào DataProfile, KHÔNG sửa profile gốc."""
    desc_by_name = {
        c["name"]: c for c in raw.get("columns", []) if isinstance(c, dict)
    }

    enriched_columns = []
    for col in profile.columns:
        extra = desc_by_name.get(col.name, {})
        enriched_columns.append(
            col.model_copy(
                update={
                    "description": extra.get("description"),
                    "semantic_type": extra.get("semantic_type"),
                }
            )
        )

    return profile.model_copy(
        update={
            "dataset_description": raw.get("dataset_description"),
            "columns": enriched_columns,
        }
    )


def enrich(profile: DataProfile, llm: LLMClient | None = None) -> DataProfile:
    """Stage 2 (TÙY CHỌN): làm giàu bản tóm tắt bằng LLM.

    Thiết kế để KHÔNG BAO GIỜ làm pipeline sập vì lỗi liên quan LLM:
      - Nếu `llm is None` -> trả về profile gốc, không làm gì cả.
      - Nếu LLM trả JSON lỗi/không đúng cấu trúc -> log cảnh báo (qua
        exception bị nuốt có kiểm soát) và trả về profile gốc thay vì
        raise lỗi, vì đây là bước TÙY CHỌN (không nằm trên đường găng
        của FR-02 cốt lõi).

    Args:
        profile: DataProfile do Stage 1 (`profile()`) sinh ra.
        llm: một LLMClient (ví dụ ClaudeClient()). None -> bỏ qua.

    Returns:
        DataProfile mới (không sửa đổi `profile` truyền vào). Nếu làm
        giàu thất bại, trả về bản sao giống hệt profile gốc.
    """
    if llm is None:
        return profile

    try:
        raw = llm.complete_json(_build_enrichment_prompt(profile))
        return _merge_enrichment(profile, raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Làm giàu là tùy chọn -> lỗi ở đây không được phép chặn pipeline.
        return profile


# TODO (mở rộng thêm - không bắt buộc cho MVP Tuần 1-8):
#   - Có thể thay _guess_group_columns bằng một classifier nhẹ (không
#     phải LLM) nếu muốn tăng độ chính xác nhận diện kiểu ngữ nghĩa cột
#     (xem thảo luận về "tự train" trong docs/SRS.md, phần ghi chú).
#   - Ghi log số token/chi phí mỗi lần gọi enrich() để phục vụ NFR-01
#     (đo hiệu năng) và FR-10 (log độ trễ từng module).
