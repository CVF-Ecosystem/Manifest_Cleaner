# Dữ liệu golden tổng hợp v1.1.0

Ngày chuẩn bị: **22-11-2026**.

## Phạm vi và giá trị chứng minh

Bộ `tests/fixtures/golden_v110` có ba workbook đầu vào cố định cùng ba file
kỳ vọng JSON viết tay. Các kỳ vọng được suy ra bằng cách đọc trực tiếp ô nguồn
và hợp đồng nghiệp vụ đã giữ lại, không được tạo từ kết quả chạy parser.

| Hãng | Nguồn kiểm tra | Kỳ vọng quan trọng |
|---|---|---|
| VOSCO | Hai container, ô hàng chứa RICE / PORT HAIPHONG / STEEL | Giữ đúng RICE và STEEL; hai container F, mỗi container 25 tấn; VOC; seal có số 0 đầu |
| VINAFCO | Một container, header GWKGS và số 25000 | 25 tấn; BL001; MSCU1234567; seal 001234; 20DC; VFC |
| VIMC | Ba dòng demo gốc, layout trọng lượng trước/sau mô tả | Nội bộ 16.055/8/27 tấn; lúc xuất 16.06/8/27; 20GP → 20DC; giữ 40HC/20DC; VMC; số lượng 3 |

Các con số, tên trường và mapping đã được chép thành giá trị cố định. Test kiểm
cả canonical records, hàng chuẩn bị xuất và cells trong file Excel thực; đồng
thời kiểm chính xác 16 tên/thứ tự cột của từng hãng. Các giá trị thập phân trong
bảng dùng ký pháp JSON với dấu chấm thập phân. Điểm heuristic và câu chữ
cảnh báo không phải kỳ vọng cố định.

**Bộ này là dữ liệu tổng hợp, chưa có xác nhận nghiệp vụ từ Cảng.** Ba test pass
chứng minh các ca hồi quy nêu trên hoạt động; không chứng minh mọi biến thể
manifest hoặc tỷ lệ chính xác trong vận hành. Không dùng fixture để thay thế
việc kiểm tra import trên môi trường thử của hệ thống cảng.

## Bảo toàn và chạy lại

File nguồn được sao nguyên bytes từ hai workbook audit và một workbook demo
của gói v1.0.0 gốc. SHA-256 nằm trong expected JSON; test xác nhận trước/sau chạy.
Input được đặt chỉ đọc trong môi trường chuẩn bị gói. Các file xuất phục vụ test
được tạo riêng trong thư mục tạm và tự dọn sau khi kiểm tra.

```bash
python -m unittest tests.test_golden_v110 -v
```

Không có chức năng tự regenerate expected. Nếu thay đổi nghiệp vụ, cần review
nguồn, lý do và diff kỳ vọng bằng tay. Khi có mẫu thật cùng output được cảng
chấp nhận, bổ sung bộ riêng, ghi người/ngày xác nhận và phiên bản quy tắc; không
đổi nhãn dữ liệu tổng hợp hiện tại thành dữ liệu thật.
