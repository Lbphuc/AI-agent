/**
 * Hàm định dạng số liệu tập trung theo quy chuẩn Việt Nam (vi-VN).
 * Tuân thủ tiêu chuẩn:
 * - Dấu chấm (.) phân cách phần nghìn.
 * - Dấu phẩy (,) phân cách phần thập phân.
 * - Không gọi toFixed trực tiếp ở bất kỳ component nào.
 */


export function formatNumber(
  value: number | null | undefined,
  options?: { decimals?: number; forceSign?: boolean }
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  const decimals = options?.decimals ?? (Number.isInteger(value) ? 0 : 1);
  const formatter = new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  const formatted = formatter.format(Math.abs(value));
  if (value < 0) {
    return `−${formatted}`;
  }
  if (options?.forceSign && value > 0) {
    return `+${formatted}`;
  }
  return formatted;
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 1,
  forceSign = false
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  const formattedNum = formatNumber(value, { decimals, forceSign });
  return `${formattedNum}%`;
}

/**
 * Định dạng nhãn trục X ngắn gọn cho chuỗi thời gian hoặc danh mục.
 * Ví dụ: "2026-01" -> "T1/26", "2026-08" -> "T8/26"
 */
export function formatAxisDate(label: string | number): string {
  if (typeof label !== "string") {
    return String(label);
  }

  const ymMatch = label.match(/^(\d{4})[-/](\d{1,2})$/);
  if (ymMatch) {
    const [, year, month] = ymMatch;
    const shortYear = year.slice(2);
    return `T${parseInt(month, 10)}/${shortYear}`;
  }

  const ymdMatch = label.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (ymdMatch) {
    const [, , month, day] = ymdMatch;
    return `${parseInt(day, 10)}/${parseInt(month, 10)}`;
  }

  return label;
}

/**
 * Định dạng giá trị thay đổi có kèm ký hiệu trực quan ▲ / ▼ và dấu + / −.
 * Giúp người khiếm thị màu (color blind) phân biệt tăng/giảm mà không chỉ dựa vào màu sắc.
 */
export function formatSignedChange(
  value: number,
  unit?: string
): { text: string; icon: "▲" | "▼" | "—"; isPositive: boolean; isNegative: boolean } {
  if (Math.abs(value) < 1e-9) {
    return {
      text: `0${unit ? ` ${unit}` : ""}`,
      icon: "—",
      isPositive: false,
      isNegative: false,
    };
  }

  const isPos = value > 0;
  const numStr = formatNumber(Math.abs(value));
  const sign = isPos ? "+" : "−";
  const icon = isPos ? "▲" : "▼";
  const unitSuffix = unit ? ` ${unit}` : "";

  return {
    text: `${icon} ${sign}${numStr}${unitSuffix}`,
    icon,
    isPositive: isPos,
    isNegative: !isPos,
  };
}
