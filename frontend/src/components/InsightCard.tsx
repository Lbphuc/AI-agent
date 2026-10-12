import { useState } from "react";
import type { InsightResult, AnalysisGoal, ReportMeta } from "../api/types";
import "./InsightCard.css";

interface Props {
  insight: InsightResult;
  goal: AnalysisGoal;
  meta?: ReportMeta | null;
}

export default function InsightCard({ insight, goal, meta }: Props) {
  const [copied, setCopied] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(false);

  const confidence = insight.confidence_score;
  const isLowConfidence = confidence != null && confidence < 0.8;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(insight.insight_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignored
    }
  };

  const goalSummary = meta?.goal_summary || `Hệ thống đã phân tích dữ liệu theo câu hỏi: “${goal.question}”.`;

  return (
    <div className="insight-card">
      <div className="insight-card-header">
        <div className="insight-title-group">
          <div className="insight-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2a7 7 0 0 1 7 7c0 2.5-1.5 4.5-3 6l-1 3H9l-1-3C6.5 13.5 5 11.5 5 9a7 7 0 0 1 7-7z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
              />
              <line x1="9" y1="21" x2="15" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
          <h2 className="insight-heading">Nhận xét phân tích</h2>
        </div>

        <button className="btn-copy" onClick={handleCopy} title="Sao chép nội dung nhận xét">
          {copied ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Đã sao chép
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              Sao chép
            </>
          )}
        </button>
      </div>

      {/* Goal Summary */}
      {goalSummary && (
        <div className="insight-goal-summary">
          <strong>Hệ thống hiểu câu hỏi của bạn là:</strong> {goalSummary}
        </div>
      )}

      {/* Insight Text */}
      <div className="insight-body">
        <p className="insight-text">{insight.insight_text}</p>
      </div>

      {/* Cảnh báo chỉ hiện khi độ tin cậy thấp (< 0.8) */}
      {isLowConfidence && (
        <div className="insight-warning-box">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>Một số con số trong nhận xét chưa khớp hoàn toàn dữ liệu, hãy đối chiếu với bảng số liệu trước khi dùng.</span>
        </div>
      )}

      {/* Chi tiết kỹ thuật thu gọn */}
      <div className="tech-details-container">
        <button
          className="tech-details-toggle"
          onClick={() => setShowTechDetails(!showTechDetails)}
          aria-expanded={showTechDetails}
        >
          <span>Chi tiết kỹ thuật</span>
          <span className="toggle-arrow">{showTechDetails ? "▴" : "▾"}</span>
        </button>

        {showTechDetails && (
          <div className="tech-details-content">
            {confidence != null && (
              <div className="tech-detail-row">
                <span className="detail-label">Độ khớp số liệu:</span>
                <span className="detail-value">{Math.round(confidence * 100)}%</span>
              </div>
            )}
            {meta?.model_name && (
              <div className="tech-detail-row">
                <span className="detail-label">Mô hình AI:</span>
                <span className="detail-value">{meta.model_name}</span>
              </div>
            )}
            {meta && (
              <div className="tech-detail-row">
                <span className="detail-label">Số dòng dữ liệu:</span>
                <span className="detail-value">{meta.rows_used} / {meta.rows_total} dòng</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
