# MC64: xuất đúng mẫu import TOS

Risk: R2
Worker: Sonnet 5.5 effort high, subagent implementation worker
Reviewer: Opus 5.5 orchestrator, không viết mã của lượt này

Ngày 26-11-2026. Căn cứ:

- Operator đưa mẫu import thật `Manifest/Test/Template_LuocKhaiHangHoa.xlsx`.
- Operator đưa `Manifest/Test/mnf.xlsx`, file ghép tay từ dữ liệu của app và đã import được vào TOS.
- Operator yêu cầu app ghi dữ liệu đã lọc thẳng vào cấu trúc đó, thay cho copy/paste. Cột app không có dữ liệu để trống.

Đây là sửa lỗi cùng phạm vi [WO_MC_TOS_EXPORT](../work_orders/WO_MC_TOS_EXPORT.md): mục tiêu MC61/MC64, đường dẫn, rủi ro và tác động đều không đổi. Hai file nghiệp vụ nằm ngoài Git.

## Thay đổi

- `exporter._write_tos_sheet` ghi vùng dữ liệu thành Excel Table `Sheet1`, kiểu TableStyleMedium2, 47 cột: 46 cột TOS cộng `Column1` để trống, rộng 0,1.
  - Bỏ định dạng tiêu đề riêng và bộ lọc của sheet. Table tự có bộ lọc.
  - Giá trị, kiểu số/chữ, màu ô và thuộc tính tài liệu giữ nguyên. `export_form` đổi thành `TOS_TEMPLATE47`.
  - Không có dòng nào thì vẫn tạo Table hợp lệ với một dòng trống.
- `carriers.TOS_EXPORT_COLUMNS` là `TOS_COLUMNS` cộng `Column1`.
- `bl_change.read_tos_file` nhận file 46 cột (xuất trước lượt này) hoặc 47 cột, và bỏ qua dữ liệu cột `Column1`. File Đổi B/L giữ nguyên Table.
- Có thêm `tests/test_tos_table.py` (11 ca). Các test cũ đổi sang 47 tiêu đề.
- Reviewer sửa chữ trên app và tài liệu từ "mẫu TOS 46 cột" thành "mẫu import TOS (Template_LuocKhaiHangHoa)".

## Kiểm của reviewer

- **Diff mã nguồn.** Đúng phạm vi đã giao, không có lỗi logic. Test mới kiểm từng thuộc tính Table, kiểu dữ liệu, cột trống và các bố cục bị từ chối.
- **Kiểm thử.** Chạy lại 342 ca, đạt. Gate worker-return PASS 7/7, reviewer-fast PASS 8/8. Kiểm tra phát hành PASS với 152 mục.
- **Đối chiếu dữ liệu thật.** Chạy lại cả luồng ra thư mục tạm: CLI VOSCO `MNF TAU FF2643S.xls`, CLI VIMC `MNF FF2643S_VIMC.xls`, rồi `bl_change` (36 đổi, 0 khác biệt). So với `mnf.xlsx`:
  - Table `Sheet1`/`Sheet1`, vùng `A1:AU298`, kiểu, 47 tên cột, không bộ lọc sheet, tên sheet: **giống hệt**.
  - 297/297 container. Các cột app điền khớp hoàn toàn.
  - Chỉ khác ở 7 cột operator điền tay mà app để trống theo yêu cầu: Cảng xếp, Cảng dỡ, Cảng đích, Cntr Class, CntrClass và 2 cột Hàng nội/ngoại.
  - Khác thêm ở các ô mẫu còn sót trong 2 dòng đầu của `mnf.xlsx`: OOG_* và Cảng chuyển/giao nhận.
- **Excel thật.** Mở qua Excel COM ẩn không làm được trong môi trường này. Lỗi `0x800A03EC` xảy ra cả với `mnf.xlsx`, nên đây là giới hạn môi trường, không phải lỗi file. Chưa có kiểm tra bằng Excel thật.
- **File để operator thử.** Kết quả được chép vào `Manifest/Test/FF2643S_APP_TEMPLATE_DOI_BL.xlsx`, kèm file `.bl_change.json`.

## Ghi nhận không chặn

- Đổi B/L với file tàu 46 cột cũ cho ra file không có Table. Nên xuất lại bước một bằng bản mới.
- Màu ô phủ tới cột AT. Cột `Column1` không tô, và vì rộng 0,1 nên không thấy.
- Cont VINAFCO `VFCU2251345` vẫn ghi SVM. Operator sửa tay thành VFC theo quyết định trước.

## Kết quả import và lượt sửa thứ hai

- **Import.** Operator báo `FF2643S_APP_TEMPLATE_DOI_BL.xlsx` đã import vào SGPTOS thành công. Màn hình Lược khai hàng hóa cho thấy dữ liệu nạp đúng cột.
- **Quyết định operator.** Tàu nội địa, mọi dòng của cả ba hãng, viết hoa toàn bộ:
  - R `NTAU`, S `NHẬP TÀU`.
  - T `TAU-BAI`, U `GIAO NHẬN TÀU <=> BÃI`.
  - AF `IMPORT`, AH `HÀNG NỘI`.
  - AG và AE để trống.
  - Chữ `F` trong `mnf.xlsx` nghĩa là FULL. AG và AH mang cùng một thông tin.
  - Quyết định này thay câu "các cột TOS khác để trống" của MC61 cho 6 cột trên. Bảng tiêu chí trong roadmap giữ nguyên để không đổi mã băm đã duyệt.
- **Worker** Sonnet 5.5, effort high:
  - Thêm hằng số `carriers.TOS_FIXED_VALUES`, áp trong `exporter.tos_row`. Bộ ghi Excel và dòng trống của file rỗng không bị đổi.
  - Thêm một câu vào ghi chú xem trước.
  - Thêm 6 ca test. Bộ test giờ có 348 ca.
- **Reviewer:**
  - Sáu chuỗi đều viết hoa và ở dạng NFC. Các cột đúng vị trí: R=18, S=19, T=20, U=21, AF=32, AH=34. AE=31 và AG=33 để trống.
  - Sửa ngay một lỗi: worker đã đổi kiểu xuống dòng của 6 file Python từ LF sang CRLF. Đã đưa về LF, sau đó diff thật chỉ còn 85/34 dòng.
  - Chạy lại 348 ca, đạt.
  - Chạy luồng FF2643S thật: 297 dòng đều mang đúng 6 giá trị. 14 cột app điền vẫn khớp `mnf.xlsx`. Table vẫn là `A1:AU298`, 47 cột.
  - File thử mới: `Manifest/Test/FF2643S_APP_TEMPLATE_DOI_BL_v2.xlsx`.

## Còn mở

- **MC64:** bản đầu đã import được. Operator import thử bản có giá trị cố định `FF2643S_APP_TEMPLATE_DOI_BL_v2.xlsx`.
- Chưa commit, chưa build lại EXE.
