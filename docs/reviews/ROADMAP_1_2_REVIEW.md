# Kiểm chứng Manifest Cleaner 1.2.0

Risk: R2
Worker: Sol 6.2 Medium, Terra 6.1 High và orchestrator tích hợp
Reviewer: Astra 6.2 Medium độc lập

Ngày 24-11-2026. Commit sản phẩm cục bộ `9c7e68eb76facead1a90e0ce2be5aed0fbf769d4`. Các quyết định dưới đây áp dụng cho phạm vi được kiểm trên chính bản này.

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| M01 | VERIFIED | Bản phát triển ngang cấp Core. Pin, cài đặt và hồ sơ đánh giá độc lập buộc vào work order. So sánh trả CURRENT_ASSESSED và pre-dispatch đạt cả 7 kiểm tra. |
| M11 | VERIFIED | Mẫu VINAFCO 2629DS đọc 57 bản ghi, bỏ đúng 15 dòng tổng hợp 191–205. 2535HS đọc 4 bản ghi và giữ tọa độ tổng hợp 41–55. SHA-256 hai nguồn giữ nguyên. Hồi quy giữ dòng thiếu mã sát bảng tổng hợp và giữ cả dòng chi tiết có tiêu đề tổng hợp nằm bên phải. |
| M12 | VERIFIED | 2629DS khớp TOTAL 57 và 34 × 20DC, 21 × 40HC, 2 × 40RF. 2535HS có 2 × 20DC, 2 × 40HC và tổng nguồn thiếu nhãn. Ca cùng container đi với nhiều B/L tách riêng số container và số quan hệ. Ca thiếu mã, chồng bảng hoặc không rõ phạm vi báo chưa thể đối soát. |
| M21 | VERIFIED | Kiểm trực tiếp bằng EXE trên Windows: thấy hai sheet, dòng tiêu đề và mẫu; chọn Chi tiết, đối soát 1/1 và xuất thành công. Hồi quy xác nhận hủy chọn không tự đọc, mở review không đổi mặc định cho workbook tiếp theo. |
| M22 | VERIFIED | Fixture VOSCO báo cột J/L và đúng dòng trong vùng đã nhận diện, kể cả trước dòng K đầu hoặc thiếu khối lượng. Dòng mô tả TOTAL QUALITY STEEL không cắt vùng rà soát. Kết quả chỉ là ứng viên để đối chiếu. |
| M31 | VERIFIED | Subprocess cp1252 kiểm help, lỗi đối số, lỗi xử lý và JSON đầu ra chứa tên file có emoji. UTF-8 giữ tiếng Việt. Hồi quy giữ cặp Excel/JSON khi xuất bị chặn. |
| M32 | IMPLEMENTED_UNPROVED | Có EXE và đã xác minh luồng cục bộ trên Windows. Phần còn lại là chạy trên máy độc lập sạch/offline và nghiệm thu import vào hệ thống Cảng với dữ liệu được xác nhận. |
| M41 | VERIFIED | Một registry dùng chung cho cả ba hãng, bao gồm giá trị operator trong adapter. Golden giữ đúng mẫu 16 cột, làm tròn và cách đếm. Archive EXE chứa đủ ba adapter. |
| M42 | BLOCKED | Đội phát triển sẽ chuẩn bị và kiểm adapter khi operator cung cấp hãng, mẫu manifest và quy tắc hoặc file đầu ra do nghiệp vụ xác nhận. |

## Kiểm kỹ thuật và luồng Windows

- Python 3.11.9 x64, Tcl/Tk 8.6 và dependency theo pin. `scripts/check_release.py --tests` đạt 218 unittest và 93 mục SHA-256. Reviewer độc lập chạy lại 71 ca trọng tâm và tái hiện các ca biên. Một lần chạy tích hợp trước đó đọc trong khi adapter đang được sửa dở và gặp lỗi số lượng phần tử của tuple. Bản hoàn chỉnh được kiểm lại từ bộ phụ thuộc đã pin.
- Workspace bootstrap cài bằng nguồn Core chính thức trong clone tạm. Lần checkout đầu dừng vì giới hạn đường dẫn Windows. Không có project đích lúc lỗi. Bật core.longpaths riêng trong clone tạm, checkout lại đúng commit và bootstrap thành công. Doctor kiểm chứng pin và origin. Review độc lập và biên nhận pre-dispatch ở [hồ sơ kích hoạt](activation-roadmap/).
- `SETUP.cmd` của gói nền thất bại qua cmd.exe với dòng LF, trước khi cài phụ thuộc. Chuẩn hóa riêng các launcher .cmd sang CRLF và ghi .gitattributes để duy trì khi checkout. Setup và BUILD_EXE đã chạy thành công sau sửa. Build dùng PyInstaller 6.22.3, Windows build 26200.
- EXE thử trực tiếp từ bản sao có cả dấu tiếng Việt và khoảng trắng, với working directory khác thư mục EXE. Dùng workbook tổng hợp hai sheet, chọn rõ Chi tiết, thấy chênh lệch 0 và xuất một dòng Excel đủ 16 cột cùng JSON. Kiểm tra cùng session ID, phiên bản 1.2.0, review mở lại được với đúng nguồn, và hash Excel khớp `metadata.last_export.excel_sha256`. SHA-256 EXE `ce54f87709f1558ec1d2e695b23b0a8c71a52275e14c4cd2b5adf57e76cddbb6`.
- Terra chạy luồng Tk native từ nguồn với hộp thoại file được cấp đường dẫn bằng harness. Đã sửa seal, lưu/mở lại review và xuất cặp file thật. Kiểm cuối dùng Win32 khóa Excel đã xuất từ EXE và gọi exporter từ nguồn cùng phiên bản. Exporter báo lỗi ghi, lỗi gốc WinError 5. Hash Excel và JSON giữ nguyên sau thử. Ca khóa này kiểm exporter, không kiểm hộp thoại lỗi trong EXE.
- Reviewer đã giữ bản đầu vì trường hợp mất dòng cạnh tiêu đề tổng hợp, sót ứng viên VOSCO, cấu hình sheet lan sang file khác và operator chưa dùng chung phía adapter. Sau sửa, reviewer xác nhận độc lập các ca biên đã qua và chấp nhận M11/M12/M21/M22/M41. Các biên nhận runner được lưu trong [roadmap-1.2](roadmap-1.2/).

## Quyết định còn mở

Bản 1.2.0 đủ bằng chứng cho kiểm thử cục bộ trên máy Windows này. Bản gốc 1.1.1 và các repo hãng đã được bảo toàn trong lượt chuyển project. Chưa có xác nhận nghiệp vụ từ hệ thống Cảng, máy thử độc lập sạch/offline hoặc triển khai hãng kế tiếp. Gói EXE là bản build local và cần dùng nguyên thư mục dist/ManifestCleaner. Project giữ công việc ở REVIEW cho phần nghiệm thu còn mở. Lịch sử Git là cục bộ.
