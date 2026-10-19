import React, { useState, useEffect, useRef } from "react";
import type { ChartType, ChartVerdict } from "../api/types";
import { CHART_NAMES } from "./ChartTypePicker";
import "./ChartConfirmDialog.css";

interface ChartConfirmDialogProps {
  isOpen: boolean;
  verdict: ChartVerdict | null;
  strategyName?: string;
  onConfirmOverride: (ackCodes: string[]) => void;
  onAcceptSuggestion: (altChart: ChartType) => void;
  onCancel: () => void;
}

const STORAGE_KEY = "ai_agent_bi_chart_acks";

export function getSessionAcks(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveSessionAcks(codes: string[]): void {
  try {
    const existing = new Set(getSessionAcks());
    codes.forEach((c) => existing.add(c));
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(existing)));
  } catch {
    // ignore sessionStorage errors
  }
}

export const ChartConfirmDialog: React.FC<ChartConfirmDialogProps> = ({
  isOpen,
  verdict,
  strategyName = "Chiến lược hiện tại",
  onConfirmOverride,
  onAcceptSuggestion,
  onCancel,
}) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [dontAskAgain, setDontAskAgain] = useState(false);
  const safeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setDontAskAgain(false);
      setTimeout(() => {
        safeButtonRef.current?.focus();
      }, 50);
    }
  }, [isOpen, verdict]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onCancel();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen || !verdict) return null;

  const isBlocked = verdict.status === "blocked" || Boolean(verdict.requires_double_confirm);
  const chosenChartName = CHART_NAMES[verdict.chart_type] || verdict.chart_type;

  const allCodes = verdict.reasons.map((r) => r.code);
  const confirmCodes = verdict.reasons
    .filter((r) => r.severity === "confirm")
    .map((r) => r.code);

  const bestAlt = verdict.alternatives?.[0] || null;
  const bestAltName = bestAlt ? CHART_NAMES[bestAlt] || bestAlt : null;

  // Xử lý xác nhận cho biểu đồ ít phù hợp (xác nhận 1 lần)
  const handleSingleConfirm = () => {
    if (dontAskAgain && confirmCodes.length > 0) {
      saveSessionAcks(confirmCodes);
    }
    onConfirmOverride(allCodes);
  };

  // Bước 1 cho biểu đồ "không áp dụng" -> chuyển sang bước 2
  const handleProceedToStep2 = () => {
    setStep(2);
  };

  // Bước 2 cho biểu đồ "không áp dụng" -> xác nhận lần 2 và sinh cả mã force:
  const handleDoubleConfirm = () => {
    const forceCodes = allCodes.map((c) => `force:${c}`);
    const finalCodes = Array.from(new Set([...allCodes, ...forceCodes, "force:all"]));
    if (dontAskAgain && finalCodes.length > 0) {
      saveSessionAcks(finalCodes);
    }
    onConfirmOverride(finalCodes);
  };

  return (
    <div
      className="chart-confirm-overlay"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
      aria-describedby="dialog-desc"
    >
      <div className="chart-confirm-modal">
        {/* Header */}
        <div className={`chart-confirm-header ${isBlocked ? "blocked" : "confirm"}`}>
          <span style={{ fontSize: "20px" }}>{isBlocked ? (step === 2 ? "🚨" : "⛔") : "⚠️"}</span>
          <div style={{ flex: 1 }}>
            <h3 id="dialog-title" className="chart-confirm-title">
              {isBlocked
                ? step === 1
                  ? "Xác nhận lần 1: Biểu đồ không áp dụng cho ngữ cảnh này"
                  : "Xác nhận lần 2: Cảnh báo nghiêm ngặt & Xác nhận rủi ro"
                : "Biểu đồ này có thể chưa phù hợp"}
            </h3>
          </div>
          {isBlocked && (
            <span className="chart-step-badge">
              Bước {step}/2
            </span>
          )}
        </div>

        {/* Body */}
        <div id="dialog-desc" className="chart-confirm-body">
          <div className="chart-confirm-subtitle">
            Bạn chọn: <strong>{chosenChartName}</strong> &nbsp;·&nbsp; Mục tiêu:{" "}
            <strong>{strategyName}</strong>
          </div>

          {isBlocked && step === 2 ? (
            <div className="warning-box-step2">
              <p style={{ margin: "0 0 8px 0", fontWeight: 600 }}>
                ⚠️ Lưu ý quan trọng trước khi ép vẽ biểu đồ:
              </p>
              <p style={{ margin: "0 0 6px 0" }}>
                Biểu đồ <strong>{chosenChartName}</strong> không tương thích tự nhiên với cấu trúc dữ liệu hoặc chiến lược <strong>{strategyName}</strong>.
              </p>
              <p style={{ margin: 0, opacity: 0.9 }}>
                Hệ thống sẽ cố gắng thích ứng dữ liệu để hiển thị, nhưng biểu đồ có thể <em>bị sai lệch ngữ nghĩa trực quan</em>, che khuất hoặc thể hiện không trọn vẹn bản chất dữ liệu (ví dụ: lấy giá trị tuyệt đối cho số âm, hoặc gộp nhóm tự động).
              </p>
            </div>
          ) : (
            <>
              <ul className={`chart-confirm-reasons ${isBlocked ? "blocked" : ""}`}>
                {verdict.reasons.map((r, idx) => (
                  <li key={idx}>{r.message}</li>
                ))}
              </ul>

              {bestAlt && (
                <div className="chart-confirm-suggestion">
                  💡 <strong>Gợi ý thay thế:</strong> {bestAltName} sẽ trực quan và chính xác hơn cho mục tiêu này.
                </div>
              )}
            </>
          )}

          {(!isBlocked || step === 2) && (
            <label className="chart-confirm-suppress">
              <input
                type="checkbox"
                checked={dontAskAgain}
                onChange={(e) => setDontAskAgain(e.target.checked)}
              />
              <span>Ghi nhớ lựa chọn này cho các lần phân tích tiếp theo trong phiên</span>
            </label>
          )}
        </div>

        {/* Footer */}
        <div className="chart-confirm-footer">
          {isBlocked ? (
            step === 1 ? (
              <>
                <button
                  type="button"
                  className="btn-modal btn-modal-cancel"
                  onClick={onCancel}
                >
                  Hủy
                </button>
                {bestAlt && (
                  <button
                    type="button"
                    ref={safeButtonRef}
                    className="btn-modal btn-modal-safe"
                    onClick={() => onAcceptSuggestion(bestAlt)}
                  >
                    Đổi sang {bestAltName}
                  </button>
                )}
                <button
                  type="button"
                  className="btn-modal btn-modal-override"
                  onClick={handleProceedToStep2}
                >
                  Tiếp tục xác nhận (Bước 1/2) ➔ Xem cảnh báo
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="btn-modal btn-modal-cancel"
                  onClick={() => setStep(1)}
                >
                  Quay lại bước 1
                </button>
                <button
                  type="button"
                  className="btn-modal btn-modal-warning"
                  onClick={handleDoubleConfirm}
                >
                  Xác nhận (Bước 2/2) & Tiến hành phân tích ngay
                </button>
              </>
            )
          ) : (
            <>
              <button
                type="button"
                className="btn-modal btn-modal-cancel"
                onClick={onCancel}
              >
                Hủy
              </button>

              <button
                type="button"
                className="btn-modal btn-modal-override"
                onClick={handleSingleConfirm}
              >
                Vẫn dùng {chosenChartName} & Phân tích ngay
              </button>

              {bestAlt ? (
                <button
                  type="button"
                  ref={safeButtonRef}
                  className="btn-modal btn-modal-safe"
                  onClick={() => onAcceptSuggestion(bestAlt)}
                >
                  Dùng {bestAltName}
                </button>
              ) : (
                <button
                  type="button"
                  ref={safeButtonRef}
                  className="btn-modal btn-modal-safe"
                  onClick={onCancel}
                >
                  Đổi về Tự động
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
