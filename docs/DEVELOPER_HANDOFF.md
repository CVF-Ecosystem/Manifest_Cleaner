# Bàn giao Manifest Cleaner Unified v1.1.1 cho agent local

**Đọc trước:** [LOCAL_AGENT_V111.md](LOCAL_AGENT_V111.md) cho bản vá CLI, các bước kiểm tra local và đề xuất tăng khả năng đọc Excel lộn xộn. Phần đề xuất chưa phải tính năng đã triển khai trong 1.1.1. Hướng dẫn vận hành 1.1 được kế thừa bên dưới.

## 1. Mục tiêu và trạng thái bàn giao

Một ứng dụng local, một manifest của một hãng trong mỗi phiên, xuất đúng hợp
đồng nhập hệ thống cảng. Chọn theo **VOSCO / VIMC / VINAFCO**; tên tàu hoặc tên
file không quyết định bộ đọc. Mã hãng khai thác, quy đổi kích cỡ và cách xuất
đặc thù của từng hãng vẫn được giữ.

Đây là **gói mã nguồn và công thức đóng gói**. Gói này chưa kèm Windows EXE đã
build/nghiệm thu; kiểm thử không giao diện đã chạy trong môi trường chuẩn bị.
Kết quả và số test cuối cùng nằm trong `docs/VALIDATION_REPORT.md`. Không coi
test của các helper GUI là bằng chứng cửa sổ đã được kiểm tra trực quan.

`SOURCE_PROVENANCE.json` ghi ba repository/commit nền. Các fixture audit và
golden là dữ liệu tổng hợp. Chưa có bộ kết quả import thật được Cảng xác nhận.

## 2. Chạy bản nguồn trên Windows

Giải nén toàn bộ gói vào thư mục có quyền ghi. Khuyến nghị Python **3.12 x64** có
thành phần Tcl/Tk; phạm vi khai báo của gói là Python 3.10–3.13 x64.

```bat
START.cmd
```

Launcher dùng `.venv` riêng của ứng dụng. Nếu môi trường đã đủ và đúng thư viện,
START mở app, không gọi pip hoặc yêu cầu mạng. Khi thiếu môi trường/phụ thuộc,
START gọi SETUP. SETUP chỉ cài các phiên bản trong `requirements.txt` vào `.venv`,
không cài package vào Python hệ thống.

SETUP lần lượt thử Python 3.12, 3.11, 3.13, 3.10 rồi Python mặc định, nhưng chỉ
chọn phiên bản 64-bit trong khoảng hỗ trợ và có Tkinter. Một `.venv` cũ sai
Python hoặc thiếu Tcl/Tk được báo rõ; giữ lại bằng cách đổi tên rồi tạo môi
trường mới sau khi sửa Python. Tcl/Tk là thành phần của bản cài Python, không
được khắc phục bằng cách lặp cài bốn thư viện Excel.

Môi trường hạn chế mạng có thể chuẩn bị wheelhouse bằng Python/Windows cùng
kiến trúc ở máy được phép tải, sau đó tạo `.venv` nếu chưa có và cài local:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt
.venv\Scripts\python.exe scripts\check_release.py --runtime-only
START.cmd
```

Wheelhouse không có trong gói này. Bản nguồn vẫn cần Python/Tkinter và đủ các
wheel tương thích; START không thay thế các điều kiện đó.

## 3. Xác minh gói và chạy kiểm thử

```bat
py -3.12 scripts\check_release.py
.venv\Scripts\python.exe scripts\check_release.py --runtime-only
RUN_TESTS.cmd
```

Lệnh đầu kiểm SHA-256 của các file liệt kê trong `PACKAGE_MANIFEST.sha256`, không
cài package hoặc sửa file. Lệnh runtime kiểm Python, Tkinter, khả năng import
và đúng bốn phiên bản phụ thuộc. Tkinter import được không có nghĩa đã mở và
nghiệm thu giao diện.

Có thể kiểm checksum, runtime rồi chạy toàn bộ test trong một lệnh:

```bat
.venv\Scripts\python.exe scripts\check_release.py --tests
```

Checksum giúp phát hiện bytes bị thay đổi hoặc file thiếu so với gói bàn giao;
không phải chữ ký số xác nhận nguồn phát hành. Khi sửa source, checksum cũ có
thể thất bại là đúng. Agent phát hành phải tạo lại manifest checksum sau khi
chốt code/tài liệu/test, không sửa checksum để bỏ qua lỗi trong một gói vừa tải.

Không chạy `create_samples.py` đè lên samples khi kiểm gói nhận được. Nếu cần
tạo demo mới để phát triển, dùng thư mục riêng:

```bat
.venv\Scripts\python.exe scripts\create_samples.py --output demo_generated
```

EXPECTED trong demo được chương trình sinh, không phải chuẩn độc lập. Golden
độc lập ở `tests/fixtures/golden_v110` có expected JSON viết tay và input cố
định; đọc `docs/GOLDEN_DATA_V110.md`. Không regenerate golden từ output parser.

## 4. Kiến trúc và các ranh giới cần giữ

| Thành phần | Vai trò |
|---|---|
| `common.py` | Text, số/đơn vị, trạng thái rỗng tường minh, đọc XLS/XLSX, kiểm tra nguồn/công thức |
| `engine.py` | Cấu hình, phiên, validation, chỉnh sửa/xác minh/loại, nguồn SHA-256, save/resume review v2 |
| `exporter.py` | Mapping 16 cột dùng chung với preview; Excel và sidecar; staging/rollback khi lỗi ghi |
| `gui.py` | Tkinter, worker/queue, bảng cần kiểm tra, sửa theo trường, nguồn/preview, lưu và khôi phục phiên |
| `cli.py` | Xử lý/khôi phục/xuất không cần giao diện |
| `carriers/<hãng>/` | Parser và quy tắc riêng hãng, mapping xuất của hãng |
| `tests/` | Hồi quy, hợp đồng import, lỗi ghi file, nguồn thay đổi và golden tổng hợp |

API adapter giữ dạng:

```python
parse_manifest(path, *, settings=None, progress=None)
# {'records': [...], 'issues': [...], 'metadata': {...}}
refresh_derived_fields(record, settings=None)
is_supported_size_type(size_type, settings=None)
```

`Weight_Value` là tấn, chưa làm tròn sớm. `Size_Type` là mã nguồn;
`VTOS_Size` là mã xuất. Dữ liệu nguồn và tọa độ nằm trong `raw`/metadata. Xem
`ADAPTER_CONTRACT.md` và các tài liệu `*_FIXES_V110.md` để biết thay đổi cụ thể.

## 5. Chỉnh sửa, xác minh và chặn xuất

`update_record(record_id, changes, reason, verified_fields=...)` chỉ ghi nhận
trường thực sự đổi và trường được xác minh rõ ràng. Gửi lại mọi giá trị cũ từ
form không tự xác minh chúng. Issue đơn trường có `field`; issue kết hợp có
`resolution_fields`. Sửa seal không được vô tình xóa lỗi trọng lượng/F/E.

`acknowledge_record` ghi căn cứ đã kiểm cảnh báo, không xóa error. Loại record
cần lý do và vẫn nằm trong review JSON. Lỗi toàn file như header đổi đơn vị hoặc
công thức nguồn thiếu kết quả cần sửa/tính lại nguồn rồi nhập lại.

`preview_record_for_export(session, record)` dùng cùng mapping 16 cột với xuất,
nhưng preview không vượt qua chốt validation. `export_port_bundle` mặc định tạo
Excel cùng `.review.json`, cùng `session_id`. Excel có custom properties và
review có receipt/hash để đối chiếu, không thêm cột vào schema nhập cảng.

Hai file được chuẩn bị trước khi commit. Khi một lần ghi thất bại, cố khôi
phục output trước đó; nếu việc khôi phục cũng thất bại, báo rõ và giữ thư mục
recovery. Đây không phải giao dịch nguyên tử hai file ở cấp hệ điều hành.

Khôi phục review v2 và xuất lại đều kiểm nguồn theo SHA-256. Khi chuyển máy,
có thể chọn lại đúng file nguồn nhưng bytes phải trùng. Thay nguồn không được
ngầm giữ các chỉnh sửa của lần xử lý khác.

## 6. Cấu hình và file người dùng

`settings.example.json` là mẫu; `settings.json` là cấu hình người dùng. GUI đọc
settings cạnh thư mục nguồn khi chạy Python, cạnh `ManifestCleaner.exe` khi
đóng gói. Giao diện đang dùng giá trị lưu trong phiên khôi phục có thể khác cấu
hình máy; điều này phải hiện rõ, không tự ghi đè settings của máy.

- Chung: `number_format`, `weight_kind`, `selected_sheet`.
- VOSCO: fixed columns, đơn vị mặc định; `cargo` không so với tare; `unknown`
  giữ legacy kèm cảnh báo. Alias `sheet_name` được chuẩn hóa thành selected_sheet.
- VIMC: grammar từng dòng quyết định nguồn kg/tấn; các bảng mapping được quản
  lý riêng. Không phục hồi dispatch theo tên tàu.
- VINAFCO: alias cột, đơn vị, operator, ngưỡng và mapping theo tài liệu hãng;
  `target_sheet_name` được chuẩn hóa. Header lặp đổi cột/đơn vị phải chặn.

Tên cấu hình sai, kiểu sai hoặc đơn vị chưa hỗ trợ phải báo lỗi. Không âm thầm
bỏ cấu hình rồi tuyên bố đang dùng đúng profile. Giữ số Excel native là số để
tránh diễn giải lại theo locale.

## 7. Build EXE và kiểm tra trên máy đích

```bat
BUILD_EXE.cmd
```

Build script chuẩn bị phụ thuộc, cài PyInstaller theo khoảng **6.x** đang dùng
trong recipe, chạy test, rồi build `onedir` bằng `ManifestCleaner.spec`. Chưa
pin một phiên bản PyInstaller cụ thể đã được nghiệm thu Windows trong gói này.
`BUILD_INFO.txt` ghi phiên bản thực dùng để agent local có thể khóa lại sau khi
nghiệm thu; không gọi recipe hiện tại là build tái lập bit-for-bit.

Đích là `dist\ManifestCleaner\ManifestCleaner.exe`. Chuyển **toàn bộ thư mục**
`dist\ManifestCleaner`. Script đặt `START_HERE.html`, `settings.example.json`,
checklist và BUILD_INFO cạnh EXE để người dùng tìm được; README cùng toàn bộ
`docs/` và `samples/` được sao theo đúng đường dẫn tương đối để liên kết trong
hướng dẫn mở được. PyInstaller cũng chứa
tài nguyên bên trong thư mục hỗ trợ; không đặt settings cá nhân vào đó vì GUI
đọc cạnh EXE.

Build với `--noconfirm` có thể thay thư mục dist trước đó. Dùng dist như đầu ra
build; đặt bản đang vận hành ở thư mục khác và lưu cấu hình/phiên công việc trước
khi rebuild. Thực hiện `docs/WINDOWS_RELEASE_CHECKLIST.md` trước khi bàn giao EXE
cho người dùng. Gói nguồn hiện tại không chứng minh các bước đó đã hoàn thành.

## 8. Các việc tiếp nhận còn lại

1. Kiểm GUI trực quan trên Windows với bộ demo và các trường hợp cần kiểm tra.
2. Build EXE, thử cả thư mục có khoảng trắng/chữ Việt và thư mục chạy không phải
   working directory của EXE; xác nhận settings và nguồn được tìm đúng.
3. Thử Excel đang mở khóa file output, lưu/resume phiên, nguồn bị đổi và khôi phục
   khi thao tác ghi thất bại; đọc thông báo thay vì chỉ nhìn file có tồn tại.
4. Đối chiếu manifest hiện có với người nghiệp vụ và import thử theo quy trình
   của Cảng; bổ sung golden thật riêng khi đã được xác nhận.

Không cần tài khoản AI/API để sử dụng. Pipeline xử lý manifest không gọi mạng;
cài phụ thuộc/build có thể cần mạng. Thêm hãng sau này bằng adapter + đăng ký
engine/settings/schema/test/spec; đây là module nội bộ, chưa phải cơ chế nạp
plugin tùy ý.
