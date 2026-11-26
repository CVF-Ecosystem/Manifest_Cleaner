# Xuất theo mẫu TOS và đổi B/L giữa hai hãng

Ngày 26-11-2026. Trước đây file xuất của mỗi hãng có thứ tự và tên cột riêng, và người dùng dán từng cột vào phần mềm quản lý container TOS của Cảng. Operator đưa `Manifest/Vtos.xlsx`, là mẫu chuẩn TOS gồm 46 cột, và chốt bốn quyết định:

- Dùng một mẫu xuất chung theo thứ tự TOS. File xuất sẽ được import thẳng vào TOS, và operator tự kiểm thử trên TOS.
- Quy tắc một phiên xử lý một workbook của một hãng được giữ nguyên.
- Khi hãng VIMC gửi hàng qua tàu VOSCO, việc đổi B/L VOSCO sang B/L VIMC làm ở một chỗ tách riêng do người dùng tự thực hiện. Manifest VIMC đi qua bước một với quy tắc VIMC hiện có.
- Ghi chú để trống trong file Excel và vẫn hiện trên app. Trọng lượng lấy theo manifest gốc.

Các quyết định này thay ba quy tắc cũ:

- Quy tắc "Giữ định dạng nhập Cảng 16 cột đã chốt cho từng hãng" trong `AGENTS.md` của project.
- Dòng "Tên/thứ tự cột VIMC khác hai app còn lại được giữ" trong `docs/AUDIT_FIXES.md`, vốn chờ hệ thống Cảng xác nhận.
- Quyết định ngày 24-11-2026 rằng Ghi chú trong file Excel giữ đủ thông điệp.

Căn cứ là mẫu TOS do operator cung cấp và quyết định của operator. Hồi quy nằm ở MC63.

## Tiêu chí nghiệm thu

| ID | Kết quả cần đạt |
|---|---|
| MC61 | Cả ba hãng xuất cùng một mẫu: đủ 46 tiêu đề TOS, đúng thứ tự, kể cả bốn tiêu đề trùng có dấu cách cuối. App chỉ điền các cột có căn cứ: Số lượng, Số BL, Số Container, Hãng khai thác, Kích cỡ (mã VTOS), F/E, TL hàng, hai cột seal dạng văn bản, Chủ hàng, hai cột Loại hàng và Hàng hóa. Kích cỡ ISO điền theo năm cặp mã đã thấy trong mẫu TOS. Cột "Loại hàng" ghi mã GP, ER hoặc ET và cột "Loại hàng " ghi đúng tên trong TOS (General, Empty Reefer, EMPTY TANK), lần lượt cho loại hàng GENERAL, EMPTY REEFER và EMPTY TANK của app. Loại hàng khác: cột mã để trống, cột tên ghi giá trị của app. Ghi chú và các cột TOS khác để trống. Độ chính xác (%) và STT không còn trong file Excel. Giữ quy tắc theo hãng về số lượng, làm tròn, EMPTY, kiểm seal và tô màu cảnh báo. Xem trước trên app giữ STT và Ghi chú. Phiên review v2 lưu từ bản 16 cột mở lại được và xuất theo mẫu TOS. |
| MC62 | Cửa sổ Đổi B/L mở được khi chưa có phiên. Cửa sổ nhận hai file đã xuất ở bước một: file tàu và file B/L của hãng gửi hàng. App ghép theo số container và lấy từ file hãng gửi sáu trường: Số lượng, Số BL, Hãng khai thác, Chủ hàng, TL hàng, Hàng hóa. Giá trị trống không đè giá trị đã có. Khác biệt kích cỡ, F/E, seal hoặc loại hàng được báo và giữ theo file tàu. Container chỉ có ở file hãng gửi, và B/L gom chỉ đổi một phần, được liệt kê. App báo và dừng trong bốn trường hợp: file không đúng mẫu TOS, container trùng trong một file, hai lần chọn cùng một file, không có container chung. Mẫu TOS không ghi tên tàu hay chuyến. Vì vậy cửa sổ hiện tên file nguồn của từng file để người dùng xác nhận, và chỉ chặn khi không có container chung. Kết quả gồm file TOS mới và JSON truy vết hai nguồn: SHA-256 và từng thay đổi. File nguồn không bị ghi. |
| MC63 | Có hồi quy tự chứa cho MC61 và MC62 bằng fixture tổng hợp. Đối chiếu cục bộ FF2643S cộng bill VIMC với `Vtos.xlsx` trên 297 container. Khác biệt duy nhất được chấp nhận ở các cột app điền là 8 container 40RH rỗng có TL hàng 3,8 tấn theo manifest so với 4,5 tấn trong TOS. Dữ liệu nghiệp vụ không đưa vào Git. Bộ kiểm thử chạy đúng pin. |
| MC64 | Operator import file trên TOS và xác nhận kết quả. Các cột TOS app để trống, và các mã ISO hoặc mã loại hàng chưa có bằng chứng, được giữ ở trạng thái mở cho tới khi có kết quả thử. |

## Bằng chứng ban đầu

- Mẫu TOS FF2643S có 297 dòng. Với 36 container VIMC gửi qua VOSCO, TOS dùng B/L, hãng, chủ hàng, trọng lượng, hàng hóa và số lượng của VIMC. Sau khi ghép thử, chín trường so sánh khớp TOS trên cả 297 container, trừ 8 container 40RH rỗng: TOS ghi 4,5 tấn, manifest ghi 3,8 tấn, và operator chốt dùng số của manifest.
- Trong mẫu TOS, Kích cỡ là mã VTOS và khớp 297/297 với cột Kích cỡ VTOS của app. Kích cỡ ISO theo mẫu: 20DC 22G0, 40HC 45G0, 45HC L5G0, 40RH 45R0, 20TK 22T0. Mã và tên loại hàng: GP General, ER Empty Reefer, ET EMPTY TANK.
- Ghi chú trong TOS là nhãn ngắn do người nhập gõ, không lấy từ manifest.
- Trong mẫu, 13 cột có giá trị trên cả 297 dòng nhưng file của app để trống: Xác nhận, VGM, Nhóm TL, Cảng xếp, Cảng dỡ, Cảng đích, hai cột Phương Án, hai cột Phương Thức Giao Nhận, hai cột Cntr Class và hai cột Hàng nội/ngoại. Khi import thử ở MC64, operator cần kiểm xem TOS tự điền các cột này hay yêu cầu nhập.

## Coverage snapshot

```cvf-milestone-coverage-json
{
  "schemaVersion": "cvf.milestoneCoverage@1.0.0",
  "authority": {
    "path": "docs/roadmaps/MC_TOS_EXPORT.md",
    "heading": "## Tiêu chí nghiệm thu",
    "sha256": "afb98ff7925ae385eba8bfab15400bcf3aa3fbd374f6ccbbe9d96e2c6ab63348"
  },
  "milestone": {
    "id": "MC3",
    "consumer": "Người xử lý manifest tại Cảng",
    "outcome": "File xuất import thẳng vào TOS, gồm cả trường hợp đổi B/L giữa hai hãng",
    "checkpoint": {
      "trigger": "Đã có file mẫu TOS từ app và kết quả đối chiếu cục bộ",
      "owner": "Operator tại Cảng",
      "decision": "Chấp nhận sau khi import thử trên TOS hoặc trả về danh sách cột cần sửa"
    }
  },
  "phase": "PLAN",
  "action": {
    "kind": "PLAN",
    "selected": [],
    "owner": "Orchestrator",
    "output": "Tiêu chí và kế hoạch",
    "budgetMinutes": 180,
    "stop": "Không suy đoán mã TOS chưa có bằng chứng. Không ghi vào file nguồn. Sau một lượt sửa thất bại, audit trước lượt phụ thuộc.",
    "next": "Work order WO_MC_TOS_EXPORT"
  },
  "rows": [
    {"id": "MC61", "state": "NOT_STARTED", "gap": "Mỗi hãng một mẫu 16 cột riêng", "owner": "Orchestrator / maintainer", "destination": "Mốc MC61 trong roadmap MC3", "evidence": []},
    {"id": "MC62", "state": "NOT_STARTED", "gap": "Đổi B/L đang làm tay trên TOS", "owner": "Orchestrator / maintainer", "destination": "Mốc MC62 trong roadmap MC3", "evidence": []},
    {"id": "MC63", "state": "NOT_STARTED", "gap": "Chưa có hồi quy cho mẫu TOS", "owner": "Orchestrator / maintainer", "destination": "Mốc MC63 trong roadmap MC3", "evidence": []},
    {"id": "MC64", "state": "NOT_STARTED", "gap": "Chưa import thử trên TOS", "owner": "Operator", "destination": "Mốc MC64 trong roadmap MC3", "evidence": []}
  ],
  "supportingWork": [],
  "conclusions": {
    "tranche": "PENDING",
    "trancheSummary": "Cần làm và kiểm",
    "trancheEvidence": [],
    "product": "PENDING",
    "productSummary": "Chờ import thử trên TOS",
    "acceptance": [],
    "owner": "Orchestrator"
  }
}
```
