# Báo cáo kiểm chứng — Manifest Cleaner Unified 1.1.1

Ngày **22-11-2026** (Asia/Ho_Chi_Minh). Gói nền: 1.1.0 do người dùng cung cấp.

## Kết quả thực thi

**202/202 unittest đạt**, 0 thất bại, 0 lỗi thực thi, 0 bỏ qua. Gồm **191 ca giữ nguyên** từ 1.1.0 và **11 ca mới** trong `test_cli_v111`. Lần chạy đầy đủ mất 3.925 giây trên môi trường bên dưới; đây không phải benchmark file lớn.

- Toàn bộ suite: `python -m unittest discover -s tests -v`; log tại [TEST_OUTPUT.txt](TEST_OUTPUT.txt).
- Runtime: Python x64, import Tkinter và các dependency pin đều đạt. Import Tkinter không đồng nghĩa đã mở cửa sổ.
- Ca hồi quy chính: chạy với nhánh CLI 1.1.0 phát hiện JSON bị thay; chạy với 1.1.1 đạt. Log tại [F10_BEFORE_AFTER.txt](F10_BEFORE_AFTER.txt).
- Demo kế thừa: sao nguyên `samples/` sang thư mục tạm khác và mở bằng 1.1.1, **4/4 phiên đạt**. Ba demo thường giữ 0 lỗi; demo cần kiểm tra giữ 2 record và 7 lỗi chặn.
- Golden 3 hãng, hợp đồng 16 cột, lưu/mở phiên, nguồn/hash, rollback và các quy tắc cũ được chạy lại trong suite.
- Các file adapter/mapping, common/engine/exporter/GUI và 191 test nền được so byte với bản 1.1.0; phần nghiệp vụ giữ nguyên.
- Gói có manifest SHA-256 cho từng file; kết quả cuối được kiểm bằng `scripts/check_release.py`. ZIP được kiểm CRC và đối chiếu mọi byte với thư mục phát hành trước khi bàn giao.

## Phân bố kiểm thử

| Module | Số ca | Kết quả |
|---|---:|---|
| `test_cli_v110` | 13 | Đạt |
| `test_cli_v111` | 11 | Đạt |
| `test_common` | 8 | Đạt |
| `test_export_v110` | 15 | Đạt |
| `test_golden_v110` | 3 | Đạt |
| `test_gui_v110` | 16 | Đạt |
| `test_integration` | 14 | Đạt |
| `test_review_safety` | 6 | Đạt |
| `test_session_v110` | 23 | Đạt |
| `test_vimc` | 25 | Đạt |
| `test_vimc_v110` | 9 | Đạt |
| `test_vinafco` | 16 | Đạt |
| `test_vinafco_v110` | 13 | Đạt |
| `test_vosco` | 19 | Đạt |
| `test_vosco_v110` | 11 | Đạt |
| **Tổng** | **202** | **Đạt** |

## Phạm vi 11 ca mới

1. Cặp Excel/JSON tường minh đã có: giữ nguyên cả hai khi nguồn lỗi, có hoặc không `--overwrite`.
2. JSON theo tên mặc định: bảo vệ cặp đã có.
3. JSON tùy chọn ở thư mục khác: bảo vệ cặp và không tạo sidecar ngoài yêu cầu.
4. Chỉ còn JSON cũ nhưng không có Excel: bảo vệ JSON.
5. Excel cũ, JSON đích mới: dừng trước khi ghi hoặc tạo thư mục.
6. `--no-review` với nguồn lỗi: giữ nguyên Excel và sidecar cũ.
7. Resume phiên còn lỗi: không thay cặp cũ hoặc phiên đã lưu.
8. Hai đích mới, có `--review`: giữ khả năng lưu báo cáo lỗi và mở lại, không có Excel.
9. Hai đích mới, không `--review`: không tạo đầu ra.
10. Lưu report-only: giữ hành vi lưu và ghi đè tường minh.
11. Nguồn hợp lệ: ghi đè cả cặp thành công, cùng session/hash và đúng trọng lượng trong Excel.

Các ca có nhiều tình huống con nhưng được đếm theo 11 phương thức test, không tăng số đếm theo từng assert.

## Môi trường

- Python **3.12.14**, 64-bit; `Linux-6.18.57-x86_64-with-glibc2.41`.
- pandas 2.2.3; openpyxl 3.1.5; XlsxWriter 3.2.9; xlrd 2.0.1.
- Chạy trên một phiên bản Python; phạm vi khai báo 3.10–3.13 chưa được kiểm theo ma trận đầy đủ.

## Giới hạn và việc giao local

- Chưa chạy GUI native, build/chạy EXE Windows hoặc import vào hệ thống Cảng. Tests GUI dùng widget giả và engine/file thật.
- Golden và demo là dữ liệu tổng hợp; chưa phải bộ manifest/output được Cảng xác nhận. Không dùng số test để diễn giải thành độ chính xác vận hành.
- Giữ các giới hạn 1.1.0 về công thức XLS cũ; không có kiểm kê cache công thức tương đương XLSX/XML.
- Cơ chế xuất hai file vẫn không phải giao dịch chung bảo đảm khi mất điện. Bản vá xử lý chính nhánh CLI có lỗi validation; tests rollback cũ xử lý lỗi I/O bắt được.
- `--no-review` khi xuất hợp lệ vẫn chỉ tạo Excel; sidecar cũ cùng tên, nếu có, không được cập nhật. Dùng tên mới để tránh nhầm cặp như hướng dẫn nền.
- Đề xuất nhận diện bố cục/merge/profile, rà nguồn độc lập, sửa nhóm và tự lưu chỉ nằm trong [LOCAL_AGENT_V111.md](LOCAL_AGENT_V111.md), chưa có trong runtime 1.1.1.

Hướng dẫn nghiệm thu chi tiết: [LOCAL_AGENT_V111.md](LOCAL_AGENT_V111.md) và [WINDOWS_RELEASE_CHECKLIST.md](WINDOWS_RELEASE_CHECKLIST.md).
