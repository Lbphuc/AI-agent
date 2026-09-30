<center>

# ĐỀ XUẤT DỰ ÁN (PROJECT PROPOSAL)

## AI Agent hỗ trợ phân tích, trực quan hóa và sinh thông tin chuyên sâu từ dữ liệu kinh doanh
</center>
---

## 1. Bối cảnh và động lực

Các doanh nghiệp vừa và nhỏ thường lưu trữ dữ liệu kinh doanh (doanh thu, chi nhánh, sản phẩm...) dưới dạng file bảng tính (CSV/Excel) nhưng thiếu nhân sự chuyên môn phân tích dữ liệu (data analyst) để khai thác insight. Việc tạo ra một biểu đồ đúng, đúng ngữ cảnh và kèm nhận xét có ý nghĩa vẫn đòi hỏi kỹ năng về thống kê, công cụ trực quan hóa và tư duy phân tích.

Nghiên cứu LIDA (Dibia, 2023) đã chứng minh rằng có thể dùng mô hình ngôn ngữ lớn (LLM) để tự động hóa quy trình sinh trực quan hóa dữ liệu thông qua một pipeline nhiều giai đoạn: tóm tắt dữ liệu, sinh mục tiêu phân tích, sinh mã trực quan hóa và sinh đồ họa có phong cách. Tuy nhiên, LIDA tập trung vào việc **sinh biểu đồ đẹp và đa dạng ngữ pháp trực quan hóa**, chứ chưa giải quyết bài toán **trả lời trực tiếp một câu hỏi kinh doanh cụ thể bằng cả số liệu tính toán lẫn nhận xét ngôn ngữ tự nhiên** — đây chính là khoảng trống mà dự án này hướng tới.

## 2. Phát biểu bài toán

Xây dựng một hệ thống web cho phép người dùng:
1. Tải lên một file dữ liệu kinh doanh dạng CSV (ví dụ: `doanh_thu.csv` gồm các cột Tháng, Chi nhánh, Doanh thu).
2. Đặt một câu hỏi bằng ngôn ngữ tự nhiên, ví dụ: *"Phân tích xu hướng doanh thu 12 tháng gần nhất và cho biết chi nhánh nào giảm mạnh nhất."*
3. Nhận lại một kết quả tổng hợp gồm:
   - Biểu đồ doanh thu theo tháng (xu hướng theo thời gian).
   - Biểu đồ so sánh doanh thu giữa các chi nhánh.
   - Bảng/chỉ số mức tăng/giảm theo từng chi nhánh.
   - Đoạn nhận xét (insight) bằng ngôn ngữ tự nhiên, tóm tắt phát hiện chính và trả lời trực tiếp câu hỏi.

## 3. Mục tiêu dự án

### 3.1. Mục tiêu tổng quát
Thiết kế và xây dựng một AI Agent có khả năng tự động hóa toàn bộ quy trình: **hiểu dữ liệu → hiểu câu hỏi → tính toán → trực quan hóa → diễn giải**, dựa trên kiến trúc pipeline nhiều giai đoạn tương tự LIDA nhưng mở rộng thêm khả năng suy luận số liệu và sinh nhận xét.

### 3.2. Mục tiêu cụ thể
- (O1) Xây dựng module tóm tắt dữ liệu tự động từ file CSV (schema, thống kê, kiểu dữ liệu, nhận diện cột thời gian/cột định danh).
- (O2) Xây dựng module hiểu câu hỏi, chuyển câu hỏi tự do của người dùng thành các mục tiêu phân tích có cấu trúc.
- (O3) Xây dựng module sinh và thực thi mã phân tích (pandas) một cách an toàn (sandbox), có cơ chế phát hiện và tự sửa lỗi.
- (O4) Xây dựng module sinh biểu đồ trực quan tương ứng với từng loại phân tích (xu hướng, so sánh).
- (O5) Xây dựng module sinh nhận xét bằng ngôn ngữ tự nhiên, bám sát số liệu đã tính toán được (hạn chế hallucination).
- (O6) Xây dựng giao diện web hoàn chỉnh: tải file, đặt câu hỏi, hiển thị kết quả tổng hợp.
- (O7) Xây dựng bộ chỉ số đánh giá (dựa trên VER/SEVQ của LIDA, mở rộng thêm chỉ số chính xác số liệu) và tiến hành đánh giá hệ thống trên nhiều bộ dữ liệu, nhiều câu hỏi mẫu.

## 4. Phạm vi dự án

### Trong phạm vi
- Dữ liệu đầu vào: file CSV có cấu trúc bảng (dữ liệu dạng long/wide phổ biến trong báo cáo kinh doanh: thời gian, danh mục, giá trị số).
- Các dạng câu hỏi hỗ trợ: xu hướng theo thời gian, so sánh giữa các nhóm/danh mục, tính tăng/giảm (growth rate), tìm giá trị lớn nhất/nhỏ nhất.
- Biểu đồ: line chart (xu hướng), bar chart (so sánh) — 2 loại biểu đồ chính, đủ đáp ứng ví dụ bài toán.
- Ngôn ngữ giao tiếp: tiếng Việt.

### Ngoài phạm vi (giới hạn của dự án trong 8 tuần)
- Không hỗ trợ nhiều file/nhiều nguồn dữ liệu cùng lúc (join dữ liệu đa bảng).
- Không sinh infographic có phong cách nghệ thuật (khác với INFOGRAPHER của LIDA) — tập trung vào biểu đồ chuẩn, dễ đọc cho mục đích kinh doanh.
- Không triển khai đa người dùng/phân quyền (multi-tenant), chỉ demo single-user.
- Chưa tối ưu cho dữ liệu cực lớn (>1 triệu dòng).

## 5. Kiến trúc hệ thống đề xuất

Hệ thống gồm 6 module xử lý chính, kế thừa tư tưởng pipeline đa giai đoạn của LIDA (Dibia, 2023) nhưng được thiết kế lại để phù hợp bài toán trả lời câu hỏi kinh doanh:

| # | Module | Vai trò | Tương ứng trong LIDA |
|---|---|---|---|
| 1 | **Data Profiler** (Bộ tóm tắt dữ liệu) | Trích xuất schema, kiểu dữ liệu, thống kê, nhận diện cột thời gian/định danh | SUMMARIZER |
| 2 | **Question Interpreter** (Bộ hiểu câu hỏi) | Phân tích câu hỏi tự do → mục tiêu phân tích có cấu trúc (JSON) | Mở rộng từ GOAL EXPLORER (đảo chiều: từ câu hỏi người dùng thay vì tự sinh mục tiêu) |
| 3 | **Analysis Code Generator** | Sinh mã pandas để tính toán số liệu cần thiết (tổng theo tháng, tăng trưởng theo chi nhánh...) | Mở rộng từ VISGENERATOR (code generator) |
| 4 | **Sandbox Executor** | Thực thi mã an toàn, phát hiện lỗi, tự sinh lại nếu lỗi | VISGENERATOR (code executor) |
| 5 | **Chart Generator** | Sinh đặc tả biểu đồ (line/bar) từ kết quả tính toán | VISGENERATOR (phần trực quan hóa) |
| 6 | **Insight Generator** | Tổng hợp số liệu đã tính → viết nhận xét ngôn ngữ tự nhiên | Không có trong LIDA gốc — module mới, thay thế vai trò truyền tải giá trị của INFOGRAPHER nhưng bằng văn bản thay vì hình ảnh phong cách |

**Nguyên tắc thiết kế kế thừa từ LIDA:**
- Tách biệt bước **sinh mã (LLM)** và bước **thực thi mã (runtime)** — theo tinh thần Program-Aided Language Models mà LIDA áp dụng — giúp kết quả tính toán chính xác thay vì để LLM tự nhẩm số liệu.
- Dùng kỹ thuật **fill-in-the-middle** với code scaffold cho module sinh mã phân tích, giới hạn phạm vi code LLM có thể sinh ra để tăng an toàn khi thực thi.
- Cơ chế **lọc lỗi nhiều tầng** (loại bỏ ứng viên lỗi biên dịch, tự sửa khi thất bại) tương tự code executor của LIDA.
- Module Insight Generator lấy **cảm hứng từ SEVQ** của LIDA — tự đánh giá chất lượng đầu ra trước khi trả về người dùng.

## 6. Công nghệ dự kiến

| Thành phần | Công nghệ |
|---|---|
| Backend | Python, FastAPI |
| Xử lý/tính toán dữ liệu | pandas |
| LLM | Claude API (Anthropic) |
| Biểu đồ | Plotly hoặc Recharts (backend trả JSON spec, frontend render) |
| Sandbox thực thi code | Subprocess giới hạn quyền / container hóa (Docker) |
| Frontend | React |
| Lưu trữ tạm | Bộ nhớ phiên (session) hoặc SQLite cho demo |

## 7. Kế hoạch thực hiện 8 tuần

| Tuần | Nội dung công việc | Đầu ra (deliverable) |
|---|---|---|
| **Tuần 1** | Nghiên cứu tài liệu (LIDA và các công trình liên quan), xác định yêu cầu chi tiết, thiết kế kiến trúc tổng thể, chuẩn bị môi trường phát triển (repo, CI cơ bản), thu thập/tạo bộ dữ liệu mẫu (doanh_thu.csv và các file thử nghiệm khác) | Tài liệu đặc tả yêu cầu (SRS rút gọn), sơ đồ kiến trúc hệ thống, repo khởi tạo |
| **Tuần 2** | Xây dựng module **Data Profiler**: trích xuất schema, thống kê, nhận diện cột thời gian/định danh bằng pandas; viết prompt làm giàu tóm tắt bằng LLM (tùy chọn) | Module Data Profiler hoạt động độc lập, có unit test với 3-5 bộ dữ liệu mẫu |
| **Tuần 3** | Xây dựng module **Question Interpreter**: thiết kế prompt few-shot, định nghĩa schema JSON cho mục tiêu phân tích, xử lý các loại câu hỏi (xu hướng, so sánh, tăng/giảm) | Module Question Interpreter, tập câu hỏi thử nghiệm và kết quả phân rã tương ứng |
| **Tuần 4** | Xây dựng **Analysis Code Generator** + **Sandbox Executor**: thiết kế code scaffold pandas, cơ chế fill-in-the-middle, thực thi an toàn, xử lý lỗi và tự sinh lại | Module sinh & thực thi mã phân tích, đo thử tỷ lệ lỗi ban đầu (AER) |
| **Tuần 5** | Xây dựng **Chart Generator**: chuyển kết quả tính toán thành đặc tả biểu đồ line/bar; tích hợp thư viện biểu đồ ở frontend | Module sinh biểu đồ, demo hiển thị biểu đồ từ dữ liệu mẫu |
| **Tuần 6** | Xây dựng **Insight Generator**: thiết kế prompt sinh nhận xét bám sát số liệu đã tính, cơ chế tự đánh giá chất lượng nhận xét (tương tự SEVQ); ghép nối toàn bộ pipeline 6 module | Pipeline end-to-end chạy được từ upload CSV đến trả kết quả đầy đủ |
| **Tuần 7** | Xây dựng giao diện web hoàn chỉnh (upload, chat hỏi-đáp, hiển thị biểu đồ + nhận xét); kiểm thử tích hợp; sửa lỗi UX | Website demo hoàn chỉnh, có thể thao tác đầu-cuối |
| **Tuần 8** | Đánh giá hệ thống trên nhiều bộ dữ liệu và câu hỏi mẫu theo bộ chỉ số đã định nghĩa (mục 8); tối ưu prompt dựa trên kết quả đánh giá; hoàn thiện báo cáo đồ án, chuẩn bị slide/demo bảo vệ | Báo cáo đánh giá kèm số liệu, tài liệu đồ án hoàn chỉnh, slide bảo vệ, video/demo trực tiếp |

**Ghi chú tiến độ:** Tuần 1–6 tập trung xây dựng từng module theo đúng thứ tự luồng dữ liệu (data-first: phải hiểu dữ liệu trước khi hiểu câu hỏi, phải tính toán xong mới vẽ biểu đồ và sinh nhận xét) — điều này giúp mỗi module có thể kiểm thử độc lập trước khi ghép nối, giảm rủi ro debug toàn hệ thống ở giai đoạn cuối.

## 8. Kế hoạch đánh giá (Evaluation Plan)

Kế thừa và mở rộng 2 chỉ số VER và SEVQ mà LIDA đề xuất (Dibia, 2023):

| Chỉ số | Mô tả | Cách đo |
|---|---|---|
| **Analysis Error Rate (AER)** | Tỷ lệ câu hỏi mà mã phân tích không thực thi được (tương đương VER của LIDA) | Số lần lỗi biên dịch/thực thi ÷ tổng số lần thử, trên bộ câu hỏi thử nghiệm |
| **Numeric Accuracy** | Độ chính xác số liệu trong nhận xét so với số liệu thực tính toán được | Đối chiếu tự động các con số LLM nêu trong nhận xét với kết quả pandas |
| **Insight Relevance** | Mức độ nhận xét trả lời đúng trọng tâm câu hỏi | Dùng LLM tự chấm điểm 1–10 kèm lý do (tương tự SEVQ), có đối chiếu ngẫu nhiên bằng đánh giá thủ công |
| **Latency** | Thời gian phản hồi trung bình từ lúc gửi câu hỏi đến khi trả kết quả đầy đủ | Đo thời gian thực thi từng module và tổng pipeline |

**Bộ dữ liệu đánh giá dự kiến:** 5–8 bộ CSV mô phỏng dữ liệu kinh doanh (doanh thu theo tháng/chi nhánh, số lượng đơn hàng theo sản phẩm...), mỗi bộ kèm 3–5 câu hỏi mẫu thuộc các dạng khác nhau (xu hướng, so sánh, tăng/giảm).

## 9. Rủi ro và biện pháp giảm thiểu

| Rủi ro | Mức độ | Biện pháp giảm thiểu |
|---|---|---|
| LLM sinh mã phân tích sai hoặc không thực thi được | Cao | Áp dụng code scaffold + fill-in-the-middle để giới hạn phạm vi sinh mã; cơ chế tự sửa lỗi nhiều lượt |
| LLM "bịa" số liệu trong phần nhận xét (hallucination) | Cao | Tách bạch bước tính toán (pandas, kết quả xác định) và bước diễn giải (LLM chỉ được đọc số liệu đã tính, không tự suy luận số) |
| Chi phí/độ trễ gọi API LLM nhiều lần trong 1 pipeline | Trung bình | Gộp một số bước prompt khi có thể; cache kết quả tóm tắt dữ liệu; giới hạn số lần retry |
| Bảo mật khi thực thi mã do LLM sinh ra | Cao | Chạy trong sandbox cô lập (container/subprocess giới hạn quyền), không cho phép truy cập file hệ thống hoặc mạng |
| Câu hỏi người dùng mơ hồ, không đủ thông tin | Trung bình | Định nghĩa giá trị mặc định hợp lý (ví dụ mặc định "12 tháng gần nhất" nếu không rõ khoảng thời gian) và có thể hỏi lại người dùng khi cần |
| Thời gian 8 tuần eo hẹp so với khối lượng công việc | Trung bình | Ưu tiên 2 loại biểu đồ và 3 dạng câu hỏi chính (mục 4 — Phạm vi), để lại các mở rộng cho phần "hướng phát triển" |

## 10. Kết quả kỳ vọng

- Một hệ thống web demo hoàn chỉnh, cho phép tải file CSV, đặt câu hỏi kinh doanh bằng tiếng Việt, và nhận về biểu đồ + số liệu + nhận xét trong một lần tương tác.
- Bộ số liệu đánh giá định lượng (AER, Numeric Accuracy, Insight Relevance, Latency) trên nhiều bộ dữ liệu/câu hỏi thử nghiệm.
- Báo cáo đồ án trình bày đầy đủ: cơ sở lý thuyết (dựa trên LIDA), thiết kế kiến trúc, chi tiết cài đặt từng module, kết quả đánh giá, hạn chế và hướng phát triển.

## 11. Hướng phát triển sau đồ án

- Hỗ trợ join nhiều bảng dữ liệu, nhiều nguồn (database, Excel nhiều sheet).
- Mở rộng thêm các dạng câu hỏi phức tạp hơn (dự báo, phân tích tương quan giữa nhiều chỉ số).
- Bổ sung khả năng sinh infographic có phong cách (như module INFOGRAPHER của LIDA) cho báo cáo trình bày.
- Tối ưu chi phí/độ trễ bằng cách fine-tune mô hình nhỏ hơn cho riêng tác vụ sinh mã phân tích, theo đúng hướng mà LIDA đề xuất trong phần hạn chế về triển khai (Dibia, 2023).

---

## Tài liệu tham khảo

Dibia, V. (2023). LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics: System Demonstrations*, 113–126.
