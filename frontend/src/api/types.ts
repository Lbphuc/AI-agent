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
export type ChartType =
  | "kpi"
  | "line"
  | "area"
  | "bar"
  | "bar_horizontal"
  | "pie"
  | "stacked_bar"
  | "waterfall"
  | "scatter"
  | "heatmap"
  | "box"
  | "histogram";

export type DataShape =
  | "kpi"
  | "category_series"
  | "waterfall"
  | "points"
  | "matrix"
  | "boxes"
  | "bins";

export interface Reason {
  code: string;
  severity: "block" | "confirm" | "info";
  message: string;
  suggest: ChartType[];
}

export interface ChartVerdict {
  status: "ok" | "confirm" | "blocked";
  chart_type: ChartType;
  reasons: Reason[];
  alternatives: ChartType[];
  requires_double_confirm?: boolean;
  confirm_step?: number;
}

export interface ChartOption {
  chart_type: ChartType;
  verdict: "recommended" | "ok" | "confirm" | "blocked";
  reasons: Reason[];
  requires_fetch: boolean;
}

export interface ChartCatalogItem {
  chart_type: ChartType;
  display_name: string;
  icon: string;
  status: "ready" | "soon";
  fitness: "recommended" | "ok" | "confirm" | "blocked";
  verdict: "ok" | "confirm" | "blocked";
  requires_double_confirm?: boolean;
  reasons: Reason[];
  data_shape: DataShape;
}

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
  chart_catalog?: Record<string, ChartCatalogItem[]>;
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

export interface WaterfallStep {
  name?: string;
  label?: string;
  value?: number;
  delta?: number;
  subtotal?: number;
  is_total?: boolean;
}

export interface ScatterPoint {
  name: string;
  x: number;
  y: number;
}

export interface HeatmapCell {
  x: string;
  y: string;
  value: number;
  intensity: number;
}

export interface HeatmapMatrix {
  x_labels: string[];
  y_labels: string[];
  cells: HeatmapCell[];
  min: number;
  max: number;
}

export interface BoxData {
  name: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean?: number;
  outliers?: number[];
}

export interface HistogramBin {
  label: string;
  bin_start: number;
  bin_end: number;
  count: number;
  percent: number;
}

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
  data_shape?: DataShape;
  selection?: "auto" | "user";
  notes?: string[];
  options?: ChartOption[];
  kpi_value?: number | null;
  kpi_delta?: number | null;
  kpi_delta_pct?: number | null;
  kpi_delta_percent?: number | null;
  kpi_period?: string | null;
  waterfall_steps?: WaterfallStep[] | null;
  scatter_points?: ScatterPoint[] | null;
  heatmap_matrix?: HeatmapMatrix | null;
  box_data?: BoxData[] | null;
  histogram_bins?: HistogramBin[] | null;
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
  chart_check?: ChartVerdict | null;
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
  meta?: {
    computed_in_sec?: number;
  } | null;
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
  detail: string | { message?: string; verdict?: ChartVerdict };
}
