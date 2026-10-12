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

const HIGHLIGHT_COLOR = "hsl(0, 80%, 62%)";  // đỏ – dùng cho highlight_x và highlight_series

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

function perspectiveTag(spec: ChartSpec): { label: string; tagClass: string } {
  if (spec.perspective === "trend_by_group") {
    return { label: "Xu hướng nhóm", tagClass: "badge-blue" };
  }
  if (spec.perspective === "share_of_total") {
    return { label: "Tỷ trọng", tagClass: "badge-purple" };
  }
  if (spec.perspective === "period_change") {
    return { label: "Biến động kỳ", tagClass: "badge-orange" };
  }
  if (spec.perspective === "contribution_to_change") {
    return { label: "Đóng góp thay đổi", tagClass: "badge-green" };
  }
  if (spec.perspective === "cumulative") {
    return { label: "Lũy kế", tagClass: "badge-blue" };
  }
  if (spec.perspective === "moving_average") {
    return { label: "Trung bình trượt", tagClass: "badge-blue" };
  }

  const t = spec.title.toLowerCase();
  if (t.includes("xu hướng") || t.includes("trend")) {
    return { label: "Xu hướng", tagClass: "badge-blue" };
  }
  if (t.includes("tăng trưởng") || t.includes("tăng/giảm")) {
    return { label: "Tăng trưởng", tagClass: "badge-orange" };
  }
  return { label: "So sánh", tagClass: "badge-purple" };
}

export default function ChartPanel({ charts }: Props) {
  if (charts.length === 0) return null;

  const primaryCharts = charts.filter((c) => c.role !== "supplementary");
  const supplementaryCharts = charts.filter((c) => c.role === "supplementary");

  return (
    <div className="chart-panel animate-fade-in-up">
      {/* ── BIỂU ĐỒ CHÍNH (PRIMARY) ── */}
      <div className="chart-section primary-section">
        <div className="section-header">
          <div className="section-title-row">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h2 className="chart-panel-title">Biểu Đồ Trả Lời Chính</h2>
            <span className="badge badge-blue">{primaryCharts.length} biểu đồ</span>
          </div>
        </div>

        <div className="chart-grid primary-grid">
          {primaryCharts.map((spec, idx) => (
            <ChartCard key={spec.perspective || `primary-${idx}`} spec={spec} colorOffset={idx} />
          ))}
        </div>
      </div>

      {/* ── GÓC NHÌN BỔ SUNG (SUPPLEMENTARY) ── */}
      {supplementaryCharts.length > 0 && (
        <div className="chart-section supplementary-section animate-fade-in">
          <div className="section-header supplementary-header">
            <div className="section-title-row">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <polygon points="12 2 2 7 12 12 22 7 12 2" stroke="currentColor" strokeWidth="2"/>
                <polyline points="2 17 12 22 22 17" stroke="currentColor" strokeWidth="2"/>
                <polyline points="2 12 12 17 22 12" stroke="currentColor" strokeWidth="2"/>
              </svg>
              <h2 className="chart-panel-title">Góc Nhìn Bổ Sung</h2>
              <span className="badge badge-purple">{supplementaryCharts.length} góc nhìn</span>
            </div>
            <p className="section-desc">
              Tự động phân rã chi tiết để giải thích toàn diện hiện tượng phía sau con số tổng quát
            </p>
          </div>

          <div className="chart-grid supplementary-grid">
            {supplementaryCharts.map((spec, idx) => (
              <ChartCard
                key={spec.perspective || `supp-${idx}`}
                spec={spec}
                colorOffset={idx + primaryCharts.length}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ChartCard({ spec, colorOffset }: { spec: ChartSpec; colorOffset: number }) {
  const rows = buildRows(spec);
  const seriesKeys = Object.keys(spec.series);
  const isPercent = seriesKeys.some((k) => k.toLowerCase().includes("%") || k.toLowerCase().includes("rate"));

  const { label: tagLabel, tagClass } = perspectiveTag(spec);
  const isMultiSeries = seriesKeys.length > 1;

  return (
    <div className={`chart-card card animate-fade-in-up ${spec.role === "supplementary" ? "card-supplementary" : ""}`}>
      <div className="chart-card-header">
        <div className="chart-card-title-row">
          <span className={`badge ${tagClass}`}>{tagLabel}</span>
          {spec.role === "supplementary" && (
            <span className="badge badge-ghost">Bổ sung</span>
          )}
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
              {isMultiSeries && (
                <Legend wrapperStyle={{ fontSize: "13px", color: "hsl(220, 15%, 65%)" }} />
              )}
              {seriesKeys.map((key, i) => {
                const isHighlighted = spec.highlight_series === key;
                const strokeColor = isHighlighted
                  ? HIGHLIGHT_COLOR
                  : SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length];
                const strokeWidth = isHighlighted ? 3.5 : (spec.highlight_series ? 1.8 : 2.5);
                const strokeOpacity = (spec.highlight_series && !isHighlighted) ? 0.35 : 1;

                return (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeOpacity={strokeOpacity}
                    dot={{
                      r: isHighlighted ? 5 : 3.5,
                      fill: strokeColor,
                      fillOpacity: strokeOpacity,
                    }}
                    activeDot={{ r: 6 }}
                  />
                );
              })}
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
              {isMultiSeries && (
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
                        !isMultiSeries && spec.highlight_x && row.label === spec.highlight_x
                          ? HIGHLIGHT_COLOR
                          : SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]
                      }
                      fillOpacity={
                        !isMultiSeries && spec.highlight_x && row.label !== spec.highlight_x ? 0.65 : 1
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
              {isMultiSeries && (
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
                        !isMultiSeries && spec.highlight_x && row.label === spec.highlight_x
                          ? HIGHLIGHT_COLOR
                          : SERIES_COLORS[(colorOffset + i) % SERIES_COLORS.length]
                      }
                      fillOpacity={
                        !isMultiSeries && spec.highlight_x && row.label !== spec.highlight_x ? 0.65 : 1
                      }
                    />
                  ))}
                </Bar>
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Ghi chú nổi bật (Target / Highlight) */}
      {spec.highlight_series && (
        <div className="chart-highlight-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Tập trung vào đường: <strong>{spec.highlight_series}</strong>
        </div>
      )}
      {spec.highlight_x && !isMultiSeries && (
        <div className="chart-highlight-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
            <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          Nổi bật: <strong>{spec.highlight_x}</strong>
        </div>
      )}

      {/* Caption nhận xét tất định */}
      {spec.caption && (
        <div className="chart-caption">
          <div className="chart-caption-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </div>
          <p className="chart-caption-text">{spec.caption}</p>
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
