# Manifest Cleaner Unified 1.1.1

Ngày phát hành: **22-11-2026** — Asia/Ho_Chi_Minh. Bản nền: **1.1.0** do người dùng cung cấp.

## Bản vá đã thực hiện

**F10 / P2 — CLI làm lệch cặp Excel–JSON sau một lần xuất bị chặn.**

Trong 1.1.0, nếu đã có `port.xlsx` và `port.review.json`, một lần chạy khác với dữ liệu còn lỗi, cùng `--output`, `--review` và `--overwrite` có thể ghi đè JSON trước khi exporter từ chối tạo Excel. Kết quả là Excel cũ và JSON mới thuộc hai phiên khác nhau.

Trong 1.1.1, CLI kiểm tra lỗi dữ liệu và các đích xuất **trước khi ghi**. Khi không thể xuất Excel, cờ ghi đè không cho phép thay riêng JSON của bộ kết quả.

| Tình huống | Hành vi 1.1.1 |
|---|---|
| Còn lỗi chặn; Excel hoặc JSON đích đã tồn tại | Dừng; giữ nguyên các file đích, kể cả khi có `--overwrite`. |
| Excel cũ, JSON được chỉ định ở đường dẫn mới | Dừng trước khi tạo JSON hoặc thư mục mới. |
| JSON cũ còn nhưng Excel đã bị di chuyển/xóa | Giữ nguyên JSON cũ. |
| Hai đích đều mới; có `--review` tường minh | Lưu JSON lỗi để tiếp tục đối chiếu; không tạo Excel nhập Cảng. |
| Hai đích đều mới; không chỉ định `--review` | Không tạo file đầu ra; hướng dẫn lưu đối chiếu riêng. |
| Chỉ yêu cầu `--review`, không có `--output` | Tiếp tục lưu phiên kể cả khi còn lỗi. Muốn ghi đè báo cáo đã có vẫn phải chỉ định `--overwrite`. |
| Dữ liệu hợp lệ và có `--overwrite` | Xuất bộ Excel–JSON qua cơ chế staging/rollback đã có. |

Thông báo lỗi nêu rõ các file cũ được giữ và hướng dẫn dùng tên mới cho báo cáo lỗi riêng:

```bash
python -m manifest_cleaner.cli input.xlsx --carrier VIMC --review input_can_kiem_tra.json
```

Lệnh kiểm tra có thể trả mã **2** khi báo cáo đã lưu nhưng dữ liệu vẫn còn lỗi. Lệnh yêu cầu xuất bị chặn trả mã **1**. Không tự đổi tên đích hoặc bỏ qua lỗi để xuất.

## Phạm vi thay đổi

- Logic chạy chỉ thay nhánh xuất thất bại trong `manifest_cleaner/cli.py`; phiên bản ứng dụng tăng lên 1.1.1.
- Bổ sung `tests/test_cli_v111.py` với **11 ca**. Các ca dùng nguồn Excel và file xuất thật trong thư mục tạm; kiểm bytes, hash, session ID và giá trị Excel khi cần.
- Giữ bộ 191 kiểm thử cũ, ba adapter, mapping hãng, quy tắc F/E/BL/trọng lượng và mẫu 16 cột.
- Giữ nguyên golden và demo 1.1.0 để đối chiếu; review v2 cũ tiếp tục mở được bằng bản mới.
- Cập nhật hướng dẫn, thông tin nguồn kế thừa, báo cáo kiểm chứng và checksum.

Kết quả chạy đầy đủ nằm trong [VALIDATION_REPORT.md](VALIDATION_REPORT.md) và [TEST_OUTPUT.txt](TEST_OUTPUT.txt). Ca hồi quy chính đã được chạy với CLI 1.1.0 và phát hiện JSON bị đổi; cùng ca đó đạt sau bản vá.

## Đề xuất tiếp theo được bàn giao riêng

[LOCAL_AGENT_V111.md](LOCAL_AGENT_V111.md) ghi các khoảng trống về bố cục Excel, mẫu trong từng hãng, đối soát nguồn và trải nghiệm sửa lỗi. **Các mục mang nhãn đề xuất chưa được triển khai trong 1.1.1.** Bản vá này tập trung xử lý F10 để local có một nền rõ ràng kiểm tra tiếp.

Phạm vi sản phẩm tiếp tục là **tiếp nhận → làm sạch → đối chiếu → xuất manifest đúng mẫu**. Một phiên xử lý một manifest của một hãng; hãng tàu là lựa chọn chính.

## Kiểm chứng còn cần tại local

Gói chứa mã nguồn chạy bằng Python và công thức build. Chưa build/chạy EXE Windows, kiểm tra giao diện native hoặc import thật vào hệ thống Cảng trong môi trường bàn giao này. Dùng [LOCAL_AGENT_V111.md](LOCAL_AGENT_V111.md) và [WINDOWS_RELEASE_CHECKLIST.md](WINDOWS_RELEASE_CHECKLIST.md) để kiểm tra ở máy đích.
