/**
 * API client – gọi backend FastAPI.
 * Sử dụng fetch tiêu chuẩn với AbortSignal để hỗ trợ hủy request đang chạy.
 */
import type {
  AnalysisGoal,
  AnalysisLevel,
  AnalysisMode,
  AnalyzeResponse,
  ChartSpec,
  ChartType,
  ChartVerdict,
  DataProfile,
  DeepenResponse,
  InterpretResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ArbitrationError extends Error {
  status: number;
  verdict?: ChartVerdict;

  constructor(message: string, status: number, verdict?: ChartVerdict) {
    super(message);
    this.name = "ArbitrationError";
    this.status = status;
    this.verdict = verdict;
  }
}

async function handleResponseError(res: Response): Promise<never> {
  let detail = `Lỗi ${res.status}`;
  let verdict: ChartVerdict | undefined;

  try {
    const json = await res.json();
    if (typeof json.detail === "string") {
      detail = json.detail;
    } else if (json.detail && typeof json.detail === "object") {
      detail = json.detail.message || JSON.stringify(json.detail);
      verdict = json.detail.verdict;
    } else if (Array.isArray(json.detail)) {
      detail = json.detail.map((d: { msg: string }) => d.msg).join("; ");
    }
  } catch {
    // ignore json error
  }

  if (res.status === 409 || (res.status === 422 && verdict)) {
    throw new ArbitrationError(detail, res.status, verdict);
  }
  if (res.status === 400) throw new Error(`File không hợp lệ: ${detail}`);
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
  chartPref?: ChartType[] | ChartType | null,
  ack?: string[] | null,
  signal?: AbortSignal
): Promise<InterpretResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  form.append("mode", mode);
  if (chartPref) {
    if (Array.isArray(chartPref)) {
      form.append("chart_prefs", JSON.stringify(chartPref));
      if (chartPref.length > 0) {
        form.append("chart_pref", chartPref[0]);
      }
    } else {
      form.append("chart_pref", chartPref);
    }
  }
  if (ack && ack.length > 0) {
    form.append("ack", JSON.stringify(ack));
  }

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
  chartPref?: ChartType[] | ChartType | null,
  ack?: string[] | null,
  signal?: AbortSignal
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  form.append("expand_views", String(expandViews));
  if (goal) {
    form.append("goal", JSON.stringify(goal));
  }
  if (chartPref) {
    if (Array.isArray(chartPref)) {
      form.append("chart_prefs", JSON.stringify(chartPref));
      if (chartPref.length > 0) {
        form.append("chart_pref", chartPref[0]);
      }
    } else {
      form.append("chart_pref", chartPref);
    }
  }
  if (ack && ack.length > 0) {
    form.append("ack", JSON.stringify(ack));
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
  chartPref?: ChartType[] | ChartType | null,
  ack?: string[] | null,
  signal?: AbortSignal
): Promise<DeepenResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("goal", JSON.stringify(goal));
  form.append("level", level);
  if (chartPref) {
    if (Array.isArray(chartPref)) {
      form.append("chart_prefs", JSON.stringify(chartPref));
      if (chartPref.length > 0) {
        form.append("chart_pref", chartPref[0]);
      }
    } else {
      form.append("chart_pref", chartPref);
    }
  }
  if (ack && ack.length > 0) {
    form.append("ack", JSON.stringify(ack));
  }

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

/**
 * Gọi POST /render để chuyển đổi biểu đồ sang hình dạng dữ liệu khác (stateless, tất định).
 */
export async function renderChart(
  file: File,
  goal: AnalysisGoal,
  level: AnalysisLevel = "descriptive",
  chartType: ChartType,
  ack?: string[] | null,
  signal?: AbortSignal
): Promise<ChartSpec> {
  const form = new FormData();
  form.append("file", file);
  form.append("goal", JSON.stringify(goal));
  form.append("level", level);
  form.append("chart_type", chartType);
  if (ack && ack.length > 0) {
    form.append("ack", JSON.stringify(ack));
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/render`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new Error("Không kết nối được backend khi chuyển đổi biểu đồ.");
  }

  if (!res.ok) await handleResponseError(res);
  return res.json() as Promise<ChartSpec>;
}
