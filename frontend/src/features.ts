/**
 * features.ts — Cấu hình tính năng mở rộng theo đề xuất A3.
 * Thêm tính năng mới = thêm 1 dòng, không sửa đổi bố cục giao diện.
 */

export type FeatureStatus = "active" | "soon" | "hidden";

export type IconName =
  | "sparkles"
  | "clock"
  | "bookmark"
  | "gear"
  | "download"
  | "thumbs"
  | "link";

export interface RailItem {
  id: string;
  label: string;
  icon: IconName;
  status: FeatureStatus;
}

export const RAIL_ITEMS: RailItem[] = [
  { id: "analyze",  label: "Phân tích", icon: "sparkles", status: "active" },
  { id: "history",  label: "Lịch sử",   icon: "clock",    status: "soon" },
  { id: "saved",    label: "Đã lưu",    icon: "bookmark", status: "soon" },
  { id: "settings", label: "Cài đặt",   icon: "gear",     status: "soon" },
];

export interface ToolbarAction {
  id: string;
  label: string;
  icon: IconName;
  status: FeatureStatus;
}

export const RESULT_ACTIONS: ToolbarAction[] = [
  { id: "export",   label: "Xuất báo cáo", icon: "download", status: "active" },
  { id: "feedback", label: "Phản hồi",     icon: "thumbs",   status: "soon" },
  { id: "share",    label: "Chia sẻ",      icon: "link",     status: "soon" },
];
