import React, { useState } from "react";
import type { DeepenResponse, AnalysisLevel } from "../api/types";
import { ChartCard } from "./ChartCard";
import { RecommendationList } from "./RecommendationCard";

interface DeepenSectionProps {
  level: AnalysisLevel;
  data?: DeepenResponse;
  loading?: boolean;
  onRetry?: () => void;
}

const LEVEL_TITLES: Record<AnalysisLevel, { title: string; badge: string; badgeClass: string }> = {
  descriptive: {
    title: "Phân tích mô tả",
    badge: "Mô tả",
    badgeClass: "section-badge-diagnostic",
  },
  diagnostic: {
    title: "Yếu tố đóng góp & Điểm nghẽn",
    badge: "Chẩn đoán",
    badgeClass: "section-badge-diagnostic",
  },
  forecast: {
    title: "Dự báo chuỗi thời gian (Ước tính)",
    badge: "Dự báo",
    badgeClass: "section-badge-forecast",
  },
  prescriptive: {
    title: "Gợi ý chiến lược & Đề xuất hành động",
    badge: "Đề xuất",
    badgeClass: "section-badge-prescriptive",
  },
};

export const DeepenSection: React.FC<DeepenSectionProps> = ({
  level,
  data,
  loading = false,
  onRetry,
}) => {
  const [showBases, setShowBases] = useState(false);
  const info = LEVEL_TITLES[level] || LEVEL_TITLES.diagnostic;

  if (loading) {
    return (
      <div className="deepen-section-card" role="region" aria-label={`Đang tải ${info.title}`}>
        <div className="deepen-section-header">
          <div className="deepen-section-title-group">
            <h3 className="deepen-section-title">{info.title}</h3>
            <span className={`deepen-section-badge ${info.badgeClass}`}>{info.badge}</span>
          </div>
        </div>
        <div className="loading-card" style={{ padding: "16px", border: "none" }}>
          <div className="loading-steps">
            <div className="loading-step">
              <div className="loading-step-dot" />
              <span>Đang tính toán các chỉ số chuyên sâu và tổng hợp căn cứ...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Thu thập toàn bộ biểu đồ trong các sections của DeepenResponse
  const allCharts = (data.sections || []).flatMap((s) => s.charts || []);
  const baseSections = (data.sections || []).filter((s) => s.level !== "prescriptive");
  const mainSection = (data.sections || []).find((s) => s.level === level) || data.sections?.[0];

  return (
    <div className="deepen-section-card" role="region" aria-label={info.title}>
      <div className="deepen-section-header">
        <div className="deepen-section-title-group">
          <h3 className="deepen-section-title">{info.title}</h3>
          <span className={`deepen-section-badge ${info.badgeClass}`}>{info.badge}</span>
        </div>
        {onRetry && (
          <button type="button" className="section-retry-btn" onClick={onRetry}>
            Tính lại
          </button>
        )}
      </div>

      {/* Cảnh báo nếu có */}
      {data.warnings && data.warnings.length > 0 && (
        <div className="section-warnings">
          {data.warnings.map((w, i) => (
            <div key={i}>⚠️ {w}</div>
          ))}
        </div>
      )}

      {/* Nhận xét AI hoặc lời diễn giải */}
      {mainSection?.narrative?.insight_text && (
        <div className="section-narrative">
          {mainSection.narrative.insight_text}
        </div>
      )}

      {/* Cấp Prescriptive: Thẻ khuyến nghị trích dẫn Fact */}
      {level === "prescriptive" && (
        <>
          <RecommendationList recommendations={data.recommendations} facts={data.facts} />

          {/* Khối căn cứ chẩn đoán & dự báo thu gọn */}
          {baseSections.length > 0 && (
            <div className="collapsible-bases">
              <div
                className="collapsible-bases-summary"
                onClick={() => setShowBases(!showBases)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") setShowBases(!showBases);
                }}
              >
                <span>
                  {showBases ? "▼ Thu gọn" : "▶ Xem"} căn cứ số liệu chi tiết (Chẩn đoán & Dự báo)
                </span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {data.facts.length} sự thật đã tính toán
                </span>
              </div>

              {showBases && (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "12px" }}>
                  {baseSections.map((sec, idx) => (
                    <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      <h5 style={{ margin: "0", fontSize: "13px", color: "var(--text-secondary)" }}>
                        {sec.level === "diagnostic" ? "Yếu tố đóng góp & Tương quan" : "Dự báo chuỗi thời gian"}
                      </h5>
                      {sec.narrative?.insight_text && (
                        <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                          {sec.narrative.insight_text}
                        </div>
                      )}
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                        {(sec.charts || []).map((chart, cIdx) => (
                          <ChartCard key={cIdx} chart={chart} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Biểu đồ chuyên sâu của cấp (Diagnostic hoặc Forecast) */}
      {level !== "prescriptive" && allCharts.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
          {allCharts.map((chart, idx) => (
            <ChartCard key={idx} chart={chart} />
          ))}
        </div>
      )}
    </div>
  );
};
