# VIMC: những phần đã giữ và sửa trong ứng dụng hợp nhất

> Tài liệu nền của bản 1.0.0. Thay đổi bổ sung trong bản 1.1.0: [CARRIER_FIXES_V110.md](CARRIER_FIXES_V110.md) và [RELEASE_NOTES_V1_1.md](RELEASE_NOTES_V1_1.md).

Ngày thực hiện: 22-11-2026.

Nguồn tham chiếu: `CVF-Ecosystem/Manifest-Cleaner_VIMC`, nhánh `main`, commit `03e0d34e3fe4a27d8d2ce0d54d96ea9275370436`.

## 1. Cách chọn và xử lý

Người dùng chọn **hãng tàu VIMC** rồi chọn **một file manifest** cho mỗi lần xử lý. Không có danh sách tên tàu; tên file và tên tàu không quyết định bộ đọc.

Adapter nhận dạng cấu trúc từng dòng container:

| Dạng nguồn đã hỗ trợ | Quy ước trọng lượng nguồn |
|---|---|
| Container – seal – kích cỡ – trọng lượng – mô tả | Tấn, kế thừa dạng Hải Phòng/PIONEER cũ |
| Container – seal – kích cỡ – mô tả – trọng lượng | Kg, kế thừa dạng MARINER/Đà Nẵng cũ |
| Container trong MARKS kèm trạng thái rỗng rõ ràng | Có thể thiếu trọng lượng; không tự đặt bằng 0 |

Các dạng này được phép xuất hiện chung trong một manifest. Nếu một dòng có thể đọc theo cả hai vị trí trọng lượng, ứng dụng giữ nguyên dòng và yêu cầu kiểm tra; không dùng tên tàu để chọn một đáp án.

## 2. Những quy tắc cũ được bảo tồn

- Nhận diện bảng qua các cột thông tin chủ hàng, MARKS & NUMBERS và DESCRIPTION/DISCRIPTION/PACKAGES trong 20 dòng đầu.
- Nhận diện nhóm `B/L NO:`; lấy số vận đơn từ cột thứ ba như nguồn cũ, bổ sung cách ghi số ngay cạnh nhãn khi cột thứ ba trống.
- Tách shipper, consignee, notify theo `1)`, `2)`, `3)` và xử lý `SAME AS CONSIGNEE`.
- Giữ các biểu thức chính quy cũ thành hàm tương thích để kiểm thử các ví dụ đang hoạt động.
- SOC dùng mã khai thác `SVM`; COC dùng `VMC`.
- Giữ bảng ánh xạ kích cỡ sang VTOS hiện có, bao gồm các quy ước địa phương như `40GP → 40HC`. Đây là **mã xuất của quy trình hiện tại**, không thay đổi mã vật lý gốc.
- Giữ tank → `GENERAL`; tank rỗng → `EMPTY`.
- Giữ khả năng đọc XLSX được đặt nhầm đuôi `.xls` thông qua chữ ký file ở bộ đọc chung.
- Đơn vị nội bộ là tấn; không làm tròn trước khi xuất.

## 3. Các finding đã sửa

| Vấn đề nguồn cũ | Cách xử lý mới |
|---|---|
| Chọn parser dựa vào tên tàu/file | Chỉ chọn VIMC; nhận dạng cấu trúc từng dòng |
| Dòng container không parse được biến mất | Trả về record với raw/source và lỗi cần kiểm tra |
| Container thiếu consignee bị loại | Giữ record; đánh dấu thiếu chủ hàng |
| Bỏ qua mô tả/marks ở dòng party sau B/L | Đọc cả thông tin party và container tại dòng đó |
| `EMPTY BOTTLES` khiến cả B/L thành rỗng | Chỉ nhận dạng cụm trạng thái rỗng rõ ràng; giữ nguyên tên hàng |
| Một dòng rỗng ảnh hưởng các dòng có hàng trong B/L | Trạng thái trên dòng chỉ áp dụng cho dòng đó; tiêu đề nhóm áp dụng từ vị trí xuất hiện trở về sau |
| Dùng trọng lượng hàng so với tare để suy ra rỗng | Không suy ra E từ ngưỡng 3/5 tấn; hàng nhẹ vẫn giữ mô tả và trạng thái có hàng |
| 0 bị coi là thiếu trọng lượng | Phân biệt 0 với None; 0 giữ đơn vị tấn |
| Dòng lặp làm tăng số lượng mà không cảnh báo | Giữ dòng, cảnh báo theo cặp B/L–container; khác B/L không bị tự xóa |
| Trùng MARKS và dòng chi tiết có thể gây hiểu nhầm | Đối chiếu cùng container và lưu cả hai bằng chứng; không xuất MARKS thành container thứ hai |
| Mã vật lý và VTOS trộn trong một trường | Giữ `Size_Type`, `Physical_ISO_Size`, `VTOS_Size` riêng biệt |
| Chỉ đọc sheet đầu tiên | Đọc các sheet có bảng VIMC; sheet bìa không chứa container được bỏ qua |

Nếu một tiêu đề ghi rỗng nhưng dòng có mô tả hàng, ứng dụng giữ mô tả và tạo lỗi mâu thuẫn để kiểm tra. Không biến mô tả hàng thành `EMPTY` chỉ vì một suy diễn.

## 4. Hợp đồng dữ liệu và xuất file

Adapter cung cấp:

```python
parse_manifest(path, *, settings=None, progress=None)
refresh_derived_fields(record, settings=None)
```

`parse_manifest` trả `records`, `issues`, `metadata`. Mỗi record giữ file, sheet, dòng Excel, cột/đoạn nguồn, chuỗi ban đầu, các giá trị gốc, mẫu đã dùng và các quy tắc áp dụng. Các trường nguồn không bị thay thế khi sửa dữ liệu qua giao diện.

`refresh_derived_fields` tính lại mã ISO vật lý, VTOS và loại hàng sau khi người dùng sửa kích cỡ hoặc F/E. Hàm không suy diễn lại F/E, không ghi đè mô tả hàng và không thay operator đã có.

Trình xuất chung tiếp tục sử dụng **16 cột VIMC thực tế**, đúng thứ tự:

1. STT
2. Số Vận Đơn
3. Số Container
4. Số niêm chì
5. Số niêm chì 1
6. Chủ hàng
7. Kích cỡ
8. Loại Container
9. Hãng khai thác
10. Loại hàng
11. F/E
12. Trọng lượng (Tấn)
13. Hàng hóa
14. Số lượng
15. Độ chính xác (%)
16. Ghi chú

`Kích cỡ` và `Loại Container` lấy mã VTOS theo quy trình cũ; mã nguồn/ISO vật lý vẫn được giữ trong bản ghi kiểm tra. Cột `Độ chính xác (%)` chỉ được giữ để tương thích mẫu xuất; đó là điểm quy ước theo cách nhận dạng, không phải tỷ lệ chính xác đã đo trên dữ liệu thực tế. Việc chấp nhận xuất dựa trên các lỗi/cảnh báo cần kiểm tra.

## 5. Kiểm thử đã chạy

```bash
python -m unittest tests.test_vimc -v
```

**25 test pass** tại thời điểm hoàn thành adapter. Bộ kiểm thử gồm các ví dụ parser cũ và file XLSX tổng hợp, kiểm tra luồng đọc workbook đến canonical records:

- Ba dạng nguồn trộn trong cùng manifest; thay filename MARINER/PIONEER không thay kết quả.
- Dòng mơ hồ có số ở cả hai đầu phần hàng/trọng lượng.
- Container không đọc đủ, thiếu consignee, thiếu header.
- `EMPTY BOTTLES`, hàng nhẹ, trọng lượng 0, phạm vi áp dụng của nhóm rỗng.
- Tiêu đề SOC xuất hiện sau không thay operator của container ở phía trước.
- Empty trong MARKS, MARKS thiếu chi tiết của container có hàng, đối chiếu MARKS với detail.
- Dòng lặp cùng B/L và container liên quan nhiều B/L.
- Tách mã vật lý/VTOS, giữ tank → GENERAL.
- Container nằm ngay ở dòng party; bảng cũ ba cột; manifest nằm sau sheet bìa.
- Quy ước số có dấu chấm/phẩy, giữ độ chính xác trước xuất, XLSX đổi đuôi XLS.
- Sửa dữ liệu rồi tính lại trường dẫn xuất mà không ghi đè hàng hóa/F/E.

Không dùng dữ liệu manifest thực tế ngoài repo để khẳng định tỷ lệ chính xác. Các trường hợp nghiệp vụ mới vẫn có thể cần bổ sung parser hoặc cấu hình; việc đó không đòi hỏi tách thành ứng dụng khác. Bộ test tổng hợp đã đủ để kiểm chứng các lỗi cụ thể và tiếp tục triển khai, không đặt yêu cầu cung cấp mẫu thành điều kiện chặn sử dụng.
