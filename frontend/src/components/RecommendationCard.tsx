import React from "react";
import type { Recommendation, Fact } from "../api/types";
import { FactChip } from "./FactChip";
import "./RecommendationCard.css";

interface RecommendationCardProps {
  recommendation: Recommendation;
  factsMap?: Record<string, Fact>;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation,
  factsMap = {},
}) => {
  const priorityClass = `priority-${recommendation.priority.replace(/\s+/g, "-")}`;

  return (
    <div className="recommendation-card">
      <div className="rec-header">
        <div className="rec-title-group">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--accent)" }}>
            <path d="M9 18h6" />
            <path d="M10 22h4" />
            <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5" />
          </svg>
          <h4 className="rec-title">{recommendation.title}</h4>
        </div>
        <span className={`rec-priority ${priorityClass}`}>
          {recommendation.priority}
        </span>
      </div>

      <div className="rec-body">
        <div className="rec-action">
          <strong>Hành động:</strong> {recommendation.action}
        </div>
        <div className="rec-rationale">
          <strong>Căn cứ:</strong> {recommendation.rationale}
        </div>
      </div>

      {recommendation.fact_ids && recommendation.fact_ids.length > 0 && (
        <div className="rec-citations">
          <span className="rec-citations-label">Dẫn chứng số liệu:</span>
          <div className="rec-chips">
            {recommendation.fact_ids.map((fid) => (
              <FactChip key={fid} factId={fid} fact={factsMap[fid]} />
            ))}
          </div>
        </div>
      )}

      {recommendation.caveat && (
        <div className="rec-caveat">
          <span className="rec-caveat-label">Cần kiểm chứng: </span>
          <span>{recommendation.caveat}</span>
        </div>
      )}
    </div>
  );
};

interface RecommendationListProps {
  recommendations: Recommendation[];
  facts?: Fact[];
}

export const RecommendationList: React.FC<RecommendationListProps> = ({
  recommendations,
  facts = [],
}) => {
  const factsMap: Record<string, Fact> = {};
  for (const f of facts) {
    factsMap[f.id] = f;
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="recommendations-container">
        <div className="rec-caveat">
          Chưa đủ bằng chứng để đưa ra đề xuất chiến lược cụ thể dựa trên dữ liệu hiện tại.
        </div>
      </div>
    );
  }

  return (
    <div className="recommendations-container">
      {recommendations.map((rec, i) => (
        <RecommendationCard key={i} recommendation={rec} factsMap={factsMap} />
      ))}
      <div className="recommendations-disclaimer">
        * Gợi ý tham khảo do AI tổng hợp từ số liệu trong file của bạn; chưa tính chi phí, biên lợi nhuận hay bối cảnh bên ngoài.
      </div>
    </div>
  );
};
