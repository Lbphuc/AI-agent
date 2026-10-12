import React from "react";
import "./AppHeader.css";

export const AppHeader: React.FC = () => {
  return (
    <header className="app-header">
      <div className="header-left">
        <div className="header-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="3" width="7" height="7" rx="2" fill="var(--accent)" />
            <rect x="14" y="3" width="7" height="7" rx="2" fill="var(--chart-3)" />
            <rect x="3" y="14" width="7" height="7" rx="2" fill="var(--chart-2)" />
            <rect x="14" y="14" width="7" height="7" rx="2" fill="var(--chart-4)" />
          </svg>
        </div>
        <div className="header-brand-info">
          <h1 className="header-title">AI Agent BI</h1>
          <span className="header-badge">v0.1.0</span>
        </div>
      </div>

      <nav className="header-nav" aria-label="Điều hướng chính">
        <a
          href="/api/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="header-link"
          title="Tài liệu API Swagger"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          API Docs
        </a>
      </nav>
    </header>
  );
};
