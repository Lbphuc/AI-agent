"""Module Excel Exporter.

Sinh workbook .xlsx hoàn chỉnh từ AnalyzeResponse với biểu đồ Excel gốc (native charts),
bảng số liệu chi tiết, sheet tóm tắt và sheet phương pháp tính.
Chống chèn công thức (Formula Injection), đặt tên sheet an toàn, tự động căn độ rộng cột.
"""
from __future__ import annotations

import io
import re
from typing import Any

import xlsxwriter

from ..schemas import AnalyzeResponse, ChartSpec, ExportSections, ExportXlsxRequest


def safe_sheet_name(name: str, existing: set[str]) -> str:
    """Tạo tên sheet Excel hợp lệ:
    - Tối đa 31 ký tự.
    - Cấm các ký tự: [ ] : * ? / \\
    - Không trùng với tên sheet đã có (không phân biệt hoa/thường).
    """
    cleaned = re.sub(r"[\[\]:*?/\\]", "_", name).strip()
    if not cleaned:
        cleaned = "Sheet"
    base = cleaned[:27]
    candidate = base
    counter = 1
    while candidate.lower() in {s.lower() for s in existing}:
        candidate = f"{base[:24]}_{counter}"
        counter += 1
    existing.add(candidate)
    return candidate


def _write_safe_string(worksheet: Any, row: int, col: int, val: Any, cell_format: Any = None) -> None:
    """Ghi chuỗi an toàn bằng write_string để chống Formula Injection.
    Bất kỳ giá trị nào bắt đầu bằng =, +, -, @ đều không bị Excel diễn giải thành lệnh.
    """
    val_str = "" if val is None else str(val)
    worksheet.write_string(row, col, val_str, cell_format)


def _write_safe_cell(worksheet: Any, row: int, col: int, val: Any, num_fmt: Any = None, str_fmt: Any = None) -> None:
    """Ghi ô dữ liệu: số ghi bằng write_number, chuỗi ghi bằng write_string."""
    if val is None:
        worksheet.write_blank(row, col, None, str_fmt)
    elif isinstance(val, (int, float)):
        worksheet.write_number(row, col, float(val), num_fmt)
    else:
        worksheet.write_string(row, col, str(val), str_fmt)


def generate_excel_report(request: ExportXlsxRequest) -> bytes:
    """Sinh file .xlsx dưới dạng bytes từ ExportXlsxRequest."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False})

    sections = request.sections or ExportSections()
    response = request.response
    existing_sheets: set[str] = set()

    # Định dạng chung
    header_fmt = workbook.add_format({
        "bold": True,
        "font_size": 14,
        "font_color": "#1E293B",
        "bottom": 2,
        "bottom_color": "#475569",
    })
    sub_fmt = workbook.add_format({
        "italic": True,
        "font_color": "#64748B",
        "font_size": 10,
    })
    table_header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#F1F5F9",
        "border": 1,
        "border_color": "#CBD5E1",
        "font_color": "#0F172A",
    })
    data_str_fmt = workbook.add_format({
        "border": 1,
        "border_color": "#E2E8F0",
    })
    data_num_fmt = workbook.add_format({
        "border": 1,
        "border_color": "#E2E8F0",
        "num_format": "#,##0.0",
    })
    bold_fmt = workbook.add_format({"bold": True, "font_color": "#0F172A"})
    italic_disclaimer = workbook.add_format({"italic": True, "font_color": "#64748B", "font_size": 9})

    # =========================================================================
    # 1. Sheet "Tóm tắt"
    # =========================================================================
    summary_sheet_name = safe_sheet_name("Tóm tắt", existing_sheets)
    ws_summary = workbook.add_worksheet(summary_sheet_name)
    ws_summary.set_column(0, 0, 24)
    ws_summary.set_column(1, 1, 65)

    cur_row = 0
    title_text = "BÁO CÁO PHÂN TÍCH DỮ LIỆU KINH DOANH"
    if request.org_name:
        title_text = f"{request.org_name} — {title_text}"
    ws_summary.write(cur_row, 0, title_text, header_fmt)
    cur_row += 2

    # Thông tin cơ bản
    ws_summary.write(cur_row, 0, "Câu hỏi phân tích:", bold_fmt)
    _write_safe_string(ws_summary, cur_row, 1, response.goal.question if response.goal else "")
    cur_row += 1

    if response.meta and response.meta.goal_summary:
        ws_summary.write(cur_row, 0, "Hệ thống hiểu là:", bold_fmt)
        _write_safe_string(ws_summary, cur_row, 1, response.meta.goal_summary)
        cur_row += 1

    if response.meta:
        ws_summary.write(cur_row, 0, "Thời gian tạo:", bold_fmt)
        _write_safe_string(ws_summary, cur_row, 1, response.meta.generated_at)
        cur_row += 1

        ws_summary.write(cur_row, 0, "Mô hình AI:", bold_fmt)
        _write_safe_string(ws_summary, cur_row, 1, response.meta.model_name)
        cur_row += 1

        ws_summary.write(cur_row, 0, "Số dòng dữ liệu:", bold_fmt)
        rows_info = f"{response.meta.rows_used} dòng đã phân tích (trong tổng số {response.meta.rows_total} dòng)"
        _write_safe_string(ws_summary, cur_row, 1, rows_info)
        cur_row += 1

    show_insight = getattr(sections, "insight", True) and getattr(sections, "summary", True)
    if show_insight and response.insight and response.insight.insight_text:
        cur_row += 1
        ws_summary.write(cur_row, 0, "NHẬN XÉT CỦA HỆ THỐNG", bold_fmt)
        cur_row += 1
        _write_safe_string(ws_summary, cur_row, 0, response.insight.insight_text)
        cur_row += 1
        ws_summary.write(
            cur_row, 0,
            "Lưu ý: Nhận xét do AI tạo từ số liệu đã tính toán; hãy đối chiếu với bảng số liệu ở các sheet tiếp theo.",
            italic_disclaimer,
        )
        cur_row += 2

    # Danh mục biểu đồ
    cur_row += 1
    ws_summary.write(cur_row, 0, "DANH MỤC CÁC BIỂU ĐỒ TRONG BÁO CÁO", bold_fmt)
    cur_row += 1
    ws_summary.write(cur_row, 0, "STT", table_header_fmt)
    ws_summary.write(cur_row, 1, "Tên biểu đồ", table_header_fmt)
    cur_row += 1

    chart_idx = 1
    for chart in response.charts:
        is_primary = getattr(chart, "role", "primary") == "primary"
        if is_primary and not sections.primary_chart:
            continue
        if not is_primary and not sections.supplementary_charts:
            continue
        ws_summary.write_number(cur_row, 0, chart_idx, data_num_fmt)
        _write_safe_string(ws_summary, cur_row, 1, chart.title, data_str_fmt)
        chart_idx += 1
        cur_row += 1

    # =========================================================================
    # 2. Từng biểu đồ -> 1 sheet riêng kèm bảng số liệu & native Excel chart
    # =========================================================================
    chart_counter = 0
    for chart in response.charts:
        is_primary = getattr(chart, "role", "primary") == "primary"
        if is_primary and not sections.primary_chart:
            continue
        if not is_primary and not sections.supplementary_charts:
            continue

        chart_counter += 1
        sheet_title = chart.title or f"Biểu đồ {chart_counter}"
        sheet_name = safe_sheet_name(sheet_title, existing_sheets)
        ws_chart = workbook.add_worksheet(sheet_name)

        ws_chart.set_column(0, 0, 20)
        # Các cột series
        series_keys = list(chart.series.keys()) if chart.series else []
        for s_col in range(1, len(series_keys) + 1):
            ws_chart.set_column(s_col, s_col, 18)

        # Tiêu đề sheet
        ws_chart.write(0, 0, chart.title, header_fmt)
        sub_text = f"Đơn vị: {chart.unit}" if chart.unit else ""
        if chart.caption:
            sub_text = f"{sub_text} — {chart.caption}" if sub_text else chart.caption
        if sub_text:
            ws_chart.write(1, 0, sub_text, sub_fmt)

        table_start_row = 3
        # Header bảng
        first_task = response.goal.tasks[0] if (response.goal and response.goal.tasks) else None
        x_label = "Chỉ mục"
        if is_primary and first_task and first_task.group_by:
            x_label = first_task.group_by
        elif getattr(chart, "perspective", None) == "share_of_total":
            x_label = "Nhóm"
        elif getattr(chart, "perspective", None) == "trend_by_group":
            x_label = "Thời gian"

        ws_chart.write(table_start_row, 0, x_label, table_header_fmt)
        for s_idx, s_name in enumerate(series_keys):
            ws_chart.write(table_start_row, 1 + s_idx, s_name, table_header_fmt)

        # Dữ liệu
        n_rows = len(chart.x) if chart.x else 0
        for r in range(n_rows):
            row_num = table_start_row + 1 + r
            x_val = chart.x[r] if r < len(chart.x) else ""
            _write_safe_cell(ws_chart, row_num, 0, x_val, num_fmt=data_num_fmt, str_fmt=data_str_fmt)
            for s_idx, s_name in enumerate(series_keys):
                s_vals = chart.series.get(s_name, [])
                val = s_vals[r] if r < len(s_vals) else None
                _write_safe_cell(ws_chart, row_num, 1 + s_idx, val, num_fmt=data_num_fmt, str_fmt=data_str_fmt)

        # Tạo biểu đồ gốc (native chart) trong Excel
        if n_rows > 0 and series_keys:
            chart_type_map = {
                "bar": "column",
                "line": "line",
                "pie": "pie",
                "area": "area",
            }
            excel_chart_type = chart_type_map.get(chart.chart_type, "column")
            native_chart = workbook.add_chart({"type": excel_chart_type})

            for s_idx, s_name in enumerate(series_keys):
                native_chart.add_series({
                    "name": [sheet_name, table_start_row, 1 + s_idx],
                    "categories": [sheet_name, table_start_row + 1, 0, table_start_row + n_rows, 0],
                    "values": [sheet_name, table_start_row + 1, 1 + s_idx, table_start_row + n_rows, 1 + s_idx],
                })

            native_chart.set_title({"name": chart.title})
            native_chart.set_style(10)
            native_chart.set_size({"width": 640, "height": 380})

            # Đặt biểu đồ bên phải bảng số liệu
            chart_col = len(series_keys) + 2
            ws_chart.insert_chart(table_start_row, chart_col, native_chart)

    # =========================================================================
    # 3. Sheet "Cách tính & Lưu ý"
    show_calc_notes = getattr(sections, "calculation_notes", True) and getattr(sections, "methodology", True)
    if show_calc_notes:
        notes_sheet_name = safe_sheet_name("Cách tính & Lưu ý", existing_sheets)
        ws_notes = workbook.add_worksheet(notes_sheet_name)
        ws_notes.set_column(0, 0, 28)
        ws_notes.set_column(1, 1, 65)

        ws_notes.write(0, 0, "PHƯƠNG PHÁP TÍNH TOÁN VÀ GHI CHÚ KỸ THUẬT", header_fmt)

        row_n = 2
        ws_notes.write(row_n, 0, "Hạng mục", table_header_fmt)
        ws_notes.write(row_n, 1, "Mô tả chi tiết", table_header_fmt)
        row_n += 1

        first_task = response.goal.tasks[0] if (response.goal and response.goal.tasks) else None
        metric_label = first_task.metric if first_task else "Không xác định"
        group_label = first_task.group_by if (first_task and first_task.group_by) else "Không xác định"

        items = [
            ("Mục tiêu phân tích", response.goal.question if response.goal else ""),
            ("Thời gian áp dụng", f"{response.goal.time_start or 'Đầu'} đến {response.goal.time_end or 'Cuối'}" if response.goal else "Toàn bộ"),
            ("Chỉ số đo lường", metric_label),
            ("Nhóm phân loại", group_label),
            ("Công thức tỷ trọng", "Tỷ trọng (%) = (Giá trị của nhóm / Tổng toàn bộ) * 100"),
            ("Công thức biến động", "% Thay đổi = ((Kỳ này - Kỳ trước) / Kỳ trước) * 100"),
            ("Công thức đóng góp", "Đóng góp thay đổi = Kỳ cuối - Kỳ đầu"),
            ("Trung bình trượt", "MA3 = Trung bình cộng của 3 kỳ liên tiếp (kỳ hiện tại và 2 kỳ trước)"),
        ]

        if response.meta and response.meta.notes:
            for i, note in enumerate(response.meta.notes, 1):
                items.append((f"Lưu ý bổ sung #{i}", note))

        for label, desc in items:
            ws_notes.write(row_n, 0, label, bold_fmt)
            _write_safe_string(ws_notes, row_n, 1, desc, data_str_fmt)
            row_n += 1

    workbook.close()
    return output.getvalue()
