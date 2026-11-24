# Bàn giao kiểm tra local và đề xuất hoàn thiện — 1.1.1

Ngày: **22-11-2026**. Đây là hướng dẫn cho agent local tiếp nhận bản vá và kế hoạch nâng cấp có giới hạn phạm vi.

## 1. Mục tiêu cần giữ

Ứng dụng phục vụ người nhận manifest tại Cảng: **nhận một file của một hãng, làm sạch dữ liệu, xử lý các điểm cần đối chiếu và xuất đúng mẫu nhập hệ thống hiện có**.

Người dùng chọn **VOSCO / VIMC / VINAFCO**. Các khác biệt của VIMC từ nguồn Hải Phòng/Đà Nẵng là các họ mẫu trong cùng hãng. Tên tàu từng được dùng để nhớ tuyến, không phải điều kiện chọn parser. Đơn vị và F/E phải có căn cứ trong nội dung/quy tắc đã xác nhận.

**Đã làm trong 1.1.1:** sửa F10 ở CLI và thêm kiểm thử. **Các mục 4–8 bên dưới là đề xuất**, chưa được thực hiện trong mã. Agent có thể dùng chúng làm backlog khi người dùng chọn bước phát triển tiếp theo.

## 2. Kiểm tra bản vá tại Windows

Giải nén vào thư mục riêng, giữ gói và kết quả nghiệp vụ đang dùng. Từ thư mục ứng dụng:

```bat
py -3.12 scripts\check_release.py
SETUP.cmd
.venv\Scripts\python.exe scripts\check_release.py --runtime-only
.venv\Scripts\python.exe -m unittest tests.test_cli_v111 -v
RUN_TESTS.cmd
```

Kỳ vọng: checksum hợp lệ; môi trường đủ phụ thuộc; **11 ca mới đạt**, toàn bộ suite **202 ca đạt**. SETUP cần tải phụ thuộc nếu máy chưa có; có thể dùng wheelhouse như hướng dẫn bàn giao chung. Đừng chạy tạo demo đè lên `samples/` hoặc cập nhật checksum chỉ để làm kiểm tra pass.

### Tái hiện chính F10 qua dòng lệnh

Tạo đầu vào thử bằng helper có sẵn, toàn bộ trong thư mục mới `local_v111_check`:

```bat
.venv\Scripts\python.exe -c "from scripts.create_samples import create_vimc; create_vimc('local_v111_check/good.xlsx'); create_vimc('local_v111_check/bad.xlsx', consignee='')"
.venv\Scripts\python.exe -m manifest_cleaner.cli local_v111_check/good.xlsx --carrier VIMC --output local_v111_check/port.xlsx --review local_v111_check/port.review.json
```

Chụp SHA-256 của cặp đã xuất, sau đó cố xuất lại bằng nguồn còn lỗi:

```bat
.venv\Scripts\python.exe -c "from pathlib import Path; import hashlib,json; p=Path('local_v111_check'); (p/'before.json').write_text(json.dumps({n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('port.xlsx','port.review.json')}), encoding='utf-8')"
.venv\Scripts\python.exe -m manifest_cleaner.cli local_v111_check/bad.xlsx --carrier VIMC --output local_v111_check/port.xlsx --review local_v111_check/port.review.json --overwrite
```

Lệnh thứ hai **phải bị chặn** và báo giữ nguyên đích; mã thoát 1 là kết quả mong đợi của ca này. Kiểm tra cả hai hash:

```bat
.venv\Scripts\python.exe -c "from pathlib import Path; import hashlib,json; p=Path('local_v111_check'); old=json.loads((p/'before.json').read_text(encoding='utf-8')); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in old.items()); print('PASS: Excel va JSON cu deu giu nguyen')"
```

Lưu báo cáo lỗi riêng:

```bat
.venv\Scripts\python.exe -m manifest_cleaner.cli local_v111_check/bad.xlsx --carrier VIMC --review local_v111_check/bad_can_kiem_tra.json
```

Kỳ vọng: JSON mới được lưu và có thể mở lại phiên; Excel/JSON cũ không thay đổi; mã thoát 2 vì dữ liệu vẫn còn lỗi. Nếu chạy lại từ đầu, dùng một thư mục thử mới để không nhầm với kết quả cũ.

### Kiểm tra trải nghiệm thực tế

1. Chạy `START.cmd`; mở từng demo đúng hãng, xem nguồn/preview và xuất sang tên mới.
2. Mở bốn JSON demo từ `samples/` trong 1.1.1. Ba demo thường không có lỗi chặn; demo cần kiểm tra vẫn giữ các vấn đề chưa giải quyết.
3. Với demo cần kiểm tra, sửa riêng seal rồi xác nhận lỗi F/E/trọng lượng chưa tự mất. Lưu/mở phiên và kiểm dữ liệu sửa còn nguyên.
4. Thử file đích đang được Excel mở khóa, đường dẫn có dấu/khoảng trắng và mức scale Windows đang dùng.
5. Build bằng `BUILD_EXE.cmd`, chuyển cả thư mục `dist\ManifestCleaner`; thử trên môi trường đích theo checklist Windows.
6. Đối chiếu manifest thực đang có với output từ app cũ/file đã được Cảng chấp nhận. Ghi khác biệt theo container + B/L + trường; chưa có căn cứ thì ghi chưa xác nhận, không tự sửa expected cho khớp kết quả mới.

Ghi báo cáo ngắn gồm Windows/Python, kết quả test, nguồn thử, bước tái hiện, giá trị kỳ vọng/thực tế và ảnh lỗi nếu cần. Chỉ dùng dữ liệu tổng hợp/đã ẩn danh khi chia sẻ ra ngoài máy nghiệp vụ.

## 3. Nền hiện tại đã có

Các chức năng sau đã có từ 1.1.0 và được giữ lại: nhận chữ ký XLS/XLSX/XLSM; giữ số 0 đầu của mã/seal ở các định dạng hỗ trợ; chuẩn hóa nhãn; tách nhiều dòng trong ô; xử lý party/BL theo nhóm; quy đổi kg/tấn theo quy tắc hãng; giữ ứng viên lỗi để sửa; tra nguồn; xác nhận từng trường; preview đúng 16 cột; lưu/mở phiên review v2; xuất Excel kèm JSON.

Không coi những chức năng này là đề xuất mới. Khả năng đọc linh hoạt còn khác nhau giữa các hãng:

| Căn cứ mã hiện tại | Khoảng trống cần giải quyết |
|---|---|
| `carriers/vosco/adapter.py`: các cột A/B/F/K/O/S | Vị trí dòng đã linh hoạt hơn, nhưng đổi vị trí cột vẫn cần cải tiến. |
| `carriers/vimc/adapter.py`: tìm header trong 20 dòng đầu; BL chủ yếu ở cột thứ ba/nhãn đầu dòng | File thêm nhiều dòng mở đầu hoặc đổi vị trí cột có thể không được hiểu như mẫu cũ. |
| `carriers/vinafco/adapter.py`: alias cột/header, header lặp | Đã dò linh hoạt; header đổi cấu trúc/đơn vị được phát hiện và dừng, chưa tự chia các vùng thành schema riêng. |
| `common.py`: đọc giá trị ô thành DataFrame | Chưa cung cấp mô hình vùng merge chung. Một số BL merge đọc được nhờ ngữ cảnh, chưa bao phủ mọi kiểu merge. |
| `source_fragments` của adapter | Chỉ là các đoạn đã được parser ghi nhận; chưa phải lượt rà độc lập mọi ứng viên trong vùng nguồn. |

## 4. Cách làm script thông minh và linh hoạt hơn

**Nguyên tắc đề xuất: linh hoạt với cách trình bày, quyết định dữ liệu theo bằng chứng.** Giữ nguyên workbook nguồn, chuẩn hóa trên bản làm việc; mỗi giá trị xuất phải truy được về nguồn và quy tắc.

### A. Nhận diện vùng bảng và cột theo nội dung

Dò tổ hợp header, vài dòng dữ liệu và cấu trúc nhóm BL trong phạm vi hợp lý; hỗ trợ header gồm nhiều hàng Excel. Chuẩn hóa alias, khoảng trắng, xuống dòng của nhãn. Chỉ dùng vị trí cột cũ như một mẫu đã biết khi cấu trúc còn phù hợp.

Khi có hai cột trọng lượng hoặc hai cách ghép hợp lý, trình bày tên cột, vài giá trị mẫu và cách hiểu để người dùng chọn một lần cho đúng vùng. Không buộc sửa từng container khi nguyên nhân là ánh xạ toàn bảng.

### B. Hiểu merge và kế thừa trong đúng nhóm

Giữ địa chỉ ô gốc và phạm vi merge. Cho B/L/chủ hàng kế thừa trong đúng vùng merge hoặc block đã nhận diện. Dừng kế thừa khi sang nhóm mới.

Container, seal và trọng lượng không được điền xuống cả cột chỉ vì ô dưới trống. Một trọng lượng chung cho nhiều container có thể là tổng; không tự lặp lại hoặc chia đều nếu nguồn/quy tắc chưa xác nhận.

### C. Chọn mẫu trong hãng và theo dõi đơn vị rõ ràng

Bắt đầu bằng các preset nhỏ: **hãng → mẫu nguồn → phiên bản quy tắc**. Có thể đặt nhãn `VIMC – mẫu nguồn Hải Phòng` và `VIMC – mẫu nguồn Đà Nẵng` sau khi xác nhận các họ mẫu. Nhận diện thực tế dựa vào header, cách viết dòng, vị trí và đơn vị; cảng nguồn chỉ hỗ trợ gợi ý. Một cảng có thể có nhiều phiên bản mẫu.

Phần lớn file quen thuộc nên tự chọn đúng mẫu; chỉ hỏi khi nhiều mẫu cùng phù hợp. Lựa chọn đã xác nhận có thể lưu cục bộ và tái dùng nếu dấu hiệu cấu trúc vẫn khớp.

Ghi bằng chứng đơn vị từ **ô dữ liệu → header/vùng → mẫu đã xác nhận**. Có xung đột thì nêu rõ. Phân biệt đơn vị kg/tấn với ý nghĩa hàng/vỏ/tổng trọng lượng. Không đoán đơn vị chỉ từ số lớn/nhỏ hoặc tên cảng.

### D. Xử lý từng vùng có header riêng

Với một manifest có header lặp thay đổi cột/đơn vị, nâng từ hành vi dừng hiện tại thành các block có mapping và đơn vị riêng khi bằng chứng đủ. Block chưa xác định được phải xuất hiện trong danh sách cần xem. Quan hệ BL/party không được tự mang qua block khác nếu thiếu căn cứ.

### E. Rà nguồn độc lập để phát hiện dòng chưa được ghép

Sau parser chính, kiểm tra vùng manifest đã chọn để tìm ứng viên container chưa liên kết với record hoặc quyết định bỏ qua có lý do. Giữ tọa độ để người dùng xem; không coi mọi chuỗi số là container.

Ví dụ: VOSCO đã nhận được các container ở K nhưng còn một dòng lệch sang L. Lượt rà phải chỉ ra dòng lệch, thay vì cho rằng đã có kết quả nên mọi dữ liệu đều được đọc.

## 5. Các nâng cấp giao diện có giá trị

| Ưu tiên | Đề xuất | Điều người dùng nhận được |
|---|---|---|
| Cao | Bảng “Ứng dụng hiểu file này như sau” | Hãng, sheet/vùng, mẫu, ánh xạ cột, đơn vị và chỗ chưa rõ; sửa cách đọc trước khi sửa từng dòng. |
| Cao | Đối soát trước xuất | Số bản ghi, container duy nhất, B/L, dòng giữ/loại, ứng viên chưa ghép; so tổng nguồn khi có bằng chứng. |
| Cao | Nhóm vấn đề theo nguyên nhân và nút “Mục tiếp theo” | Xử lý tập trung thiếu chủ hàng, thiếu seal, đơn vị mơ hồ…; lọc theo B/L/trường. |
| Cao | Giải thích từng trường bằng tiếng Việt | Ví dụ: “25000 KGS tại G12 → 25 tấn; đơn vị từ ô nguồn”; hiển thị quy tắc mapping kích cỡ ngay cạnh giá trị xuất. |
| Sau đó | Sửa nhiều dòng trong phạm vi đã chọn | Xem trước các dòng bị ảnh hưởng, chỉ đổi trường đã chọn; lịch sử từng dòng và hoàn tác, không tự xác nhận lỗi khác. |
| Sau đó | Tự lưu nháp và hoàn tác | Khôi phục công việc khi đóng bất ngờ; kiểm đúng nguồn bằng hash, không ghi đè workbook gốc. |

Đối soát cần phân biệt **dòng container–B/L** với **container duy nhất**. Nếu cùng container có hai quan hệ B/L hợp lệ, giữ cả hai; không xóa chỉ để số đếm bằng nhau. Chỉ so tổng trọng lượng khi đơn vị, ý nghĩa và phạm vi cộng giống nhau; không cộng lẫn cargo/gross rồi báo khớp.

Trên giao diện nên dùng trạng thái “Đủ điều kiện xuất / Cần đối chiếu / Cần bổ sung” thay cho một tỷ lệ đúng chưa được đo. Nếu hợp đồng nhập Cảng vẫn cần cột `Độ chính xác (%)`, giữ cột legacy và giải thích đúng ý nghĩa.

## 6. Bộ tình huống nghiệm thu cho nâng cấp đọc Excel

Đây là **ca cần bổ sung khi triển khai các đề xuất**, không phải các ca được tuyên bố đã đạt trong 1.1.1.

| Tình huống | Kết quả kỳ vọng |
|---|---|
| Chèn 25 dòng tiêu đề/trống trước cùng dữ liệu | Không đổi container, BL, F/E, trọng lượng và mẫu xuất. |
| Đổi thứ tự cột; header xuống dòng/ghép 2–3 hàng | Mapping đúng nếu bằng chứng đủ; cột trùng phải yêu cầu chọn. |
| BL merge trên ba dòng container | Cả ba nhận đúng BL; nhóm kế tiếp không bị kế thừa nhầm. |
| Một trọng lượng merge cho nhiều container | Giữ mơ hồ để kiểm tra; không nhân hoặc chia đều tự động. |
| `25000 KGS`; header KG + số native 25000; `25 TONS` | Cùng 25 tấn trong phạm vi khai báo tương ứng. |
| Ô ghi KG nhưng header ghi TONS | Hiển thị xung đột và căn cứ; không che mất thông tin nguồn. |
| Mã container có ký tự O/0 hoặc I/1 khó phân biệt | Không sửa nội dung mã bằng suy đoán; đề xuất và yêu cầu đối chiếu. |
| Một record hợp lệ ở K và ứng viên lệch sang L | Ứng viên lệch phải được đưa ra kiểm tra. |
| Hai block lần lượt 25 tấn và 25000 kg | Quy đổi từng block; không thiếu/lặp record hoặc rò BL. |
| Tổng ghi trên manifest khác tổng thu được | Báo lệch cùng phạm vi tính; không bịa các dòng còn thiếu. |
| Sửa chủ hàng cho 10 dòng được chọn | Chỉ chủ hàng thay đổi; lỗi F/E/trọng lượng khác vẫn còn. |
| Một container liên quan hai B/L | Giữ quan hệ; số dòng và số container duy nhất được báo riêng. |
| Đổi tên file hoặc tên tàu | Không làm thay đổi lựa chọn grammar nếu cấu trúc nguồn không đổi. |

Giữ golden viết tay độc lập exporter. Bổ sung biến thể trình bày của cùng một nội dung để kiểm tra tính nhất quán; khi có cặp manifest thật/output đã được Cảng chấp nhận, lưu riêng với trạng thái xác nhận. Không cần chờ đủ mọi mẫu thật mới bắt đầu cải tiến lớp đọc cấu trúc.

## 7. Thứ tự thực hiện đề xuất

1. **Hiện tại:** nghiệm thu bản vá 1.1.1 trên local theo mục 2.
2. **Đợt kế tiếp:** nhận diện bảng/cột + merge có phạm vi + bằng chứng đơn vị; lưu preset mẫu tối thiểu. Ưu tiên các biến thể đang làm người dùng phải sửa tay.
3. **Sau đó:** rà ứng viên chưa ghép, bảng đối soát và điều hướng/giải thích vấn đề; xử lý nhiều block có schema riêng.
4. **Hoàn thiện thao tác:** sửa nhóm có preview/hoàn tác và tự lưu nháp.

Mỗi đợt phải giữ toàn bộ mẫu 16 cột, mapping và hành vi cũ đã xác nhận. Khi thêm một quy tắc mới, ghi điều kiện áp dụng, ví dụ vào/ra và ca kiểm chứng. Chưa cần một bộ máy plugin tổng quát hoặc trình tự thiết kế parser cho người dùng.

## 8. Phạm vi sản phẩm

Chất lượng được đánh giá bằng khả năng đọc đúng nhiều mẫu, phát hiện chỗ thiếu/mơ hồ, giảm thao tác sửa tay và tạo file nhập đúng hợp đồng. Số liệu đối soát chỉ phục vụ manifest đang xử lý. Định hướng này giữ ứng dụng là công cụ làm sạch/chuyển đổi dữ liệu, đúng vai trò người dùng đã xác định.
