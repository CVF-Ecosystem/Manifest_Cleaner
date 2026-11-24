# VIMC và VOSCO — sửa lỗi đã tái hiện trong audit độc lập

Phiên bản: **1.1.0**. Ngày: **22-11-2026**.

Tài liệu này ghi thay đổi của hai adapter. Mã hãng khai thác, mapping kích cỡ
VTOS, mapping loại hàng và hợp đồng cột import tiếp tục theo từng hãng.

## 1. F02 — Giữ dòng VIMC có mã container bị hỏng

Các dạng đã tái hiện trong audit:

```text
VIMU 2300126 654321 20GP 25 STEEL
VIMU-2300126 654321 20GP 25 STEEL
VIM2300126 654321 20GP 25 STEEL
```

Cả ba hiện thành bản ghi chỉnh sửa được, giữ nguyên mã lỗi và nguyên văn nguồn.
Ứng dụng đọc những trường còn xác định được, gắn lỗi vào số container và chặn
xuất import. Người dùng phải đọc nguồn và sửa mã hoặc loại bản ghi có lý do.
Không tự thêm chữ, bỏ dấu gạch hoặc nối số để ngầm coi mã đã đúng.

Nhận diện ứng viên được tách khỏi kiểm tra hợp lệ. Ứng viên rộng hơn cần có
cấu trúc dòng phù hợp: vị trí đầu dòng/đoạn và kích cỡ container gần đó. Một seal
ba chữ như `VMC1234567` giữa mã container đúng và kích cỡ không bị tách thành
container thứ hai. Các dòng TOTAL, SEAL, PHONE, tổng số container, trạng thái
SOC/COC và tên hàng độc lập được kiểm tra âm tính.

Cơ chế này hỗ trợ các biến thể có bằng chứng cấu trúc; không khẳng định khôi phục
được mọi mã hỏng bất kỳ. Văn bản không ghép thành container được giữ trong
`metadata.source_fragments` để đối chiếu, thay vì bị mất khỏi báo cáo nguồn.

## 2. Đối soát vùng nguồn VIMC

`metadata.source_fragments` lưu sheet, dòng, cột, dòng con trong ô, nội dung,
trạng thái và lý do. Đoạn có bản ghi được liên kết bằng `record_id`.

`metadata.coverage` gồm:

| Trường | Nội dung |
|---|---|
| `source_fragments` | Số đoạn có nội dung đã ghi nhận trong vùng mô tả, MARKS và ô có ứng viên |
| `parsed_fragments` | Đoạn container có grammar và mã nhận diện được |
| `unresolved_fragments` | Đoạn container còn lỗi mã hoặc grammar mơ hồ/chưa đủ |
| `ignored_fragments` | Tiêu đề, trạng thái, ghi chú hoặc văn bản không có cấu trúc container được hỗ trợ; nội dung vẫn được giữ |
| `corroborating_fragments` | MARKS đối chiếu với một bản ghi chi tiết đã có |

Tổng bốn nhóm bằng `source_fragments`. Các con số phản ánh lúc đọc nguồn, không
phải số container duy nhất và không phải tỷ lệ chính xác. Một container có thể
có cả detail và MARKS. Validation hiện tại vẫn quyết định dữ liệu đã đủ để xuất
sau chỉnh sửa hay chưa.

VIMC cũng nhận `selected_sheet`: có thể chọn một sheet cụ thể; tên không tồn tại
trả lỗi rõ ràng. Khi không chọn, giữ hành vi quét các sheet như phiên bản trước.

## 3. F09 — Đọc tiếp thông tin party qua dòng Excel

Marker `1)`, `2)`, `3)` có thể nằm trên dòng riêng và tên tương ứng ở dòng sau.
Adapter tiếp tục đọc trong cùng B/L, giữ cả tên và địa chỉ nguồn, đồng thời lưu
`raw.party_evidence` với tọa độ từng phần.

Continuation kết thúc khi xuất hiện dòng container, tổng hoặc B/L mới. Nội dung
không có marker ở dòng container không bị gán vào tên party trước đó. Marker rõ
ràng vẫn có thể khai báo party ngay trên dòng có hàng, giữ trường hợp nguồn đã
được hỗ trợ. Tên ở B/L trước không được chuyển sang B/L kế tiếp.

Tên dùng để xuất vẫn lấy dòng tên đầu tiên theo quy trình hiện có; phần địa chỉ
và các dòng tiếp theo nằm trong dữ liệu đối chiếu.

## 4. F04 — VOSCO dùng cùng một danh sách mô tả để đếm và ghép

Trước đây bước nhận dạng loại `PORT HAIPHONG` ra khỏi số dòng nhưng bước ghép
vẫn lấy dòng đó. Với hai container và `RICE / PORT HAIPHONG / STEEL`, container
thứ hai bị gán PORT HAIPHONG với điểm 100.

Phiên bản này phân loại một lần theo dòng nguồn: hàng hóa, thông tin cảng,
tổng, attached list, khoảng trống và mô tả theo số lượng. Bước đếm và bước ghép
theo vị trí dùng cùng danh sách đã phân loại. Dòng PORT ở đầu, giữa hoặc cuối
không làm dịch hàng. `TRANSPORT EQUIPMENT` được giữ là hàng, không bị loại chỉ
vì có chuỗi con `PORT `.

Mỗi record giữ:

- `raw.description_cell`: nguyên văn toàn bộ ô nguồn.
- `raw.description_line_evidence`: nội dung, loại và số dòng gốc.
- `raw.description_source_lines`: các dòng được dùng để gán mô tả.
- `raw.description_match_type`: cách ghép.

Nếu số dòng hàng còn lại không đủ, vẫn phải fallback có cảnh báo và điểm thấp;
không tự coi đó là ghép chính xác. Quy tắc theo số lượng/kích cỡ và tinh chỉnh
mô tả legacy tiếp tục được giữ.

## 5. F05 — Nghĩa trọng lượng VOSCO tham gia quyết định F/E

`weight_kind` chỉ nhận `gross`, `cargo`, `unknown`; giá trị sai bị từ chối.

| Cấu hình | Hành vi |
|---|---|
| `gross` | Giữ quy tắc khối lượng vỏ của VOSCO và cảnh báo tank hiện có |
| `cargo` | Không so khối lượng hàng với vỏ container; hàng dương như 2 tấn hoặc 0,01 tấn giữ F |
| `unknown` | Giữ quy tắc legacy để tương thích, kèm cảnh báo `FE_WEIGHT_KIND_UNCONFIRMED` cần đối chiếu |

Khai báo EMPTY vẫn được giữ theo nguồn. Nếu cấu hình nói đây là khối lượng hàng
và số đó lớn hơn 0, xuất hiện lỗi `EMPTY_CARGO_WEIGHT_CONFLICT`, yêu cầu xác nhận
cả F/E và khối lượng. Khi khối lượng hàng bằng 0 nhưng chưa có khai báo EMPTY,
giữ F và có cảnh báo trọng lượng F bằng 0; không tự tuyên bố container rỗng.

Lưu ý vận hành: đặt `cargo` hoặc `gross` khi đã biết nghĩa của cột nguồn. Không
dùng việc đổi cấu hình chỉ để loại cảnh báo. Mặc định VOSCO vẫn là `unknown`.

## 6. Kiểm thử

Lệnh kiểm tra trực tiếp:

```bash
python -m unittest tests.test_vimc tests.test_vosco tests.test_vimc_v110 tests.test_vosco_v110 -v
```

Kết quả lúc hoàn thành thay đổi: **63 test pass**, gồm 44 test cũ không sửa và
19 test hồi quy mới. Các subtest bao phủ ba dạng mã lỗi VIMC, lỗi trong MARKS,
hai đoạn trong một ô, ca âm tính với seal/tổng/contact, ranh giới party/B/L,
chọn sheet, PORT trước/giữa/sau, tổng/attached list/khoảng trống, hàng chứa từ
TRANSPORT, hàng nhẹ theo cargo, default unknown, enum sai và mâu thuẫn EMPTY.

Các workbook tái hiện là dữ liệu tổng hợp chứng minh hành vi cụ thể; kết quả
test không được coi là tỷ lệ chính xác đã đo trên manifest vận hành của cảng.
