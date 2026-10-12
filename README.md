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
  - **155/155 tests backend pass 100%** (`pytest backend/tests`).
  - **14/14 tests frontend pass 100%** (`npm test` với Vitest).
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
- **Kiểm thử:** Đạt **72/72 tests pass** (bổ sung 38 test mới phủ toàn bộ O3a, O3b, orchestrator, timeout process).

### CHANGELOG Tuần 3

- **Refactor:** tách `LLMClient`/`ClaudeClient` ra `backend/app/llm_client.py`
  dùng chung, vì từ tuần này có 2 module (O1 Stage 2, O2) cùng cần đến
  — tránh trùng lặp code, tránh lệch nhau khi đổi model mặc định.
- **Chốt schema:** `AnalysisTask.type`/`find` chuyển từ `str` tự do
  sang `Literal[...]` (đúng như đã ghi chú "cố tình chưa sửa" ở Tuần
  1-2 — nay cài đặt O2 thật nên chốt lại). Thay `AnalysisGoal.time_range`
  (chuỗi tự do) bằng `time_scope` (nhãn LLM chọn: "all" |
  "last_3_months" | "last_6_months" | "last_12_months" | "custom") +
  `time_start`/`time_end` (ngày cụ thể do PYTHON tính, không phải LLM).
- **Mới:** `question_interpreter.interpret()` — prompt few-shot (5 ví
  dụ, gắn chặt vào tên cột thật của dataset để giảm hallucination),
  xử lý đúng 3 loại phân tích trong kế hoạch (trend, comparison,
  growth_rate). Có "grounding check": mọi `metric`/`group_by` LLM
  chọn đều bị đối chiếu lại với `DataProfile` bằng code tất định,
  raise `QuestionInterpretationError` rõ ràng nếu LLM bịa cột không
  tồn tại — KHÁC với `O1.enrich()` (module tùy chọn, fail êm), O2 nằm
  trên đường găng nên fail LOUD có chủ đích.
- **Mới:** endpoint demo `/interpret` (chạy O1+O2 nối tiếp), theo đúng
  mẫu đã lập ở Tuần 1 với `/profile`.
- **Đã kiểm chứng:** ví dụ chạy xuyên suốt đồ án ("phân tích xu hướng
  12 tháng + chi nhánh giảm mạnh nhất") cho ra đúng khoảng thời gian
  2025-09 → 2026-08 khớp 100% với dữ liệu thật trong `doanh_thu.csv`.

### CHANGELOG Tuần 2

- **Fix:** cột số nhỏ (ví dụ điểm đánh giá 1-5) từng bị `pd.to_datetime()`
  nhận nhầm thành cột thời gian → giới hạn chỉ thử ép kiểu ngày trên
  cột dạng chuỗi.
- **Fix:** cột văn bản tự do / định danh (mỗi dòng gần như một giá trị
  khác nhau) từng bị nhận nhầm là cột nhóm khi dùng ngưỡng tuyệt đối
  `nunique() <= 20` trên tập dữ liệu nhỏ → đổi sang ngưỡng theo TỶ LỆ
  (`nunique / row_count <= 0.5`).
- **Mới:** `data_profiler.enrich()` — Stage 2 (tùy chọn, gọi Claude
  API một lần duy nhất để sinh mô tả dataset + mô tả/kiểu ngữ nghĩa
  từng cột). Thiết kế fail-safe: lỗi LLM không làm sập pipeline.

### Review & fix sau khi tự kiểm tra kỹ code Tuần 1-2

- **Fix (thiết kế):** `DataProfile` thiếu khoảng thời gian thực tế của
  cột thời gian → thêm `time_min`/`time_max`, tính bằng hàm
  `_time_range()`. Cần thiết để O2 (Tuần 3) giải nghĩa các biểu thức
  thời gian tương đối (vd: "12 tháng gần nhất") mà không phải đọc lại
  DataFrame thô.
- **Fix (logging):** `enrich()` trước đây nuốt lỗi hoàn toàn im lặng
  dù docstring nói "log cảnh báo" — nay đã thêm `logging.warning(...,
  exc_info=True)` thật, đã verify log xuất hiện đúng khi LLM lỗi.
- **Fix (robustness):** nếu LLM trả JSON hợp lệ nhưng sai cấu trúc
  (ví dụ một list thay vì object), `raw.get(...)` sẽ raise
  `AttributeError` không nằm trong except cũ → vẫn crash dù đã có
  try/except. Đã thêm kiểm tra `isinstance(raw, dict)` + bắt thêm
  `AttributeError`, có test khóa lại hành vi đúng.
- **Fix (API robustness):** endpoint `/profile` giờ bắt lỗi CSV không
  hợp lệ/rỗng, trả `HTTPException(400, ...)` gọn thay vì để lộ
  traceback thô ra client.
- **Fix (hạ tầng):** thêm `CORSMiddleware` vào FastAPI app từ sớm, để
  không bị chặn khi tích hợp frontend React ở Tuần 7.
- **Fix (phụ thuộc):** chặn trên `pandas<5.0` trong `requirements.txt`
  — chính thay đổi dtype trong pandas 3.0 là nguyên nhân 2 bug ở trên,
  nên cần kiểm soát version chặt hơn `>=` đơn thuần.
- **Fix (tài liệu):** sửa tham chiếu file không tồn tại trong
  `main.py`, cập nhật docstring lỗi thời trong test (nói "3 bộ dữ
  liệu" trong khi đã có 5 bộ).

### Cố tình CHƯA sửa (ghi nhận, để dành cho tuần sau)

- `AnalysisTask.type`/`find`, `ChartSpec.chart_type` vẫn là `str` tự
  do thay vì `Literal[...]` — sẽ chốt giá trị hợp lệ khi cài đặt thật
  O2/O4 (Tuần 3, 5) để tránh khóa cứng quá sớm.
- Ngưỡng `nunique <= 50` trong `_guess_group_columns` là số cứng, chưa
  test ở quy mô dữ liệu thật lớn (>50 danh mục) — theo dõi khi có bộ
  dữ liệu lớn hơn.

## Cấu trúc thư mục

```
ai-agent-bi/
├── README.md
├── requirements.txt
├── pytest.ini
├── docs/
│   ├── SRS.md                 # Đặc tả yêu cầu rút gọn
│   └── ARCHITECTURE.md        # Kiến trúc hệ thống chi tiết
├── data/samples/               # Bộ dữ liệu mẫu để phát triển & test (5 bộ)
│   ├── doanh_thu.csv
│   ├── ban_hang_san_pham.csv
│   ├── chi_phi_van_hanh.csv
│   ├── danh_gia_khach_hang.csv  # edge-case: cột văn bản tự do
│   └── ton_kho.csv              # edge-case: giá trị thiếu
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app (CORS, xử lý lỗi upload)
│   │   ├── schemas.py          # Hợp đồng dữ liệu (I/O) giữa các module
│   │   ├── llm_client.py       # LLMClient/ClaudeClient dùng chung (từ Tuần 3)
│   │   └── modules/
│   │       ├── data_profiler.py         # O1 - đã cài đặt (Stage 1+2)
│   │       ├── question_interpreter.py  # O2 - đã cài đặt
│   │       ├── code_generator.py        # O3a - stub
│   │       ├── sandbox_executor.py      # O3b - stub
│   │       ├── chart_generator.py       # O4 - stub
│   │       └── insight_generator.py     # O5 - stub
│   └── tests/
│       ├── test_data_profiler.py       # O1 Stage 1 (7 kịch bản)
│       ├── test_enrichment.py          # O1 Stage 2 (5 kịch bản)
│       └── test_question_interpreter.py # O2 (10 kịch bản)
└── .github/workflows/ci.yml
```

## Khởi động nhanh

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# chạy test
pytest -v

# chạy server (khi đã có FastAPI)
uvicorn backend.app.main:app --reload
```

## Tài liệu tham khảo

Dibia, V. (2023). LIDA: A Tool for Automatic Generation of Grammar-Agnostic
Visualizations and Infographics using Large Language Models. *Proceedings
of the 61st Annual Meeting of the Association for Computational
Linguistics: System Demonstrations*, 113–126.
