import { useState, useCallback, useRef } from "react";
import type { FormEvent } from "react";
import { analyzeData } from "./api/client";
import type { AnalyzeResponse } from "./api/types";
import FileUpload from "./components/FileUpload";
import ChartPanel from "./components/ChartPanel";
import InsightCard from "./components/InsightCard";
import "./App.css";

// ── State machine ────────────────────────────────────────────
type AppState = "idle" | "loading" | "result" | "error";

const EXAMPLE_QUESTIONS = [
  "Xu hướng doanh thu theo tháng trong 12 tháng gần nhất?",
  "So sánh doanh thu giữa các chi nhánh năm nay?",
  "Chi nhánh nào có tốc độ tăng trưởng thấp nhất?",
  "Tổng doanh thu theo quý?",
];

export default function App() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [expandViews, setExpandViews] = useState(true);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [history, setHistory] = useState<{ question: string; result: AnalyzeResponse }[]>([]);
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const isLoading = appState === "loading";
  const canSubmit = !!file && question.trim().length > 0 && !isLoading;

  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      if (!canSubmit || !file) return;

      setAppState("loading");
      setErrorMsg(null);

      try {
        const data = await analyzeData(file, question.trim(), expandViews);
        setResult(data);
        setHistory((prev) => [{ question: question.trim(), result: data }, ...prev.slice(0, 4)]);
        setAppState("result");
        // Cuộn đến kết quả
        setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Lỗi không xác định");
        setAppState("error");
      }
    },
    [canSubmit, file, question, expandViews]
  );

  const handleReset = useCallback(() => {
    setAppState("idle");
    setResult(null);
    setErrorMsg(null);
    // Giữ file và question để người dùng có thể hỏi tiếp
  }, []);

  const handleNewQuestion = useCallback((q: string) => {
    setQuestion(q);
    questionRef.current?.focus();
  }, []);

  return (
    <div className="app-wrapper">
      {/* ── HEADER ── */}
      <header className="app-header glass">
        <div className="header-inner container">
          <div className="header-brand">
            <div className="brand-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="3" width="7" height="7" rx="1" fill="currentColor" opacity="0.8"/>
                <rect x="14" y="3" width="7" height="7" rx="1" fill="currentColor"/>
                <rect x="3" y="14" width="7" height="7" rx="1" fill="currentColor"/>
                <rect x="14" y="14" width="7" height="7" rx="1" fill="currentColor" opacity="0.6"/>
              </svg>
            </div>
            <div>
              <h1 className="brand-name gradient-text">AI Agent BI</h1>
              <p className="brand-tagline">Phân tích dữ liệu kinh doanh thông minh</p>
            </div>
          </div>
          <nav className="header-nav">
            <a href="/api/docs" target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2"/>
                <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="2"/>
              </svg>
              API Docs
            </a>
          </nav>
        </div>
      </header>

      {/* ── MAIN ── */}
      <main className="app-main container">

        {/* ── HERO ── */}
        <section className="hero-section">
          <div className="hero-badge badge badge-purple animate-fade-in">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
            Powered by Gemini AI
          </div>
          <h2 className="hero-title animate-fade-in-up">
            Đặt câu hỏi bằng <span className="gradient-text">ngôn ngữ tự nhiên</span>,<br />
            nhận biểu đồ và nhận xét tức thì
          </h2>
          <p className="hero-subtitle animate-fade-in-up">
            Tải lên file CSV hoặc Excel, hỏi về xu hướng, so sánh chi nhánh, tốc độ tăng trưởng —<br />
            AI sẽ phân tích và tạo biểu đồ tự động.
          </p>
        </section>

        {/* ── QUERY CARD ── */}
        <section className="query-section">
          <form className="query-card card" onSubmit={handleSubmit} noValidate>

            {/* File upload */}
            <div className="form-group">
              <label className="form-label">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2"/>
                  <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="2"/>
                </svg>
                Dữ liệu
              </label>
              <FileUpload
                onFileSelect={setFile}
                selectedFile={file}
                disabled={isLoading}
              />
            </div>

            {/* Question */}
            <div className="form-group">
              <label className="form-label" htmlFor="question-input">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Câu hỏi phân tích
              </label>
              <textarea
                id="question-input"
                ref={questionRef}
                className="input"
                rows={3}
                placeholder="Ví dụ: Xu hướng doanh thu theo tháng trong 12 tháng gần nhất?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
                }}
              />
              <div className="question-hint">
                <kbd>Ctrl</kbd> + <kbd>Enter</kbd> để gửi
              </div>
            </div>

            {/* Example questions */}
            <div className="example-questions">
              <span className="example-label">Ví dụ:</span>
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="example-chip"
                  onClick={() => handleNewQuestion(q)}
                  disabled={isLoading}
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Options */}
            <div className="form-options">
              <label className="checkbox-label" title="Tự động phân tích thêm các góc nhìn: xu hướng theo nhóm, tỷ trọng, biến động kỳ...">
                <input
                  type="checkbox"
                  checked={expandViews}
                  onChange={(e) => setExpandViews(e.target.checked)}
                  disabled={isLoading}
                />
                <span className="checkbox-text">
                  <strong>Hiển thị thêm góc nhìn</strong> (xu hướng theo chi nhánh, tỷ trọng, đóng góp thay đổi...)
                </span>
              </label>
            </div>

            {/* Submit */}
            <div className="form-actions">
              <button
                id="submit-btn"
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={!canSubmit}
              >
                {isLoading ? (
                  <>
                    <div className="spinner" />
                    Đang phân tích…
                  </>
                ) : (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                    </svg>
                    Phân tích ngay
                  </>
                )}
              </button>

              {(appState === "result" || appState === "error") && (
                <button type="button" className="btn btn-ghost" onClick={handleReset}>
                  Hỏi lại
                </button>
              )}
            </div>
          </form>
        </section>

        {/* ── LOADING STATE ── */}
        {isLoading && (
          <section className="loading-section animate-fade-in">
            <div className="loading-card card">
              <div className="loading-steps">
                {["Đọc & phân tích file dữ liệu (O1)", "Giải nghĩa câu hỏi bằng AI (O2)", "Sinh & chạy code phân tích (O3)", "Tạo biểu đồ (O4)", "Sinh nhận xét (O5)"].map((step, i) => (
                  <div key={i} className="loading-step" style={{ animationDelay: `${i * 0.4}s` }}>
                    <div className="loading-step-dot" style={{ animationDelay: `${i * 0.4}s` }} />
                    <span>{step}</span>
                  </div>
                ))}
              </div>
              <p className="loading-note">Quá trình phân tích có thể mất 10–30 giây tùy độ phức tạp của dữ liệu.</p>
            </div>
          </section>
        )}

        {/* ── ERROR STATE ── */}
        {appState === "error" && errorMsg && (
          <section className="error-section animate-slide-down">
            <div className="error-card card">
              <div className="error-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                  <line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </div>
              <div>
                <h3 className="error-title">Không thể phân tích</h3>
                <p className="error-message">{errorMsg}</p>
              </div>
            </div>
          </section>
        )}

        {/* ── RESULT STATE ── */}
        {appState === "result" && result && (
          <section className="result-section" ref={resultRef}>
            <div className="result-header">
              <div className="result-question">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                <span>"{result.goal.question}"</span>
              </div>
              <div className="result-stats">
                <span className="badge badge-green">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <polyline points="20 6 9 17 4 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  {result.charts.length} biểu đồ
                </span>
                {result.task_results.length > 0 && (
                  <span className="badge badge-blue">{result.task_results.length} nhiệm vụ</span>
                )}
              </div>
            </div>

            {/* Insight */}
            {result.insight && (
              <InsightCard insight={result.insight} goal={result.goal} />
            )}

            {/* Charts */}
            <ChartPanel charts={result.charts} />

            {/* Ask another question */}
            <div className="followup-card card animate-fade-in-up">
              <div className="followup-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <polyline points="9 14 4 9 9 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M20 20v-7a4 4 0 0 0-4-4H4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Hỏi tiếp (file giữ nguyên)
              </div>
              <div className="followup-chips">
                {[
                  "Tháng nào có doanh thu cao nhất?",
                  "Chi nhánh nào tăng trưởng tốt nhất?",
                  "So sánh hiệu suất từng quý?",
                ].map((q) => (
                  <button
                    key={q}
                    className="example-chip"
                    onClick={() => {
                      handleNewQuestion(q);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ── HISTORY (nếu có) ── */}
        {history.length > 1 && appState === "result" && (
          <section className="history-section animate-fade-in">
            <h3 className="history-title">Câu hỏi trước đó</h3>
            <div className="history-list">
              {history.slice(1).map((h, i) => (
                <button
                  key={i}
                  className="history-item"
                  onClick={() => {
                    setResult(h.result);
                    setQuestion(h.question);
                    setAppState("result");
                    resultRef.current?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                    <polyline points="12 6 12 12 16 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  {h.question}
                </button>
              ))}
            </div>
          </section>
        )}
      </main>

      {/* ── FOOTER ── */}
      <footer className="app-footer">
        <div className="container">
          <p>AI Agent BI – Đồ án tốt nghiệp · Dựa trên kiến trúc LIDA (Dibia, 2023)</p>
        </div>
      </footer>
    </div>
  );
}
