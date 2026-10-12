import React, { useState, useEffect, useRef } from "react";
import type { ExportSections } from "../api/types";
import "./ExportDialog.css";

export type ExportFormat = "pdf" | "excel" | "png";

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  supplementaryCount: number;
  onExport: (format: ExportFormat, sections: ExportSections, orgName: string) => Promise<void>;
}

const STORAGE_KEY_SECTIONS = "ai_agent_bi_export_sections";
const STORAGE_KEY_ORG = "ai_agent_bi_export_org";

export const ExportDialog: React.FC<ExportDialogProps> = ({
  isOpen,
  onClose,
  supplementaryCount,
  onExport,
}) => {
  const [format, setFormat] = useState<ExportFormat>("pdf");
  const [orgName, setOrgName] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY_ORG) || "";
    } catch {
      return "";
    }
  });

  const [sections, setSections] = useState<ExportSections>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SECTIONS);
      if (saved) return JSON.parse(saved);
    } catch {
      // Fallback
    }
    return {
      insight: true,
      primary_chart: true,
      supplementary_charts: true,
      data_tables: true,
      calculation_notes: true,
    };
  });

  const [isExporting, setIsExporting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFocusRef = useRef<HTMLInputElement>(null);

  // Esc key and focus trap
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    setTimeout(() => firstFocusRef.current?.focus(), 50);

    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleToggleSection = (key: keyof ExportSections) => {
    setSections((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem(STORAGE_KEY_SECTIONS, JSON.stringify(next));
      } catch {
        // Ignored
      }
      return next;
    });
  };

  const handleOrgNameChange = (val: string) => {
    setOrgName(val);
    try {
      localStorage.setItem(STORAGE_KEY_ORG, val);
    } catch {
      // Ignored
    }
  };

  const handleConfirm = async () => {
    setIsExporting(true);
    try {
      await onExport(format, sections, orgName);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="dialog-backdrop" onClick={onClose} role="presentation">
      <div
        className="dialog-card glass"
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-dialog-title"
      >
        <div className="dialog-header">
          <div className="dialog-title-group">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <h2 id="export-dialog-title" className="dialog-title">
              Xuất báo cáo phân tích
            </h2>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Đóng">
            ✕
          </button>
        </div>

        <div className="dialog-body">
          {/* Định dạng */}
          <div className="dialog-field-group">
            <label className="dialog-label">Định dạng file</label>
            <div className="format-options">
              <label className={`format-chip ${format === "pdf" ? "active" : ""}`}>
                <input
                  type="radio"
                  name="exportFormat"
                  value="pdf"
                  checked={format === "pdf"}
                  onChange={() => setFormat("pdf")}
                  ref={firstFocusRef}
                />
                <span className="format-icon">📄</span>
                <div>
                  <strong>PDF Báo cáo</strong>
                  <small>Vector in ấn sắc nét</small>
                </div>
              </label>

              <label className={`format-chip ${format === "excel" ? "active" : ""}`}>
                <input
                  type="radio"
                  name="exportFormat"
                  value="excel"
                  checked={format === "excel"}
                  onChange={() => setFormat("excel")}
                />
                <span className="format-icon">📊</span>
                <div>
                  <strong>Excel (.xlsx)</strong>
                  <small>Biểu đồ gốc chỉnh sửa được</small>
                </div>
              </label>

              <label className={`format-chip ${format === "png" ? "active" : ""}`}>
                <input
                  type="radio"
                  name="exportFormat"
                  value="png"
                  checked={format === "png"}
                  onChange={() => setFormat("png")}
                />
                <span className="format-icon">🖼️</span>
                <div>
                  <strong>Ảnh PNG</strong>
                  <small>Dán vào slide / báo cáo</small>
                </div>
              </label>
            </div>
          </div>

          {/* Nội dung báo cáo */}
          <div className="dialog-field-group">
            <label className="dialog-label">Nội dung bao gồm</label>
            <div className="sections-grid">
              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={sections.insight !== false}
                  onChange={() => handleToggleSection("insight")}
                />
                <span>Nhận xét AI</span>
              </label>

              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={sections.primary_chart !== false}
                  onChange={() => handleToggleSection("primary_chart")}
                />
                <span>Biểu đồ chính</span>
              </label>

              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={sections.supplementary_charts !== false}
                  onChange={() => handleToggleSection("supplementary_charts")}
                />
                <span>Góc nhìn bổ sung ({supplementaryCount})</span>
              </label>

              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={sections.data_tables !== false}
                  onChange={() => handleToggleSection("data_tables")}
                />
                <span>Bảng số liệu (Phụ lục A)</span>
              </label>

              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={sections.calculation_notes !== false}
                  onChange={() => handleToggleSection("calculation_notes")}
                />
                <span>Phương pháp tính (Phụ lục B)</span>
              </label>
            </div>
          </div>

          {/* Tên đơn vị */}
          <div className="dialog-field-group">
            <label htmlFor="org-name-input" className="dialog-label">
              Tên đơn vị / Doanh nghiệp <span className="label-hint">(hiện ở đầu báo cáo)</span>
            </label>
            <input
              id="org-name-input"
              type="text"
              className="text-input"
              placeholder="Ví dụ: Công ty Cổ phần ABC"
              value={orgName}
              onChange={(e) => handleOrgNameChange(e.target.value)}
            />
          </div>
        </div>

        <div className="dialog-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isExporting}>
            Hủy
          </button>
          <button className="btn btn-primary" onClick={handleConfirm} disabled={isExporting}>
            {isExporting ? "Đang xuất..." : "Xuất báo cáo"}
          </button>
        </div>
      </div>
    </div>
  );
};
