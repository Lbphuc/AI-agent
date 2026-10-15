# Kiến trúc Hệ thống

## AI Agent Phân tích, Trực quan hóa và Sinh Insight từ Dữ liệu Kinh doanh (4 Cấp độ Phân tích)

Kiến trúc kế thừa tư tưởng pipeline đa giai đoạn của LIDA (Dibia, 2023) —
tách rời bước LLM sinh mã và bước runtime thực thi mã (theo tinh thần
Program-Aided Language Models) — đồng thời mở rộng toàn diện theo mô hình
trưởng thành phân tích 4 cấp của Gartner: **Mô tả (Descriptive) · Chẩn đoán (Diagnostic) · Dự báo (Forecast) · Đề xuất (Prescriptive)**.

---

## 1. Sơ đồ luồng xử lý toàn diện (Comprehensive Data-flow View)

```
                       Gửi (File + Câu hỏi + Chế độ phân tích Pills)
                                             │
                       POST /interpret (File, Question, Mode)
                                             ▼
                 { AnalysisGoal, levels, notices, goal_summary }
                 Hiển thị ngay khung chờ (Skeleton) + Goal Summary
                                             │
            ┌────────────────────────────────┴────────────────────────────────┐
            ▼                                                                 ▼
   TUYẾN 1: PHÂN TÍCH MÔ TẢ                                         TUYẾN 2: PHÂN TÍCH SÂU 3 CẤP
      (POST /analyze)                                                  (POST /deepen theo cấp)
            │                                                                 │
   O1: Data Profiler                                                analytics/ (THUẦN PYTHON TẤT ĐỊNH)
            │                                                       ├── series.py (window_compare)
   O2: Bỏ qua (đã có goal)                                         ├── diagnostic.py (driver, correlation)
            │                                                       ├── forecast.py (5 mô hình, backtest, dải 80%)
   O3: LLM Code Gen + Sandbox                                      └── facts.py (FactSheet có ID)
            │                                                                 │
   O4: Chart Gen (primary)                                                    ▼
            │                                                     FactSheet (Bảng sự thật định lượng)
   Perspective Planner (supplementary)                                        │
            │                                            LLM chỉ nhận FactSheet: diễn giải & sinh đề xuất
   O5: Insight Gen (NLG)                                                      │
            │                                                                 ▼
            │                                                      verify.py (Kiểm chứng tất định)
            │                                                                 │
            └────────────────────────────────┬────────────────────────────────┘
                                             ▼
                              Kết quả hiển thị tích hợp:
                 Goal Summary & Notices → Nhận xét trả lời câu hỏi
              → Khu vực ưu tiên theo Mode (Chẩn đoán / Dự báo / Đề xuất)
                 → Biểu đồ chính & Dashboard đa góc nhìn
```

---

## 2. Sáu quyết định thiết kế cốt lõi của Hệ thống Phân tích Sâu

1. **Phép tính ở 3 cấp mới đều là Python tin cậy, không phải mã LLM sinh:**
   - Sandbox chặn `import` và mỗi tiến trình `spawn` phải nạp lại thư viện nặng vừa chậm vừa dễ vượt timeout.
   - Nhánh chẩn đoán và dự báo chạy bằng Python tất định (numpy/pandas) đảm bảo thời gian tính toán < 100ms, độ tin cậy toán học tuyệt đối.
   - Phần trả lời câu hỏi gốc vẫn đi qua O3 (LLM sinh mã → sandbox → đo AER), bảo toàn câu chuyện nghiên cứu của đồ án.

2. **Bảng sự thật (FactSheet) làm nguồn duy nhất cho LLM:**
   - Mỗi con số mà LLM được phép nhắc đến là một `Fact` có `id` ổn định (`F1`, `F2`...).
   - LLM không nhận raw DataFrame, không tự ý bịa số tự do.

3. **Đề xuất chiến lược được kiểm chứng bằng cấu trúc (Citation-grounded Verification):**
   - Mỗi khuyến nghị phải trả về `fact_ids` hợp lệ.
   - Module `verify.py` kiểm tra: ID có thật trong FactSheet, số liệu và tên thực thể khớp fact trích dẫn, fact ước tính phải ghi rõ "ước tính/dự kiến", cấm từ khẳng định nhân quả tuyệt đối. Khuyến nghị vi phạm bị loại bỏ ngay lập tức.

4. **Thực thi theo yêu cầu & chạy song song (`/interpret`, `/analyze`, `/deepen`):**
   - `/interpret` hiểu câu hỏi một lần duy nhất. Sau đó client gọi song song `/analyze` và `/deepen` cho các cấp cần thiết.
   - Khi người dùng đổi pill sau khi đã có kết quả: hệ thống chỉ gọi `/deepen` để **chạy bù cấp còn thiếu**, không gọi lại `/interpret` hay `/analyze`.

5. **So sánh theo cửa sổ (`window_compare`), không so điểm đầu với điểm cuối:**
   - N kỳ gần nhất so với N kỳ liền trước để khử nhiễu và mùa vụ.
   - Đồng bộ hóa logic giữa chẩn đoán và `Perspective Planner` để dashboard và chẩn đoán không bao giờ mâu thuẫn số liệu.

6. **Dự báo trung thực: độ tin cậy từ Backtest cuốn chiếu, dải bất định conformal:**
   - 5 mô hình ứng viên (naive, seasonal_naive, linear, holt, seasonal_decomp) cạnh tranh trên backtest rolling-origin.
   - Dải tin cậy 80% lấy từ phân vị sai số backtest thật (conformal prediction).
   - Guard nghiêm ngặt: từ chối dự báo khi dữ liệu < 15 kỳ hoặc thiếu > 20% chuỗi.

---

## 3. Kiến trúc các thành phần mới

### 3.1. Package `backend/app/modules/analytics/`
- **`availability.py`:** Hàm thuần `compute_availability()` và `resolve_levels()`. Kiểm tra cấu trúc dữ liệu để xác định pill nào dùng được ngay khi tải file lên.
- **`series.py`:** Suy ra tần suất dữ liệu (ngày/tuần/tháng/quý), chính sách tổng hợp (`sum`/`mean`), reindex lấp đầy chuỗi, hàm so sánh cửa sổ `window_compare()`.
- **`diagnostic.py`:** Tính đóng góp từng nhóm theo cửa sổ kỳ, drill-down tìm nhóm dẫn dắt (driver) sụt giảm/tăng trưởng mạnh nhất, tính tương quan chuẩn hóa theo chuỗi (within-series z-score correlation) để khử hiệu ứng quy mô.
- **`forecast.py`:** 5 mô hình dự báo thuần numpy (~15 dòng mỗi mô hình), rolling-origin backtest ($h=3$), dải tin cậy 80% conformal, đánh giá độ tin cậy và kiểm tra guard.
- **`verify.py`:** Bộ kiểm chứng tất định trích dẫn sự thật cho khuyến nghị chiến lược.
- **`prescriptive.py`:** Tổng hợp FactSheet đa cấp, prompt LLM sinh đề xuất có dẫn chứng, cơ chế thử lại tối đa 1 lần nếu đề xuất bị reject, trả về kết quả rỗng trung thực khi thiếu bằng chứng.

### 3.2. Frontend UI Layer (Pills & Workspace)
- **`ModePicker` (5 Pills):**
  - Tự động (`auto`): AI suy luận cấp độ cần chạy từ câu hỏi.
  - Tổng quan (`descriptive`): Xem toàn cảnh số liệu và dashboard đa góc nhìn.
  - Tìm nguyên nhân (`diagnostic`): Yếu tố đóng góp & điểm nghẽn.
  - Dự đoán tương lai (`forecast`): Dự báo xu hướng và dải tin cậy 80%.
  - Gợi ý chiến lược (`prescriptive`): Đề xuất hành động kèm dẫn chứng số liệu.
- **`DeepenSection`:** Render linh hoạt từng cấp độ phân tích chuyên sâu với huy hiệu riêng, biểu đồ chuyên dụng và khối căn cứ thu gọn.
- **`RecommendationCard` & `FactChip`:** Thẻ đề xuất hiển thị mức ưu tiên, hành động, căn cứ, điều kiện kiểm chứng (`caveat`), và chip dẫn chứng `FactChip` có tooltip số liệu chi tiết.
- **`ChartCard` (Nâng cấp Dự báo):** Hỗ trợ `ComposedChart` với đường nét đứt cho chuỗi dự báo, vùng tô mờ cho dải bất định 80%, và đường tham chiếu dọc `ReferenceLine` tại mốc bắt đầu dự báo.

---

## 4. Ánh xạ công nghệ

| Thành phần | Công nghệ | Trạng thái |
|---|---|---|
| Backend framework | FastAPI | Đã triển khai (`main.py`) |
| Xử lý dữ liệu & Profiling | pandas + openpyxl | Đã cài đặt (O1, hỗ trợ số Việt Nam, availability) |
| Module Chẩn đoán | numpy + pandas | Đã cài đặt (`analytics/diagnostic.py`) |
| Module Dự báo | numpy thuần (5 mô hình + backtest) | Đã cài đặt (`analytics/forecast.py`) |
| Kiểm chứng Đề xuất | Python tất định regex + numerical matching | Đã cài đặt (`analytics/verify.py`) |
| Sinh Đề xuất Chiến lược | Gemini API (`google-genai`) qua `LLMClient` | Đã cài đặt (`analytics/prescriptive.py`) |
| Xuất báo cáo Excel | XlsxWriter (native charts + formula safety) | Đã cài đặt (`modules/excel_exporter.py`) |
| Sandbox thực thi mã mô tả | Subprocess spawn + AST check 3 lớp | Đã hoàn thành Tuần 4 |
| Trực quan hóa Biểu đồ | Recharts 3.x (Bar, Line, Pie, Area, Composed) | Đã hoàn thành |
| Frontend | React 19 + TypeScript + Vite | Đã hoàn thành (ModePicker, DeepenSection, FactChip, RecommendationCard) |
| Kiểm thử Backend | pytest (167 tests xanh 100%) | Đã hoàn thành |
| Kiểm thử Frontend | Vitest (16 tests xanh 100%) | Đã hoàn thành |

---

## 5. Kết quả thực nghiệm chính

Số liệu đo lường thực tế từ `backend/scripts/measure_deepen.py` trên 20 seed:

| Tiêu chí | Kết quả thực nghiệm | Ý nghĩa |
|---|---|---|
| **Tỷ lệ tìm đúng Driver chẩn đoán** | **100.0% (20/20 seed)** | Hệ thống luôn chỉ ra chính xác Đà Nẵng × Điện tử là nguyên nhân cốt lõi gây sụt giảm |
| **Độ trễ tính toán Chẩn đoán** | **~44.2 ms** | Nhanh hơn 300 lần so với việc dùng LLM sinh mã |
| **MAPE backtest Dự báo** | **3.29%** | Mô hình có mùa vượt trội hoàn toàn so với đường cơ sở naive |
| **Độ phủ thực tế dải tin cậy 80%** | **100.0%** | Dải bất định conformal bao bọc an toàn mọi điểm thực tế ngoài mẫu |
| **Độ trễ tính toán Dự báo** | **~9.6 ms** | Cực kỳ tối ưu, hoàn toàn không gây trễ giao diện |
| **Hiệu quả bộ kiểm chứng verify.py** | **Chặn 100% đề xuất vi phạm** | Phát hiện và loại bỏ toàn bộ các trường hợp ID giả, số bịa, thiếu caveat, thiếu tên thực thể |
