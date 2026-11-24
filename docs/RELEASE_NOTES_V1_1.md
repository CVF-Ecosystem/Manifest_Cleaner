# Manifest Cleaner Unified 1.1.0 — bản nâng cấp sau audit độc lập

> Tài liệu lịch sử của bản 1.1.0. Bản hiện tại là 1.1.1; xem [bản vá F10](RELEASE_NOTES_V1_1_1.md) và [kết quả kiểm thử hiện tại](VALIDATION_REPORT.md).

Ngày phát hành: **22-11-2026**, múi giờ Asia/Ho_Chi_Minh. Bản nền: gói `Manifest_Cleaner_Unified_v1.0.0_2026-11-22.zip` do người dùng cung cấp. SHA-256 và các repo/commit kế thừa được ghi trong `SOURCE_PROVENANCE.json`.

**Kết quả:** đã sửa các finding F01–F09 theo những tình huống tái hiện trong audit; bổ sung lưu/mở lại phiên, đối chiếu nguồn, xem trước đúng dữ liệu xuất và xuất kèm hồ sơ đối chiếu. Bộ kiểm thử phát hành đạt **191/191**, gồm 88 ca có sẵn và 103 ca bổ sung; không có ca bị bỏ qua.

Đây là **bản mã nguồn hoàn chỉnh để chạy bằng Python**, kèm launcher Windows và công thức build EXE. Chưa đóng gói hoặc chạy EXE Windows trong môi trường kiểm chứng này. Xem [VALIDATION_REPORT.md](VALIDATION_REPORT.md) để phân biệt kết quả đã chạy và phần nghiệm thu còn cần môi trường thực tế.

## 1. Đối chiếu finding với bản sửa

| ID / mức audit | Vấn đề đã tái hiện ở 1.0.0 | Hành vi của 1.1.0 | Bằng chứng hồi quy |
|---|---|---|---|
| F01 / P1 | Chỉ sửa seal nhưng form gửi mọi trường, vô tình xóa lỗi F/E hoặc lỗi ghép trọng lượng–mô tả | Chỉ ghi nhận trường thay đổi; xác nhận trường giữ nguyên phải được chọn riêng. Lỗi liên quan nhiều trường cần đủ các trường đó. | `test_session_v110`, `test_gui_v110` |
| F02 / P1 | VIMC bỏ qua các ứng viên mã container có khoảng trắng, gạch nối hoặc thiếu chữ, rồi xuất thiếu dòng | Giữ ứng viên có cấu trúc được hỗ trợ và bằng chứng nguồn thành record cần sửa; không tự sửa mã thành hợp lệ. Có kiểm tra âm với seal, tổng và số điện thoại. | `test_vimc_v110` |
| F03 / P1 | VINAFCO nhận header `GWKGS` nhưng hiểu 25000 thành 25000 tấn; header lặp đổi đơn vị/cột vẫn dùng schema cũ | Nhận diện header và đơn vị chung một lần: 25000 KGS → 25 tấn. Header lặp thay đổi schema/đơn vị tạo lỗi toàn file, dừng vùng không chắc chắn và giữ bằng chứng. | `test_vinafco_v110`, `test_golden_v110` |
| F04 / P1 | VOSCO có `RICE / PORT HAIPHONG / STEEL` nhưng ghép container thứ hai thành `PORT HAIPHONG` | Phân loại mô tả thống nhất cho cả đếm và ghép; nhận đúng RICE/STEEL, lưu dòng nguồn tương ứng và dòng metadata bị loại khỏi tên hàng. | `test_vosco_v110`, `test_golden_v110` |
| F05 / P1 | VOSCO khai báo trọng lượng hàng nhưng vẫn so với tare; 2 tấn hàng nhẹ có thể thành E | `cargo` tham gia logic F/E; hàng dương không bị coi là rỗng do nhẹ hơn tare. `unknown` giữ quy tắc nền và cảnh báo. EMPTY + khối lượng hàng dương tạo lỗi liên quan F/E và trọng lượng. | `test_vosco_v110`, `test_session_v110` |
| F06 / P2 | Chọn lỗi của container B nhưng nút hành động tác động container A đang chọn ở tab ẩn | Các nút lấy selection từ tab hiện hành; dialog nêu container/B/L; lỗi toàn file không cho dùng thao tác theo dòng. | `test_gui_v110` |
| F07 / P2 có điều kiện | Ô công thức chưa có kết quả lưu bị đọc thành trống, có thể làm mất dòng | Với XLSX/XLSM, kiểm XML trước khi đọc, chặn công thức chưa có kết quả hoặc kết quả lỗi trên sheet đang xử lý. Bao gồm sheet VIMC đã nhận diện nhưng không tạo record. Không tự tính công thức. | `test_session_v110` |
| F08 / P2 | CLI được truyền đường dẫn cấu hình không tồn tại nhưng âm thầm dùng mặc định | `--settings` đã chỉ định phải đọc được và hợp lệ; sai thì dừng. Enum, mapping, tên cấu hình và sheet được kiểm tra. | `test_session_v110`, `test_cli_v110` |
| F09 / P2 | VIMC có marker `2)` ở một dòng, tên consignee ở dòng sau nhưng không đọc tiếp | Đọc continuation trong đúng vai trò và B/L, dừng ở marker/nhóm/container/tổng phù hợp; giữ tọa độ bằng chứng. | `test_vimc_v110` |

Phạm vi F02 là các dạng ứng viên đã được bộ nhận diện hỗ trợ và kiểm thử, không phải bảo đảm mọi chuỗi hỏng tùy ý đều được hiểu là container. F07 chưa có cơ chế kiểm tra cache tương đương cho XLS nhị phân; không diễn giải kiểm thử XLSX thành chứng nhận XLS.

## 2. Nâng cấp cho công việc đối chiếu

### Xem rõ nguồn và kết quả sẽ xuất

Form sửa có tab đối chiếu nguyên văn/bằng chứng với **16 cột xuất thực tế**. Preview dùng cùng quy tắc mapping, số lượng, làm tròn và nhãn EMPTY với exporter; phản ánh các giá trị đang sửa nhưng chưa thay session. Trường liên quan lỗi có dấu `*`. JSON kỹ thuật được thu gọn.

Dòng VIMC mơ hồ có bộ chọn cách đọc; không chọn sẵn phương án. Người dùng đối chiếu rồi điền và xác nhận trọng lượng/mô tả, ghi căn cứ và lưu. Cách này giữ quyết định nghiệp vụ có dấu vết thay vì chỉ làm mất thông báo lỗi.

### Tra nguồn và hiểu đúng số đếm

Ba adapter ghi `source_fragments` và các số đếm tại thời điểm đọc. Cửa sổ **Tra nguồn** hiển thị vị trí, nguyên văn, trạng thái và lý do. VOSCO bổ sung bằng chứng dòng cảng/tổng/danh sách đính kèm và thông tin số lượng; VIMC giữ đoạn chưa đọc chắc; VINAFCO giữ dòng thiếu mã container và phần sau header thay đổi.

Những số đếm này là ảnh chụp của quá trình đọc nguồn, không tự đổi khi người dùng sửa record. Chúng chỉ tính các đoạn parser đã ghi nhận, không phải số ô toàn workbook, số container hay tỷ lệ chính xác. Lỗi hiện tại được thống kê riêng theo container và toàn file.

### Lưu và mở lại phiên

Review JSON chuyển sang **v2**, lưu records, bằng chứng gốc, lỗi nền, cấu hình, chỉnh sửa, xác nhận, dòng đã loại và lịch sử. Mở lại không chạy parser để ghi đè chỉnh sửa. SHA-256 bảo đảm đúng manifest nguồn; nguồn đã di chuyển có thể chọn lại khi nội dung khớp.

Mã kiểm tra payload phát hiện file bị hỏng hoặc nội dung không nhất quán, không phải chữ ký xác thực người chỉnh sửa. Manifest nguồn đã đổi phải được mở thành phiên mới hoặc tìm lại đúng bản nguồn cũ. JSON v1.0 tiếp tục dùng tham khảo, không được tự nâng nhãn để mở như phiên v2.

Demo REVIEW trong gói dùng đường dẫn tương đối với JSON, nên có thể mở sau khi giải nén nếu giữ INPUT cạnh REVIEW. Phiên làm việc thông thường giữ đường dẫn tuyệt đối và hỗ trợ chọn lại nguồn.

### Xuất bộ Excel và đối chiếu

GUI/CLI mặc định xuất `.xlsx` kèm `.review.json`. Cả hai cùng session ID/source hash; JSON ghi SHA-256 của Excel. Thông tin kỹ thuật ở custom properties và JSON, không thêm cột vào mẫu nhập Cảng.

Ứng dụng kiểm tra cả hai đích trước khi ghi đè, chuẩn bị đủ file rồi mới thay thế. Khi lỗi ghi được bắt, chương trình khôi phục các đích đã thay; nếu khôi phục tiếp tục lỗi, giữ bản dự phòng và báo đường dẫn. Mỗi lần thay một file là atomic; hai file không phải một giao dịch bảo đảm chung khi mất điện/tắt tiến trình đột ngột.

Trong rà soát tích hợp đã sửa thêm xung đột tên backup khi đích có tên `previous_0.xlsx` hoặc JSON khác thư mục có tên `previous_1.json`. Các ca hồi quy kiểm cả giá trị Excel, nội dung JSON và hash khớp nhau sau ghi đè.

### Cấu hình, CLI và bộ chạy

Giao diện hiển thị cấu hình hiệu lực, cho chọn sheet và nghĩa trọng lượng `gross/cargo/unknown`. Chỉ thay đổi thật mới yêu cầu đọc lại. CLI có `--resume`, `--source`, `--sheet`, `--no-review` và `--review` tùy chọn đích JSON; các tổ hợp trái nghĩa bị từ chối.

Launcher Windows kiểm Python/x64/Tkinter và đúng thư viện đã pin. Môi trường đã đủ không chạy pip mỗi lần mở app. Bộ build kiểm thử trước khi đóng gói và ghi phiên bản thực vào `BUILD_INFO.txt`. Script `scripts/check_release.py` kiểm checksum gói, runtime hoặc chạy lại suite; xem [WINDOWS_RELEASE_CHECKLIST.md](WINDOWS_RELEASE_CHECKLIST.md).

## 3. Tương thích nghiệp vụ

- Mỗi phiên vẫn là một manifest/một hãng; hỗ trợ VOSCO, VIMC, VINAFCO và nhận dạng bố cục từ nội dung.
- Giữ **16 cột** theo từng mẫu, thứ tự/tên cột, operator, mapping kích cỡ VTOS/loại hàng, quy tắc EMPTY và phạm vi số lượng theo nhóm BL/Master B/L.
- VIMC/VINAFCO tiếp tục làm tròn trọng lượng ở bước xuất theo quy tắc cũ; VOSCO giữ độ chính xác sau quy đổi.
- Seal có số 0 đầu giữ dạng text. Chuỗi giống công thức được xuất như văn bản.
- `Độ chính xác (%)` vẫn là tên cột tương thích và là điểm theo quy tắc, không phải độ chính xác vận hành đã đo.

## 4. Dùng bản mới

1. Giải nén 1.1.0 vào thư mục riêng. Giữ bản 1.0 và các file nghiệp vụ đang dùng để có thể đối chiếu.
2. Mở `START_HERE.html`; chạy `START.cmd` trên máy đã có Python phù hợp. Lần thiết lập đầu cần tải phụ thuộc hoặc chuẩn bị thư viện offline.
3. Chạy thử `samples/DEMO_<HANG>_INPUT.xlsx`, kiểm tra form và xuất bằng tên mới. Có thể thử **Mở phiên đã lưu** với JSON demo.
4. Đối với manifest thật, kiểm tra số container/BL, F/E, trọng lượng và các trường hợp cảnh báo trước khi xuất. Dùng bộ mẫu được Cảng chấp nhận để nghiệm thu nghiệp vụ.
5. Giữ cả Excel, review JSON và nguồn gốc tương ứng. Khi chỉ xuất Excel bằng `--no-review`, JSON cũ cùng tên, nếu có, không được cập nhật; nên dùng tên đích mới để tránh nhầm cặp.

## 5. Mức kiểm chứng của bản phát hành

**Đã thực hiện:** 191 tests, kiểm tra Python/biên dịch cú pháp, tạo lại demo, mở lại các phiên demo sau khi di chuyển thư mục, đối chiếu golden viết tay cho ba hãng, kiểm tra checksum và nội dung ZIP. Log, phiên bản thư viện và kết quả có trong [VALIDATION_REPORT.md](VALIDATION_REPORT.md), [validation_result.json](validation_result.json) và [TEST_OUTPUT.txt](TEST_OUTPUT.txt).

**Chưa thực hiện:** chạy giao diện native/EXE trên Windows và import vào hệ thống Cảng. Các test GUI gọi callback thật với widget giả và engine/file thật; không thay thế kiểm tra trực quan. Bộ golden là dữ liệu tổng hợp, chưa được Cảng xác nhận. XLS có giới hạn về kiểm tra cache công thức. Build PyInstaller chưa được pin theo một build Windows đã nghiệm thu; ghi phiên bản thực khi build để có căn cứ tái lập.

Các giới hạn này không phải finding đã bị bỏ qua trong mã. Chúng là phạm vi chưa có môi trường hoặc dữ liệu để nghiệm thu, được tách khỏi kết quả hồi quy đã đạt.
