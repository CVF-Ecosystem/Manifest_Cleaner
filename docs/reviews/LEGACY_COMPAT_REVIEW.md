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

## Đối chiếu ba cặp workbook ngày 25-11-2026

| Manifest | Số dòng Excel cũ | Số dòng app trước → sau | Lỗi chặn trước → sau | Cảnh báo trước → sau |
| --- | ---: | ---: | ---: | ---: |
| VIMC BDNG 2639S | 128 | 138 → 138 | 90 → 0 | 0 → 0 |
| VIMC BDNA 2644S | 490 | 490 → 490 | 310 → 1 | 6 → 6 |
| VOSCO VFON 2640S | 317 | 321 → 317 | 38 → 0 | 83 → 18 |

- VIMC dùng dòng tổng EMPTY khi số lượng theo từng cỡ khớp toàn bộ MARKS của cùng B/L, kể cả khi MARKS bắt đầu ở trang trước. BDNG có thêm 10 cặp B/L–container trong nguồn so với Excel cũ. Chín nằm ở dòng hàng có chi tiết tại S625 và một nằm ở nhóm rỗng L662/S662. BDNA nhận đủ 107 dòng rỗng, gồm bốn dòng chi tiết ghi `SOC RF EMPTY`.
- BDNA vẫn khóa xuất vì `Sheet1!L699` khai 40RF và `Sheet1!S699` khai 40HC cho cùng container. Sáu cảnh báo mã ngắn tiếp tục dùng bằng chứng đối chiếu giữa MARKS và dòng chi tiết. Bản cũ đã xuất 40HC cho dòng xung đột. Quyết định loại kích cỡ được giữ cho operator đối chiếu nguồn.
- VOSCO coi `DOOR/OTI` là nhãn giao nhận. Tổng 669,10 tấn xác nhận 31 dòng ở K1243, gồm 10 trọng lượng tại S1283. Dòng đầu của S1283 là đơn vị TONS của số tại cuối S1243. 18 dòng còn cảnh báo đều ghi EMPTY, gồm 15 dòng 40RF nặng 5 tấn ở dòng nguồn 559 và 3 dòng 20TK nặng 11 tấn ở dòng 1058.
- Cả ba file mới giữ đủ cặp B/L–container của bản cũ. Hai manifest không có lỗi chặn được xuất thử với đúng tiêu đề 16 cột. Kiểm rule màu trong Excel tạo từ VFON cho đúng 18 số thứ tự, ưu tiên vàng cho dòng cảnh báo và xanh nhạt cho dòng rỗng không có cảnh báo. Ghi chú giữ câu thông báo đầy đủ. Màu cảnh báo dựa vào vấn đề còn hiệu lực của phiên và không dùng quy tắc kiểm định dạng seal đã bỏ theo quyết định của operator.

Chỉ đọc sáu workbook nghiệp vụ trong `Manifest/` và đối chiếu SHA-256 trước/sau. Kết quả xuất thử nằm trong thư mục tạm. Chạy lại năm file trong `dist/` với cùng lựa chọn sheet MANIFEST của VINAFCO đạt 788 dòng, 0 lỗi chặn và 3 cảnh báo. Log đọc có cảnh báo thư viện openpyxl về vùng in CGL trong workbook VINAFCO. Kiểm Tk thật ở ba mức tỷ lệ cho tiêu đề và tác giả. Kiểm màu và thứ tự ưu tiên qua OOXML, vì phiên Excel COM cục bộ từ chối mở file mẫu với mã `0x800A03EC`. Chưa kiểm lại bằng EXE.

Trên Windows Tk, đã thử bố cục 595 × 430 với hệ số Tk 2.0, cuộn tới các trường, lưu bằng Enter và hủy bằng Escape. Thanh lý do, Lưu và Hủy hiển thị trong vùng làm việc. Việc lưu dòng áp dụng vào phiên hiện tại. Nút Lưu đối chiếu lưu phiên ra JSON. Xử lý lại từ manifest gốc để tính lại các cảnh báo cấu trúc của bản cũ.

### Hiệu chỉnh theo xác nhận về container lạnh và container bồn

- Danh mục Hapag-Lloyd đưa ví dụ container khô 40 ft vỏ 3,75 tấn và một số mẫu reefer cao 40 ft vỏ 4,30–4,80 tấn. VOSCO dùng mốc 4,80 tấn cộng biên 0,50 tấn hiện có để cảnh báo trọng lượng tổng của 40RF/40RH khai rỗng. Mốc dry, cách suy luận F/E và phép kiểm container có hàng giữ theo quy tắc trước. Container bồn 20TK đã có mốc riêng 5,50 tấn và ngưỡng cảnh báo rỗng 6,00 tấn. Một số bồn chuyên dụng Seaco công bố vỏ 4,50–5,50 tấn. [Dry Hapag-Lloyd](https://www.hapag-lloyd.com/en/services-information/cargo-fleet/container/40-standard.html), [Danh mục reefer Hapag-Lloyd, trang 43](https://static-cf.hapag-lloyd.com/content/dam/website/downloads/local_info/HPL-CONTAINER_SPECIFICATION.pdf), [Bồn chuyên dụng Seaco](https://seacoglobal.com/equipment/tank-containers/specialised-tanks/t20-t22-specialised-tanks/)
- Với BDNA, xác nhận operator dùng chiều cao khai ở chi tiết 40HC và loại lạnh khai ở MARKS 40RF, được mô tả hàng lạnh củng cố. Khi hai nguồn thống nhất theo mẫu này trên một container F, VIMC ghi lại cả hai giá trị, quy đổi sang 40RH trong Excel, lưu mã vật lý tham chiếu 45R1 và xuất với cảnh báo. Chênh lệch chưa có đủ căn cứ vẫn dẫn đến lỗi chặn. [BIC Size & Type Codes](https://www.bic-code.org/size-type-code/), [Bảng mã thiết bị Hapag-Lloyd](https://www.hapag-lloyd.com/en/services-information/cargo-fleet/container/container-type-groups.html)
- Cả ba manifest xuất thử và mở lại được JSON. BDNA đạt 490 dòng, 0 lỗi chặn, 7 cảnh báo. VFON đạt 317 dòng, 0 lỗi chặn, 3 cảnh báo cho 20TK khai rỗng 11 tấn. Mười lăm dòng 40RF khai rỗng 5 tấn vẫn giữ E, 5 tấn. BDNG đạt 138 dòng, 0 lỗi chặn, 0 cảnh báo. Quy tắc màu trong Excel đánh dấu đúng số thứ tự cảnh báo. Sáu workbook nguồn không đổi SHA-256. Năm manifest hồi quy cũ đạt 788 dòng, 0 lỗi chặn và 3 cảnh báo.

### Định dạng trọng lượng và màu đối chiếu Excel

VFON dùng định dạng **General** cho cột **TL hàng**, giống bản Excel cũ. Ô I2 lưu số 9 và số lẻ vẫn được ghi dạng số. Quy tắc tô vàng dùng đúng mẫu tham chiếu bên cột seal của tool cũ, gồm sáu chữ số cho VOSCO và sáu hoặc bảy chữ số cho VIMC/VINAFCO. Seal trống bỏ qua bước tham chiếu. Khi cần đánh dấu, bản xuất giữ câu **⚠️ Seal không hợp lệ** và tô vàng ô **Số niêm chì** cùng **Ghi chú**. Số container có cảnh báo còn hiệu lực cũng được đánh dấu trên ô tương ứng và ô ghi chú. Giá trị seal và quy tắc cho phép xuất lấy từ phiên, còn dấu tham chiếu định dạng seal chỉ áp dụng ở bản xem trước và Excel.

Đối chiếu theo cặp B/L–container trên 317 dòng VFON. Excel xuất thử khớp đủ 96 dòng seal được đánh dấu với bản xử lý cũ. Hai cột seal khớp giá trị cũ. Kết quả phiên là 0 lỗi chặn và 3 cảnh báo nghiệp vụ. Các workbook đối chiếu được đọc cục bộ và giữ nguyên SHA-256.

### VOSCO FF2643S: nhãn giao nhận DOOR-CY và CY-DOOR · 26-11-2026

Operator báo `MNF TAU FF2643S` (VOSCO) không import được. Tại dòng tiêu đề của vận đơn, cột K ghi loại dịch vụ giao nhận `DOOR-CY` (Sheet1!K17 và K43) và `CY-DOOR` (K879). Bộ đọc chỉ coi các nhãn đã liệt kê (`DOOR-DOOR`, `DOOR/OTI`, `OTI/OTI`, `OTI/DOOR`, `DB-CY`, `OTI-CY`) là siêu dữ liệu, nên hai nhãn này bị đọc thành số container. Hậu quả: ba dòng container giả, 21 lỗi chặn xuất và 30 cảnh báo "chưa rõ phạm vi đếm" phát sinh từ ba dòng đó.

| Manifest | Số dòng Excel cũ | Số dòng app trước → sau | Lỗi chặn trước → sau | Cảnh báo trước → sau |
| --- | ---: | ---: | ---: | ---: |
| VOSCO FF2643S | 297 | 300 → 297 | 21 → 0 | 36 → 4 |

- **Sửa:** thêm `DOOR-CY` và `CY-DOOR` vào danh sách nhãn giao nhận của VOSCO. Chỉ thêm hai nhãn đã quan sát trong nguồn. Chữ lạ cạnh số vận đơn, kể cả biến thể chưa thấy như `DOOR-XY`, vẫn được giữ làm ứng viên container để xem lại.
- **Đối chiếu app cũ** (`Processed_MNF TAU FF2643S.xlsx`): đủ 297 container, 88 vận đơn, không có dòng nào là nhãn. Mỗi container khớp về vận đơn, hãng khai thác, kích cỡ VTOS, seal, hàng hóa. Còn hai nhóm khác biệt, đều có từ trước và không do sửa này:
  - Bốn container `FAJU2019024`, `FAJU2019071`, `FAJU2019132`, `FAJU2019153` khai EMPTY TANK nặng khoảng 11 tấn. App cũ ghi F/TANK. App này giữ E theo khai báo nguồn và báo `EMPTY_WEIGHT_CONFLICT`. Đây là bốn cảnh báo còn lại, chờ xác nhận nguồn như các ca FAJU trước.
  - Mười container ở vận đơn `VOSHPH268283` (nhóm `SELU4743129`…`VIMU6244714`) app cũ để trống trọng lượng. App này đọc đủ 10 số từ ô nối tiếp Sheet1!S1552 (cột 19). Tổng 29 container của vận đơn là 565,85 tấn, đúng bằng dòng `Total:565.85` trong nguồn.
- **Kiểm chứng:** xuất thử vào thư mục tạm cho 297 dòng, 16 cột, 88 vận đơn, mọi số container đủ 11 ký tự, mở lại JSON đối chiếu không lỗi. Chạy 8 file khác nhau trong `Manifest/` và `dist/` với cả ba hãng (24 tổ hợp), kết quả xuất giống hệt trước và sau ở 23 tổ hợp, chỉ FF2643S với VOSCO đổi. SHA-256 file nguồn không đổi. Thêm hai ca hồi quy theo đúng bố cục thật bằng dữ liệu giả và mở rộng ca nhãn cũ. Hai ca đầu thất bại với danh sách nhãn cũ.
