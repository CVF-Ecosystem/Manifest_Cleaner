# VINAFCO 1.1.0 — sửa F03 và đối soát dòng chưa đủ dữ liệu

## Phạm vi thay đổi

Giữ adapter riêng VINAFCO và hợp đồng xuất 16 cột hiện có. Không đổi mapping VTOS, operator, cách tính số lượng theo nhóm, quy tắc gross/tare, làm tròn hoặc nhãn `EMPTY` của đầu ra legacy.

### F03: tên cột và đơn vị được nhận cùng một lần

`GWKGS`, `GROSSWEIGHTKG`, `G.W. (KGS)` và các hậu tố đơn vị được hỗ trợ đều chuyển 25.000 kg thành 25 tấn. Một bộ phân tích header trả đồng thời tên trường và đơn vị hiệu lực; không còn nhận được cột nhưng làm mất hậu tố đơn vị rồi mặc định thành tấn.

`col_gw` vẫn hỗ trợ tên cột tùy chỉnh. Có thể cấu hình phần tên cơ sở, ví dụ `CÂN`, để nhận `CANKGS`; hoặc cấu hình đầy đủ `MY MASS (KGS)`. Nếu tên không có đơn vị, dùng `default_weight_unit` đã kiểm tra hợp lệ. Chữ T cuối một tên thông thường như `WEIGHT` không tự trở thành chú thích đơn vị tấn. Đơn vị ghi ngay trong giá trị ô vẫn được bộ đọc trọng lượng chung xử lý như trước.

### Header lặp phải có cùng cấu trúc và đơn vị

Header lặp cùng tập/vị trí cột và cùng đơn vị hiệu lực được chấp nhận; khác cách viết tương đương như `GWKGS` và `G.W. (KG)` không gây lỗi.

Nếu header lặp đổi vị trí hoặc tập cột, đổi đơn vị hoặc tạo cột trùng, adapter phát lỗi `VINAFCO_HEADER_CHANGED` và dừng đọc phần phía sau. File nhập Cảng bị chặn. Bản đối chiếu giữ header cũ/mới, vị trí dòng và nội dung phần chưa đọc trong `metadata.source_fragments`. Người dùng cần tách/chọn đúng một bảng thống nhất rồi xử lý lại. Bản này không tự ghép nhiều bảng khác cấu trúc.

### Không bỏ dòng có thông tin container nhưng thiếu mã

Một dòng có kích cỡ, seal, trọng lượng hoặc mô tả trong các cột tương ứng, nhưng thiếu số container, được giữ thành record chưa hoàn chỉnh và phát lỗi `VINAFCO_CONTAINER_MISSING`. Người dùng có thể bổ sung mã từ nguồn hoặc loại dòng có lý do. Bảng chỉ có những candidate thiếu mã vẫn được nhận diện để người dùng thấy lỗi, thay vì báo không thấy bảng.

Các dòng đã nhận diện rõ là party `(S)/(C)/(N)`, phần tiếp nối party, header hoặc tổng cộng không tự tạo container. Nhãn tổng cộng được kiểm tra theo ngữ cảnh; mô tả như `TOTAL QUALITY STEEL` không bị coi là footer chỉ vì có chữ `TOTAL`.

## Bằng chứng nguồn và chỉ số đối soát

`metadata.source_fragments` giữ vị trí sheet/dòng, nội dung và trạng thái của từng dòng không trống trong bảng đã chọn. `metadata.coverage` đếm các nhóm:

- `parsed_fragments`: dòng container đã nhận dạng; vẫn có thể còn lỗi trường dữ liệu.
- `unresolved_fragments`: candidate thiếu/sai mã hoặc phần chưa được đọc sau header thay đổi.
- `corroborating_fragments`: ngữ cảnh party/B/L đã dùng để bổ sung dữ liệu.
- `ignored_fragments`: header, tổng cộng và dòng không phải container có lý do đã ghi.

Tổng bốn nhóm bằng `source_fragments`. Đây là đối soát mức đọc nguồn, không phải tỷ lệ chính xác hay cam kết dữ liệu đã đạt nghiệm thu. Công thức Excel chưa có giá trị cache được lớp đọc/kiểm tra chung xử lý riêng; adapter này không tính công thức.

## Kiểm chứng

Chạy `python -m unittest tests.test_vinafco tests.test_vinafco_v110 -v`.

Bộ test mới bao gồm: header kg liền chữ và có dấu phân cách, alias cấu hình, numeric Excel giữ nguyên dù chọn decimal_comma, header lặp tương đương, đổi đơn vị, đổi thứ tự cột, cột trùng, candidate thiếu mã và sửa mã, bảng chỉ có candidate, party/footer không tạo record giả, mô tả chứa TOTAL, đối soát số dòng và cấu hình alias trùng trường.

Các mẫu đều là dữ liệu tổng hợp để kiểm chứng các lỗi đã tái hiện. Cần giữ bước nghiệm thu mẫu manifest thật và file nhập Cảng trên bản phân phối cuối.
