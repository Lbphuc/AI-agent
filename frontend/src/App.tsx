import { useState, useCallback, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import type { FormEvent } from "react";
import {
  analyzeData,
  profileData,
  interpretQuestion,
  deepenAnalysis,
  renderChart,
  ArbitrationError,
} from "./api/client";
import type {
  AnalyzeResponse,
  ExportSections,
  DataProfile,
  AnalysisMode,
  AnalysisLevel,
  InterpretResponse,
  DeepenResponse,
  ChartType,
  ChartVerdict,
  ChartOption,
  ChartSpec,
} from "./api/types";
import FileUpload from "./components/FileUpload";
import ChartPanel from "./components/ChartPanel";
import InsightCard from "./components/InsightCard";
import { AppHeader } from "./components/AppHeader";
import { AppRail } from "./components/AppRail";
import { QueryBar } from "./components/QueryBar";
import { ResultToolbar } from "./components/ResultToolbar";
import { ModePicker } from "./components/ModePicker";
import { ChartTypePicker, CHART_NAMES } from "./components/ChartTypePicker";
import {
  ChartConfirmDialog,
  getSessionAcks,
  saveSessionAcks,
} from "./components/ChartConfirmDialog";
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
  const [selectedCharts, setSelectedCharts] = useState<ChartType[]>([]);
  const chartPref = selectedCharts[0] || null;
  const setChartPref = useCallback((ct: ChartType | null) => {
    setSelectedCharts(ct ? [ct] : []);
  }, []);
  const [ackCodes, setAckCodes] = useState<string[]>([]);
  const [expandViews, setExpandViews] = useState(true);

  // Hộp thoại xác nhận biểu đồ (ChartConfirmDialog)
  const [confirmVerdict, setConfirmVerdict] = useState<ChartVerdict | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [strategyToast, setStrategyToast] = useState<string | null>(null);
  const pendingActionRef = useRef<((effectiveAcks: string[]) => void) | null>(null);

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

  /**
   * Chạy các tác vụ phân tích nặng sau khi đã xác thực biểu đồ hợp lệ
   */
  const executeAnalysis = useCallback(
    async (
      interp: InterpretResponse,
      currentAcks: string[],
      currentRunId: number,
      abortController: AbortController,
      chartsToUse: ChartType[] = selectedCharts
    ) => {
      const { goal, levels } = interp;
      const tasks: Promise<void>[] = [];
      let hasSuccessfulTask = false;
      let openedConfirm = false;

      // 1. Phân tích mô tả (O1..O5)
      if (levels.includes("descriptive")) {
        tasks.push(
          (async () => {
            try {
              const descRes = await analyzeData(
                file!,
                question.trim(),
                expandViews,
                goal,
                chartsToUse.length > 0 ? chartsToUse : null,
                currentAcks,
                abortController.signal
              );
              if (runIdRef.current === currentRunId) {
                setDescriptiveResult(descRes);
                hasSuccessfulTask = true;
              }
            } catch (err) {
              if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                if (err instanceof ArbitrationError && err.verdict) {
                  openedConfirm = true;
                  setConfirmVerdict(err.verdict);
                  setIsConfirmOpen(true);
                  pendingActionRef.current = (effectiveAcks: string[]) => {
                    setAppState("loading");
                    handleSubmit(undefined, effectiveAcks, chartsToUse);
                  };
                  setAppState("idle");
                } else {
                  console.error("Descriptive analysis error:", err);
                  setErrorMsg(err instanceof Error ? err.message : "Đã xảy ra lỗi phân tích.");
                  setAppState("error");
                }
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
              const presRes = await deepenAnalysis(
                file!,
                goal,
                "prescriptive",
                mode === "prescriptive" && chartsToUse.length > 0 ? chartsToUse : null,
                currentAcks,
                abortController.signal
              );
              if (runIdRef.current === currentRunId) {
                setDeepenResults((prev) => ({ ...prev, prescriptive: presRes }));
                hasSuccessfulTask = true;
              }
            } catch (err) {
              if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                if (err instanceof ArbitrationError && err.verdict) {
                  openedConfirm = true;
                  setConfirmVerdict(err.verdict);
                  setIsConfirmOpen(true);
                  pendingActionRef.current = (effectiveAcks: string[]) => {
                    setAppState("loading");
                    handleSubmit(undefined, effectiveAcks, chartsToUse);
                  };
                  setAppState("idle");
                } else {
                  console.warn("Prescriptive deepen error/warning:", err);
                }
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
                const diagRes = await deepenAnalysis(
                  file!,
                  goal,
                  "diagnostic",
                  mode === "diagnostic" && chartsToUse.length > 0 ? chartsToUse : null,
                  currentAcks,
                  abortController.signal
                );
                if (runIdRef.current === currentRunId) {
                  setDeepenResults((prev) => ({ ...prev, diagnostic: diagRes }));
                  hasSuccessfulTask = true;
                }
              } catch (err) {
                if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                  if (err instanceof ArbitrationError && err.verdict) {
                    openedConfirm = true;
                    setConfirmVerdict(err.verdict);
                    setIsConfirmOpen(true);
                    pendingActionRef.current = (effectiveAcks: string[]) => {
                      setAppState("loading");
                      handleSubmit(undefined, effectiveAcks, chartsToUse);
                    };
                    setAppState("idle");
                  } else {
                    console.warn("Diagnostic deepen error/warning:", err);
                  }
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
                const fcRes = await deepenAnalysis(
                  file!,
                  goal,
                  "forecast",
                  mode === "forecast" && chartsToUse.length > 0 ? chartsToUse : null,
                  currentAcks,
                  abortController.signal
                );
                if (runIdRef.current === currentRunId) {
                  setDeepenResults((prev) => ({ ...prev, forecast: fcRes }));
                  hasSuccessfulTask = true;
                }
              } catch (err) {
                if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
                  if (err instanceof ArbitrationError && err.verdict) {
                    openedConfirm = true;
                    setConfirmVerdict(err.verdict);
                    setIsConfirmOpen(true);
                    pendingActionRef.current = (effectiveAcks: string[]) => {
                      setAppState("loading");
                      handleSubmit(undefined, effectiveAcks, chartsToUse);
                    };
                    setAppState("idle");
                  } else {
                    console.warn("Forecast deepen error/warning:", err);
                  }
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
        if (hasSuccessfulTask) {
          setAppState("result");
          setTimeout(() => {
            resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 80);
        } else if (!openedConfirm) {
          setErrorMsg((prev) => prev || "Không thể tải kết quả phân tích do lỗi máy chủ.");
          setAppState("error");
        }
      }
    },
    [file, question, expandViews, mode, selectedCharts]
  );

  // Thực hiện phân tích song song
  const handleSubmit = useCallback(
    async (
      e?: FormEvent,
      overrideAcks?: string[],
      overrideCharts?: ChartType[]
    ) => {
      e?.preventDefault();
      if (!canSubmit || !file) return;

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

      const activeCharts = overrideCharts ?? selectedCharts;
      const allAcks = Array.from(
        new Set([...(overrideAcks ?? ackCodes), ...getSessionAcks()])
      );

      try {
        const interp = await interpretQuestion(
          file,
          question.trim(),
          mode,
          activeCharts.length > 0 ? activeCharts : null,
          allAcks,
          abortController.signal
        );
        if (runIdRef.current !== currentRunId) return;

        setInterpretResponse(interp);

        if (interp.chart_check) {
          const verdict = interp.chart_check;
          const isBlocked = verdict.status === "blocked" || Boolean(verdict.requires_double_confirm);

          if (isBlocked) {
            const unforced = verdict.reasons
              .map((r) => r.code)
              .filter((c) => !allAcks.includes(`force:${c}`) && !allAcks.includes("force:all"));

            if (unforced.length > 0) {
              setConfirmVerdict(verdict);
              setIsConfirmOpen(true);
              pendingActionRef.current = (effectiveAcks: string[]) => {
                setAppState("loading");
                executeAnalysis(interp, effectiveAcks, currentRunId, abortController, activeCharts);
              };
              setAppState("idle");
              return;
            }
          } else if (verdict.status === "confirm") {
            const unacked = verdict.reasons
              .filter((r) => r.severity === "confirm")
              .map((r) => r.code)
              .filter((c) => !allAcks.includes(c));

            if (unacked.length > 0) {
              setConfirmVerdict(verdict);
              setIsConfirmOpen(true);
              pendingActionRef.current = (effectiveAcks: string[]) => {
                setAppState("loading");
                executeAnalysis(interp, effectiveAcks, currentRunId, abortController, activeCharts);
              };
              setAppState("idle");
              return;
            }
          }
        }

        await executeAnalysis(interp, allAcks, currentRunId, abortController, activeCharts);
      } catch (err) {
        if (runIdRef.current === currentRunId && !abortController.signal.aborted) {
          if (err instanceof ArbitrationError && err.verdict) {
            setConfirmVerdict(err.verdict);
            setIsConfirmOpen(true);
            pendingActionRef.current = (effectiveAcks: string[]) => {
              setAppState("loading");
              handleSubmit(undefined, effectiveAcks, activeCharts);
            };
            setAppState("idle");
          } else {
            setErrorMsg(err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.");
            setAppState("error");
          }
        }
      }
    },
    [canSubmit, file, question, mode, selectedCharts, ackCodes, executeAnalysis]
  );

  // Đổi pill sau khi đã có kết quả -> chạy bù cấp còn thiếu
  const handleModeChange = useCallback(
    async (newMode: AnalysisMode) => {
      setMode(newMode);

      if (chartPref && profile?.chart_catalog) {
        const levelKey = newMode === "auto" ? "descriptive" : newMode;
        const catalogItems = profile.chart_catalog[levelKey] || [];
        const prefItem = catalogItems.find((i) => i.chart_type === chartPref);
        if (prefItem?.fitness === "blocked" || prefItem?.verdict === "blocked") {
          const oldName = CHART_NAMES[chartPref] || chartPref;
          setChartPref(null);
          setStrategyToast(
            `Biểu đồ ${oldName} không áp dụng cho chế độ mới — đã chuyển về Tự động.`
          );
          setTimeout(() => setStrategyToast(null), 5000);
        }
      }

      if (appState !== "result" || !file || !interpretResponse?.goal) return;

      const goal = interpretResponse.goal;
      const targetLevels = MODE_TO_LEVELS[newMode] || [];
      const allAcks = Array.from(new Set([...ackCodes, ...getSessionAcks()]));

      for (const lvl of targetLevels) {
        if (lvl === "descriptive") continue;
        if (deepenResults[lvl]) continue;

        setDeepenLoading((prev) => ({ ...prev, [lvl]: true }));
        try {
          const res = await deepenAnalysis(file, goal, lvl, chartPref, allAcks);
          setDeepenResults((prev) => ({ ...prev, [lvl]: res }));
        } catch (err) {
          if (err instanceof ArbitrationError) {
            setConfirmVerdict(err.verdict || null);
            setIsConfirmOpen(true);
          } else {
            console.error(`Lỗi khi tải cấp ${lvl}:`, err);
          }
        } finally {
          setDeepenLoading((prev) => ({ ...prev, [lvl]: false }));
        }
      }
    },
    [appState, file, interpretResponse, deepenResults, chartPref, profile, ackCodes]
  );

  const handleReset = useCallback(() => {
    abortControllerRef.current?.abort();
    setAppState("idle");
    setDescriptiveResult(null);
    setDeepenResults({});
    setInterpretResponse(null);
    setErrorMsg(null);
    setIsFormExpanded(false);
    setChartPref(null);
    setAckCodes([]);
    setStrategyToast(null);
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

  const handleConfirmOverride = useCallback((newCodes: string[]) => {
    const updated = Array.from(new Set([...ackCodes, ...getSessionAcks(), ...newCodes]));
    setAckCodes(updated);
    saveSessionAcks(newCodes);
    setIsConfirmOpen(false);
    setConfirmVerdict(null);
    setAppState("loading");

    if (pendingActionRef.current) {
      const act = pendingActionRef.current;
      pendingActionRef.current = null;
      act(updated);
    } else {
      setTimeout(() => handleSubmit(undefined, updated), 50);
    }
  }, [ackCodes, handleSubmit]);

  const handleAcceptSuggestion = useCallback((altChart: ChartType) => {
    setSelectedCharts([altChart]);
    setIsConfirmOpen(false);
    setConfirmVerdict(null);
    pendingActionRef.current = null;
    setAppState("loading");
    setTimeout(() => handleSubmit(undefined, undefined, [altChart]), 50);
  }, [handleSubmit]);

  const handleConfirmCancel = useCallback(() => {
    setIsConfirmOpen(false);
    setConfirmVerdict(null);
    pendingActionRef.current = null;
  }, []);

  // Đổi loại biểu đồ trên từng thẻ (menu ⋯)
  const handleSwitchChart = useCallback(
    async (targetChart: ChartSpec, option: ChartOption) => {
      const allAcks = Array.from(new Set([...ackCodes, ...getSessionAcks()]));

      if (option.verdict === "blocked") {
        const unforced = option.reasons
          .map((r) => r.code)
          .filter((c) => !allAcks.includes(`force:${c}`));

        if (unforced.length > 0) {
          setConfirmVerdict({
            status: "blocked",
            chart_type: option.chart_type,
            reasons: option.reasons,
            alternatives: [],
            requires_double_confirm: true,
            confirm_step: 1,
          });
          setIsConfirmOpen(true);
          pendingActionRef.current = (effectiveAcks: string[]) => {
            applyChartSwitch(targetChart, option, effectiveAcks);
          };
          return;
        }
      } else if (option.verdict === "confirm") {
        const unacked = option.reasons
          .filter((r) => r.severity === "confirm")
          .map((r) => r.code)
          .filter((c) => !allAcks.includes(c));

        if (unacked.length > 0) {
          setConfirmVerdict({
            status: "confirm",
            chart_type: option.chart_type,
            reasons: option.reasons,
            alternatives: [],
            requires_double_confirm: false,
            confirm_step: 1,
          });
          setIsConfirmOpen(true);
          pendingActionRef.current = (effectiveAcks: string[]) => {
            applyChartSwitch(targetChart, option, effectiveAcks);
          };
          return;
        }
      }

      await applyChartSwitch(targetChart, option, allAcks);
    },
    [ackCodes, file, interpretResponse, mode]
  );

  const applyChartSwitch = async (
    targetChart: ChartSpec,
    option: ChartOption,
    currentAcks: string[]
  ) => {
    if (!file || !interpretResponse?.goal) return;

    if (option.requires_fetch) {
      try {
        const newSpec = await renderChart(
          file,
          interpretResponse.goal,
          (mode === "auto" ? "descriptive" : mode) as AnalysisLevel,
          option.chart_type,
          currentAcks
        );

        setDescriptiveResult((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            charts: prev.charts.map((c) => (c.title === targetChart.title ? newSpec : c)),
          };
        });
        setDeepenResults((prev) => {
          const next = { ...prev };
          for (const k of Object.keys(next) as AnalysisLevel[]) {
            const dr = next[k];
            if (dr?.sections) {
              next[k] = {
                ...dr,
                sections: dr.sections.map((sec) => ({
                  ...sec,
                  charts: sec.charts.map((c) => (c.title === targetChart.title ? newSpec : c)),
                })),
              };
            }
          }
          return next;
        });
      } catch (err) {
        if (err instanceof ArbitrationError) {
          setConfirmVerdict(err.verdict || null);
          setIsConfirmOpen(true);
        } else {
          alert(err instanceof Error ? err.message : "Không thể chuyển đổi biểu đồ.");
        }
      }
    } else {
      setDescriptiveResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          charts: prev.charts.map((c) =>
            c.title === targetChart.title ? { ...c, chart_type: option.chart_type } : c
          ),
        };
      });
      setDeepenResults((prev) => {
        const next = { ...prev };
        for (const k of Object.keys(next) as AnalysisLevel[]) {
          const dr = next[k];
          if (dr?.sections) {
            next[k] = {
              ...dr,
              sections: dr.sections.map((sec) => ({
                ...sec,
                charts: sec.charts.map((c) =>
                  c.title === targetChart.title ? { ...c, chart_type: option.chart_type } : c
                ),
              })),
            };
          }
        }
        return next;
      });
    }
  };

  const handleResetCardToAuto = useCallback(() => {
    setChartPref(null);
    handleSubmit();
  }, [handleSubmit]);

  // Xác định cấp độ phân tích trọng tâm (Primary Focus Level) theo câu hỏi
  const effectivePrimaryLevel: AnalysisLevel = useMemo(() => {
    if (mode !== "auto") return mode;
    const obj = interpretResponse?.goal?.objective;
    const lvls = interpretResponse?.goal?.levels || interpretResponse?.levels || [];
    if (obj === "contribution_to_change" || obj === "top_decliners" || lvls.includes("diagnostic")) {
      if (obj === "forecast") return "forecast";
      if (obj === "prescriptive_action") return "prescriptive";
      return "diagnostic";
    }
    if (obj === "forecast" || lvls.includes("forecast")) {
      return "forecast";
    }
    if (obj === "prescriptive_action" || lvls.includes("prescriptive")) {
      return "prescriptive";
    }
    return "descriptive";
  }, [mode, interpretResponse]);

  // Khử trùng lặp biểu đồ giữa phần chuyên sâu (Forecast/Diagnostic) và phần Mô tả (Descriptive)
  const visibleDescriptiveCharts: ChartSpec[] = useMemo(() => {
    const rawCharts = descriptiveResult?.charts || [];
    if (!rawCharts.length) return [];

    const hasForecastChart =
      !dismissedLevels.has("forecast") &&
      (deepenResults.forecast?.sections?.[0]?.charts?.length || 0) > 0;
    const hasDiagnosticChart =
      !dismissedLevels.has("diagnostic") &&
      (deepenResults.diagnostic?.sections?.[0]?.charts?.length || 0) > 0;

    return rawCharts.filter((c) => {
      // Nếu đã hiển thị biểu đồ Dự báo (gồm cả chuỗi lịch sử + tương lai) trên đỉnh,
      // ẩn biểu đồ đường Xu hướng đơn lẻ bị lặp lại ở phần mô tả
      if (
        hasForecastChart &&
        effectivePrimaryLevel === "forecast" &&
        c.role === "primary" &&
        (c.chart_type === "line" || c.chart_type === "area") &&
        Object.keys(c.series || {}).length === 1
      ) {
        return false;
      }
      // Nếu đã hiển thị biểu đồ Chẩn đoán Đóng góp ở trên, ẩn biểu đồ đóng góp phụ bị lặp
      if (hasDiagnosticChart && c.perspective === "contribution_to_change") {
        return false;
      }
      return true;
    });
  }, [descriptiveResult, deepenResults, dismissedLevels, effectivePrimaryLevel]);

  const supplementaryCount = useMemo(() => {
    return visibleDescriptiveCharts.filter((c) => c.role === "supplementary").length;
  }, [visibleDescriptiveCharts]);

  const totalChartCount = useMemo(() => {
    let count = visibleDescriptiveCharts.length;
    if (!dismissedLevels.has("diagnostic")) {
      count += deepenResults.diagnostic?.sections?.reduce((acc, s) => acc + (s.charts?.length || 0), 0) || 0;
    }
    if (!dismissedLevels.has("forecast")) {
      count += deepenResults.forecast?.sections?.reduce((acc, s) => acc + (s.charts?.length || 0), 0) || 0;
    }
    return count;
  }, [visibleDescriptiveCharts, deepenResults, dismissedLevels]);

  const timeRangeStr = useMemo(() => {
    const goal = descriptiveResult?.goal || interpretResponse?.goal;
    if (!goal) return null;
    const { time_start, time_end } = goal;
    if (time_start && time_end) return `${time_start} – ${time_end}`;
    return null;
  }, [descriptiveResult, interpretResponse]);

  const primaryMethodName = useMemo(() => {
    switch (effectivePrimaryLevel) {
      case "diagnostic":
        return "Tìm nguyên nhân (Chẩn đoán)";
      case "forecast":
        return "Dự báo xu hướng";
      case "prescriptive":
        return "Gợi ý chiến lược";
      default:
        return "Tổng quan mô tả";
    }
  }, [effectivePrimaryLevel]);

  const reportModel = useMemo(() => {
    if (!descriptiveResult) return null;
    return buildReportModel(
      descriptiveResult,
      file?.name || "data.csv",
      exportSections,
      reportOrgName,
      deepenResults
    );
  }, [descriptiveResult, file, exportSections, reportOrgName, deepenResults]);

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
      <AppHeader />

      <div className="app-main-layout">
        <AppRail activeId={activeRailId} onSelect={setActiveRailId} />

        <div className="app-content-wrapper">
          {hasResult && !isFormExpanded && (
            <QueryBar
              filename={file?.name || "data.csv"}
              question={question}
              onEdit={handleEditQuery}
              onReset={handleReset}
            />
          )}

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

                  <ModePicker
                    currentMode={mode}
                    onModeChange={handleModeChange}
                    availability={profile?.availability}
                    disabled={isLoading}
                  />

                  <div className="chart-picker-row">
                    <div className="chart-picker-label-group">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="20" x2="18" y2="10" />
                        <line x1="12" y1="20" x2="12" y2="4" />
                        <line x1="6" y1="20" x2="6" y2="14" />
                      </svg>
                      <span>Chọn biểu đồ trực quan hóa:</span>
                    </div>
                    <ChartTypePicker
                      values={selectedCharts}
                      onChangeMulti={setSelectedCharts}
                      catalog={profile?.chart_catalog}
                      strategy={mode}
                      disabled={isLoading}
                    />
                  </div>

                  {strategyToast && (
                    <div className="strategy-toast" role="status">
                      <span>ℹ</span>
                      <span>{strategyToast}</span>
                    </div>
                  )}

                  <textarea
                    id="question-input"
                    ref={questionRef}
                    className="question-textarea"
                    rows={3}
                    placeholder="Ví dụ: Vì sao doanh thu sụt giảm và dự báo xu hướng các quý tới?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={isLoading}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
                    }}
                  />
                  <div className="question-hint">Nhấn Ctrl + Enter để gửi câu hỏi</div>
                </div>

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

              {isLoading && (
                <div className="loading-card">
                  <div className="loading-steps">
                    {[
                      "Thẩm định cấu trúc và ma trận biểu đồ của dữ liệu",
                      "Hiểu ý định & xác thực tính tương thích của biểu đồ lựa chọn",
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

          {hasResult && (
            <main className="workspace-content" ref={resultRef}>
              <ResultToolbar
                chartCount={totalChartCount}
                timeRangeStr={timeRangeStr}
                primaryMethod={primaryMethodName}
                onOpenExport={() => setIsExportOpen(true)}
              />

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

              {/* KHU VỰC ƯU TIÊN: Cấp độ phân tích trọng tâm được hiển thị ngay bên trên */}
              {effectivePrimaryLevel === "diagnostic" && !dismissedLevels.has("diagnostic") && (
                <DeepenSection
                  level="diagnostic"
                  data={deepenResults.diagnostic}
                  loading={deepenLoading.diagnostic}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {effectivePrimaryLevel === "forecast" && !dismissedLevels.has("forecast") && (
                <DeepenSection
                  level="forecast"
                  data={deepenResults.forecast}
                  loading={deepenLoading.forecast}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {effectivePrimaryLevel === "prescriptive" && !dismissedLevels.has("prescriptive") && (
                <DeepenSection
                  level="prescriptive"
                  data={deepenResults.prescriptive}
                  loading={deepenLoading.prescriptive}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {/* Nhận xét AI cấp mô tả */}
              {descriptiveResult?.insight && (
                <InsightCard
                  insight={descriptiveResult.insight}
                  goal={descriptiveResult.goal}
                  meta={descriptiveResult.meta}
                  hideGoalSummary={Boolean(interpretResponse?.goal_summary)}
                />
              )}

              {/* Lưới biểu đồ chính và góc nhìn bổ sung (đã khử biểu đồ trùng lặp) */}
              {visibleDescriptiveCharts.length > 0 && (
                <ChartPanel
                  charts={visibleDescriptiveCharts}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {/* Các cấp phân tích phụ khác nếu chưa hiển thị ở trên */}
              {effectivePrimaryLevel !== "diagnostic" && deepenResults.diagnostic && !dismissedLevels.has("diagnostic") && (
                <DeepenSection
                  level="diagnostic"
                  data={deepenResults.diagnostic}
                  loading={deepenLoading.diagnostic}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {effectivePrimaryLevel !== "forecast" && deepenResults.forecast && !dismissedLevels.has("forecast") && (
                <DeepenSection
                  level="forecast"
                  data={deepenResults.forecast}
                  loading={deepenLoading.forecast}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

              {effectivePrimaryLevel !== "prescriptive" && deepenResults.prescriptive && !dismissedLevels.has("prescriptive") && (
                <DeepenSection
                  level="prescriptive"
                  data={deepenResults.prescriptive}
                  loading={deepenLoading.prescriptive}
                  onSwitchChart={handleSwitchChart}
                  onResetToAuto={handleResetCardToAuto}
                />
              )}

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

          <footer className="app-footer">
            AI Agent BI — Hệ thống trực quan hóa & Phân tích Dữ liệu Kinh doanh 4 Cấp độ Thông minh
          </footer>
        </div>
      </div>

      <ChartConfirmDialog
        isOpen={isConfirmOpen}
        verdict={confirmVerdict}
        strategyName={
          mode === "auto"
            ? "Tự động"
            : mode === "descriptive"
            ? "Tổng quan (Mô tả)"
            : mode === "diagnostic"
            ? "Tìm nguyên nhân (Chẩn đoán)"
            : mode === "forecast"
            ? "Dự đoán tương lai"
            : "Gợi ý chiến lược"
        }
        onConfirmOverride={handleConfirmOverride}
        onAcceptSuggestion={handleAcceptSuggestion}
        onCancel={handleConfirmCancel}
      />

      <ExportDialog
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        supplementaryCount={supplementaryCount}
        onExport={handleExport}
      />

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
