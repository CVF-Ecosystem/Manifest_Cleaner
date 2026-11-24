# Đối chiếu manifest thực tế trên Manifest Cleaner 1.2.1

Risk: R2
Worker: Sol 6.2 Medium, Terra 6.1 High và orchestrator tích hợp
Reviewer: Astra 6.2 Medium độc lập

Kiểm ngày 24-11-2026 trên máy Windows hiện tại. Ghép dòng theo cặp số container và số vận đơn, kiểm đủ thứ tự 16 cột và so riêng các trường nghiệp vụ. Hai cột điểm quy tắc và ghi chú phản ánh các vấn đề cần đối chiếu của app mới.

Kết luận về mười trọng lượng VOSCO được đính chính ở phần 1.2.3 bên dưới. Người sử dụng chỉ ra ô nối tiếp `S618` trong manifest gốc.

| Mốc | Kết quả quan sát |
| --- | --- |
| MC51 · VIMC | `MNF BS2622S-TT.xls` đọc 157 dòng trên 52 B/L. Cả 13 cột nghiệp vụ và thứ tự dòng khớp bản `Processed_MNF BS2622S-TT.xlsx`. 315 lỗi chặn xuất giảm còn 0. Đã xuất Excel thật, mở lại JSON và xác minh SHA-256 của Excel. |
| MC52 · VOSCO | `MNF TAU FF2601S.xls` đọc 309 dòng, khớp đủ cặp container–B/L với `Processed_MNF TAU FF2601S1.xlsx`. Bản xem trước khớp số lượng và cả 299 trọng lượng đã gán. Bản 1.2.1 chặn xuất do chưa tìm được mười trọng lượng trong cùng vận đơn. Hai dòng ghi EMPTY nhưng có trọng lượng cao vẫn cần kiểm F/E và loại hàng. |
| MC53 · VINAFCO | Ba nguồn có 4, 57 và 261 dòng. So từng dòng trên cả 13 cột nghiệp vụ với kết quả chạy lại bộ đọc và bộ xử lý VINAFCO cũ. Cả ba khớp và đều xuất được Excel cùng JSON khi chọn sheet `MANIFEST`. Phạm vi so sánh dùng kết quả tái chạy từ code cũ vì thư mục hiện có ba file nguồn. |

## Căn cứ sửa theo nguồn

- VIMC dùng dấu vai trò trong cột A ở khối ngay sau số B/L khi ô tương ứng của cột dưới tiêu đề để trống. Dòng tổng SOC của sáu B/L khớp số lượng, kích cỡ và phạm vi chi tiết, làm đúng 21 mã SVM. 136 dòng còn lại mang mã VMC. Một mã ngắn và kích cỡ khớp nguyên văn giữa dòng chi tiết và ô MARKS độc lập, nên được giữ kèm cảnh báo. Phiên có 141 cảnh báo seal và một cảnh báo mã ngắn.
- VOSCO nhận diện năm ký hiệu giao nhận ở 37 đoạn văn bản cột K. Các ký hiệu vẫn tra được trong bằng chứng nguồn. Ô `K578` có 30 container và `S578` chứa 20 trọng lượng ở các vị trí được cột hàng hóa xác nhận. Mười ô trọng lượng tương ứng trong bản đã xử lý cũ để trống. Hai xung đột F/E có dấu EMPTY và trọng lượng 11 tấn mỗi dòng.
- SHA-256 của các workbook đầu vào và hai bản xuất tham chiếu vẫn khớp giá trị trước khi kiểm. Hồi quy tự chứa dùng dữ liệu giả lập.

## Windows

- Nút xuất trong GUI Tk từ mã nguồn đã được kiểm bằng đúng file VIMC. Luồng xuất yêu cầu xác nhận 142 cảnh báo và tạo 157 dòng dữ liệu, 16 cột, kèm JSON mở lại được. Đường dẫn cho hộp thoại và thao tác xác nhận được cấp trong bài kiểm thử.
- Python 3.11.9 x64, dependency theo pin và PyInstaller 6.22.3. Kiểm đủ 228 unittest và 94 mục SHA-256. EXE 1.2.1 khởi động và đóng bình thường từ thư mục làm việc ngoài project. Gói chứa đủ ba adapter và chạy từ `dist/1.2.1/ManifestCleaner`. SHA-256 EXE `fab0dca9cd372635159442248bf3dcc896d0c29a268af40da642bff39d3b7732`. Đã đối chiếu lại SHA-256 EXE 1.2.0 tại thư mục build ban đầu.
- Reviewer tái hiện các ca biên, gồm ghi chú chứa mã ngắn trong MARKS, đổi mã thủ công rồi mở lại phiên, mô tả kiểu số trong Excel và khoảng trống làm mơ hồ vị trí trọng lượng. Những trường hợp mất căn cứ ghép dữ liệu vẫn được đưa vào đối chiếu.
- Reviewer kiểm quy tắc ghép trọng lượng trên cặp VOSCO XLS thực tế và một fixture XLSX chứa CRLF thật. Một fixture khác đã ghi thêm dấu xuống dòng vào ô nên trả về trạng thái cần đối chiếu. Nghiệm thu import tại Cảng và chạy trên máy Windows sạch vẫn còn mở.

## Đính chính VOSCO trong bản 1.2.3

Ô gộp chứa danh sách container bắt đầu ở `K578`. Hai ô gộp chứa trọng lượng của cùng vận đơn bắt đầu ở `S578` và `S618`. Ô đầu có 20 trọng lượng, cộng 415,42 tấn. Ô nối tiếp có đúng 10 trọng lượng, cộng 115,60 tấn. Cả 30 giá trị cộng đúng tổng 531,02 tấn ghi ở cuối ô `S618`, trước khi vận đơn tiếp theo bắt đầu ở `F641`.

Bộ đọc VOSCO quét phần còn lại của cùng vận đơn khi đã xác định được một dãy trọng lượng khớp đầu danh sách container. Chỉ ghép phần nối tiếp khi có một ô phù hợp và số lượng, đơn vị, tổng nguồn khớp. Từng trọng lượng giữ tọa độ ô và số dòng bên trong ô. Ca có nhiều ứng viên, sai tổng hoặc vượt ranh giới vận đơn vẫn đưa vào đối chiếu.

Đã mở file gốc và xuất qua giao diện Tk trên Windows. File xuất đủ 309 dòng và 16 cột, không có lỗi chặn xuất. Mười ô `I138:I147` lấy giá trị từ `S618` dòng 1–10, các trọng lượng còn lại khớp bản cũ. JSON mở lại đúng nguồn, giữ tọa độ và khớp SHA-256 với Excel. Hai cảnh báo EMPTY/trọng lượng cao vẫn cần đối chiếu nghiệp vụ.

Reviewer độc lập xác minh file thực tế và các ca giả lập có ô nối tiếp lẫn thông tin chủ hàng, thiếu đơn vị, nhiều khối chi tiết, nhiều ô trọng lượng, thiếu giá trị hoặc gặp vận đơn mới. Bộ nguồn đạt 233 kiểm thử và 94 mục SHA-256.

## Quy tắc khai báo trong bản 1.2.4

Người vận hành xác nhận trọng lượng trên manifest của hãng là tổng vỏ và hàng. Mỗi lần đọc mới dùng `gross` và xuất tổng theo đơn vị tấn của mẫu Cảng. Phiên đã lưu giữ quy ước và giá trị đã ghi nhận lúc xử lý.

Số niêm chì được ghi theo khai báo nguồn. Hai cột xuất giữ nguyên chữ, số 0 đầu, khoảng trắng và dấu phân cách thuộc trường seal, ở dạng văn bản Excel. App đã bỏ cảnh báo và tô màu theo mẫu seal 6–7 chữ số. Việc đối chiếu với seal thực tế thực hiện khi container xuống bãi.

Kiểm năm manifest thực tế trên máy Windows. VIMC có 157 dòng, VOSCO có 309 dòng và VINAFCO có 322 dòng trong ba file. Cả năm file đều xử lý theo `gross`, xuất đủ 16 cột và mở lại được qua JSON. VOSCO giữ hai cảnh báo mâu thuẫn giữa khai báo EMPTY và trọng lượng cao.

Kiểm độc lập các seal có số 0 đầu, dấu phân cách, chữ thường và văn bản giống công thức. Trường hợp một dòng VIMC có nhiều cách tách seal và kích cỡ cần xác nhận theo nguyên văn nguồn. Đã kiểm 246 ca và 94 mục SHA-256 trên bộ nguồn.

## Rà cảnh báo, ghi chú và lưu dòng trong bản 1.2.5

Đã rà các nơi phát sinh thông báo ở ba adapter và bộ kiểm tra chung, luồng sửa hoặc xác nhận dòng, mở lại phiên, lọc trên giao diện, xem trước và ghi Excel. Kết quả dưới đây dùng năm manifest nghiệp vụ đọc tại máy.

| Nguồn | Kết quả đọc mới | Căn cứ xử lý |
| --- | --- | --- |
| VOSCO FF2601S | 309 dòng, 2 cảnh báo | Bỏ 61 cảnh báo số lượng sai ở các dòng nguồn 59, 578 và 911. Dòng 59 kê 60 container của hai phần chi tiết (38 + 22). Dòng 578 kê 10 × 20DC và 20 × 40HC. Dòng 911 kê 8 × 20DC và 1 × 40HC. Mô tả hàng khớp Excel cũ trên cả 309 dòng. |
| VOSCO dòng 980 | Giữ E và 11 tấn trên hai dòng | Mô tả ghi EMPTY. Tổng khai cao hơn ngưỡng đối chiếu 6 tấn cho 20TK (vỏ tham chiếu 5,5 tấn và biên 0,5 tấn). Cảnh báo ghi rõ số liệu để người dùng đối chiếu. |
| VIMC BS2622S-TT | 157 dòng, 1 cảnh báo | Mã ngắn có cùng số trên dòng chi tiết và MARKS. Giữ số theo nguồn, cho phép xác nhận số container. Mã hỏng thiếu bằng chứng vẫn chặn xuất. |
| VINAFCO, ba manifest | 4, 57 và 261 dòng, tổng 0 cảnh báo | 228 dòng có mô tả hàng và trọng lượng phù hợp trạng thái F. Giữ căn cứ suy luận trong quy tắc đọc. Trạng thái mặc định, thiếu bằng chứng hoặc mâu thuẫn có thông báo riêng. |

Các kiểm thử giả lập bao gồm sai số lượng thực, nhiều cỡ trên cùng dòng, tổng ghi riêng, phạm vi B/L lặp, mẫu ghi khối lượng trong mô tả hàng, trị số thay đổi sau xác nhận, dòng VIMC trùng có trọng lượng khác nhau và ghi chú toàn file. Bản xuất giữ 16 cột. Cột Ghi chú dùng vấn đề còn hiệu lực của từng dòng và căn cứ cho trường đã sửa hoặc xác nhận. JSON giữ lịch sử, quy tắc và vấn đề toàn file. Các dòng rõ dữ liệu, chưa chỉnh sửa có ghi chú trống.

Trên Windows Tk, đã thử bố cục 595 × 430 với hệ số Tk 2.0, cuộn tới các trường, lưu bằng Enter và hủy bằng Escape. Thanh lý do, Lưu và Hủy hiển thị trong vùng làm việc. Việc lưu dòng áp dụng vào phiên hiện tại. Nút Lưu đối chiếu lưu phiên ra JSON. Xử lý lại từ manifest gốc để tính lại các cảnh báo cấu trúc của bản cũ.
