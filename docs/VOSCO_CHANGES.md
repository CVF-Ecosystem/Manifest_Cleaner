# VOSCO — chuyển vào ứng dụng Manifest Cleaner chung

> Tài liệu nền của bản 1.0.0. Thay đổi bổ sung trong bản 1.1.0: [CARRIER_FIXES_V110.md](CARRIER_FIXES_V110.md) và [RELEASE_NOTES_V1_1.md](RELEASE_NOTES_V1_1.md).

## Căn cứ và phạm vi

Mô-đun kế thừa mã nguồn đang vận hành của `CVF-Ecosystem/Manifest-Cleaner_VOSCO`, nhánh `cvf-next`, commit `e5a78dd0444349990b08992ceb57758aa074dcb8` ngày 10-09-2026.

Người dùng chọn **hãng tàu VOSCO**. Tên tàu và tên file không được sử dụng để tự chọn hãng. Mô-đun chỉ đọc file Excel tại máy, trả dữ liệu và các mục cần kiểm tra; không mở cửa sổ, không kết nối mạng, không tự gửi hoặc ghi đè dữ liệu nguồn.

## Các quy tắc được giữ

- Bố cục cột A/B/F/K/O/S của manifest VOSCO; đọc sheet đầu tiên theo cách dùng cũ. Có thể đặt `sheet_name` trong cấu hình để chọn sheet khác.
- Nhận các khối thông tin `(S)`, `(C)`, `(N)` và số BL theo mẫu VOSCO hiện tại.
- Tách container, số niêm chì và kích cỡ từ chuỗi đang dùng. Giữ số 0 đầu của niêm chì.
- Giữ mapping SOC/COC sang mã hãng khai thác `SVC`/`VOC` và toàn bộ mapping kích cỡ VTOS hiện có, bao gồm `40GP → 40HC`, `20RF → 22R0`. Đây là mapping đầu ra của quy trình cảng; mã nguồn vẫn được giữ riêng.
- Giữ các cách gán mô tả theo dòng, theo số lượng/kích cỡ, hoặc dùng chung; giữ bước tinh chỉnh mô tả cuối cùng của app VOSCO.
- Mô tả đầu ra viết hoa, bỏ dấu theo cách dùng cũ; mô tả gốc vẫn được lưu để đối chiếu.
- Giữ quy tắc loại hàng, kiểm tra niêm chì 6 chữ số và cảnh báo tank của VOSCO. Quy tắc này không được áp sang hãng khác.
- Bộ xuất chung giữ đúng hợp đồng 16 cột của VOSCO. Mô-đun không tự bổ sung cột vào file nhập cảng và không làm tròn trọng lượng ở bước đọc.

## Các lỗi đã sửa

| Vấn đề cũ | Cách xử lý hiện tại |
|---|---|
| `25,500 KGS` bị đọc thành `25.5 KGS`; `25 500 KGS` chỉ còn `500` | Dùng bộ đọc số/đơn vị chung; các trường hợp này đều thành `25.5 TONS`. Trọng lượng nguồn và đơn vị nguồn được giữ riêng. |
| Xuất trị số KGS vào cột trọng lượng nhưng bỏ mất đơn vị | `Weight_Value` luôn là tấn trước khi suy luận F/E và trước khi xuất. |
| Bỏ dòng trọng lượng lỗi rồi dịch các trọng lượng phía sau sang container khác | Giữ đúng vị trí dòng lỗi. Ví dụ `10 TONS / lỗi / 30 TONS` thành `10 / chưa xác định / 30`. |
| Một trọng lượng bị lặp cho nhiều container | Không tự lặp hoặc chia. Nếu số dòng trọng lượng khác số container, giữ container và yêu cầu kiểm tra/nhập lại trọng lượng. |
| Ô Excel vốn là số có thể bị đọc lại theo dấu phân cách của văn bản | Giữ kiểu số khi truyền vào bộ xử lý chung: giá trị số `1.234` vẫn là `1.234` tấn dưới cả ba cấu hình quy ước số. |
| Lọc bỏ container do thiếu chủ hàng hoặc tên chứa `PORT,` | Giữ toàn bộ container đã nhận dạng. Thiếu tên chủ hàng là mục cần kiểm tra. |
| BL mới không đúng mẫu có thể dùng nhầm BL trước đó | Kết thúc khối BL trước; giữ container với BL chưa xác định và thông báo lỗi. |
| Chênh số dòng mô tả vẫn có thể ghi điểm 100 | Chỉ dùng ghép theo dòng khi số lượng khớp; fallback có cảnh báo và điểm thấp. Điểm này là tín hiệu nội bộ, không phải xác suất chính xác. |
| Suy luận F/E khác nhau giữa KGS và TONS | Chuẩn hóa về tấn trước khi suy luận. |
| Tank dùng ngưỡng vỏ container khô | Dùng khối lượng vỏ tank theo cấu hình cũ (`20TK`: 5,5 tấn). |
| Khai báo EMPTY có thể bị đổi thành F mà không nêu mâu thuẫn | Nhận dạng cụm trạng thái EMPTY rõ ràng, giữ E và cảnh báo nếu trọng lượng mâu thuẫn. Không coi hàng hóa `EMPTY BOTTLES` là khai báo container rỗng. |
| Số niêm chì thuần số có thể bị đọc nhầm thành kích cỡ khi thiếu type | Loại chuỗi toàn chữ số khỏi ứng viên kích cỡ; giữ niêm chì và nêu thiếu kích cỡ. |
| Một dòng container không đọc được trở thành lỗi toàn file nhưng không sửa được trên giao diện | Giữ dòng đó thành bản ghi chờ hoàn thiện, có mã bản ghi, dữ liệu nguồn và lỗi gắn đúng trường. Có thể điền/sửa hoặc loại dòng có lý do; không dịch vị trí trọng lượng phía sau. |
| Kích cỡ bất kỳ như `BANANA` có thể đi thẳng ra cột VTOS | Chỉ chấp nhận các khóa mapping hiện có. `is_supported_size_type()` kiểm tra mã; mã chưa biết để trống VTOS/loại hàng và chặn xuất cho đến khi được xử lý. |
| Luôn bỏ đúng 16 dòng đầu | Tìm điểm bắt đầu bằng BL, marker hoặc container trong các cột đã xác định; vẫn giữ số dòng Excel thật. |

## Dữ liệu đối chiếu

Mỗi bản ghi có tên file, sheet, dòng Excel và dòng container trong ô; có số BL gốc, ô container, ô trọng lượng, đơn vị nguồn, mô tả gốc, dữ liệu chủ hàng và các quy tắc đã áp dụng. Trường `raw` giữ bằng chứng nguồn; các giá trị đã chuẩn hóa được lưu riêng.

Lỗi container không đọc được, BL chưa xác định, thiếu kích cỡ hoặc trọng lượng không gán chắc chắn đều được trả về bộ kiểm tra chung. Không tự xóa các dòng để làm file kết quả trông hợp lệ.

Dòng container chưa phân tích được vẫn có thể mở để sửa từ bảng dữ liệu. Thông tin chưa xác định như kích cỡ hoặc F/E được để trống; thông tin đã đọc chắc chắn và vị trí nguồn vẫn được giữ. Các thông báo có `record_id` và `field` để giao diện liên kết đúng trường. Với cảnh báo số lượng/kích cỡ trong mô tả không khớp, `resolution_fields` gồm `Description` và `Size_Type` để việc xác nhận bao quát cả hai thông tin liên quan.

Khi người dùng sửa kích cỡ/F/E trên giao diện, `refresh_derived_fields()` chỉ cập nhật kích cỡ VTOS và loại hàng. Hàm không tự sửa lại F/E, mô tả hoặc mã hãng khai thác người dùng đã nhập.

## Kiểm chứng

Lệnh kiểm tra riêng:

```bash
python -m unittest discover -s tests -p test_vosco.py -v
```

Bộ **19 ca kiểm thử** sử dụng workbook XLSX tổng hợp và các tình huống hồi quy: giữ mapping/niêm chì đầu 0, đơn vị KGS/TONS, số có dấu phân cách, vị trí trọng lượng lỗi, không lặp trọng lượng chung, không mất dòng do chủ hàng, ranh giới BL sai, tiêu đề lệch dòng, mô tả thiếu dòng, tank/EMPTY, hàng `EMPTY BOTTLES`, gán mô tả theo số lượng, container hỏng, thiếu kích cỡ, sửa thủ công và XLSX được đặt đuôi `.xls`. Các ca bổ sung xác nhận dòng container hỏng vẫn có thể sửa/loại trên phiên chung, cảnh báo F/E suy luận hiện rõ, ô Excel dạng số không bị ảnh hưởng bởi cấu hình dấu phân cách, và kích cỡ chưa được map bị chặn.

## Giới hạn còn lại

- Đây vẫn là bộ đọc **mẫu VOSCO hiện có**, với các cột A/B/F/K/O/S. Nếu hãng đổi cột hoặc đổi hẳn mẫu, ứng dụng sẽ báo để bổ sung cấu hình/bộ đọc; không tự đoán bố cục khác.
- Số BL giữ quy tắc chữ/số hiện tại của app. BL ngoài quy tắc được giữ trong dữ liệu gốc và cần sửa/xác nhận.
- Mặc định vẫn đọc sheet đầu. Nếu sheet khác cũng có container, có cảnh báo để kiểm tra phạm vi; ứng dụng không tự gộp các sheet có thể là bản lặp.
- Chưa có cặp manifest thực tế và kết quả cảng đã xác nhận trong repo. Các test tổng hợp kiểm chứng những sửa đổi nêu trên; không được hiểu là đã xác nhận mọi biến thể manifest thực tế.
- Cách suy luận F/E theo ngưỡng khối lượng được kế thừa để không thay toàn bộ nghiệp vụ. Trường `Weight_Kind` mặc định là `unknown` vì mã cũ không chứng minh ô nguồn là trọng lượng hàng hay tổng trọng lượng; có thể khai báo rõ bằng cấu hình `weight_kind`. Khi còn `unknown`, các dòng dùng suy luận này có cảnh báo `FE_WEIGHT_KIND_UNCONFIRMED` gắn với F/E để người dùng thấy và đối chiếu. Trọng lượng không đủ bằng chứng gán theo container phải được kiểm tra trước khi xuất.
