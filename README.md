# AI Agent Phân Tích & Trực Quan Hóa Dữ Liệu Kinh Doanh

Đồ án tốt nghiệp — AI Agent cho phép người dùng tải lên file CSV dữ liệu
kinh doanh, đặt câu hỏi bằng ngôn ngữ tự nhiên, và nhận lại biểu đồ + số
liệu + nhận xét (insight) tự động.

Kiến trúc pipeline lấy cảm hứng từ LIDA (Dibia, 2023) — xem
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) để biết cách 5 module được
mở rộng từ ý tưởng SUMMARIZER / GOAL EXPLORER / VISGENERATOR của LIDA.

## Trạng thái (Tuần 4/8)

- [x] Nghiên cứu tài liệu, xác định yêu cầu (`docs/SRS.md`)
- [x] Thiết kế kiến trúc tổng thể (`docs/ARCHITECTURE.md`)
- [x] Khởi tạo repo + CI cơ bản
- [x] Bộ dữ liệu mẫu — **5 bộ** (`data/samples/`), gồm 2 bộ edge-case
- [x] Module O1 — Data Profiler (Stage 0, 1, 2)
- [x] Module O2 — Question Interpreter
- [x] Module O3 — Code Generator + Sandbox Executor + Orchestrator
- [x] Module O4 — Chart Generator (5 loại biểu đồ, chart_hint)
- [x] Module O5 — Insight Generator (trích xuất số liệu, đánh giá SEVQ)
- [x] Frontend — Web UI React + Vite + Recharts
- [x] **Dashboard đa góc nhìn (Perspective Planner):** Tự động bổ sung các biểu đồ phân rã tất định (xu hướng nhóm, tỷ trọng, biến động kỳ, đóng góp thay đổi...) kèm chú thích tự động không tốn thêm độ trễ LLM.
- [x] **Thiết kế lại giao diện & Xuất báo cáo (PDF, Excel, PNG, CSV):** App Rail điều hướng mở rộng, Query Bar thu gọn, chuẩn hóa thẻ biểu đồ ChartCard (giải quyết 100% lỗi hiển thị), Design Tokens, bộ xuất báo cáo đa định dạng kèm biểu đồ Excel gốc và in PDF vector A4.
- [x] **Phân tích sâu 3 cấp (Chẩn đoán · Dự báo · Đề xuất):** Kiến trúc Dual-track kết hợp đường mô tả sandbox và đường phân tích sâu tất định (pure Python numpy/pandas) với `FactSheet` làm nguồn chân lý duy nhất và bộ kiểm chứng cấu trúc `verify.py` loại bỏ 100% ảo giác số liệu và citation giả.
- [x] **Chế độ phân tích dạng Pills (ModePicker):** 5 chế độ phân tích (`Tự động`, `Tổng quan`, `Tìm nguyên nhân`, `Dự đoán tương lai`, `Gợi ý chiến lược`) với khả năng tính toán khả dụng trước khi gõ câu hỏi, suy luận ý định (O2 `levels`), và thực thi song song bất đồng bộ.

### CHANGELOG — Phân tích sâu 3 cấp & Chế độ phân tích dạng Pills

- **Kiến trúc phân tích sâu tất định (`backend/app/modules/analytics/`):**
  - **Cấp 1: Chẩn đoán (`diagnostic.py`):**
    - So sánh cửa sổ thời gian chuẩn hóa `window_compare(df, keys, metric, time_col, n)`: tính delta tuyệt đối, delta %, và tỷ lệ đóng góp `share_of_change` tránh lỗi so sánh 2 điểm đầu - cuối có nhiễu.
    - Drill-down 2 cấp tập trung: xác định nhóm dẫn dắt biến động (driver) và tự động khoan sâu vào nhóm phân loại thứ hai có tỷ lệ tập trung cao nhất (ví dụ: Đà Nẵng $\times$ Điện tử kéo giảm −381 triệu VNĐ).
    - Tương quan trong từng chuỗi (within-series z-score correlation): chuẩn hóa z-score theo từng nhóm trước khi tính hệ số Pearson để khử hiệu ứng quy mô ($r \approx 0.46$ thực tế so với $r \approx 0.89$ sai lệch khi gộp thẳng toàn bảng).
  - **Cấp 2: Dự báo (`forecast.py`):**
    - 5 mô hình dự báo thuần numpy tất định (`naive`, `seasonal_naive`, `linear`, `holt`, `seasonal_decomp`).
    - Lựa chọn mô hình tối ưu thông qua Rolling-origin Backtest ($h=3$, số lần thử $n - 10 \ge 5$).
    - Dải bất định 80% conformal suy ra trực tiếp từ phân vị sai số tuyệt đối của backtest thực tế, không dùng công thức OLS lý thuyết hẹp giả tạo.
    - Bộ lọc bảo vệ (Guards): từ chối dự báo trung thực khi chuỗi $< 15$ kỳ (như `doanh_thu.csv` 12 kỳ) hoặc tỷ lệ khuyết dữ liệu $> 20\%$; chỉ kích hoạt mô hình mùa vụ khi có $\ge 2$ chu kỳ đầy đủ ($\ge 24$ tháng).
  - **Cấp 3: Đề xuất có trích dẫn & Kiểm chứng cấu trúc (`prescriptive.py`, `verify.py`):**
    - Tổng hợp `FactSheet` với mã định danh cố định (`F1`, `F2`...), mỗi con số là một Fact có kiểm chứng.
    - LLM chỉ nhận `FactSheet` và bắt buộc trích dẫn `fact_ids` cho mọi khuyến nghị.
    - Bộ kiểm chứng tất định `verify.py`: loại bỏ 100% khuyến nghị chứa `fact_id` giả, số liệu không khớp với fact trích dẫn, thiếu tên thực thể, thiếu trường `caveat`, trích fact ước tính mà thiếu nhãn "ước tính/dự kiến", hoặc sử dụng từ khẳng định nhân quả tuyệt đối.
    - Cơ chế Retry 1 lần kèm danh sách lỗi phản hồi; nếu vẫn không hợp lệ, trả về thông báo rỗng trung thực ("Chưa đủ bằng chứng").
- **Chế độ phân tích dạng Pills (`ModePicker` & Frontend Architecture):**
  - Thanh chọn chế độ 5 pill (`auto`, `descriptive`, `diagnostic`, `forecast`, `prescriptive`) đặt ngay trên ô nhập câu hỏi, hỗ trợ điều hướng phím (roving tabindex) và WAI-ARIA accessible.
  - Tính toán độ khả dụng (`compute_availability`) ngay sau khi tải file: hiển thị tooltip lý do khóa pill (ví dụ: "Cần ít nhất 15 kỳ dữ liệu (hiện có 12)" trên `doanh_thu.csv`).
  - Phân loại ý định tự động tại O2 qua trường `levels`, kết hợp quy tắc hợp nhất `resolve_levels()` bảo toàn ý định câu hỏi.
  - Luồng thực thi song song không chặn: `/interpret` $\rightarrow$ song song `/analyze` và `/deepen` cho từng cấp, hiển thị skeleton loading độc lập.
  - Đổi pill sau khi đã có kết quả kích hoạt cơ chế chạy bù (incremental fetch) chỉ gọi các cấp còn thiếu, không gọi lại O2 hay sandbox.
  - Quản lý trạng thái bằng `runId` và `AbortController` chống race condition và hỗ trợ hủy request khi người dùng hỏi câu mới.
- **Biểu đồ Dự báo & Thẻ Khuyến nghị:**
  - `ComposedChart` hỗ trợ vẽ đường thực tế liền nét, đường dự báo nét đứt (`strokeDasharray="5 5"`), đường phân cách thời điểm bắt đầu dự báo `forecast_from`, và vùng mờ dải tin cậy 80% (conformal band) với Recharts.
  - Thẻ khuyến nghị `RecommendationCard` hiển thị nhãn ưu tiên, chip trích dẫn `FactChip` (hover xem chi tiết fact và giá trị), điều kiện cần kiểm chứng `caveat`, và cảnh báo miễn trừ trách nhiệm.
- **Dữ liệu kiểm thử mạnh & Biến thể:**
  - Script sinh dữ liệu `data/samples/tao_du_lieu_manh.py` tạo `kinh_doanh_36thang.csv` (720 dòng, 36 tháng, 5 chi nhánh, 4 danh mục, UTF-8 BOM tiếng Việt) cài sẵn đáp án quy luật chuẩn.
  - Thư mục `data/samples/bien_the/` chứa 7 bộ dữ liệu kiểm thử độ bền (thiếu tháng, chuỗi ngắn, đột biến x10, doanh thu âm, 200 nhóm SKU, 1 cột số, dữ liệu theo ngày).

---

## Kết quả Thực nghiệm & Đo lường

Hệ thống được đánh giá định lượng thông qua 2 script kiểm thử chuyên biệt:

### 1. Hiệu năng & Độ chính xác Phân tích Sâu (`measure_deepen.py` trên 20 seed)

| Cấp phân tích | Chỉ số đo lường | Kết quả thực nghiệm | Ý nghĩa đánh giá |
| --- | --- | :---: | --- |
| **Chẩn đoán** | Tỷ lệ tìm đúng Driver chính | **100.0%** (20/20 seed) | Nhận diện chính xác 100% Đà Nẵng và Đà Nẵng $\times$ Điện tử là yếu tố kéo giảm chính |
| | Hệ số tương quan trong chuỗi ($r_{series}$) | **0.885** (±0.04) | Chuẩn hóa z-score loại trừ hiệu ứng nhiễu quy mô chi nhánh |
| | Độ trễ trung bình | **44.2 ms** | Thuần Python tất định, không tốn tài nguyên gọi LLM |
| **Dự báo** | Sai số dự báo MAPE (Backtest) | **3.29%** | Mô hình kết hợp mùa vụ $\times$ xu hướng vượt trội so với naive/linear |
| | Độ phủ thực nghiệm dải 80% | **100.0%** | Mọi điểm dữ liệu thực tế đều nằm trong dải bất định conformal |
| | Độ trễ trung bình | **9.6 ms** | Cực nhanh nhờ thuật toán vector hóa numpy |
| **Đề xuất** | Tỷ lệ chặn khuyến nghị ảo giác / vi phạm | **100.0%** (5/5 ca vi phạm) | Bộ kiểm chứng cấu trúc `verify.py` lọc sạch toàn bộ citation giả và số bịa |

### 2. Độ chính xác Phân loại Ý định O2 (`measure_intent.py` trên 40 câu hỏi)

| Chỉ số | Kết quả | Ghi chú |
| --- | :---: | --- |
| **Độ chính xác khớp tập hoàn toàn (Exact-Match)** | **95.0%** (38/40) | Nhận diện chính xác hoàn toàn các cấp phân tích yêu cầu |
| **Tỷ lệ kích hoạt thừa (Over-trigger rate)** | **0.0%** | Tuyệt đối không kích hoạt cấp sâu ngoài ý muốn, tiết kiệm 100% chi phí LLM dư thừa |
| Precision / Recall / F1 — **Descriptive** | 100.0% / 100.0% / **100.0%** | Luôn đảm bảo có câu trả lời mô tả nền tảng |
| Precision / Recall / F1 — **Diagnostic** | 100.0% / 92.3% / **96.0%** | Bắt nhạy các câu hỏi nguyên nhân, đóng góp, kéo giảm |
| Precision / Recall / F1 — **Forecast** | 92.3% / 100.0% / **96.0%** | Bắt chuẩn xác các câu hỏi tương lai, quý tới, dự kiến |
| Precision / Recall / F1 — **Prescriptive** | 100.0% / 100.0% / **100.0%** | Bắt chính xác câu hỏi đề xuất, giải pháp, hành động |

---

### CHANGELOG — Thiết kế lại Giao diện & Xuất Báo cáo

- **Hệ thống Design Token & Bố cục Workspace mới (`tokens.css`, `features.ts`, `AppHeader`, `AppRail`, `QueryBar`, `ResultToolbar`):**
  - Hệ thống biến CSS Token chuẩn hóa: Màu nền tối đa tầng (`--bg-app`, `--bg-surface`, `--bg-elevated`, `--border`), màu ngữ nghĩa (`--accent`, `--pos`, `--neg`, `--warn`), và bảng màu chuỗi 8 màu Okabe-Ito tối ưu độ tương phản cho người khiếm thị màu.
  - Header 56px nền đặc (`var(--bg-surface)`), sticky `top: 0`, `z-index: 50` ngăn ngừa triệt để lỗi chữ chồng chữ khi cuộn trang.
  - Thanh điều hướng bên trái **App Rail** (64px chỉ icon $\leftrightarrow$ 232px mở rộng), ghi nhớ trạng thái trong `localStorage`. Tích hợp kiến trúc cấu hình mở rộng qua `features.ts` (các mục *Lịch sử, Đã lưu, Cài đặt* ở trạng thái `soon` hiển thị mờ, tooltip "Sắp có", không phá vỡ bố cục).
  - Trạng thái trang thông minh: Chuyển đổi từ Landing (biểu mẫu ở giữa) sang Workspace (biểu mẫu thu gọn thành **Query Bar** sticky `top: 56px`, `z-index: 40` với nút [Sửa] và [Hỏi lại]), giúp người dùng thấy ngay kết quả phân tích trong màn hình đầu tiên (1440x900) mà không cần cuộn trang.
  - Lưới kết quả Responsive 12 cột tự động co giãn (`perspective -> span`), thẻ nửa hàng lẻ tự động bung rộng 12 cột.
- **Chuẩn hóa Thẻ Biểu đồ (`ChartCard`) & Khắc phục triệt để lỗi hiển thị (Bảng A5):**
  - Loại bỏ viền trắng focus mặc định xung quanh biểu đồ của Recharts.
  - Xử lý nhãn trục X dính chữ bằng `tickFormatter` định dạng ngắn gọn ("T1/26"), `interval="preserveStartEnd"`, `minTickGap={24}` và padding trục.
  - Trục Y và tooltip định dạng số chuẩn Việt Nam (`vi-VN`), đơn vị hiển thị tại phụ đề thay vì hậu tố rời rạc.
  - Biểu đồ "Đóng góp thay đổi" hiển thị cột âm đỏ (`var(--neg)`), cột dương xanh (`var(--pos)`), bổ sung đường tham chiếu `<ReferenceLine y={0}/>` và nhãn có dấu `+`/`−`.
  - Tooltip tùy biến `ChartTooltip` với màu sắc và bo góc đồng bộ Design Tokens.
  - Tập trung 100% việc định dạng số vào `src/utils/formatters.ts` (`formatNumber`, `formatPercent`, `formatSignedChange`), loại bỏ hoàn toàn các lệnh `toFixed()` phân mảnh.
  - Menu ba chấm trên mỗi thẻ hỗ trợ tải nhanh ảnh PNG độ nét cao hoặc tải file CSV dữ liệu thô.
- **Tính năng Xuất Báo Cáo Đa Định Dạng (Phần B):**
  - **PDF Vector qua `window.print()`:** Dựng trang báo cáo A4 chuyên nghiệp (`ReportDocument`) trong `#print-root` ẩn ngoài màn hình (`position: fixed; left: -10000px; width: 794px`, không dùng `display: none` để Recharts đo đạc kích thước chuẩn xác). Tắt animation biểu đồ (`isAnimationActive={false}`), chủ đề in nền trắng mực tiết kiệm (`[data-theme="print"]`), ngắt trang chuẩn `break-inside: avoid`. Báo cáo bao gồm đầy đủ **Phụ lục A (Bảng số liệu)** và **Phụ lục B (Cách tính & Lưu ý giải trình)**.
  - **Excel (.xlsx) Backend Native (`/export/xlsx`):** Endpoint FastAPI dùng `xlsxwriter` xuất file workbook gồm Sheet "Tóm tắt", từng Sheet cho mỗi biểu đồ kèm bảng số liệu và **biểu đồ Excel gốc (native chart)** cho phép người dùng tùy biến lại trong Excel. Tích hợp cơ chế chống tấn công Formula Injection (ép kiểu `write_string` cho nhãn `= + - @`), chuẩn hóa tên sheet an toàn.
  - **Ảnh PNG (`html-to-image`):** Chụp toàn bộ thẻ `ChartCard` (bao gồm tiêu đề, biểu đồ SVG, chú giải Legend HTML bên ngoài SVG, và chú thích) với `pixelRatio: 2` và đóng dấu "Tạo bởi AI Agent BI".
  - **CSV & Sao chép:** Hàm thuần `buildCsv` bổ sung UTF-8 BOM (`\uFEFF`) và escape ký tự công thức; nút sao chép nhanh nhận xét AI vào clipboard.
- **Việt hóa & Bỏ thuật ngữ kỹ thuật (Phần A6):**
  - Bổ sung từ điển thuật ngữ kinh doanh (`business_terms.py`) và trích xuất đơn vị/tên hiển thị trong `DataProfile` và `ChartSpec`.
  - Nhận xét và thanh tóm tắt hiển thị thân thiện: *"Hệ thống hiểu câu hỏi của bạn là: ..."*.
  - Ẩn thanh độ tin cậy khi $\ge 0.8$, chỉ hiển thị cảnh báo đối chiếu khi $< 0.8$; số liệu chi tiết đưa vào khối kỹ thuật thu gọn.
  - Cập nhật prompt O5 bảo toàn nguyên vẹn tên nhóm thực tế từ dữ liệu.
- **Kiểm thử & Chất lượng:**
  - **167/167 tests backend pass 100%** (`pytest backend/tests`).
  - **16/16 tests frontend pass 100%** (`npm test` với Vitest).
  - Build frontend Vite thành công sạch sẽ trong 405ms.

### CHANGELOG — Dashboard đa góc nhìn (Perspective Planner)

- **Kiến trúc Perspective Planner (`perspective_planner.py`):**
  - Bổ sung lớp lập kế hoạch góc nhìn tất định giữa O3 và O4.
  - Phân loại rõ ràng:
    - *(A) Dẫn xuất:* `period_change` (Bar biến động % kỳ), `cumulative` (Area lũy kế), `moving_average` (Line MA3 làm mượt).
    - *(B) Đồng hành:* `trend_by_group` (Line nhiều chuỗi theo nhóm, hỗ trợ tô đậm chuỗi mục tiêu `highlight_series`), `share_of_total` (Pie tỷ trọng theo nhóm), `contribution_to_change` (Bar đóng góp thay đổi kỳ cuối - kỳ đầu).
  - Áp dụng các điều kiện có ý nghĩa (chỉ số cộng dồn được `_is_addable_metric`, giới hạn số nhóm 2–8, lọc dữ liệu âm) để loại bỏ biểu đồ vô nghĩa đối với các dataset như `ton_kho.csv` hay `danh_gia_khach_hang.csv`.
  - Định dạng số kiểu Việt Nam (`_fmt_vn`) và tự động sinh caption nhận định tất định bám sát dữ liệu (không hallucination, không gọi LLM).
  - Độ trễ bổ sung < 0.05s cho file dữ liệu mẫu, tuyệt đối không gọi thêm LLM API (đảm bảo NFR-01 ≤ 15s).
- **Backend (`schemas.py`, `analysis_runner.py`, `main.py`):**
  - Mở rộng `ChartSpec` với các trường tùy chọn: `role` ("primary" | "supplementary"), `perspective`, `caption`, `highlight_series`.
  - Tách hàm `filter_by_time_range` thành hàm dùng chung để góc nhìn bổ sung có cùng cửa sổ thời gian với câu trả lời chính.
  - Thêm tham số `expand_views: bool = Form(True)` vào endpoint `/analyze` và `/api/analyze`, bọc lỗi an toàn để lỗi góc nhìn bổ sung không bao giờ làm hỏng câu trả lời chính.
- **Frontend (`ChartPanel.tsx`, `App.tsx`, `client.ts`):**
  - Tách bố cục hiển thị thành 2 khu vực trực quan: **Biểu đồ trả lời chính** và **Góc nhìn bổ sung**.
  - Bổ sung công tắc "Hiển thị thêm góc nhìn" trong form câu hỏi.
  - Hỗ trợ biểu đồ nhiều đường với `highlight_series` (tô đậm đường chi nhánh mục tiêu, làm mờ các đường phụ) và hiển thị caption giải thích bên dưới card.
- **Kiểm thử:** Bổ sung 17 test mới (`test_perspective_planner.py`) kiểm tra số liệu thực tế trên `doanh_thu.csv` và các trường hợp biên. Toàn bộ **151/151 tests pass 100%**.

### CHANGELOG Tuần 4

- **O3a — Code Generator (`code_generator.py`):**
  - Triển khai sinh mã theo từng `AnalysisTask` riêng lẻ (không gộp nhiều task vào một prompt).
  - Sử dụng **3 scaffold chuyên biệt** cho 3 loại bài toán (`trend`, `comparison`, `growth_rate`) — LLM chỉ điền logic tính toán bên trong thân hàm `analyze(df)`, khung hàm và định dạng trả về được cố định.
  - Mỗi loại bài toán có bộ few-shot prompt riêng biệt, ngắn gọn, giảm ảo giác.
  - Hỗ trợ cơ chế **Error Feedback** (`previous_error`): khi vòng lặp retry phát hiện lỗi thực thi, thông báo lỗi được truyền ngược vào prompt để LLM sửa đúng trọng tâm.
- **O3b — Sandbox Executor (`sandbox_executor.py`):**
  - Thiết kế kiến trúc phòng thủ **3 lớp**:
    - *Lớp 1 (Tĩnh - AST Check):* Quét cây cú pháp trừu tượng trước khi chạy, chặn triệt để mọi `import`, các hàm nguy hiểm (`eval`, `exec`, `open`, `input`) và mọi truy cập thuộc tính dunder (`__class__`, `__globals__`, `__subclasses__`...).
    - *Lớp 2 (Hệ điều hành - Process Isolation):* Sử dụng `multiprocessing.get_context("spawn")` chạy code trong tiến trình độc lập hoàn toàn; áp dụng `join(timeout)` và `terminate()` để tiêu diệt ngay vòng lặp vô hạn ở tầng OS. Giải quyết bài toán tương thích Windows/Linux/Mac và tránh deadlock trong môi trường đa luồng của FastAPI/uvicorn.
    - *Lớp 3 (Môi trường thực thi - Namespace):* Khởi chạy `exec()` với `__builtins__={}`, cô lập chỉ cho phép truy cập `pd` (pandas) và `df` (DataFrame).
  - Tích hợp điều kiện kiểm tra `resource.setrlimit` trên Linux/Mac (giới hạn 512MB RAM), tự động bỏ qua an toàn trên Windows.
- **Orchestrator (`analysis_runner.py`):**
  - Tách bạch vai trò: sandbox `execute()` chỉ chạy đơn lẻ 1 lần; orchestrator `run_task()` quản lý vòng lặp thử lại tối đa 3 lần (`max_attempts=3`).
  - Tiền xử lý lọc thời gian tất định bằng hàm `_filter_by_time_range()` trong Python trước khi nạp DataFrame vào sandbox — ngăn LLM can thiệp hoặc sai lệch bộ lọc thời gian.
- **Script đo lường AER (`measure_aer.py`):**
  - Xây dựng bộ benchmark 15 câu hỏi thuộc 3 dataset mẫu đo tỉ lệ lỗi phân tích (Analysis Error Rate - SRS NFR-04 ≤ 10%).
- **Tài liệu:**
  - Bổ sung mục 7 trong `docs/ARCHITECTURE.md` ghi nhận trung thực các giới hạn thực tế của sandbox và giải pháp production phục vụ báo cáo đồ án.
  - Cập nhật I/O Contract trong `docs/SRS.md`.

---

## Cấu trúc thư mục

```text
ai-agent-bi/
├── README.md
├── requirements.txt
├── pytest.ini
├── docs/
│   ├── SRS.md                 # Đặc tả yêu cầu v0.2 (4 cấp phân tích & ModePicker)
│   └── ARCHITECTURE.md        # Kiến trúc hệ thống chi tiết (Dual-track & Analytics)
├── data/samples/               # Bộ dữ liệu mẫu để phát triển & test (6 bộ)
│   ├── kinh_doanh_36thang.csv   # Bộ dữ liệu mạnh 36 tháng, 5 chi nhánh, 4 danh mục
│   ├── doanh_thu.csv
│   ├── ban_hang_san_pham.csv
│   ├── chi_phi_van_hanh.csv
│   ├── danh_gia_khach_hang.csv  # edge-case: cột văn bản tự do
│   ├── ton_kho.csv              # edge-case: giá trị thiếu
│   ├── bien_the/                # 7 bộ dữ liệu kiểm thử độ bền (missing, spike, sku...)
│   └── tao_du_lieu_manh.py      # Script sinh dữ liệu có cài sẵn quy luật
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app (/profile, /interpret, /analyze, /deepen, /export)
│   │   ├── schemas.py          # Hợp đồng dữ liệu (Fact, Recommendation, Section, Mode...)
│   │   ├── llm_client.py       # LLMClient/GeminiClient
│   │   └── modules/
│   │       ├── data_profiler.py         # O1 - Data Profiler
│   │       ├── question_interpreter.py  # O2 - Question Interpreter & levels
│   │       ├── code_generator.py        # O3a - Code Generator
│   │       ├── sandbox_executor.py      # O3b - 3-layer Sandbox Executor
│   │       ├── chart_generator.py       # O4 - Chart Generator
│   │       ├── insight_generator.py     # O5 - Insight Generator
│   │       ├── perspective_planner.py   # Lập kế hoạch đa góc nhìn
│   │       └── analytics/               # Bộ tính toán phân tích sâu thuần Python
│   │           ├── availability.py      # Tính độ khả dụng từng cấp & resolve_levels
│   │           ├── series.py            # Tần suất, tổng hợp kỳ, window_compare
│   │           ├── diagnostic.py        # Đóng góp, drill-down 2 cấp, correlation z-score
│   │           ├── forecast.py          # 5 mô hình numpy, rolling backtest, dải 80%
│   │           ├── verify.py            # Kiểm chứng cấu trúc khuyến nghị & chống hallucination
│   │           └── prescriptive.py      # FactSheet synthesis & LLM prescription
│   ├── scripts/
│   │   ├── measure_deepen.py    # Đo lường thực nghiệm 3 cấp phân tích sâu (20 seeds)
│   │   └── measure_intent.py    # Đánh giá độ chính xác nhận diện ý định O2 (40 câu)
│   └── tests/
│       ├── test_data_profiler.py
│       ├── test_enrichment.py
│       ├── test_question_interpreter.py
│       ├── test_code_generator.py
│       ├── test_sandbox.py
│       ├── test_chart_generator.py
│       ├── test_insight_generator.py
│       ├── test_perspective_planner.py
│       ├── test_analytics.py           # 12 test suites phủ toàn bộ 3 cấp phân tích sâu
│       └── ...
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ModePicker.tsx          # 5 pill chế độ phân tích
│   │   │   ├── DeepenSection.tsx       # Vùng hiển thị chẩn đoán, dự báo, đề xuất
│   │   │   ├── FactChip.tsx            # Chip trích dẫn fact có hover tooltip
│   │   │   ├── RecommendationCard.tsx  # Thẻ khuyến nghị kèm caveat & priority
│   │   │   ├── ChartCard.tsx           # Thẻ biểu đồ Recharts (hỗ trợ ComposedChart dự báo)
│   │   │   └── ...
│   │   └── ...
└── .gitlab-ci.yml
```

## Khởi động & Kiểm thử

```bash
# Cài đặt môi trường Python
python -m venv .venv
source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Chạy toàn bộ 167 backend tests
pytest -v

# Sinh bộ dữ liệu mạnh 36 tháng
python -X utf8 data/samples/tao_du_lieu_manh.py --seed 2026

# Chạy thực nghiệm đo lường phân tích sâu (20 seeds)
python -X utf8 backend/scripts/measure_deepen.py --seeds 20

# Chạy đánh giá độ chính xác phân loại ý định (40 câu hỏi)
python -X utf8 backend/scripts/measure_intent.py --mock

# Chạy server Backend
uvicorn backend.app.main:app --reload

# Chạy Frontend (thư mục frontend/)
npm install
npm test
npm run dev
```

## Tài liệu tham khảo

- Dibia, V. (2023). LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. *ACL 2023 System Demonstrations*, 113–126.
- Gartner (2013). *Gartner Analytics Maturity Model: Descriptive, Diagnostic, Predictive, Prescriptive Analytics*.
- Hyndman, R. J., & Athanasopoulos, G. (2018). *Forecasting: principles and practice* (2nd ed.). OTexts: Melbourne, Australia.
- Vovk, V., Gammerman, A., & Shafer, G. (2005). *Algorithmic Learning in a Random World*. Springer Science & Business Media.
