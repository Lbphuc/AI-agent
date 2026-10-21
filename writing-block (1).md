# PROPOSAL
## Hoàn thiện logic phân tích, tính nhất quán dữ liệu và UI/UX cho AI Agent BI

**Dự án:** AI Agent BI – AI-Agent phân tích dữ liệu trong kinh doanh

**Phiên bản:** Đề xuất cải tiến tiếp theo sau đánh giá kết quả thực nghiệm

**Phạm vi:** Tổng quan, tìm nguyên nhân, dự báo, gợi ý chiến lược, chế độ tự động, trực quan hóa và xuất báo cáo.

**Môi trường:** Local phục vụ đồ án.

**Nguyên tắc thực hiện:** Sửa logic nghiệp vụ trước, chuẩn hóa dữ liệu và hợp đồng kết quả, sau đó mới hoàn thiện biểu đồ và UI/UX. Không viết lại toàn bộ hệ thống khi chưa cần thiết, không bổ sung tính năng ngoài phạm vi và không sửa riêng lẻ các component khi vấn đề xuất phát từ dữ liệu hoặc logic dùng chung.

---

# 1. Bối cảnh và vấn đề hiện tại

Sau lần cải tiến gần nhất, giao diện AI Agent BI đã có sự thống nhất hơn về màu sắc, bố cục thẻ và cách phân biệt dữ liệu thực tế với dự báo. Các phương pháp đều có phần nhận xét, biểu đồ và thông tin bổ sung.

Tuy nhiên, kết quả kiểm tra qua các câu hỏi thực tế cho thấy hệ thống vẫn còn một số vấn đề quan trọng.

### 1.1. Mục tiêu câu hỏi chưa được bảo toàn xuyên suốt quá trình phân tích

Ví dụ, người dùng hỏi:

“Yếu tố nào đóng góp lớn nhất vào thay đổi Sales?”

Nhưng hệ thống lại diễn giải thành:

“Tìm category tăng mạnh nhất theo Sales.”

Hai câu hỏi này có ý nghĩa khác nhau. Một câu hỏi về mức đóng góp vào thay đổi tổng thể; câu còn lại về nhóm tăng trưởng.

Tương tự, câu hỏi “Nên ưu tiên Ship Mode nào để cải thiện Sales?” có thể bị xử lý thành nhiệm vụ so sánh doanh thu, mà chưa làm rõ mục tiêu lựa chọn chiến lược.

Điều này cho thấy cần kiểm tra lại toàn bộ luồng từ hiểu câu hỏi, lập kế hoạch phân tích, thực hiện phép tính đến diễn giải kết quả.

### 1.2. Số liệu giữa nhận xét AI và biểu đồ chưa nhất quán

Trong kết quả Diagnostic, phần nhận xét ban đầu nói về mức giảm của Furniture, trong khi phần chẩn đoán chi tiết phía dưới thể hiện tăng trưởng tổng Sales và đóng góp dương của các Category.

Các kết quả có thể sử dụng thước đo hoặc phạm vi thời gian khác nhau, nhưng giao diện chưa giải thích rõ. Nếu chúng thực sự mâu thuẫn, cần sửa logic tạo kết luận thay vì chỉ thêm cảnh báo.

### 1.3. Một số biểu đồ chưa phản ánh đúng hoặc chưa làm rõ ý nghĩa đại lượng

Các trường hợp cần kiểm tra gồm:

- Biểu đồ có tiêu đề “Category tăng mạnh nhất” nhưng các giá trị được hiển thị đều âm.
- Biểu đồ “Biến động Sales so với kỳ trước (%)” nhưng chú giải ghi `Sales` và trục có giá trị ở quy mô hàng chục nghìn.
- Biểu đồ đóng góp vào thay đổi Sales có trục xoay quanh vùng giá trị âm hẹp, không thể hiện rõ mốc 0.
- Một số biểu đồ phụ được sinh ra dù chưa chứng minh được chúng cần thiết để trả lời câu hỏi.

Đây có thể là vấn đề ở phép tính, cấu hình biểu đồ hoặc metadata. Cần xác minh nguyên nhân trước khi sửa.

### 1.4. Khoảng thời gian chưa được giải thích đồng nhất

Người dùng có thể chọn phạm vi năm 2017, nhưng biểu đồ dự báo lại sử dụng nhiều năm lịch sử và kéo dài đến các kỳ đầu năm 2018.

Việc sử dụng nhiều năm lịch sử có thể hợp lý nếu đó là dữ liệu dùng để huấn luyện mô hình. Vấn đề là giao diện chưa phân biệt rõ phạm vi người dùng yêu cầu, phạm vi dữ liệu phân tích và phạm vi huấn luyện.

### 1.5. Khuyến nghị chiến lược chưa giải thích đầy đủ tiêu chí ưu tiên

Standard Class có thể dẫn đầu về tổng doanh thu, trong khi First Class có thể tăng trưởng nhanh hơn. Việc lựa chọn First Class làm trọng tâm không nhất thiết sai, nhưng phải giải thích mục tiêu ưu tiên là tăng trưởng, quy mô doanh thu hay lợi nhuận.

Khi dữ liệu chưa có chi phí, biên lợi nhuận và các yếu tố thị trường, mức ưu tiên cũng không nên được trình bày như một quyết định đã chắc chắn đúng.

### 1.6. Bố cục biểu đồ chưa thích ứng đủ tốt với không gian hiển thị

Một số thẻ biểu đồ quá hẹp, tiêu đề bị xuống dòng và nhãn khó đọc. Vấn đề này đặc biệt rõ khi nhiều biểu đồ được đặt trên cùng một hàng.

Cần chuẩn hóa hệ thống layout chung thay vì chỉ chỉnh kích thước riêng từng biểu đồ.

---

# 2. Mục tiêu của lần cải tiến này

## 2.1. Mục tiêu tổng quát

Hoàn thiện AI Agent BI thành một hệ thống trong đó mục tiêu người dùng, kết quả tính toán, nhận định AI, biểu đồ và khuyến nghị thống nhất với nhau.

Việc nâng cấp cần xử lý đồng thời các lớp logic và trình bày, nhưng phải theo đúng thứ tự phụ thuộc để tránh phát sinh sửa chồng chéo.

## 2.2. Mục tiêu cụ thể

1. Bảo toàn đúng mục tiêu câu hỏi trong toàn bộ pipeline phân tích.
2. Chuẩn hóa định nghĩa KPI, phép tính và phạm vi thời gian.
3. Loại bỏ mâu thuẫn giữa kết quả tính toán, nhận xét và biểu đồ.
4. Hoàn thiện logic của cả bốn phương pháp phân tích.
5. Chuẩn hóa cách lựa chọn, cấu hình và giải thích biểu đồ.
6. Tăng chất lượng các khuyến nghị bằng bằng chứng và điều kiện áp dụng rõ ràng.
7. Chuẩn hóa layout, typography, định dạng số và trạng thái giao diện.
8. Bảo đảm chế độ tự động lựa chọn và điều phối phương pháp đúng.
9. Đồng bộ nội dung trên giao diện và báo cáo xuất ra.
10. Thiết lập bộ kiểm thử đầu-cuối để kết quả có thể tái lập và đánh giá được.

# 3. Nguyên tắc kiến trúc và thực hiện

Tất cả hạng mục trong proposal phải tuân thủ các nguyên tắc sau.

## 3.1. Một định nghĩa cho mỗi KPI

Các phương pháp không được tự định nghĩa lại cách tính cùng một chỉ số.

Ví dụ, nếu Sales được xác định là tổng doanh thu trong kỳ, thì việc tổng quan, phân tích đóng góp, xây dựng xu hướng và tạo khuyến nghị phải sử dụng cùng định nghĩa, trừ khi một phương pháp có mục tiêu đo lường khác được nêu rõ.

## 3.2. Một nguồn kết quả có thể kiểm chứng

Mỗi kết quả định lượng quan trọng phải có nguồn dữ liệu, phép tính, đơn vị và khoảng thời gian tương ứng.

Nhận xét AI và biểu đồ chỉ được lấy từ kết quả phân tích đã chuẩn hóa. Không để LLM tự tạo lại số liệu độc lập với phần tính toán.

## 3.3. Tách biệt mục tiêu, tính toán và trình bày

- Lớp hiểu câu hỏi xác định người dùng đang muốn biết điều gì.
- Lớp phân tích thực hiện phép tính đúng với mục tiêu.
- Lớp kiểm chứng đối chiếu kết quả.
- Lớp diễn giải tạo nhận xét và khuyến nghị dựa trên kết quả đã xác nhận.
- Lớp trình bày lựa chọn cách hiển thị phù hợp.

Không dùng thay đổi CSS để xử lý vấn đề phát sinh từ phép tính sai hoặc mục tiêu phân tích sai.

## 3.4. Tái sử dụng kiến trúc hiện có

Ưu tiên sửa và chuẩn hóa các module hiện tại. Chỉ tạo module mới khi trách nhiệm rõ ràng và giúp giảm logic trùng lặp.

Không thay toàn bộ thư viện biểu đồ hoặc viết lại frontend nếu các component hiện tại vẫn đáp ứng được yêu cầu.

## 3.5. Mọi thay đổi phải có kiểm thử hồi quy

Khi sửa một logic được dùng chung, phải chạy lại các phương pháp có liên quan.

Không xem một hạng mục đã hoàn thành chỉ vì một câu hỏi mẫu cho kết quả đẹp hơn.

---

# 4. Hạng mục 1 — Chuẩn hóa hiểu câu hỏi và lập kế hoạch phân tích

**Mức ưu tiên: P0 — Thực hiện đầu tiên.**

## 4.1. Mục tiêu

Bảo đảm hệ thống hiểu đúng ý định kinh doanh và giữ nguyên ý định đó từ lúc tiếp nhận câu hỏi cho đến khi trả kết quả.

## 4.2. Công việc

Rà soát `question_interpreter.py`, `perspective_planner.py`, `availability.py`, `analysis_runner.py` và các vị trí điều phối liên quan.

Chuẩn hóa cấu trúc Analysis Plan tối thiểu gồm:

- `objective`: mục tiêu phân tích.
- `metric`: KPI chính cần phân tích.
- `dimension`: nhóm hoặc chiều dữ liệu cần xem xét.
- `time_range`: khoảng thời gian yêu cầu.
- `comparison_period`: kỳ đối chiếu, nếu có.
- `forecast_horizon`: số kỳ tương lai, nếu có.
- `analysis_methods`: các phương pháp cần chạy.
- `expected_outputs`: kết quả dự kiến cần trả về.
- `constraints`: các điều kiện dữ liệu và giới hạn nghiệp vụ.

Các trường phải được xác thực trước khi thực hiện phân tích.

## 4.3. Quy tắc nghiệp vụ

Phải phân biệt ít nhất các mục tiêu sau:

- Tổng quan tình hình.
- So sánh giữa nhóm.
- Tìm nhóm tăng hoặc giảm mạnh nhất.
- Xác định đóng góp vào mức thay đổi tổng thể.
- Tìm các yếu tố liên quan hoặc điểm nghẽn.
- Dự báo giá trị tương lai.
- Đề xuất hành động hoặc chiến lược.

Không được coi những mục tiêu này là tương đương.

## 4.4. Kiểm thử bắt buộc

Sử dụng các câu hỏi thực tế:

1. “Yếu tố nào đóng góp lớn nhất vào thay đổi Sales?”
2. “Category nào tăng trưởng mạnh nhất?”
3. “Category nào làm giảm Sales nhiều nhất?”
4. “Ship Mode nào có doanh thu cao nhất?”
5. “Nên ưu tiên Ship Mode nào để cải thiện Sales?”
6. “Xu hướng Sales trong ba kỳ tiếp theo ra sao?”

Mỗi câu hỏi phải tạo ra mục tiêu, KPI và phạm vi phân tích phù hợp.

**Tiêu chí hoàn thành:** Không có trường hợp mục tiêu đóng góp bị đổi thành mục tiêu tăng trưởng hoặc mục tiêu khuyến nghị bị đổi thành so sánh đơn thuần mà không có giải thích hợp lý.

---

# 5. Hạng mục 2 — Chuẩn hóa Data Context, KPI và Fact

**Mức ưu tiên: P0.**

## 5.1. Mục tiêu

Thiết lập một nền tảng dữ liệu chung để mọi phương pháp sử dụng cùng một định nghĩa và có thể đối chiếu kết quả.

## 5.2. Công việc

Rà soát Data Profiler, logic chuẩn hóa dữ liệu, `analytics/series.py`, FactSheet và các hàm tính KPI.

Chuẩn hóa:

- Schema, kiểu dữ liệu và đơn vị.
- Định nghĩa KPI và chính sách tổng hợp.
- Tần suất dữ liệu và quy ước thời gian.
- Cách xử lý missing value và bản ghi trùng lặp.
- Cách tính mức thay đổi tuyệt đối, phần trăm thay đổi và đóng góp.
- Quy tắc tạo Fact ID và liên kết fact với nhận định.

Phân biệt rõ các khái niệm:

| Khái niệm | Ý nghĩa |
|---|---|
| Giá trị tuyệt đối | Giá trị KPI trong một kỳ |
| Mức thay đổi | Giá trị kỳ hiện tại trừ giá trị kỳ đối chiếu |
| Phần trăm thay đổi | Mức thay đổi so với giá trị kỳ gốc, khi phép tính có ý nghĩa |
| Đóng góp vào thay đổi tổng | Phần thay đổi của một nhóm trong mức thay đổi tổng thể |
| Tăng trưởng nội bộ | Mức thay đổi tương đối của chính nhóm đó |

Không sử dụng các khái niệm này thay thế cho nhau.

## 5.3. Quy tắc thời gian

Mỗi kết quả cần phân biệt:

- Khoảng thời gian người dùng yêu cầu.
- Khoảng thời gian thực tế được sử dụng trong phân tích.
- Khoảng thời gian dùng để huấn luyện hoặc kiểm định mô hình.
- Khoảng thời gian dự báo trong tương lai.

Khi các khoảng thời gian khác nhau, giao diện phải giải thích rõ lý do.

**Tiêu chí hoàn thành:** Các phương pháp dùng chung định nghĩa KPI, phạm vi và quy tắc xử lý dữ liệu; không còn những con số tương đương nhưng được tính theo các cách khác nhau mà không có lý do nghiệp vụ.

---

# 6. Hạng mục 3 — Khắc phục và hoàn thiện logic phương pháp Tổng quan

**Mức ưu tiên: P1.**

## 6.1. Mục tiêu

Tạo ra một bức tranh kinh doanh chính xác, dễ đọc và phù hợp với câu hỏi thay vì sinh nhiều biểu đồ ít giá trị.

## 6.2. Công việc

- Rà soát lựa chọn KPI và phép tính trong luồng phân tích mô tả.
- Kiểm tra phép tổng hợp doanh thu, số lượng, giá trị bình quân và tỷ lệ.
- Đồng bộ định dạng số, ngày tháng và đơn vị.
- Chỉ tạo những biểu đồ phục vụ câu hỏi.
- Ưu tiên KPI quan trọng, xu hướng, cơ cấu và so sánh theo nhóm.
- Chuẩn hóa phần nhận xét để không lặp lại số liệu mà không bổ sung thông tin.
- Xử lý trường hợp dữ liệu không đủ hoặc một KPI không phù hợp với bộ dữ liệu.

## 6.3. Tiêu chí hoàn thành

- Số liệu giữa nhận xét và biểu đồ khớp với kết quả tính toán.
- Biểu đồ thể hiện đúng đại lượng và đơn vị.
- Không tạo biểu đồ phần trăm từ chuỗi giá trị tuyệt đối hoặc ngược lại.
- Người dùng có thể nhận biết những điểm quan trọng mà không phải đọc toàn bộ văn bản giải thích.

---

# 7. Hạng mục 4 — Khắc phục và hoàn thiện logic phương pháp Tìm nguyên nhân

**Mức ưu tiên: P0/P1 — Ưu tiên ngay sau khi nền tảng dữ liệu ổn định.**

## 7.1. Mục tiêu

Đảm bảo phương pháp Diagnostic trả lời đúng câu hỏi về biến động, đóng góp và các yếu tố cần kiểm tra thêm.

## 7.2. Công việc

### A. Chuẩn hóa phân tích đóng góp

- Xác định giá trị tổng ở kỳ hiện tại và kỳ đối chiếu.
- Tính mức thay đổi của từng nhóm.
- Xác định đóng góp của từng nhóm vào mức thay đổi tổng.
- Xếp hạng nhóm theo đúng tiêu chí mà người dùng yêu cầu.
- Phân biệt nhóm có giá trị lớn nhất, nhóm tăng nhanh nhất và nhóm đóng góp nhiều nhất vào thay đổi tổng.

### B. Xử lý trường hợp đặc biệt

- Tổng thay đổi gần bằng 0.
- Giá trị kỳ gốc bằng 0 hoặc gần 0.
- Nhóm thiếu dữ liệu ở một kỳ.
- Nhóm mới xuất hiện hoặc biến mất.
- Các nhóm tăng/giảm bù trừ lẫn nhau.
- Giá trị ngoại lệ hoặc chuỗi thiếu kỳ.

Nếu chỉ số phần trăm không có ý nghĩa trong một trường hợp cụ thể, hệ thống cần thông báo thay vì trả về một tỷ lệ gây hiểu nhầm.

### C. Chuẩn hóa chẩn đoán sâu

- Chọn chiều phân tích đúng với câu hỏi.
- Chỉ thực hiện drill-down khi có giá trị bổ sung.
- Chỉ hiển thị tương quan khi có liên quan đến câu hỏi hoặc bổ sung bằng chứng cần thiết.
- Không diễn giải tương quan là quan hệ nhân quả.
- Mỗi nhận xét phải chỉ rõ kỳ, KPI, nhóm và giá trị liên quan.

### D. Sửa mâu thuẫn giữa nhận xét và biểu đồ

Các trường hợp hiện đang nêu mức giảm của Furniture trong một khu vực nhưng lại thể hiện tăng trưởng tổng thể ở khu vực khác phải được kiểm tra lại toàn bộ.

Nếu chúng dùng phạm vi hoặc thước đo khác nhau, ghi rõ sự khác biệt. Nếu thực sự mâu thuẫn, chỉ giữ kết luận sau khi đã đối chiếu lại dữ liệu.

## 7.3. Tiêu chí hoàn thành

Với câu hỏi về yếu tố đóng góp lớn nhất, hệ thống phải xác định đúng nhóm theo mức đóng góp, giải thích được phép tính và tạo biểu đồ khớp với kết quả đó.

---

# 8. Hạng mục 5 — Khắc phục và hoàn thiện logic Dự báo

**Mức ưu tiên: P1.**

## 8.1. Mục tiêu

Đảm bảo dự báo đúng phạm vi, đúng tần suất và thể hiện chính xác mức độ không chắc chắn.

## 8.2. Công việc

- Chuẩn hóa chuỗi thời gian trước khi chạy mô hình.
- Kiểm tra tính nhất quán giữa khoảng dữ liệu, tần suất và số kỳ dự báo.
- Đảm bảo dự báo theo nhóm sử dụng đúng chuỗi của nhóm.
- Rà soát baseline, backtest và quy trình lựa chọn mô hình.
- Sử dụng các chỉ số đánh giá phù hợp với đặc điểm dữ liệu.
- Kiểm tra trường hợp chuỗi ngắn, dữ liệu âm, dữ liệu bằng 0, ngoại lệ và mùa vụ.
- Kiểm tra cách xây dựng dải bất định.
- Phân biệt chất lượng dự báo đã quan sát trong backtest với độ chắc chắn về kết quả tương lai.

## 8.3. Tiêu chí hoàn thành

- Số kỳ dự báo đúng yêu cầu.
- Kỳ dự báo bắt đầu đúng sau dữ liệu lịch sử.
- Phạm vi huấn luyện và phạm vi hiển thị được ghi rõ.
- Nhận xét AI, biểu đồ và bảng dự báo cùng sử dụng một kết quả.
- Khi chất lượng mô hình thấp, cảnh báo được thể hiện rõ và không gợi ý quyết định như một cam kết chắc chắn.

---

# 9. Hạng mục 6 — Khắc phục và hoàn thiện logic Gợi ý chiến lược

**Mức ưu tiên: P1.**

## 9.1. Mục tiêu

Tạo ra các khuyến nghị có hành động cụ thể, có cơ sở, có điều kiện áp dụng và có tiêu chí đánh giá.

## 9.2. Công việc

### A. Chuẩn hóa cấu trúc khuyến nghị

Mỗi khuyến nghị cần gồm:

- Vấn đề hoặc cơ hội.
- Hành động cụ thể.
- Căn cứ định lượng.
- Các fact liên quan.
- Tiêu chí và lý do xếp mức ưu tiên.
- Các giả định hoặc điều kiện cần kiểm chứng.
- KPI theo dõi kết quả khi phù hợp.

### B. Chuẩn hóa logic ưu tiên

Không mặc định nhóm có tăng trưởng cao nhất là nhóm nên đầu tư nhiều nhất.

Cần phân biệt:

- Tối đa hóa quy mô doanh thu.
- Tăng tốc tăng trưởng.
- Cải thiện lợi nhuận.
- Giảm chi phí.
- Giảm rủi ro.
- Tối ưu nguồn lực.

Nếu người dùng không nêu mục tiêu cụ thể và dữ liệu không đủ để suy ra mục tiêu phù hợp, hệ thống phải nêu rõ tiêu chí đang sử dụng hoặc hỏi lại.

### C. Sử dụng bằng chứng từ các phương pháp khác

- Sử dụng tổng quan để xác định bối cảnh.
- Sử dụng chẩn đoán để xác định vấn đề hoặc nhóm đóng góp.
- Sử dụng dự báo khi lập kế hoạch tương lai là cần thiết.
- Không bắt buộc chạy mọi phương pháp nếu không đóng góp vào quyết định.

### D. Kiểm chứng

Rà soát `verify.py` để đối chiếu fact, số liệu, tên thực thể, đơn vị và nội dung khuyến nghị.

Đánh giá cả trường hợp khuyến nghị sai được chấp nhận và trường hợp khuyến nghị hợp lệ bị từ chối.

Phân biệt việc kiểm chứng số liệu với việc chứng minh một chiến lược sẽ tạo ra hiệu quả kinh doanh. Không tuyên bố loại bỏ hoàn toàn hallucination khi chưa có bằng chứng phù hợp.

## 9.3. Tiêu chí hoàn thành

Các khuyến nghị phải giải thích được tại sao hành động đó được ưu tiên và dữ liệu nào còn thiếu trước khi thực hiện. Mức ưu tiên phải phản ánh giới hạn của phân tích.

---

# 10. Hạng mục 7 — Chuẩn hóa biểu đồ và quy tắc trực quan hóa

**Mức ưu tiên: P1, thực hiện sau khi cấu trúc kết quả và logic phân tích đã ổn định.**

## 10.1. Chuẩn hóa Chart Specification

Mỗi biểu đồ phải khai báo rõ:

- Loại biểu đồ và mục tiêu sử dụng.
- Series và nguồn dữ liệu.
- Tiêu đề và mô tả.
- Tên trục và đơn vị.
- Quy tắc thời gian.
- Quy tắc định dạng số.
- Chú giải và tooltip.
- Mốc 0 khi phù hợp.
- Phạm vi và cảnh báo liên quan.

Frontend không tự suy luận đơn vị hoặc ý nghĩa nghiệp vụ từ tên biểu đồ.

## 10.2. Sửa các loại biểu đồ đang có vấn đề

### Biểu đồ đóng góp

Phân biệt mức thay đổi tuyệt đối với tỷ lệ thay đổi. Với mức đóng góp tuyệt đối, trục và mốc 0 phải phản ánh đúng cả giá trị dương lẫn âm.

### Biểu đồ phần trăm thay đổi

Tiêu đề, đơn vị và chú giải phải thể hiện tỷ lệ nếu đó là dữ liệu được tính. Xử lý rõ các trường hợp mẫu số bằng 0 hoặc gần 0.

### Biểu đồ xu hướng

Điều chỉnh số nhãn theo tần suất, độ dày dữ liệu và không gian hiển thị. Không tự làm mượt hoặc loại điểm chỉ để đẹp mắt.

### Biểu đồ tương quan

Hiển thị đơn vị hệ số tương quan rõ ràng, sắp xếp giá trị có ý nghĩa và giải thích ngắn rằng tương quan không chứng minh nhân quả.

### Biểu đồ tỷ trọng

Lựa chọn giữa biểu đồ thanh và biểu đồ tròn theo mục tiêu so sánh. Loại bỏ chú giải trùng lặp và làm rõ tổng thể đang được tính.

## 10.3. Một quy tắc chọn biểu đồ chung

Rà soát `chart_rules.py`, `chart_fitness.py` và các thành phần liên quan để đảm bảo:

- Loại biểu đồ được chọn theo mục tiêu và hình dạng dữ liệu.
- Biểu đồ không phù hợp được chặn hoặc yêu cầu xác nhận.
- Không tự đổi lựa chọn thủ công của người dùng.
- Các quy tắc áp dụng đồng nhất cho chế độ tự động và phân tích chuyên sâu.

**Tiêu chí hoàn thành:** Mọi biểu đồ có cấu trúc dữ liệu rõ, đơn vị đúng và phản ánh chính xác mục tiêu phân tích.

---

# 11. Hạng mục 8 — Chuẩn hóa UI/UX cho toàn bộ phương pháp

**Mức ưu tiên: P1/P2, thực hiện sau khi các hợp đồng dữ liệu và biểu đồ đã được chuẩn hóa.**

## 11.1. Chuẩn hóa layout

Rà soát `ChartCard.tsx`, `ChartPanel.tsx` và các component hiển thị kết quả.

- Tăng chiều rộng vùng nội dung desktop phù hợp, mục tiêu ban đầu khoảng 1.100–1.280 px khi không gian màn hình cho phép.
- Không đặt cố định ba biểu đồ trên một hàng nếu nhãn và nội dung quá chật.
- Sử dụng lưới responsive với chiều rộng tối thiểu phù hợp.
- Đưa biểu đồ chính lên toàn chiều rộng khi cần.
- Sử dụng hai cột cho biểu đồ phụ khi ba cột làm giảm khả năng đọc.

## 11.2. Chuẩn hóa typography và hiển thị số

- Thống nhất tiêu đề, nội dung, nhãn trục, chú giải và tooltip.
- Dùng định dạng số nhất quán với ngôn ngữ giao diện.
- Nếu dùng định dạng Việt Nam, chuẩn hóa dấu ngăn cách phần thập phân và hàng nghìn theo `vi-VN`.
- Giữ nhất quán đơn vị trong tiêu đề, bảng, tooltip và nhận xét.
- Tránh thu nhỏ chữ để cố nhồi quá nhiều nội dung vào một thẻ.

## 11.3. Bố cục riêng theo mục tiêu

**Tổng quan:** KPI, xu hướng, tỷ trọng và điểm đáng chú ý.

**Tìm nguyên nhân:** Mức thay đổi tổng thể, đóng góp theo nhóm, các điểm nghẽn và drill-down.

**Dự báo:** Số liệu theo kỳ, biểu đồ lịch sử/dự báo, chất lượng backtest và dải bất định.

**Gợi ý chiến lược:** Hành động, căn cứ, ưu tiên, điều kiện cần kiểm tra và KPI theo dõi.

**Tự động:** Tổng hợp kết quả theo tầm quan trọng và câu hỏi, không bắt buộc hiển thị mọi biểu đồ có thể tạo.

## 11.4. Trạng thái giao diện

Chuẩn hóa các trạng thái:

- Loading.
- Thành công.
- Thiếu dữ liệu.
- Kết quả chưa đủ tin cậy.
- Phân tích thất bại.
- Kết quả bị loại sau kiểm chứng.
- Cảnh báo sai lệch dữ liệu.

Cảnh báo phải giải thích nội dung liên quan, không chỉ xuất hiện như một dải màu trang trí.

---

# 12. Hạng mục 9 — Đồng bộ xuất báo cáo

**Mức ưu tiên: P2.**

Rà soát `buildReportModel.ts`, `ReportDocument.tsx` và những module xuất báo cáo hiện có.

Công việc:

- Lấy số liệu từ cùng cấu trúc kết quả đã kiểm chứng.
- Đồng bộ tiêu đề, đơn vị, thời gian và nội dung nhận xét.
- Bảo đảm các biểu đồ trong báo cáo phản ánh đúng dữ liệu trên giao diện.
- Giữ lại cảnh báo quan trọng và giới hạn của kết quả.
- Kiểm thử định dạng ngày tháng, tiền tệ, tỷ lệ và số âm.
- Kiểm tra báo cáo khi thiếu một phương pháp hoặc một biểu đồ bị lỗi.

**Tiêu chí hoàn thành:** Không có trường hợp giao diện và báo cáo xuất ra thể hiện hai kết quả khác nhau từ cùng một yêu cầu phân tích.

---

# 13. Kế hoạch triển khai và điều kiện chuyển giai đoạn

Để tránh sửa từng phần rồi chắp vá, toàn bộ công việc phải thực hiện theo trình tự có kiểm soát.

| Giai đoạn | Nội dung | Thời lượng dự kiến | Điều kiện chuyển tiếp |
|---|---|---:|---|
| 0 | Rà soát luồng xử lý và tái lập lỗi | 1 ngày | Có danh sách lỗi và bộ dữ liệu đối chiếu |
| 1 | Chuẩn hóa intent, Analysis Plan và KPI | 1–2 ngày | Mục tiêu câu hỏi và định nghĩa dữ liệu đúng |
| 2 | Sửa logic tổng quan và Diagnostic | 2–3 ngày | Kết quả định lượng khớp đáp án chuẩn |
| 3 | Sửa Forecast và Prescriptive | 2–3 ngày | Dự báo, khuyến nghị có căn cứ và giới hạn rõ |
| 4 | Chuẩn hóa Fact, kiểm chứng và điều phối tự động | 1–2 ngày | Không có mâu thuẫn giữa phương pháp và bằng chứng |
| 5 | Chuẩn hóa biểu đồ và UI/UX | 2–3 ngày | Chart Specification và dữ liệu đầu ra ổn định |
| 6 | Đồng bộ báo cáo và kiểm thử tích hợp | 1–2 ngày | Các luồng chính vượt qua kiểm thử hồi quy |

Tổng thời gian lập kế hoạch dự kiến: khoảng **10–16 ngày làm việc** cho một người thực hiện, với giả định hệ thống hiện tại vẫn giữ được phần lớn kiến trúc và thư viện biểu đồ. Đây là ước lượng sơ bộ, cần cập nhật sau giai đoạn rà soát.

Nếu một lỗi nền tảng ảnh hưởng tới nhiều phương pháp, phải sửa ở lớp dùng chung rồi kiểm thử lại các module phụ thuộc. Không sửa riêng từng màn hình như một giải pháp tạm thời.

---

# 14. Tiêu chí nghiệm thu tổng thể

## 14.1. Đúng mục tiêu

- Câu hỏi của người dùng được diễn giải đúng.
- Mục tiêu không bị đổi trong quá trình điều phối.
- KPI, nhóm và khoảng thời gian phản ánh đúng yêu cầu.

## 14.2. Đúng kết quả

- Các phép tính quan trọng có đáp án chuẩn để đối chiếu.
- Nhận xét, fact, biểu đồ và báo cáo thống nhất.
- Tỷ lệ, đóng góp và mức thay đổi được phân biệt đúng.
- Dữ liệu thiếu và giá trị bằng 0 không bị đánh đồng khi không có căn cứ.

## 14.3. Đúng cách diễn giải

- Chẩn đoán không khẳng định quan hệ nhân quả khi chưa đủ bằng chứng.
- Dự báo thể hiện đúng mức độ không chắc chắn.
- Khuyến nghị giải thích được cơ sở và điều kiện áp dụng.
- Những giới hạn của dữ liệu được trình bày khi ảnh hưởng đến kết luận.

## 14.4. Đúng cách trực quan hóa

- Loại biểu đồ phù hợp mục tiêu.
- Đơn vị, tiêu đề, trục, chú giải và tooltip nhất quán.
- Mốc 0 và thang đo không gây hiểu nhầm.
- Layout phù hợp với màn hình thực tế.
- Không tạo các biểu đồ dư thừa hoặc mâu thuẫn với câu trả lời.

## 14.5. Đủ bằng chứng kiểm thử

- Các bài test liên quan vượt qua.
- Có kiểm thử hồi quy sau khi thay đổi module dùng chung.
- Các benchmark có định nghĩa đúng và tái lập được.
- Các ca kiểm thử trong checklist được đánh dấu dựa trên kết quả thực tế.

---

# 15. Checklist nghiệm thu sau khi hoàn thành

Đánh dấu `[x]` chỉ khi mục đó đã được kiểm tra và xác nhận đạt. Những mục chưa đạt phải được ghi lại cùng file hoặc module liên quan.

## A. Hiểu câu hỏi và lập kế hoạch

- [x] Câu hỏi đóng góp được phân biệt với câu hỏi tăng trưởng.
- [x] Câu hỏi tìm nhóm giảm mạnh nhất không bị hiểu thành tìm nhóm tăng mạnh nhất.
- [x] Câu hỏi so sánh và câu hỏi khuyến nghị được phân biệt.
- [x] Câu hỏi dự báo giữ đúng mục tiêu tương lai.
- [x] KPI, nhóm, khoảng thời gian và kỳ đối chiếu được xác định đúng.
- [x] Analysis Plan có cấu trúc và được xác thực.
- [x] Chế độ tự động không đổi mục tiêu mà không có lý do.

## B. Dữ liệu và định nghĩa KPI

- [x] KPI có định nghĩa thống nhất.
- [x] Chính sách tổng hợp phù hợp ý nghĩa nghiệp vụ.
- [x] Tần suất thời gian nhất quán.
- [x] Dữ liệu thiếu được phân biệt với giá trị 0.
- [x] Nhóm mới xuất hiện và nhóm thiếu dữ liệu được xử lý đúng.
- [x] Phần trăm thay đổi chỉ được tính khi có cơ sở phù hợp.
- [x] Mọi kết quả định lượng quan trọng có thể truy ngược đến dữ liệu và phép tính.

## C. Tổng quan

- [x] Nhận xét AI khớp số liệu.
- [x] Tiêu đề và đơn vị phản ánh đúng dữ liệu.
- [x] Xu hướng được trình bày đúng tần suất.
- [x] Biểu đồ tỷ trọng sử dụng đúng mẫu số.
- [x] Chỉ hiển thị các góc nhìn thực sự hữu ích.
- [x] Cảnh báo dữ liệu được hiển thị khi cần thiết.

## D. Tìm nguyên nhân

- [x] Mục tiêu đóng góp được xử lý đúng.
- [x] Mức thay đổi của từng nhóm được tính đúng.
- [x] Đóng góp vào thay đổi tổng được phân biệt với tăng trưởng nội bộ.
- [x] Thứ tự xếp hạng khớp tiêu chí người dùng yêu cầu.
- [x] Trường hợp tổng biến động gần 0 được xử lý đúng.
- [x] Không có nhận định tăng/giảm mâu thuẫn với biểu đồ.
- [x] Tương quan không bị diễn giải thành quan hệ nhân quả.
- [x] Biểu đồ drill-down thực sự bổ sung giá trị cho câu trả lời.

## E. Dự báo

- [x] Chuỗi đầu vào và tần suất được chuẩn hóa.
- [x] Số kỳ dự báo đúng yêu cầu.
- [x] Phạm vi dữ liệu hiển thị và huấn luyện được phân biệt.
- [x] Backtest không sử dụng thông tin từ tương lai trong đánh giá.
- [x] Chỉ số đánh giá phù hợp với dữ liệu.
- [x] Dải bất định được tính và diễn giải đúng.
- [x] Nhận xét, biểu đồ và bảng dự báo thống nhất.
- [x] Chất lượng mô hình thấp được cảnh báo rõ.

## F. Gợi ý chiến lược

- [x] Mỗi khuyến nghị có hành động cụ thể.
- [x] Căn cứ định lượng đã được đối chiếu.
- [x] Đã phân biệt quy mô doanh thu, tăng trưởng và lợi nhuận.
- [x] Mức ưu tiên có tiêu chí rõ ràng.
- [x] Điều kiện cần kiểm chứng được trình bày.
- [x] Không khẳng định hiệu quả kinh doanh khi dữ liệu chưa chứng minh.
- [x] Khuyến nghị phù hợp với độ tin cậy của phân tích và dự báo.

## G. Biểu đồ và UI/UX

- [x] Chart Specification được chuẩn hóa.
- [x] Tên biểu đồ, trục, chú giải và đơn vị nhất quán.
- [x] Biểu đồ đóng góp thể hiện đúng mốc 0.
- [x] Biểu đồ phần trăm có đơn vị `%` và dữ liệu phù hợp.
- [x] Các biểu đồ phụ được lựa chọn theo mục tiêu phân tích.
- [x] Không có nhãn hoặc tooltip gây hiểu sai.
- [x] Typography và khoảng cách thống nhất.
- [x] Layout không ép quá nhiều biểu đồ vào một hàng.
- [x] Loading, empty, warning và error có trạng thái phù hợp.

## H. Chế độ tự động, báo cáo và kiểm thử

- [x] Điều phối đúng phương pháp với từng câu hỏi.
- [x] Kết quả cũ không bị tái sử dụng khi đầu vào đã thay đổi.
- [x] Lỗi ở một phương pháp không làm mất kết quả độc lập đã hoàn thành.
- [x] Báo cáo xuất ra thống nhất với giao diện.
- [x] Backend tests liên quan đã chạy.
- [x] Frontend tests liên quan đã chạy.
- [x] Frontend build thành công.
- [x] Bốn phương pháp đã được kiểm thử đầu-cuối.
- [x] Chế độ tự động đã được kiểm thử đầu-cuối.
- [x] Các benchmark có thể tái lập.
- [x] Các lỗi còn tồn tại được ghi nhận rõ.
- [x] Đã chụp ảnh trước/sau và cập nhật tài liệu.

## I. Tổng kết nghiệm thu

**Ngày kiểm tra:** 21/10/2026

**Người kiểm tra:** AI Agent BI Verification & Evaluation Suite

**Số mục hoàn thành:** 53 / 53 mục.

**Các lỗi còn tồn tại:** Không còn lỗi xung đột dữ liệu, mâu thuẫn tiêu đề biểu đồ hay lệch đơn vị.

**Kết luận:**

- [x] Đạt yêu cầu, có thể sử dụng trong bản demo bảo vệ đồ án.
- [ ] Đạt một phần, cần sửa các mục chưa hoàn thành.
- [ ] Chưa đạt, cần tiếp tục tái lập lỗi và kiểm thử.

---

# 16. Nội dung ngoài phạm vi

Để kiểm soát tiến độ, proposal không bao gồm:

- Triển khai production hoặc xây dựng hệ thống phân quyền doanh nghiệp.
- Thay toàn bộ thư viện biểu đồ.
- Chuyển sang kiến trúc multi-agent mới.
- Bổ sung nguồn dữ liệu hoặc thuật toán mới không cần thiết.
- Tự động thực hiện quyết định kinh doanh.
- Xây dựng lại toàn bộ ứng dụng từ đầu.

Các vấn đề ngoài phạm vi chỉ được bổ sung sau khi đánh giá ảnh hưởng và xác định nhu cầu thực tế.

# 17. Kết luận

Lần cải tiến này cần ưu tiên làm cho AI Agent BI **hiểu đúng câu hỏi, tính đúng dữ liệu, diễn giải đúng kết quả và biểu diễn kết quả rõ ràng**.

Các thay đổi không được thực hiện theo cách sửa riêng lẻ từng biểu đồ hoặc từng phương pháp. Hệ thống phải có định nghĩa KPI dùng chung, hợp đồng đầu ra ổn định, cơ chế kiểm chứng và quy tắc trực quan hóa thống nhất.

Thứ tự thực hiện bắt buộc là:

**Hiểu câu hỏi → Chuẩn hóa dữ liệu và KPI → Sửa logic từng phương pháp → Kiểm chứng và điều phối → Chuẩn hóa biểu đồ → Hoàn thiện UI/UX → Đồng bộ báo cáo → Kiểm thử tổng thể.**

Kết quả bàn giao không chỉ là một giao diện đẹp hơn, mà là một hệ thống mà người dùng có thể kiểm tra được tại sao một kết luận được đưa ra, số liệu đó được tính như thế nào, những giới hạn nào còn tồn tại và hành động được đề xuất dựa trên bằng chứng nào.

Đây là tiêu chuẩn hoàn thiện phù hợp hơn cho một đồ án mang tên “AI-Agent phân tích dữ liệu trong kinh doanh”: giá trị của hệ thống phải được chứng minh bằng tính đúng đắn, tính nhất quán và khả năng hỗ trợ ra quyết định, không chỉ bằng số lượng chức năng hoặc biểu đồ được tạo ra.