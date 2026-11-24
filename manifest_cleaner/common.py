"""Shared, deterministic helpers. Importing this module never starts a GUI."""
from __future__ import annotations

import math
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd


def text_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_text(value: Any) -> str:
    text = text_value(value).replace("Đ", "D").replace("đ", "d")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(text.upper().split())


def seal_text(value: Any) -> str:
    """Return declared seal text exactly, including spaces and punctuation."""
    return value if isinstance(value, str) else text_value(value)


def is_explicit_empty(value: Any) -> bool:
    """Match container-status phrases, never goods such as EMPTY BOTTLES."""
    text = normalize_text(value).strip(" .:;-_")
    if not text:
        return False
    # Remove only a recognized quantity/size annotation, not arbitrary cargo words.
    text = re.sub(r"\s*\(?\d+\)?\s*[X×]\s*(?:20|40|45)'?\s*[A-Z0-9]+(?:\s+(?:SOC|COC))?\s*$", "", text).strip(" ,;()")
    text = re.sub(r"^(?:SOC|COC|S\.O\.C\.?|C\.O\.C\.?)\s*[-:/]?\s*", "", text)
    text = re.sub(r"\s*[-:/]?\s*(?:SOC|COC|S\.O\.C\.?|C\.O\.C\.?)$", "", text)
    return bool(re.fullmatch(r"(?:EMPTY(?:\s+(?:CONTAINERS?|CNTRS?|CONT))?|(?:CONTAINER|CONT|CHUYEN)\s+RONG|RONG|NO CARGO)", text))


def parse_weight(text: Any, default_unit: str = "TONS", number_format: str = "legacy") -> dict | None:
    """Read a weight once and return tonnes without early rounding.

    Legacy profiles: commas group kg and are decimal separators for tonnes;
    dots are decimal separators. With both separators the last one is decimal.
    A configured decimal_comma/decimal_dot convention overrides the legacy rule.
    Native Excel numeric cells are numeric, not locale-formatted strings.
    """
    raw = text_value(text)
    if not raw or isinstance(text, bool):
        return None
    match = re.fullmatch(r"\s*([+-]?[\d\s\u00a0\u202f.,]+)\s*(KGS?|KILOGRAMS?|TONNES?|TONS?|MT|T)?\s*", raw, re.I)
    if not match:
        return None
    numeric = re.sub(r"[\s\u00a0\u202f]", "", match.group(1))
    source_unit = (match.group(2) or default_unit).upper().strip()
    if source_unit in {"KG", "KGS", "KILOGRAM", "KILOGRAMS"}:
        source_unit = "KGS"
    elif source_unit in {"T", "MT", "TON", "TONS", "TONNE", "TONNES"}:
        source_unit = "TONS"
    else:
        return None
    if number_format not in {"legacy", "decimal_comma", "decimal_dot"}:
        return None
    if isinstance(text, (int, float, Decimal)):
        numeric = str(text)
    elif "," in numeric and "." in numeric:
        decimal_sep = "," if numeric.rfind(",") > numeric.rfind(".") else "."
        if number_format != "legacy":
            requested = "," if number_format == "decimal_comma" else "."
            if requested != decimal_sep:
                return None
        grouping = "." if decimal_sep == "," else ","
        integer, fraction = numeric.rsplit(decimal_sep, 1)
        if not re.fullmatch(r"[+-]?\d{1,3}(?:" + re.escape(grouping) + r"\d{3})+", integer) or not fraction.isdigit():
            return None
        numeric = integer.replace(grouping, "") + "." + fraction
    else:
        sep = "," if "," in numeric else "." if "." in numeric else None
        if sep:
            count = numeric.count(sep)
            is_groups = bool(re.fullmatch(r"[+-]?\d{1,3}(?:" + re.escape(sep) + r"\d{3})+", numeric))
            if count > 1:
                if not is_groups:
                    return None
                configured_decimal = "," if number_format == "decimal_comma" else "." if number_format == "decimal_dot" else None
                if sep == configured_decimal:
                    return None
                numeric = numeric.replace(sep, "")
            elif number_format == "decimal_comma":
                if sep == ".":
                    if not is_groups:
                        return None
                    numeric = numeric.replace(".", "")
                else:
                    numeric = numeric.replace(",", ".")
            elif number_format == "decimal_dot":
                if sep == ",":
                    if not is_groups:
                        return None
                    numeric = numeric.replace(",", "")
            elif sep == ",":
                numeric = numeric.replace(",", "") if source_unit == "KGS" and is_groups else numeric.replace(",", ".")
    try:
        value = Decimal(numeric)
        if not value.is_finite() or value < 0:
            return None
        if source_unit == "KGS":
            value /= Decimal("1000")
        result = float(value)
        if not math.isfinite(result):
            return None
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return {"value": result, "unit": "TONS", "source_unit": source_unit, "raw": raw}


def issue(code: str, message: str, *, severity: str = "warning", record_id=None, field=None, source_row=None, source_sheet=None) -> dict:
    return {"code": code, "severity": severity, "message": message, "record_id": record_id,
            "field": field, "source_row": source_row, "source_sheet": source_sheet}


def inspect_workbook_source(path: str | Path) -> dict:
    """Inspect source evidence that data_only readers cannot retain.

    This does not evaluate formulas. Missing results in selected manifest sheets
    become blocking source issues in the engine, rather than invisible blank rows.
    The legacy read_workbook API remains useful for reading raw cached values.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError("Không tìm thấy file manifest.")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("File vượt 50 MB. Hãy tách đúng manifest cần xử lý.")
    with path.open("rb") as handle:
        magic = handle.read(8)
    result = {"available_sheets": [], "formula_cells": [], "formula_cache_scan": "not_available_xls"}
    if magic.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        import xlrd
        book = xlrd.open_workbook(path, on_demand=True)
        try:
            result["available_sheets"] = book.sheet_names()
        finally:
            book.release_resources()
        return result
    if not magic.startswith(b"PK\x03\x04"):
        raise ValueError("Nội dung file không phải Excel XLS/XLSX hợp lệ, hoặc file đã bị hỏng.")
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 256 * 1024 * 1024:
            raise ValueError("Nội dung Excel sau giải nén quá lớn; hãy giữ vùng manifest cần xử lý.")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib.get("Target", "") for r in relations
                   if r.attrib.get("TargetMode") != "External"}
        for sheet in workbook.findall(f"{ns}sheets/{ns}sheet"):
            name = sheet.attrib.get("name", "")
            result["available_sheets"].append(name)
            target = targets.get(sheet.attrib.get(rel_ns + "id"), "")
            if not target:
                continue
            entry = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            if entry not in archive.namelist():
                continue
            with archive.open(entry) as handle:
                for _, element in ET.iterparse(handle, events=("end",)):
                    if element.tag == ns + "c":
                        formula = element.find(ns + "f")
                        value = element.find(ns + "v")
                        if formula is not None:
                            kind = element.attrib.get("t", "n")
                            cache_missing = value is None or (value.text is None and kind != "str")
                            cache_error = kind == "e"
                            if cache_missing or cache_error:
                                address = element.attrib.get("r", "?")
                                row_match = re.search(r"(\d+)$", address)
                                result["formula_cells"].append({
                                    "source_sheet": name, "source_cell": address,
                                    "source_row": int(row_match.group(1)) if row_match else None,
                                    "formula": (formula.text or "")[:1000],
                                    "cached_value": value.text if value is not None else None,
                                    "status": "error" if cache_error else "missing",
                                })
                        element.clear()
                    elif element.tag == ns + "row":
                        element.clear()
    result["formula_cache_scan"] = "xlsx_xml"
    return result


def read_workbook(path: str | Path) -> list[tuple[str, pd.DataFrame]]:
    """Read one local workbook by actual file signature, including renamed .xls.

    Excel text values and formatted integer identifiers keep leading zeros.
    Formulas are not executed; missing cached formula values stay missing.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError("Không tìm thấy file manifest.")
    if path.suffix.lower() not in {".xls", ".xlsx", ".xlsm"}:
        raise ValueError("Chọn file Excel .xls, .xlsx hoặc .xlsm.")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("File vượt 50 MB. Hãy tách đúng manifest cần xử lý.")
    with path.open("rb") as handle:
        magic = handle.read(8)
    if magic.startswith(b"PK\x03\x04"):
        from openpyxl import load_workbook
        # Passing bytes stream also accepts XLSX contents with a legacy .xls name.
        output = []
        with path.open("rb") as stream:
            book = load_workbook(stream, read_only=True, data_only=True, keep_links=False)
            try:
                for sheet in book.worksheets:
                    rows = []
                    if (sheet.max_row or 0) > 200000 or (sheet.max_column or 0) > 1000:
                        raise ValueError("Sheet quá lớn; hãy giữ vùng manifest cần xử lý.")
                    for cells in sheet.iter_rows():
                        row = []
                        for cell in cells:
                            value = cell.value
                            fmt = cell.number_format or ""
                            if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer() and re.fullmatch(r"0{2,30}", fmt):
                                value = str(int(value)).zfill(len(fmt))
                            row.append("" if value is None else value)
                        rows.append(row)
                    df = pd.DataFrame(rows, dtype=object)
                    df.attrs["sheet_name"] = sheet.title
                    output.append((sheet.title, df))
            finally:
                book.close()
        return output
    if magic.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        import xlrd
        book = xlrd.open_workbook(path, formatting_info=True)
        output = []
        try:
            for sheet in book.sheets():
                if sheet.nrows > 200000 or sheet.ncols > 1000:
                    raise ValueError("Sheet quá lớn; hãy giữ vùng manifest cần xử lý.")
                rows = []
                for row_index in range(sheet.nrows):
                    row = []
                    for cell in sheet.row(row_index):
                        value = cell.value
                        if cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
                            value = ""
                        elif cell.ctype == xlrd.XL_CELL_NUMBER:
                            fmt = book.format_map[book.xf_list[cell.xf_index].format_key].format_str
                            if float(value).is_integer() and re.fullmatch(r"0{2,30}", fmt or ""):
                                value = str(int(value)).zfill(len(fmt))
                        elif cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate_as_datetime(value, book.datemode)
                        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                            value = bool(value)
                        elif cell.ctype == xlrd.XL_CELL_ERROR:
                            value = xlrd.error_text_from_code.get(value, "#EXCEL_ERROR")
                        row.append(value)
                    rows.append(row)
                df = pd.DataFrame(rows, dtype=object)
                df.attrs["sheet_name"] = sheet.name
                output.append((sheet.name, df))
        finally:
            book.release_resources()
        return output
    raise ValueError("Nội dung file không phải Excel XLS/XLSX hợp lệ, hoặc file đã bị hỏng.")
