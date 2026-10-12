import { describe, it, expect } from "vitest";
import { formatNumber, formatPercent, formatSignedChange, formatAxisDate } from "../utils/formatters";
import { buildCsv } from "./buildCsv";
import { buildReportModel } from "./buildReportModel";
import type { AnalyzeResponse, ChartSpec } from "../api/types";

describe("Vietnamese formatters (formatters.ts)", () => {
  it("formats standard numbers with dot as thousand separator", () => {
    expect(formatNumber(15000)).toBe("15.000");
    expect(formatNumber(1500000)).toBe("1.500.000");
    expect(formatNumber(0)).toBe("0");
  });

  it("formats decimal numbers with comma as decimal separator", () => {
    expect(formatNumber(1250.5, { decimals: 1 })).toBe("1.250,5");
    expect(formatNumber(42.85, { decimals: 2 })).toBe("42,85");
  });

  it("formats negative numbers with minus symbol", () => {
    expect(formatNumber(-320)).toBe("−320");
    expect(formatNumber(-1250.5, { decimals: 1 })).toBe("−1.250,5");
  });

  it("handles forced sign correctly", () => {
    expect(formatNumber(250, { forceSign: true })).toBe("+250");
    expect(formatNumber(-250, { forceSign: true })).toBe("−250");
  });

  it("handles null, undefined and NaN gracefully", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
  });

  it("formats percentages with % suffix", () => {
    expect(formatPercent(42.5)).toBe("42,5%");
    expect(formatPercent(-12.1, 1, true)).toBe("−12,1%");
    expect(formatPercent(null)).toBe("—");
  });

  it("formats signed changes with accessible icons ▲ and ▼", () => {
    const pos = formatSignedChange(250, "triệu VNĐ");
    expect(pos.isPositive).toBe(true);
    expect(pos.icon).toBe("▲");
    expect(pos.text).toContain("▲ +250 triệu VNĐ");

    const neg = formatSignedChange(-320, "triệu VNĐ");
    expect(neg.isNegative).toBe(true);
    expect(neg.icon).toBe("▼");
    expect(neg.text).toContain("▼ −320 triệu VNĐ");

    const zero = formatSignedChange(0, "triệu VNĐ");
    expect(zero.icon).toBe("—");
    expect(zero.text).toBe("0 triệu VNĐ");
  });

  it("formats axis date labels nicely", () => {
    expect(formatAxisDate("2026-01")).toBe("T1/26");
    expect(formatAxisDate("2026-08")).toBe("T8/26");
    expect(formatAxisDate("2026-01-15")).toBe("15/1");
    expect(formatAxisDate("Hà Nội")).toBe("Hà Nội");
  });
});

describe("CSV generator (buildCsv.ts)", () => {
  it("includes UTF-8 BOM at the beginning", () => {
    const chart: ChartSpec = {
      chart_type: "bar",
      title: "Test",
      x: ["Hà Nội", "Đà Nẵng"],
      series: { "Doanh thu": [100, 200] },
      highlight_x: null,
    };
    const csv = buildCsv(chart);
    expect(csv.startsWith("\uFEFF")).toBe(true);
  });

  it("escapes formula injection characters (=, +, -, @)", () => {
    const chart: ChartSpec = {
      chart_type: "bar",
      title: "Security Test",
      x: ["=1+1", "+cmd", "-calc", "@exec", "Normal"],
      series: { "Value": [1, 2, 3, 4, 5] },
      highlight_x: null,
    };
    const csv = buildCsv(chart);
    expect(csv).toContain("'=1+1");
    expect(csv).toContain("'+cmd");
    expect(csv).toContain("'-calc");
    expect(csv).toContain("'@exec");
    expect(csv).toContain("Normal");
  });

  it("escapes quotes and commas in cell text", () => {
    const chart: ChartSpec = {
      chart_type: "bar",
      title: "Quotes Test",
      x: ['Chi nhánh, "Khu vực 1"'],
      series: { "Doanh thu": [500] },
      highlight_x: null,
    };
    const csv = buildCsv(chart);
    expect(csv).toContain('"Chi nhánh, ""Khu vực 1"""');
  });
});

describe("Report Model Builder (buildReportModel.ts)", () => {
  const sampleResponse: AnalyzeResponse = {
    goal: {
      question: "So sánh doanh thu chi nhánh",
      time_scope: "last_12_months",
      time_start: "2026-01",
      time_end: "2026-08",
      tasks: [{ type: "comparison", metric: "Doanh_thu_trieu_vnd", group_by: "Chi_nhanh", find: null, chart_hint: null }],
    },
    task_results: [],
    charts: [
      {
        chart_type: "bar",
        title: "So sánh doanh thu theo chi nhánh",
        x: ["HN", "HCM"],
        series: { "Doanh thu": [1000, 2000] },
        highlight_x: null,
        role: "primary",
        display_name: "Doanh thu",
        unit: "triệu VNĐ",
      },
      {
        chart_type: "pie",
        title: "Tỷ trọng doanh thu",
        x: ["HN", "HCM"],
        series: { "Tỷ trọng (%)": [33.3, 66.7] },
        highlight_x: null,
        role: "supplementary",
        perspective: "share_of_total",
      },
    ],
    insight: {
      insight_text: "HCM dẫn đầu doanh thu.",
      confidence_score: 0.95,
    },
    meta: {
      generated_at: "2026-10-12T10:00:00Z",
      model_name: "Gemini AI",
      rows_total: 100,
      rows_used: 80,
      goal_summary: "So sánh doanh thu giữa các chi nhánh, từ 2026-01 đến 2026-08.",
      notes: ["Góc nhìn tỷ trọng hợp lệ"],
    },
  };

  it("builds full report model with all sections enabled", () => {
    const model = buildReportModel(sampleResponse, "doanh_thu.csv", {
      insight: true,
      primary_chart: true,
      supplementary_charts: true,
      data_tables: true,
      calculation_notes: true,
    }, "Công ty ABC");

    expect(model.orgName).toBe("Công ty ABC");
    expect(model.filename).toBe("doanh_thu.csv");
    expect(model.insightText).toBe("HCM dẫn đầu doanh thu.");
    expect(model.charts.length).toBe(2);
    expect(model.calculationNotes.length).toBeGreaterThan(0);
    expect(model.isLowConfidence).toBe(false);
  });

  it("filters out sections when set to false", () => {
    const model = buildReportModel(sampleResponse, "doanh_thu.csv", {
      insight: false,
      primary_chart: true,
      supplementary_charts: false,
      data_tables: false,
      calculation_notes: false,
    });

    expect(model.insightText).toBeUndefined();
    expect(model.charts.length).toBe(1); // Only primary chart
    expect(model.calculationNotes.length).toBe(0);
  });

  it("flags low confidence when confidence score < 0.8", () => {
    const lowConfResponse: AnalyzeResponse = {
      ...sampleResponse,
      insight: {
        insight_text: "Phân tích không chắc chắn.",
        confidence_score: 0.72,
      },
    };
    const model = buildReportModel(lowConfResponse, "data.csv", {});
    expect(model.isLowConfidence).toBe(true);
  });
});
