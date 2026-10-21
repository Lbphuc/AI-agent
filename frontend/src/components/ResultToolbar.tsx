import React from "react";
import { RESULT_ACTIONS, type ToolbarAction } from "../features";
import "./ResultToolbar.css";

interface ResultToolbarProps {
  chartCount: number;
  timeRangeStr?: string | null;
  primaryMethod?: string | null;
  onOpenExport: () => void;
}

export const ResultToolbar: React.FC<ResultToolbarProps> = ({
  chartCount,
  timeRangeStr,
  primaryMethod,
  onOpenExport,
}) => {
  return (
    <div className="result-toolbar" role="toolbar" aria-label="Thanh công cụ kết quả">
      <div className="toolbar-summary">
        {primaryMethod && (
          <span className="badge-chip badge-primary-method" style={{ background: "rgba(59, 130, 246, 0.15)", color: "#38bdf8", borderColor: "rgba(59, 130, 246, 0.3)" }}>
            <span style={{ fontWeight: 600 }}>Phương pháp:</span> {primaryMethod}
          </span>
        )}

        <span className="badge-chip">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          {chartCount} biểu đồ
        </span>

        {timeRangeStr && (
          <span className="badge-chip">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            {timeRangeStr}
          </span>
        )}
      </div>

      <div className="toolbar-actions">
        {RESULT_ACTIONS.map((action) => {
          const isExport = action.id === "export";
          const isSoon = action.status === "soon";

          return (
            <button
              key={action.id}
              className={`toolbar-btn ${isExport ? "btn-accent" : ""} ${isSoon ? "soon" : ""}`}
              onClick={isExport ? onOpenExport : undefined}
              disabled={isSoon}
              title={isSoon ? `${action.label} (Sắp có)` : action.label}
              aria-label={action.label}
            >
              <ActionIcon action={action} />
              <span>{action.label}</span>
              {isExport && <span className="btn-caret">▾</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
};

function ActionIcon({ action }: { action: ToolbarAction }) {
  if (action.id === "export") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    );
  }
  if (action.id === "feedback") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
      </svg>
    );
  }
  if (action.id === "share") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
    );
  }
  return null;
}
