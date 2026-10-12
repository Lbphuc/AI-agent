/**
 * API client – gọi backend FastAPI.
 * Sử dụng fetch (không cần axios) để tránh thêm bundle size.
 * VITE_API_BASE_URL: để trống → dùng proxy Vite (/api/*) khi dev,
 *                    đặt URL thật khi deploy (ví dụ: https://api.example.com).
 */
import type { AnalyzeResponse } from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Gọi POST /analyze.
 * @param file   File CSV hoặc Excel tải lên
 * @param question Câu hỏi ngôn ngữ tự nhiên
 * @returns AnalyzeResponse từ backend
 * @throws Error có message từ backend (400/422/503) hoặc lỗi mạng
 */
export async function analyzeData(
  file: File,
  question: string,
  expandViews: boolean = true
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  form.append("expand_views", String(expandViews));

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/analyze`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new Error(
      "Không kết nối được backend. Kiểm tra backend đã chạy chưa:\n" +
      "uvicorn backend.app.main:app --reload --port 8000"
    );
  }

  if (!res.ok) {
    // FastAPI trả về { detail: "..." } hoặc { detail: [...] }
    let detail = `Lỗi ${res.status}`;
    try {
      const json = await res.json();
      if (typeof json.detail === "string") {
        detail = json.detail;
      } else if (Array.isArray(json.detail)) {
        // Validation errors từ Pydantic
        detail = json.detail.map((d: { msg: string }) => d.msg).join("; ");
      }
    } catch {
      // ignore JSON parse error
    }

    // Map HTTP status → message thân thiện
    if (res.status === 400) throw new Error(`File không hợp lệ: ${detail}`);
    if (res.status === 422) throw new Error(`Không phân tích được: ${detail}`);
    if (res.status === 500) throw new Error(`Lỗi máy chủ (500): ${detail}`);
    if (res.status === 502) throw new Error(`Backend chưa khởi động hoặc không thể kết nối. Vui lòng chạy: uvicorn backend.app.main:app --reload`);
    if (res.status === 503) throw new Error(`Dịch vụ AI đang quá tải hoặc tạm thời hết quota: ${detail}`);
    throw new Error(detail);
  }

  return res.json() as Promise<AnalyzeResponse>;
}
