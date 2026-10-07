import { useRef, useState, useCallback } from "react";
import type { DragEvent, ChangeEvent } from "react";
import "./FileUpload.css";

interface Props {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  disabled?: boolean;
}

const ACCEPTED = ".csv,.xlsx,.xls";
const MAX_SIZE_MB = 20;

export default function FileUpload({ onFileSelect, selectedFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback((file: File): string | null => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["csv", "xlsx", "xls"].includes(ext ?? "")) {
      return "Chỉ chấp nhận file CSV hoặc Excel (.csv, .xlsx, .xls)";
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File quá lớn (tối đa ${MAX_SIZE_MB} MB)`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      const err = validate(file);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      onFileSelect(file);
    },
    [validate, onFileSelect]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset input để cho phép upload lại cùng file
      e.target.value = "";
    },
    [handleFile]
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="file-upload-wrapper">
      <div
        id="file-drop-zone"
        className={`file-drop-zone ${dragging ? "dragging" : ""} ${selectedFile ? "has-file" : ""} ${disabled ? "disabled" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={disabled ? undefined : onDrop}
        onClick={() => { if (!disabled) inputRef.current?.click(); }}
        role="button"
        tabIndex={0}
        aria-label="Kéo thả hoặc bấm để chọn file dữ liệu"
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          onChange={onInputChange}
          className="file-input-hidden"
          aria-hidden="true"
        />

        {selectedFile ? (
          <div className="file-info animate-fade-in">
            <div className="file-icon file-icon-active">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <polyline points="10 9 9 9 8 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="file-meta">
              <span className="file-name">{selectedFile.name}</span>
              <span className="file-size">{formatSize(selectedFile.size)}</span>
            </div>
            <div className="file-change-hint">Bấm để đổi file</div>
          </div>
        ) : (
          <div className="file-placeholder">
            <div className="file-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <polyline points="16 16 12 12 8 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <line x1="12" y1="12" x2="12" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="file-hint-text">
              <span className="file-hint-primary">Kéo thả file vào đây</span>
              <span className="file-hint-secondary">hoặc bấm để chọn</span>
            </div>
            <div className="file-formats">
              <span className="badge badge-blue">CSV</span>
              <span className="badge badge-purple">XLSX</span>
              <span className="badge badge-blue">XLS</span>
              <span className="file-formats-note">• Tối đa {MAX_SIZE_MB} MB</span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="file-error animate-slide-down" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
            <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
