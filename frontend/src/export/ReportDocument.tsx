import React from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  ComposedChart,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  Legend,
} from "recharts";
import type { ReportModel, ReportChartItem } from "./types";
import { formatNumber, formatPercent, formatAxisDate } from "../utils/formatters";
import "./ReportDocument.css";

const PRINT_COLORS = [
  "#0072B2", // Sky Blue
  "#D55E00", // Vermilion
  "#009E73", // Teal / Green
  "#CC79A7", // Purple
  "#E69F00", // Orange
  "#4F46E5", // Indigo
  "#B45309", // Amber
  "#334155", // Slate
];

interface ReportDocumentProps {
  model: ReportModel;
}

export const ReportDocument: React.FC<ReportDocumentProps> = ({ model }) => {
  const { sections } = model;

  return (
    <div className="report-document theme-print" data-theme="print">
      {/* ── 1. ĐẦU TRANG ── */}
      <header className="report-header">
        <div className="report-brand">
          {model.orgName && <div className="report-org">{model.orgName}</div>}
          <h1 className="report-title">{model.title}</h1>
        </div>
        <div className="report-meta-grid">
          <div>
            <strong>Tập dữ liệu:</strong> {model.filename}
          </div>
          <div>
            <strong>Thời gian tạo:</strong> {model.generatedAt}
          </div>
          <div>
            <strong>Dữ liệu:</strong> {model.rowsInfo}
          </div>
          <div>
            <strong>Công cụ:</strong> {model.modelName}
          </div>
        </div>
      </header>

      {/* ── 2 & 3. CÂU HỎI & MỤC TIÊU ── */}
      <section className="report-section report-card">
        <h2 className="report-h2">1. Câu hỏi & Mục tiêu phân tích</h2>
        <div className="report-field">
          <strong>Câu hỏi ban đầu:</strong>
          <p className="report-quote">“{model.question}”</p>
        </div>
        {model.goalSummary && (
          <div className="report-field">
            <strong>Hệ thống hiểu câu hỏi là:</strong>
            <p className="report-summary">{model.goalSummary}</p>
          </div>
        )}
      </section>

      {/* ── 4. NHẬN XÉT AI ── */}
      {sections.insight !== false && model.insightText && (
        <section className="report-section report-card">
          <h2 className="report-h2">2. Nhận xét phân tích tổng quan</h2>
          <div className="report-insight-box">
            <p className="report-insight-text">{model.insightText}</p>
            <p className="report-disclaimer">
              * Nhận xét do AI tạo từ số liệu đã tính toán; hãy đối chiếu với bảng số liệu ở phụ lục.
            </p>
            {model.isLowConfidence && (
              <p className="report-warning">
                ⚠️ Lưu ý: Một số con số trong nhận xét có độ khớp thấp, hãy đối chiếu kỹ trước khi sử dụng.
              </p>
            )}
          </div>
        </section>
      )}

      {/* ── PHÂN TÍCH CHẨN ĐOÁN (NẾU CÓ) ── */}
      {(model.diagnosticNarrative || (model.diagnosticFacts && model.diagnosticFacts.length > 0)) && (
        <section className="report-section report-card">
          <h2 className="report-h2">Chẩn đoán yếu tố đóng góp & Điểm nghẽn</h2>
          {model.diagnosticNarrative && (
            <div className="report-insight-box" style={{ backgroundColor: "#eff6ff", borderColor: "#bfdbfe", marginBottom: 12 }}>
              <p className="report-insight-text" style={{ color: "#1e40af" }}>{model.diagnosticNarrative}</p>
              <p className="report-disclaimer">* Diễn giải chẩn đoán dựa trên kết quả phân tích đóng góp và tương quan.</p>
            </div>
          )}
          {model.diagnosticFacts && model.diagnosticFacts.length > 0 && (
            <table className="report-table">
              <thead>
                <tr>
                  <th style={{ width: "10%" }}>Mã</th>
                  <th style={{ width: "18%" }}>Đối tượng</th>
                  <th style={{ width: "18%" }}>Chỉ số</th>
                  <th style={{ width: "16%" }}>Mức thay đổi</th>
                  <th>Diễn giải chi tiết</th>
                </tr>
              </thead>
              <tbody>
                {model.diagnosticFacts.map((f) => (
                  <tr key={f.id}>
                    <td><strong>[{f.id}]</strong></td>
                    <td>{f.entity || "Tổng thể"}</td>
                    <td>{f.metric}</td>
                    <td>{typeof f.value === "number" ? formatNumber(f.value) : f.value} {f.unit || ""}</td>
                    <td>{f.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* ── DỰ BÁO TƯƠNG LAI (NẾU CÓ) ── */}
      {(model.forecastNarrative || (model.forecastFacts && model.forecastFacts.length > 0)) && (
        <section className="report-section report-card">
          <h2 className="report-h2">Dự báo xu hướng chuỗi thời gian</h2>
          {model.forecastNarrative && (
            <div className="report-insight-box" style={{ backgroundColor: "#fdf4ff", borderColor: "#f5d0fe", marginBottom: 12 }}>
              <p className="report-insight-text" style={{ color: "#86198f" }}>{model.forecastNarrative}</p>
              <p className="report-disclaimer">* Mọi số liệu là ước tính dự báo kèm khoảng tin cậy 80% từ kiểm định sai số backtest.</p>
            </div>
          )}
          {model.forecastFacts && model.forecastFacts.length > 0 && (
            <table className="report-table">
              <thead>
                <tr>
                  <th style={{ width: "12%" }}>Mã</th>
                  <th style={{ width: "18%" }}>Kỳ áp dụng</th>
                  <th style={{ width: "20%" }}>Giá trị ước tính</th>
                  <th>Ghi chú & Khoảng tin cậy</th>
                </tr>
              </thead>
              <tbody>
                {model.forecastFacts.map((f) => (
                  <tr key={f.id}>
                    <td><strong>[{f.id}]</strong></td>
                    <td>{f.period || "Tương lai"}</td>
                    <td>{typeof f.value === "number" ? formatNumber(f.value) : f.value} {f.unit || ""}</td>
                    <td>{f.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* ── ĐỀ XUẤT CHIẾN LƯỢC (NẾU CÓ) ── */}
      {model.recommendations && model.recommendations.length > 0 && (
        <section className="report-section report-card">
          <h2 className="report-h2">Đề xuất chiến lược & Hành động ưu tiên</h2>
          <div className="report-rec-grid">
            {model.recommendations.map((rec, i) => {
              const pClass = `priority-${rec.priority.toLowerCase().replace(/\s+/g, "_")}`;
              const badgeClass = `report-badge-${rec.priority.toLowerCase().replace(/\s+/g, "_")}`;
              return (
                <div key={i} className={`report-rec-card ${pClass}`}>
                  <div className="report-rec-header">
                    <span className="report-rec-title">{i + 1}. {rec.title}</span>
                    <span className={`report-badge ${badgeClass}`}>Ưu tiên: {rec.priority}</span>
                  </div>
                  <div className="report-rec-body">
                    <p style={{ margin: "0 0 6px 0" }}><strong>Hành động:</strong> {rec.action}</p>
                    <p style={{ margin: "0 0 6px 0" }}><strong>Căn cứ số liệu:</strong> {rec.rationale}</p>
                    {rec.caveat && (
                      <div className="report-rec-caveat">
                        <strong>Lưu ý cần kiểm chứng:</strong> {rec.caveat}
                      </div>
                    )}
                    {rec.fact_ids && rec.fact_ids.length > 0 && (
                      <div className="report-rec-citations">
                        <span style={{ fontSize: 11, color: "#64748b" }}>Căn cứ Fact:</span>
                        {rec.fact_ids.map((fid) => (
                          <span key={fid} className="report-fact-pill">[{fid}]</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── CẢNH BÁO & GIỚI HẠN (NẾU CÓ) ── */}
      {model.warnings && model.warnings.length > 0 && (
        <section className="report-section report-card" style={{ borderColor: "#fde68a", backgroundColor: "#fffbeb" }}>
          <h2 className="report-h2" style={{ borderLeftColor: "#d97706" }}>Lưu ý kỹ thuật & Giới hạn dữ liệu</h2>
          <ul style={{ margin: 0, paddingLeft: 20, color: "#92400e", fontSize: 12, lineHeight: 1.6 }}>
            {model.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {/* ── 5 & 6. CÁC BIỂU ĐỒ ── */}
      {model.charts.length > 0 && (
        <section className="report-section">
          <h2 className="report-h2">3. Trực quan hóa dữ liệu</h2>
          <div className="report-charts-list">
            {model.charts.map((item, idx) => (
              <div key={idx} className="report-chart-card report-card">
                <div className="report-chart-header">
                  <h3 className="report-h3">
                    3.{idx + 1}. {item.spec.title}
                  </h3>
                  {item.spec.unit && (
                    <span className="report-chart-unit">Đơn vị: {item.spec.unit}</span>
                  )}
                </div>

                <div className="report-chart-canvas">
                  <RenderStaticChart item={item} />
                </div>

                {item.spec.caption && (
                  <p className="report-chart-caption">▎{item.spec.caption}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── 7. PHỤ LỤC A — BẢNG SỐ LIỆU ── */}
      {sections.data_tables !== false && model.charts.length > 0 && (
        <section className="report-section report-appendix">
          <h2 className="report-h2">Phụ lục A — Bảng số liệu chi tiết</h2>
          {model.charts.map((item, idx) => (
            <div key={idx} className="report-table-wrapper report-card">
              <h4 className="report-h4">
                Bảng A.{idx + 1}: {item.spec.title}
              </h4>
              <table className="report-table">
                <thead>
                  <tr>
                    {item.headers.map((h, hIdx) => (
                      <th key={hIdx}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {item.rows.slice(0, 30).map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => (
                        <td key={cIdx}>
                          {typeof cell === "number" ? formatNumber(cell) : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {item.rows.length > 30 && (
                    <tr>
                      <td colSpan={item.headers.length} className="report-table-more">
                        (Còn {item.rows.length - 30} dòng nữa — xem file Excel đính kèm)
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      )}

      {/* ── 8. PHỤ LỤC B — CÁCH TÍNH & LƯU Ý ── */}
      {sections.calculation_notes !== false && model.calculationNotes.length > 0 && (
        <section className="report-section report-appendix report-card">
          <h2 className="report-h2">Phụ lục B — Phương pháp tính toán & Ghi chú kỹ thuật</h2>
          <table className="report-table report-calc-table">
            <thead>
              <tr>
                <th style={{ width: "35%" }}>Hạng mục</th>
                <th>Mô tả / Công thức</th>
              </tr>
            </thead>
            <tbody>
              {model.calculationNotes.map((item, i) => (
                <tr key={i}>
                  <td><strong>{item.label}</strong></td>
                  <td>{item.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ── CHÂN TRANG BÁO CÁO ── */}
      <footer className="report-footer">
        <span>Tạo tự động bởi AI Agent BI</span>
        <span>Hệ thống phân tích dữ liệu 4 cấp độ</span>
      </footer>
    </div>
  );
};

/**
 * Vẽ biểu đồ tĩnh (không animation) kích thước chuẩn A4 (~680px rộng)
 */
function RenderStaticChart({ item }: { item: ReportChartItem }) {
  const { spec } = item;
  const seriesKeys = Object.keys(spec.series || {});
  const width = 680;
  const height = 300;
  const isForecast = Boolean(spec.forecast_from || spec.band);

  // Chuẩn hóa dữ liệu cho Recharts
  const chartData = (spec.x || []).map((xVal, i) => {
    const pt: Record<string, string | number> = { name: xVal };
    for (const k of seriesKeys) {
      pt[k] = spec.series[k]?.[i] ?? 0;
    }
    if (spec.band) {
      const lower = spec.band.lower?.[i];
      const upper = spec.band.upper?.[i];
      if (lower !== undefined && upper !== undefined && lower !== null && upper !== null) {
        const lNum = Math.max(0, Number(lower));
        const uNum = Math.max(0, Number(upper));
        pt._band_lower = lNum;
        pt._band_range = Math.max(0, uNum - lNum);
      }
    }
    return pt;
  });

  // Chế độ Dự báo: Sử dụng ComposedChart với Dải tin cậy 80% và đường ngắt quãng
  if (isForecast) {
    const displaySeriesKeys = seriesKeys;

    return (
      <ComposedChart data={chartData} width={width} height={height} margin={{ top: 12, right: 20, left: 20, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis dataKey="name" tickFormatter={formatAxisDate} stroke="#475569" />
        <YAxis tickFormatter={(v) => formatNumber(v)} stroke="#475569" />
        <Legend />

        {spec.forecast_from && (
          <ReferenceLine
            x={spec.forecast_from}
            stroke="#D97706"
            strokeDasharray="4 4"
            label={{ value: "Dự báo", position: "insideTopLeft", fill: "#B45309", fontSize: 11 }}
          />
        )}

        {spec.band && (
          <>
            <Area
              type="monotone"
              dataKey="_band_lower"
              stackId="band_stack"
              fill="transparent"
              stroke="none"
              legendType="none"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="_band_range"
              stackId="band_stack"
              fill="#FDE68A"
              fillOpacity={0.45}
              stroke="none"
              name="Khoảng tin cậy 80%"
              isAnimationActive={false}
            />
          </>
        )}

        {displaySeriesKeys.map((k, i) => {
          const isForecastKey = k.toLowerCase().includes("dự báo") || k.toLowerCase().includes("forecast");
          return (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              stroke={isForecastKey ? "#D97706" : PRINT_COLORS[i % PRINT_COLORS.length]}
              strokeWidth={isForecastKey ? 2.5 : 2}
              strokeDasharray={isForecastKey ? "5 5" : undefined}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          );
        })}
      </ComposedChart>
    );
  }

  // Biểu đồ Thác nước (Waterfall)
  if (spec.chart_type === "waterfall" || spec.data_shape === "waterfall") {
    const steps = (spec.waterfall_steps && spec.waterfall_steps.length > 0)
      ? spec.waterfall_steps
      : (spec.x || []).map((name, i) => ({
          label: name,
          name: name,
          delta: Number(spec.series[seriesKeys[0]]?.[i] ?? 0),
          value: Number(spec.series[seriesKeys[0]]?.[i] ?? 0),
          is_total: i === 0 || i === (spec.x || []).length - 1,
        }));

    let running = 0;
    const wfData = steps.map((step) => {
      const d = Number(step.delta ?? step.value ?? 0);
      let base = 0;
      let val = 0;
      let color = PRINT_COLORS[0];

      if (step.is_total) {
        base = 0;
        val = d;
        running = d;
        color = "#0284C7";
      } else {
        if (d >= 0) {
          base = running;
          val = d;
          running += d;
          color = "#059669";
        } else {
          base = running + d;
          val = Math.abs(d);
          running += d;
          color = "#DC2626";
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
      <BarChart data={wfData} width={width} height={height} margin={{ top: 12, right: 20, left: 20, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis dataKey="name" stroke="#475569" />
        <YAxis tickFormatter={(v) => formatNumber(v)} stroke="#475569" />
        <ReferenceLine y={0} stroke="#94A3B8" strokeWidth={1.5} />
        <Bar dataKey="_base" stackId="wf_stack" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="_val" stackId="wf_stack" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {wfData.map((entry, idx) => (
            <Cell key={idx} fill={entry._color} />
          ))}
        </Bar>
      </BarChart>
    );
  }

  // Biểu đồ Cột ngang (Bar Horizontal)
  if (spec.chart_type === "bar_horizontal") {
    const hasNegative = chartData.some((d) =>
      seriesKeys.some((k) => typeof d[k] === "number" && (d[k] as number) < 0)
    );
    const isSigned = spec.perspective === "contribution_to_change" || spec.perspective === "period_change" || (spec.unit === "%" && hasNegative) || hasNegative;

    return (
      <BarChart data={chartData} layout="vertical" width={width} height={height} margin={{ top: 10, right: 20, left: 30, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis
          type="number"
          stroke="#475569"
          tickFormatter={(v) => (spec.unit === "%" ? formatPercent(v) : formatNumber(v))}
          domain={isSigned ? [(dataMin: number) => Math.min(0, dataMin), (dataMax: number) => Math.max(0, dataMax)] : undefined}
        />
        <YAxis dataKey="name" type="category" stroke="#475569" width={80} />
        {isSigned && <ReferenceLine x={0} stroke="#94A3B8" strokeWidth={1.5} />}
        <Legend />
        {seriesKeys.map((k, sIdx) => (
          <Bar key={k} dataKey={k} name={spec.display_name && seriesKeys.length === 1 ? spec.display_name : k} fill={PRINT_COLORS[sIdx % PRINT_COLORS.length]} isAnimationActive={false} maxBarSize={36} radius={[0, 4, 4, 0]}>
            {isSigned &&
              chartData.map((pt, cIdx) => {
                const val = Number(pt[k] || 0);
                return <Cell key={cIdx} fill={val >= 0 ? "#059669" : "#DC2626"} />;
              })}
          </Bar>
        ))}
      </BarChart>
    );
  }

  if (spec.chart_type === "pie") {
    const pieData = (spec.x || []).map((name, i) => ({
      name,
      value: spec.series[seriesKeys[0]]?.[i] ?? 0,
    }));

    return (
      <PieChart width={width} height={height}>
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={90}
          isAnimationActive={false}
          label={({ name, percent }: { name?: string; percent?: number }) =>
            `${name || ""}: ${formatPercent((percent || 0) * 100, 1)}`
          }
        >
          {pieData.map((_, i) => (
            <Cell key={i} fill={PRINT_COLORS[i % PRINT_COLORS.length]} />
          ))}
        </Pie>
        <Legend />
      </PieChart>
    );
  }

  if (spec.chart_type === "area") {
    return (
      <AreaChart data={chartData} width={width} height={height} margin={{ top: 10, right: 20, left: 20, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis dataKey="name" tickFormatter={formatAxisDate} stroke="#475569" />
        <YAxis tickFormatter={(v) => formatNumber(v)} stroke="#475569" />
        <Legend />
        {seriesKeys.map((k, i) => (
          <Area
            key={k}
            type="monotone"
            dataKey={k}
            fill={PRINT_COLORS[i % PRINT_COLORS.length]}
            stroke={PRINT_COLORS[i % PRINT_COLORS.length]}
            fillOpacity={0.25}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    );
  }

  if (spec.chart_type === "line") {
    return (
      <LineChart data={chartData} width={width} height={height} margin={{ top: 10, right: 20, left: 20, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis dataKey="name" tickFormatter={formatAxisDate} stroke="#475569" />
        <YAxis tickFormatter={(v) => formatNumber(v)} stroke="#475569" />
        <Legend />
        {seriesKeys.map((k, i) => (
          <Line
            key={k}
            type="monotone"
            dataKey={k}
            stroke={PRINT_COLORS[i % PRINT_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    );
  }

  if (spec.chart_type === "scatter") {
    const scatterData = (spec.scatter_points && spec.scatter_points.length > 0)
      ? spec.scatter_points
      : (spec.x || []).map((name, i) => {
          const yVal = Number(spec.series[seriesKeys[0]]?.[i] ?? 0);
          const parsedX = parseFloat(name);
          const xVal = !isNaN(parsedX) ? parsedX : (i + 1);
          return { name, x: xVal, y: yVal };
        });

    return (
      <ScatterChart width={width} height={height} margin={{ top: 10, right: 20, left: 20, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
        <XAxis dataKey="x" name="X" stroke="#475569" tickFormatter={(v) => formatNumber(v)} />
        <YAxis dataKey="y" name="Y" stroke="#475569" tickFormatter={(v) => formatNumber(v)} />
        <Legend />
        <Scatter name={spec.display_name || "Điểm quan sát"} data={scatterData} fill={PRINT_COLORS[0]} isAnimationActive={false} />
      </ScatterChart>
    );
  }

  // Bar chart (mặc định)
  const isContribution = spec.perspective === "contribution_to_change";
  const hasNegative = chartData.some((d) =>
    seriesKeys.some((k) => typeof d[k] === "number" && (d[k] as number) < 0)
  );
  const isSigned = isContribution || spec.perspective === "period_change" || (spec.unit === "%" && hasNegative) || hasNegative;

  return (
    <BarChart data={chartData} width={width} height={height} margin={{ top: 10, right: 20, left: 20, bottom: 25 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
      <XAxis dataKey="name" tickFormatter={formatAxisDate} stroke="#475569" />
      <YAxis
        tickFormatter={(v) => (spec.unit === "%" ? formatPercent(v) : formatNumber(v))}
        stroke="#475569"
        domain={isSigned ? [(dataMin: number) => Math.min(0, dataMin), (dataMax: number) => Math.max(0, dataMax)] : undefined}
      />
      {isSigned && <ReferenceLine y={0} stroke="#94A3B8" strokeWidth={1.5} />}
      <Legend />
      {seriesKeys.map((k, sIdx) => (
        <Bar key={k} dataKey={k} name={spec.display_name && seriesKeys.length === 1 ? spec.display_name : k} fill={PRINT_COLORS[sIdx % PRINT_COLORS.length]} isAnimationActive={false} maxBarSize={50}>
          {isSigned &&
            chartData.map((pt, cIdx) => {
              const val = Number(pt[k] || 0);
              return <Cell key={cIdx} fill={val >= 0 ? "#059669" : "#DC2626"} />;
            })}
        </Bar>
      ))}
    </BarChart>
  );
}
