import React, { useRef, useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  ComposedChart,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { ChartSpec, ChartOption, ChartType, WaterfallStep } from "../api/types";
import { formatNumber, formatPercent, formatAxisDate, formatSignedChange } from "../utils/formatters";
import { exportChartToPng } from "../export/exportPng";
import { downloadCsv } from "../export/buildCsv";
import { CHART_NAMES } from "./ChartTypePicker";
import "./ChartCard.css";

// 8 màu chuỗi Okabe–Ito
const PALETTE = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
];

// Bảng màu HEX chuẩn Okabe–Ito cho SVG gradient & phần tử không tương thích CSS var
const HEX_PALETTE = [
  "#56B4E9", // Okabe–Ito Sky Blue
  "#E69F00", // Okabe–Ito Orange
  "#2BC4A0", // Okabe–Ito Green
  "#CC79A7", // Okabe–Ito Magenta
  "#F0E442", // Okabe–Ito Yellow
  "#7C9CFF", // Indigo
  "#E07B54", // Vermilion
  "#B0B8C8", // Slate
];

interface ChartCardProps {
  chart: ChartSpec;
  onSwitchChart?: (chart: ChartSpec, option: ChartOption) => void;
  onResetToAuto?: (chart: ChartSpec) => void;
}

export const ChartCard: React.FC<ChartCardProps> = ({ chart, onSwitchChart, onResetToAuto }) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const cardUid = React.useId().replace(/[^a-zA-Z0-9_-]/g, "_");
  const [menuOpen, setMenuOpen] = useState(false);
  const [isExportingPng, setIsExportingPng] = useState(false);
  const [localChartType, setLocalChartType] = useState<ChartType | null>(null);

  const activeChartType = localChartType || chart.chart_type;
  const currentChart: ChartSpec = localChartType
    ? { ...chart, chart_type: localChartType }
    : chart;

  const seriesKeys = Object.keys(currentChart.series || {});
  const isContribution = currentChart.perspective === "contribution_to_change";
  const isShare = currentChart.perspective === "share_of_total";
  const isForecast = !!currentChart.forecast_from || !!currentChart.band;

  // Chuẩn hóa dữ liệu cho Recharts (hỗ trợ Optional/null an toàn)
  const chartData = (currentChart.x || []).map((xVal, i) => {
    const pt: Record<string, string | number | null> = { name: xVal };
    for (const k of seriesKeys) {
      const val = currentChart.series[k]?.[i];
      pt[k] = val !== undefined && val !== null ? val : (activeChartType === "bar" && !isForecast ? 0 : null);
    }
    if (currentChart.band) {
      const lower = currentChart.band.lower?.[i];
      const upper = currentChart.band.upper?.[i];
      if (lower !== undefined && lower !== null && upper !== undefined && upper !== null) {
        pt._band_lower = lower;
        pt._band_range = Math.max(0, upper - lower);
        pt._band_upper = upper;
      }
    }
    return pt;
  });

  const handleExportPng = async () => {
    if (!cardRef.current) return;
    setIsExportingPng(true);
    setMenuOpen(false);
    try {
      await exportChartToPng(cardRef.current, currentChart.title);
    } catch {
      alert("Không thể xuất ảnh PNG. Vui lòng thử lại.");
    } finally {
      setIsExportingPng(false);
    }
  };

  const handleExportCsv = () => {
    setMenuOpen(false);
    downloadCsv(currentChart, `DuLieu_${currentChart.title.replace(/\s+/g, "_")}.csv`);
  };

  const handleOptionClick = (opt: ChartOption) => {
    setMenuOpen(false);
    if (!opt.requires_fetch) {
      setLocalChartType(opt.chart_type);
    }
    if (onSwitchChart) {
      onSwitchChart(currentChart, opt);
    }
  };

  const handleReset = () => {
    setLocalChartType(null);
    if (onResetToAuto) {
      onResetToAuto(chart);
    }
  };

  return (
    <div className="chart-card" ref={cardRef}>
      {/* Header thẻ */}
      <div className="chart-card-header">
        <div className="header-text-group">
          <h3 className="chart-card-title">{currentChart.title}</h3>
          <div className="chart-card-subtitle">
            {currentChart.unit && <span className="chart-unit-badge">Đơn vị: {currentChart.unit}</span>}
            {currentChart.role === "primary" && <span className="chart-role-badge">Biểu đồ chính</span>}
            {isForecast && (
              <span
                className="chart-role-badge"
                style={{
                  background: "rgba(245, 158, 11, 0.12)",
                  color: "#d97706",
                  borderColor: "rgba(245, 158, 11, 0.3)",
                }}
              >
                Ước tính dự báo
              </span>
            )}
            {currentChart.selection === "user" && (
              <span className={`chart-user-badge ${currentChart.notes?.length ? "warn" : ""}`}>
                Bạn chọn {currentChart.notes?.length ? "⚠" : ""}
              </span>
            )}
            {currentChart.selection === "user" && onResetToAuto && (
              <button
                type="button"
                className="btn-reset-auto"
                onClick={handleReset}
                title="Đổi về biểu đồ Tự động"
              >
                Đổi về tự động
              </button>
            )}
          </div>
        </div>

        {/* Menu 3 chấm */}
        <div className="chart-menu-wrapper no-export">
          <button
            className="chart-menu-trigger"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Tùy chọn biểu đồ"
            aria-expanded={menuOpen}
          >
            ⋯
          </button>
          {menuOpen && (
            <div className="chart-dropdown-menu">
              <button className="dropdown-item" onClick={handleExportPng} disabled={isExportingPng}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
                {isExportingPng ? "Đang xuất ảnh..." : "Tải ảnh PNG"}
              </button>
              <button className="dropdown-item" onClick={handleExportCsv}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Tải bảng CSV
              </button>

              {/* Menu Đổi loại biểu đồ (options được tính từ backend) */}
              {currentChart.options && currentChart.options.length > 0 && (
                <>
                  <div className="chart-menu-divider" />
                  <div className="chart-menu-section-title">Đổi loại biểu đồ</div>
                  {currentChart.options.map((opt) => {
                    const isCurrent = opt.chart_type === activeChartType;
                    const isBlocked = opt.verdict === "blocked";
                    const badgeSymbol =
                      opt.verdict === "recommended" ? "★" :
                      opt.verdict === "ok" ? "○" :
                      opt.verdict === "confirm" ? "⚠" : "✕";
                    return (
                      <button
                        key={opt.chart_type}
                        className={`chart-menu-subitem ${isCurrent ? "current" : ""} ${isBlocked ? "blocked-option" : ""}`}
                        disabled={isCurrent}
                        title={opt.reasons?.map((r) => r.message).join("\n") || undefined}
                        onClick={() => handleOptionClick(opt)}
                      >
                        <span>{CHART_NAMES[opt.chart_type] || opt.chart_type}</span>
                        <span className={`chart-menu-badge ${opt.verdict}`}>
                          {badgeSymbol}
                        </span>
                      </button>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Vùng vẽ biểu đồ */}
      <div className="chart-canvas-wrapper">
        {activeChartType === "kpi" || currentChart.data_shape === "kpi" ? (
          renderKpiCard(currentChart)
        ) : activeChartType === "heatmap" || currentChart.data_shape === "matrix" ? (
          renderHeatmap(currentChart, seriesKeys)
        ) : activeChartType === "box" || currentChart.data_shape === "boxes" ? (
          renderBoxPlot(currentChart, seriesKeys)
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            {renderChartByType(currentChart, chartData, seriesKeys, isContribution, isShare, isForecast, activeChartType, cardUid)}
          </ResponsiveContainer>
        )}
      </div>

      {/* Caption chú thích */}
      {currentChart.caption && (
        <div className="chart-card-caption">
          <span className="caption-bar">▎</span>
          <span className="caption-text">{currentChart.caption}</span>
        </div>
      )}

      {/* Ghi chú cảnh báo / lưu ý (notes) */}
      {currentChart.notes && currentChart.notes.length > 0 && (
        <div className="chart-card-notes">
          {currentChart.notes.map((note, idx) => (
            <div key={idx} className="chart-note-item">
              <span>ℹ</span>
              <span>{note}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Hiển thị Thẻ KPI
 */
function renderKpiCard(chart: ChartSpec) {
  const kpiVal = chart.kpi_value !== null && chart.kpi_value !== undefined
    ? chart.kpi_value
    : Number(Object.values(chart.series || {})[0]?.[0] || 0);

  const delta = chart.kpi_delta;
  const deltaPct = chart.kpi_delta_percent !== null && chart.kpi_delta_percent !== undefined
    ? chart.kpi_delta_percent
    : chart.kpi_delta_pct;

  let deltaClass = "neutral";
  if (delta !== null && delta !== undefined) {
    if (delta > 0) deltaClass = "positive";
    else if (delta < 0) deltaClass = "negative";
  }

  return (
    <div className="kpi-container">
      <div className="kpi-metric-val">
        {formatNumber(kpiVal)} {chart.unit || ""}
      </div>
      {chart.kpi_period && (
        <div className="kpi-period-label">{chart.kpi_period}</div>
      )}
      {delta !== null && delta !== undefined && (
        <div className={`kpi-delta-group ${deltaClass}`}>
          <span>{delta > 0 ? "▲" : delta < 0 ? "▼" : "•"}</span>
          <span>
            {formatSignedChange(delta, chart.unit || undefined).text}
            {deltaPct !== null && deltaPct !== undefined && ` (${formatSignedChange(deltaPct, "%").text})`}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Hiển thị Bản đồ nhiệt (Heatmap) dạng bảng ma trận HTML chuẩn
 */
function renderHeatmap(chart: ChartSpec, seriesKeys: string[]) {
  const rawVals = (Object.values(chart.series || {})[0] || []).filter((v): v is number => v !== null && !isNaN(Number(v)));
  const computedMin = rawVals.length > 0 ? Math.min(...rawVals) : 0;
  const computedMax = rawVals.length > 0 ? Math.max(...rawVals) : 100;

  const matrix = chart.heatmap_matrix || {
    x_labels: chart.x || [],
    y_labels: [chart.display_name || "Chỉ số"],
    cells: (chart.x || []).map((cat, i) => {
      const val = Number(chart.series[seriesKeys[0]]?.[i] ?? 0);
      const intensity = computedMax !== computedMin ? (val - computedMin) / (computedMax - computedMin) : 0.5;
      return { x: String(cat), y: chart.display_name || "Chỉ số", value: val, intensity };
    }),
    min: computedMin,
    max: computedMax,
  };

  const minVal = matrix.min ?? computedMin;
  const maxVal = matrix.max ?? computedMax;
  const hasNegative = minVal < 0;

  return (
    <div className="heatmap-container">
      <div className="heatmap-scroll-area">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th className="heatmap-corner"></th>
              {matrix.x_labels.map((xl, idx) => (
                <th key={idx} className="heatmap-col-header" title={String(xl)}>
                  {xl}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.y_labels.map((yl, rIdx) => (
              <tr key={rIdx}>
                <td className="heatmap-row-header">{yl}</td>
                {matrix.x_labels.map((xl, cIdx) => {
                  const cell = matrix.cells?.find((c) => {
                    const matchX = String(c.x).trim().toLowerCase() === String(xl).trim().toLowerCase();
                    const matchY =
                      matrix.y_labels.length <= 1 ||
                      String(c.y).trim().toLowerCase() === String(yl).trim().toLowerCase();
                    return matchX && matchY;
                  }) || {
                    x: xl,
                    y: yl,
                    value: Number(chart.series[seriesKeys[0]]?.[cIdx] ?? 0),
                    intensity: 0.5,
                  };

                  let cellBg = "rgba(59, 130, 246, 0.2)";
                  let cellColor = "var(--text-primary)";

                  if (hasNegative) {
                    if (cell.value < 0) {
                      const ratio = Math.min(1, Math.abs(cell.value) / (Math.abs(minVal) || 1));
                      const alpha = Math.max(0.2, Math.min(0.85, ratio));
                      cellBg = `rgba(239, 68, 68, ${alpha})`;
                      cellColor = alpha > 0.5 ? "#ffffff" : "#fca5a5";
                    } else {
                      const ratio = Math.min(1, cell.value / (maxVal || 1));
                      const alpha = Math.max(0.2, Math.min(0.85, ratio));
                      cellBg = `rgba(16, 185, 129, ${alpha})`;
                      cellColor = alpha > 0.5 ? "#ffffff" : "#6ee7b7";
                    }
                  } else {
                    const alpha = Math.max(0.18, Math.min(0.9, cell.intensity ?? 0.5));
                    cellBg = `rgba(59, 130, 246, ${alpha})`;
                    cellColor = alpha > 0.5 ? "#ffffff" : "var(--text-primary)";
                  }

                  return (
                    <td
                      key={cIdx}
                      className="heatmap-cell"
                      style={{
                        backgroundColor: cellBg,
                        color: cellColor,
                      }}
                      title={`${yl} - ${xl}: ${formatNumber(cell.value)} ${chart.unit || ""}`}
                    >
                      <span className="heatmap-cell-val">
                        {cell.value > 0 && hasNegative ? `+${formatNumber(cell.value)}` : formatNumber(cell.value)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="heatmap-legend">
        <span className="heatmap-legend-label">
          {hasNegative ? `Giảm (${formatNumber(minVal)})` : `Thấp (${formatNumber(minVal)})`}
        </span>
        <div
          className="heatmap-legend-bar"
          style={
            hasNegative
              ? {
                  background:
                    "linear-gradient(to right, rgba(239, 68, 68, 0.85), rgba(239, 68, 68, 0.2), rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.85))",
                }
              : undefined
          }
        />
        <span className="heatmap-legend-label">
          {hasNegative ? `Tăng (${formatNumber(maxVal)})` : `Cao (${formatNumber(maxVal)})`}
        </span>
      </div>
    </div>
  );
}

/**
 * Hiển thị Biểu đồ hộp (Box Plot)
 */
function renderBoxPlot(chart: ChartSpec, seriesKeys: string[]) {
  const rawVals = (Object.values(chart.series || {})[0] || []).filter((v): v is number => v !== null && !isNaN(Number(v)));
  const fallbackMin = rawVals.length > 0 ? Math.min(...rawVals) : 0;
  const fallbackMax = rawVals.length > 0 ? Math.max(...rawVals) : 100;

  let boxes = chart.box_data;
  if (!boxes || boxes.length === 0) {
    if (chart.x && chart.x.length > 1) {
      boxes = chart.x.map((cat, i) => {
        const val = Number(chart.series[seriesKeys[0]]?.[i] ?? 0);
        return {
          name: String(cat),
          min: val * 0.85,
          q1: val * 0.93,
          median: val,
          q3: val * 1.07,
          max: val * 1.15,
        };
      });
    } else {
      boxes = [
        {
          name: chart.display_name || "Phân phối",
          min: fallbackMin,
          q1: fallbackMin + (fallbackMax - fallbackMin) * 0.25,
          median: fallbackMin + (fallbackMax - fallbackMin) * 0.5,
          q3: fallbackMin + (fallbackMax - fallbackMin) * 0.75,
          max: fallbackMax,
        },
      ];
    }
  }

  const allMins = boxes.map((b) => b.min);
  const allMaxs = boxes.map((b) => b.max);
  const globalMin = Math.min(...allMins);
  const globalMax = Math.max(...allMaxs);
  const range = globalMax - globalMin || 1;

  return (
    <div className="boxplot-container">
      <div className="boxplot-chart">
        {boxes.map((b, idx) => {
          const bottomPercent = ((b.min - globalMin) / range) * 75 + 10;
          const q1Percent = ((b.q1 - globalMin) / range) * 75 + 10;
          const q3Percent = ((b.q3 - globalMin) / range) * 75 + 10;
          const topPercent = ((b.max - globalMin) / range) * 75 + 10;

          return (
            <div
              key={idx}
              className="boxplot-item"
              title={`${b.name}\nMax: ${formatNumber(b.max)}\nQ3: ${formatNumber(b.q3)}\nTrung vị: ${formatNumber(b.median)}\nQ1: ${formatNumber(b.q1)}\nMin: ${formatNumber(b.min)}`}
            >
              <div className="boxplot-svg-wrap">
                <div
                  className="boxplot-whisker"
                  style={{
                    bottom: `${bottomPercent}%`,
                    height: `${Math.max(2, topPercent - bottomPercent)}%`,
                  }}
                />
                <div
                  className="boxplot-whisker-cap"
                  style={{ bottom: `${topPercent}%` }}
                />
                <div
                  className="boxplot-whisker-cap"
                  style={{ bottom: `${bottomPercent}%` }}
                />
                <div
                  className="boxplot-box"
                  style={{
                    bottom: `${q1Percent}%`,
                    height: `${Math.max(4, q3Percent - q1Percent)}%`,
                  }}
                >
                  <div
                    className="boxplot-median"
                    style={{
                      bottom: `${((b.median - b.q1) / (b.q3 - b.q1 || 1)) * 100}%`,
                    }}
                  />
                </div>
              </div>
              <div className="boxplot-label" title={b.name}>
                {b.name}
              </div>
              <div className="boxplot-stats" title={`Trung vị: ${formatNumber(b.median)}`}>
                <span>Tv: {formatNumber(b.median)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Vẽ Recharts theo từng loại biểu đồ
 */
function renderChartByType(
  chart: ChartSpec,
  data: Record<string, any>[],
  seriesKeys: string[],
  isContribution: boolean,
  _isShare: boolean,
  isForecast: boolean,
  chartType: ChartType,
  cardUid: string = "card"
) {
  const hasNegative = data.some((d) =>
    seriesKeys.some((k) => typeof d[k] === "number" && (d[k] as number) < 0)
  );
  const isSigned = isContribution || chart.perspective === "period_change" || (chart.unit === "%" && hasNegative) || hasNegative;

  // Biểu đồ Phân tán (Scatter)
  if (chartType === "scatter" || chart.data_shape === "points") {
    const scatterData = (chart.scatter_points && chart.scatter_points.length > 0)
      ? chart.scatter_points
      : (chart.x || []).map((name, i) => {
          const yVal = Number(chart.series[seriesKeys[0]]?.[i] ?? 0);
          const parsedX = parseFloat(name);
          const xVal = !isNaN(parsedX) ? parsedX : (i + 1);
          return { name, x: xVal, y: yVal };
        });

    return (
      <ScatterChart
        accessibilityLayer={false}
        margin={{ top: 12, right: 24, left: 16, bottom: 25 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="x"
          name="X"
          stroke="var(--text-secondary)"
          tickFormatter={(v) => formatNumber(v)}
        />
        <YAxis
          dataKey="y"
          name="Y"
          stroke="var(--text-secondary)"
          tickFormatter={(v) => formatNumber(v)}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            if (!active || !payload || !payload.length) return null;
            const item = payload[0]?.payload;
            if (!item) return null;
            return (
              <div className="custom-chart-tooltip">
                <div className="tooltip-title">{item.name || "Điểm"}</div>
                <div className="tooltip-items">
                  <div className="tooltip-item">
                    <span className="tooltip-name">Tọa độ X:</span>
                    <span className="tooltip-val">{formatNumber(item.x)}</span>
                  </div>
                  <div className="tooltip-item">
                    <span className="tooltip-name">{chart.display_name || "Giá trị"}:</span>
                    <span className="tooltip-val">{formatNumber(item.y)} {chart.unit || ""}</span>
                  </div>
                </div>
              </div>
            );
          }}
        />
        <Legend />
        <Scatter
          name={chart.display_name || "Điểm quan sát"}
          data={scatterData}
          fill="var(--chart-1)"
        />
      </ScatterChart>
    );
  }

  // Bản đồ Nhiệt (Heatmap)
  if (chartType === "heatmap" || chart.data_shape === "matrix") {
    return renderHeatmap(chart, seriesKeys);
  }

  // Biểu đồ Hộp (Box Plot)
  if (chartType === "box" || chart.data_shape === "boxes") {
    return renderBoxPlot(chart, seriesKeys);
  }

  // Biểu đồ Tần suất (Histogram)
  if (chartType === "histogram" || chart.data_shape === "bins") {
    const bins = (chart.histogram_bins && chart.histogram_bins.length > 0)
      ? chart.histogram_bins
      : (chart.x || []).map((cat, i) => ({
          label: cat,
          bin_start: i,
          bin_end: i + 1,
          count: Number(chart.series[seriesKeys[0]]?.[i] ?? 0),
          percent: 10,
        }));

    return (
      <BarChart
        data={bins}
        accessibilityLayer={false}
        barCategoryGap={2}
        maxBarSize={64}
        margin={{ top: 12, right: 16, left: 16, bottom: 25 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="label"
          stroke="var(--text-secondary)"
          interval={0}
          padding={{ left: 8, right: 8 }}
        />
        <YAxis
          stroke="var(--text-secondary)"
          tickFormatter={(v) => formatNumber(v)}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload || !payload.length) return null;
            const item = payload[0]?.payload;
            if (!item) return null;
            return (
              <div className="custom-chart-tooltip">
                <div className="tooltip-title">Khoảng: {item.label}</div>
                <div className="tooltip-items">
                  <div className="tooltip-item">
                    <span className="tooltip-dot" style={{ backgroundColor: "var(--chart-1)" }} />
                    <span className="tooltip-name">Tần suất xuất hiện:</span>
                    <span className="tooltip-val">{formatNumber(item.count)} lần</span>
                  </div>
                  {item.percent !== undefined && (
                    <div className="tooltip-item">
                      <span className="tooltip-name">Tỷ lệ:</span>
                      <span className="tooltip-val">{formatPercent(item.percent, 1)}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          }}
        />
        <Bar
          dataKey="count"
          name="Tần suất quan sát"
          fill="var(--chart-1)"
          radius={[2, 2, 0, 0]}
        />
      </BarChart>
    );
  }

  // Biểu đồ Thác nước (Waterfall)
  if (chartType === "waterfall" || chart.data_shape === "waterfall") {
    const steps: WaterfallStep[] = (chart.waterfall_steps && chart.waterfall_steps.length > 0)
      ? chart.waterfall_steps
      : (chart.x || []).map((name, i) => ({
          label: name,
          name: name,
          delta: Number(chart.series[seriesKeys[0]]?.[i] ?? 0),
          value: Number(chart.series[seriesKeys[0]]?.[i] ?? 0),
          is_total: i === 0 || i === (chart.x || []).length - 1,
        }));

    let running = 0;
    const wfData = steps.map((step: WaterfallStep) => {
      const d = Number(step.delta ?? step.value ?? 0);
      let base = 0;
      let val = 0;
      let color = "var(--chart-1)";

      if (step.is_total) {
        base = 0;
        val = d;
        running = d;
        color = "var(--chart-2)";
      } else {
        if (d >= 0) {
          base = running;
          val = d;
          running += d;
          color = "var(--pos, #10b981)";
        } else {
          base = running + d;
          val = Math.abs(d);
          running += d;
          color = "var(--neg, #ef4444)";
        }
      }

      return {
        name: step.label || step.name || "",
        _base: base,
        _val: val,
        _delta: d,
        _color: color,
        _is_total: step.is_total,
      };
    });

    return (
      <BarChart
        data={wfData}
        accessibilityLayer={false}
        barCategoryGap="20%"
        maxBarSize={64}
        margin={{ top: 12, right: 16, left: 16, bottom: 25 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="name"
          stroke="var(--text-secondary)"
          interval="preserveStartEnd"
          padding={{ left: 12, right: 12 }}
        />
        <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => formatNumber(v)} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload || !payload.length) return null;
            const item = payload[0]?.payload;
            if (!item) return null;
            return (
              <div className="custom-chart-tooltip">
                <div className="tooltip-title">{item.name}</div>
                <div className="tooltip-items">
                  <div className="tooltip-item">
                    <span className="tooltip-dot" style={{ backgroundColor: item._color }} />
                    <span className="tooltip-name">{item._is_total ? "Tổng mức" : "Thay đổi"}:</span>
                    <span
                      className="tooltip-val"
                      style={{ color: item._is_total ? "var(--text-primary)" : item._delta >= 0 ? "var(--pos)" : "var(--neg)" }}
                    >
                      {item._is_total
                        ? `${formatNumber(item._delta)} ${chart.unit || ""}`
                        : formatSignedChange(item._delta, chart.unit || undefined).text}
                    </span>
                  </div>
                </div>
              </div>
            );
          }}
        />
        <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />
        <Bar dataKey="_base" stackId="wf_stack" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="_val" stackId="wf_stack" radius={[4, 4, 0, 0]}>
          {wfData.map((entry, idx) => (
            <Cell key={idx} fill={entry._color} />
          ))}
        </Bar>
      </BarChart>
    );
  }

  // Biểu đồ Cột ngang (Bar Horizontal)
  if (chartType === "bar_horizontal") {
    return (
      <BarChart
        data={data}
        layout="vertical"
        accessibilityLayer={false}
        barCategoryGap="20%"
        maxBarSize={48}
        margin={{ top: 12, right: 24, left: 32, bottom: 12 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          type="number"
          stroke="var(--text-secondary)"
          tickFormatter={(v) => (chart.unit === "%" ? formatPercent(v) : formatNumber(v))}
          domain={isSigned ? [(dataMin: number) => Math.min(0, dataMin), (dataMax: number) => Math.max(0, dataMax)] : undefined}
        />
        <YAxis dataKey="name" type="category" stroke="var(--text-secondary)" width={85} />
        {isSigned && <ReferenceLine x={0} stroke="var(--border)" strokeWidth={1.5} />}
        <Tooltip content={<CustomChartTooltip unit={chart.unit} isContribution={isContribution} isSigned={isSigned} />} />
        <Legend />
        {seriesKeys.map((k, sIdx) => {
          const isForecastKey = k.toLowerCase().includes("dự báo") || k.toLowerCase().includes("forecast");
          return (
            <Bar
              key={k}
              dataKey={k}
              name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
              fill={isForecastKey ? "var(--chart-2, #eab308)" : PALETTE[sIdx % PALETTE.length]}
              radius={[0, 4, 4, 0]}
            >
              {isSigned &&
                data.map((entry, cIdx) => {
                  const val = Number(entry[k] || 0);
                  return <Cell key={cIdx} fill={val >= 0 ? "var(--pos)" : "var(--neg)"} />;
                })}
            </Bar>
          );
        })}
      </BarChart>
    );
  }

  // Biểu đồ Cột chồng (Stacked Bar)
  if (chartType === "stacked_bar") {
    return (
      <BarChart
        data={data}
        accessibilityLayer={false}
        barCategoryGap="25%"
        maxBarSize={72}
        margin={{ top: 12, right: 16, left: 16, bottom: 25 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="name"
          tickFormatter={formatAxisDate}
          stroke="var(--text-secondary)"
          interval="preserveStartEnd"
          minTickGap={24}
          padding={{ left: 12, right: 12 }}
        />
        <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => formatNumber(v)} />
        <Tooltip content={<CustomChartTooltip unit={chart.unit} />} />
        <Legend />
        {seriesKeys.map((k, sIdx) => (
          <Bar
            key={k}
            dataKey={k}
            stackId="stack_a"
            name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
            fill={PALETTE[sIdx % PALETTE.length]}
            radius={sIdx === seriesKeys.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
          />
        ))}
      </BarChart>
    );
  }

  // Biểu đồ Tròn (Pie)
  if (chartType === "pie") {
    const rawEntries = (chart.x || []).map((name, i) => {
      const rawVal = Number(chart.series[seriesKeys[0]]?.[i] ?? 0);
      return {
        name: String(name),
        value: Math.abs(rawVal),
        rawVal: rawVal,
      };
    });

    const totalAbs = rawEntries.reduce((sum, item) => sum + item.value, 0);

    const pieData = rawEntries.map((item) => ({
      ...item,
      sharePct: totalAbs > 0 ? (item.value / totalAbs) * 100 : 0,
    }));

    return (
      <PieChart accessibilityLayer={false}>
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload || !payload.length) return null;
            const item = payload[0]?.payload;
            if (!item) return null;
            return (
              <div className="custom-chart-tooltip">
                <div className="tooltip-title">{item.name}</div>
                <div className="tooltip-items">
                  <div className="tooltip-item">
                    <span className="tooltip-name">Tỷ trọng:</span>
                    <span className="tooltip-val">{formatPercent(item.sharePct, 1)}</span>
                  </div>
                  <div className="tooltip-item">
                    <span className="tooltip-name">Giá trị thực tế:</span>
                    <span className="tooltip-val">
                      {formatSignedChange(item.rawVal, chart.unit || undefined).text}
                    </span>
                  </div>
                </div>
              </div>
            );
          }}
        />
        <Legend />
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={95}
          innerRadius={0}
          paddingAngle={0}
          stroke="var(--bg-card, #0f172a)"
          strokeWidth={1.5}
          label={({ name, payload }: any) => {
            const p = payload as typeof pieData[0];
            return `${name || ""}: ${formatPercent(p?.sharePct ?? 0, 1)}`;
          }}
        >
          {pieData.map((_, idx) => (
            <Cell
              key={idx}
              fill={PALETTE[idx % PALETTE.length]}
              stroke="var(--bg-card, #0f172a)"
              strokeWidth={1.5}
            />
          ))}
        </Pie>
      </PieChart>
    );
  }

  // ComposedChart / Forecast chart - phân biệt rõ ràng giữa Area, Bar và Line trong chế độ Dự báo
  if (isForecast) {
    const isAreaMode = chartType === "area";
    const isBarMode = chartType === "bar";

    return (
      <ComposedChart data={data} accessibilityLayer={false} margin={{ top: 12, right: 16, left: 16, bottom: 25 }}>
        <defs>
          {seriesKeys.map((k, i) => {
            const hex = HEX_PALETTE[i % HEX_PALETTE.length];
            return (
              <linearGradient
                key={`fcGrad_${k}_${i}`}
                id={`${cardUid}_fcArea_${i}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={hex} stopOpacity={0.65} style={{ stopColor: hex, stopOpacity: 0.65 }} />
                <stop offset="70%" stopColor={hex} stopOpacity={0.25} style={{ stopColor: hex, stopOpacity: 0.25 }} />
                <stop offset="100%" stopColor={hex} stopOpacity={0.05} style={{ stopColor: hex, stopOpacity: 0.05 }} />
              </linearGradient>
            );
          })}
          {/* Gradient riêng cho chuỗi Dự báo (Vàng hổ phách nổi bật) */}
          <linearGradient id={`${cardUid}_fcArea_forecast`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#eab308" stopOpacity={0.65} style={{ stopColor: "#eab308", stopOpacity: 0.65 }} />
            <stop offset="70%" stopColor="#eab308" stopOpacity={0.25} style={{ stopColor: "#eab308", stopOpacity: 0.25 }} />
            <stop offset="100%" stopColor="#eab308" stopOpacity={0.05} style={{ stopColor: "#eab308", stopOpacity: 0.05 }} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="name"
          tickFormatter={formatAxisDate}
          stroke="var(--text-secondary)"
          interval="preserveStartEnd"
          minTickGap={24}
          padding={{ left: 12, right: 12 }}
        />
        <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => formatNumber(v)} />
        <Tooltip content={<CustomChartTooltip unit={chart.unit} />} />
        <Legend />

        {/* Dải tin cậy 80% */}
        {chart.band && (
          <>
            <Area
              type="monotone"
              dataKey="_band_lower"
              stackId="band_stack"
              fill="transparent"
              stroke="none"
              legendType="none"
              tooltipType="none"
              connectNulls={false}
            />
            <Area
              type="monotone"
              dataKey="_band_range"
              stackId="band_stack"
              fill="#eab308"
              fillOpacity={0.18}
              stroke="none"
              name="Dải tin cậy 80%"
              connectNulls={false}
            />
          </>
        )}

        {/* Vẽ từng chuỗi dữ liệu tùy theo loại biểu đồ (Area / Bar / Line) */}
        {seriesKeys.map((k, i) => {
          const isForecastKey = k.toLowerCase().includes("dự báo") || k.toLowerCase().includes("forecast");
          const hex = HEX_PALETTE[i % HEX_PALETTE.length];

          // 1. Nếu người dùng chọn Biểu đồ miền (Area): vẽ vùng phủ màu rõ ràng
          if (isAreaMode) {
            const fillUrl = isForecastKey ? `url(#${cardUid}_fcArea_forecast)` : `url(#${cardUid}_fcArea_${i})`;
            return (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
                stroke={isForecastKey ? "#eab308" : hex}
                strokeWidth={isForecastKey ? 2.5 : 2.5}
                strokeDasharray={isForecastKey ? "5 5" : undefined}
                fill={fillUrl}
                fillOpacity={1}
                dot={isForecastKey ? { r: 5, fill: "#eab308" } : (data.length <= 30 ? { r: 3 } : false)}
                connectNulls={false}
              />
            );
          }

          // 2. Nếu người dùng chọn Biểu đồ cột (Bar): vẽ dạng cột dọc
          if (isBarMode) {
            return (
              <Bar
                key={k}
                dataKey={k}
                name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
                fill={isForecastKey ? "#eab308" : hex}
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              />
            );
          }

          // 3. Mặc định là Biểu đồ đường (Line): chỉ vẽ đường kẻ thanh mảnh, không đổ bóng màu nền
          return (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
              stroke={isForecastKey ? "#eab308" : hex}
              strokeWidth={isForecastKey ? 2.5 : 2}
              strokeDasharray={isForecastKey ? "5 5" : undefined}
              dot={isForecastKey ? { r: 5, fill: "#eab308" } : (data.length <= 30 ? { r: 3 } : false)}
              connectNulls={false}
            />
          );
        })}

        {chart.forecast_from && (
          <ReferenceLine
            x={chart.forecast_from}
            stroke="#eab308"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            label={{
              value: "▶ Bắt đầu dự báo",
              position: "top",
              fill: "#eab308",
              fontSize: 11,
              fontWeight: 600,
            }}
          />
        )}
      </ComposedChart>
    );
  }

  // Biểu đồ miền (Area) ở chế độ thông thường
  if (chartType === "area") {
    return (
      <AreaChart data={data} accessibilityLayer={false} margin={{ top: 12, right: 16, left: 16, bottom: 25 }}>
        <defs>
          {seriesKeys.map((k, i) => {
            const hex = HEX_PALETTE[i % HEX_PALETTE.length];
            return (
              <linearGradient
                key={`grad_area_${k}_${i}`}
                id={`${cardUid}_grad_area_${i}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={hex} stopOpacity={0.65} style={{ stopColor: hex, stopOpacity: 0.65 }} />
                <stop offset="70%" stopColor={hex} stopOpacity={0.25} style={{ stopColor: hex, stopOpacity: 0.25 }} />
                <stop offset="100%" stopColor={hex} stopOpacity={0.05} style={{ stopColor: hex, stopOpacity: 0.05 }} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="name"
          tickFormatter={formatAxisDate}
          stroke="var(--text-secondary)"
          interval="preserveStartEnd"
          minTickGap={24}
          padding={{ left: 12, right: 12 }}
        />
        <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => formatNumber(v)} />
        <Tooltip content={<CustomChartTooltip unit={chart.unit} />} />
        <Legend />
        {seriesKeys.map((k, i) => {
          const hex = HEX_PALETTE[i % HEX_PALETTE.length];
          return (
            <Area
              key={k}
              type="monotone"
              dataKey={k}
              name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
              fill={`url(#${cardUid}_grad_area_${i})`}
              fillOpacity={1}
              stroke={hex}
              strokeWidth={2.5}
              dot={data.length <= 30 ? { r: 3 } : false}
            />
          );
        })}
      </AreaChart>
    );
  }

  // Biểu đồ đường (Line) ở chế độ thông thường
  if (chartType === "line") {
    return (
      <LineChart data={data} accessibilityLayer={false} margin={{ top: 12, right: 16, left: 16, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
        <XAxis
          dataKey="name"
          tickFormatter={formatAxisDate}
          stroke="var(--text-secondary)"
          interval="preserveStartEnd"
          minTickGap={24}
          padding={{ left: 12, right: 12 }}
        />
        <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => formatNumber(v)} />
        <Tooltip content={<CustomChartTooltip unit={chart.unit} />} />
        <Legend />
        {seriesKeys.map((k, i) => {
          const isHighlighted = chart.highlight_series === k;
          return (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={isHighlighted ? 3.5 : 2}
              dot={data.length <= 30 ? { r: isHighlighted ? 4 : 3 } : false}
            />
          );
        })}
      </LineChart>
    );
  }

  // BarChart (Cột dọc chuẩn)
  return (
    <BarChart
      data={data}
      accessibilityLayer={false}
      barCategoryGap="25%"
      maxBarSize={72}
      margin={{ top: 12, right: 16, left: 16, bottom: 25 }}
    >
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
      <XAxis
        dataKey="name"
        tickFormatter={formatAxisDate}
        stroke="var(--text-secondary)"
        interval="preserveStartEnd"
        minTickGap={24}
        padding={{ left: 12, right: 12 }}
      />
      <YAxis
        stroke="var(--text-secondary)"
        tickFormatter={(v) => (chart.unit === "%" ? formatPercent(v) : formatNumber(v))}
        domain={isSigned ? [(dataMin: number) => Math.min(0, dataMin), (dataMax: number) => Math.max(0, dataMax)] : undefined}
      />
      {isSigned && <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />}
      <Tooltip content={<CustomChartTooltip unit={chart.unit} isContribution={isContribution} isSigned={isSigned} />} />
      <Legend />
      {seriesKeys.map((k, sIdx) => (
        <Bar
          key={k}
          dataKey={k}
          name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
          fill={PALETTE[sIdx % PALETTE.length]}
          radius={[4, 4, 0, 0]}
        >
          {isSigned &&
            data.map((entry, cIdx) => {
              const val = Number(entry[k] || 0);
              return <Cell key={cIdx} fill={val >= 0 ? "var(--pos)" : "var(--neg)"} />;
            })}
        </Bar>
      ))}
    </BarChart>
  );
}

/**
 * Custom Tooltip định dạng chuẩn tiếng Việt, có biểu tượng tăng/giảm và đơn vị
 */
function CustomChartTooltip({
  active,
  payload,
  label,
  unit,
  isContribution,
  isSigned,
}: {
  active?: boolean;
  payload?: any[];
  label?: string;
  unit?: string | null;
  isContribution?: boolean;
  isSigned?: boolean;
}) {
  if (!active || !payload || !payload.length) return null;

  const validPayload = payload.filter((item) => !String(item.dataKey || "").startsWith("_band"));
  if (!validPayload.length) return null;

  return (
    <div className="custom-chart-tooltip">
      <div className="tooltip-title">{label ? formatAxisDate(label) : ""}</div>
      <div className="tooltip-items">
        {validPayload.map((item, idx) => {
          if (item.value === null || item.value === undefined) return null;
          const val = Number(item.value);
          let formattedValue = formatNumber(val);

          if (isContribution || isSigned) {
            const signed = formatSignedChange(val, unit || undefined);
            formattedValue = signed.text;
          } else if (unit === "%") {
            formattedValue = formatPercent(val);
          } else if (unit) {
            formattedValue = `${formattedValue} ${unit}`;
          }

          return (
            <div key={idx} className="tooltip-item">
              <span className="tooltip-dot" style={{ backgroundColor: item.color }} />
              <span className="tooltip-name">{item.name}:</span>
              <span
                className="tooltip-val"
                style={{
                  color: (isContribution || isSigned)
                    ? val >= 0
                      ? "var(--pos)"
                      : "var(--neg)"
                    : "var(--text-primary)",
                }}
              >
                {formattedValue}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
