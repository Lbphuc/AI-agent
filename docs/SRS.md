# Tài liệu Đặc tả Yêu cầu Phần mềm (SRS — rút gọn)

## AI Agent Phân tích, Trực quan hóa và Sinh Insight từ Dữ liệu Kinh doanh

**Phiên bản:** 0.2 (Mở rộng 4 Cấp độ Phân tích & Chế độ Pills)
**Trạng thái:** Hoàn thiện — đã triển khai đầy đủ

---

## 1. Giới thiệu

### 1.1. Mục đích tài liệu
Tài liệu này đặc tả yêu cầu chức năng và phi chức năng cho hệ thống AI Agent hỗ trợ phân tích và trực quan hóa dữ liệu kinh doanh đa cấp độ (Mô tả, Chẩn đoán, Dự báo, Đề xuất), làm cơ sở thiết kế kiến trúc (xem `ARCHITECTURE.md`).

### 1.2. Phạm vi sản phẩm
Hệ thống web cho phép người dùng tải lên file CSV hoặc Excel chứa dữ liệu kinh doanh, chọn chế độ phân tích hoặc để AI tự động suy luận ý định, đặt câu hỏi bằng tiếng Việt tự nhiên, và nhận lại:
1. **Phân tích mô tả (Descriptive):** Toàn cảnh các chỉ số, biểu đồ chính và dashboard đa góc nhìn.
2. **Phân tích chẩn đoán (Diagnostic):** Phân tích yếu tố đóng góp theo cửa sổ chu kỳ, drill-down 2 cấp tìm điểm nghẽn tập trung, tương quan trong từng chuỗi khử hiệu ứng quy mô.
3. **Phân tích dự báo (Forecast):** Dự báo định lượng thuần numpy qua backtest rolling-origin, dải tin cậy 80% conformal, đánh giá mức độ tin cậy và cơ chế từ chối (guard) trung thực.
4. **Phân tích đề xuất (Prescriptive):** Khuyến nghị hành động dựa trên FactSheet, bắt buộc trích dẫn sự thật (`fact_ids`), được kiểm chứng cấu trúc tất định để loại bỏ hoàn toàn hiện tượng bịa đặt (hallucination).

### 1.3. Tài liệu tham khảo
- Dibia, V. (2023). LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. *Proceedings of the 61st ACL: System Demonstrations*, 113–126.
- Gartner Business Analytics Maturity Model (Descriptive, Diagnostic, Predictive, Prescriptive).
- Hyndman, R. J., & Athanasopoulos, G. (2018). *Forecasting: principles and practice* (2nd ed.). OTexts.

### 1.4. Từ viết tắt

| Viết tắt | Ý nghĩa |
|---|---|
| LLM | Large Language Model |
| FR | Functional Requirement (yêu cầu chức năng) |
| NFR | Non-functional Requirement (yêu cầu phi chức năng) |
| AER | Analysis Error Rate |
| MAPE | Mean Absolute Percentage Error |
| FactSheet | Bảng sự thật định lượng có mã ID duy nhất làm căn cứ cho LLM |

---

## 2. Mô tả tổng quan

### 2.1. Bối cảnh sản phẩm
Doanh nghiệp thường đối mặt với các bài toán: *"Số liệu hiện tại thế nào?"* (Mô tả), *"Vì sao lại giảm/tăng?"* (Chẩn đoán), *"Tương lai sắp tới ra sao?"* (Dự báo), và *"Nên hành động gì?"* (Đề xuất). Hệ thống tự động hóa toàn bộ 4 cấp độ này với nguyên tắc cốt lõi: **mọi phép tính định lượng đều do Python tất định xử lý; LLM chỉ diễn giải và sinh đề xuất dựa trên các fact có mã dẫn chứng đã kiểm định**.

### 2.2. Đối tượng người dùng
Chủ doanh nghiệp nhỏ, nhân viên kinh doanh/vận hành, sinh viên, nhà phân tích dữ liệu muốn đào sâu nguyên nhân và dự báo xu hướng nhanh chóng.

### 2.3. Giả định và ràng buộc
- Dữ liệu đầu vào là file CSV hoặc Excel (.xlsx) có cấu trúc bảng.
- Backend xử lý tính toán tất định bằng numpy/pandas; LLM (Gemini) thực hiện suy luận ý định và sinh ngôn ngữ tự nhiên.
- Mọi khuyến nghị chiến lược phải gắn liền với mã fact có thật trong FactSheet.

---

## 3. Yêu cầu chức năng (Functional Requirements)

| ID | Mô tả | Module liên quan | Ưu tiên |
|---|---|---|---|
| FR-01 | Hệ thống cho phép người dùng tải lên file CSV | Giao diện web | Cao |
| FR-02 | Hệ thống tự động trích xuất schema, kiểu dữ liệu, thống kê mô tả, nhận diện cột thời gian/nhóm/số và kiểm tra tính khả dụng cho từng chế độ | O1 — Data Profiler / Availability | Cao |
| FR-03 | Hệ thống cho phép người dùng nhập câu hỏi bằng ngôn ngữ tự nhiên (tiếng Việt) | Giao diện web | Cao |
| FR-04 | Hệ thống phân rã câu hỏi thành mục tiêu phân tích có cấu trúc và suy ra các cấp phân tích (`levels`) | O2 — Question Interpreter | Cao |
| FR-05 | Hệ thống sinh mã phân tích (pandas) tương ứng với mục tiêu mô tả | O3a — Code Generator | Cao |
| FR-06 | Hệ thống thực thi mã phân tích trong sandbox an toàn, phát hiện lỗi và tự sinh lại tối đa N lần | O3b — Sandbox Executor | Cao |
| FR-07 | Hệ thống sinh biểu đồ trực quan từ kết quả tính toán | O4 — Chart Generator | Cao |
| FR-08 | Hệ thống sinh nhận xét ngôn ngữ tự nhiên, bám sát số liệu đã tính, trả lời trực tiếp câu hỏi | O5 — Insight Generator | Cao |
| FR-09 | Hệ thống hiển thị kết quả tổng hợp trên giao diện web theo bố cục ưu tiên cấp độ đang chọn | Giao diện web | Cao |
| FR-10 | Hệ thống ghi log lỗi và độ trễ của từng module để phục vụ đánh giá | Toàn hệ thống | Trung bình |
| FR-11 | Hệ thống áp dụng giá trị mặc định hợp lý khi câu hỏi thiếu thông tin | O2 — Question Interpreter | Trung bình |
| FR-12 | Hệ thống đọc được file Excel (.xlsx) và CSV với nhiều bảng mã (UTF-8, cp1258) và tự phát hiện dấu phân cách | O1 — Data Profiler / main.py | Cao |
| FR-13 | Hệ thống tự động nhận biết và chuyển đổi số định dạng Việt Nam ("1.500.000") thành giá trị số trước khi phân tích | O1 — Data Profiler (Stage 0) | Cao |
| FR-14 | Hệ thống cho phép tải lên nhiều file cùng lúc và trả về DataProfile riêng biệt cho từng file (/profile-many) | O1 — Data Profiler / main.py | Trung bình |
| FR-15 | Hệ thống hỗ trợ Dashboard đa góc nhìn (Perspective Planner) tự động bổ sung biểu đồ phân rã tất định kèm chú thích tự động | Perspective Planner | Cao |
| FR-16 | Hệ thống hỗ trợ xuất báo cáo đa định dạng: PDF vector A4, Excel (.xlsx kèm biểu đồ gốc), ảnh PNG, và CSV UTF-8 BOM | Backend / Giao diện web | Cao |
| FR-17 | Giao diện hỗ trợ cấu hình mở rộng tính năng (App Rail, Result Toolbar), thanh truy vấn thu gọn trong workspace, và hệ thống Design Token | Giao diện web | Cao |
| FR-18 | **Phân tích Chẩn đoán (Diagnostic):** Phân tích đóng góp qua `window_compare()`, drill-down 2 cấp tìm điểm nghẽn tập trung, tương quan trong từng chuỗi khử hiệu ứng quy mô (within-series z-score) | analytics/diagnostic.py | Cao |
| FR-19 | **Phân tích Dự báo (Forecast):** Dự báo định lượng qua 5 mô hình numpy, rolling-origin backtest, dải tin cậy 80% conformal, đánh giá mức độ tin cậy và guard từ chối khi < 15 kỳ | analytics/forecast.py | Cao |
| FR-20 | **Phân tích Đề xuất (Prescriptive):** Tổng hợp FactSheet, gọi LLM sinh khuyến nghị trích dẫn `fact_ids`, bộ kiểm chứng tất định `verify.py` loại bỏ đề xuất bịa số/thiếu căn cứ | analytics/prescriptive.py | Cao |
| FR-21 | **Chế độ Phân tích Pills (ModePicker):** 5 chế độ (Tự động, Tổng quan, Tìm nguyên nhân, Dự đoán tương lai, Gợi ý chiến lược), làm mờ pill không khả dụng kèm lý do, thực thi song song, chạy bù khi đổi pill sau kết quả | ModePicker / main.py | Cao |

---

## 4. Yêu cầu phi chức năng (Non-functional Requirements)

| ID | Mô tả |
|---|---|
| NFR-01 (Hiệu năng) | Thời gian phản hồi phân tích sâu (Chẩn đoán/Dự báo) ≤ 500ms cho file dữ liệu; toàn bộ pipeline song song ≤ 10 giây |
| NFR-02 (Bảo mật) | Mã sinh do LLM chạy trong sandbox cô lập; phép tính 3 cấp sâu là Python tất định an toàn, không sinh mã bằng LLM |
| NFR-03 (Độ tin cậy) | Tỷ lệ tìm đúng driver chẩn đoán = 100%; dải dự báo 80% đạt độ phủ thực nghiệm ≥ 80%; tỷ lệ loại bỏ đề xuất sai phạm qua verify = 100% |
| NFR-04 (Khả năng sử dụng) | Giao diện Pills tương thích chuẩn WCAG (phím mũi tên, ARIA radiogroup, thông báo lý do khi nút bị khóa) |
| NFR-05 (Khả năng mở rộng) | Kiến trúc stateless, cờ tính năng `FEATURE_DEEPEN`, các module độc lập có unit test đầy đủ |

---

## 5. Đặc tả giao diện module (I/O Contract)

Interface chi tiết được định nghĩa bằng Pydantic trong `backend/app/schemas.py`:

| Module | Input | Output |
|---|---|---|
| O1 — Data Profiler | `DataFrame` | `DataProfile` (schema, n_periods, frequency, availability) |
| O2 — Question Interpreter | `question: str`, `DataProfile` | `AnalysisGoal` (time_scope, tasks, levels: list[AnalysisLevel]) |
| /interpret | `file`, `question`, `mode` | `InterpretResponse` (goal, levels, notices, goal_summary) |
| /analyze | `file`, `question`, `expand_views`, `goal` (tùy chọn) | `AnalyzeResponse` (goal, task_results, charts, insight, meta) |
| /deepen | `file`, `goal`, `level` ("diagnostic" \| "forecast" \| "prescriptive") | `DeepenResponse` (level, sections, recommendations, facts, warnings) |
| analytics/diagnostic | `df`, `profile`, `goal` | `tuple[Section, list[Fact]]` |
| analytics/forecast | `df`, `profile`, `goal`, `h=3` | `tuple[Section, list[Fact]]` |
| analytics/verify | `Recommendation`, `list[Fact]` | `tuple[bool, Optional[str]]` |
| analytics/prescriptive | `df`, `profile`, `goal`, `llm` | `DeepenResponse` (sections, recommendations, facts) |

---

## 6. Tiêu chí nghiệm thu (Acceptance Criteria)

1. **Bộ dữ liệu kiểm thử mạnh (`kinh_doanh_36thang.csv`, 720 dòng, 36 tháng, 5 chi nhánh, 4 danh mục):**
   - Chẩn đoán chỉ ra chính xác Đà Nẵng là chi nhánh giảm duy nhất (−279 triệu VNĐ), và drill-down chỉ ra ngành Điện tử Đà Nẵng (−381 triệu VNĐ).
   - Tương quan marketing trong từng chuỗi đạt $r \approx 0.46$ (tránh con số sai lệch $r \approx 0.89$ do hiệu ứng quy mô).
   - Dự báo chọn mô hình có mùa (seasonal_decomp) với MAPE backtest < 5%, dải tin cậy 80% bao trọn thực tế.
2. **Bộ dữ liệu ngắn (`doanh_thu.csv`, 12 kỳ):**
   - Pill "Dự đoán tương lai" bị khóa kèm thông báo lý do *"Cần ít nhất 15 kỳ dữ liệu (hiện có 12)"*.
   - Chế độ Tổng quan và Tìm nguyên nhân vẫn hoạt động bình thường.
3. **Bộ kiểm chứng đề xuất (`verify.py`):**
   - 100% khuyến nghị hiển thị đều trích dẫn `fact_ids` có thật và con số khớp với FactSheet.
   - Các trường hợp bịa số, thiếu caveat, thiếu tên đối tượng, hoặc khẳng định chắc chắn số liệu ước tính đều bị loại bỏ tự động.
4. **Hồi quy & Tương thích ngược:**
   - 100% bài test các tuần trước vẫn pass đầy đủ.
   - Không làm hỏng chức năng xuất báo cáo PDF và Excel.
