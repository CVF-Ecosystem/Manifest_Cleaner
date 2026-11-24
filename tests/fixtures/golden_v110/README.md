# Golden fixtures v1.1.0 — dữ liệu tổng hợp

**Đây là dữ liệu tổng hợp, chưa phải manifest hoặc kết quả được Cảng xác nhận.**
Không dùng các fixture để ước tính tỷ lệ chính xác trên dữ liệu thật.

Ba workbook là bản sao nguyên bytes của nguồn cố định:

| Input | Nguồn tạo trước bản sửa | Điều cần giữ |
|---|---|---|
| `vosco_metadata_lines.input.xlsx` | Workbook tái hiện audit `vosco_shifted_description.xlsx` | Hai container có hàng RICE/STEEL; dòng PORT ở giữa không dịch hàng; mỗi container 25 tấn |
| `vinafco_joined_kg_header.input.xlsx` | Workbook tái hiện audit `joined_unit.xlsx` | GWKGS ưu tiên kg: 25.000 kg thành 25 tấn; số BL/seal/size/operator đúng |
| `vimc_mixed_layouts.input.xlsx` | `samples/DEMO_VIMC_INPUT.xlsx` trong gói v1.0.0 gốc | Ba layout đã hỗ trợ; 16.055/8/27 tấn nội bộ; 16.06/8/27 tấn lúc xuất (ký pháp dấu chấm thập phân trong JSON) |

Mỗi file `.expected.json` được **viết tay sau khi đọc ô nguồn**, có giải thích
`reasoning`. Không chạy parser hoặc exporter để sinh kỳ vọng. Không có script
regenerate golden. Cấu hình dùng để đọc nguồn được ghi cố định trong JSON.

Kỳ vọng kiểm tra số lượng bản ghi, các trường nghiệp vụ, đơn vị nội bộ, mapping,
16 tên/thứ tự cột và giá trị xuất quan trọng. Chuỗi cảnh báo và điểm heuristic
không bị đóng băng, vì thay đổi nội dung hướng dẫn không nên làm sai golden.

SHA-256 của input được cố định trong JSON và được kiểm tra trước/sau test.
Workbook input được đặt quyền chỉ đọc trong môi trường tạo gói; test luôn xuất
kết quả vào thư mục tạm, không ghi lại fixture. Không phụ thuộc việc hệ điều hành
có thực thi quyền chỉ đọc giống nhau hay không.

Chạy từ thư mục ứng dụng:

```bash
python -m unittest tests.test_golden_v110 -v
```

Nếu thay đổi nghiệp vụ được phê duyệt, đọc lại nguồn và sửa kỳ vọng bằng tay,
ghi rõ lý do, rồi review diff. Không cập nhật expected từ output mới chỉ để test
pass. Khi có mẫu thật đã ẩn thông tin cần bảo mật và file import được Cảng chấp
nhận, bổ sung thành một bộ riêng với trạng thái xác nhận, không đổi nhãn bộ này.
