import { useState, useCallback, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import type { FormEvent } from "react";
import { analyzeData } from "./api/client";
import type { AnalyzeResponse, ExportSections } from "./api/types";
import FileUpload from "./components/FileUpload";
import ChartPanel from "./components/ChartPanel";
import InsightCard from "./components/InsightCard";
import { AppHeader } from "./components/AppHeader";
import { AppRail } from "./components/AppRail";
import { QueryBar } from "./components/QueryBar";
import { ResultToolbar } from "./components/ResultToolbar";
import { ExportDialog, type ExportFormat } from "./export/ExportDialog";
import { ReportDocument } from "./export/ReportDocument";
import { buildReportModel } from "./export/buildReportModel";
import { triggerPrintReport } from "./export/printReport";
import { exportToExcel } from "./export/exportApi";
import "./App.css";

type AppState = "idle" | "loading" | "result" | "error";

const EXAMPLE_QUESTIONS = [
  "Xu hướng doanh thu theo tháng trong 12 tháng gần nhất?",
  "So sánh doanh thu giữa các chi nhánh năm nay?",
  "Chi nhánh nào có tốc độ tăng trưởng thấp nhất?",
  "Tổng doanh thu theo quý?",
];

export default function App() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [activeRailId, setActiveRailId] = useState("analyze");
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [expandViews, setExpandViews] = useState(true);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Trạng thái thu gọn/mở rộng biểu mẫu khi đang ở màn hình kết quả
  const [isFormExpanded, setIsFormExpanded] = useState(false);

  // Hộp thoại xuất báo cáo
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [reportOrgName, setReportOrgName] = useState("");
  const [exportSections, setExportSections] = useState<ExportSections>({
    insight: true,
    primary_chart: true,
    supplementary_charts: true,
    data_tables: true,
    calculation_notes: true,
  });

  const questionRef = useRef<HTMLTextAreaElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const isLoading = appState === "loading";
  const hasResult = appState === "result" && result !== null;
  const canSubmit = !!file && question.trim().length > 0 && !isLoading;

  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      if (!canSubmit || !file) return;

      setAppState("loading");
      setErrorMsg(null);
      setIsFormExpanded(false);

      try {
        const data = await analyzeData(file, question.trim(), expandViews);
        setResult(data);
        setAppState("result");
        setTimeout(() => {
          resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 80);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.");
        setAppState("error");
      }
    },
    [canSubmit, file, question, expandViews]
  );

  const handleReset = useCallback(() => {
    setAppState("idle");
    setResult(null);
    setErrorMsg(null);
    setIsFormExpanded(false);
  }, []);

  const handleEditQuery = useCallback(() => {
    setIsFormExpanded(true);
    setTimeout(() => {
      questionRef.current?.focus();
    }, 100);
  }, []);

  const handleNewQuestion = useCallback((q: string) => {
    setQuestion(q);
    setIsFormExpanded(true);
    questionRef.current?.focus();
  }, []);

  // Đếm số góc nhìn bổ sung
  const supplementaryCount = useMemo(() => {
    if (!result?.charts) return 0;
    return result.charts.filter((c) => c.role === "supplementary").length;
  }, [result]);

  // Chuỗi khoảng thời gian
  const timeRangeStr = useMemo(() => {
    if (!result?.goal) return null;
    const { time_start, time_end } = result.goal;
    if (time_start && time_end) return `${time_start} – ${time_end}`;
    return null;
  }, [result]);

  // Model dữ liệu báo cáo cho trang in ẩn (#print-root)
  const reportModel = useMemo(() => {
    if (!result) return null;
    return buildReportModel(
      result,
      file?.name || "data.csv",
      exportSections,
      reportOrgName
    );
  }, [result, file, exportSections, reportOrgName]);

  // Xử lý xuất báo cáo theo các định dạng
  const handleExport = useCallback(
    async (format: ExportFormat, sections: ExportSections, orgName: string) => {
      if (!result) return;
      setExportSections(sections);
      setReportOrgName(orgName);

      if (format === "pdf") {
        triggerPrintReport(file?.name || "data.csv");
      } else if (format === "excel") {
        await exportToExcel(result, file?.name || "data.csv", sections, orgName);
      } else if (format === "png") {
        // Tải ảnh PNG cho biểu đồ chính
        const primaryCard = document.querySelector(".col-span-12 .chart-card") as HTMLElement;
        if (primaryCard && result.charts[0]) {
          const { exportChartToPng } = await import("./export/exportPng");
          await exportChartToPng(primaryCard, result.charts[0].title);
        } else {
          alert("Vui lòng bấm nút '⋯' trên góc từng biểu đồ để tải ảnh PNG riêng biệt.");
        }
      }
    },
    [result, file]
  );

  return (
    <div className="app-shell">
      {/* ── 1. HEADER CỐ ĐỊNH 56px ── */}
      <AppHeader />

      <div className="app-main-layout">
        {/* ── 2. THANH BÊN ĐIỀU HƯỚNG (RAIL) ── */}
        <AppRail activeId={activeRailId} onSelect={setActiveRailId} />

        {/* ── 3. KHU VỰC NỘI DUNG CHÍNH ── */}
        <div className="app-content-wrapper">
          {/* Thanh truy vấn thu gọn (chỉ hiện khi đã có kết quả trong workspace) */}
          {hasResult && !isFormExpanded && (
            <QueryBar
              filename={file?.name || "data.csv"}
              question={question}
              onEdit={handleEditQuery}
              onReset={handleReset}
            />
          )}

          {/* TRƯỜNG HỢP 1: LANDING STATE (Chưa có kết quả hoặc đang bấm Sửa) */}
          {(!hasResult || isFormExpanded) && (
            <main className="landing-content">
              {!hasResult && (
                <section className="hero-section">
                  <div className="hero-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                    </svg>
                    Hệ thống AI Phân tích Dữ liệu Kinh doanh
                  </div>
                  <h2 className="hero-title">
                    Phân tích dữ liệu bằng ngôn ngữ tự nhiên
                  </h2>
                  <p className="hero-subtitle">
                    Tải lên file dữ liệu doanh thu, chi nhánh hoặc bán hàng — đặt câu hỏi bằng tiếng Việt để xem biểu đồ và nhận xét tức thì.
                  </p>
                </section>
              )}

              {/* Form truy vấn */}
              <form className="query-card" onSubmit={handleSubmit} noValidate>
                <div className="form-group">
                  <label className="form-label">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    Tập dữ liệu phân tích
                  </label>
                  <FileUpload onFileSelect={setFile} selectedFile={file} disabled={isLoading} />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="question-input">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    Câu hỏi của bạn
                  </label>
                  <textarea
                    id="question-input"
                    ref={questionRef}
                    className="question-textarea"
                    rows={3}
                    placeholder="Ví dụ: So sánh doanh thu giữa các chi nhánh trong năm nay?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={isLoading}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
                    }}
                  />
                  <div className="question-hint">Nhấn Ctrl + Enter để gửi câu hỏi</div>
                </div>

                {/* Câu hỏi gợi ý */}
                <div className="example-questions">
                  <span className="example-label">Gợi ý:</span>
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

                <div className="form-options">
                  <label className="checkbox-label" title="Tự động bổ sung các góc nhìn: xu hướng theo nhóm, tỷ trọng, đóng góp thay đổi...">
                    <input
                      type="checkbox"
                      checked={expandViews}
                      onChange={(e) => setExpandViews(e.target.checked)}
                      disabled={isLoading}
                    />
                    <span>
                      <strong>Dashboard đa góc nhìn:</strong> Tự động phân tích thêm xu hướng, tỷ trọng và đóng góp thay đổi
                    </span>
                  </label>
                </div>

                <div className="form-actions">
                  <button type="submit" className="btn-primary" disabled={!canSubmit}>
                    {isLoading ? (
                      <>
                        <div className="spinner" />
                        Đang phân tích...
                      </>
                    ) : (
                      <>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                        </svg>
                        Phân tích ngay
                      </>
                    )}
                  </button>

                  {hasResult && isFormExpanded && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setIsFormExpanded(false)}
                    >
                      Đóng biểu mẫu
                    </button>
                  )}
                </div>
              </form>

              {/* Trạng thái đang tải */}
              {isLoading && (
                <div className="loading-card">
                  <div className="loading-steps">
                    {[
                      "Đọc & thẩm định cấu trúc dữ liệu",
                      "Hiểu câu hỏi và trích xuất chỉ số",
                      "Tính toán các số liệu thống kê",
                      "Tạo các biểu đồ trực quan hóa",
                      "Tổng hợp nhận xét bằng AI",
                    ].map((step, i) => (
                      <div key={i} className="loading-step">
                        <div className="loading-step-dot" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                  <p className="loading-note">Quá trình phân tích thường mất khoảng 10–15 giây.</p>
                </div>
              )}

              {/* Thông báo lỗi */}
              {appState === "error" && errorMsg && (
                <div className="error-card">
                  <div>
                    <h3 className="error-title">Không thể hoàn tất phân tích</h3>
                    <p className="error-message">{errorMsg}</p>
                  </div>
                </div>
              )}
            </main>
          )}

          {/* TRƯỜNG HỢP 2: WORKSPACE STATE (Kết quả hiển thị ngay màn đầu) */}
          {hasResult && (
            <main className="workspace-content" ref={resultRef}>
              {/* Thanh công cụ kết quả */}
              <ResultToolbar
                chartCount={result.charts.length}
                timeRangeStr={timeRangeStr}
                onOpenExport={() => setIsExportOpen(true)}
              />

              {/* Nhận xét AI */}
              {result.insight && (
                <InsightCard insight={result.insight} goal={result.goal} meta={result.meta} />
              )}

              {/* Lưới biểu đồ 12 cột */}
              <ChartPanel charts={result.charts} />

              {/* Gợi ý hỏi tiếp */}
              <div className="followup-card">
                <div className="followup-header">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="9 14 4 9 9 4" />
                    <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
                  </svg>
                  Gợi ý hỏi tiếp trên tập dữ liệu này
                </div>
                <div className="followup-chips">
                  {[
                    "Chi nhánh nào có doanh thu cao nhất?",
                    "Chi nhánh nào tăng trưởng mạnh nhất?",
                    "Diễn biến doanh thu tổng theo tháng?",
                  ].map((q) => (
                    <button
                      key={q}
                      className="example-chip"
                      onClick={() => {
                        handleNewQuestion(q);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </main>
          )}

          {/* Footer */}
          <footer className="app-footer">
            AI Agent BI — Hệ thống trực quan hóa & Phân tích Dữ liệu Kinh doanh Thông minh
          </footer>
        </div>
      </div>

      {/* ── 4. MODAL XUẤT BÁO CÁO ── */}
      <ExportDialog
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        supplementaryCount={supplementaryCount}
        onExport={handleExport}
      />

      {/* ── 5. KHỐI IN VECTOR ẨN (#print-root) CHO BÁO CÁO A4 ── */}
      {reportModel && (() => {
        const printContainer = document.getElementById("print-root");
        if (printContainer) {
          return createPortal(<ReportDocument model={reportModel} />, printContainer);
        }
        return (
          <div id="print-root">
            <ReportDocument model={reportModel} />
          </div>
        );
      })()}
    </div>
  );
}
