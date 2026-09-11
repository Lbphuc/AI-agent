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
- **Mới:** 2 bộ dữ liệu edge-case (`danh_gia_khach_hang.csv` — có cột
  văn bản tự do; `ton_kho.csv` — có giá trị thiếu) để tổng số bộ dữ
  liệu mẫu đạt 5, đúng mục tiêu Tuần 2 trong kế hoạch 8 tuần.

## Cấu trúc thư mục

```
ai-agent-bi/
├── README.md
├── requirements.txt
├── pytest.ini
├── docs/
│   ├── SRS.md                 # Đặc tả yêu cầu rút gọn
│   └── ARCHITECTURE.md        # Kiến trúc hệ thống chi tiết
├── data/samples/               # Bộ dữ liệu mẫu để phát triển & test
│   ├── doanh_thu.csv
│   ├── ban_hang_san_pham.csv
│   └── chi_phi_van_hanh.csv
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── schemas.py          # Hợp đồng dữ liệu (I/O) giữa các module
│   │   └── modules/
│   │       ├── data_profiler.py         # O1 - đã cài đặt
│   │       ├── question_interpreter.py  # O2 - stub
│   │       ├── code_generator.py        # O3a - stub
│   │       ├── sandbox_executor.py      # O3b - stub
│   │       ├── chart_generator.py       # O4 - stub
│   │       └── insight_generator.py     # O5 - stub
│   └── tests/
│       └── test_data_profiler.py
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
