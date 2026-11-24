# VINAFCO: nguồn kế thừa và các thay đổi

> Tài liệu nền của bản 1.0.0. Thay đổi bổ sung trong bản 1.1.0: [VINAFCO_FIXES_V110.md](VINAFCO_FIXES_V110.md) và [RELEASE_NOTES_V1_1.md](RELEASE_NOTES_V1_1.md).

## Phạm vi

Adapter kế thừa quy tắc nghiệp vụ và bảng ánh xạ từ repo `CVF-Ecosystem/Manifest-Cleaner_VINAFCO`, nhánh `cvf-next`, commit `e743b7325bdb95ff5a72c9a9f985a41ad08b04f0` (10-09-2026).

Nguồn: https://github.com/CVF-Ecosystem/Manifest-Cleaner_VINAFCO/tree/e743b7325bdb95ff5a72c9a9f985a41ad08b04f0

Người dùng chọn **VINAFCO** trong ứng dụng chung. Adapter không đọc tên tàu, tên chuyến hoặc tên file để chọn quy tắc. Mỗi lần xử lý một file Excel. Bộ xuất dùng chung phụ trách đúng thứ tự cột và định dạng nhập cảng.

Dữ liệu chuẩn và màn hình đối chiếu giữ mô tả đã đọc để kiểm tra. Riêng file nhập cảng vẫn có thể dùng nhãn `EMPTY` cho container E theo hợp đồng xuất của ứng dụng cũ; mô tả nguồn vẫn nằm trong bản đối chiếu.

## Quy tắc được giữ

- Cấu trúc party theo các nhãn `(S)`, `(C)`, `(N)`; mỗi nhóm shipper là một nhóm B/L nguồn.
- Operator mặc định `VFC` cho COC và `SVF` cho SOC. SOC được kiểm tra ở shipper, mô tả và ghi chú bằng từ/ký hiệu đầy đủ, tránh nhận nhầm chuỗi nằm trong một từ khác.
- Bảng kích cỡ VTOS từ bản cũ, gồm các ánh xạ riêng như `40GP → 40HC`, `22R1 → 22R0`, `45R1 → 45RH`. Đây là bảng phục vụ đầu ra của cảng, không phải tuyên bố chuẩn hóa mọi nhãn thành mã ISO.
- F/E theo chính sách gross/tare cũ khi không có trạng thái tường minh: 20 ft 2,3 tấn; 40 ft 3,8 tấn; 45 ft 4,5 tấn; reefer 20 ft 3,0 tấn và 40 ft 4,8 tấn. Mọi suy luận F/E đều kèm cảnh báo. Các ngưỡng này là cấu hình, không được mô tả là trọng lượng vỏ cân thực tế.
- Giữ riêng `Size_Type` nguồn và `VTOS_Size` đầu ra. Tên chủ hàng lấy dòng đầu và cắt thông tin liên hệ như bản cũ. Mô tả hàng được viết hoa/bỏ dấu như quy trình nguồn; bản có dấu luôn lưu trong `raw`.

## Lỗi đã sửa

1. **Trọng lượng:** dùng bộ đọc số và đơn vị chung. `25,000 KGS` thành 25 tấn; `25.000,50 KGS` và `25,000.50 KGS` thành 25,0005 tấn. Không làm tròn sớm, không biến giá trị không đọc được thành 0. Số Excel dạng numeric không bị diễn giải lại theo locale.
2. **Đơn vị trong tiêu đề:** `GW (KGS)` được nhận đúng là kg; đơn vị ghi rõ ở từng ô vẫn do bộ đọc chung xử lý. Khi không có đơn vị trong ô/tiêu đề, cấu hình đơn vị mặc định thực sự được áp dụng.
3. **Không mất container khi thiếu chủ hàng:** mọi container đã phát hiện được giữ lại; thiếu consignee, B/L hoặc trọng lượng là lỗi cần bổ sung. Không lọc mất dòng như bản cũ.
4. **B/L ở dòng shipper/ô gộp:** B/L được lấy từ mọi dòng trong nhóm, không chỉ dòng container; không tràn thông tin sang nhóm shipper tiếp theo. Chỉ điền ngược một B/L còn thiếu khi cả nhóm có đúng một B/L duy nhất.
5. **Header linh hoạt:** chuẩn hóa khoảng trắng, xuống dòng, chữ hoa/thường trước khi dò; cột không cần bắt đầu ở A/B. Không tự chọn giữa hai cột trọng lượng có thể cùng khớp.
6. **Nhiều sheet:** quét các sheet; nếu nhiều bảng manifest có dữ liệu thì dừng với lỗi rõ ràng. Có thể chọn sheet bằng `target_sheet_name`. Sheet mẫu chỉ có header không gây nhầm với manifest có dữ liệu.
7. **Rỗng có dấu và hàng hóa chứa từ EMPTY:** `RỖNG` được nhận đúng; `EMPTY BOTTLES` không bị coi là một nhãn trạng thái rỗng. Không thay mô tả gốc thành `EMPTY` khi F/E được suy luận.
8. **Mâu thuẫn F/E:** giữ trạng thái tường minh trong nguồn, đồng thời phát lỗi nếu trọng lượng dẫn tới suy luận trái ngược. Không tự giấu bất đồng bằng cách đổi trạng thái rồi ghi đè mô tả.
9. **Reefer:** `22R1`, `22R0` và các mã đầu ra tương ứng được phân loại cargo nhất quán. Độ dài vật lý của mã ISO dùng cho ngưỡng tare được tách khỏi nhãn VTOS đầu ra.
10. **Dấu vết nguồn:** mỗi record có tên file, sheet, dòng Excel, giá trị gốc, party block và các quy tắc đã áp dụng. Container không đúng mẫu vẫn hiện để sửa, không bị bỏ qua.
11. **Chỉ số tương thích:** trường `Confidence` là điểm hoàn chỉnh/suy luận kiểu cũ, không phải độ chính xác được đo. Điểm giảm khi phải mặc định/suy luận F/E, thiếu trường hoặc có lỗi. Quyết định được xuất file dựa trên validation, không dựa vào điểm này.
12. **Chỉnh sửa thủ công:** `refresh_derived_fields` chỉ tính lại kích cỡ VTOS và loại hàng từ kích cỡ/F/E đang chọn; giữ nguyên F/E, mô tả và operator người dùng đã nhập. `is_supported_size_type` cho lớp kiểm tra chung biết kích cỡ có đủ ánh xạ đã xác nhận hay chưa. Lỗi mâu thuẫn F/E yêu cầu đối chiếu cả F/E lẫn trọng lượng trước khi giải quyết.

## Cấu hình được hỗ trợ

Ứng dụng chung truyền một dictionary cấu hình cho riêng VINAFCO; adapter không tự nạp `config.ini` của ứng dụng cũ. Các phần INI cũ không hoạt động như `[VimcSpecific]`, regex tùy ý và định dạng Excel không được chuyển vào adapter VINAFCO. Định dạng thuộc bộ xuất dùng chung; VIMC có adapter riêng.

| Khóa | Tác dụng |
|---|---|
| `target_sheet_name` | Chọn một sheet cụ thể khi workbook có nhiều manifest |
| `peek_rows` | Số dòng đầu để dò header, mặc định 80 |
| `col_party_raw`, `col_bill_no`, `col_container_no`, `col_seal`, `col_type`, `col_comm`, `col_gw`, `col_remarks` | Bổ sung tên cột nguồn tương ứng |
| `operator_soc`, `operator_coc` | Mã hãng khai thác, mặc định SVF/VFC |
| `default_weight_unit` | Đơn vị mặc định khi nguồn không ghi, mặc định TONS |
| `number_format` | `legacy`, `decimal_comma`, `decimal_dot` |
| `weight_kind` | `gross` cho lần đọc manifest mới. Phiên đã lưu giữ quy ước xử lý ban đầu |
| `tare_20ft`, `tare_40ft`, `tare_45ft`, `tare_20rf`, `tare_40rf`, `tare_45rf` | Ngưỡng tare theo tấn |
| `min_payload`, `safety_margin` | Ngưỡng và biên độ cho chính sách gross cũ, mỗi giá trị mặc định 0,1 tấn |
| `cargo_weight_empty_threshold` | Trường tương thích cấu hình và phiên cũ |
| `size_to_vtos` hoặc `size_to_iso` | Dictionary bổ sung/ghi đè ánh xạ kích cỡ VTOS |
| `cargo_type_mapping` hoặc `size_type_to_cargo_type_base` | Dictionary bổ sung/ghi đè loại hàng cơ bản |

Các tên cũ vẫn được chấp nhận: `default_weight_unit_if_missing`, `tare_20ft_empty_vgm`, `tare_40ft_empty_vgm`, `tare_20rf_empty_vgm`, `tare_40rf_empty_vgm`, `min_payload_for_f_vgm`, `safety_margin_tons`. Nếu đồng thời khai báo tên mới và tên cũ, tên mới được ưu tiên.

## Kiểm chứng và giới hạn

Chạy: `python -m unittest discover -s tests -p test_vinafco.py -v`.

Các ca hồi quy tạo XLSX tổng hợp để kiểm tra parse số, header di chuyển/xuống dòng, B/L ở dòng shipper, không làm mất container thiếu consignee, cấu hình đơn vị/ngưỡng/mapping/operator, F/E có dấu/mâu thuẫn, reefer, giữ mô tả khi chỉnh sửa, nhiều sheet, file XLSX mang đuôi XLS, và số B/L/seal có số 0 đầu được định dạng trong Excel.

Repo nguồn không kèm manifest nghiệp vụ thật hoặc output đã được cảng xác nhận. Vì vậy bộ kiểm thử chứng minh các lỗi đã nêu được sửa và giữ các hợp đồng dữ liệu nêu trên; chưa thay thế việc đối chiếu input/output thật của người dùng. Không tự hứa hỗ trợ PDF/ảnh/OCR hoặc mọi mẫu manifest VINAFCO chỉ vì chúng cùng tên hãng. Trùng container/B/L và đối soát đa trường được xử lý tại lớp validation chung, không xóa dữ liệu trong adapter.
