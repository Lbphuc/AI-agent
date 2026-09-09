"""Module O1 — Data Profiler.

Trích xuất schema, kiểu dữ liệu, thống kê mô tả, và nhận diện cột thời
gian / cột nhóm (định danh) / cột số từ một DataFrame.

Đây là module xử lý THUẦN TÚY BẰNG LUẬT (rule-based) — không gọi LLM —
tương ứng Stage 1 (base summary generation) của SUMMARIZER trong LIDA
(Dibia, 2023). Việc làm giàu ngữ nghĩa bằng LLM (Stage 2 của LIDA) là
phần mở rộng TÙY CHỌN, chưa cài đặt trong scaffold này (xem TODO cuối
file và docs/SRS.md mục 3, FR-02).

Lưu ý kỹ thuật: dùng pd.api.types.is_string_dtype() thay vì so sánh
`dtype == object`, vì từ pandas >= 2.x / 3.x, các cột chuỗi có thể có
dtype "str" hoặc "string" thay vì "object" tùy phiên bản/cấu hình.
"""
from __future__ import annotations

import pandas as pd

from ..schemas import ColumnProfile, DataProfile


def _guess_time_column(df: pd.DataFrame) -> str | None:
    """Đoán cột thời gian: cột đầu tiên có thể ép kiểu datetime thành công."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        try:
            pd.to_datetime(df[col], errors="raise")
            return col
        except (ValueError, TypeError):
            continue
    return None


def _guess_group_columns(df: pd.DataFrame, time_col: str | None) -> list[str]:
    """Đoán các cột nhóm/định danh: cột kiểu chuỗi có số giá trị duy nhất
    không quá lớn so với tổng số dòng (tránh nhầm cột tự do như ghi chú)."""
    groups: list[str] = []
    for col in df.columns:
        if col == time_col:
            continue
        if pd.api.types.is_string_dtype(df[col]) and df[col].nunique() <= max(
            20, len(df) // 2
        ):
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


# TODO (mở rộng — không bắt buộc cho MVP Tuần 1-8):
#   - Stage 2 (LLM enrichment): gọi Claude API để sinh mô tả ngữ nghĩa
#     cho từng cột (ví dụ "Doanh_thu_trieu_vnd" -> "Doanh thu theo
#     tháng, đơn vị triệu VNĐ"), theo đúng cách LIDA làm giàu tóm tắt.
#   - Có thể thay _guess_group_columns bằng một classifier nhẹ (không
#     phải LLM) nếu muốn tăng độ chính xác nhận diện kiểu ngữ nghĩa cột
#     (xem thảo luận về "tự train" trong docs/SRS.md, phần ghi chú).
