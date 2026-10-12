import type { AnalyzeResponse, ExportSections } from "../api/types";

/**
 * Gọi API backend /export/xlsx để sinh file Excel chuẩn với biểu đồ gốc.
 */
export async function exportToExcel(
  response: AnalyzeResponse,
  filename = "data.csv",
  sections?: ExportSections,
  orgName?: string
): Promise<void> {
  const payload = {
    response,
    filename,
    org_name: orgName?.trim() || null,
    sections: sections || {},
  };

  const res = await fetch("/api/export/xlsx", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let errMsg = "Không thể xuất file Excel";
    try {
      const errJson = await res.json();
      if (errJson.detail) errMsg = errJson.detail;
    } catch {
      // Fallback
    }
    throw new Error(errMsg);
  }

  // Lấy tên file từ Content-Disposition header nếu có
  const disposition = res.headers.get("Content-Disposition");
  let downloadFilename = `BaoCao_${filename.replace(/\.[^/.]+$/, "")}_${Date.now()}.xlsx`;

  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match && utf8Match[1]) {
      downloadFilename = decodeURIComponent(utf8Match[1]);
    } else {
      const regularMatch = disposition.match(/filename="?([^";]+)"?/i);
      if (regularMatch && regularMatch[1]) {
        downloadFilename = regularMatch[1];
      }
    }
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = downloadFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
