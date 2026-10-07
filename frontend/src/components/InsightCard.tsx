import type { InsightResult, AnalysisGoal } from "../api/types";
import "./InsightCard.css";

interface Props {
  insight: InsightResult;
  goal: AnalysisGoal;
}

const TIME_SCOPE_LABELS: Record<string, string> = {
  all: "Toàn bộ dữ liệu",
  last_3_months: "3 tháng gần nhất",
  last_6_months: "6 tháng gần nhất",
  last_12_months: "12 tháng gần nhất",
  custom: "Khoảng thời gian tùy chỉnh",
};

export default function InsightCard({ insight, goal }: Props) {
  const confidence = insight.confidence_score;
  const confidencePct = confidence != null ? Math.round(confidence * 100) : null;

  const confidenceColor =
    confidence == null ? "muted"
    : confidence >= 0.8 ? "green"
    : confidence >= 0.6 ? "orange"
    : "red";

  const confidenceLabel =
    confidence == null ? "—"
    : confidence >= 0.8 ? "Cao"
    : confidence >= 0.6 ? "Trung bình"
    : "Thấp";

  return (
    <div className="insight-card card animate-fade-in-up">
      {/* Header */}
      <div className="insight-header">
        <div className="insight-title-row">
          <div className="insight-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.5 4.5-3 6l-1 3H9l-1-3C6.5 13.5 5 11.5 5 9a7 7 0 0 1 7-7z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
              <line x1="9" y1="21" x2="15" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <h2 className="insight-title">Nhận Xét AI</h2>
        </div>

        <div className="insight-meta">
          <span className="badge badge-blue">{TIME_SCOPE_LABELS[goal.time_scope] ?? goal.time_scope}</span>
          {goal.time_start && goal.time_end && (
            <span className="insight-period">
              {goal.time_start} → {goal.time_end}
            </span>
          )}
        </div>
      </div>

      <div className="divider" />

      {/* Nội dung insight */}
      <p className="insight-text">{insight.insight_text}</p>

      {/* Confidence */}
      {confidencePct != null && (
        <div className="confidence-block">
          <div className="confidence-header">
            <span className="confidence-label">Độ tin cậy</span>
            <span className={`confidence-value confidence-${confidenceColor}`}>
              {confidenceLabel} ({confidencePct}%)
            </span>
          </div>
          <div className="progress-bar">
            <div
              className={`progress-fill progress-fill-${confidenceColor}`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      )}

      {/* Tasks summary */}
      {goal.tasks.length > 0 && (
        <div className="insight-tasks">
          <span className="insight-tasks-label">Nhiệm vụ đã phân tích:</span>
          <div className="insight-tasks-list">
            {goal.tasks.map((t, i) => (
              <span key={i} className={`badge ${t.type === "trend" ? "badge-blue" : t.type === "growth_rate" ? "badge-orange" : "badge-purple"}`}>
                {t.type === "trend" ? "Xu hướng" : t.type === "growth_rate" ? "Tăng trưởng" : "So sánh"}: {t.metric}
                {t.group_by ? ` / ${t.group_by}` : ""}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
