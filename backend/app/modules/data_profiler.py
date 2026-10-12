"""Module O1 — Data Profiler.

Trích xuất schema, kiểu dữ liệu, thống kê mô tả, và nhận diện cột thời
gian / cột nhóm (định danh) / cột số từ một DataFrame (Stage 1), cộng
thêm một bước làm giàu ngữ nghĩa tùy chọn bằng LLM (Stage 2).

- **Stage 0** (`_clean()`): làm sạch tối thiểu TRƯỚC khi đoán kiểu cột
  — trim tên cột, xóa cột/dòng rỗng, chuyển số định dạng Việt Nam
  ("1.500.000") thành float. Bắt buộc chạy trước Stage 1 để tránh
  bug nhầm dtype với dữ liệu Excel thực tế (FR-12).
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
import logging
import re
import warnings

import pandas as pd

from ..llm_client import LLMClient
from ..schemas import ColumnProfile, DataProfile
from .business_terms import resolve_column_display

logger = logging.getLogger(__name__)

# Pattern so dinh dang Viet Nam: 1.500.000 hoac 1.500.000,50
# Giai thich:
#   ^-?          : tuy chon dau tru
#   \d{1,3}      : 1-3 chu so dau
#   (\.\d{3})*   : khong hoac nhieu nhom .000 (dau cham = ngan phan)
#   (,\d+)?$     : tuy chon phan thap phan dung dau phay
_VN_NUMBER_PATTERN = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$")


# =============================================================================
# Stage 0 — Làm sạch dữ liệu tối thiểu (chạy TRƯỚC Stage 1)
# =============================================================================


def _drop_empty_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Xoa cot 'Unnamed: N' (Excel xuat du) chi khi rong hoan toan.

    Chi xoa khi vua khop ten 'Unnamed: N' VUA rong hoan toan — tranh
    xoa nham cot that su co du lieu chi vi khong co ten.
    """
    to_drop = [
        col for col in df.columns
        if re.match(r"^Unnamed: \d+$", str(col)) and df[col].isna().all()
    ]
    return df.drop(columns=to_drop)


def _strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Loai bo khoang trang thua o dau/cuoi gia tri trong cot chuoi."""
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].str.strip()
    return df


def _convert_vn_formatted_numbers(
    df: pd.DataFrame, min_match_ratio: float = 0.8
) -> pd.DataFrame:
    """Chuyen cot text dang '1.500.000' (kieu VN) thanh so thuc (float).

    Chi chuyen neu >= min_match_ratio gia tri khong null trong cot khop
    _VN_NUMBER_PATTERN — tranh chuyen nham cot text thuong co vai gia
    tri tinh co giong so.

    Nguyen tac chuyen doi:
      '1.500.000'  -> xoa dau cham -> '1500000'   -> 1500000.0
      '1.500,50'   -> xoa cham, doi phay thanh cham -> '1500.50' -> 1500.5
    """
    for col in df.columns:
        if not pd.api.types.is_string_dtype(df[col]):
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        match_ratio = non_null.str.match(_VN_NUMBER_PATTERN).mean()
        if match_ratio >= min_match_ratio:
            converted = (
                non_null
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )
            df[col] = converted.reindex(df.index)
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Lam sach toi thieu (Stage 0) TRUOC khi doan kieu cot (Stage 1).

    Thu tu thuc hien co chu y:
    1. Trim ten cot — dam bao step sau khop ten chinh xac.
    2. Xoa cot Unnamed rong — giam nhieu tu dinh dang Excel du.
    3. Xoa dong rong hoan toan — giam nhieu dinh dang Excel.
    4. Trim gia tri chuoi — can lam truoc khi match pattern so.
    5. Chuyen so VN ('1.500.000') — phai sau trim de pattern khop dung.

    CO Y KHONG lam:
    - Tu do vi tri dong header (qua nhieu heuristic, de vo).
    - Xu ly o merge (merged cells) trong Excel.
    - Tu sua loi chinh ta ten cot.
    """
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = _drop_empty_unnamed_columns(df)
    df = df.dropna(axis=0, how="all").reset_index(drop=True)
    df = _strip_string_columns(df)
    df = _convert_vn_formatted_numbers(df)
    return df


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


def _time_range(
    df: pd.DataFrame, time_col: str | None
) -> tuple[str | None, str | None]:
    """Tính khoảng thời gian [min, max] thực tế của cột thời gian.

    Cần thiết để O2 (Question Interpreter, Tuần 3) giải nghĩa các
    biểu thức thời gian tương đối trong câu hỏi (ví dụ "12 tháng gần
    nhất") mà KHÔNG phải tự đọc lại DataFrame thô — nếu không có
    trường này, O2 buộc phải vi phạm ranh giới module (chỉ nên phụ
    thuộc DataProfile, không phụ thuộc DataFrame).
    """
    if time_col is None:
        return None, None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(df[time_col], errors="coerce").dropna()
    if parsed.empty:
        return None, None
    return str(parsed.min().date()), str(parsed.max().date())


def profile(df: pd.DataFrame, n_samples: int = 3) -> DataProfile:
    """Sinh bản tóm tắt (profile) cho một DataFrame.

    Args:
        df: DataFrame đã đọc từ file CSV/Excel do người dùng tải lên.
        n_samples: số giá trị mẫu (không null, duy nhất) lấy cho mỗi cột.

    Returns:
        DataProfile — dùng làm ngữ cảnh nền (grounding context) cho
        module Question Interpreter (O2) ở bước tiếp theo.
    """
    # Stage 0: lam sach TRUOC khi doan kieu cot — thu tu bat buoc
    # (xem ly do chi tiet trong docstring _clean()).
    df = _clean(df)
    time_col = _guess_time_column(df)
    time_min, time_max = _time_range(df, time_col)
    group_cols = _guess_group_columns(df, time_col)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    columns: list[ColumnProfile] = []
    for col in df.columns:
        series = df[col]
        disp_name, unit = resolve_column_display(col)
        columns.append(
            ColumnProfile(
                name=col,
                dtype=str(series.dtype),
                n_unique=int(series.nunique()),
                n_missing=int(series.isna().sum()),
                samples=[str(v) for v in series.dropna().unique()[:n_samples]],
                min=str(series.min()) if col in numeric_cols else None,
                max=str(series.max()) if col in numeric_cols else None,
                display_name=disp_name,
                unit=unit,
            )
        )

    return DataProfile(
        row_count=len(df),
        columns=columns,
        time_column=time_col,
        time_min=time_min,
        time_max=time_max,
        group_columns=group_cols,
        numeric_columns=numeric_cols,
    )


# =============================================================================
# Stage 2 — Làm giàu ngữ nghĩa bằng LLM (TÙY CHỌN, FR-02 phần mở rộng)
# =============================================================================
# LLMClient / ClaudeClient dùng chung được định nghĩa ở backend/app/llm_client.py
# (từ Tuần 3, khi O2 cũng bắt đầu cần đến LLM — xem docstring ở đó).


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
        if not isinstance(raw, dict):
            # LLM co the tra ve JSON hop le nhung khong phai object
            # (vd mot list) - raw.get(...) se raise AttributeError neu
            # khong chan truoc; quy no ve ValueError de nhat quan voi
            # cac loi "cau truc JSON sai" khac ben duoi.
            raise ValueError(
                f"LLM tra ve kieu {type(raw).__name__}, ky vong dict/JSON object"
            )
        return _merge_enrichment(profile, raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as exc:
        # Làm giàu là tùy chọn -> lỗi ở đây không được phép chặn pipeline,
        # nhưng PHẢI log lại (kèm traceback) để còn debug được khi tích
        # hợp Claude API thật — trước bản sửa này, lỗi bị nuốt hoàn toàn
        # im lặng, mâu thuẫn với FR-10 (ghi log lỗi từng module).
        logger.warning(
            "Stage 2 (enrich) that bai, tra ve profile goc khong lam giau. "
            "Loi: %s",
            exc,
            exc_info=True,
        )
        return profile


# TODO (mở rộng thêm - không bắt buộc cho MVP Tuần 1-8):
#   - Có thể thay _guess_group_columns bằng một classifier nhẹ (không
#     phải LLM) nếu muốn tăng độ chính xác nhận diện kiểu ngữ nghĩa cột
#     (xem thảo luận về "tự train" trong docs/SRS.md, phần ghi chú).
#   - Ghi log số token/chi phí mỗi lần gọi enrich() để phục vụ NFR-01
#     (đo hiệu năng) và FR-10 (log độ trễ từng module).
