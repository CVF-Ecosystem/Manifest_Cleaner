# Giao diện và đối chiếu dữ liệu — 1.1.0

Ứng dụng vẫn chạy local, mỗi phiên xử lý một manifest của một hãng tàu. Từ 26-11-2026 (MC3), file nhập Cảng theo mẫu import TOS (Template_LuocKhaiHangHoa) dùng chung cho cả ba hãng.

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
- Giá trị sẽ ghi vào file theo mẫu TOS, theo đúng hàm tạo dữ liệu của exporter.
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

Khi xuất Excel, tùy chọn **Kèm đối chiếu JSON** cạnh nút **Xuất file Manifest** mặc định được bật. File JSON dùng để mở lại phiên. Ví dụ:

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

## Danh sách Gần đây

Khi chưa mở file, vùng bảng hiện mục **Gần đây** gồm tối đa 5 manifest đã đọc, của mọi hãng, mới nhất ở trên. Mỗi dòng ghi tên file, hãng, số container lúc đọc và ngày đọc. Số container là số lúc đọc, không cập nhật theo file.

- Bấm một mục để mở lại bằng đúng hãng đã dùng cho file đó. Ô **Hãng tàu** tự chuyển theo. Quy tắc của hãng khác không bao giờ được áp lên file này.
- Danh sách chỉ ghi file đọc thành công. File có nhiều bảng chỉ được ghi sau khi chọn sheet. Mở lại phiên đối chiếu JSON không thêm vào danh sách, vì bấm mục sẽ đọc lại manifest từ đầu, không khôi phục chỉnh sửa.
- File đã bị xóa hoặc di chuyển: app báo, bỏ mục đó khỏi danh sách và không mở gì. Đường dẫn chỉ được kiểm tra lúc bấm.
- **Xóa danh sách** xóa toàn bộ. Danh sách nằm trong `recent_files.json` cạnh `settings.json`, chỉ ở máy này và không đưa lên Git. Thư mục không ghi được hoặc file hỏng thì danh sách trống, app vẫn chạy bình thường.
- Cửa sổ thấp hiện ít dòng hơn cho vừa vùng bảng, tối thiểu một dòng.

## Thẻ SOC / COC

Thẻ thứ 7 ghi `số dòng SOC / số dòng COC`, đếm theo dòng như thẻ F và E. App đọc mã hãng khai thác mà quy tắc của hãng đã ghi: VOSCO là SVC/VOC, VIMC là SVM/VMC, VINAFCO là SVF/VFC. Nếu `settings.json` của hãng đặt `operator_soc` hoặc `operator_coc`, app dùng mã trong cấu hình. Dòng có mã khác cả hai được ghi riêng thành `khác n` và không gộp vào bên nào.

## Xem trước file Manifest

Nút **Xem trước…** cạnh **Lưu đối chiếu…** mở bảng các cột app điền vào file mẫu TOS, theo thứ tự TOS, cùng STT và Ghi chú chỉ hiện trên app: seal dạng văn bản, trọng lượng đã quy đổi và làm tròn, mã VTOS, mã ISO và loại hàng theo TOS. File Excel để trống Ghi chú. Bản xem trước dùng chung hàm dựng dòng với lệnh xuất, nên hai bên khớp từng ô.

- Ô **Lọc** tìm trong mọi cột. Dòng đếm ghi tổng, số đang hiện, F và E.
- Màu theo file Excel: nền vàng là dòng có cảnh báo, nền xanh là container rỗng, chữ nâu là dòng có ô container hoặc seal được tô vàng.
- Khi còn lỗi chặn, vẫn xem trước được. Dòng còn lỗi có nền đỏ, nút xuất trong cửa sổ bị khóa và ghi rõ lý do.
- **Xuất file Manifest…** trong cửa sổ đóng bản xem trước rồi chạy lệnh xuất như bình thường. Esc để đóng. Ctrl+C sao chép dòng đang chọn.

## Phóng to cửa sổ phụ

Các cửa sổ phụ có nút phóng to/khôi phục cạnh nút đóng, và bấm đúp thanh tiêu đề cũng phóng to. Nút thu nhỏ màu xám vì cửa sổ phụ khóa cửa sổ chính cho tới khi đóng.
