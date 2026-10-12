import type { AnalyzeResponse, ExportSections } from "../api/types";
import type { ReportModel, ReportChartItem } from "./types";

export function buildReportModel(
  response: AnalyzeResponse,
  filename: string,
  sections: ExportSections,
  orgName?: string
): ReportModel {
  const meta = response.meta;
  const goal = response.goal;
  const firstTask = goal?.tasks?.[0];

  const generatedAt = meta?.generated_at
    ? new Date(meta.generated_at).toLocaleString("vi-VN")
    : new Date().toLocaleString("vi-VN");

  const modelName = meta?.model_name || "AI Agent BI";
  const rowsInfo = meta
    ? `${meta.rows_used} dòng đã phân tích (trong tổng số ${meta.rows_total} dòng)`
    : "Đã phân tích toàn bộ tập dữ liệu";

  const goalSummary = meta?.goal_summary || goal?.question || "";
  const confidence = response.insight?.confidence_score ?? null;
  const isLowConfidence = confidence !== null && confidence < 0.8;

  // Xây dựng danh sách biểu đồ kèm bảng dữ liệu
  const chartItems: ReportChartItem[] = [];

  for (const chart of response.charts || []) {
    const isPrimary = (chart.role || "primary") === "primary";
    if (isPrimary && sections.primary_chart === false) {
      continue;
    }
    if (!isPrimary && sections.supplementary_charts === false) {
      continue;
    }

    const seriesKeys = Object.keys(chart.series || {});
    const xLabel = isPrimary && firstTask?.group_by
      ? firstTask.group_by
      : chart.perspective === "share_of_total"
      ? "Nhóm"
      : chart.perspective === "trend_by_group"
      ? "Thời gian"
      : "Chỉ mục";

    const headers = [xLabel, ...seriesKeys.map((k) => chart.display_name && seriesKeys.length === 1 ? chart.display_name : k)];

    const rows: (string | number)[][] = [];
    const nRows = chart.x?.length || 0;
    for (let r = 0; r < nRows; r++) {
      const rowVal: (string | number)[] = [chart.x[r]];
      for (const k of seriesKeys) {
        const val = chart.series[k]?.[r];
        rowVal.push(val !== undefined ? val : "—");
      }
      rows.push(rowVal);
    }

    let calculationNote = "";
    if (chart.perspective === "share_of_total") {
      calculationNote = "Tỷ trọng (%) = (Giá trị từng nhóm / Tổng các nhóm) × 100.";
    } else if (chart.perspective === "period_change") {
      calculationNote = "% Thay đổi = ((Giá trị kỳ này − Giá trị kỳ trước) / Giá trị kỳ trước) × 100.";
    } else if (chart.perspective === "contribution_to_change") {
      calculationNote = "Đóng góp tuyệt đối = Giá trị kỳ cuối − Giá trị kỳ đầu.";
    } else if (chart.perspective === "cumulative") {
      calculationNote = "Tổng lũy kế cộng dồn qua từng mốc thời gian.";
    } else if (chart.perspective === "moving_average") {
      calculationNote = "Đường MA3 tính bằng trung bình cộng 3 kỳ gần nhất để làm mượt dao động.";
    }

    chartItems.push({
      spec: chart,
      headers,
      rows,
      calculationNote,
    });
  }

  // Phụ lục B: Cách tính & Lưu ý
  const metricName = firstTask?.metric || "Không xác định";
  const groupName = firstTask?.group_by || "Không xác định";

  const calculationNotes = [
    { label: "Mục tiêu phân tích", desc: goal?.question || "" },
    {
      label: "Thời gian áp dụng",
      desc: goal?.time_start && goal?.time_end
        ? `${goal.time_start} đến ${goal.time_end}`
        : "Toàn bộ chuỗi thời gian",
    },
    { label: "Chỉ số đo lường", desc: metricName },
    { label: "Nhóm phân loại", desc: groupName },
    { label: "Công thức tỷ trọng", desc: "Tỷ trọng (%) = (Giá trị nhóm / Tổng) × 100" },
    { label: "Công thức biến động", desc: "% Thay đổi = ((Kỳ này − Kỳ trước) / Kỳ trước) × 100" },
    { label: "Công thức đóng góp", desc: "Đóng góp tuyệt đối = Kỳ cuối − Kỳ đầu" },
    { label: "Trung bình trượt", desc: "MA3 = Trung bình 3 kỳ liên tiếp (kỳ hiện tại và 2 kỳ trước)" },
  ];

  if (meta?.notes && meta.notes.length > 0) {
    meta.notes.forEach((note, i) => {
      calculationNotes.push({
        label: `Lưu ý bổ sung #${i + 1}`,
        desc: note,
      });
    });
  }

  return {
    title: "BÁO CÁO PHÂN TÍCH DỮ LIỆU KINH DOANH",
    orgName: orgName?.trim() || undefined,
    filename,
    question: goal?.question || "",
    goalSummary,
    generatedAt,
    modelName,
    rowsInfo,
    insightText: sections.insight !== false ? response.insight?.insight_text : undefined,
    confidenceScore: confidence,
    isLowConfidence,
    charts: chartItems,
    calculationNotes: sections.calculation_notes !== false ? calculationNotes : [],
    sections,
  };
}
