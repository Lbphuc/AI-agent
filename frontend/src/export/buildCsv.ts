import type { ChartSpec } from "../api/types";

/**
 * Tạo nội dung file CSV từ ChartSpec.
 * Chống Formula Injection: Thêm dấu ' ở đầu nếu ô bắt đầu bằng =, +, -, @.
 * Hỗ trợ tiếng Việt: Thêm UTF-8 BOM (\uFEFF) để Excel mở không bị vỡ font.
 */
export function buildCsv(chart: ChartSpec): string {
  const seriesKeys = Object.keys(chart.series || {});
  const headers = ["Chỉ mục", ...seriesKeys.map((k) => (chart.display_name && seriesKeys.length === 1 ? chart.display_name : k))];

  const escapeCell = (val: unknown): string => {
    if (val === null || val === undefined) return "";
    let str = String(val);

    // Chống Formula Injection cho Excel
    if (/^[=+\-@]/.test(str)) {
      str = `'${str}`;
    }

    // Nếu chứa dấu phẩy, dấu nháy kép hoặc xuống dòng -> bọc trong dấu nháy kép
    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
      str = `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const lines: string[] = [];
  lines.push(headers.map(escapeCell).join(","));

  const nRows = chart.x?.length || 0;
  for (let r = 0; r < nRows; r++) {
    const row = [chart.x[r], ...seriesKeys.map((k) => chart.series[k]?.[r] ?? "")];
    lines.push(row.map(escapeCell).join(","));
  }

  // Thêm UTF-8 BOM ở đầu file
  return "\uFEFF" + lines.join("\r\n");
}

export function downloadCsv(chart: ChartSpec, filename = "du_lieu_bieu_do.csv"): void {
  const csvContent = buildCsv(chart);
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
