"""Module từ điển thuật ngữ kinh doanh nội bộ (Phần A6).

Chuẩn hóa tên hiển thị (display_name) và đơn vị tính (unit) của cột dữ liệu
để giao diện, biểu đồ, báo cáo PDF và Excel luôn thân thiện với người dùng
Việt Nam, không để lộ tên biến kỹ thuật (vd: Doanh_thu_trieu_vnd -> Doanh thu, triệu VNĐ).
"""
from __future__ import annotations


_TERM_DICTIONARY: dict[str, tuple[str, str | None]] = {
    "doanh_thu": ("Doanh thu", "triệu VNĐ"),
    "doanh_thu_trieu_vnd": ("Doanh thu", "triệu VNĐ"),
    "doanh_so": ("Doanh số", "triệu VNĐ"),
    "chi_phi": ("Chi phí", "triệu VNĐ"),
    "chi_phi_trieu_vnd": ("Chi phí", "triệu VNĐ"),
    "chi_phi_marketing": ("Chi phí marketing", "triệu VNĐ"),
    "chi_phi_marketing_trieu_vnd": ("Chi phí marketing", "triệu VNĐ"),
    "loai_chi_phi": ("Loại chi phí", None),
    "loi_nhuan": ("Lợi nhuận", "triệu VNĐ"),
    "chi_nhanh": ("Chi nhánh", None),
    "danh_muc": ("Danh mục", None),
    "nganh_hang": ("Ngành hàng", None),
    "khu_vuc": ("Khu vực", None),
    "phan_khuc": ("Phân khúc", None),
    "san_pham": ("Sản phẩm", None),
    "thang": ("Tháng", None),
    "ngay": ("Ngày", None),
    "nam": ("Năm", None),
    "quy": ("Quý", None),
    "thoi_gian": ("Thời gian", None),
    "so_luong": ("Số lượng", "sản phẩm"),
    "so_luong_ton": ("Số lượng tồn kho", "đơn vị"),
    "ton_kho": ("Tồn kho", "đơn vị"),
    "kho": ("Kho hàng", None),
    "kho_hang": ("Kho hàng", None),
    "diem_danh_gia": ("Điểm đánh giá", "điểm"),
    "danh_gia": ("Đánh giá", "điểm"),
    "rating": ("Đánh giá", "điểm"),
    "khach_hang": ("Khách hàng", None),
    "don_hang": ("Đơn hàng", "đơn"),
    "gia": ("Giá bán", "VNĐ"),
    "don_gia": ("Đơn giá", "VNĐ"),
}

_UNIT_SUFFIXES: list[tuple[str, str]] = [
    ("_trieu_vnd", "triệu VNĐ"),
    ("_nghin_vnd", "nghìn VNĐ"),
    ("_ty_vnd", "tỷ VNĐ"),
    ("_vnd", "VNĐ"),
    ("_usd", "USD"),
    ("_phan_tram", "%"),
    ("_pct", "%"),
]


def resolve_column_display(name: str) -> tuple[str, str | None]:
    """Phân giải tên cột thành (display_name, unit)."""
    key = name.lower().strip()
    if key in _TERM_DICTIONARY:
        return _TERM_DICTIONARY[key]

    detected_unit: str | None = None
    clean_name = name

    for suffix, unit in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            detected_unit = unit
            clean_name = name[: -len(suffix)]
            key = key[: -len(suffix)]
            break

    if key in _TERM_DICTIONARY:
        disp, dict_unit = _TERM_DICTIONARY[key]
        return disp, detected_unit or dict_unit

    words = clean_name.replace("_", " ").split()
    formatted = " ".join(word.capitalize() for word in words) if words else name
    return formatted, detected_unit
