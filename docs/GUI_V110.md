# Giao diện và đối chiếu dữ liệu — 1.1.0

Ứng dụng vẫn chạy local, mỗi phiên xử lý một manifest của một hãng tàu. File nhập Cảng giữ đúng mẫu 16 cột theo hãng.

## Các thay đổi người dùng nhìn thấy

### 1. Sửa một trường không tự xác nhận cả dòng

Cửa sổ **Chỉnh sửa / xác nhận** có ô **Đã đối chiếu trường này** cạnh từng trường. Khi lưu:

- Trường thực sự thay đổi được gửi để cập nhật.
- Trường giữ nguyên chỉ được xác nhận khi người dùng tích đúng ô của trường đó.
- Chỉ mở rồi lưu form không làm mất lỗi, không tự xác nhận F/E, trọng lượng hoặc mô tả.
- Lý do sửa hoặc căn cứ xác nhận là bắt buộc.
- Trường liên quan lỗi/cảnh báo được đánh dấu `*` và có nhãn nổi bật.

Ví dụ: sửa số niêm chì không còn làm mất lỗi “nhóm vận đơn ghi rỗng nhưng dòng container có mô tả hàng”. Nếu F/E thực sự đúng, người dùng phải xác nhận chính trường F/E và ghi căn cứ.

### 2. Nút thao tác dùng dòng được chọn trong tab đang mở

Trong tab **Cần kiểm tra**, các nút **Xem / sửa dòng**, **Đã đối chiếu**, **Loại / khôi phục dòng** áp dụng cho container của lỗi đang chọn. Selection cũ ở tab Container không được dùng thay thế.

Nếu chọn lỗi toàn file, các nút theo dòng bị vô hiệu hóa. Lỗi toàn file vẫn có thể được mở bằng nhấp đúp để đọc thông báo. Dialog xác nhận hoặc loại dòng hiển thị rõ số container và B/L.

Số lỗi trong phần tổng hợp phân biệt:

- Số lỗi theo dòng và số container có lỗi.
- Số lỗi toàn file.
- Số cảnh báo.
- Số container duy nhất, số dòng đang giữ và số dòng đã loại.

### 3. Đối chiếu nguồn với giá trị sẽ ghi vào Excel

Trong cửa sổ sửa, mở tab **Nguồn và giá trị sẽ xuất** để xem:

- Nguyên văn dòng/ô nguồn khi adapter có lưu thông tin này.
- Bằng chứng nguồn theo từng cột.
- Giá trị sẽ ghi vào mẫu 16 cột, theo đúng hàm tạo dữ liệu của exporter.
- Chỗ quy đổi kích cỡ, làm tròn trọng lượng và nhãn hàng `EMPTY` có thể được nhìn thấy trước khi xuất.

Sau khi sửa ô nhập, bấm **Cập nhật xem trước theo các ô đang sửa**. Xem trước không tự lưu chỉnh sửa và không bỏ qua các lỗi chặn xuất.

Phần **Hiện dữ liệu kỹ thuật (JSON)** được thu gọn, dành cho người cần kiểm tra sâu nguồn, quy tắc và mã lỗi.

Nút **Tra nguồn** ở cửa sổ chính mở các đoạn nguồn mà bộ đọc đã ghi nhận, gồm vị trí, nguyên văn và lý do nhận diện/bỏ qua/chờ đối chiếu. Trạng thái trong cửa sổ này được ghi rõ là **tại lần đọc nguồn**; nó không thay thế danh sách lỗi hiện tại sau khi người dùng sửa dữ liệu. Chọn một dòng để đọc toàn bộ nội dung dài. Với bộ đọc chưa có danh sách đoạn nguồn, ứng dụng thông báo rõ và vẫn cho xem nguồn tại từng container.

### 4. Dòng VIMC có hai cách đọc

Khi adapter trả về hai cách đọc trọng lượng/mô tả, form hiển thị các phương án nhưng không tự chọn. Người dùng đối chiếu nguồn, chọn phương án rồi bấm **Điền và xác nhận 2 trường**.

Thao tác này điền trọng lượng đã đổi sang tấn, mô tả tương ứng và tích xác nhận hai trường liên quan. Vẫn phải ghi căn cứ và lưu; chỉ mở danh sách không giải quyết lỗi. Người dùng cũng có thể nhập từng trường thủ công.

### 5. Cấu hình hiệu lực được hiển thị

Phía trên bảng có thông tin về quy ước số, ý nghĩa trọng lượng, sheet và bộ quy tắc đang dùng. **Cấu hình đọc** cho phép sửa:

- Quy ước số của dữ liệu dạng chữ.
- Ý nghĩa trọng lượng: chưa xác nhận, tổng trọng lượng hoặc trọng lượng hàng.
- Sheet cần xử lý; có thể chọn từ tên sheet đã đọc hoặc nhập chính xác tên.

Lưu lại đúng cấu hình hiện tại không vô hiệu hóa phiên. Khi có thay đổi, người dùng cần lưu đối chiếu nếu muốn giữ công việc đang sửa, sau đó chủ động xử lý lại nguồn. Cấu hình mới không tự thay dữ liệu đã được người dùng chỉnh sửa.

## Lưu và mở lại công việc

### Lưu phiên

**Lưu đối chiếu** ghi file JSON có dữ liệu nguồn, kết quả, lỗi, lịch sử sửa/xác nhận/loại và cấu hình của phiên.

Khi xuất Excel, tùy chọn **Xuất kèm đối chiếu JSON để mở lại phiên** mặc định được bật. Ví dụ:

```text
manifest_VIMC_CLEAN.xlsx
manifest_VIMC_CLEAN.review.json
```

Nếu một file trong bộ đã tồn tại, ứng dụng yêu cầu xác nhận trước khi ghi đè. Xuất thành công cả bộ thì phiên được đánh dấu đã lưu. Nếu tắt xuất kèm JSON, các chỉnh sửa chưa lưu đối chiếu vẫn được bảo vệ bằng cảnh báo khi đóng hoặc mở phiên khác.

### Mở lại phiên

1. Bấm **Mở phiên đã lưu** và chọn JSON đối chiếu được hỗ trợ.
2. Ứng dụng kiểm tra đúng manifest gốc bằng dấu kiểm tra SHA-256.
3. Nếu file gốc đã di chuyển, chọn lại file có cùng nội dung.
4. Phiên khôi phục các chỉnh sửa, xác nhận, dòng đã loại và cấu hình đã lưu. Không chạy lại parser để thay thế các chỉnh sửa.

File nguồn đã thay đổi nội dung không được dùng để mở lại phiên cũ. JSON không hợp lệ cũng không được bỏ qua bằng cách chọn một nguồn khác. Mở phiên thất bại giữ nguyên phiên hiện tại.

## Kiểm thử và giới hạn

`tests/test_gui_v110.py` có 16 kiểm thử gọi callback thật của GUI với widget giả, sử dụng engine, adapter, exporter và file thực. Các ca kiểm thử tập trung vào hai lỗi đã audit, xác nhận từng trường, chọn cách đọc VIMC, khôi phục phiên, chuyển vị trí nguồn, xuất kèm đối chiếu và cấu hình không thay đổi. Xem trước phải phản ánh cả các ô chưa lưu mà không làm thay đổi session; bảng tra nguồn phải phân biệt trạng thái lúc đọc với lỗi hiện tại.

Các kiểm thử này xác minh logic, không thay thế kiểm tra trực quan Tkinter hoặc chạy EXE trên Windows. Trước bàn giao vận hành, kiểm tra trên máy sử dụng: màn hình/DPI, đường dẫn tiếng Việt, file Excel đang mở, thư mục hạn chế quyền ghi và quá trình mở lại phiên đã lưu.
