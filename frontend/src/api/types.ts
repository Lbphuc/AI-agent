/**
 * Kiểu dữ liệu API – mapping từ schemas.py của FastAPI backend.
 * Khớp với hệ thống phân tích sâu 3 cấp (Diagnostic, Forecast, Prescriptive)
 * và Chế độ phân tích dạng Pills (ModePicker).
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

export type AnalysisLevel = "descriptive" | "diagnostic" | "forecast" | "prescriptive";
export type AnalysisMode = "auto" | "descriptive" | "diagnostic" | "forecast" | "prescriptive";

export interface ModeAvailability {
  available: boolean;
  reason?: string | null;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  n_unique: number;
  n_missing: number;
  samples: string[];
  min?: string | null;
  max?: string | null;
  description?: string | null;
  semantic_type?: string | null;
  display_name?: string | null;
  unit?: string | null;
}

export interface DataProfile {
  row_count: number;
  columns: ColumnProfile[];
  time_column?: string | null;
  time_min?: string | null;
  time_max?: string | null;
  group_columns: string[];
  numeric_columns: string[];
  dataset_description?: string | null;
  frequency?: string | null;
  n_periods?: number | null;
  availability?: Record<string, ModeAvailability>;
}

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
  levels?: AnalysisLevel[];
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
  series: Record<string, (number | null)[]>;
  highlight_x: string | null;
  role?: ChartRole;
  perspective?: Perspective;
  caption?: string | null;
  highlight_series?: string | null;
  display_name?: string | null;
  unit?: string | null;
  band?: {
    lower: (number | null)[];
    upper: (number | null)[];
  } | null;
  forecast_from?: string | null;
}

export interface InsightResult {
  insight_text: string;
  confidence_score: number | null;
}

export interface ReportMeta {
  generated_at: string;
  model_name: string;
  rows_total: number;
  rows_used: number;
  goal_summary: string;
  notes: string[];
  deepen?: Record<string, ModeAvailability>;
}

export interface AnalyzeResponse {
  goal: AnalysisGoal;
  task_results: TaskResult[];
  charts: ChartSpec[];
  insight: InsightResult | null;
  meta?: ReportMeta | null;
}

export interface Notice {
  kind: "added" | "skipped" | "info";
  level?: AnalysisLevel | null;
  message: string;
}

export interface InterpretResponse {
  goal: AnalysisGoal;
  levels: AnalysisLevel[];
  notices: Notice[];
  goal_summary: string;
}

export interface Fact {
  id: string;
  kind: "total" | "contribution" | "driver" | "correlation" | "forecast" | "share";
  entity?: string | null;
  metric: string;
  value: number;
  unit?: string | null;
  period?: string | null;
  estimate?: boolean;
  text: string;
}

export interface Recommendation {
  title: string;
  action: string;
  rationale: string;
  fact_ids: string[];
  priority: "cao" | "trung bình" | "thấp";
  caveat: string;
}

export interface Section {
  level: AnalysisLevel;
  charts: ChartSpec[];
  narrative?: InsightResult | null;
  warnings: string[];
}

export interface DeepenResponse {
  level: AnalysisLevel;
  sections: Section[];
  recommendations: Recommendation[];
  facts: Fact[];
  warnings: string[];
}

export interface ExportSections {
  summary?: boolean;
  insight?: boolean;
  primary_chart?: boolean;
  supplementary_charts?: boolean;
  data_tables?: boolean;
  methodology?: boolean;
  calculation_notes?: boolean;
}

export interface ExportXlsxRequest {
  response: AnalyzeResponse;
  filename?: string;
  org_name?: string | null;
  sections?: ExportSections;
}

/** Lỗi trả về từ FastAPI (HTTPException detail) */
export interface ApiError {
  detail: string;
}
