import React, { useState } from "react";
import type { DeepenResponse, AnalysisLevel, ChartSpec, ChartOption } from "../api/types";
import ChartPanel from "./ChartPanel";
import { RecommendationList } from "./RecommendationCard";

interface DeepenSectionProps {
  level: AnalysisLevel;
  data?: DeepenResponse;
  loading?: boolean;
  onRetry?: () => void;
  onSwitchChart?: (chart: ChartSpec, option: ChartOption) => void;
  onResetToAuto?: (chart: ChartSpec) => void;
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

function renderFormattedText(text: string): React.ReactNode {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={idx} style={{ color: "var(--text-primary)" }}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

export const DeepenSection: React.FC<DeepenSectionProps> = ({
  level,
  data,
  loading = false,
  onRetry,
  onSwitchChart,
  onResetToAuto,
}) => {
  const [showBases, setShowBases] = useState(false);
  const info = LEVEL_TITLES[level] || LEVEL_TITLES.diagnostic;

  if (loading) {
    return (
      <div className="deepen-section-card" role="region" aria-label={`Đang tải ${info.title}`}>
        <div className="deepen-section-header">
          <div className="deepen-section-title-group">
            <h3 className="deepen-section-title">{info.title}</h3>
            <span className={`section-badge ${info.badgeClass}`}>{info.badge}</span>
          </div>
        </div>
        <div className="section-loading">
          <div className="spinner" />
          <span>Đang bóc tách số liệu chuyên sâu ({info.badge})...</span>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const mainSection = data.sections?.[0];
  const allCharts = data.sections?.flatMap((s) => s.charts || []) || [];
  const baseSections = data.sections?.filter((s) => s.level !== "prescriptive") || [];
  const realWarnings = (data.warnings || []).filter((w) => !w.toLowerCase().includes("chính sách"));

  return (
    <div className="deepen-section-card" role="region" aria-label={info.title}>
      <div className="deepen-section-header">
        <div className="deepen-section-title-group">
          <h3 className="deepen-section-title">{info.title}</h3>
          <span className={`section-badge ${info.badgeClass}`}>{info.badge}</span>
          {data.meta?.computed_in_sec && (
            <span className="section-time">({data.meta.computed_in_sec}s)</span>
          )}
        </div>
        {onRetry && (
          <button type="button" className="section-retry-btn" onClick={onRetry}>
            Tính lại
          </button>
        )}
      </div>

      {realWarnings.length > 0 && (
        <div className="section-warnings">
          {realWarnings.map((w, i) => (
            <div key={i}>⚠️ {w}</div>
          ))}
        </div>
      )}

      {mainSection?.narrative?.insight_text && (
        <div className="section-narrative">
          {renderFormattedText(mainSection.narrative.insight_text)}
        </div>
      )}

      {level === "prescriptive" && (
        <>
          <RecommendationList recommendations={data.recommendations} facts={data.facts} />

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
                          {renderFormattedText(sec.narrative.insight_text)}
                        </div>
                      )}
                      {sec.charts && sec.charts.length > 0 && (
                        <ChartPanel
                          charts={sec.charts}
                          onSwitchChart={onSwitchChart}
                          onResetToAuto={onResetToAuto}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {level !== "prescriptive" && allCharts.length > 0 && (
        <ChartPanel
          charts={allCharts}
          onSwitchChart={onSwitchChart}
          onResetToAuto={onResetToAuto}
        />
      )}
    </div>
  );
};
