# Quyết định giao diện Manifest Cleaner 1.2.7

**Phạm vi**  
Tkinter trên Windows, làm việc cục bộ. Tiếp tục luồng mở manifest, xem nguồn, sửa và xác nhận dòng, lưu phiên và xuất Excel đã mô tả trong [hướng dẫn GUI](GUI_V110.md).

**Nền và chữ**  
Dùng giao diện sáng tại cửa sổ ứng dụng, với nền trang `#F3F6F9` và bảng trắng. Xanh đậm dành cho thao tác chính và mục đang chọn. Đỏ và vàng sẫm đánh dấu lỗi và cảnh báo, xanh lục dành cho trạng thái thuận, xám đậm dành cho trạng thái không khả dụng. Mỗi trạng thái có nhãn hoặc số. Segoe UI 10 pt dùng cho nội dung và nút. Tên ứng dụng 15 pt, số tổng hợp 17 pt đậm. Mã kỹ thuật dùng Consolas 9 pt.

Chọn theme ttk `clam` tùy chỉnh vì theme Windows gốc lấy màu nền nút từ bộ vẽ của hệ điều hành, bỏ qua màu do ứng dụng đặt. Theme tùy chỉnh cho phép phân cấp nút đặc, nút viền và hành động loại dòng. Hộp chọn tệp và thư mục do Windows cung cấp.

**Màn chính và phản hồi**  
Thanh thao tác gọn nằm trên số liệu hiện tại, bộ lọc và hai bảng. Hàng nút và ô JSON luôn dành chỗ ở chân cửa sổ. Trạng thái và thanh tiến độ nằm cùng dòng với tên file. Hai số Lỗi chặn và Cảnh báo mở danh sách đã lọc. Bảng Container ghi số lỗi hoặc số cảnh báo, trạng thái xác nhận hoặc đã loại. Form dòng đã loại đọc lý do từ lịch sử phiên. Hai bảng hỗ trợ Ctrl+C dạng TSV.

Dòng tác giả luôn căn giữa chân cửa sổ và là dòng duy nhất ở đó. Ô kèm JSON nằm cạnh nút Xuất file Manifest. Phản hồi khi đang đọc, gặp lỗi hoặc hoàn tất thao tác lưu và xuất hiện bên phải tên file. Không có dòng nhắc lý do khóa Xuất: lỗi chặn hiện ở thẻ Lỗi chặn màu đỏ, đổi hãng hoặc đổi cấu hình hiện ở dòng trạng thái. Số dòng và cảnh báo sau khi đọc xong nằm ở dải tóm tắt và bảng đối chiếu.

Bảng rỗng phân biệt chưa mở tệp, bộ lọc rỗng và không có lỗi. Khi đọc nền, vùng bảng báo đang đọc. Khi lỗi đọc, hộp thoại nêu nguyên nhân và bước thử lại. Dòng tóm tắt chỉ nêu sheet khi tệp có nhiều sheet, và chỉ nêu quy ước đọc khi khác mặc định của hãng, như phiên cũ dùng trọng lượng hàng. Cấu hình chi tiết nằm trong hộp thoại Cấu hình đọc và JSON. Giữ luồng đọc nền hiện có. Worker gọi bộ đọc đến khi có kết quả và hiện chưa có tín hiệu hủy hợp tác hay cơ chế khôi phục phiên cũ nguyên tử. Vì vậy lượt này giữ nút thao tác hiện có. Sau khi xuất, nút **Mở thư mục kết quả** dùng đường dẫn thư mục thực từ kết quả xuất.

**Danh sách và chi tiết**  
Tab **Cần kiểm tra** nhóm theo mã vấn đề và hiện số lượng. Mỗi dòng con hiện container, mức, trường và địa chỉ `Sheet!A1` khi có đủ bằng chứng tọa độ. Khi thiếu cột, hiện tên sheet và số dòng đã biết. Panel bên phải có thể thu gọn. Một dòng hiển thị tiêu đề, container, B/L, nguồn, thông báo đầy đủ và giá trị thô nếu có. Một nhóm hiển thị số lượng và gợi ý mở từng dòng. Nút theo dòng chỉ khả dụng khi chọn vấn đề gắn với container. Lỗi toàn file có thể mở nguồn.

**Tinh chỉnh hướng A và số cont 20'/40', ngày 25-11-2026**  
Operator xem hai ảnh mô phỏng dữ liệu tổng hợp và chọn hướng A: giữ ttk `clam` và bảng màu hiện có, thêm thanh cuộn mảnh nếu chi phí thấp, không dùng thư viện `sv-ttk`. `sv-ttk` đổi nút chính sang xanh Windows và dùng ảnh nút cố định pixel không co theo DPI.

- Nút phụ có viền nhạt `#B4C1CE` và hiện viền xanh khi rê chuột. Hướng dẫn và Xóa bộ lọc là nút dạng chữ. Ô nhập và checkbox giữ viền `#8193A5` để đạt tương phản 3:1.
- Checkbox vẽ bằng ảnh theo mật độ màn hình: ô trắng viền xám, khi chọn có nền xanh đậm và dấu tích trắng.
- Thẻ số liệu nền trắng, viền mảnh, có sọc màu bên trái theo ý nghĩa. Lỗi chặn và Cảnh báo bằng 0 hiện số và sọc màu xám. Khi lớn hơn 0 thì đổi sang đỏ hoặc vàng. Nhãn hai thẻ này vẫn là nút mở danh sách đã lọc.
- Thẻ F và E ghi số cont theo thứ tự 20'/40', ví dụ `82 / 200`, chú thích `20'/40'`. Khi có cont 45', ghi ba số theo thứ tự 20'/40'/45', ví dụ `3 / 31 / 1`, chú thích `20'/40'/45'`. Thẻ Container giữ tổng số container khác nhau, dòng phụ ghi `20'/40'/45': 132/184/1`. Cỡ lấy từ mã VTOS: bắt đầu bằng 2 là 20', 40 hoặc 42 là 40', 45 hoặc ISO L5 là 45'. Cont 45' không gộp vào 40'. Dòng chưa rõ cỡ ghi riêng thành `chưa rõ cỡ n`. Số đếm theo cùng cách với phần thống kê của phiên. File xuất và JSON không đổi.
- Bảng có tiêu đề nền xanh nhạt chữ xanh đậm, dòng thường xen kẽ nền `#F7F9FB`, dòng đang chọn nền `#CFE3F4` chữ tối. Trạng thái dòng đủ dữ liệu là `✓`, cảnh báo `▲ n cảnh báo`, lỗi `✕ n lỗi`. Ctrl+C sao chép đúng chữ hiển thị.
- Thanh cuộn mảnh màu xám. Thanh tiến độ giữ chỗ bên phải dòng tên file, chỉ hiện màu khi đang đọc.

**Quyết định operator ngày 24-11-2026**  
Cột **Ghi chú** trong Excel 16 cột và JSON giữ nguyên câu thông báo đầy đủ. Tiêu đề ngắn chỉ dùng trong giao diện.

**Nguồn và kiểm thử**  
Suy ra từ `DESIGN.md` §1, §5, §8 và §12 Ops / Industrial. Pin đọc trước là commit `09c970f449f4806e7dbd852fa449dfe4fb6fcd30`. Repo CVF gốc tại lần đọc bổ sung ở commit `deeb2170a8f30477c6d51a6e70e6f98289d54959`, cho cùng Git blob `7a3a812f886c70b1c49f0fc630867f8936041ec7` theo `git hash-object DESIGN.md`. Chỉ dẫn `.cvf/runtime/workspace-advice/MANIFEST_CLEANER_UI_GUIDANCE.vi.md` có SHA-256 `802b773bd8bc2aeb19fe0e29e589fac85001e11af4a6f6e45e4a634ef05b3341`. Tài liệu gốc thuộc repo tham chiếu, quyết định triển khai nằm tại project.

Operator xác nhận ngày 25-11-2026 không cần thử giao diện riêng trên máy ở Cảng vì EXE chạy offline như nhau. Khác biệt còn lại giữa các máy là tỷ lệ hiển thị và độ phân giải, đã kiểm ở 100%, 125% và 150%. Sau khi có EXE đã review, dùng mẫu tổng hợp mở đủ ba hãng, thu cửa sổ, lọc và sửa thử một dòng, lưu/mở lại JSON, xuất vào đường dẫn tiếng Việt, mở thư mục kết quả và đối chiếu 16 cột. Sau đó kiểm có kiểm soát một tệp được phép nhập Cảng. [Hồ sơ phép thử trên máy phát triển](reviews/ui-1.2.7/README.md)
