import React, { useState } from "react";
import { RAIL_ITEMS, type IconName } from "../features";
import "./AppRail.css";

const STORAGE_KEY_RAIL = "ai_agent_bi_rail_expanded";

interface AppRailProps {
  activeId: string;
  onSelect: (id: string) => void;
}

export const AppRail: React.FC<AppRailProps> = ({ activeId, onSelect }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_RAIL);
      return saved !== null ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const toggleRail = () => {
    setIsExpanded((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY_RAIL, JSON.stringify(next));
      } catch {
        // Ignored
      }
      return next;
    });
  };

  return (
    <aside
      className={`app-rail ${isExpanded ? "expanded" : "collapsed"}`}
      aria-label="Điều hướng ứng dụng"
    >
      <div className="rail-items-list">
        {RAIL_ITEMS.map((item) => {
          const isActive = item.id === activeId;
          const isSoon = item.status === "soon";

          return (
            <button
              key={item.id}
              className={`rail-btn ${isActive ? "active" : ""} ${isSoon ? "soon" : ""}`}
              onClick={() => {
                if (!isSoon) onSelect(item.id);
              }}
              disabled={isSoon}
              title={isSoon ? `${item.label} (Tính năng sắp có)` : item.label}
              aria-label={item.label}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="rail-icon">
                <RailIcon icon={item.icon} />
              </span>
              {isExpanded && <span className="rail-label">{item.label}</span>}
              {isExpanded && isSoon && <span className="soon-badge">Sắp có</span>}
            </button>
          );
        })}
      </div>

      <div className="rail-footer">
        <button
          className="rail-toggle-btn"
          onClick={toggleRail}
          title={isExpanded ? "Thu gọn thanh bên" : "Mở rộng thanh bên"}
          aria-label={isExpanded ? "Thu gọn thanh bên" : "Mở rộng thanh bên"}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{ transform: isExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          {isExpanded && <span className="rail-label">Thu gọn</span>}
        </button>
      </div>
    </aside>
  );
};

function RailIcon({ icon }: { icon: IconName }) {
  switch (icon) {
    case "sparkles":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
        </svg>
      );
    case "clock":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case "bookmark":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />
        </svg>
      );
    case "gear":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    default:
      return null;
  }
}
