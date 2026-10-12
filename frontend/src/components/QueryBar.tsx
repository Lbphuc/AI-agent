import React from "react";
import "./QueryBar.css";

interface QueryBarProps {
  filename: string;
  question: string;
  onEdit: () => void;
  onReset: () => void;
}

export const QueryBar: React.FC<QueryBarProps> = ({
  filename,
  question,
  onEdit,
  onReset,
}) => {
  return (
    <div className="query-bar" role="region" aria-label="Thanh thông tin truy vấn">
      <div className="query-info">
        <div className="query-file-badge" title={`File dữ liệu: ${filename}`}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span className="file-name">{filename}</span>
        </div>

        <div className="query-text-container" title={question}>
          <span className="query-prefix">Câu hỏi:</span>
          <span className="query-question">“{question}”</span>
        </div>
      </div>

      <div className="query-actions">
        <button className="query-btn btn-edit" onClick={onEdit} title="Sửa câu hỏi hoặc file">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
          Sửa
        </button>
        <button className="query-btn btn-reset" onClick={onReset} title="Làm mới để phân tích câu hỏi khác">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
          Hỏi lại
        </button>
      </div>
    </div>
  );
};
