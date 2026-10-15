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
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { ChartSpec } from "../api/types";
import { formatNumber, formatPercent, formatAxisDate, formatSignedChange } from "../utils/formatters";
import { exportChartToPng } from "../export/exportPng";
import { downloadCsv } from "../export/buildCsv";
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

interface ChartCardProps {
  chart: ChartSpec;
}

export const ChartCard: React.FC<ChartCardProps> = ({ chart }) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isExportingPng, setIsExportingPng] = useState(false);

  const seriesKeys = Object.keys(chart.series || {});
  const isContribution = chart.perspective === "contribution_to_change";
  const isShare = chart.perspective === "share_of_total";
  const isForecast = !!chart.forecast_from || !!chart.band;

  // Chuẩn hóa dữ liệu cho Recharts (hỗ trợ Optional/null an toàn)
  const chartData = (chart.x || []).map((xVal, i) => {
    const pt: Record<string, string | number | null> = { name: xVal };
    for (const k of seriesKeys) {
      const val = chart.series[k]?.[i];
      pt[k] = val !== undefined && val !== null ? val : (chart.chart_type === "bar" && !isForecast ? 0 : null);
    }
    if (chart.band) {
      const lower = chart.band.lower?.[i];
      const upper = chart.band.upper?.[i];
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
      await exportChartToPng(cardRef.current, chart.title);
    } catch {
      alert("Không thể xuất ảnh PNG. Vui lòng thử lại.");
    } finally {
      setIsExportingPng(false);
    }
  };

  const handleExportCsv = () => {
    setMenuOpen(false);
    downloadCsv(chart, `DuLieu_${chart.title.replace(/\s+/g, "_")}.csv`);
  };

  return (
    <div className="chart-card" ref={cardRef}>
      {/* Header thẻ */}
      <div className="chart-card-header">
        <div className="header-text-group">
          <h3 className="chart-card-title">{chart.title}</h3>
          <div className="chart-card-subtitle">
            {chart.unit && <span className="chart-unit-badge">Đơn vị: {chart.unit}</span>}
            {chart.role === "primary" && <span className="chart-role-badge">Biểu đồ chính</span>}
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
            </div>
          )}
        </div>
      </div>

      {/* Vùng vẽ biểu đồ */}
      <div className="chart-canvas-wrapper">
        <ResponsiveContainer width="100%" height={300}>
          {renderChartByType(chart, chartData, seriesKeys, isContribution, isShare, isForecast)}
        </ResponsiveContainer>
      </div>

      {/* Caption chú thích */}
      {chart.caption && (
        <div className="chart-card-caption">
          <span className="caption-bar">▎</span>
          <span className="caption-text">{chart.caption}</span>
        </div>
      )}
    </div>
  );
};

function renderChartByType(
  chart: ChartSpec,
  data: Record<string, any>[],
  seriesKeys: string[],
  isContribution: boolean,
  isShare: boolean,
  isForecast: boolean
) {
  if (chart.chart_type === "pie" || isShare) {
    const pieData = (chart.x || []).map((name, i) => ({
      name,
      value: chart.series[seriesKeys[0]]?.[i] ?? 0,
    }));

    return (
      <PieChart accessibilityLayer={false}>
        <Tooltip content={<CustomChartTooltip unit="%" />} />
        <Legend />
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={95}
          innerRadius={40}
          paddingAngle={3}
          label={({ name, percent }: { name?: string; percent?: number }) =>
            `${name || ""}: ${formatPercent((percent || 0) * 100, 1)}`
          }
        >
          {pieData.map((_, idx) => (
            <Cell key={idx} fill={PALETTE[idx % PALETTE.length]} />
          ))}
        </Pie>
      </PieChart>
    );
  }

  // ComposedChart / Forecast chart
  if (isForecast) {
    return (
      <ComposedChart data={data} accessibilityLayer={false} margin={{ top: 12, right: 16, left: 16, bottom: 25 }}>
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
              fill="var(--chart-2)"
              fillOpacity={0.16}
              stroke="none"
              name="Dải tin cậy 80%"
              connectNulls={false}
            />
          </>
        )}

        {seriesKeys.map((k, i) => {
          const isForecastKey = k.toLowerCase().includes("dự báo") || k.toLowerCase().includes("forecast");
          return (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
              stroke={isForecastKey ? "var(--chart-2)" : PALETTE[i % PALETTE.length]}
              strokeWidth={isForecastKey ? 2.5 : 2}
              strokeDasharray={isForecastKey ? "5 5" : undefined}
              dot={{ r: isForecastKey ? 4 : 3 }}
              connectNulls={false}
            />
          );
        })}

        {chart.forecast_from && (
          <ReferenceLine
            x={chart.forecast_from}
            stroke="var(--text-muted)"
            strokeDasharray="3 3"
            label={{
              value: "Dự báo",
              position: "top",
              fill: "var(--text-muted)",
              fontSize: 11,
            }}
          />
        )}
      </ComposedChart>
    );
  }

  if (chart.chart_type === "area") {
    return (
      <AreaChart data={data} accessibilityLayer={false} margin={{ top: 12, right: 16, left: 16, bottom: 25 }}>
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
        {seriesKeys.map((k, i) => (
          <Area
            key={k}
            type="monotone"
            dataKey={k}
            name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
            fill={PALETTE[i % PALETTE.length]}
            stroke={PALETTE[i % PALETTE.length]}
            fillOpacity={0.25}
          />
        ))}
      </AreaChart>
    );
  }

  if (chart.chart_type === "line") {
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
              dot={{ r: isHighlighted ? 4 : 3 }}
            />
          );
        })}
      </LineChart>
    );
  }

  // BarChart (Cột chuẩn)
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
      {isContribution && <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />}
      <Tooltip content={<CustomChartTooltip unit={chart.unit} isContribution={isContribution} />} />
      <Legend />
      {seriesKeys.map((k, sIdx) => (
        <Bar
          key={k}
          dataKey={k}
          name={chart.display_name && seriesKeys.length === 1 ? chart.display_name : k}
          fill={PALETTE[sIdx % PALETTE.length]}
          radius={[4, 4, 0, 0]}
        >
          {isContribution &&
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
}: {
  active?: boolean;
  payload?: any[];
  label?: string;
  unit?: string | null;
  isContribution?: boolean;
}) {
  if (!active || !payload || !payload.length) return null;

  const validPayload = payload.filter((item) => !String(item.dataKey || "").startsWith("_band"));
  if (!validPayload.length) return null;

  return (
    <div className="custom-chart-tooltip">
      <div className="tooltip-title">{label}</div>
      <div className="tooltip-items">
        {validPayload.map((item, idx) => {
          if (item.value === null || item.value === undefined) return null;
          const val = Number(item.value);
          let formattedValue = formatNumber(val);

          if (isContribution) {
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
                  color: isContribution
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
