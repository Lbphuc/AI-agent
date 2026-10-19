import type { ChartSpec, ChartOption } from "../api/types";
import { ChartCard } from "./ChartCard";
import "./ChartPanel.css";

interface Props {
  charts: ChartSpec[];
  onSwitchChart?: (chart: ChartSpec, option: ChartOption) => void;
  onResetToAuto?: (chart: ChartSpec) => void;
}

/**
 * Bảng ánh xạ perspective -> độ rộng cột (CSS Grid 12 cột).
 * - Biểu đồ chuỗi thời gian (trend_by_group, cumulative, moving_average) cần chiều ngang: 12 cột.
 * - Biểu đồ so sánh/tỷ trọng (share_of_total, contribution_to_change, period_change): 6 cột.
 * - Khi số thẻ nửa hàng là lẻ, thẻ cuối tự động chiếm 12 cột để tránh để trống 1 ô.
 */
function computeGridSpans(charts: ChartSpec[]): number[] {
  const baseSpans = charts.map((c) => {
    if (c.role === "primary") return 12;
    if (
      c.perspective === "trend_by_group" ||
      c.perspective === "cumulative" ||
      c.perspective === "moving_average"
    ) {
      return 12;
    }
    return 6;
  });

  // Kiểm tra số thẻ 6 cột liên tiếp
  const finalSpans = [...baseSpans];
  let halfWidthSequence: number[] = [];

  for (let i = 0; i < finalSpans.length; i++) {
    if (finalSpans[i] === 6) {
      halfWidthSequence.push(i);
    } else {
      // Kết thúc chuỗi thẻ 6 cột, nếu lẻ thì nâng thẻ cuối lên 12 cột
      if (halfWidthSequence.length % 2 === 1) {
        const lastIdx = halfWidthSequence[halfWidthSequence.length - 1];
        finalSpans[lastIdx] = 12;
      }
      halfWidthSequence = [];
    }
  }

  // Xử lý chuỗi 6 cột ở cuối danh sách
  if (halfWidthSequence.length % 2 === 1) {
    const lastIdx = halfWidthSequence[halfWidthSequence.length - 1];
    finalSpans[lastIdx] = 12;
  }

  return finalSpans;
}

export default function ChartPanel({ charts, onSwitchChart, onResetToAuto }: Props) {
  if (!charts || charts.length === 0) {
    return (
      <div className="chart-panel-empty">
        <p>Không có dữ liệu biểu đồ để hiển thị.</p>
      </div>
    );
  }

  const spans = computeGridSpans(charts);

  return (
    <div className="charts-grid-12">
      {charts.map((chart, idx) => (
        <div
          key={idx}
          className={`chart-grid-col col-span-${spans[idx]}`}
          style={{ gridColumn: `span ${spans[idx]}` }}
        >
          <ChartCard
            chart={chart}
            onSwitchChart={onSwitchChart}
            onResetToAuto={onResetToAuto}
          />
        </div>
      ))}
    </div>
  );
}
