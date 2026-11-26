# Manifest Cleaner

Ứng dụng Windows xử lý manifest của **VOSCO**, **VIMC** và **VINAFCO**. Mỗi phiên đọc một workbook, hỗ trợ đối chiếu theo container và xuất Excel theo **mẫu TOS 46 cột** dùng chung cho cả ba hãng để import vào TOS của Cảng. Khi một hãng gửi hàng qua tàu của hãng khác, tab **Đổi B/L** lấy B/L của hãng gửi vào file tàu. Dữ liệu được xử lý cục bộ.

## Bắt đầu

- **Gói Windows** — Giải nén cả thư mục `ManifestCleaner` rồi mở `ManifestCleaner.exe` trong thư mục đó.
- **Mã nguồn** — Cài Python 3.12 64-bit có Tcl/Tk, rồi chạy `START.cmd` ở thư mục dự án. Lần đầu cần kết nối để cài thư viện.

Dùng [mẫu tổng hợp trong samples/](samples/) để thử quy trình trước khi mở manifest nghiệp vụ.

## Quy trình sử dụng

1. **Mở manifest.** Chọn hãng tàu, bấm **Mở manifest…** và chọn tệp Excel. Chọn sheet chi tiết nếu ứng dụng phát hiện nhiều bảng phù hợp.
2. **Đối chiếu dữ liệu.** Xem số dòng, lỗi chặn và cảnh báo trên dải tóm tắt. Trong tab **Cần kiểm tra**, chọn vấn đề để xem container, B/L, thông báo và vị trí nguồn.
3. **Sửa hoặc xác nhận.** Dùng **Xem / sửa dòng** để so dữ liệu nguồn với giá trị sẽ xuất. Ghi lý do khi lưu chỉnh sửa, xác nhận cảnh báo hoặc loại dòng. Dùng **Lưu đối chiếu…** để giữ phiên đang làm.
4. **Xuất Excel.** Khi đã xử lý hết lỗi chặn, bấm **Xuất file Manifest…**. Excel ghi chú và tô màu các mục cần đối chiếu. Tùy chọn xuất kèm JSON lưu phiên ngay cạnh Excel. Bấm **Mở thư mục kết quả** để xem tệp.
5. **Làm tiếp phiên đã lưu.** Chọn **Mở phiên đã lưu…** và mở JSON đối chiếu. Nếu manifest gốc đã chuyển thư mục, chọn lại tệp có cùng nội dung.

**Trọng lượng** là tổng vỏ và hàng, thể hiện bằng tấn. **Seal** được ghi dạng văn bản theo khai báo, kể cả chữ và số 0 đầu. Màu seal trong Excel là dấu tham chiếu theo mẫu của hãng để đối chiếu.

## Dòng lệnh và kiểm thử

Dùng các lệnh sau trong thư mục dự án sau khi chạy `SETUP.cmd` hoặc `START.cmd`.

```powershell
.\.venv\Scripts\python.exe -m manifest_cleaner.cli "samples\DEMO_VIMC_INPUT.xlsx" --carrier VIMC --output "dist\exports\demo.xlsx"
.\.venv\Scripts\python.exe -m manifest_cleaner.cli --help
.\.venv\Scripts\python.exe -B scripts\check_release.py --tests
```

## Đóng gói và chia sẻ

Chạy `BUILD_EXE.cmd` để kiểm thử và đóng gói vào `dist/ManifestCleaner/`. Có thể lưu gói bàn giao theo phiên bản tại `dist/<phiên bản>/ManifestCleaner/`. Khi gửi gói, chỉ nén thư mục `ManifestCleaner` cùng các tệp bên trong. Gói thư mục này dành cho máy phát triển và những người được chọn.

Cho người dùng cuối, chạy `BUILD_ONEFILE.cmd` để tạo `dist/onefile/ManifestCleaner.exe` và chỉ gửi đúng file này. File tự giải nén nên mỗi lần mở mất vài giây. `settings.json` và `recent_files.json` nằm cạnh file exe.

Dùng `Manifest/` cho tệp nghiệp vụ cục bộ. Giữ manifest thật, Excel xuất và JSON đối chiếu ngoài Git.

[Hướng dẫn offline](START_HERE.html) · [Danh mục tài liệu](docs/INDEX.md) · [Hợp đồng bộ đọc](ADAPTER_CONTRACT.md) · [Nguồn kế thừa](SOURCE_PROVENANCE.json)

**Tien - Tan Thuan Port @2026**
