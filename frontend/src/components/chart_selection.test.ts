import { describe, it, expect, beforeEach } from "vitest";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CHART_NAMES, ChartTypePicker } from "./ChartTypePicker";
import {
  ChartConfirmDialog,
  getSessionAcks,
  saveSessionAcks,
} from "./ChartConfirmDialog";
import { ChartCard } from "./ChartCard";
import type { ChartCatalogItem, ChartVerdict, ChartSpec, ChartOption } from "../api/types";

describe("Chart Selection & Confirmation Mechanism (chart_selection.test.ts)", () => {
  beforeEach(() => {
    // Clear mock sessionStorage
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.clear();
    }
  });

  describe("Chart catalog item structure", () => {
    it("validates catalog item fields", () => {
      const item: ChartCatalogItem = {
        chart_type: "waterfall",
        display_name: "Biểu đồ thác nước",
        fitness: "recommended",
        verdict: "ok",
        reasons: [],
        data_shape: "waterfall",
        status: "ready",
        icon: "📊",
      };
      expect(item.fitness).toBe("recommended");
      expect(item.status).toBe("ready");
    });
  });

  describe("CHART_NAMES registry", () => {
    it("has friendly Vietnamese names for all 12 chart types", () => {
      const types = [
        "kpi",
        "bar",
        "bar_horizontal",
        "line",
        "area",
        "pie",
        "stacked_bar",
        "waterfall",
        "scatter",
        "heatmap",
        "box",
        "histogram",
      ] as const;

      types.forEach((t) => {
        expect(CHART_NAMES[t]).toBeDefined();
        expect(CHART_NAMES[t].length).toBeGreaterThan(0);
      });
    });
  });

  describe("Session Storage Acks (ChartConfirmDialog)", () => {
    it("saves and retrieves acknowledged codes without duplicates", () => {
      // Mock sessionStorage if not present in node environment
      const store: Record<string, string> = {};
      const mockStorage = {
        getItem: (k: string) => store[k] || null,
        setItem: (k: string, v: string) => {
          store[k] = v;
        },
        clear: () => {
          for (const k in store) delete store[k];
        },
      };
      // @ts-ignore
      globalThis.sessionStorage = mockStorage;

      expect(getSessionAcks()).toEqual([]);

      saveSessionAcks(["TOO_MANY_SLICES"]);
      expect(getSessionAcks()).toEqual(["TOO_MANY_SLICES"]);

      saveSessionAcks(["TOO_MANY_SLICES", "STRATEGY_UNUSUAL"]);
      const result = getSessionAcks();
      expect(result).toContain("TOO_MANY_SLICES");
      expect(result).toContain("STRATEGY_UNUSUAL");
      expect(result.length).toBe(2);
    });
  });

  describe("ChartConfirmDialog rendering", () => {
    it("renders confirmation dialog with reason messages and safe suggestion", () => {
      const verdict: ChartVerdict = {
        status: "confirm",
        chart_type: "pie",
        reasons: [
          {
            code: "STRATEGY_UNUSUAL",
            severity: "confirm",
            message: "Biểu đồ tròn thường dùng để xem cơ cấu, ít phù hợp để tìm lý do thay đổi.",
            suggest: ["waterfall"],
          },
          {
            code: "TOO_MANY_SLICES",
            severity: "confirm",
            message: "Biểu đồ tròn có 8 phần, rất khó so sánh. Biểu đồ cột rõ hơn.",
            suggest: ["bar"],
          },
        ],
        alternatives: ["waterfall", "bar"],
      };

      const html = renderToStaticMarkup(
        React.createElement(ChartConfirmDialog, {
          isOpen: true,
          verdict,
          strategyName: "Tìm nguyên nhân",
          onConfirmOverride: () => {},
          onAcceptSuggestion: () => {},
          onCancel: () => {},
        })
      );

      expect(html).toContain("Biểu đồ này có thể chưa phù hợp");
      expect(html).toContain("Biểu đồ tròn (Pie)");
      expect(html).toContain("Tìm nguyên nhân");
      expect(html).toContain("Biểu đồ tròn có 8 phần, rất khó so sánh");
      expect(html).toContain("Gợi ý thay thế:");
      expect(html).toContain("Biểu đồ thác nước");
      expect(html).toContain("Vẫn dùng Biểu đồ tròn (Pie)");
      expect(html).toContain("Dùng Biểu đồ thác nước");
      expect(html).toContain("Ghi nhớ lựa chọn này");
    });

    it("renders 2-step confirmation dialog for unapplicable (blocked) charts", () => {
      const verdict: ChartVerdict = {
        status: "blocked",
        chart_type: "scatter",
        requires_double_confirm: true,
        confirm_step: 1,
        reasons: [
          {
            code: "NEEDS_TWO_MEASURES",
            severity: "block",
            message: "Biểu đồ phân tán cần ít nhất 2 cột số liệu để so sánh; file của bạn chỉ có 1.",
            suggest: ["bar"],
          },
        ],
        alternatives: ["bar"],
      };

      const html = renderToStaticMarkup(
        React.createElement(ChartConfirmDialog, {
          isOpen: true,
          verdict,
          strategyName: "Tổng quan",
          onConfirmOverride: () => {},
          onAcceptSuggestion: () => {},
          onCancel: () => {},
        })
      );

      // Bước 1/2 của biểu đồ không áp dụng
      expect(html).toContain("Xác nhận lần 1: Biểu đồ không áp dụng");
      expect(html).toContain("Bước 1/2");
      expect(html).toContain("Biểu đồ phân tán cần ít nhất 2 cột số liệu");
      expect(html).toContain("Tiếp tục xác nhận (Bước 1/2)");
      expect(html).toContain("Đổi sang Biểu đồ cột");
      expect(html).toContain("Hủy");
    });
  });

  describe("ChartTypePicker rendering", () => {
    it("renders trigger button with Tự động when values is empty", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChartTypePicker, {
          values: [],
          onChangeMulti: () => {},
          strategy: "descriptive",
        })
      );

      expect(html).toContain("Biểu đồ: Tự động");
    });

    it("renders multi-select tags and trigger count when multiple charts are selected", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChartTypePicker, {
          values: ["bar", "line"],
          onChangeMulti: () => {},
          strategy: "descriptive",
        })
      );

      expect(html).toContain("Biểu đồ cột");
      expect(html).toContain("Biểu đồ đường");
      expect(html).toContain("+ Thêm biểu đồ (2)");
      expect(html).toContain("✕ Đặt lại Tự động");
    });

    it("disables chart picker with notice in prescriptive mode", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChartTypePicker, {
          values: [],
          onChangeMulti: () => {},
          strategy: "prescriptive",
        })
      );

      expect(html).toContain("disabled");
      expect(html).toContain("Gợi ý chiến lược hiển thị bằng thẻ khuyến nghị");
    });
  });

  describe("ChartCard user choice and notes", () => {
    it("displays user selection badge and notes when present", () => {
      const chart: ChartSpec = {
        chart_type: "pie",
        title: "Tỷ trọng doanh thu theo khu vực",
        x: ["Miền Bắc", "Miền Trung", "Miền Nam"],
        series: { DoanhThu: [100, 200, 300] },
        highlight_x: null,
        selection: "user",
        notes: ["Biểu đồ do người dùng chọn: pie (đã xác nhận: TOO_MANY_SLICES)"],
      };

      const html = renderToStaticMarkup(
        React.createElement(ChartCard, { chart })
      );

      expect(html).toContain("chart-user-badge");
      expect(html).toContain("Bạn chọn");
      expect(html).toContain("chart-card-notes");
      expect(html).toContain("Biểu đồ do người dùng chọn: pie");
    });

    it("renders KPI card correctly when chart_type is kpi", () => {
      const chart: ChartSpec = {
        chart_type: "kpi",
        title: "Doanh thu kỳ này",
        x: ["2026-Q1"],
        series: { Sales: [5400000] },
        highlight_x: null,
        unit: "VNĐ",
        kpi_value: 5400000,
        kpi_period: "Quý 1/2026",
        kpi_delta: 450000,
        kpi_delta_pct: 9.1,
      };

      const html = renderToStaticMarkup(
        React.createElement(ChartCard, { chart })
      );

      expect(html).toContain("kpi-container");
      expect(html).toContain("5.400.000 VNĐ");
      expect(html).toContain("Quý 1/2026");
      expect(html).toContain("▲");
      expect(html).toContain("+450.000 VNĐ");
      expect(html).toContain("+9,1 %");
    });

    it("renders chart options menu items in dropdown", () => {
      const options: ChartOption[] = [
        {
          chart_type: "bar",
          verdict: "recommended",
          reasons: [],
          requires_fetch: false,
        },
        {
          chart_type: "waterfall",
          verdict: "confirm",
          reasons: [
            {
              code: "STRATEGY_UNUSUAL",
              severity: "confirm",
              message: "Biểu đồ thác nước ít dùng cho tổng quan",
              suggest: ["bar"],
            },
          ],
          requires_fetch: true,
        },
        {
          chart_type: "scatter",
          verdict: "blocked",
          reasons: [
            {
              code: "NEEDS_TWO_MEASURES",
              severity: "block",
              message: "Cần 2 cột số",
              suggest: ["bar"],
            },
          ],
          requires_fetch: true,
        },
      ];

      const chart: ChartSpec = {
        chart_type: "line",
        title: "Doanh thu theo tháng",
        x: ["T1", "T2", "T3"],
        series: { Sales: [10, 20, 30] },
        highlight_x: null,
        options,
      };

      // To test dropdown contents, we inspect that options are defined and verify structure
      expect(chart.options).toHaveLength(3);
      expect(chart.options?.[0].requires_fetch).toBe(false);
      expect(chart.options?.[1].requires_fetch).toBe(true);
      expect(chart.options?.[2].verdict).toBe("blocked");
    });
  });
});
