# AI Agent Phân Tích & Trực Quan Hóa Dữ Liệu Kinh Doanh

Đồ án tốt nghiệp — AI Agent cho phép người dùng tải lên file CSV dữ liệu
kinh doanh, đặt câu hỏi bằng ngôn ngữ tự nhiên, và nhận lại biểu đồ + số
liệu + nhận xét (insight) tự động.

Kiến trúc pipeline lấy cảm hứng từ LIDA (Dibia, 2023) — xem
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) để biết cách 5 module được
mở rộng từ ý tưởng SUMMARIZER / GOAL EXPLORER / VISGENERATOR của LIDA.

## Trạng thái (Tuần 2/8)

- [x] Nghiên cứu tài liệu, xác định yêu cầu (`docs/SRS.md`)
- [x] Thiết kế kiến trúc tổng thể (`docs/ARCHITECTURE.md`)
- [x] Khởi tạo repo + CI cơ bản
- [x] Bộ dữ liệu mẫu — **5 bộ** (`data/samples/`), gồm 2 bộ edge-case
- [x] Module O1 — Data Profiler Stage 1 (rule-based, đã sửa 2 bug phát
      hiện khi test với dữ liệu edge-case — xem CHANGELOG bên dưới)
- [x] Module O1 — Data Profiler Stage 2 (làm giàu ngữ nghĩa bằng LLM,
      tùy chọn, có test với client giả lập)
- [ ] Module O2 — Question Interpreter (Tuần 3)
- [ ] Module O3 — Code Generator + Sandbox Executor (Tuần 4)
- [ ] Module O4 — Chart Generator (Tuần 5)
- [ ] Module O5 — Insight Generator (Tuần 6)

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
│   │   └── modules/
│   │       ├── data_profiler.py         # O1 - đã cài đặt (Stage 1+2)
│   │       ├── question_interpreter.py  # O2 - stub
│   │       ├── code_generator.py        # O3a - stub
│   │       ├── sandbox_executor.py      # O3b - stub
│   │       ├── chart_generator.py       # O4 - stub
│   │       └── insight_generator.py     # O5 - stub
│   └── tests/
│       ├── test_data_profiler.py   # Stage 1 (7 kịch bản)
│       └── test_enrichment.py      # Stage 2 (5 kịch bản)
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
