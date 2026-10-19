import React, { useState, useRef, useEffect } from "react";
import type {
  AnalysisLevel,
  AnalysisMode,
  ChartCatalogItem,
  ChartType,
} from "../api/types";
import "./ChartTypePicker.css";

export const CHART_NAMES: Record<ChartType, string> = {
  kpi: "Thẻ chỉ số (KPI)",
  bar: "Biểu đồ cột",
  bar_horizontal: "Biểu đồ cột ngang",
  line: "Biểu đồ đường",
  area: "Biểu đồ miền (Area)",
  pie: "Biểu đồ tròn (Pie)",
  stacked_bar: "Biểu đồ cột chồng",
  waterfall: "Biểu đồ thác nước",
  scatter: "Biểu đồ phân tán (Scatter)",
  heatmap: "Bản đồ nhiệt (Heatmap)",
  box: "Biểu đồ hộp (Box Plot)",
  histogram: "Biểu đồ tần suất (Histogram)",
};

interface ChartTypePickerProps {
  value?: ChartType | null;
  values?: ChartType[];
  onChange?: (chartType: ChartType | null) => void;
  onChangeMulti?: (chartTypes: ChartType[]) => void;
  catalog?: Record<string, ChartCatalogItem[]>;
  strategy: AnalysisLevel | AnalysisMode;
  disabled?: boolean;
}

export const ChartTypePicker: React.FC<ChartTypePickerProps> = ({
  value,
  values,
  onChange,
  onChangeMulti,
  catalog,
  strategy,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Normalize selected chart types
  const selectedTypes: ChartType[] = values
    ? values
    : value
    ? [value]
    : [];

  const updateSelection = (next: ChartType[]) => {
    if (onChangeMulti) {
      onChangeMulti(next);
    }
    if (onChange) {
      onChange(next[0] || null);
    }
  };

  const toggleChart = (type: ChartType) => {
    if (selectedTypes.includes(type)) {
      updateSelection(selectedTypes.filter((t) => t !== type));
    } else {
      updateSelection([...selectedTypes, type]);
    }
  };

  const removeChart = (type: ChartType, e: React.MouseEvent) => {
    e.stopPropagation();
    updateSelection(selectedTypes.filter((t) => t !== type));
  };

  const resetToAuto = () => {
    updateSelection([]);
    setIsOpen(false);
  };

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Handle keyboard navigation: Esc to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const levelKey = strategy === "auto" ? "descriptive" : strategy;
  const items: ChartCatalogItem[] = catalog?.[levelKey] || [];

  // Group items theo muc phu hop
  const recommendedItems = items.filter(
    (i) => i.fitness === "recommended" && i.verdict !== "blocked"
  );
  const okItems = items.filter(
    (i) => i.fitness === "ok" && i.verdict !== "blocked"
  );
  const confirmItems = items.filter(
    (i) => i.fitness === "confirm" && i.verdict !== "blocked"
  );
  const blockedItems = items.filter(
    (i) => i.fitness === "blocked" || i.verdict === "blocked"
  );

  const isPrescriptive = strategy === "prescriptive";

  return (
    <div className="chart-picker-container" ref={dropdownRef}>
      {/* 1. Hiển thị các tag biểu đồ đã chọn (nếu có) */}
      {selectedTypes.length > 0 && (
        <div className="chart-picker-tags">
          {selectedTypes.map((t) => (
            <span key={t} className="chart-chip-tag">
              <span>{CHART_NAMES[t] || t}</span>
              <button
                type="button"
                className="chart-chip-remove"
                onClick={(e) => removeChart(t, e)}
                title={`Bỏ chọn ${CHART_NAMES[t] || t}`}
                aria-label={`Bỏ chọn ${CHART_NAMES[t] || t}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* 2. Nút bấm mở dropdown thêm biểu đồ */}
      <button
        type="button"
        className={`chart-picker-trigger ${selectedTypes.length > 0 ? "active" : ""}`}
        onClick={() => !disabled && !isPrescriptive && setIsOpen(!isOpen)}
        disabled={disabled || isPrescriptive}
        title={
          isPrescriptive
            ? "Gợi ý chiến lược hiển thị bằng thẻ khuyến nghị; biểu đồ căn cứ dùng chế độ tự động."
            : "Chọn một hoặc nhiều loại biểu đồ mong muốn"
        }
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span>
          {selectedTypes.length === 0
            ? "Biểu đồ: Tự động"
            : `+ Thêm biểu đồ (${selectedTypes.length})`}
        </span>
        <span style={{ fontSize: "10px", opacity: 0.7 }}>▾</span>
      </button>

      {/* 3. Nút đặt lại về Tự động khi có biểu đồ được chọn */}
      {selectedTypes.length > 0 && !disabled && (
        <button
          type="button"
          className="chart-picker-chip-reset"
          onClick={resetToAuto}
          title="Đặt lại về chế độ Tự động"
          aria-label="Đặt lại về Tự động"
        >
          <span>✕ Đặt lại Tự động</span>
        </button>
      )}

      {/* 4. Menu Dropdown đa lựa chọn */}
      {isOpen && (
        <div className="chart-picker-dropdown" role="listbox" aria-multiselectable="true">
          {/* Mục Tự động mặc định */}
          <div
            role="option"
            aria-selected={selectedTypes.length === 0}
            className={`chart-picker-item ${selectedTypes.length === 0 ? "selected" : ""}`}
            onClick={resetToAuto}
          >
            <div className="chart-picker-item-left">
              <span className="chart-checkbox-box">
                {selectedTypes.length === 0 && "✓"}
              </span>
              <span><strong>✨ Tự động</strong> (Khuyên dùng)</span>
            </div>
            {selectedTypes.length === 0 && <span style={{ fontSize: "12px", color: "#60a5fa" }}>Mặc định</span>}
          </div>

          <div style={{ height: "1px", background: "var(--border, #333d4e)", margin: "4px 0" }} />

          {/* Nhóm Khuyến nghị (★ Phù hợp nhất) */}
          {recommendedItems.length > 0 && (
            <div>
              <div className="chart-picker-group-title">
                <span>★ Phù hợp nhất</span>
              </div>
              {recommendedItems.map((item) => {
                const isSoon = item.status === "soon";
                const isSelected = selectedTypes.includes(item.chart_type);
                return (
                  <div
                    key={item.chart_type}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={isSoon}
                    className={`chart-picker-item ${isSelected ? "selected" : ""} ${isSoon ? "disabled" : ""}`}
                    onClick={() => !isSoon && toggleChart(item.chart_type)}
                  >
                    <div className="chart-picker-item-left">
                      <span className="chart-checkbox-box">
                        {isSelected && "✓"}
                      </span>
                      <span>{item.display_name}</span>
                    </div>
                    {isSoon && <span className="chart-badge badge-soon">Sắp có</span>}
                  </div>
                );
              })}
            </div>
          )}

          {/* Nhóm Dùng được (○ Dùng được) */}
          {okItems.length > 0 && (
            <div>
              <div className="chart-picker-group-title">
                <span>○ Dùng được</span>
              </div>
              {okItems.map((item) => {
                const isSoon = item.status === "soon";
                const isSelected = selectedTypes.includes(item.chart_type);
                return (
                  <div
                    key={item.chart_type}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={isSoon}
                    className={`chart-picker-item ${isSelected ? "selected" : ""} ${isSoon ? "disabled" : ""}`}
                    onClick={() => !isSoon && toggleChart(item.chart_type)}
                  >
                    <div className="chart-picker-item-left">
                      <span className="chart-checkbox-box">
                        {isSelected && "✓"}
                      </span>
                      <span>{item.display_name}</span>
                    </div>
                    {isSoon && <span className="chart-badge badge-soon">Sắp có</span>}
                  </div>
                );
              })}
            </div>
          )}

          {/* Nhóm Ít phù hợp (⚠ Xác nhận 1 lần) */}
          {confirmItems.length > 0 && (
            <div>
              <div className="chart-picker-group-title">
                <span>⚠ Ít phù hợp (Xác nhận 1 lần)</span>
              </div>
              {confirmItems.map((item) => {
                const isSoon = item.status === "soon";
                const isSelected = selectedTypes.includes(item.chart_type);
                return (
                  <div
                    key={item.chart_type}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={isSoon}
                    className={`chart-picker-item ${isSelected ? "selected" : ""} ${isSoon ? "disabled" : ""}`}
                    onClick={() => !isSoon && toggleChart(item.chart_type)}
                  >
                    <div className="chart-picker-item-left">
                      <span className="chart-checkbox-box">
                        {isSelected && "✓"}
                      </span>
                      <span>{item.display_name}</span>
                    </div>
                    {isSoon ? (
                      <span className="chart-badge badge-soon">Sắp có</span>
                    ) : (
                      <span className="chart-badge badge-single-confirm">Xác nhận 1 lần</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Nhóm Không áp dụng (⛔ Không áp dụng - Xác nhận 2 lần) - CHO PHÉP CHỌN, KHÔNG CHẶN */}
          {blockedItems.length > 0 && (
            <div>
              <div className="chart-picker-group-title">
                <span>⛔ Không áp dụng (Xác nhận 2 lần)</span>
              </div>
              {blockedItems.map((item) => {
                const isSoon = item.status === "soon";
                const isSelected = selectedTypes.includes(item.chart_type);
                return (
                  <div
                    key={item.chart_type}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={isSoon}
                    className={`chart-picker-item ${isSelected ? "selected" : ""} ${isSoon ? "disabled" : ""}`}
                    onClick={() => !isSoon && toggleChart(item.chart_type)}
                    title={
                      isSoon
                        ? "Đang phát triển"
                        : "Biểu đồ này không tương thích với dữ liệu/chiến lược, cần xác nhận 2 lần khi phân tích"
                    }
                  >
                    <div className="chart-picker-item-left">
                      <span className="chart-checkbox-box">
                        {isSelected && "✓"}
                      </span>
                      <span>{item.display_name}</span>
                    </div>
                    {isSoon ? (
                      <span className="chart-badge badge-soon">Sắp có</span>
                    ) : (
                      <span className="chart-badge badge-double-confirm">Xác nhận 2 lần</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
