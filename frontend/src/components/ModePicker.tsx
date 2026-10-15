import React, { useRef } from "react";
import type { AnalysisMode, ModeAvailability } from "../api/types";
import "./ModePicker.css";

export interface ModeDef {
  id: AnalysisMode;
  label: string;
  hint: string;
  icon: string;
  requires: "descriptive" | "diagnostic" | "forecast" | "prescriptive" | null;
}

export const ANALYSIS_MODES: ModeDef[] = [
  {
    id: "auto",
    label: "Tự động",
    hint: "Hệ thống tự hiểu bạn cần gì",
    icon: "wand",
    requires: null,
  },
  {
    id: "descriptive",
    label: "Tổng quan",
    hint: "Xem bức tranh toàn cảnh",
    icon: "layout",
    requires: "descriptive",
  },
  {
    id: "diagnostic",
    label: "Tìm nguyên nhân",
    hint: "Xem yếu tố nào đóng góp nhiều nhất vào thay đổi",
    icon: "search",
    requires: "diagnostic",
  },
  {
    id: "forecast",
    label: "Dự đoán tương lai",
    hint: "Ước tính xu hướng sắp tới",
    icon: "trend",
    requires: "forecast",
  },
  {
    id: "prescriptive",
    label: "Gợi ý chiến lược",
    hint: "Gợi ý tham khảo dựa trên số liệu của bạn",
    icon: "bulb",
    requires: "prescriptive",
  },
];

interface ModePickerProps {
  currentMode: AnalysisMode;
  onModeChange: (mode: AnalysisMode) => void;
  availability?: Record<string, ModeAvailability>;
  disabled?: boolean;
}

function renderModeIcon(icon: string) {
  switch (icon) {
    case "wand":
      return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M15 4V2m0 16v-2m7-7h-2M4 11H2m15.07-7.07l-1.41 1.41M5.34 16.66l-1.41 1.41m0-14.14l1.41 1.41m11.32 11.32l1.41 1.41" />
          <path d="m14 9-9 9" />
        </svg>
      );
    case "layout":
      return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      );
    case "search":
      return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case "trend":
      return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
          <polyline points="17 6 23 6 23 12" />
        </svg>
      );
    case "bulb":
      return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 18h6" />
          <path d="M10 22h4" />
          <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5" />
        </svg>
      );
    default:
      return null;
  }
}

export const ModePicker: React.FC<ModePickerProps> = ({
  currentMode,
  onModeChange,
  availability,
  disabled = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const activeDef = ANALYSIS_MODES.find((m) => m.id === currentMode) || ANALYSIS_MODES[0];

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let newIndex = -1;
    if (e.key === "ArrowRight") {
      newIndex = (index + 1) % ANALYSIS_MODES.length;
    } else if (e.key === "ArrowLeft") {
      newIndex = (index - 1 + ANALYSIS_MODES.length) % ANALYSIS_MODES.length;
    }

    if (newIndex >= 0) {
      e.preventDefault();
      const targetMode = ANALYSIS_MODES[newIndex];
      const isTargetAvailable =
        !targetMode.requires ||
        !availability ||
        availability[targetMode.requires]?.available !== false;

      if (isTargetAvailable) {
        onModeChange(targetMode.id);
        const buttons = containerRef.current?.querySelectorAll<HTMLButtonElement>("button.mode-pill");
        buttons?.[newIndex]?.focus();
      }
    }
  };

  return (
    <div className="mode-picker-container" role="region" aria-label="Chọn chế độ phân tích">
      <div
        className="mode-picker-pills"
        role="radiogroup"
        aria-label="Chế độ phân tích"
        ref={containerRef}
      >
        {ANALYSIS_MODES.map((mode, index) => {
          const isSelected = mode.id === currentMode;
          const req = mode.requires;
          const availInfo = req && availability ? availability[req] : undefined;
          const isAvailable = availInfo ? availInfo.available : true;
          const isDisabled = disabled || !isAvailable;
          const disabledReason = !isAvailable ? availInfo?.reason || "Chưa đủ dữ liệu cho chế độ này" : undefined;

          return (
            <button
              key={mode.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              aria-disabled={!isAvailable}
              tabIndex={isSelected ? 0 : -1}
              className={`mode-pill ${isSelected ? "active" : ""}`}
              disabled={isDisabled}
              title={disabledReason || mode.hint}
              onClick={() => {
                if (!isDisabled) {
                  onModeChange(mode.id);
                } else if (disabledReason) {
                  alert(disabledReason);
                }
              }}
              onKeyDown={(e) => handleKeyDown(e, index)}
            >
              <span className="mode-pill-icon">{renderModeIcon(mode.icon)}</span>
              <span className="mode-pill-label">{mode.label}</span>
            </button>
          );
        })}
      </div>

      <div className="mode-picker-hint">
        <span>{activeDef.hint}</span>
        {activeDef.id !== "auto" && activeDef.id !== "descriptive" && (
          <span className="mode-picker-hint-badge">• Đã bao gồm phần Tổng quan</span>
        )}
      </div>
    </div>
  );
};
