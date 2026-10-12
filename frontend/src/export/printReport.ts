/**
 * Điều khiển in báo cáo PDF qua hộp thoại print của trình duyệt (Hướng 2).
 * Đổi tên document.title để trình duyệt tự động đặt tên file PDF khi lưu,
 * sau đó khôi phục lại sau sự kiện afterprint.
 */
export function triggerPrintReport(filename: string): void {
  const originalTitle = document.title;
  const cleanName = filename.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9_\-]/g, "_");
  const dateStr = new Date().toISOString().slice(0, 10);
  const pdfTitle = `BaoCao_${cleanName}_${dateStr}`;

  document.title = pdfTitle;

  const handleAfterPrint = () => {
    document.title = originalTitle;
    window.removeEventListener("afterprint", handleAfterPrint);
  };

  window.addEventListener("afterprint", handleAfterPrint);

  // Đợi 100ms để SVG / DOM hoàn thành render
  setTimeout(() => {
    window.print();
    // Fallback nếu trình duyệt không bắn afterprint
    setTimeout(() => {
      document.title = originalTitle;
    }, 2000);
  }, 150);
}
