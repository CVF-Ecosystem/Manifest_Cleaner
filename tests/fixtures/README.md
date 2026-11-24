# True XLS fixture

`padded_identifiers.xls` is a synthetic minimal BIFF8 workbook in an OLE/CFB
container, generated with Python `struct`. It contains no shipping data.

- Worksheet: `Manifest`.
- A1: numeric 42, Excel number format `000000`; the reader must return `"000042"`.
- B1: native numeric 1.234, General format; the reader must preserve the numeric value.

This is a genuine binary XLS file, not an XLSX renamed to XLS. It exercises the
xlrd branch separately from the renamed-file regressions.
