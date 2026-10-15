import { useState, useCallback, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import type { FormEvent } from "react";
import { analyzeData, profileData, interpretQuestion, deepenAnalysis } from "./api/client";
import type {
  AnalyzeResponse,
  ExportSections,
  DataProfile,
  AnalysisMode,
  AnalysisLevel,
  InterpretResponse,
  DeepenResponse,
} from "./api/types";
import FileUpload from "./components/FileUpload";
import ChartPanel from "./components/ChartPanel";
import InsightCard from "./components/InsightCard";
import { AppHeader } from "./components/AppHeader";
import { AppRail } from "./components/AppRail";
import { QueryBar } from "./components/QueryBar";
import { ResultToolbar } from "./components/ResultToolbar";
import { ModePicker } from "./components/ModePicker";
import { DeepenSection } from "./components/DeepenSection";
import { ExportDialog, type ExportFormat } from "./export/ExportDialog";
import { ReportDocument } from "./export/ReportDocument";
import { buildReportModel } from "./export/buildReportModel";
import { triggerPrintReport } from "./export/printReport";
import { exportToExcel } from "./export/exportApi";
import "./App.css";

type AppState = "idle" | "loading" | "result" | "error";

const MODE_TO_LEVELS: Record<AnalysisMode, AnalysisLevel[]> = {
  auto: ["descriptive"],
  descriptive: ["descriptive"],
  diagnostic: ["descriptive", "diagnostic"],
  forecast: ["descriptive", "forecast"],
  prescriptive: ["descriptive", "diagnostic", "forecast", "prescriptive"],
};

export default function App() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [activeRailId, setActiveRailId] = useState("analyze");
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<DataProfile | null>(null);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AnalysisMode>("auto");
  const [expandViews, setExpandViews] = useState(true);

  // Kết quả phân tích
  const [interpretResponse, setInterpretResponse] = useState<InterpretResponse | null>(null);
  const [descriptiveResult, setDescriptiveResult] = useState<AnalyzeResponse | null>(null);
  const [deepenResults, setDeepenResults] = useState<Partial<Record<AnalysisLevel, DeepenResponse>>>({});
  const [deepenLoading, setDeepenLoading] = useState<Partial<Record<AnalysisLevel, boolean>>>({});
  const [dismissedLevels, setDismissedLevels] = useState<Set<AnalysisLevel>>(new Set());

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isFormExpanded, setIsFormExpanded] = useState(false);

  // Quản lý huỷ request và chống đua trạng thái (race condition)
  const runIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

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
  const hasResult = appState === "result" && (descriptiveResult !== null || Object.keys(deepenResults).length > 0);
  const canSubmit = !!file && question.trim().length > 0 && !isLoading;

  // Tự động thẩm định profile khi chọn file
  const handleFileSelect = useCallback(async (newFile: File) => {
    setFile(newFile);
    setProfile(null);
    try {
      const prof = await profileData(newFile);
      setProfile(prof);
    } catch (err) {
      console.warn("Không thể tải thông tin profile dữ liệu:", err);
    }
  }, []);

  // Câu hỏi gợi ý linh hoạt theo mode và profile
  const exampleQuestions = useMemo(() => {
    const metric = profile?.numeric_columns?.[0] || "Doanh thu";
    const group = profile?.group_columns?.[0] || "Chi nhánh";

    switch (mode) {
      case "diagnostic":
        return [
          `Vì sao ${metric.toLowerCase()} thay đổi theo ${group.toLowerCase()}?`,
          `Yếu tố nào đóng góp lớn nhất vào thay đổi ${metric.toLowerCase()}?`,
          `Phân tích nguyên nhân biến động ${metric.toLowerCase()} gần đây?`,
        ];
      case "forecast":
        return [
          `Dự báo ${metric.toLowerCase()} 3 kỳ tới?`,
          `Xu hướng ${metric.toLowerCase()} sắp tới ra sao?`,
          `Dự kiến ${metric.toLowerCase()} quý tiếp theo?`,
        ];
      case "prescriptive":
        return [
          `Nên ưu tiên ${group.toLowerCase()} nào để cải thiện ${metric.toLowerCase()}?`,
          `Đề xuất chiến lược tối ưu hóa ${metric.toLowerCase()}?`,
          `Cần hành động gì để thúc đẩy tăng trưởng ${metric.toLowerCase()}?`,
        ];
      default:
        return [
          `Xu hướng ${metric.toLowerCase()} theo tháng trong 12 tháng gần nhất?`,
          `So sánh ${metric.toLowerCase()} giữa các ${group.toLowerCase()} năm nay?`,
          `${group} nào có ${metric.toLowerCase()} cao nhất?`,
          `Tổng ${metric.toLowerCase()} theo quý?`,
        ];
    }
  }, [mode, profile]);

  // Thực hiện phân tích song song
  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      if (!canSubmit || !file) return;

      // Hủy request trước đó nếu còn đang chạy
      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      runIdRef.current += 1;
      const currentRunId = runIdRef.current;

      setAppState("loading");
      setErrorMsg(null);
      setIsFormExpanded(false);
      setDismissedLevels(new Set());
      setDescriptiveResult(null);
      setDeepenResults({});
      setDeepenLoading({});

      try {
        // Bước 1: Gọi /interpret để hiểu câu hỏi và suy ra các level cần chạy
        const interp = await interpretQuestion(file, question.trim(), mode, abortController.signal);
        if (runIdRef.current !== currentRunId) return;

        setInterpretResponse(interp);
        const { goal, levels } = interp;

        // Bước 2: Chạy song song các nhánh phân tích
        const tasks: Promise<void>[] = [];

        // 1. Phân tích mô tả (O1..O5)
        if (levels.includes("descriptive")) {
          tasks.push(
            (async () => {
              try {
                const descRes = await analyzeData(file, question.trim(), expandViews, goal, abortController.signal);
                if (runIdRef.current === currentRunId) {
                  setDescriptiveResult(descRes);
                }
              } catch (err) {
                if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                  console.error("Descriptive analysis error:", err);
                }
              }
            })()
          );
        }

        // 2. Phân tích đề xuất (prescriptive trả cả căn cứ)
        if (levels.includes("prescriptive")) {
          setDeepenLoading((prev) => ({ ...prev, prescriptive: true }));
          tasks.push(
            (async () => {
              try {
                const presRes = await deepenAnalysis(file, goal, "prescriptive", abortController.signal);
                if (runIdRef.current === currentRunId) {
                  setDeepenResults((prev) => ({ ...prev, prescriptive: presRes }));
                }
              } catch (err) {
                if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                  console.error("Prescriptive error:", err);
                }
              } finally {
                if (runIdRef.current === currentRunId) {
                  setDeepenLoading((prev) => ({ ...prev, prescriptive: false }));
                }
              }
            })()
          );
        } else {
          // Diagnostic
          if (levels.includes("diagnostic")) {
            setDeepenLoading((prev) => ({ ...prev, diagnostic: true }));
            tasks.push(
              (async () => {
                try {
                  const diagRes = await deepenAnalysis(file, goal, "diagnostic", abortController.signal);
                  if (runIdRef.current === currentRunId) {
                    setDeepenResults((prev) => ({ ...prev, diagnostic: diagRes }));
                  }
                } catch (err) {
                  if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                    console.error("Diagnostic error:", err);
                  }
                } finally {
                  if (runIdRef.current === currentRunId) {
                    setDeepenLoading((prev) => ({ ...prev, diagnostic: false }));
                  }
                }
              })()
            );
          }

          // Forecast
          if (levels.includes("forecast")) {
            setDeepenLoading((prev) => ({ ...prev, forecast: true }));
            tasks.push(
              (async () => {
                try {
                  const fcRes = await deepenAnalysis(file, goal, "forecast", abortController.signal);
                  if (runIdRef.current === currentRunId) {
                    setDeepenResults((prev) => ({ ...prev, forecast: fcRes }));
                  }
                } catch (err) {
                  if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                    console.error("Forecast error:", err);
                  }
                } finally {
                  if (runIdRef.current === currentRunId) {
                    setDeepenLoading((prev) => ({ ...prev, forecast: false }));
                  }
                }
              })()
            );
          }
        }

        await Promise.allSettled(tasks);

        if (runIdRef.current === currentRunId) {
          setAppState("result");
          setTimeout(() => {
            resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 80);
        }
      } catch (err) {
        if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
          setErrorMsg(err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.");
          setAppState("error");
        }
      }
    },
    [canSubmit, file, question, mode, expandViews]
  );

  // Đổi pill sau khi đã có kết quả -> chạy bù cấp còn thiếu
  const handleModeChange = useCallback(
    async (newMode: AnalysisMode) => {
      setMode(newMode);
      if (appState !== "result" || !file || !interpretResponse?.goal) return;

      const goal = interpretResponse.goal;
      const targetLevels = MODE_TO_LEVELS[newMode] || [];

      for (const lvl of targetLevels) {
        if (lvl === "descriptive") continue;
        if (deepenResults[lvl]) continue; // Đã có rồi, không cần gọi lại

        setDeepenLoading((prev) => ({ ...prev, [lvl]: true }));
        try {
          const res = await deepenAnalysis(file, goal, lvl);
          setDeepenResults((prev) => ({ ...prev, [lvl]: res }));
        } catch (err) {
          console.error(`Lỗi khi tải cấp ${lvl}:`, err);
        } finally {
          setDeepenLoading((prev) => ({ ...prev, [lvl]: false }));
        }
      }
    },
    [appState, file, interpretResponse, deepenResults]
  );

  const handleReset = useCallback(() => {
    abortControllerRef.current?.abort();
    setAppState("idle");
    setDescriptiveResult(null);
    setDeepenResults({});
    setInterpretResponse(null);
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
    if (!descriptiveResult?.charts) return 0;
    return descriptiveResult.charts.filter((c) => c.role === "supplementary").length;
  }, [descriptiveResult]);

  // Chuỗi khoảng thời gian
  const timeRangeStr = useMemo(() => {
    const goal = descriptiveResult?.goal || interpretResponse?.goal;
    if (!goal) return null;
    const { time_start, time_end } = goal;
    if (time_start && time_end) return `${time_start} – ${time_end}`;
    return null;
  }, [descriptiveResult, interpretResponse]);

  // Model dữ liệu báo cáo cho trang in ẩn (#print-root)
  const reportModel = useMemo(() => {
    if (!descriptiveResult) return null;
    return buildReportModel(
      descriptiveResult,
      file?.name || "data.csv",
      exportSections,
      reportOrgName
    );
  }, [descriptiveResult, file, exportSections, reportOrgName]);

  // Xử lý xuất báo cáo theo các định dạng
  const handleExport = useCallback(
    async (format: ExportFormat, sections: ExportSections, orgName: string) => {
      if (!descriptiveResult) return;
      setExportSections(sections);
      setReportOrgName(orgName);

      if (format === "pdf") {
        triggerPrintReport(file?.name || "data.csv");
      } else if (format === "excel") {
        await exportToExcel(descriptiveResult, file?.name || "data.csv", sections, orgName);
      } else if (format === "png") {
        const primaryCard = document.querySelector(".col-span-12 .chart-card") as HTMLElement;
        if (primaryCard && descriptiveResult.charts[0]) {
          const { exportChartToPng } = await import("./export/exportPng");
          await exportChartToPng(primaryCard, descriptiveResult.charts[0].title);
        } else {
          alert("Vui lòng bấm nút '⋯' trên góc từng biểu đồ để tải ảnh PNG riêng biệt.");
        }
      }
    },
    [descriptiveResult, file]
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
                    Hệ thống AI Phân tích Dữ liệu Kinh doanh 4 Cấp độ
                  </div>
                  <h2 className="hero-title">
                    Phân tích đa cấp độ bằng ngôn ngữ tự nhiên
                  </h2>
                  <p className="hero-subtitle">
                    Mô tả toàn cảnh • Chẩn đoán yếu tố đóng góp • Dự báo chuỗi thời gian • Đề xuất chiến lược có căn cứ
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
                  <FileUpload onFileSelect={handleFileSelect} selectedFile={file} disabled={isLoading} />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="question-input">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    Chế độ phân tích & Câu hỏi
                  </label>

                  {/* ModePicker (5 Pills) */}
                  <ModePicker
                    currentMode={mode}
                    onModeChange={handleModeChange}
                    availability={profile?.availability}
                    disabled={isLoading}
                  />

                  <textarea
                    id="question-input"
                    ref={questionRef}
                    className="question-textarea"
                    rows={3}
                    placeholder="Ví dụ: Vì sao doanh thu Đà Nẵng sụt giảm và dự báo xu hướng quý tới?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={isLoading}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
                    }}
                  />
                  <div className="question-hint">Nhấn Ctrl + Enter để gửi câu hỏi</div>
                </div>

                {/* Câu hỏi gợi ý theo mode */}
                <div className="example-questions">
                  <span className="example-label">Gợi ý:</span>
                  {exampleQuestions.map((q) => (
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
                      "Thẩm định cấu trúc và kiểm tra tính khả dụng của dữ liệu",
                      "Hiểu ý định người dùng & xác định cấp độ phân tích (O2)",
                      "Tính toán các số liệu thống kê tất định (Chẩn đoán / Dự báo / FactSheet)",
                      "Tạo các biểu đồ trực quan hóa chuyên sâu",
                      "Kiểm chứng dẫn chứng và tổng hợp nhận xét bằng AI",
                    ].map((step, i) => (
                      <div key={i} className="loading-step">
                        <div className="loading-step-dot" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                  <p className="loading-note">Quá trình phân tích chuyên sâu thường mất khoảng 5–10 giây.</p>
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
                chartCount={(descriptiveResult?.charts.length || 0) + (deepenResults.diagnostic?.sections[0]?.charts.length || 0)}
                timeRangeStr={timeRangeStr}
                onOpenExport={() => setIsExportOpen(true)}
              />

              {/* Hộp tóm tắt mục tiêu & Notices */}
              {interpretResponse?.goal_summary && (
                <div className="goal-summary-card">
                  <div className="goal-summary-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    Hệ thống hiểu yêu cầu của bạn là:
                  </div>
                  <p className="goal-summary-text">{interpretResponse.goal_summary}</p>
                  {interpretResponse.notices && interpretResponse.notices.length > 0 && (
                    <div className="notices-list">
                      {interpretResponse.notices.map((n, idx) => {
                        if (n.level && dismissedLevels.has(n.level)) return null;
                        return (
                          <div key={idx} className={`notice-item notice-${n.kind}`}>
                            <span>{n.message}</span>
                            {n.kind === "added" && n.level && (
                              <button
                                type="button"
                                className="notice-dismiss-btn"
                                onClick={() => setDismissedLevels((prev) => new Set([...prev, n.level!]))}
                              >
                                Bỏ phần này
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Nhận xét AI cấp mô tả */}
              {descriptiveResult?.insight && (
                <InsightCard
                  insight={descriptiveResult.insight}
                  goal={descriptiveResult.goal}
                  meta={descriptiveResult.meta}
                />
              )}

              {/* KHU VỰC ƯU TIÊN: Cấp độ đang chọn được hiển thị ngay bên trên */}
              {mode === "diagnostic" && !dismissedLevels.has("diagnostic") && (
                <DeepenSection
                  level="diagnostic"
                  data={deepenResults.diagnostic}
                  loading={deepenLoading.diagnostic}
                />
              )}

              {mode === "forecast" && !dismissedLevels.has("forecast") && (
                <DeepenSection
                  level="forecast"
                  data={deepenResults.forecast}
                  loading={deepenLoading.forecast}
                />
              )}

              {mode === "prescriptive" && !dismissedLevels.has("prescriptive") && (
                <DeepenSection
                  level="prescriptive"
                  data={deepenResults.prescriptive}
                  loading={deepenLoading.prescriptive}
                />
              )}

              {/* Lưới biểu đồ chính và góc nhìn bổ sung (Mô tả) */}
              {descriptiveResult?.charts && descriptiveResult.charts.length > 0 && (
                <ChartPanel charts={descriptiveResult.charts} />
              )}

              {/* Các cấp phân tích phụ khác nếu được bật hoặc tự động suy ra */}
              {mode !== "diagnostic" && deepenResults.diagnostic && !dismissedLevels.has("diagnostic") && (
                <DeepenSection
                  level="diagnostic"
                  data={deepenResults.diagnostic}
                  loading={deepenLoading.diagnostic}
                />
              )}

              {mode !== "forecast" && deepenResults.forecast && !dismissedLevels.has("forecast") && (
                <DeepenSection
                  level="forecast"
                  data={deepenResults.forecast}
                  loading={deepenLoading.forecast}
                />
              )}

              {mode !== "prescriptive" && deepenResults.prescriptive && !dismissedLevels.has("prescriptive") && (
                <DeepenSection
                  level="prescriptive"
                  data={deepenResults.prescriptive}
                  loading={deepenLoading.prescriptive}
                />
              )}

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
                  {exampleQuestions.map((q) => (
                    <button
                      key={q}
                      className="example-chip"
                      onClick={() => handleNewQuestion(q)}
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
            AI Agent BI — Hệ thống trực quan hóa & Phân tích Dữ liệu Kinh doanh 4 Cấp độ Thông minh
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
