import { toPng } from "html-to-image";

/**
 * Xuất một thẻ biểu đồ (ChartCard DOM element) sang ảnh PNG chất lượng cao (pixelRatio: 2).
 * Chụp toàn bộ thẻ gồm tiêu đề, biểu đồ, chú giải (Legend HTML) và chú thích.
 */
export async function exportChartToPng(
  element: HTMLElement,
  title: string
): Promise<void> {
  try {
    const dataUrl = await toPng(element, {
      pixelRatio: 2,
      backgroundColor: "#141B2D", // Nền thẻ chuẩn Dark Mode
      cacheBust: true,
      filter: (node) => {
        // Bỏ qua các nút thao tác menu trong thẻ khi xuất ảnh
        if (node instanceof HTMLElement && node.classList.contains("no-export")) {
          return false;
        }
        return true;
      },
    });

    const safeTitle = title
      .toLowerCase()
      .replace(/[^a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/g, "_")
      .slice(0, 40);

    const filename = `BieuDo_${safeTitle}_${Date.now()}.png`;

    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    console.error("Lỗi xuất ảnh PNG:", err);
    throw new Error("Không thể tạo ảnh PNG từ biểu đồ này.");
  }
}
