# TKINTER_DESKTOP_UI_GUIDANCE

Status: CANDIDATE
Source project: Manifest_Cleaner
Source revision: c9cb81f282d4c1c5d8ad0ebef6a999e1ba42025a
Updated: 2026-11-25

## Trigger / Observation

CVF chưa có hướng dẫn UI cho ứng dụng desktop Tkinter. Project tự suy ra từ DESIGN.md mục 12 Ops/Industrial. Hướng dẫn hiện có mô tả thứ bậc, trạng thái và khả năng truy cập ở mức nguyên tắc. Phép kiểm Tk cần thêm cách đặt vùng làm việc theo DPI, giữ các điều khiển đáy và xác minh focus trong widget có cuộn. Đây là khoảng trống hướng dẫn áp dụng cho desktop.

## Source / Evidence

Worker đã đọc `DESIGN.md` §1, §5, §8, §12 tại pin CVF gốc `09c970f449f4806e7dbd852fa449dfe4fb6fcd30` và chỉ dẫn gốc có SHA-256 `802b773bd8bc2aeb19fe0e29e589fac85001e11af4a6f6e45e4a634ef05b3341`. Release đang ở working tree trên source revision nêu trên. [Quyết định project](../../UI_DESIGN_DECISIONS.md) và [bằng chứng có ảnh tổng hợp](../ui-1.2.7/README.md) ghi phạm vi và điều kiện đo. Nguồn và kết quả là bằng chứng worker, chờ kiểm độc lập.

## Project Action / Verification

IMPLEMENTATION_WORKER dùng ttk `clam`, Per-Monitor V2, bảng theo loại vấn đề và chi tiết bản ghi. Dùng kiểm Tk thật để đo bounds và thao tác phím, kiểm Ctrl+C giữ số 0 đầu, và đối chiếu XML nội dung ô trên mẫu tổng hợp. Người làm tiếp UI native đọc hồ sơ này trước khi chọn theme hoặc sửa layout. Môi trường thật tại Cảng và kéo cửa sổ giữa các màn hình DPI khác nhau còn mở.

## Parent Value / Dedup

Ứng viên bổ sung một ví dụ kiểm Tk/Windows vào hướng dẫn frontend hiện có. Điểm dùng lại gồm kiểm vị trí widget ở minsize, đo tương phản trạng thái vô hiệu, kiểm thứ tự Tab thực và phân biệt tỷ lệ Tk mô phỏng với DPI vật lý. Owner frontend của CVF so với hướng dẫn đang có trước khi quyết định phạm vi. Bằng chứng mới giới hạn ở một app, không đề nghị tạo thêm skill. [Biên nhận đưa ứng viên vào danh sách xem xét](../../learning_intake/TKINTER_DESKTOP_UI_GUIDANCE.intake.json)

## Feedback State And Links

| Ranh giới | Trạng thái | Bằng chứng / bước tiếp theo |
| --- | --- | --- |
| Sửa tại project | WORKER_VERIFIED | Working tree 1.2.7 và hồ sơ kiểm, REVIEWER độc lập tiếp nhận. |
| Quyết định của parent | PENDING_PARENT_ASSESSMENT | Owner CVF so với hướng dẫn đang có. |
| Triển khai tại parent | NOT_IMPLEMENTED | Chờ quyết định. |
| Trả về project | NOT_RETURNED | Chờ phiên bản hoặc receipt nếu có. |
| Project áp dụng bản trả về | NOT_APPLIED | Chờ operator và kiểm độc lập. |

## Claim Boundary

Đo trên Windows Tk tại máy phát triển, DPI thực 125% và tỷ lệ Tk 100/150%. Ảnh và test mẫu chỉ dùng dữ liệu tổng hợp. Hồ sơ không có nghiệm thu EXE, máy Cảng hoặc xác nhận thay đổi hướng dẫn parent.
