/**
 * API client – gọi backend FastAPI.
 * Sử dụng fetch tiêu chuẩn với AbortSignal để hỗ trợ hủy request đang chạy.
 */
import type {
  AnalysisGoal,
  AnalysisLevel,
  AnalysisMode,
  AnalyzeResponse,
  DataProfile,
  DeepenResponse,
  InterpretResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponseError(res: Response): Promise<never> {
  let detail = `Lỗi ${res.status}`;
  try {
    const json = await res.json();
    if (typeof json.detail === "string") {
      detail = json.detail;
    } else if (Array.isArray(json.detail)) {
      detail = json.detail.map((d: { msg: string }) => d.msg).join("; ");
    }
  } catch {
    // ignore json error
  }

  if (res.status === 400) throw new Error(`File không hợp lệ: ${detail}`);
  if (res.status === 422) throw new Error(`Không phân tích được: ${detail}`);
  if (res.status === 500) throw new Error(`Lỗi máy chủ (500): ${detail}`);
  if (res.status === 502)
    throw new Error(
      "Backend chưa khởi động hoặc không thể kết nối. Vui lòng kiểm tra cổng 8000."
    );
  if (res.status === 503)
    throw new Error(`Dịch vụ AI đang quá tải hoặc tạm thời hết quota: ${detail}`);
  throw new Error(detail);
}

/**
 * Gọi POST /profile để lấy cấu trúc dữ liệu và khả năng dùng các chế độ phân tích.
 */
export async function profileData(
  file: File,
  signal?: AbortSignal
): Promise<DataProfile> {
  const form = new FormData();
  form.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/profile`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new Error("Không kết nối được backend khi đọc hồ sơ dữ liệu.");
  }

  if (!res.ok) await handleResponseError(res);
  return res.json() as Promise<DataProfile>;
}

/**
 * Gọi POST /interpret để hiểu câu hỏi và suy ra các cấp độ phân tích (levels).
 */
export async function interpretQuestion(
  file: File,
  question: string,
  mode: AnalysisMode = "auto",
  signal?: AbortSignal
): Promise<InterpretResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  form.append("mode", mode);

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/interpret`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new Error("Không kết nối được backend khi giải nghĩa câu hỏi.");
  }

  if (!res.ok) await handleResponseError(res);
  return res.json() as Promise<InterpretResponse>;
}

/**
 * Gọi POST /analyze. Nếu đã có goal thì truyền kèm để bỏ qua O2.
 */
export async function analyzeData(
  file: File,
  question: string,
  expandViews: boolean = true,
  goal?: AnalysisGoal,
  signal?: AbortSignal
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  form.append("expand_views", String(expandViews));
  if (goal) {
    form.append("goal", JSON.stringify(goal));
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/analyze`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new Error("Không kết nối được backend khi thực hiện phân tích.");
  }

  if (!res.ok) await handleResponseError(res);
  return res.json() as Promise<AnalyzeResponse>;
}

/**
 * Gọi POST /deepen để chạy phân tích sâu theo cấp: diagnostic | forecast | prescriptive.
 */
export async function deepenAnalysis(
  file: File,
  goal: AnalysisGoal,
  level: AnalysisLevel,
  signal?: AbortSignal
): Promise<DeepenResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("goal", JSON.stringify(goal));
  form.append("level", level);

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/deepen`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new Error(`Không kết nối được backend khi thực hiện phân tích sâu (${level}).`);
  }

  if (!res.ok) await handleResponseError(res);
  return res.json() as Promise<DeepenResponse>;
}
