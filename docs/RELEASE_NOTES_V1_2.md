# Manifest Cleaner 1.2.0

- VINAFCO nhận diện bảng tổng hợp theo cấu trúc, giữ vị trí nguồn và đối chiếu với số container đã đọc. Chênh lệch được nêu khi phạm vi và số liệu nguồn đủ rõ. Tổng thiếu nhãn được báo là chưa xác định.
- Khi VINAFCO có nhiều bảng ứng viên, app hiển thị sheet, dòng tiêu đề và vài dòng mẫu để người dùng chọn cho manifest đang mở.
- VOSCO đưa ứng viên ở cột liền kề vào mục cần kiểm tra khi dòng có cấu trúc số container và kích cỡ phù hợp trong vùng chi tiết đã nhận diện. Dòng thiếu B/L hoặc trọng lượng vẫn có thể được báo để kiểm tra.
- CLI hỗ trợ đầu ra chuyển hướng dùng mã hóa Windows cũ. JSON vẫn giữ được ký tự Unicode qua escape hợp lệ.
- Danh sách hãng, bộ đọc, operator, cấu hình mặc định và quy tắc xuất được đăng ký chung cho engine, GUI, CLI và đóng gói. Các mẫu Excel 16 cột và review v2 tiếp tục tương thích.

Bản này hỗ trợ VOSCO, VIMC và VINAFCO. Nghiệm thu nhập Cảng cần dữ liệu và quy tắc do đầu mối nghiệp vụ xác nhận.
