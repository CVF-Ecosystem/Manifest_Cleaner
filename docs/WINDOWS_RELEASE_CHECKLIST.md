# Checklist phát hành Windows — Manifest Cleaner Unified v1.1.1

**Trạng thái trong gói nguồn:** chưa build/nghiệm thu EXE Windows; chưa có kiểm
tra trực quan GUI Windows hoặc import thật trên hệ thống Cảng. Các ô dưới đây
để người kiểm tra local điền. Số test đã chạy trong môi trường chuẩn bị nằm tại
`docs/VALIDATION_REPORT.md`, không được tự đánh dấu thay cho bước Windows.

Người kiểm tra: ____________________

Ngày, máy/Windows, Python: ____________________

## A. Gói nguồn và môi trường

- [ ] Giải nén toàn bộ gói vào thư mục có quyền ghi; không chạy từ bên trong ZIP.
- [ ] Chạy `py -3.12 scripts\check_release.py`; xác nhận không có checksum thiếu/sai.
- [ ] Có Python 3.12 x64 kèm Tcl/Tk, hoặc phiên bản trong phạm vi 3.10–3.13 x64.
- [ ] Chạy `SETUP.cmd`; thư viện vào `.venv`, không yêu cầu quyền quản trị.
- [ ] `scripts\check_release.py --runtime-only` chạy bằng Python trong `.venv` pass.
- [ ] Máy bị hạn chế mạng: đã chuẩn bị wheelhouse đúng Python/Windows x64 và
      cài đầy đủ offline; không coi thiếu wheelhouse là lỗi parser.
- [ ] `RUN_TESTS.cmd` hoàn thành; ghi phiên bản và kết quả test của lần chạy này.

## B. GUI bản Python

- [ ] `START.cmd` mở app; mở lại với môi trường khỏe không chạy pip/tải thư viện.
- [ ] Bảng/nhãn tiếng Việt hiển thị đúng ở mức scale Windows đang dùng.
- [ ] Mở đúng demo từng hãng; chọn sheet/cấu hình hiển thị đúng hãng và nguồn.
- [ ] File có lỗi vẫn giữ record; lỗi liên kết đúng dòng; nút xuất bị chặn.
- [ ] Sửa riêng seal không xóa lỗi F/E hoặc trọng lượng; các checkbox xác minh
      chỉ tác động trường thực sự đã đối chiếu.
- [ ] Preview trong cửa sổ sửa khớp 16 cột file Excel thực, gồm mapping và làm tròn.
- [ ] Dòng loại/khôi phục có xác nhận đúng container/B/L và lý do; có trong JSON.
- [ ] Khôi phục `.review.json` giữ chỉnh sửa/loại/xác minh; nguồn cùng bytes ở
      vị trí mới được chọn lại; nguồn đã thay đổi bị từ chối.
- [ ] Đóng hoặc mở manifest khác khi còn chỉnh sửa hiện thông báo bảo vệ công việc.

## C. Xuất và lỗi ghi file

- [ ] Chạy `python -m unittest tests.test_cli_v111 -v`; đủ 11 ca đạt.
- [ ] Tái hiện cặp Excel/JSON cũ + manifest mới có lỗi + CLI `--overwrite`: cả hai file cũ phải giữ nguyên SHA-256. Dùng hướng dẫn trong `LOCAL_AGENT_V111.md`.
- [ ] Xuất tạo cặp `.xlsx` + `.review.json`; cả hai có cùng session ID và receipt.
- [ ] Không ghi đè output đã có nếu chưa chọn ghi đè.
- [ ] Khi Excel đang mở/khóa file đích, app báo lỗi; kiểm cặp output cũ vẫn nhất
      quán, không báo thành công chỉ vì một file có tồn tại.
- [ ] Thử thư mục không được ghi hoặc đích mất kết nối; thông báo cho biết kết
      quả và đường dẫn phục hồi nếu không thể khôi phục đầy đủ.
- [ ] Seal số 0 đầu vẫn là text. Dữ liệu bắt đầu bằng `=`/`+`/`-`/`@` không tự
      chạy công thức; URL không tự chuyển thành hyperlink.
- [ ] Mở file import bằng Excel và kiểm tên/thứ tự đúng 16 cột, không có cột kỹ
      thuật thêm vào. JSON đối chiếu không dùng để import vào Cảng.

## D. Đóng gói và tài nguyên đi cùng

- [ ] Dùng `BUILD_EXE.cmd` trên Windows; bản dist cũ/cấu hình công việc đã được
      bảo toàn trước khi `--noconfirm` thay đầu ra build.
- [ ] Có `dist\ManifestCleaner\ManifestCleaner.exe` và đầy đủ thư mục hỗ trợ.
- [ ] Có `START_HERE.html`, `settings.example.json`, checklist này và BUILD_INFO
      cạnh EXE. Không chỉ sao chép riêng file EXE.
- [ ] Có `README.md`, toàn bộ `docs/` và `samples/` đúng vị trí tương đối;
      nhấp các liên kết tài liệu và demo từ START_HERE không bị thiếu file.
- [ ] Ghi phiên bản PyInstaller thực từ BUILD_INFO. Nếu chốt phát hành, khóa
      phiên bản đã nghiệm thu đó trong quy trình build nội bộ.
- [ ] Chạy bản EXE từ thư mục mới có khoảng trắng/chữ Việt, không phụ thuộc thư
      mục source hoặc Python đang cài ở máy build.
- [ ] Chạy bằng shortcut với working directory khác; config vẫn nằm cạnh EXE.
- [ ] Tạo/sửa settings qua GUI, đóng/mở lại; settings còn đúng. Không đặt cấu
      hình cá nhân trong thư mục tài nguyên `_internal`.
- [ ] Chạy bộ demo trên máy Windows thử chưa cài Python; kiểm Tk, XLS và XLSX.
- [ ] Thử một lần offline sau khi EXE đủ file; đọc/xử lý/xuất không yêu cầu mạng.

## E. Nghiệm thu nghiệp vụ và ghi nhận phát hành

- [ ] Với từng hãng, người nghiệp vụ đối chiếu manifest thực đang có và kết quả
      xuất: số container/B/L, F/E, kg/tấn, seal, chủ hàng, mapping và hàng hóa.
- [ ] Import thử theo quy trình Cảng; ghi phiên bản hệ thống nhận và kết quả.
- [ ] Mọi thay đổi mapping/hợp đồng cột có căn cứ và người chấp thuận; không đồng
      nhất mapping khác nhau giữa hãng chỉ để làm code gọn.
- [ ] Lưu bộ input/output đã được chấp nhận riêng, ghi trạng thái xác nhận;
      không đổi nhãn golden tổng hợp thành dữ liệu Cảng xác nhận.
- [ ] Ghi bản phát hành, phiên bản Python/PyInstaller, kết quả test, giới hạn
      còn lại và vị trí bản dự phòng. Chỉ sau bước này mới tuyên bố EXE đã được
      kiểm tra trên các môi trường đã nêu.

Kết quả/giới hạn còn lại: _________________________________________________

Người xác nhận nghiệp vụ: _______________________________________________
