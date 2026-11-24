# Bản sửa sau audit — Manifest Cleaner Unified 1.0.0

> Nhật ký lịch sử của bản 1.0.0, được giữ để truy nguồn. Kết quả audit độc lập và các sửa đổi mới thuộc bản 1.1.0 được ghi trong [RELEASE_NOTES_V1_1.md](RELEASE_NOTES_V1_1.md); kết quả kiểm thử hiện tại ở [VALIDATION_REPORT.md](VALIDATION_REPORT.md).

Ngày: 22-11-2026. Căn cứ là mã nguồn ba repo tại commit trong `SOURCE_PROVENANCE.json` và các yêu cầu được người dùng chốt.

## Quyết định phạm vi

Một app local; một manifest/một hãng mỗi phiên; menu chọn VOSCO, VIMC, VINAFCO. Hải Phòng/Đà Nẵng là các biến thể nguồn của VIMC, nhận dạng từ cấu trúc nội dung. Tên tàu không còn là khóa chọn parser. Dùng các quy tắc có sẵn làm nền, sửa lỗi đã xác minh, giữ các hợp đồng xuất thực tế trong source.

## Ma trận finding → thay đổi → bằng chứng

| Finding | Thay đổi đã triển khai | Kiểm chứng |
|---|---|---|
| VOSCO/VINAFCO đọc sai dấu phân cách và đơn vị | Helper số chung, quy ước theo hãng, đổi về tấn một lần, giữ số Excel native | `test_common`, các tests số của VOSCO/VINAFCO |
| VOSCO một trọng lượng bị lặp cho nhiều container | Giữ vị trí từng dòng trọng lượng; quan hệ thiếu/mơ hồ thành lỗi từng record | `test_single_weight_is_not_reused_for_two_containers`, `test_invalid_weight_retains_position` |
| Thiếu consignee làm mất container | Giữ record; lỗi trường bắt buộc trong phiên; sửa/loại phải có lý do | Tests thiếu consignee của cả ba hãng và integration |
| VOSCO loại tên chứa PORT, | Bỏ bộ lọc làm mất record | `test_blank_and_port_named_consignees_do_not_remove_containers` |
| Container chưa parse biến mất | Placeholder có record_id/raw/source; cho phép hoàn thiện hoặc loại có lý do | Tests unparsed của ba hãng, VOSCO correction/exclusion |
| BL sai/khác hàng bị gắn nhầm | Tách ranh giới BL, giữ BL tại shipper/ô gộp và không điền qua nhóm khác | Tests BL của VOSCO/VINAFCO |
| EMPTY BOTTLES làm container có hàng bị E | Chỉ nhận cụm trạng thái container rõ ràng; áp theo đúng phạm vi | Tests empty-status chung/VIMC/VINAFCO |
| VIMC dùng trọng lượng hàng so với tare | Bỏ phép suy luận sai nghĩa này trong VIMC; khối lượng nhẹ vẫn F nếu có hàng | `test_light_cargo_is_not_empty_by_tare_threshold` |
| Zero bị coi là thiếu | Kiểm tra None riêng, giữ zero và đơn vị | `test_zero_retained_and_scoped_empty` |
| Tare tank VOSCO không được dùng | Dùng bảng tare tank; hiển thị mâu thuẫn giữa trọng lượng và trạng thái | Tests tank/explicit empty VOSCO |
| Confidence 100 khi fallback hoặc thiếu dữ liệu | Giảm điểm/hình thành issue; UI dùng trạng thái kiểm tra; tên cột legacy giữ vì tương thích | Tests thiếu mô tả và trường thiếu; tài liệu giải thích điểm theo quy tắc |
| ISO/VTOS và loại hàng trộn ý nghĩa | Giữ mã nguồn và VTOS riêng; sửa reefer aliases; giữ tank→GENERAL riêng VIMC | Tests mapping/refresh của ba hãng |
| Cấu hình VINAFCO không vào luồng chạy | Nối unit, tare, margin, mappings, operator, sheet và aliases cấu hình vào adapter | Tests configuration/header unit VINAFCO |
| Header VINAFCO có xuống dòng/dịch cột bị từ chối | Chuẩn hóa trước khi nhận diện, tìm cột bằng nhãn | Tests relocated/multiline header |
| Trùng container/tổng số lượng | Giữ quan hệ BL–container, cảnh báo/chặn bản sao chưa đối chiếu; đếm distinct trong nhóm legacy | Integration duplicate, multiple BL, master-group quantity |
| Seal 6 và 7 số bị đánh giá khác nhau | Một quy tắc cảnh báo 6–7 số cho mẫu legacy, không xóa seal chữ/số; Excel đánh dấu cùng quy tắc | Integration schema/types và kiểm tra exporter |
| Core phụ thuộc Tk và trùng tên package | Namespaces theo carrier; API headless; GUI dùng worker queue, Tk chỉ ở thread chính | Import/CLI/integration; đọc mã GUI |
| Đổi quy ước số vẫn xuất dữ liệu cũ | Engine gắn lỗi SETTINGS_CHANGED; GUI và exporter chặn đến khi đọc lại | `test_changed_settings_block_export_until_reprocessing` |
| Xác nhận chung có thể bỏ qua lỗi | Acknowledge chỉ giải quyết cảnh báo; lỗi cần xác minh các trường liên quan | `test_acknowledgement_does_not_remove_unresolved_weight_error` |
| Sửa một trường làm hết lỗi liên quan nhiều trường | `resolution_fields` yêu cầu đủ weight+description hoặc F/E+weight | Tests coupled ambiguity |
| Nhập kích cỡ/mã operator tùy ý vẫn xuất | Validator hãng kiểm tra bảng mã; mã chưa biết bị chặn | Integration unknown size; review safety unknown operator |
| Tiêu đề SOC/EMPTY ảnh hưởng ngược dòng trước | VIMC áp trạng thái theo thứ tự nguồn | Tests later-owner/later-empty headings |
| Định dạng số có 0 đầu mất trong XLS thật | Đọc formatting bằng xlrd và giữ các format thuần `000000` | Fixture BIFF8 thật và `test_true_xls_preserves_formatted_identifier_and_native_number` |

## Hành vi có chủ ý được giữ

- Bảng mã VTOS và mã operator của các repo là căn cứ hiện tại. Các chuyển đổi như `40GP→40HC` được giữ ở lớp mapping xuất; không coi đó là chuyển đổi vật lý phổ quát.
- VIMC tank xuất GENERAL; VOSCO/VINAFCO theo bảng loại hàng riêng.
- Tên/thứ tự cột VIMC khác hai app còn lại được giữ tự động theo hãng. Không tự ép cả ba thành một schema mới chưa được hệ thống Cảng xác nhận.
- `Số lượng` giữ phạm vi nhóm theo legacy (BL với VOSCO; Master_BL_Group_ID với VIMC/VINAFCO). Đếm container phân biệt trong nhóm để tránh nhân số do bản sao.
- Giữ cột seal thứ hai theo mẫu hiện tại và giữ tên cột điểm legacy. Mô tả dữ liệu gốc và nguồn không bị đưa thêm vào file import; có trong phiên/JSON đối chiếu.
- VOSCO/VINAFCO còn giữ các ngưỡng suy luận đang dùng; trường hợp suy luận hoặc xung đột được ghi rõ. Không tuyên bố tare giả định là cân nặng vỏ chính xác của từng container.

## Phạm vi chưa được chứng nhận

Chưa chạy ứng dụng với hệ thống quản lý container của Cảng, chưa có bộ input/output nghiệp vụ thật trong repo và chưa tạo EXE Windows trong môi trường Linux này. GUI Tkinter được đọc mã/kiểm tra tích hợp logic, chưa chạy kiểm thử trực quan: môi trường từ chối tạo socket Unix nên không khởi tạo được display X thử nghiệm. Các giới hạn này được ghi trong báo cáo kiểm chứng; bản mã nguồn, launcher và regression suite vẫn đầy đủ.

Không thay đổi/push các repo nguồn. Gói hợp nhất có thể được giao cho agent local để chạy, build Windows và đưa vào repository đích do người dùng quản lý.
