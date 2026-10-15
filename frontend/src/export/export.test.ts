import { describe, it, expect } from "vitest";
import { formatNumber, formatPercent, formatSignedChange, formatAxisDate } from "../utils/formatters";
import { buildCsv } from "./buildCsv";
import { buildReportModel } from "./buildReportModel";
import type { AnalyzeResponse, ChartSpec } from "../api/types";
import { ANALYSIS_MODES } from "../components/ModePicker";

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
    expect(formatAxisDate("Da Nang")).toBe("Da Nang");
  });
});

describe("CSV Export Generator (buildCsv.ts)", () => {
  const mockChart: ChartSpec = {
    chart_type: "bar",
    title: "Doanh thu theo chi nhánh",
    x: ["Hà Nội", "TP.HCM", "Đà Nẵng"],
    series: {
      "Doanh thu": [1200, 1500, 800],
    },
    highlight_x: null,
  };

  it("adds UTF-8 BOM at the beginning of CSV content", () => {
    const csv = buildCsv(mockChart);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
  });

  it("sanitizes CSV formula injection symbols (=, +, -, @)", () => {
    const injectionChart: ChartSpec = {
      chart_type: "bar",
      title: "Test Injection",
      x: ["=SUM(A1:A10)", "@cmd", "+123"],
      series: {
        "Giá trị": [10, 20, 30],
      },
      highlight_x: null,
    };

    const csv = buildCsv(injectionChart);
    expect(csv).toContain("'=SUM(A1:A10)");
    expect(csv).toContain("'@cmd");
    expect(csv).toContain("'+123");
  });

  it("handles null series values without crashing", () => {
    const forecastChart: ChartSpec = {
      chart_type: "line",
      title: "Dự báo",
      x: ["T1", "T2", "T3"],
      series: {
        "Thực tế": [100, 110, null],
        "Dự báo": [null, 110, 125],
      },
      highlight_x: null,
    };
    const csv = buildCsv(forecastChart);
    expect(csv).toContain("T1");
    expect(csv).toContain("100");
  });
});

describe("Report Model Builder (buildReportModel.ts)", () => {
  const sampleResponse: AnalyzeResponse = {
    goal: {
      question: "So sánh doanh thu chi nhánh?",
      time_scope: "all",
      time_start: "2026-01-01",
      time_end: "2026-12-31",
      tasks: [
        {
          type: "comparison",
          metric: "Doanh_thu",
          group_by: "Chi_nhanh",
          find: null,
          chart_hint: null,
        },
      ],
    },
    task_results: [],
    charts: [
      {
        chart_type: "bar",
        title: "Doanh thu theo chi nhánh",
        x: ["Hà Nội", "TP.HCM"],
        series: { "Doanh thu": [1200, 1500] },
        highlight_x: null,
        role: "primary",
      },
      {
        chart_type: "pie",
        title: "Tỷ trọng doanh thu",
        x: ["Hà Nội", "TP.HCM"],
        series: { "Tỷ trọng": [44.4, 55.6] },
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
      rows_total: 100,
      rows_used: 100,
      goal_summary: "So sánh doanh thu chi nhánh",
      notes: [],
      model_name: "gemini-2.5-flash",
      generated_at: "2026-10-12T10:00:00Z",
    },
  };

  it("builds full report model with all sections enabled", () => {
    const model = buildReportModel(
      sampleResponse,
      "doanh_thu.csv",
      {
        insight: true,
        primary_chart: true,
        supplementary_charts: true,
        data_tables: true,
        calculation_notes: true,
      },
      "Công ty ABC"
    );

    expect(model.orgName).toBe("Công ty ABC");
    expect(model.filename).toBe("doanh_thu.csv");
    expect(model.insightText).toBe("HCM dẫn đầu doanh thu.");
    expect(model.charts.length).toBe(2);
    expect(model.calculationNotes.length).toBeGreaterThan(0);
    expect(model.isLowConfidence).toBe(false);
  });

  it("handles null series values in report data tables gracefully", () => {
    const responseWithNulls: AnalyzeResponse = {
      ...sampleResponse,
      charts: [
        {
          chart_type: "line",
          title: "Dự báo doanh thu",
          x: ["T1", "T2", "T3"],
          series: {
            "Thực tế": [100, 110, null],
            "Dự báo": [null, 110, 125],
          },
          highlight_x: null,
          role: "primary",
          forecast_from: "T2",
        },
      ],
    };
    const model = buildReportModel(responseWithNulls, "data.csv", {});
    expect(model.charts[0].rows[0][2]).toBe("—"); // null converted to "—"
    expect(model.charts[0].rows[2][1]).toBe("—"); // null converted to "—"
    expect(model.charts[0].calculationNote).toContain("Ước tính dự báo chuỗi thời gian");
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

describe("ModePicker definition (ModePicker.tsx)", () => {
  it("defines exactly 5 modes with auto as first", () => {
    expect(ANALYSIS_MODES.length).toBe(5);
    expect(ANALYSIS_MODES[0].id).toBe("auto");
    expect(ANALYSIS_MODES.map((m) => m.id)).toEqual([
      "auto",
      "descriptive",
      "diagnostic",
      "forecast",
      "prescriptive",
    ]);
  });
});
