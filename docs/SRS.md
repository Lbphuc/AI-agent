# Tài liệu Đặc tả Yêu cầu Phần mềm (SRS — rút gọn)

## AI Agent Phân tích, Trực quan hóa và Sinh Insight từ Dữ liệu Kinh doanh

**Phiên bản:** 0.1 (Tuần 1/8)
**Trạng thái:** Nháp — sẽ cập nhật khi thiết kế chi tiết từng module ở các tuần tiếp theo

---

## 1. Giới thiệu

### 1.1. Mục đích tài liệu
Tài liệu này đặc tả yêu cầu chức năng và phi chức năng cho hệ thống AI Agent hỗ trợ phân tích và trực quan hóa dữ liệu kinh doanh, làm cơ sở thiết kế kiến trúc (xem `ARCHITECTURE.md`) và triển khai trong 8 tuần.

### 1.2. Phạm vi sản phẩm
Hệ thống web cho phép người dùng tải lên file CSV chứa dữ liệu kinh doanh (ví dụ: doanh thu theo tháng/chi nhánh), đặt câu hỏi bằng tiếng Việt tự nhiên, và nhận lại biểu đồ, bảng số liệu và nhận xét (insight) tự động — không cần biết lập trình hay công cụ phân tích dữ liệu.

### 1.3. Tài liệu tham khảo
Dibia, V. (2023). LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics: System Demonstrations*, 113–126.

### 1.4. Từ viết tắt

| Viết tắt | Ý nghĩa |
|---|---|
| LLM | Large Language Model |
| FR | Functional Requirement (yêu cầu chức năng) |
| NFR | Non-functional Requirement (yêu cầu phi chức năng) |
| AER | Analysis Error Rate |
| SEVQ | Self-Evaluated Visualization Quality (khái niệm gốc từ LIDA) |

---

## 2. Mô tả tổng quan

### 2.1. Bối cảnh sản phẩm
Doanh nghiệp vừa và nhỏ thường có dữ liệu kinh doanh dạng bảng nhưng thiếu nhân sự phân tích chuyên môn. Hệ thống đóng vai trò một "nhà phân tích dữ liệu ảo", tự động hóa toàn bộ chuỗi: hiểu dữ liệu → hiểu câu hỏi → tính toán → trực quan hóa → diễn giải.

### 2.2. Đối tượng người dùng
Chủ doanh nghiệp nhỏ, nhân viên kinh doanh/vận hành không có nền tảng kỹ thuật, sinh viên/nhà nghiên cứu muốn khám phá dữ liệu nhanh.

### 2.3. Giả định và ràng buộc
- Dữ liệu đầu vào là file CSV có cấu trúc bảng, có ít nhất một cột thời gian và một cột giá trị số.
- Người dùng đặt câu hỏi bằng tiếng Việt.
- Hệ thống cần kết nối Internet để gọi API LLM (Claude); không hoạt động ở chế độ offline hoàn toàn.
- Giới hạn 8 tuần phát triển → xem "Phạm vi trong/ngoài" trong Project Proposal.

---

## 3. Yêu cầu chức năng (Functional Requirements)

| ID | Mô tả | Module liên quan | Ưu tiên |
|---|---|---|---|
| FR-01 | Hệ thống cho phép người dùng tải lên file CSV | Giao diện web | Cao |
| FR-02 | Hệ thống tự động trích xuất schema, kiểu dữ liệu, thống kê mô tả, nhận diện cột thời gian/nhóm/số | O1 — Data Profiler | Cao |
| FR-03 | Hệ thống cho phép người dùng nhập câu hỏi bằng ngôn ngữ tự nhiên (tiếng Việt) | Giao diện web | Cao |
| FR-04 | Hệ thống phân rã câu hỏi thành mục tiêu phân tích có cấu trúc (loại phân tích, chỉ số, cột nhóm) | O2 — Question Interpreter | Cao |
| FR-05 | Hệ thống sinh mã phân tích (pandas) tương ứng với mục tiêu | O3a — Code Generator | Cao |
| FR-06 | Hệ thống thực thi mã phân tích trong sandbox an toàn, phát hiện lỗi và tự sinh lại tối đa N lần | O3b — Sandbox Executor | Cao |
| FR-07 | Hệ thống sinh biểu đồ trực quan (line chart xu hướng, bar chart so sánh) từ kết quả tính toán | O4 — Chart Generator | Cao |
| FR-08 | Hệ thống sinh nhận xét ngôn ngữ tự nhiên, bám sát số liệu đã tính, trả lời trực tiếp câu hỏi | O5 — Insight Generator | Cao |
| FR-09 | Hệ thống hiển thị kết quả tổng hợp (biểu đồ + bảng số liệu + nhận xét) trên giao diện web | Giao diện web | Cao |
| FR-10 | Hệ thống ghi log lỗi và độ trễ của từng module để phục vụ đánh giá | Toàn hệ thống | Trung bình |
| FR-11 | Hệ thống áp dụng giá trị mặc định hợp lý khi câu hỏi thiếu thông tin (ví dụ: mặc định "12 tháng gần nhất" nếu không nêu rõ khoảng thời gian) | O2 — Question Interpreter | Trung bình |

---

## 4. Yêu cầu phi chức năng (Non-functional Requirements)

| ID | Mô tả |
|---|---|
| NFR-01 (Hiệu năng) | Thời gian phản hồi trung bình ≤ 15 giây cho file ≤ 10.000 dòng (bao gồm toàn bộ pipeline 5 module) |
| NFR-02 (Bảo mật) | Mã do LLM sinh ra chỉ được thực thi trong sandbox cô lập, không có quyền truy cập file hệ thống hoặc mạng ngoài |
| NFR-03 (Độ tin cậy) | Analysis Error Rate (AER) ≤ 10% trên bộ câu hỏi thử nghiệm chuẩn (xem mục 8) |
| NFR-04 (Khả năng sử dụng) | Giao diện tiếng Việt, luồng thao tác tối đa 3 bước: tải file → nhập câu hỏi → xem kết quả |
| NFR-05 (Khả năng bảo trì) | Mỗi module (O1–O5) độc lập, có interface rõ ràng (xem mục 6), có thể kiểm thử/thay thế riêng lẻ |
| NFR-06 (Khả năng mở rộng) | Kiến trúc cho phép bổ sung loại biểu đồ hoặc loại câu hỏi mới mà không phải sửa đổi toàn bộ pipeline |

---

## 5. Use Case chính

**UC-01: Phân tích xu hướng doanh thu và tìm chi nhánh giảm mạnh nhất**

- **Actor:** Người dùng doanh nghiệp
- **Điều kiện tiên quyết:** Có file CSV hợp lệ (có cột thời gian, cột chi nhánh, cột doanh thu)
- **Luồng chính:**
  1. Người dùng tải lên `doanh_thu.csv`.
  2. Hệ thống chạy O1, hiển thị tóm tắt dữ liệu đã nhận diện được (schema, khoảng thời gian, danh sách chi nhánh).
  3. Người dùng nhập câu hỏi: *"Phân tích xu hướng doanh thu 12 tháng gần nhất và cho biết chi nhánh nào giảm mạnh nhất."*
  4. Hệ thống chạy O2 → sinh mục tiêu: {trend theo tháng} + {growth_rate theo chi nhánh, find=min}.
  5. Hệ thống chạy O3 (sinh mã + thực thi) → tính tổng doanh thu theo tháng, tính % tăng trưởng theo từng chi nhánh.
  6. Hệ thống chạy O4 → sinh line chart (xu hướng theo tháng) + bar chart (so sánh chi nhánh).
  7. Hệ thống chạy O5 → sinh nhận xét, ví dụ: "Doanh thu tổng thể tăng X%; chi nhánh Đà Nẵng giảm mạnh nhất với -35,6%."
  8. Hệ thống hiển thị kết quả tổng hợp (FR-09).
- **Điều kiện kết thúc:** Người dùng nhìn thấy đầy đủ biểu đồ + số liệu + nhận xét.
- **Luồng ngoại lệ:**
  - File không hợp lệ (không có cột thời gian/số) → thông báo lỗi rõ ràng, gợi ý định dạng đúng.
  - Câu hỏi quá mơ hồ → áp dụng giá trị mặc định (FR-11) hoặc yêu cầu người dùng làm rõ.
  - Mã phân tích lỗi liên tục sau `max_attempts` lần → trả về thông báo lỗi kèm gợi ý, không để hệ thống treo.

---

## 6. Đặc tả giao diện module (I/O Contract)

Interface chi tiết được định nghĩa bằng Pydantic trong `backend/app/schemas.py`. Tóm tắt:

| Module | Input | Output |
|---|---|---|
| O1 — Data Profiler | `DataFrame` | `DataProfile` (schema, time_column, group_columns, numeric_columns) |
| O2 — Question Interpreter | `question: str`, `DataProfile` | `AnalysisGoal` (time_scope, time_start, time_end, list[AnalysisTask]) |
| O3a — Code Generator | `AnalysisGoal`, `DataProfile` | `CodeGenResult` (code, expected_outputs) |
| O3b — Sandbox Executor | `code: str`, `DataFrame` | `ExecutionResult` (success, results, error, attempts) |
| O4 — Chart Generator | `list[AnalysisTask]`, `ExecutionResult` | `list[ChartSpec]` (chart_type, title, x, series) |
| O5 — Insight Generator | `question: str`, `ExecutionResult` | `InsightResult` (insight_text, confidence_score) |

Sơ đồ luồng dữ liệu đầy đủ: xem `docs/ARCHITECTURE.md`.

---

## 7. Phân loại "gọi API LLM" vs "tự viết logic"

| Module | Cách triển khai | Lý do |
|---|---|---|
| O1 — Data Profiler | Tự viết (pandas thuần) | Phép biến đổi xác định (deterministic), không cần LLM |
| O2 — Question Interpreter | Gọi API LLM | Hiểu ngôn ngữ tự do, không thể phủ hết bằng luật |
| O3a — Code Generator | Gọi API LLM (fill-in-the-middle) | Cần suy luận sinh mã đúng theo mục tiêu |
| O3b — Sandbox Executor | Tự viết | Logic kỹ thuật thuần túy, không giao an toàn thực thi cho LLM |
| O4 — Chart Generator | Tự viết (rule-based) | Loại phân tích đã xác định trước, chỉ cần ánh xạ tất định |
| O5 — Insight Generator | Gọi API LLM | Bài toán sinh ngôn ngữ tự nhiên (NLG) |

---

## 8. Tiêu chí nghiệm thu (Acceptance Criteria)

Bộ đánh giá gồm 5–8 bộ CSV mẫu (xem `data/samples/`), mỗi bộ kèm 3–5 câu hỏi thuộc các dạng: xu hướng, so sánh, tăng/giảm.

| Tiêu chí | Ngưỡng chấp nhận |
|---|---|
| Analysis Error Rate (AER) | ≤ 10% |
| Numeric Accuracy (số liệu trong nhận xét khớp với số liệu tính toán) | ≥ 95% |
| Insight Relevance (LLM tự chấm 1–10, đối chiếu thủ công một phần) | ≥ 7/10 trung bình |
| Latency trung bình toàn pipeline | ≤ 15 giây/câu hỏi (file ≤ 10.000 dòng) |

---

## 9. Ghi chú: hướng "tự train" thay vì gọi API (tùy chọn nâng cao)

Không bắt buộc cho MVP 8 tuần, nhưng có thể cân nhắc tự huấn luyện một mô hình phân loại nhẹ (không phải LLM, ví dụ Random Forest trên đặc trưng thống kê của cột) để thay thế phần nhận diện kiểu ngữ nghĩa cột trong O1, theo hướng nghiên cứu Sato (Zhang et al., 2019) mà LIDA có trích dẫn — giúp giảm phụ thuộc gọi API cho tác vụ đơn giản này.
