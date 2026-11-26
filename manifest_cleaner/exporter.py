"""Port import files in the TOS form shared by every carrier (roadmap MC3).

The app view has 16 columns in TOS order, including STT and Ghi chú, which only
the app shows. The Excel file carries the 46 TOS headers; values keep each
carrier's rules for quantity scope, rounding, EMPTY and seal checks.
"""
from __future__ import annotations

import math
import os
import copy
import shutil
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import xlsxwriter

from .common import seal_text, text_value
from . import __version__
from .carriers import (APP_ONLY_COLUMNS, CARGO_TO_TOS, CARRIER_PROFILES, PORT_COLUMNS, TOS_COLUMNS,
                       TOS_EXPORT_COLUMNS, TOS_FIXED_VALUES, VTOS_TO_TOS_ISO)
from .engine import EDITABLE_FIELDS, FIELD_LABELS, ManifestSession, assert_source_unchanged, source_sha256


SEAL_REFERENCE_NOTE = "⚠️ Seal không hợp lệ"
IDENTIFIER_COLUMNS = {"Container_No": "Số Container", "Seal_No": "Số niêm chì"}
SHEET_NAME = "Sheet1"
EXPORT_FORM = "TOS_TEMPLATE47"
TABLE_STYLE = "Table Style Medium 2"
EXTRA_COLUMN_WIDTH = 0.1
NUMBER_COLUMNS = frozenset({"STT", "Số lượng", "TL hàng"})
WEIGHT_COLUMN = "TL hàng"
FILL_IDENTIFIER, FILL_WARNING, FILL_EMPTY = "#FFFF00", "#FFF4D8", "#DAEEF3"


def tos_cargo(cargo) -> tuple[str, str]:
    """TOS code and name for the app's cargo type; unknown types keep the app's text and no code."""
    text = text_value(cargo)
    return CARGO_TO_TOS.get(text.upper(), ("", text))


def tos_row(columns, row) -> list:
    """Place app-view values under the 46 TOS headers and add the operator's fixed values.

    The fixed values (TOS_FIXED_VALUES) are added here, not in _write_tos_sheet: the exporter
    owns what a data row means, while the writer stays a generic layout writer that never
    invents values (an empty export's placeholder row and hand-made rows stay as given).
    App-only columns and every other column stay blank.
    """
    values = dict(zip(columns, row))
    values.update(TOS_FIXED_VALUES)
    return [None if name in APP_ONLY_COLUMNS else values.get(name) for name in TOS_COLUMNS]


def _edit_notes(corrections, records):
    """Report the most recent reason for each touched field. JSON keeps the full history."""
    notes = defaultdict(list)
    seen = defaultdict(set)
    verified = {row["record_id"]: set(row.get("_current_verified_fields", row.get("_verified_fields", [])))
                for row in records}
    for change in reversed(corrections):
        if change.get("action") != "edit":
            continue
        rid = change.get("record_id")
        parts = []
        for key, label in (("changed_fields", "Đã sửa"), ("verified_fields", "Đã đối chiếu")):
            names = [name for name in EDITABLE_FIELDS if name in (change.get(key) or ()) and name not in seen[rid]]
            if key == "verified_fields":
                names = [name for name in names if name in verified.get(rid, set())]
            if names:
                parts.append(label + " " + ", ".join(FIELD_LABELS[name] for name in names))
                seen[rid].update(names)
        if parts:
            notes[rid].append(". ".join(parts) + ". " + text_value(change.get("reason")))
    return notes


def _port_rows(session: ManifestSession, *, allow_errors: bool = False,
               extra_record: dict | None = None) -> tuple[list[str], list[list], dict[str | None, list[int]]]:
    profile = CARRIER_PROFILES[session.carrier].export
    issues = session.validate()
    errors = [i for i in issues if i.get("severity") == "error"]
    if errors and not allow_errors:
        raise ValueError(f"Còn {len(errors)} lỗi cần xử lý trước khi xuất file nhập Cảng. Có thể lưu bản đối chiếu JSON.")
    records = session.active_records()
    if extra_record is not None:
        if any(r["record_id"] == extra_record["record_id"] for r in records):
            records = [extra_record if r["record_id"] == extra_record["record_id"] else r for r in records]
        else:
            records = records + [extra_record]
    quantities = defaultdict(set)
    def quantity_key(record):
        if profile.group_quantity_by_master_bl and record.get("Master_BL_Group_ID"):
            return text_value(record["Master_BL_Group_ID"])
        return text_value(record.get("BL_No"))
    for record in records:
        quantities[quantity_key(record)].add(text_value(record.get("Container_No")))
    by_record = defaultdict(list)
    for item in issues:
        if item.get("record_id") and item.get("severity") in {"warning", "error"}:
            by_record[str(item["record_id"])].append(item)
    edits = _edit_notes(session.corrections, records)
    columns = PORT_COLUMNS
    rows = []
    highlights = defaultdict(list)
    for index, record in enumerate(records, 1):
        local_issues = by_record[record["record_id"]]
        warnings = [item for item in local_issues if item["severity"] == "warning"]
        if warnings:
            highlights[None].append(index)
        identifier_fields = {item.get("field") for item in warnings if item.get("field") in IDENTIFIER_COLUMNS}
        remarks = list(dict.fromkeys(i["message"] for i in local_issues if i.get("message")))
        seal = seal_text(record.get("Seal_No"))
        seal_reference = seal.strip()
        verified = record.get("_current_verified_fields", record.get("_verified_fields", ()))
        if (profile.seal_reference_lengths and seal_reference and "Seal_No" not in verified
                and (len(seal_reference) not in profile.seal_reference_lengths
                     or not (seal_reference.isascii() and seal_reference.isdigit()))):
            identifier_fields.add("Seal_No")
            if SEAL_REFERENCE_NOTE not in remarks:
                remarks.append(SEAL_REFERENCE_NOTE)
        for field in identifier_fields:
            highlights[IDENTIFIER_COLUMNS[field]].append(index)
        if identifier_fields:
            highlights["Ghi chú"].append(index)
        remarks.extend(reversed(edits[record["record_id"]]))
        if record.get("_manual_review_reason"):
            remarks.append("Đã đối chiếu dòng. " + record["_manual_review_reason"])
        weight = record.get("Weight_Value")
        if weight is not None:
            try:
                weight = float(weight)
                if not math.isfinite(weight) or weight < 0:
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                if not allow_errors:
                    raise ValueError("Trọng lượng không hợp lệ.")
                weight = None
            if weight is not None and profile.weight_digits is not None:
                weight = float(pd.Series([weight], dtype="float64").round(profile.weight_digits).iloc[0])
        description = text_value(record.get("Description"))
        if record.get("FE_Status") == "E" and profile.empty_description is not None:
            description = profile.empty_description
        vtos = text_value(record.get("VTOS_Size"))
        cargo_code, cargo_name = tos_cargo(record.get("Cargo_Type"))
        # In TOS, Kích cỡ is the VTOS code for every carrier; the manifest's own code stays in the review.
        values = {"STT": index, "Số lượng": len(quantities[quantity_key(record)]),
                  "Số BL": text_value(record.get("BL_No")),
                  "Số Container": text_value(record.get("Container_No")), "Hãng khai thác": text_value(record.get("Operator")),
                  "Kích cỡ": vtos, "Kích cỡ ISO": VTOS_TO_TOS_ISO.get(vtos.upper(), ""),
                  "F/E": text_value(record.get("FE_Status")), "TL hàng": weight,
                  "Số niêm chì": seal, "Số niêm chì 1": seal,
                  "Chủ hàng": text_value(record.get("Cleaned_Consignee_Name_For_Output")),
                  "Loại hàng": cargo_code, "Loại hàng ": cargo_name, "Hàng hóa": description,
                  "Ghi chú": " | ".join(remarks)}
        row = [values[c] for c in columns]
        if not allow_errors:
            for name, value in zip(columns, row):
                if name not in APP_ONLY_COLUMNS and isinstance(value, str) and len(value) > 32767:
                    raise ValueError(f"Dòng {index}, cột {name} dài quá giới hạn 32767 ký tự của Excel; cần rút gọn giá trị xuất, dữ liệu gốc vẫn được giữ.")
        rows.append(row)
    return list(columns), rows, highlights


def build_port_rows(session: ManifestSession) -> tuple[list[str], list[list]]:
    """Build validated import rows; previews never bypass this export gate."""
    columns, rows, _ = _port_rows(session)
    return columns, rows


def preview_port_rows(session: ManifestSession) -> tuple[list[str], list[list], dict[str | None, list[int]]]:
    """Read-only rows for the on-screen preview, from the same conversion and highlights as the Excel export.

    Blocking errors do not stop the preview; export_port_excel still refuses to write while they remain.
    """
    return _port_rows(session, allow_errors=True)


def preview_record_for_export(session: ManifestSession, record: dict) -> dict:
    """Read-only preview using the very same conversion rules as the export."""
    columns, rows, _ = _port_rows(session, allow_errors=True, extra_record=record)
    records = session.active_records()
    index = next((i for i, r in enumerate(records) if r["record_id"] == record["record_id"]), len(records))
    return dict(zip(columns, rows[index]))


def _write_tos_sheet(book, rows, fills, weight_format) -> None:
    """Write rows laid out under TOS_COLUMNS (46 values; a 47th is ignored) as the template's Excel Table.

    The table is named Sheet1 and has the 46 TOS headers plus the blank Column1,
    as in the Port's import template. It needs at least one data row, so an empty
    export gets one empty row. Fills are static cell formats so that sorting in
    Excel moves them with their row: a yellow identifier cell beats the row's
    warning or empty fill.
    """
    sheet = book.add_worksheet(SHEET_NAME)
    formats = {}
    width = len(TOS_COLUMNS)
    rows = [list(row[:width]) + [None] * (width - len(row)) for row in rows]

    def cell_format(kind, fill):
        key = (kind, fill)
        if key not in formats:
            spec = {"num_format": {"text": "@", "weight": weight_format, "number": "General"}[kind]}
            if fill:
                spec["bg_color"] = fill
            formats[key] = book.add_format(spec)
        return formats[key]

    for col_index, label in enumerate(TOS_COLUMNS):
        longest = max((len(str(row[col_index])) for row in rows if row[col_index] is not None), default=0)
        sheet.set_column(col_index, col_index, min(45, max(len(label.strip()) + 2, longest + 2)))
    for row_index, (row, (base, cells)) in enumerate(zip(rows, fills), 1):
        for col_index, (label, value) in enumerate(zip(TOS_COLUMNS, row)):
            fill = cells.get(label, base)
            kind = "weight" if label == WEIGHT_COLUMN else "number" if label in NUMBER_COLUMNS else "text"
            if value is None or value == "":
                if fill:
                    sheet.write_blank(row_index, col_index, None, cell_format(kind, fill))
            elif kind != "text":
                sheet.write_number(row_index, col_index, float(value), cell_format(kind, fill))
            else:
                sheet.write_string(row_index, col_index, str(value), cell_format(kind, fill))
    sheet.set_column(width, width, EXTRA_COLUMN_WIDTH)
    sheet.add_table(0, 0, max(len(rows), 1), len(TOS_EXPORT_COLUMNS) - 1,
                    {"name": SHEET_NAME, "style": TABLE_STYLE,
                     "columns": [{"header": label} for label in TOS_EXPORT_COLUMNS]})
    sheet.freeze_panes(1, 0)


def export_port_excel(session: ManifestSession, path: str | Path, *, overwrite: bool = False) -> Path:
    path = Path(path).resolve()
    if path.suffix.lower() != ".xlsx":
        raise ValueError("File xuất phải có đuôi .xlsx.")
    if path == Path(session.metadata.get("source_path", "")).resolve():
        raise ValueError("Chọn tên khác với manifest gốc.")
    if path.exists() and not overwrite:
        raise FileExistsError("File đã tồn tại; chọn tên mới hoặc xác nhận ghi đè.")
    assert_source_unchanged(session)
    columns, rows, highlights = _port_rows(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".manifest_export_", suffix=".xlsx", dir=path.parent)
    os.close(fd)
    try:
        with xlsxwriter.Workbook(temp_name, {"strings_to_formulas": False, "strings_to_urls": False}) as book:
            session.metadata.setdefault("session_id", uuid.uuid4().hex)
            for name, value in {"session_id": session.metadata["session_id"],
                                "source_sha256": session.metadata.get("source_sha256", ""),
                                "app_version": __version__, "carrier": session.carrier,
                                "source_name": Path(session.metadata.get("source_path", "")).name,
                                "export_form": EXPORT_FORM}.items():
                book.set_custom_property(name, str(value))
            warning_rows = set(highlights.get(None, ()))
            marked = {label: set(highlights.get(label, ())) for label in IDENTIFIER_COLUMNS.values()}
            fe = columns.index("F/E")
            fills = []
            for number, row in enumerate(rows, 1):
                base = FILL_WARNING if number in warning_rows else FILL_EMPTY if row[fe] == "E" else None
                cells = {label: FILL_IDENTIFIER for label, numbers in marked.items() if number in numbers}
                fills.append((base, cells))
            _write_tos_sheet(book, [tos_row(columns, row) for row in rows], fills,
                             CARRIER_PROFILES[session.carrier].export.weight_format)
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return path


def export_port_bundle(session: ManifestSession, path: str | Path, *, overwrite: bool = False,
                       include_review: bool = True, review_path: str | Path | None = None) -> dict:
    """Stage Excel and its resumable review together, with rollback on I/O error.

    File replacement is atomic per file. A two-file replacement cannot be a
    filesystem-wide transaction; caught commit failures restore prior outputs.
    If rollback itself fails, recovery copies are retained and the error says so.
    """
    target = Path(path).resolve()
    if target.suffix.lower() != ".xlsx":
        raise ValueError("File xuất phải có đuôi .xlsx.")
    source = session.metadata.get("source_path")
    if source and target == Path(source).resolve():
        raise ValueError("Chọn tên khác với manifest gốc.")
    if review_path is not None and not include_review:
        raise ValueError("Đã chỉ định bản đối chiếu nhưng lại tắt xuất đối chiếu.")
    review_path = (Path(review_path).resolve() if review_path else target.with_suffix(".review.json")) if include_review else None
    if review_path and review_path.suffix.lower() != ".json":
        raise ValueError("Bản đối chiếu/phiên phải có đuôi .json.")
    if review_path and source and review_path == Path(source).resolve():
        raise ValueError("Không ghi đè manifest nguồn bằng bản đối chiếu.")
    targets = [target] + ([review_path] if review_path else [])
    if not overwrite and any(p.exists() for p in targets):
        raise FileExistsError("File Excel hoặc bản đối chiếu cùng tên đã tồn tại; chọn tên mới hoặc xác nhận ghi đè cả bộ.")
    assert_source_unchanged(session)
    build_port_rows(session)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".manifest_bundle_", dir=target.parent))
    stages = [stage]
    old_metadata = copy.deepcopy(session.metadata)
    backups = {}
    committed = []
    keep_recovery = False
    try:
        staged_excel = export_port_excel(session, stage / target.name)
        session.metadata["last_export"] = {
            "excel_path": str(target), "review_path": str(review_path) if review_path else None,
            "excel_sha256": source_sha256(staged_excel), "session_id": session.metadata["session_id"],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        staged_files = [(staged_excel, target)]
        if review_path:
            review_stage = stage
            if review_path.parent != target.parent:
                review_path.parent.mkdir(parents=True, exist_ok=True)
                review_stage = Path(tempfile.mkdtemp(prefix=".manifest_bundle_", dir=review_path.parent))
                stages.append(review_stage)
            staged_review = session.save_review(review_stage / review_path.name)
            staged_files.append((staged_review, review_path))
        # Prepare all backups before replacing either existing output.
        for index, (prepared, destination) in enumerate(staged_files):
            if destination.exists():
                backup_directory = prepared.parent / "backups"
                backup_directory.mkdir(exist_ok=True)
                backup = backup_directory / ("previous_" + str(index) + destination.suffix)
                shutil.copy2(destination, backup)
                backups[destination] = backup
        try:
            for prepared, destination in staged_files:
                os.replace(prepared, destination)
                committed.append(destination)
        except Exception as exc:
            rollback_errors = []
            for destination in reversed(committed):
                try:
                    if destination in backups:
                        os.replace(backups[destination], destination)
                    else:
                        destination.unlink(missing_ok=True)
                except OSError as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if rollback_errors:
                keep_recovery = True
                recovery = "; ".join(str(p) for p in stages)
                raise OSError(f"Xuất bộ file chưa hoàn tất và không khôi phục được toàn bộ. Bản dự phòng còn tại {recovery}. Kiểm tra cả Excel và JSON trước khi sử dụng. Lỗi gốc: {exc}") from exc
            raise OSError("Không xuất đủ bộ Excel và đối chiếu; các file đích trước đó được giữ nguyên. " + str(exc)) from exc
    except Exception:
        session.metadata.clear()
        session.metadata.update(old_metadata)
        raise
    finally:
        if not keep_recovery:
            for folder in stages:
                shutil.rmtree(folder, ignore_errors=True)
    return {"excel": target, "review": review_path}
