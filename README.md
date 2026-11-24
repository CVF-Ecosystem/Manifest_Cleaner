# Manifest Cleaner Unified 1.2.0

Ứng dụng **local**, xử lý **một manifest của một hãng tàu mỗi phiên**, hỗ trợ đối chiếu dữ liệu và xuất Excel theo mẫu nhập hệ thống quản lý container của Cảng.

**Bắt đầu:** giải nén toàn bộ thư mục, dùng Python 3.12 64-bit và chạy `START.cmd`. Mở [START_HERE.html](START_HERE.html) để xem hướng dẫn tiếng Việt dùng được offline.

**Thay đổi 1.2.0:** VINAFCO có thể chọn sheet ngay khi phát hiện nhiều bảng và đối soát phần chi tiết với bảng tổng hợp. VOSCO báo ứng viên container lệch cột trong vùng hỗ trợ. CLI hỗ trợ chuyển hướng đầu ra Windows có mã hóa cũ. [Ghi chú bản 1.2.0](docs/RELEASE_NOTES_V1_2.md) mô tả hành vi và phạm vi kiểm chứng.

**Bản nền 1.1.1:** [Hướng dẫn 1.1.1](docs/V1_1_1_GUIDE.html) và [ghi chú bản vá](docs/RELEASE_NOTES_V1_1_1.md) mô tả việc bảo vệ cặp Excel/JSON khi xuất thất bại.

**Lịch sử 1.1.0:** [Tổng hợp nâng cấp](docs/RELEASE_NOTES_V1_1.html) gồm ma trận F01–F09 và kết quả kiểm thử tại lần phát hành đó.

Gói này gồm **mã nguồn, launcher, dữ liệu thử và bộ hướng dẫn đóng gói**. Chưa kèm EXE Windows đã được build và nghiệm thu. Phạm vi kiểm chứng cuối cùng được ghi tại [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md).

## Phạm vi và hợp đồng dữ liệu

- Chọn **VOSCO / VIMC / VINAFCO** theo hãng tàu. Tên tàu không quyết định parser.
- VIMC nhận dạng bố cục từ dữ liệu, gồm trọng lượng trước mô tả theo tấn và trọng lượng sau mô tả theo kg. Dòng có nhiều cách đọc phải được đối chiếu.
- VOSCO/VINAFCO giữ tên và thứ tự **16 cột** của mẫu xuất hiện có; VIMC giữ mẫu 16 cột riêng. Hãng đang xử lý quyết định mẫu xuất.
- Mapping kích cỡ, operator và loại hàng tiếp tục theo từng hãng. Các lỗi đã tái hiện được sửa mà không đồng nhất tùy tiện quy tắc giữa các hãng.
- Đường dẫn/dấu kiểm tra file nguồn, vị trí dữ liệu, các bằng chứng được adapter thu thập và lịch sử chỉnh sửa được giữ trong phiên đối chiếu. Dòng còn thiếu thông tin được giữ để sửa hoặc loại có lý do trong các biến thể đã nhận diện.
- Luồng xử lý không cần tài khoản AI/API. Đọc manifest, sửa và xuất dữ liệu diễn ra trên máy sử dụng.

## Chạy trên Windows

1. Giải nén toàn bộ thư mục vào nơi tài khoản có quyền ghi, ví dụ Documents. Không chạy ngay trong cửa sổ xem ZIP.
2. Cài Python **3.12 64-bit**; phạm vi Python khai báo của gói là 3.10–3.13.
3. Chạy `START.cmd`. Lần chuẩn bị đầu tiên tạo `.venv` riêng và cài các thư viện trong `requirements.txt`, cần kết nối để tải phụ thuộc.
4. Chọn hãng, mở một file `.xls`, `.xlsx` hoặc `.xlsm`, rồi làm theo quy trình đối chiếu bên dưới.

Nếu đã có môi trường Python phù hợp:

```bash
python -m pip install -r requirements.txt
python app.py
```

Sau khi chuẩn bị đủ phụ thuộc, thao tác manifest không cần tải dữ liệu lên dịch vụ bên ngoài. Máy hạn chế mạng có thể được agent local chuẩn bị bộ thư viện offline.

### Đóng gói EXE

`BUILD_EXE.cmd` chạy kiểm thử rồi dùng công thức đóng gói Windows. Đường dẫn dự kiến: `dist/ManifestCleaner/ManifestCleaner.exe`. Khi bàn giao bản đã build, chuyển **cả thư mục** `dist/ManifestCleaner`, không lấy riêng file EXE.

Bộ script/spec là đầu vào cho bước build ở máy Windows; việc có sẵn chúng không đồng nghĩa EXE đã được kiểm tra. Các giới hạn Windows và nghiệm thu Cảng được nêu ở cuối tài liệu.

## Quy trình sử dụng 1.1.1

### 1. Mở nguồn và xem cấu hình hiệu lực

Chọn hãng rồi bấm **Mở manifest**. Phía trên bảng hiển thị quy ước số, ý nghĩa trọng lượng, sheet và bộ quy tắc đang dùng. Bảng tổng hợp phân biệt số container duy nhất, số dòng đang giữ, F/E, lỗi theo dòng, lỗi toàn file và dòng đã loại.

Nếu file có nhiều bảng hoặc cần chỉ định sheet, dùng **Cấu hình đọc** để chọn đúng sheet rồi **Xử lý lại**. Khi đổi hãng hoặc cấu hình, kết quả cũ không được xuất theo lựa chọn mới. Nếu đã sửa dữ liệu, lưu đối chiếu trước khi chủ động xử lý lại.

### 2. Xử lý đúng lỗi, đúng container

Mở tab **Cần kiểm tra**, nhấp đúp một lỗi để sửa container liên quan. Nút **Xem / sửa dòng**, **Đã đối chiếu**, **Loại / khôi phục dòng** luôn dùng dòng được chọn trong tab đang mở. Lỗi toàn file không áp dụng các thao tác theo dòng.

Trong cửa sổ sửa:

- Dấu `*` và nhãn nổi bật chỉ trường liên quan lỗi/cảnh báo.
- **Trường đã thay đổi** được ghi nhận cùng giá trị trước/sau.
- **Trường giữ nguyên** chỉ được xác nhận khi tích ô **Đã đối chiếu trường này** của chính trường đó.
- Mở rồi lưu form không tự xác nhận tất cả trường. Sửa seal không làm mất lỗi F/E hoặc trọng lượng chưa được giải quyết.
- Ghi **lý do chỉnh sửa / căn cứ xác nhận** trước khi lưu.

Trọng lượng sửa trên giao diện luôn là **tấn**, dùng dấu phẩy hoặc dấu chấm thập phân. F là có hàng; E là rỗng.

Với dòng VIMC có hai cách đọc, đối chiếu nguồn rồi chọn phương án và bấm **Điền và xác nhận 2 trường**. Ứng dụng điền trọng lượng/mô tả tương ứng; người dùng vẫn phải ghi căn cứ và lưu. Không có phương án được tự chọn sẵn.

**Đã đối chiếu** ở thanh công cụ dùng để ghi căn cứ cho cảnh báo; không tự xóa lỗi dữ liệu. Dòng lặp hoặc dòng không thuộc manifest có thể **Loại** với lý do. Dialog nêu rõ số container/B/L; dòng vẫn được giữ trong phiên và có thể khôi phục.

### 3. So nguồn với giá trị sẽ xuất

Tab **Nguồn và giá trị sẽ xuất** trong cửa sổ sửa cho xem nguyên văn nguồn, bằng chứng theo trường và giá trị ghi vào mẫu 16 cột. Xem trước dùng cùng quy tắc chuyển đổi với exporter, bao gồm mapping, cách làm tròn và nhãn `EMPTY`. Xem trước không bỏ qua lỗi chặn xuất và không tự lưu các ô đang sửa.

Phần JSON kỹ thuật được thu gọn. Nút **Tra nguồn** ở cửa sổ chính cho xem các đoạn nguồn mà adapter đã ghi nhận, vị trí và lý do nhận diện/bỏ qua/chờ đối chiếu. Những nhãn này là **trạng thái tại lần đọc nguồn**, không phải số lỗi hiện tại sau chỉnh sửa. Một đoạn đã nhận diện vẫn có thể còn lỗi trường dữ liệu. Số đoạn nguồn không phải số container hay tỷ lệ chính xác.

Ba adapter VOSCO/VIMC/VINAFCO đều ghi nhận đoạn nguồn theo phạm vi bố cục của mình. Đây là các đoạn parser đã thu thập, không phải xác nhận đã kiểm kê toàn bộ mọi ô trong workbook. Nếu một phiên không có danh sách này, giao diện thông báo rõ; nguồn từng container vẫn xem được trong form.

### 4. Xuất và giữ phiên làm việc

Bấm **Xuất file nhập Cảng** khi không còn lỗi chặn. Cảnh báo còn lại cần được đối chiếu và xác nhận xuất.

Mặc định tùy chọn **Xuất kèm đối chiếu JSON để mở lại phiên** được bật:

```text
manifest_VIMC_CLEAN.xlsx
manifest_VIMC_CLEAN.review.json
```

- Excel là file nhập hệ thống Cảng.
- JSON lưu phiên đối chiếu, nguồn, cấu hình và lịch sử; không dùng JSON để nhập Cảng.
- Nếu Excel hoặc JSON cùng tên đã tồn tại, ứng dụng yêu cầu xác nhận ghi đè cả bộ.
- Giữ thêm manifest gốc để có thể mở lại phiên. Bản JSON không thay thế workbook gốc.
- Có thể dùng **Lưu đối chiếu** trước khi xử lý hết lỗi để tiếp tục công việc sau.

Nếu tắt xuất kèm JSON, các chỉnh sửa chưa lưu đối chiếu vẫn có cảnh báo khi đóng/mở phiên khác. JSON từ lần xuất trước, nếu có, không được cập nhật khi chỉ xuất Excel; nên dùng tên mới để tránh nhầm cặp file.

Phím tắt: **Ctrl+O** mở manifest, **Ctrl+S** xuất, **F1** hướng dẫn.

## Lưu và mở lại phiên: review v2

Bấm **Mở phiên đã lưu** rồi chọn JSON do bản 1.1 tạo. Ứng dụng kiểm tra cấu trúc phiên, dấu kiểm tra nội dung và **SHA-256 của manifest nguồn** trước khi khôi phục.

- Các sửa đổi, xác nhận, dòng đã loại và cấu hình đã lưu được khôi phục; không chạy lại parser để thay các sửa đổi.
- Nếu manifest gốc đã di chuyển, chọn lại đúng file có cùng nội dung.
- Nếu nội dung nguồn đã đổi, dùng đúng bản nguồn cũ để tiếp tục phiên cũ, hoặc mở bản đã đổi thành phiên mới.
- Mở phiên lỗi không thay thế phiên hiện tại.
- Quy ước đang chờ áp dụng ở giao diện không được dùng thay cấu hình đã tạo phiên. Sau resume, giao diện hiển thị cấu hình của phiên đã lưu.

**JSON của bản 1.0 là báo cáo tham khảo, chưa phải phiên resumable.** Giữ bản đó để đối chiếu và mở manifest gốc bằng 1.1 để tạo phiên mới; không chỉ đổi nhãn version trong JSON cũ.

Các file REVIEW trong `samples/` của bản 1.1 dùng đường dẫn nguồn tương đối với thư mục JSON để có thể mở sau khi giải nén. Giữ INPUT cạnh REVIEW. Phiên làm việc thông thường lưu đường dẫn nguồn tuyệt đối; khi nguồn được chuyển chỗ, dùng chức năng chọn lại nguồn ở GUI hoặc `--source` ở CLI.

## Cấu hình đọc

Giao diện tự tìm `settings.json` cạnh ứng dụng; nếu chưa có file này, dùng mặc định. Có thể bắt đầu từ `settings.example.json` hoặc dùng **Cấu hình đọc**. Cấu hình sâu nằm trong tài liệu từng hãng và [docs/DEVELOPER_HANDOFF.md](docs/DEVELOPER_HANDOFF.md).

### Quy ước số và đơn vị

| Tùy chọn | Ý nghĩa |
|---|---|
| `legacy` | Giữ quy ước nguồn cũ: dấu phẩy theo ngữ cảnh kg/tấn; khi có cả hai dấu, dấu cuối là thập phân trong cách viết hợp lệ. |
| `decimal_comma` | Dấu phẩy thập phân, ví dụ `25.000,50`. |
| `decimal_dot` | Dấu chấm thập phân, ví dụ `25,000.50`. |
| `default_weight_unit` | Đơn vị mặc định khi nguồn không ghi rõ, với hãng có hỗ trợ tùy chọn này. |
| `selected_sheet` | Tên chính xác của sheet cần xử lý. Tên không tồn tại báo lỗi. |

Số đã lưu dạng numeric trong Excel giữ nguyên giá trị; không được diễn giải lại theo locale. Đơn vị ghi rõ trong ô/header được bộ đọc xử lý theo quy tắc của hãng; nội bộ dùng tấn, chưa làm tròn sớm. Không thay quy ước chỉ để làm mất cảnh báo.

### Phân biệt `cargo`, `gross`, `unknown`

| Giá trị | Ý nghĩa và cách dùng |
|---|---|
| `cargo` | Trọng lượng hàng. Với VOSCO, hàng dương không bị so với trọng lượng vỏ để suy ra rỗng. |
| `gross` | Tổng trọng lượng theo ngữ nghĩa cột nguồn; áp dụng quy tắc gross/tare của hãng có dùng suy luận này. |
| `unknown` | Chưa xác nhận nghĩa cột. VOSCO giữ hành vi legacy và cảnh báo khi phải suy luận F/E từ trọng lượng. |

Mặc định VOSCO/VIMC là `unknown`; VINAFCO là `gross`. VIMC đọc F/E từ ngữ cảnh dòng/nhóm; không chuyển sang thuật toán tare của hãng khác chỉ vì cùng tên cấu hình. Chỉ đổi `weight_kind` sau khi đã xác nhận ý nghĩa dữ liệu với nguồn nghiệp vụ.

Với VOSCO: khai báo EMPTY nhưng cấu hình `cargo` có khối lượng hàng dương tạo lỗi cần xác nhận F/E và khối lượng. Khối lượng hàng bằng 0, nếu không có khai báo EMPTY, không tự trở thành container rỗng.

## Các tình huống từ audit đã được xử lý trong 1.1

Bảng này tóm tắt hành vi của bản sửa cho các ca đã tái hiện; không phải cam kết nhận diện mọi biến thể manifest.

| Finding | Thay đổi chính |
|---|---|
| F01 — Form tự xác nhận toàn bộ trường | Chỉ gửi thay đổi; xác nhận trường giữ nguyên phải được chọn riêng. |
| F02 — Mã container VIMC hỏng bị bỏ qua | Giữ các ứng viên có cấu trúc đã hỗ trợ như mã có khoảng trắng/gạch nối hoặc thiếu chữ; yêu cầu sửa/xác nhận phù hợp, không ngầm coi mã hỏng là đúng. |
| F03 — VINAFCO đọc tên cột nhưng mất đơn vị | Nhận tên cột và đơn vị cùng một lần; header lặp đổi cột/đơn vị làm dừng và chặn xuất để đối chiếu. |
| F04 — VOSCO ghép lệch mô tả do dòng PORT | Dùng cùng tập mô tả đã phân loại cho bước đếm và ghép, giữ bằng chứng dòng nguồn. |
| F05 — Ý nghĩa trọng lượng VOSCO không tham gia suy luận | Phân biệt cargo/gross/unknown trong logic F/E và nêu mâu thuẫn cần xử lý. |
| F06 — Nút thao tác dùng selection của tab khác | Thao tác theo tab hiện hành; lỗi toàn file vô hiệu hóa nút theo dòng. |
| F07 — Công thức chưa có kết quả bị đọc như trống | Với XLSX/XLSM, công thức thiếu kết quả lưu hoặc có lỗi trong sheet được dùng tạo lỗi nguồn chặn xuất. Ứng dụng không tự tính công thức. |
| F08 — CLI nhận đường dẫn cấu hình không tồn tại | Đã chỉ định `--settings` thì file thiếu/sai phải báo lỗi; không lặng lẽ đổi sang mặc định. |
| F09 — Party VIMC ở dòng tiếp theo bị đọc thiếu | Đọc tiếp tên/địa chỉ trong cùng B/L, giữ tọa độ nguồn và dừng ở ranh giới phù hợp. |

Nếu gặp lỗi công thức XLSX/XLSM, mở nguồn bằng Excel để tính lại và lưu, hoặc tạo bản chỉ chứa giá trị, rồi xử lý lại. Cơ chế kiểm tra cache này chưa bao phủ XLS nhị phân cũ; chuyển mẫu có công thức sang XLSX hoặc bản giá trị khi cần đối chiếu công thức.

Ngoài các ca trên, VINAFCO giữ dòng có thuộc tính container nhưng thiếu mã để sửa/loại có lý do. Giới hạn chi tiết nằm tại [docs/CARRIER_FIXES_V110.md](docs/CARRIER_FIXES_V110.md), [docs/VINAFCO_FIXES_V110.md](docs/VINAFCO_FIXES_V110.md) và [docs/GUI_V110.md](docs/GUI_V110.md).

## Những quy tắc nghiệp vụ tiếp tục được giữ

| Hãng | Quy tắc tương thích |
|---|---|
| VOSCO | Operator `VOC/SVC`, bố cục A/B/F/K/O/S, các chiến lược ghép mô tả, mapping VTOS/loại hàng. |
| VIMC | Operator `VMC/SVM`, nhóm B/L, kg/tấn theo kiểu dòng, tank xuất `GENERAL`, hai cột kích cỡ xuất nhãn VTOS của mẫu cũ. |
| VINAFCO | Operator `VFC/SVF`, marker `(S)/(C)/(N)`, nhãn cột và mapping VTOS/loại hàng, quy tắc số lượng theo nhóm. |

Hai cột seal và cột ghi chú được giữ. VIMC/VINAFCO làm tròn trọng lượng ở bước xuất theo hành vi pandas của mẫu cũ; VOSCO giữ giá trị số sau quy đổi. VIMC/VINAFCO xuất nhãn hàng `EMPTY` khi E; mô tả nguồn vẫn giữ để đối chiếu. VOSCO giữ bước tinh chỉnh mô tả riêng.

Cột **Độ chính xác (%)** được giữ để tương thích. Đây là **điểm theo quy tắc**, không phải accuracy hay xác suất đã đo trên dữ liệu vận hành.

## Dùng dòng lệnh

Các lệnh sau chạy bằng Python đã cài phụ thuộc. Trên Windows, có thể thay `python` bằng `.venv\Scripts\python.exe` trong thư mục ứng dụng.

Kiểm tra nguồn và lưu phiên đối chiếu, kể cả khi còn lỗi:

```bash
python -m manifest_cleaner.cli input.xlsx --carrier VIMC --review review.json
```

Xuất Excel và JSON cùng tên mặc định:

```bash
python -m manifest_cleaner.cli input.xlsx --carrier VIMC --output output.xlsx
```

Dùng cấu hình/sheet cụ thể hoặc tên JSON riêng:

```bash
python -m manifest_cleaner.cli input.xlsx --carrier VINAFCO --settings settings.json --sheet Manifest --output output.xlsx --review review.json
```

Mở lại phiên, không truyền lại input/hãng/cấu hình:

```bash
python -m manifest_cleaner.cli --resume output.review.json --output output_2.xlsx
```

Manifest gốc đã di chuyển nhưng nội dung không đổi:

```bash
python -m manifest_cleaner.cli --resume output.review.json --source D:/Du_lieu/manifest_goc.xlsx --output output_2.xlsx
```

Chỉ xuất Excel hoặc chủ động cho phép ghi đè:

```bash
python -m manifest_cleaner.cli input.xlsx --carrier VOSCO --output output.xlsx --no-review
python -m manifest_cleaner.cli --resume output.review.json --output output_2.xlsx --overwrite
```

Lưu ý CLI:

- `--resume` dùng hãng/cấu hình trong phiên; không kết hợp input, `--carrier`, `--settings` hoặc `--sheet`.
- `--source` chỉ dùng cùng `--resume`; nội dung nguồn phải khớp SHA-256 đã lưu.
- Không kết hợp `--no-review` và `--review`.
- Không tự tìm `settings.json` cạnh app như GUI: muốn dùng cấu hình riêng phải truyền `--settings`.
- `--overwrite` cho phép thay bộ kết quả khi dữ liệu đủ điều kiện xuất. Khi còn lỗi chặn và Excel hoặc JSON đích đã có, CLI giữ nguyên các file đích kể cả khi có cờ này. Để lưu riêng báo cáo lỗi, bỏ `--output` và chọn tên `--review` mới. Nếu cả hai đích đều mới, lần xuất bị chặn vẫn lưu JSON khi đã chỉ định `--review` tường minh. Manifest nguồn luôn được bảo vệ.
- Mã thoát **0**: không có lỗi chặn; **2**: kiểm tra dữ liệu còn lỗi khi không yêu cầu xuất, hoặc đối số CLI không hợp lệ; **1**: thao tác thất bại/xuất bị chặn.
- CLI không có dialog xác nhận cảnh báo; người vận hành cần đọc `issues` và cấu hình hiệu lực trong kết quả trước khi dùng file xuất.

## Dữ liệu thử và kiểm chứng

Thư mục `samples/` có dữ liệu **tổng hợp** cho ba hãng và ca cần đối chiếu. Mở `DEMO_[HANG]_INPUT.xlsx`, xuất với tên mới và so sánh `DEMO_[HANG]_EXPECTED.xlsx`. Dùng `DEMO_VIMC_NEEDS_REVIEW.xlsx` để thử thiếu chủ hàng và dòng trọng lượng/mô tả mơ hồ.

EXPECTED của demo là kết quả minh họa từ chương trình, không phải output được Cảng xác nhận. Bộ dữ liệu đối chiếu có giá trị kỳ vọng độc lập được mô tả tại [docs/GOLDEN_DATA_V110.md](docs/GOLDEN_DATA_V110.md).

```bash
python -m unittest discover -s tests -v
python scripts/create_samples.py --output demo_generated
```

Trên Windows có thể chạy `RUN_TESTS.cmd`. Kết quả kiểm thử, phiên bản thư viện, phạm vi và giới hạn được cập nhật tại [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md); tài liệu này không tự ghi một con số test cố định.

Các demo và golden được giữ nguyên từ 1.1.0 để đối chiếu tính tương thích; bản vá chỉ đổi nhánh CLI khi xuất thất bại. Không ghi đè mẫu đóng gói trong lúc kiểm checksum. Các phiên review v2 của 1.1.0 tiếp tục được mở bằng 1.1.1.

### Giới hạn còn phải nghiệm thu

- Chưa kiểm thử trực quan giao diện Tkinter native trên Windows trong môi trường bàn giao này.
- Chưa build/chạy nghiệm thu bản EXE Windows; cần kiểm tra ở máy đích, gồm DPI, đường dẫn tiếng Việt và quyền ghi thư mục.
- Chưa nhập thử trên hệ thống quản lý container của Cảng, chưa có corpus manifest thật kèm output được Cảng xác nhận.
- Các ca hồi quy chứng minh hành vi cụ thể, không xác lập tỷ lệ chính xác vận hành hoặc bao phủ mọi định dạng chưa gặp.

Nguồn kế thừa và commit được ghi tại [SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json). Chi tiết quy tắc lịch sử nằm trong `docs/VOSCO_CHANGES.md`, `docs/VIMC_CHANGES.md`, `docs/VINAFCO_CHANGES.md`; tài liệu 1.1 ghi những sửa đổi tiếp theo. Ghi công các tác giả và quy tắc nghiệp vụ của ba repo gốc; gói này phục vụ phạm vi công việc của chủ sở hữu các repo.
