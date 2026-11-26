"""Change the shipping line's B/L on a vessel file (roadmap MC62).

Both inputs are TOS files exported by this app in step one: the vessel file, for
example a VOSCO manifest, and the file of the line that shipped containers on that
vessel, for example VIMC. Containers are matched by number. Six fields come from the
shipping line; a blank value never replaces one already present. Differences in size,
F/E, seal or cargo type are reported and the vessel value is kept. Neither source file
is written. The output keeps the vessel file's layout and colours, and a JSON trace
records both sources, their SHA-256 and every change.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
from openpyxl.packaging.custom import StringProperty
from openpyxl.styles import PatternFill

from . import __version__
from .carriers import TOS_COLUMNS
from .common import text_value
from .engine import source_sha256

CHANGED_FIELDS = ("Số lượng", "Số BL", "Hãng khai thác", "Chủ hàng", "TL hàng", "Hàng hóa")
COMPARED_FIELDS = ("Kích cỡ", "F/E", "Số niêm chì", "Số niêm chì 1", "Loại hàng", "Loại hàng ")
NUMBER_FIELDS = frozenset({"Số lượng", "TL hàng"})
CHANGE_FILL = "FFE2EFDA"
CONFLICT_FILL = "FFFFFF00"
TRACE_SCHEMA = "manifest-cleaner.blChange@1.0.0"


@dataclass
class TosFile:
    path: Path
    sha256: str
    properties: dict
    rows: dict = field(default_factory=dict)  # container -> {"row": excel row, "values": {header: value}}

    @property
    def carrier(self) -> str:
        return text_value(self.properties.get("carrier"))

    @property
    def source_name(self) -> str:
        return text_value(self.properties.get("source_name"))


def _key(value) -> str:
    return text_value(value).strip().upper()


def _same(left, right) -> bool:
    def norm(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            return str(int(number)) if number.is_integer() else repr(round(number, 6))
        return text_value(value).strip()
    return norm(left) == norm(right)


def _blank(value) -> bool:
    return value is None or text_value(value).strip() == ""


def _plain(value):
    """JSON-safe cell value; whole numbers read back from Excel as floats become ints."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def read_tos_file(path: str | Path) -> TosFile:
    path = Path(path).resolve()
    if path.suffix.lower() != ".xlsx":
        raise ValueError(f"{path.name}: cần file .xlsx đã xuất từ app theo mẫu TOS.")
    book = openpyxl.load_workbook(path, data_only=True)
    try:
        sheet = book.worksheets[0]
        headers = tuple(cell.value for cell in sheet[1])
        headers = headers[:len(TOS_COLUMNS)] if len(headers) > len(TOS_COLUMNS) and all(
            _blank(value) for value in headers[len(TOS_COLUMNS):]) else headers
        if headers != TOS_COLUMNS:
            raise ValueError(f"{path.name}: không đúng mẫu TOS 46 cột. Chọn file đã xuất từ app ở bước một.")
        properties = {prop.name: prop.value for prop in book.custom_doc_props.props}
        index = {name: position for position, name in enumerate(TOS_COLUMNS)}
        result = TosFile(path, source_sha256(path), properties)
        duplicates = []
        for row_number, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            if all(_blank(value) for value in cells):
                continue
            container = _key(cells[index["Số Container"]])
            if not container:
                raise ValueError(f"{path.name}: dòng {row_number} thiếu Số Container.")
            if container in result.rows:
                duplicates.append(container)
                continue
            result.rows[container] = {"row": row_number,
                                      "values": {name: cells[position] for name, position in index.items()}}
        if duplicates:
            shown = ", ".join(sorted(set(duplicates))[:5])
            raise ValueError(f"{path.name}: có {len(duplicates)} container trùng ({shown}). Kiểm tra lại file ở bước một.")
        if not result.rows:
            raise ValueError(f"{path.name}: không có dòng container.")
        return result
    finally:
        book.close()


def plan_bl_change(vessel: TosFile, partner: TosFile) -> dict:
    """Decide every change without writing anything."""
    if vessel.path == partner.path or vessel.sha256 == partner.sha256:
        raise ValueError("Hai lần chọn cùng một file. Chọn file tàu và file B/L của hãng gửi hàng.")
    common = [container for container in vessel.rows if container in partner.rows]
    if not common:
        raise ValueError("Hai file không có container chung. Kiểm tra lại đúng tàu và chuyến.")
    changes, conflicts, kept = [], [], []
    for container in common:
        old, new = vessel.rows[container]["values"], partner.rows[container]["values"]
        fields = {}
        for name in CHANGED_FIELDS:
            if _blank(new[name]):
                if not _blank(old[name]):
                    kept.append({"container": container, "field": name, "vessel": _plain(old[name])})
                continue
            if not _same(old[name], new[name]):
                fields[name] = {"old": _plain(old[name]), "new": _plain(new[name])}
        for name in COMPARED_FIELDS:
            if not _same(old[name], new[name]):
                conflicts.append({"container": container, "field": name, "vessel": _plain(old[name]),
                                  "partner": _plain(new[name])})
        changes.append({"container": container, "vessel_row": vessel.rows[container]["row"],
                        "partner_row": partner.rows[container]["row"], "fields": fields})
    by_bl = defaultdict(list)
    for container, item in vessel.rows.items():
        by_bl[text_value(item["values"]["Số BL"])].append(container)
    matched = set(common)
    partial = []
    for bl, containers in by_bl.items():
        hit = [c for c in containers if c in matched]
        if hit and len(hit) < len(containers):
            partial.append({"bl": bl, "total": len(containers), "matched": len(hit),
                            "remaining": [c for c in containers if c not in matched]})
    return {
        "changes": changes,
        "conflicts": conflicts,
        "kept_vessel_value_when_partner_blank": kept,
        "partner_only": [container for container in partner.rows if container not in vessel.rows],
        "partial_bls": partial,
        "summary": {"vessel_containers": len(vessel.rows), "partner_containers": len(partner.rows),
                    "matched": len(common), "changed": sum(1 for item in changes if item["fields"]),
                    "conflicts": len(conflicts), "partner_only": len(partner.rows) - len(common),
                    "partial_bls": len(partial)},
    }


def _source(item: TosFile) -> dict:
    return {"path": str(item.path), "sha256": item.sha256, "carrier": item.carrier,
            "source_name": item.source_name, "session_id": text_value(item.properties.get("session_id")),
            "source_sha256": text_value(item.properties.get("source_sha256"))}


def write_bl_change(vessel: TosFile, partner: TosFile, plan: dict, path: str | Path, *,
                    overwrite: bool = False) -> dict:
    """Write the changed vessel file and its JSON trace; sources stay untouched."""
    target = Path(path).resolve()
    trace = target.with_suffix(".bl_change.json")
    if target.suffix.lower() != ".xlsx":
        raise ValueError("File xuất phải có đuôi .xlsx.")
    if target in (vessel.path, partner.path):
        raise ValueError("Chọn tên khác với hai file nguồn.")
    if not overwrite and (target.exists() or trace.exists()):
        raise FileExistsError("File Excel hoặc file truy vết cùng tên đã tồn tại; chọn tên mới hoặc xác nhận ghi đè.")
    for item in (vessel, partner):
        if source_sha256(item.path) != item.sha256:
            raise ValueError(f"{item.path.name} đã thay đổi sau khi đối chiếu. Chọn lại file để đối chiếu lần nữa.")
    column = {name: position + 1 for position, name in enumerate(TOS_COLUMNS)}
    book = openpyxl.load_workbook(vessel.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        sheet = book.worksheets[0]
        change_fill = PatternFill(fill_type="solid", start_color=CHANGE_FILL, end_color=CHANGE_FILL)
        conflict_fill = PatternFill(fill_type="solid", start_color=CONFLICT_FILL, end_color=CONFLICT_FILL)
        for item in plan["changes"]:
            for name, value in item["fields"].items():
                cell = sheet.cell(item["vessel_row"], column[name])
                new = value["new"]
                cell.value = float(new) if name in NUMBER_FIELDS and isinstance(new, (int, float)) else text_value(new)
                if name not in NUMBER_FIELDS:
                    cell.number_format = "@"
                cell.fill = change_fill
        for item in plan["conflicts"]:
            sheet.cell(vessel.rows[item["container"]]["row"], column[item["field"]]).fill = conflict_fill
        props = book.custom_doc_props
        for name, value in {"bl_change_partner_sha256": partner.sha256, "bl_change_vessel_sha256": vessel.sha256,
                            "bl_change_partner_source": partner.source_name or partner.path.name,
                            "bl_change_app_version": __version__}.items():
            for existing in [p for p in props.props if p.name == name]:
                props.props.remove(existing)
            props.append(StringProperty(name=name, value=str(value)))
        fd, excel_temp = tempfile.mkstemp(prefix=".bl_change_", suffix=".xlsx", dir=target.parent)
        os.close(fd)
        staged.append(Path(excel_temp))
        book.save(excel_temp)
    finally:
        book.close()
    try:
        record = {"schemaVersion": TRACE_SCHEMA, "createdAt": datetime.now(timezone.utc).isoformat(),
                  "appVersion": __version__, "vessel": _source(vessel), "partner": _source(partner),
                  "rules": {"matchedBy": "Số Container", "changedFields": list(CHANGED_FIELDS),
                            "comparedFields": list(COMPARED_FIELDS), "blankNeverOverwrites": True,
                            "conflictsKeep": "vessel"},
                  "output": {"path": str(target), "sha256": source_sha256(staged[0])}, **plan}
        fd, trace_temp = tempfile.mkstemp(prefix=".bl_change_", suffix=".json", dir=target.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, default=str)
        staged.append(Path(trace_temp))
        os.replace(staged[0], target)
        os.replace(staged[1], trace)
    finally:
        for item in staged:
            item.unlink(missing_ok=True)
    return {"excel": target, "trace": trace}
