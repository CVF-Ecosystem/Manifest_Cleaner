# MC3: mẫu xuất TOS và tab Đổi B/L

Ngày 26-11-2026, kiểm trên máy phát triển Windows. Căn cứ: [roadmap MC3](../roadmaps/MC_TOS_EXPORT.md) và [work order](../work_orders/WO_MC_TOS_EXPORT.md). Đây là bằng chứng của implementation worker kèm tự kiểm. Chưa có review độc lập cho phần triển khai, và chưa import thử trên TOS.

## Đã làm

- **MC61.** Cả ba hãng xuất một mẫu: sheet `Sheet1` với đủ 46 tiêu đề TOS (`carriers.TOS_COLUMNS`). App giữ một bộ 16 cột theo thứ tự TOS (`PORT_COLUMNS`) cho xem trước. STT và Ghi chú chỉ hiện trên app, file Excel để trống. Kích cỡ là mã VTOS cho mọi hãng. Kích cỡ ISO và mã loại hàng chỉ điền theo các cặp đã thấy trong mẫu TOS. Độ chính xác (%) không còn trong file. Màu cảnh báo chuyển từ định dạng có điều kiện sang màu ô cố định, nên sắp xếp trong Excel vẫn giữ màu theo dòng. Quy tắc theo hãng về số lượng, làm tròn, EMPTY và seal không đổi.
- **MC62.** `manifest_cleaner/bl_change.py` và tab thứ ba **Đổi B/L**:
  - Nhận hai file đã xuất ở bước một, ghép theo số container, và lấy sáu trường từ file của hãng gửi hàng.
  - Giá trị trống không đè giá trị đã có. Khác biệt kích cỡ, F/E, seal và loại hàng được tô vàng và giữ theo file tàu.
  - Có liệt kê container chỉ có ở file hãng gửi và B/L gom chỉ đổi một phần.
  - Dừng khi file không đúng mẫu, container trùng trong một file, hai lần chọn cùng một file, không có container chung, hoặc file nguồn đổi sau khi đối chiếu.
  - Kết quả gồm file mới, có ô đổi tô xanh lá, và file `.bl_change.json` ghi SHA-256 hai nguồn cùng từng thay đổi.
- Tài liệu: thay quy tắc 16 cột trong `AGENTS.md`, cập nhật `docs/AUDIT_FIXES.md`, `docs/UI_DESIGN_DECISIONS.md`, README, ADAPTER_CONTRACT, DEVELOPER_HANDOFF và GUI_V110. Bộ mẫu `samples/` được tạo lại theo mẫu TOS.

## Bằng chứng

- **Kiểm thử.** `python -m unittest discover -s tests` chạy 329 ca và đạt hết (trước lượt này là 322). Sau tự review là 330 ca.
  - Có thêm 7 ca trong `tests/test_tos_bl_change.py` (8 ca sau tự review). Trong đó, ba phiên review v2 do bản 1.1.0 lưu, thời còn mẫu 16 cột, mở lại được và xuất theo mẫu TOS. Ba phiên này nằm trong `tests/fixtures/review_v2_16col/`.
  - Golden fixture được chép sang mẫu TOS theo quy tắc ghi trong `reasoning` của từng fixture, không sinh từ kết quả của app.
  - Ca kích thước tối thiểu của cửa sổ đạt ở 100%, 125% và 150%.
- **Đối chiếu cục bộ.** Dữ liệu nghiệp vụ không có trong Git.
  - Nguồn: `MNF TAU FF2643S.xls`, SHA-256 203a9a56…4a05b32. Mẫu TOS `Vtos.xlsx`: b62ec506…dbac79. Bill VIMC: c0234535…ac39c.
  - Bước một, CLI VOSCO: 297 dòng, 46 tiêu đề trùng khớp TOS, 14 cột được điền.
  - Bill VIMC ở dạng 16 cột cũ nên được chuyển sang mẫu TOS trong thư mục tạm bằng cùng hàm của exporter. Sau đó ghép bằng `bl_change`: 36 container chung, 36 đổi, 0 khác biệt, 0 container không có trên tàu, 0 B/L gom còn sót.
  - Kết quả so với `Vtos.xlsx` trên 297/297 container: 13 cột app điền khớp hoàn toàn. Cột TL hàng lệch 8 dòng, đều là 40RH rỗng (manifest 3,8 tấn, TOS 4,5 tấn), đúng khác biệt đã chốt ở MC63.
  - SHA-256 của file tàu không đổi.
- **Gate.** Pre-dispatch trusted đạt PASS 7/7 sau khi gắn work order. Activation CURRENT_ASSESSED.

## Tự review của agent triển khai

Ngày 26-11-2026, theo yêu cầu của operator, chính agent đã triển khai chuyển sang vai REVIEWER. Đây là tự review. Nó không phải review độc lập và không đáp ứng yêu cầu reviewer độc lập cho mức R2 trong work order. Gate reviewer-fast PASS 8/8 chỉ vì hồ sơ này không khai báo vai reviewer, nên kết quả đó không chứng minh tính độc lập.

Phạm vi đã xem:

- Diff của `carriers/__init__.py`, `exporter.py`, `bl_change.py` và `gui.py`.
- Các test đã sửa và test mới.
- Chữ hiển thị cho người dùng.
- Bố cục tab ở kích thước tối thiểu.

Phát hiện và cách xử lý. Cả ba lỗi đều do reviewer sửa ngay, vì mục tiêu, đường dẫn và phạm vi đều không đổi:

1. **Quan trọng.** Ở kích thước tối thiểu, nút "Xuất file TOS đã đổi B/L…" và bảng của tab Đổi B/L bị che hết, cao 1 px ở 100%, 125% và 150%. Tab chỉ cao 227 px, trong khi phần trên cần khoảng 270 px.
   - Sửa: lời giới thiệu còn một câu, mỗi file một dòng (gồm tên, hãng, số container và manifest nguồn), nút Xuất đặt cạnh dòng tóm tắt, và dùng grid để chỉ bảng co lại.
   - Sau khi sửa, nút Xuất và các nút Chọn đều hiện ở cả ba mức. Ở 150%, cửa sổ chạm chiều cao màn hình nên bảng của tab co hết, giống giới hạn của bảng Container chính.
   - Đã thêm test `test_file_choice_and_export_stay_visible_at_the_minimum_window_size`.
2. **Quan trọng.** Thông báo sau khi xuất vẫn ghi "Giữ đúng mẫu 16 cột của {hãng}". `START_HERE.html` (bốn chỗ) và `docs/WINDOWS_RELEASE_CHECKLIST.md` (ba chỗ) cũng còn nói 16 cột. Đã sửa theo mẫu TOS.
3. **Nhỏ.** Hai tiêu đề TOS "Loại hàng" và "Loại hàng " hiện giống nhau trên app. Nhãn trên app được đổi thành "Loại hàng (mã)" và "Loại hàng (tên)". Tiêu đề trong Excel giữ đúng như TOS.

Ghi nhận nhưng không sửa:

- **Ghi file không đồng thời.** `write_bl_change` thay file Excel trước rồi mới thay file JSON. Nếu bước thứ hai lỗi, file Excel mới sẽ không có file truy vết. Hai file nằm cùng thư mục nên khả năng này thấp.
- **Ghi đè file truy vết.** Tab gọi với `overwrite=True` sau khi hộp thoại Lưu đã hỏi về file Excel, nên file `.bl_change.json` cùng tên bị ghi đè mà không hỏi riêng.
- **Container trùng.** Một container thuộc hai B/L trong cùng file, hợp lệ ở VIMC, làm tab dừng với thông báo "container trùng". Cách này đúng với MC62 vì mỗi container chỉ có một dòng TOS, nhưng người dùng phải xử lý ở bước một.
- **Hàng rỗng của VIMC.** Với container rỗng, quy tắc VIMC ghi Hàng hóa là "EMPTY", nên khi đổi B/L, giá trị này thay mô tả của file tàu. Mẫu FF2643S chưa có trường hợp này.

Sau khi sửa:

- 330 test đạt.
- Đối chiếu cục bộ với `Vtos.xlsx` vẫn đúng như trước: chỉ lệch 8 container 40RH rỗng.
- Gate worker-return và reviewer-fast đạt.

## Còn mở

- **MC64:** operator import thử trên TOS. Cần xem TOS tự điền hay bắt nhập 13 cột mà mẫu có giá trị nhưng app để trống: Xác nhận, VGM, Nhóm TL, ba cột Cảng, hai cột Phương Án, hai cột Phương Thức Giao Nhận, hai cột Cntr Class, hai cột Hàng nội/ngoại.
- Mã ISO cho kích cỡ ngoài năm cặp đã thấy, và mã TOS cho loại hàng ngoài GP/ER/ET (ví dụ REEFER, EMPTY), đang để trống.
- Chưa thử tab Đổi B/L với manifest VIMC gốc, vì thư mục chỉ có bill VIMC đã xử lý.
- Chưa có review độc lập cho phần triển khai. Ngày 26-11-2026, operator yêu cầu commit trên cơ sở tự review ở trên. Bản sửa MC52 (DOOR-CY) được commit riêng trước, là `b8f1c50`. Chưa build EXE.
