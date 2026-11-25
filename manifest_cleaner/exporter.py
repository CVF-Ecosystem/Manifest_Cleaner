"""Port import files: preserve the actual 16-column schemas from each source repo."""
from __future__ import annotations

import math
import os
import copy
import shutil
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

import pandas as pd
import xlsxwriter

from .common import seal_text, text_value
from . import __version__
from .carriers import CARRIER_PROFILES
from .engine import EDITABLE_FIELDS, FIELD_LABELS, ManifestSession, assert_source_unchanged, source_sha256


SEAL_REFERENCE_NOTE = "⚠️ Seal không hợp lệ"
IDENTIFIER_COLUMNS = {"Container_No": "Số Container", "Seal_No": "Số niêm chì"}


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
    columns = profile.columns
    rows = []
    highlights = defaultdict(list)
    for index, record in enumerate(records, 1):
        local_issues = by_record[record["record_id"]]
        warnings = [item for item in local_issues if item["severity"] == "warning"]
        if warnings:
            highlights[None].append(index)
        identifier_fields = {item.get("field") for item in warnings if item.get("field") in IDENTIFIER_COLUMNS}
        # Compatibility column: a rule-based score, never measured accuracy.
        confidence = max(0, min(float(record.get("Confidence") if record.get("Confidence") is not None else 100), 80 if local_issues else 100))
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
        values = {"STT": index, "Số lượng": len(quantities[quantity_key(record)]),
                  "Số BL": text_value(record.get("BL_No")), "Số Vận Đơn": text_value(record.get("BL_No")),
                  "Số Container": text_value(record.get("Container_No")), "Hãng khai thác": text_value(record.get("Operator")),
                  "Kích cỡ": text_value(record.get(profile.primary_size_field)),
                  "Kích cỡ VTOS": text_value(record.get("VTOS_Size")), "Loại Container": text_value(record.get("VTOS_Size")),
                  "F/E": text_value(record.get("FE_Status")), "TL hàng": weight, "Trọng lượng (Tấn)": weight,
                  "Số niêm chì": seal, "Số niêm chì 1": seal,
                  "Chủ hàng": text_value(record.get("Cleaned_Consignee_Name_For_Output")),
                  "Hàng hóa": description,
                  "Loại hàng": text_value(record.get("Cargo_Type")), "Độ chính xác (%)": confidence,
                  "Ghi chú": " | ".join(remarks)}
        row = [values[c] for c in columns]
        if not allow_errors:
            for name, value in zip(columns, row):
                if isinstance(value, str) and len(value) > 32767:
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
    """Read-only preview using the very same sixteen-column conversion rules."""
    columns, rows, _ = _port_rows(session, allow_errors=True, extra_record=record)
    records = session.active_records()
    index = next((i for i, r in enumerate(records) if r["record_id"] == record["record_id"]), len(records))
    return dict(zip(columns, rows[index]))


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
                                "app_version": __version__, "carrier": session.carrier}.items():
                book.set_custom_property(name, str(value))
            sheet = book.add_worksheet("Processed_Manifest")
            header = book.add_format({"bold": True, "bg_color": "#173D5B", "font_color": "#FFFFFF", "border": 1})
            text_format = book.add_format({"num_format": "@"})
            numeric_format = book.add_format({"num_format": CARRIER_PROFILES[session.carrier].export.weight_format})
            empty_format = book.add_format({"bg_color": "#DAEEF3"})
            warning_format = book.add_format({"bg_color": "#FFF4D8"})
            identifier_format = book.add_format({"bg_color": "#FFFF00"})
            for col_index, label in enumerate(columns):
                sheet.write_string(0, col_index, label, header)
                width = min(45, max(len(label) + 2, max((len(str(row[col_index] or "")) for row in rows), default=0) + 2))
                sheet.set_column(col_index, col_index, width)
            number_columns = {"STT", "Số lượng", "TL hàng", "Trọng lượng (Tấn)", "Độ chính xác (%)"}
            for row_index, row in enumerate(rows, 1):
                for col_index, value in enumerate(row):
                    if value is None:
                        sheet.write_blank(row_index, col_index, None)
                    elif columns[col_index] in number_columns:
                        sheet.write_number(row_index, col_index, float(value), numeric_format if columns[col_index] in {"TL hàng", "Trọng lượng (Tấn)"} else None)
                    else:
                        sheet.write_string(row_index, col_index, str(value), text_format)
            from xlsxwriter.utility import xl_col_to_name
            fe_col = xl_col_to_name(columns.index("F/E"))
            last_col = xl_col_to_name(len(columns) - 1)
            if rows:
                data_range = f"A2:{last_col}{len(rows) + 1}"
                index_cell = f"${xl_col_to_name(columns.index('STT'))}2"
                # STT follows complete rows when sorted. Give the identity
                # cells priority over the general warning and empty-row colors.
                for label in ("Số Container", "Số niêm chì", "Ghi chú", None):
                    target = data_range
                    if label is not None:
                        letter = xl_col_to_name(columns.index(label))
                        target = f"{letter}2:{letter}{len(rows) + 1}"
                    conditions = []
                    numbers = highlights.get(label, ())
                    for _, run in groupby(enumerate(numbers), key=lambda item: item[1] - item[0]):
                        first, *rest = (number for _, number in run)
                        conditions.append(f"AND({index_cell}>={first},{index_cell}<={rest[-1]})"
                                          if rest else f"{index_cell}={first}")
                    for start in range(0, len(conditions), 100):
                        formula = "=OR(" + ",".join(conditions[start:start + 100]) + ")"
                        sheet.conditional_format(target, {
                            "type": "formula", "criteria": formula,
                            "format": identifier_format if label is not None else warning_format,
                            "stop_if_true": True,
                        })
                sheet.conditional_format(data_range, {"type": "formula", "criteria": f'=${fe_col}2="E"', "format": empty_format})
            sheet.freeze_panes(1, 0)
            sheet.autofilter(0, 0, len(rows), len(columns) - 1)
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
