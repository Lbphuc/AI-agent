import {
  LineChart, Line, BarChart, Bar,
  AreaChart, Area, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell,
} from "recharts";
import type { ChartSpec } from "../api/types";
import "./ChartPanel.css";

interface Props {
  charts: ChartSpec[];
}

/** Bảng màu cho các series – đủ tương phản trên nền tối */
const SERIES_COLORS = [
  "hsl(217, 91%, 60%)",   // xanh dương
  "hsl(271, 76%, 65%)",   // tím
  "hsl(151, 68%, 50%)",   // xanh lá
  "hsl(38, 92%, 58%)",    // vàng cam
  "hsl(340, 82%, 62%)",   // hồng
  "hsl(190, 80%, 52%)",   // cyan
];

/** Bảng màu cố định dùng cho Pie — đúng 6 màu khớp _MAX_PIE_SLICES */
const PALETTE = [
  "hsl(217, 91%, 60%)",
  "hsl(340, 82%, 62%)",
  "hsl(151, 68%, 50%)",
  "hsl(38, 92%, 58%)",
  "hsl(271, 76%, 65%)",
  "hsl(190, 80%, 52%)",
];

const HIGHLIGHT_COLOR = "hsl(0, 80%, 62%)";  // đỏ – dùng cho highlight_x

/** Format số lớn: 1.500.000 → 1.5M */
function formatValue(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(1);
}

/** Format % nếu series tên chứa "%" hoặc giá trị nhỏ */
function formatAxis(v: number, isPercent: boolean): string {
  if (isPercent) return `${v.toFixed(1)}%`;
  return formatValue(v);
}

function buildRows(spec: ChartSpec): Record<string, string | number>[] {
  return spec.x.map((label, i) => {
    const row: Record<string, string | number> = { label };
    for (const [key, values] of Object.entries(spec.series)) {
      row[key] = values[i] ?? 0;
    }
    return row;
  });
}

function taskTypeLabel(title: string): string {
  const t = title.toLowerCase();
  if (t.includes("xu hướng") || t.includes("trend")) return "Xu hướng";
  if (t.includes("tăng trưởng") || t.includes("tăng/giảm")) return "Tăng trưởng";
  return "So sánh";
}

export default function ChartPanel({ charts }: Props) {
  if (charts.length === 0) return null;

  return (
    <div className="chart-panel animate-fade-in-up">
      <h2 className="chart-panel-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Biểu Đồ Phân Tích
      </h2>

      <div className="chart-grid">
        {charts.map((spec, idx) => (
          <ChartCard key={idx} spec={spec} colorOffset={idx} />
        ))}
      </div>
    </div>
  );
}

function ChartCard({ spec, colorOffset }: { spec: ChartSpec; colorOffset: number }) {
  const rows = buildRows(spec);
  const seriesKeys = Object.keys(spec.series);
  const isPercent = seriesKeys.some((k) => k.toLowerCase().includes("%") || k.toLowerCase().includes("rate"));

  const tagLabel = taskTypeLabel(spec.title);
  const tagClass = tagLabel === "Xu hướng" ? "badge-blue" : tagLabel === "Tăng trưởng" ? "badge-orange" : "badge-purple";

  return (
    <div className="chart-card card animate-fade-in-up">
      <div className="chart-card-header">
        <div className="chart-card-title-row">
          <span className={`badge ${tagClass}`}>{tagLabel}</span>
          <h3 className="chart-card-title">{spec.title}</h3>
        </div>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={280}>
          {spec.chart_type === "line" ? (
            <LineChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsla(220, 15%, 40%, 0.2)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatAxis(v, isPercent)}
                width={60}
              />
              <Tooltip content={<CustomTooltip isPercent={isPercent} />} />
              {seriesKeys.length > 1 && (
                <Legend wrapperStyle={{ fontSize: "13px", color: "hsl(220, 15%, 65%)" }} />
              )}
              {seriesKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]}
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length] }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          ) : spec.chart_type === "area" ? (
            <AreaChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsla(220, 15%, 40%, 0.2)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatAxis(v, isPercent)}
                width={60}
              />
              <Tooltip content={<CustomTooltip isPercent={isPercent} />} />
              {seriesKeys.length > 1 && (
                <Legend wrapperStyle={{ fontSize: "13px", color: "hsl(220, 15%, 65%)" }} />
              )}
              {seriesKeys.map((key, i) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]}
                  fill={SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]}
                  fillOpacity={0.18}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </AreaChart>
          ) : spec.chart_type === "bar_horizontal" ? (
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsla(220, 15%, 40%, 0.2)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatAxis(v, isPercent)}
              />
              <YAxis
                type="category"
                dataKey="label"
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={130}
              />
              <Tooltip content={<CustomTooltip isPercent={isPercent} />} />
              {seriesKeys.map((key, i) => (
                <Bar key={key} dataKey={key} radius={[0, 4, 4, 0]} maxBarSize={36}>
                  {rows.map((row) => (
                    <Cell
                      key={String(row.label)}
                      fill={
                        spec.highlight_x && row.label === spec.highlight_x
                          ? HIGHLIGHT_COLOR
                          : SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]
                      }
                      fillOpacity={
                        spec.highlight_x && row.label !== spec.highlight_x ? 0.65 : 1
                      }
                    />
                  ))}
                </Bar>
              ))}
            </BarChart>
          ) : spec.chart_type === "pie" ? (
            <PieChart margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <Pie
                data={rows}
                dataKey={seriesKeys[0]}
                nameKey="label"
                outerRadius={110}
                innerRadius={40}
                paddingAngle={2}
                label={({ name, percent }: { name?: string; percent?: number }) =>
                  `${name ?? ""} ${((percent ?? 0) * 100).toFixed(1)}%`
                }
                labelLine={false}
              >
                {rows.map((_row, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => {
                  const v = value as number;
                  return isPercent ? `${v.toFixed(2)}%` : formatValue(v);
                }}
              />
            </PieChart>
          ) : (
            // spec.chart_type === "bar" (default)
            <BarChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsla(220, 15%, 40%, 0.2)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(220, 15%, 55%)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatAxis(v, isPercent)}
                width={60}
              />
              <Tooltip content={<CustomTooltip isPercent={isPercent} />} />
              {seriesKeys.length > 1 && (
                <Legend wrapperStyle={{ fontSize: "13px", color: "hsl(220, 15%, 65%)" }} />
              )}
              {seriesKeys.map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={48}
                >
                  {rows.map((row) => (
                    <Cell
                      key={String(row.label)}
                      fill={
                        spec.highlight_x && row.label === spec.highlight_x
                          ? HIGHLIGHT_COLOR
                          : SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]
                      }
                      fillOpacity={
                        spec.highlight_x && row.label !== spec.highlight_x ? 0.65 : 1
                      }
                    />
                  ))}
                </Bar>
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {spec.highlight_x && (
        <div className="chart-highlight-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
            <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          Nổi bật: <strong>{spec.highlight_x}</strong>
        </div>
      )}
    </div>
  );
}

function CustomTooltip({
  active, payload, label, isPercent,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
  isPercent: boolean;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="chart-tooltip-item">
          <span className="chart-tooltip-dot" style={{ background: p.color }} />
          <span className="chart-tooltip-name">{p.name}</span>
          <span className="chart-tooltip-value">
            {isPercent ? `${p.value.toFixed(2)}%` : formatValue(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}
