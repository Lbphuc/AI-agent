/**
 * Kiểu dữ liệu API – mapping từ schemas.py của FastAPI backend.
 * Được viết tay dựa theo AnalyzeResponse, ChartSpec, InsightResult, AnalysisGoal.
 * Khi backend thay đổi, cập nhật file này hoặc chạy:
 *   npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
 */

export type TaskType = "trend" | "comparison" | "growth_rate";
export type FindMode = "min" | "max";
export type TimeScope =
  | "all"
  | "last_3_months"
  | "last_6_months"
  | "last_12_months"
  | "custom";
export type ChartType = "line" | "area" | "bar" | "bar_horizontal" | "pie";
export type ChartHint = "area" | "pie";

export interface AnalysisTask {
  type: TaskType;
  metric: string;
  group_by: string | null;
  find: FindMode | null;
  chart_hint: ChartHint | null;
}

export interface AnalysisGoal {
  question: string;
  time_scope: TimeScope;
  time_start: string | null;
  time_end: string | null;
  tasks: AnalysisTask[];
}

export interface ExecutionResult {
  success: boolean;
  results: Record<string, unknown>;
  error: string | null;
  attempts: number;
  code: string | null;
}

export interface TaskResult {
  task: AnalysisTask;
  execution: ExecutionResult;
}

export type Perspective =
  | "primary"
  | "period_change"
  | "cumulative"
  | "moving_average"
  | "trend_by_group"
  | "share_of_total"
  | "contribution_to_change";

export type ChartRole = "primary" | "supplementary";

export interface ChartSpec {
  chart_type: ChartType;
  title: string;
  x: string[];
  series: Record<string, number[]>;
  highlight_x: string | null;
  role?: ChartRole;
  perspective?: Perspective;
  caption?: string | null;
  highlight_series?: string | null;
}

export interface InsightResult {
  insight_text: string;
  confidence_score: number | null;
}

export interface AnalyzeResponse {
  goal: AnalysisGoal;
  task_results: TaskResult[];
  charts: ChartSpec[];
  insight: InsightResult | null;
}

/** Lỗi trả về từ FastAPI (HTTPException detail) */
export interface ApiError {
  detail: string;
}
