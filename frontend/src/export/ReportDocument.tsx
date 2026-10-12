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
          <h2 className="report-h2">2. Nhận xét phân tích</h2>
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
        <span>Trang 1</span>
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

  // Chuẩn hóa dữ liệu cho Recharts
  const chartData = (spec.x || []).map((xVal, i) => {
    const pt: Record<string, string | number> = { name: xVal };
    for (const k of seriesKeys) {
      pt[k] = spec.series[k]?.[i] ?? 0;
    }
    return pt;
  });

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

  // Bar chart (mặc định)
  const isContribution = spec.perspective === "contribution_to_change";

  return (
    <BarChart data={chartData} width={width} height={height} margin={{ top: 10, right: 20, left: 20, bottom: 25 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
      <XAxis dataKey="name" tickFormatter={formatAxisDate} stroke="#475569" />
      <YAxis tickFormatter={(v) => formatNumber(v)} stroke="#475569" />
      <Legend />
      {seriesKeys.map((k, sIdx) => (
        <Bar key={k} dataKey={k} fill={PRINT_COLORS[sIdx % PRINT_COLORS.length]} isAnimationActive={false} maxBarSize={50}>
          {isContribution &&
            chartData.map((pt, cIdx) => {
              const val = Number(pt[k] || 0);
              return <Cell key={cIdx} fill={val >= 0 ? "#059669" : "#DC2626"} />;
            })}
        </Bar>
      ))}
    </BarChart>
  );
}
