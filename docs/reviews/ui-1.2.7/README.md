# Kiểm giao diện Manifest Cleaner 1.2.7

Ngày 24-11-2026. Hồ sơ IMPLEMENTATION_WORKER cho MC54, mức R1. Mẫu dùng trong ảnh và các phép thử là dữ liệu tổng hợp. Bằng chứng chờ REVIEWER độc lập xem xét.

## Nguồn thiết kế

Repo chỉ đọc ở `D:/UNG DUNG AI/TOOL AI 2026/Controlled-Vibe-Framework-CVF`. Hai tệp đầu khớp cả SHA-256 được giao và blob tại commit `09c970f449f4806e7dbd852fa449dfe4fb6fcd30`. Các mirror khớp blob của pin upstream nêu trong source receipt ở commit đó. Chính sách project vẫn dùng CORE_ONLY. Các tài liệu UI dưới đây dùng ở mức REFERENCE_ONLY và DEFERRED_PRIVATE_ONLY.

| Tệp tương đối tới repo thiết kế | Dòng đã dùng | SHA-256 |
| --- | --- | --- |
| `DESIGN.md` | 9–83, 101–125, 151–194, 207–208, 225–233, 392–402 | `b2f452daccf4a0e69c4cf15ae3895c10a4616f54619393ab0694329a6f899c96` |
| `docs/reference/agent_system_skills/ui_ux_reference_pack/README.md` | 1–119 | `2efead866b2b92f11b95cf024fd00f440d73626992fab29d694a0174a2b2fb3a` |
| `.private_reference/source_mirrors/evondev__evondevKit/skills/ui-ux/references/layouts/app.md` | 65–74, pin `a3669b675f1810c2284001f1765501f3f3d16db1` | `da52686f49adf22e7db94ba4aed0067d70e24ddc0033048fe459ae4f3459b18d` |
| `.private_reference/source_mirrors/vercel-labs__web-interface-guidelines/command.md` | 29–35, 74–77, pin `434b7f91364665f2f733b310ec54809bf8f37937` | `d246b026f4f29b5823a9cc857f9edf3d2507002e055e32040cadeaf3b38e0234` |

Áp dụng nền sáng trung tính, Segoe UI, ngữ nghĩa màu, thứ bậc nút và thứ tự thao tác–số liệu–bảng–hành động. Nhập liệu, bảng, focus và cuộn dùng widget Tk/ttk. Chọn thang 8 và 16 px logic cho khoảng cách thường dùng, mép và cụm chính. Các khoảng nhỏ dùng bội của 4 px khi cần bố cục dày. Phần CSS/React, thay accent theo theme, DM Sans, responsive di động, motion và ma trận ba theme không áp dụng cho giao diện Tk sáng này. Source giữ trong repo chỉ định. Hướng dẫn upstream được dùng để đối chiếu tiêu chí native.

## Ảnh trước và sau

Mở đúng mẫu qua handler **Mở manifest**. VIMC dùng tab **Cần kiểm tra**, VOSCO dùng tab **Container**. Ảnh trước từ mã 1.2.6 tại `c9cb81f`. Ảnh sau từ working tree 1.2.7, focus vào bảng VIMC hoặc ô tìm VOSCO để thấy trạng thái bàn phím. Ảnh là PNG Win32 `PrintWindow` của riêng cửa sổ, có thanh tiêu đề.

| Mẫu | Mức | 1.2.6 | 1.2.7 |
| --- | ---: | --- | --- |
| `DEMO_VIMC_NEEDS_REVIEW.xlsx` | 100% | [Trước](before-vimc-100.png) | [Sau](after-vimc-100.png) |
| `DEMO_VIMC_NEEDS_REVIEW.xlsx` | 125% | [Trước](before-vimc-125.png) | [Sau](after-vimc-125.png) |
| `DEMO_VIMC_NEEDS_REVIEW.xlsx` | 150% | [Trước](before-vimc-150.png) | [Sau](after-vimc-150.png) |
| `DEMO_VOSCO_INPUT.xlsx` | 100% | [Trước](before-vosco-100.png) | [Sau](after-vosco-100.png) |
| `DEMO_VOSCO_INPUT.xlsx` | 125% | [Trước](before-vosco-125.png) | [Sau](after-vosco-125.png) |
| `DEMO_VOSCO_INPUT.xlsx` | 150% | [Trước](before-vosco-150.png) | [Sau](after-vosco-150.png) |

### Phương pháp và số đo kích thước

Windows có màn hình vật lý 1920 × 1200, work area 1920 × 1140, DPI hệ điều hành 120. Harness chụp ảnh đặt ngữ cảnh Win32 DPI aware để lấy pixel gốc cho cả hai bản. Chạy Tk với `tk scaling` 1,3333 / 1,6683 / 1,9980, tương ứng 100% / 125% / 150%. 125% là mức thật của màn hình. Hai mức còn lại kiểm tỷ lệ bố cục và chữ bằng Tk trên cùng màn hình. Xác minh HWND của bản mới là Per-Monitor V2 qua `GetWindowDpiAwarenessContext`. Chưa đo kéo cửa sổ giữa hai màn hình có DPI khác nhau.

Sau khi đọc mẫu và xử lý idle, đo `winfo_reqwidth`, `winfo_reqheight` và client geometry. Thu cửa chính về minsize rồi kiểm tọa độ và kích thước thật của từng widget. Hai mẫu cho cùng kết quả dưới đây. `winfo_reqheight` là chiều cao yêu cầu tự nhiên của widget, chiều cao hiển thị do geometry và bố cục quyết định.

| Mức | `winfo_reqheight` trước → sau | `winfo_reqwidth` trước → sau | Client khi mở trước → sau | Min client trước → sau | Điều khiển kiểm thấy ở min trước → sau |
| --- | ---: | ---: | --- | --- | ---: |
| 100% | 858 → 669 px | 1497 → 1153 px | 1240×800 → 1240×800 | 1020×650 → 940×535 | 1/9 → 9/9 |
| 125% | 932 → 834 px | 1497 → 1455 px | 1240×800 → 1552×1001 | 1020×650 → 1176×669 | 1/9 → 9/9 |
| 150% | 1025 → 985 px | 1497 → 1726 px | 1240×800 → 1858×1050 | 1020×650 → 1409×802 | 1/9 → 9/9 |

Chín điều khiển đối chiếu giữa hai bản gồm Mở manifest, Xem / sửa dòng, Đã đối chiếu, Loại / khôi phục dòng, Lưu đối chiếu, Xuất, ô JSON, trạng thái và thanh tiến trình. Hồi quy bổ sung kiểm cả ô tìm, notebook và lý do khóa Xuất. Hàng tiêu đề mới cao xấp xỉ 49 px ở 100%. Tăng client từ 1460 lên 1660 px ở mức hệ điều hành 125% làm cột Chủ hàng tăng 134→234 px và cột Hàng hóa tăng 171→271 px. Ở cửa sổ hẹp, cuộn ngang đưa các cột còn lại vào vùng xem, mỗi cột giữ độ rộng đủ cho tiêu đề.

| Hộp thoại đo ở kích thước tối thiểu | 100% | 125% | 150% | Phần đã thấy và thao tác được |
| --- | --- | --- | --- | --- |
| Sửa dòng | 475×330 | 594×413 | 712×495 | Cuộn form tới trường đang focus, lý do và nút Lưu/Hủy ở chân cửa sổ. |
| Chọn sheet | 420×260 | 526×325 | 629×390 | Chọn sheet, đọc mẫu, xác nhận bằng Enter hoặc hủy. |
| Tra nguồn | 510×355 | 638×444 | 764×532 | Bảng và vùng nguyên văn trong cửa sổ. Esc đóng hộp thoại. |
| Cấu hình đọc | 420×290 | 526×363 | 629×435 | Hai ô chọn có nhãn, phần thân cuộn và nút Lưu ở chân cửa sổ. Esc đóng hộp thoại. |

## Checklist nghiệm thu

| Hạng mục | Kết quả | Cách kiểm | DESIGN.md |
| --- | --- | --- | --- |
| Bố cục ở minsize 100%, 125%, 150% | **ĐẠT** | Kiểm bounds trên Windows Tk cho điều khiển chính, nút, lý do khóa, JSON, trạng thái và thanh tiến trình. Kiểm bốn hộp thoại theo bảng trên. Cuộn bảng xem đủ dữ liệu khi hẹp. | §4 Page Rhythm, Dashboard order và §5 Tables & Dense Data |
| Tương phản văn bản ≥4,5:1 | **ĐẠT** | Tính từ màu nền/chữ của style và tag dòng. Nút chính bị khóa 5,96:1, dòng đã loại 6,13:1. | §2 và §8 |
| Trạng thái có chữ | **ĐẠT** | Ảnh VIMC có nhãn lỗi, số lượng, lý do khóa Xuất và tab chữ đậm. Ảnh VOSCO có nhãn cột và trạng thái từng dòng. | §2, §5 và §8 |
| Bàn phím và focus | **ĐẠT** | Tab qua cụm hãng, mở file, KPI, tìm, lọc, notebook, bảng và các nút dòng/lưu/xuất. Kiểm bounds của widget focus. Enter trên bảng mở sửa, Enter nhấn nút, Esc đóng hộp thoại. Ctrl+O gọi mở mẫu, Ctrl+S gọi chọn đích, F1 mở hướng dẫn. Hồi quy Tk kiểm Enter ở ô lý do, Ctrl+S/Ctrl+Enter và Esc ở hộp sửa. Ảnh sau cho thấy focus ở bảng hoặc ô tìm. Hộp thoại hệ điều hành được bắt tại lời gọi. | §5, §6 Focus và §8 |
| Đang đọc và lỗi có bước tiếp theo | **ĐẠT** | Giữ worker đọc VOSCO mẫu để đo chữ trong bảng, thanh tiến trình và lý do khóa. Ép ca lỗi giả lập để kiểm câu nguyên nhân, hướng dẫn chọn đúng file/hãng và Xử lý lại. | §5 Empty / Loading / Error và §8 |
| Nhãn ô nhập, nội dung dài, hướng sắp xếp | **ĐẠT** | Ô tìm, chọn hãng, lý do, F/E, cấu hình và chọn sheet có nhãn. Bảng giới hạn chữ theo cột, nguyên văn còn trong đối chiếu. Kiểm chiều rộng tiêu đề theo font, số căn phải và mũi tên đổi chiều. | §3, §5 Tables & Dense Data và §8 |
| Khoảng cách nhất quán | **ĐẠT** | Dùng khoảng ngắn 8 px và mép 16 px logic, với nấc 4 px cho nhãn gần trường. Đo vùng hành động và bảng ở ba tỷ lệ. | §4 Page Rhythm và §12 Ops / Industrial |
| Giao diện sáng có chủ đích | **ĐẠT** | Tk/ttk dùng palette sáng cố định, font hệ thống Segoe UI. | §1, §2, §3 và §12 Ops / Industrial |

## Tương phản

Dùng độ chói tương đối sRGB và công thức `(L sáng + 0,05) / (L tối + 0,05)`. Tỷ lệ chữ theo cặp màu quy định, không lấy pixel khử răng cưa làm màu chữ.

| Vai trò | Chữ | Nền | Tỷ lệ |
| --- | --- | --- | ---: |
| Chữ chính trên nền trang | `#182A3D` | `#F3F6F9` | 13,47:1 |
| Chữ phụ trên nền trang | `#46596C` | `#F3F6F9` | 6,66:1 |
| Chữ chính trên bảng và nút viền | `#182A3D` | `#FFFFFF` | 14,61:1 |
| Nút chính và dòng được chọn | `#FFFFFF` | `#124C72` | 9,12:1 |
| Nút chính đang hover | `#FFFFFF` | `#0C3C5C` | 11,56:1 |
| Nút chính bị khóa | `#46596C` | `#E4EAF0` | 5,96:1, trước 1,54:1 |
| Nút viền bị khóa | `#46596C` | `#F3F6F9` | 6,66:1 |
| Dòng đã loại | `#46596C` | `#E8EDF2` | 6,13:1, trước 2,75:1 |
| Tab được chọn | `#124C72` | `#E6EFF7` | 7,84:1 |
| Số lỗi / chữ loại dòng | `#9C2E28` | `#FFFFFF` | 7,41:1 |
| Số cảnh báo | `#745000` | `#FFFFFF` | 7,27:1 |
| Số F | `#166146` | `#FFFFFF` | 7,41:1 |
| Chữ dòng lỗi | `#182A3D` | `#FCECEB` | 12,76:1 |
| Chữ dòng cảnh báo | `#182A3D` | `#FFF4D8` | 13,35:1 |
| Viền focus trên nền trang | `#14669A` | `#F3F6F9` | 5,70:1 |

## Finding-To-Governance Learning Disposition

- **Bảo vệ thao tác cuối cửa sổ.** Khi bảng là vùng co giãn, dành kích thước thật cho nút, lý do khóa và trạng thái trước bảng. Đo bounds ở minsize qua các tỷ lệ font. Có thể tái dùng cách kiểm cho app Tk nghiệp vụ. Disposition: dùng trong project, chờ reviewer quyết định có chuyển bài học cho Core.
- **Tab đi theo bố cục nhìn thấy.** Thứ tự dựng widget và thứ tự hiển thị có thể khác khi pack chân cửa sổ trước. Thử Tab trên cửa sổ thật đến các thao tác chính và đảm bảo focus trong vùng xem. Disposition: dùng cùng phép kiểm trước, bằng chứng đang giới hạn ở Windows Tk.
- **Việc đọc reference và giá trị quan sát.** Tách pin/đường dẫn ra khỏi kết quả đo. Dữ liệu hiện đủ cho việc review này. Phân hạng REFERENCE_ONLY và DEFERRED_PRIVATE_ONLY giữ theo nguồn.

## Bằng chứng kiểm và các lượt sửa

Các test mới kiểm minsize ở ba tỷ lệ và lọc từ hai mục tổng hợp. `check_release.py --tests` đạt 277 test và 108 mục SHA-256 trên Python 3.11.9 x64. Nhật ký ở `.cvf/runtime/v127/check-release.log`. Biên nhận CVF và phép đo chi tiết nằm ở `.cvf/runtime/v127/` trong workspace cục bộ. Chưa đóng gói EXE trong lượt worker.

Các lần kiểm trung gian và audit được ghi trong handoff. Tệp mirror đã bị tra nhầm như blob của repo CVF trước khi đối chiếu đúng pin upstream. Harness hủy root nhiều lần từng để lại callback `_poll`. Lượt kiểm tập trung đầu tiên thiếu hỗ trợ `winfo_fpixels` và state mới ở fixture. Lượt sau phát hiện vùng Tra nguồn thiếu widget detail và fake notebook thiếu index. Lượt thử nhiều app trên cùng root phát hiện binding Configure dài hơn vòng đời nhãn, đã sửa phạm vi binding. Kiểm trạng thái một lần đầu dùng so sánh trực tiếp giá trị Tcl và dọn timer Tk bằng API Python không phù hợp. Lượt kiểm lại đọc chuỗi mode bằng `str()`, hủy đúng vòng đời root và đạt.

## Bổ sung tab Cần kiểm tra · 25-11-2026

Danh sách nhóm theo mã vấn đề. Mỗi dòng con hiển thị container, mức, trường và tọa độ có căn cứ. Panel bên phải có thể thu gọn và giữ nguyên câu thông báo, vị trí nguồn, B/L cùng dữ liệu thô đã lưu. Nhóm hiển thị tổng số và gợi cách xử lý. Bảng Container ưu tiên số lỗi chặn, rồi số cảnh báo, khi một dòng thuộc cả hai mức. Ctrl+C sao chép dòng đã chọn theo TSV và giữ nguyên số 0 đầu. [Quyết định giao diện, SHA-256 chỉ dẫn gốc và kế hoạch thử tại Cảng](../../UI_DESIGN_DECISIONS.md)

### Ảnh bổ sung

Ảnh trước của **Phần chi tiết** chụp cửa sổ sửa dòng đã có trong baseline giao diện 1.2.7 trên working tree `c9cb81f`. Ảnh sau chụp panel bên phải. Cả hai dùng `samples/DEMO_VIMC_NEEDS_REVIEW.xlsx`. Ảnh **Rỗng** chụp tab khi chưa mở file. Ảnh **Lỗi đọc** giữ đúng tên tệp mẫu và mô phỏng bộ đọc báo tệp bị khóa, rồi chụp vùng trạng thái và hướng dẫn thử lại trên cửa sổ chính. Các ảnh không chứa dữ liệu từ `dist/`. Phương pháp Win32 PrintWindow và tỷ lệ bằng Tk giữ như phần trước, gồm 125% vật lý và 100%, 150% mô phỏng.

| Trạng thái | 100% trước / sau | 125% trước / sau | 150% trước / sau |
| --- | --- | --- | --- |
| Danh sách | [Trước](issues-before-list-100.png) / [Sau](issues-after-list-100.png) | [Trước](issues-before-list-125.png) / [Sau](issues-after-list-125.png) | [Trước](issues-before-list-150.png) / [Sau](issues-after-list-150.png) |
| Chi tiết | [Trước](issues-before-detail-100.png) / [Sau](issues-after-detail-100.png) | [Trước](issues-before-detail-125.png) / [Sau](issues-after-detail-125.png) | [Trước](issues-before-detail-150.png) / [Sau](issues-after-detail-150.png) |
| Rỗng | [Trước](issues-before-empty-100.png) / [Sau](issues-after-empty-100.png) | [Trước](issues-before-empty-125.png) / [Sau](issues-after-empty-125.png) | [Trước](issues-before-empty-150.png) / [Sau](issues-after-empty-150.png) |
| Lỗi đọc | [Trước](issues-before-error-100.png) / [Sau](issues-after-error-100.png) | [Trước](issues-before-error-125.png) / [Sau](issues-after-error-125.png) | [Trước](issues-before-error-150.png) / [Sau](issues-after-error-150.png) |

### Hồi quy bổ sung

- Kiểm Tk thật ở minsize theo ba tỷ lệ. Hai mức Lỗi chặn/Cảnh báo chọn đúng tab và đúng tập dòng. Từ một dòng, panel hiển thị cùng chuỗi `message` đang lưu và có thể mở vị trí `Manifest!D6`. Chọn nhóm hiện số lượng và vô hiệu hóa thao tác sửa theo dòng. Kiểm hai binding Ctrl+C và giá trị clipboard có seal `001235`.
- Đọc mẫu tổng hợp của ba hãng từ thư mục **Hồ sơ thử tiếng Việt** và xuất file có dấu và khoảng trắng. So byte của `xl/worksheets/sheet1.xml` và `xl/sharedStrings.xml` giữa xuất đối chứng trực tiếp và xuất qua GUI sau khi dựng danh sách. Cả ba cặp khớp. Câu ghi chú tiếng Việt đầy đủ cũng khớp khi mở lại JSON. Kiểm nút mở thư mục thông qua lời gọi Windows nhận đúng đường dẫn đã xuất.
- Giữ luồng đọc nền và trạng thái chờ. Worker đọc chưa có hủy hợp tác hoặc khôi phục phiên nguyên tử nên chưa thêm nút Dừng.
- Khoảng trống hướng dẫn Tkinter được ghi trong [hồ sơ học](../learnings/TKINTER_DESKTOP_UI_GUIDANCE.md). [Intake](../../learning_intake/TKINTER_DESKTOP_UI_GUIDANCE.intake.json) mới ở trạng thái chờ parent xem xét.

| Manifest nghiệp vụ đọc cục bộ | Dòng | Lỗi chặn | Cảnh báo |
| --- | ---: | ---: | ---: |
| VIMC `MNF BS2622S-TT.xls` | 157 | 0 | 1 |
| VOSCO `MNF TAU FF2601S.xls` | 309 | 0 | 2 |
| VINAFCO `MANIFEST-NSG-2535HS.xls` | 4 | 0 | 0 |
| VINAFCO `MANIFEST-NSG-2629DS.XLS` | 57 | 0 | 0 |
| VINAFCO `MANIFEST_V26-0897HS.xlsx` | 261 | 0 | 0 |
| **Tổng** | **788** | **0** | **3** |

Bảng trên khớp kết quả từng tệp trước bổ sung. Bộ đọc để nguyên byte của cả năm tệp nguồn. Openpyxl báo `UserWarning: Print area cannot be set to Defined name: CGL!$A:$H.` khi đọc workbook VINAFCO có vùng in cũ. Đây là thông báo thư viện, không phát sinh vấn đề mới trong phiên.

Lượt kiểm tập trung đầu trả `TypeError: bad operand type for unary +: '_patch'` ở ba ca do dấu nối dòng trong test. Clipboard thất bại với `'001235' != '1235'` vì Python Tkinter chuyển chuỗi số khi lấy cả item. Audit tách từng nguyên nhân. Lượt sửa dùng khai báo context manager có ngoặc và lấy tùy chọn values trực tiếp từ Treeview. Lượt kiểm kích thước tối thiểu trả `AssertionError: 0 is not true : .!notebook.!frame2.!frame2.!frame.!frame2.!text` ở cả ba tỷ lệ. Probe Tk xác nhận thanh tiêu đề và hàng nút chiếm hết vùng khả dụng. Tăng chiều cao tối thiểu từ 535 lên 620 đơn vị bố cục, trong giới hạn màn hình, rồi chạy lại 33 ca GUI đạt.

### Bảng ánh xạ tiêu đề

Bảng lấy từ `manifest_cleaner/issue_display.py`. Test đối chiếu với các mã phát sinh trong engine và ba adapter, gồm mã thiếu trường tạo động. Mã mới từ phiên cũ hoặc nguồn chưa có trong bảng dùng tiêu đề chung theo tên trường nếu có.

| Mã | Tiêu đề giao diện |
| --- | --- |
| `ADDITIONAL_MANIFEST_SHEET` | Có thêm sheet manifest |
| `CONSIGNEE_MISSING` | Thiếu chủ hàng |
| `CONTAINER_MULTIPLE_BL` | Container có nhiều B/L |
| `CONTAINER_UNPARSED` | Chưa đọc dòng container |
| `DESCRIPTION_PACKING_TEXT` | Lẫn quy cách đóng gói |
| `DESCRIPTION_QUANTITY_MISMATCH` | Số lượng không khớp |
| `DESCRIPTION_QUANTITY_SCOPE_UNCLEAR` | Chưa rõ phạm vi đếm |
| `DESCRIPTION_REVIEW` | Kiểm tra mô tả |
| `DUPLICATE_CONTAINER_BL` | Trùng container trong B/L |
| `EMPTY_CARGO_WEIGHT_CONFLICT` | Rỗng nhưng có hàng |
| `EMPTY_WEIGHT_CONFLICT` | Container rỗng vượt ngưỡng |
| `FE_WEIGHT_KIND_UNCONFIRMED` | Chưa rõ loại trọng lượng |
| `GROSS_WEIGHT_BELOW_TARE` | Dưới vỏ tham chiếu |
| `INVALID_CONTAINER` | Sai số container |
| `INVALID_FE` | Sai trạng thái F/E |
| `INVALID_OR_MISSING_BL` | B/L thiếu hoặc sai |
| `INVALID_WEIGHT` | Trọng lượng không hợp lệ |
| `KGS_DOT_GROUPING` | Dấu chấm trong kg |
| `MISSING_BL` | Thiếu số B/L |
| `MISSING_BL_NO` | Thiếu số B/L |
| `MISSING_CARGO_TYPE` | Thiếu loại hàng |
| `MISSING_CLEANED_CONSIGNEE_NAME_FOR_OUTPUT` | Thiếu chủ hàng |
| `MISSING_CONTAINER_NO` | Thiếu số container |
| `MISSING_DESCRIPTION` | Thiếu mô tả hàng |
| `MISSING_FE_STATUS` | Thiếu trạng thái F/E |
| `MISSING_OPERATOR` | Thiếu hãng khai thác |
| `MISSING_SIZE_TYPE` | Thiếu kích cỡ |
| `MISSING_VTOS_SIZE` | Thiếu kích cỡ VTOS |
| `MISSING_WEIGHT` | Thiếu trọng lượng |
| `NO_ACTIVE_RECORDS` | Không còn dòng xuất |
| `NO_SHEETS` | Không có sheet |
| `SETTINGS_CHANGED` | Cấu hình đã đổi |
| `SHEET_NOT_FOUND` | Không tìm thấy sheet |
| `SIZE_TYPE_MISSING` | Thiếu kích cỡ |
| `SOURCE_FORMULA_ERROR` | Ô nguồn lỗi công thức |
| `SOURCE_FORMULA_UNCALCULATED` | Công thức chưa tính |
| `TANK_WEIGHT_REVIEW` | Kiểm trọng lượng bồn |
| `UNKNOWN_OPERATOR` | Chưa nhận diện hãng |
| `UNKNOWN_SIZE_TYPE` | Kích cỡ chưa quy đổi |
| `VIMC_BL_CONFLICT` | Số B/L không khớp |
| `VIMC_BL_MISSING` | Thiếu số B/L |
| `VIMC_CONSIGNEE_MISSING` | Thiếu chủ hàng |
| `VIMC_CONTAINER_DATA_CONFLICT` | Dữ liệu trùng khác nhau |
| `VIMC_CONTAINER_FORMAT` | Sai định dạng container |
| `VIMC_CONTAINER_UNPARSED` | Chưa đọc dòng container |
| `VIMC_DUPLICATE_IN_BL` | Trùng container trong B/L |
| `VIMC_FE_UNRESOLVED` | Chưa rõ F/E |
| `VIMC_HEADER_INCOMPLETE` | Thiếu cột tiêu đề |
| `VIMC_HEADER_NOT_FOUND` | Chưa nhận diện tiêu đề |
| `VIMC_LAYOUT_AMBIGUOUS` | Trọng lượng chưa rõ đơn vị |
| `VIMC_LEGACY_COMPACT_CONTAINER` | Mã container dạng ngắn |
| `VIMC_MARKS_SIZE_CONFLICT` | Kích cỡ không khớp |
| `VIMC_NO_CONTAINERS` | Không có container |
| `VIMC_SEAL_TYPE_AMBIGUOUS` | Chưa rõ seal, cỡ |
| `VIMC_SIZE_MISSING` | Thiếu kích cỡ |
| `VIMC_SIZE_UNKNOWN` | Kích cỡ chưa quy đổi |
| `VIMC_STATUS_GOODS_CONFLICT` | F/E khác mô tả |
| `VIMC_STATUS_SCOPE_CONFLICT` | F/E khác tiêu đề |
| `VIMC_WEIGHT_INVALID` | Không đọc được trọng lượng |
| `VIMC_WEIGHT_MISSING` | Thiếu trọng lượng |
| `VIMC_ZERO_LOADED_WEIGHT` | Trọng lượng bằng 0 |
| `VINAFCO_AMBIGUOUS_COLUMNS` | Cột nguồn chưa rõ |
| `VINAFCO_BL_MISSING` | Thiếu số B/L |
| `VINAFCO_CONSIGNEE_MISSING` | Thiếu chủ hàng |
| `VINAFCO_CONTAINER_MISSING` | Thiếu số container |
| `VINAFCO_CONTAINER_UNPARSED` | Chưa đọc số container |
| `VINAFCO_FE_CONFLICT` | F/E không khớp |
| `VINAFCO_FE_DEFAULTED` | F/E dùng mặc định |
| `VINAFCO_FE_INFERRED` | F/E suy từ cân nặng |
| `VINAFCO_HEADER_CHANGED` | Tiêu đề đã đổi |
| `VINAFCO_HEADER_NOT_FOUND` | Chưa nhận diện tiêu đề |
| `VINAFCO_MISSING_COLUMN` | Thiếu cột nguồn |
| `VINAFCO_MULTIPLE_TABLES` | Cần chọn bảng |
| `VINAFCO_NO_CONTAINERS` | Không có container |
| `VINAFCO_READ_ERROR` | Không đọc được file |
| `VINAFCO_SOC_COC_CONFLICT` | SOC và COC xung đột |
| `VINAFCO_SUMMARY_MISMATCH` | Bảng tổng hợp lệch |
| `VINAFCO_TYPE_UNMAPPED` | Kích cỡ chưa quy đổi |
| `VINAFCO_WEIGHT_INVALID` | Không đọc được trọng lượng |
| `VOSCO_ADJACENT_CONTAINER_CANDIDATE` | Container ở cột bên |
| `VOSCO_LAYOUT_NOT_RECOGNIZED` | Chưa nhận diện bố cục |
| `WEIGHT_ASSOCIATION_AMBIGUOUS` | Chưa ghép được trọng lượng |
| `WEIGHT_INVALID` | Không đọc được trọng lượng |
| `ZERO_FULL_WEIGHT` | Trọng lượng bằng 0 |

### Kiểm tra phát hành và bàn giao bổ sung

Kiểm phát hành cục bộ bằng `.venv/Scripts/python.exe -B scripts/check_release.py --tests`. Số kiểm thử tăng từ 277 lên 281. Danh mục kiểm SHA-256 tăng từ 108 lên 137 đường dẫn. Log kiểm thử và biên nhận pre-dispatch, worker-return nằm trong `.cvf/runtime/v127/supplement/`. Hồ sơ chuyển REVIEWER độc lập từ working tree.

| Phần | Tệp |
| --- | --- |
| Mã và kiểm thử | `manifest_cleaner/gui.py`, `manifest_cleaner/issue_display.py`, `tests/test_gui_v110.py` |
| Thiết kế và bằng chứng | `docs/UI_DESIGN_DECISIONS.md`, `docs/reviews/ui-1.2.7/README.md`, 24 ảnh `issues-*.png` trong cùng thư mục |
| Bài học và hồ sơ CVF | `docs/reviews/learnings/TKINTER_DESKTOP_UI_GUIDANCE.md`, `docs/reviews/learnings/README.md`, `docs/learning_intake/TKINTER_DESKTOP_UI_GUIDANCE.intake.json`, `docs/catalog/ARTIFACT_REGISTRY.json`, `docs/INDEX.md`, `CVF_SESSION_MEMORY.md`, handoff active |
| Checksum | `PACKAGE_MANIFEST.sha256` |

## Review độc lập · 25-11-2026

REVIEWER độc lập chạy lại 281 test, pr-ci 8/8, catalog, activation CURRENT_ASSESSED và chụp giao diện trên Windows 125% với mẫu tổng hợp và manifest thật cục bộ. Engine, exporter và adapter không đổi. Bố cục, DPI, dải tóm tắt, mẫu danh sách và chi tiết, lý do khóa Xuất đạt yêu cầu.

Phát hiện cần sửa: cột định danh của bảng Container chỉ đo theo tiêu đề. Với manifest VIMC thật, 157/157 số B/L bị cắt. Một số seal của VIMC và VINAFCO cũng bị cắt. Reviewer-local repair: sau mỗi lần làm mới, các cột Số container, Số niêm chì, Số B/L, Kích cỡ VTOS và Hãng khai thác giãn theo giá trị dài nhất, không dưới độ rộng tiêu đề và có trần. Thêm một test Tk thật cho B/L và seal dài. Đo lại trên ba manifest thật: 0 ô bị cắt ở ba cột định danh.

Còn lại không chặn: nhãn trường dạng "Trọng lượng +1" khó hiểu, cột số căn phải sát cột Chủ hàng, cột Chủ hàng bị thu hẹp khi các cột định danh rộng, hai dòng trạng thái nói cùng một ý.

### Sửa theo yêu cầu operator · 25-11-2026

Operator yêu cầu sửa hết các điểm còn lại và bỏ dòng "Đang dùng". Agent review chuyển sang vai REPAIR_WORKER cho lượt sửa giao diện R1 này. Lượt sửa không đổi engine, exporter, adapter hay file xuất.

- Nhãn trường của vấn đề nhiều trường ghi đủ tên, ví dụ "Trọng lượng, Hàng hóa", thay cho "Trọng lượng +1".
- Trọng lượng căn phải có hai khoảng trắng đệm dạng figure space để tách khỏi cột Chủ hàng. Ctrl+C bỏ phần đệm.
- Cửa sổ mặc định rộng 1440 × 820 px logic, có giới hạn theo vùng làm việc. Chủ hàng và Hàng hóa rộng hơn và co lại trước khi bảng cần cuộn ngang. Với VIMC thật ở 125%, bảng nằm trọn trong cửa sổ.
- Khi có lỗi chặn, dòng trạng thái chỉ ghi số bản ghi đã đọc. Lý do khóa Xuất vẫn nằm cạnh nút.
- Bỏ dòng "Đang dùng". Dòng tóm tắt chỉ nêu sheet khi tệp có nhiều sheet, và chỉ nêu quy ước đọc khi khác mặc định. Dòng đối soát chỉ hiện khi có nội dung, không để lại khoảng trống.

Thêm hai test GUI và cập nhật một test sao chép. Người sửa cũng là người review lượt này. Phạm vi R1 cho phép một agent giữ hai vai khi có bằng chứng kiểm. Cần reviewer khác nếu operator muốn tách vai.

### Build và chạy thử EXE 1.2.7 · 25-11-2026

Build từ commit `d58ff6292f2253bf603f6b844b7187a624842783` vào `dist/1.2.7/ManifestCleaner`, PyInstaller 6.22.3, Python 3.11.9 x64, dependency theo pin. Các bản build cũ giữ nguyên. Gói chứa đủ ba adapter, lớp hiển thị vấn đề và giao diện. Ngoài thư mục samples, gói không chứa manifest nghiệp vụ. SHA-256 EXE `0dc136197c0e4d6a15eb335206b06a26e75e87e7ae01171b4c90b256aed652e0`.

Chạy bản sao của gói từ thư mục có dấu tiếng Việt và khoảng trắng, thư mục làm việc ngoài gói. Cửa sổ mở với tiêu đề phiên bản 1.2.7. Mở `DEMO_VOSCO_INPUT.xlsx` qua hộp thoại chọn file: 1 container, 0 lỗi chặn, 0 cảnh báo. Xuất thành công, thông báo giữ mẫu 16 cột VOSCO và hiện nút Mở thư mục kết quả.

Sự cố trong lúc chạy thử: script điều khiển hộp thoại lưu không đổi được tên file trong hộp thoại kiểu mới của Windows. Hai lần, app xuất cặp Excel/JSON mẫu vào thư mục dùng gần nhất `Manifest Cleaner Final/VOSCO`. Reviewer đã xác nhận thời điểm tạo, xóa đúng hai cặp file mẫu và kiểm Git của repo đó sạch. Không file gốc nào bị đổi. Nội dung hai file xuất từ EXE chưa được kiểm độc lập vì đã xóa. Đường xuất từ nguồn cùng commit đã có hồi quy giữ nguyên byte nội dung ô.

Phát hiện mới, có từ trước 1.2.7: hộp thoại Xuất file và Lưu đối chiếu không đặt thư mục ban đầu. Windows mở thư mục dùng gần nhất, có thể là thư mục của hãng khác. Đề xuất lượt sau: đặt thư mục ban đầu là thư mục của manifest đang xử lý và thêm test.

### Thư mục mặc định của hộp thoại lưu · 25-11-2026

Theo yêu cầu operator, hộp thoại Xuất file và Lưu đối chiếu mở sẵn thư mục chứa manifest đang xử lý. Nếu thư mục đó không còn, Windows dùng thư mục mặc định của hệ thống. Nút và tiêu đề hộp thoại xuất đổi thành "Xuất file Manifest". Kiểm trên Windows thật: khi Windows còn nhớ thư mục tham chiếu từ lần trước, cả hai hộp thoại vẫn mở đúng thư mục của manifest; phép kiểm chỉ đọc thanh địa chỉ rồi bấm Cancel, không ghi file. Thêm một test và mở rộng test xuất. Đã commit theo yêu cầu operator, chưa build EXE; operator tự kiểm trước khi build.


### Tinh chỉnh hướng A và số cont 20'/40' · 25-11-2026

Operator chọn hướng A sau khi xem hai ảnh mô phỏng dữ liệu tổng hợp, và yêu cầu thẻ F hiện số cont 20'/40'. IMPLEMENTATION_WORKER làm trong MC54, mức R1, chỉ sửa phần hiển thị. Không đổi engine, exporter, adapter, JSON hay 16 cột. Activation CURRENT_ASSESSED. Pre-dispatch chạy từ Core đã pin PASS 7/7. Quyết định chi tiết nằm trong [quyết định giao diện](../../UI_DESIGN_DECISIONS.md).

- Đổi `manifest_cleaner/gui.py`: bảng màu bổ sung, nút, checkbox vẽ theo DPI, thẻ có sọc màu, số cont 20'/40', màu thẻ cảnh báo theo giá trị, dòng xen kẽ, ký hiệu trạng thái, thanh cuộn mảnh, thanh tiến độ ẩn màu khi rảnh, ô JSON cạnh nút Xuất.
- Đổi `tests/test_gui_v110.py`: cập nhật kỳ vọng Ctrl+C có ký hiệu trạng thái và vị trí ô JSON. Thêm ba test: phân loại cỡ theo mã VTOS, cách ghi thẻ có 45' và chưa rõ cỡ, và test Tk thật cho thẻ, màu cảnh báo, dòng xen kẽ, thanh tiến độ và checkbox.
- Lượt đầu, test kích thước nhỏ nhất báo thanh công cụ thừa 7 px ở 125%. Ở 150%, khung chi tiết của tab Cần kiểm tra bị ép mất. Nguyên nhân là đệm nút, đệm checkbox, ô nhập và tiêu đề bảng tăng thêm. Trả các đệm này về giá trị cũ thì cả ba tỷ lệ đều đạt. Ở 150%, ảnh chụp tại kích thước nhỏ nhất cho thấy dòng phụ của thẻ Container bị cắt. Rút gọn thành dạng `20' 132 · 40' 184 · 45' 1` thì hiện đủ.
- Đối chiếu trên manifest VFON 317 dòng, đọc cục bộ, ảnh không đưa vào repo: F `129 / 153` (tổng 282), E `3 / 31` cộng 1 cont 45', Container 317 = 132 + 184 + 1. SHA-256 ba manifest gốc trước và sau phép kiểm không đổi.
- Ảnh mẫu tổng hợp của ba hãng ở 100%, 125% và 150% lưu tại `.cvf/runtime/ui-polish`.

Giới hạn: chưa build EXE, chưa đổi số phiên bản, chưa có reviewer độc lập cho lượt này.

Phản hồi operator sau khi dùng thử. `45' 1` là một cont 45 feet. Khi đã tách 45', cần ghi theo thứ tự 20'/40'/45'. Bỏ dòng nhắc "Mở manifest để xuất" ở chân cửa sổ. Trạng thái có thể nằm ngang dòng tên file. Đã sửa như sau.

- Thẻ F/E ghi `a / b`, hoặc `a / b / c` khi có 45'. Với VFON: F `129 / 153`, E `3 / 31 / 1`. Tổng E là 35, cont 45' không nằm trong 31. Thẻ Container ghi `20'/40'/45': 132/184/1`.
- Bỏ dòng lý do khóa Xuất. Nút Xuất vẫn bị khóa theo cùng điều kiện. Trạng thái và thanh tiến độ nằm cùng dòng với tên file. Chân cửa sổ chỉ còn dòng tác giả, căn giữa, nên bảng được thêm khoảng hai dòng.
- Cập nhật test kích thước nhỏ nhất, test vị trí tác giả và trạng thái, và test cách ghi số. Ảnh ở 150% với kích thước nhỏ nhất cho thấy đủ ba số và dòng phụ. Câu trạng thái dài nhất cùng thanh tiến độ đang chạy nằm vừa một dòng ở 125%.

### Commit, push và build · 25-11-2026

Commit `3a065f3` đã push lên `main` của `CVF-Ecosystem/Manifest_Cleaner`. Build EXE vào `dist/1.2.7-3a065f3/ManifestCleaner/`, SHA-256 `5a626edf2b5fdb2c18e43afde5dd018a168ad1b9c4e3b619d1fc286ca8bed1ba`. Mở thử 12 giây và không thoát. Thay thế dòng "Giới hạn: chưa build EXE" ở trên. Số phiên bản vẫn là 1.2.7. Chưa có reviewer độc lập và chưa thử trên máy Cảng.
