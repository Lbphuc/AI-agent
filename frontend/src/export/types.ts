import type { ChartSpec, ExportSections } from "../api/types";

export interface ReportChartItem {
  spec: ChartSpec;
  headers: string[];
  rows: (string | number)[][];
  calculationNote?: string;
}

export interface ReportModel {
  title: string;
  orgName?: string;
  filename: string;
  question: string;
  goalSummary: string;
  generatedAt: string;
  modelName: string;
  rowsInfo: string;
  insightText?: string;
  confidenceScore?: number | null;
  isLowConfidence: boolean;
  charts: ReportChartItem[];
  calculationNotes: { label: string; desc: string }[];
  sections: ExportSections;
}
