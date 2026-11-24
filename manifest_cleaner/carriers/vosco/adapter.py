"""Headless VOSCO import adapter.

The input grammar and port mappings come from the operational VOSCO app.
No carrier detection or vessel-name routing is performed here.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path
import re

import pandas as pd

from ...common import (
    is_explicit_empty, issue, normalize_text, parse_weight, read_workbook,
    text_value,
)
from .mappings import (
    SAFETY_MARGIN_TONS, SIZE_TO_VTOS, TANK_TARE_WEIGHTS_TONS, TARE_WEIGHTS_TONS,
)
from .parsers import get_vtos_size, is_valid_bl, parse_container_line
from .processors import (
    CONTAINER_HEADER_PATTERNS, clean_consignee_name, clean_description_text, classify_description_lines,
    determine_fe, get_cargo_type, match_descriptions_with_confidence,
    parse_cargo_items_with_qty, refine_description_column, validate_container_info_description,
    validate_tank_weight_warning,
)

# Zero-based positions of the established VOSCO worksheet layout.
COL_MARKER, COL_PARTY, COL_BL, COL_CONTAINER, COL_DESCRIPTION, COL_WEIGHT = (
    0, 1, 5, 10, 14, 18
)
PARTY_FIELDS = {"(S)": "Shipper", "(C)": "Consignee", "(N)": "Notify"}
BL_HEADERS = {
    "B/L", "BL", "B/L NO", "BL NO", "BILL OF LADING",
    "BILL OF LADING NO", "B/L NUMBER", "BL NUMBER", "SO BL", "SO B/L",
}
WEIGHT_HEADERS = {"WEIGHT", "GROSS WEIGHT", "TRONG LUONG", "KGS", "TONS"}


def _cell(row, column):
    return text_value(row[column]) if column < len(row) else ""


def _bl_heading(value):
    return normalize_text(value).rstrip(".: ") in BL_HEADERS


def _is_container_header(line):
    value = line.strip().upper()
    return (
        value in CONTAINER_HEADER_PATTERNS
        or value in {"CONTAINER", "CONTAINER NO", "CONTAINER NO.", "CONTAINER/SEAL NO."}
        or ("CONTAINER" in value and not re.match(r"^[A-Z]{4}\d", value))
        or bool(re.match(r"^(?:TOTAL|TONG)\b", normalize_text(value)))
        or bool(re.match(r"^\(?\d+\)?\s*[xX]\s*\d{2}", value))
    )


def _parsed_lines(value):
    """Keep each original container line alongside its parsed record."""
    output = []
    for number, line in enumerate(value.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or _is_container_header(stripped):
            continue
        parsed = parse_container_line(stripped)
        output.append((number, stripped, parsed))
    return output


def _weight_slots(value, settings):
    """Invalid internal slots remain in position; totals are never assigned."""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        # Numeric Excel cells are already numbers. The textual locale setting
        # must not turn the native value 1.234 into 1234.
        return [(text_value(value), parse_weight(
            value, default_unit=settings.get("default_weight_unit", "TONS"),
            number_format=settings.get("number_format", "legacy"),
        ))]
    lines = str(value).strip().splitlines() if str(value).strip() else []
    slots = []
    for line in lines:
        normalized = normalize_text(line)
        if normalized.rstrip(".: ") in WEIGHT_HEADERS:
            continue
        if re.match(r"^(?:TOTAL|TONG)(?:\s|:|$)", normalized):
            continue
        slots.append((line, parse_weight(
            line,
            default_unit=settings.get("default_weight_unit", "TONS"),
            number_format=settings.get("number_format", "legacy"),
        )))
    return slots


def _scan_contexts(rows, sheet, first_data_index=0):
    """Find BL blocks and party markers without assuming sixteen header rows.

    A new, non-header BL value that does not match the VOSCO grammar terminates
    the preceding BL. Its containers remain visible and require correction.
    """
    contexts, parties = [], {}
    current_bl = current_raw_bl = current_group = ""
    collecting = None
    for source_row, row in enumerate(rows, start=1):
        if source_row <= first_data_index:
            contexts.append({"BL_No": "", "raw_bl": "", "Master_BL_Group_ID": ""})
            continue
        raw_bl = _cell(row, COL_BL)
        container_cell = _cell(row, COL_CONTAINER)
        marker = _cell(row, COL_MARKER).upper()
        if raw_bl and not _bl_heading(raw_bl):
            if is_valid_bl(raw_bl):
                current_bl = raw_bl
                current_raw_bl = raw_bl
                current_group = f"VOSCO:{sheet}:{raw_bl}"
                collecting = None
            elif current_group or container_cell or marker in PARTY_FIELDS:
                current_bl = ""
                current_raw_bl = raw_bl
                current_group = f"VOSCO:{sheet}:unparsed-bl:{source_row}"
                collecting = None
        if not current_group and (container_cell or marker in PARTY_FIELDS):
            current_group = f"VOSCO:{sheet}:missing-bl:{source_row}"
        if current_group:
            block = parties.setdefault(current_group, {k: [] for k in PARTY_FIELDS.values()})
            party_text = _cell(row, COL_PARTY)
            if marker in PARTY_FIELDS:
                collecting = PARTY_FIELDS[marker]
                # Preserve the original last-declaration behavior within a BL.
                block[collecting] = [party_text] if party_text else []
            elif marker:
                collecting = None
            elif collecting and party_text and not any(
                p for _, _, p in _parsed_lines(container_cell)
            ):
                block[collecting].append(party_text)
            elif any(p for _, _, p in _parsed_lines(container_cell)):
                collecting = None
        contexts.append({
            "BL_No": current_bl,
            "raw_bl": current_raw_bl,
            "Master_BL_Group_ID": current_group,
        })
    return contexts, parties


def is_supported_size_type(size_type, settings=None):
    """Only the operational source-to-port mappings are accepted."""
    return text_value(size_type).upper() in SIZE_TO_VTOS


def refresh_derived_fields(record, settings=None):
    """Recompute port codes after a manual edit; never overwrite F/E or cargo."""
    result = dict(record)
    supported = is_supported_size_type(result.get("Size_Type"), settings)
    result["VTOS_Size"] = get_vtos_size(result.get("Size_Type")) if supported else None
    result["Cargo_Type"] = (
        get_cargo_type(result.get("Size_Type", ""), result.get("FE_Status", ""))
        if supported and result.get("FE_Status") in {"F", "E"} else ""
    )
    if not result.get("Operator"):
        result["Operator"] = "SVC" if result.get("raw", {}).get("is_soc") else "VOC"
    return result


def parse_manifest(path, *, settings=None, progress=None):
    """Read one VOSCO file into records, issues and source metadata."""
    settings = dict(settings or {})
    weight_kind = settings.get("weight_kind", "unknown")
    if weight_kind not in ("gross", "cargo", "unknown"):
        raise ValueError("weight_kind của VOSCO chỉ nhận gross, cargo hoặc unknown.")
    source_file = Path(path).name
    sheets = read_workbook(path)
    issues, records, source_fragments = [], [], []
    metadata = {
        "carrier": "VOSCO", "adapter_version": "1.1.0", "profile_version": "vosco-1.1.0",
        "source_file": source_file,
        "source_baseline": "e5a78dd0444349990b08992ceb57758aa074dcb8",
        "available_sheets": [name for name, _ in sheets],
        "layout": "VOSCO A/B/F/K/O/S; header rows detected from content",
        "weight_kind": settings.get("weight_kind", "unknown"),
    }
    if not sheets:
        return {"records": [], "issues": [issue(
            "NO_SHEETS", "Không tìm thấy sheet trong file Excel.", severity="error"
        )], "metadata": metadata}

    selected_name = settings.get("sheet_name")
    if selected_name:
        selected = [entry for entry in sheets if entry[0] == selected_name]
        if not selected:
            return {"records": [], "issues": [issue(
                "SHEET_NOT_FOUND", f"Không tìm thấy sheet đã chọn: {selected_name}.",
                severity="error"
            )], "metadata": metadata}
        sheet, frame = selected[0]
    else:
        # Keep the existing operational contract: use the first sheet.
        sheet, frame = sheets[0]
    metadata["selected_sheet"] = sheet
    metadata["source_sheet"] = sheet
    for other_name, other_frame in sheets:
        if other_name == sheet:
            continue
        if any(
            parsed for row in other_frame.itertuples(index=False, name=None)
            for _, _, parsed in _parsed_lines(_cell(row, COL_CONTAINER))
        ):
            issues.append(issue(
                "ADDITIONAL_MANIFEST_SHEET",
                f"Sheet '{other_name}' cũng có container. Đang xử lý sheet '{sheet}' theo cấu hình VOSCO; cần kiểm tra phạm vi file.",
                source_sheet=other_name,
            ))

    rows = list(frame.itertuples(index=False, name=None))
    first_data_index = next((index for index, row in enumerate(rows)
                             if is_valid_bl(_cell(row, COL_BL))
                             or _cell(row, COL_MARKER).upper() in PARTY_FIELDS
                             or any(parsed or re.match(r"^[A-Z]{3,4}[\s-]*\d", raw, re.IGNORECASE)
                                    for _, raw, parsed in _parsed_lines(_cell(row, COL_CONTAINER)))),
                            len(rows))
    contexts, parties = _scan_contexts(rows, sheet, first_data_index)
    candidate_count = 0
    for source_row, (row, context) in enumerate(zip(rows, contexts), start=1):
        if source_row <= first_data_index:
            continue
        container_cell = _cell(row, COL_CONTAINER)
        description_cell = _cell(row, COL_DESCRIPTION)
        weight_cell = _cell(row, COL_WEIGHT)
        native_weight_value = row[COL_WEIGHT] if COL_WEIGHT < len(row) else ""
        lines = _parsed_lines(container_cell)
        valid = []
        for number, raw_line, parsed in lines:
            if parsed is None:
                # Keep an editable placeholder in the original position. Do not
                # silently remove the candidate or shift subsequent weights.
                candidate = re.split(r"[\s/]", raw_line, maxsplit=1)[0]
                explicit_soc = bool(re.search(r"-S\s*$", raw_line, re.IGNORECASE))
                parsed = {"no": candidate, "seal": None, "type": None,
                          "operator": "SVC" if explicit_soc else "VOC",
                          "is_soc": explicit_soc, "_unparsed": True}
            valid.append((number, raw_line, parsed))
        if not valid:
            continue
        for evidence in classify_description_lines(description_cell):
            if evidence["kind"] not in {"cargo", "blank"}:
                source_fragments.append({
                    "source_sheet": sheet, "source_row": source_row,
                    "source_column": COL_DESCRIPTION + 1, "source_line": evidence["source_line"],
                    "text": evidence["text"], "status": "corroborating" if evidence["kind"] == "quantity" else "ignored",
                    "reason": "description_metadata_" + evidence["kind"],
                })
        candidate_count += len(valid)
        weights = _weight_slots(native_weight_value, settings)
        association_ok = len(weights) == len(valid)
        assigned_weights = [value for _, value in weights] if association_ok else [None] * len(valid)
        assigned_raw_weights = [raw for raw, _ in weights] if association_ok else [""] * len(valid)
        first_description = clean_description_text(description_cell)
        fe_statuses = [
            determine_fe(first_description, weight, parsed.get("type"), weight_kind=weight_kind)
            for (_, _, parsed), weight in zip(valid, assigned_weights)
        ]
        matches = match_descriptions_with_confidence(
            [parsed for _, _, parsed in valid],
            "\n".join(raw for _, raw, _ in valid), description_cell,
            fe_statuses, bl_no=context["BL_No"],
        )
        cargo_quantities = parse_cargo_items_with_qty(description_cell)
        declared_types = Counter()
        for _, count, container_type in cargo_quantities:
            declared_types[container_type] += count
        actual_types = Counter(parsed.get("type") for _, _, parsed in valid)
        quantity_mismatch = bool(cargo_quantities and declared_types != actual_types)
        party_block = parties.get(context["Master_BL_Group_ID"], {})
        party_values = {key: "\n".join(party_block.get(key, [])).strip()
                        for key in PARTY_FIELDS.values()}

        for index, ((line_number, raw_line, parsed), weight, raw_weight, match) in enumerate(
            zip(valid, assigned_weights, assigned_raw_weights, matches), start=1
        ):
            record_id = f"VOSCO:{sheet}:{source_row}:{line_number}"
            record_issues = []

            def add(code, message, severity="warning", field=None, resolution_fields=None):
                entry = issue(code, message, severity=severity, record_id=record_id,
                              field=field, source_row=source_row, source_sheet=sheet)
                if resolution_fields:
                    entry["resolution_fields"] = list(resolution_fields)
                record_issues.append(entry)
                issues.append(entry)

            if parsed.get("_unparsed"):
                add("CONTAINER_UNPARSED",
                    f"Chưa đọc được dòng container {line_number}: {raw_line}. Điền/sửa thông tin theo bản gốc hoặc loại dòng có lý do.",
                    "error", "Container_No")
            if not context["BL_No"]:
                add("INVALID_OR_MISSING_BL",
                    f"Số BL thiếu hoặc không đúng mẫu VOSCO: {context['raw_bl'] or '(trống)'}. Container được giữ lại để sửa.",
                    "error", "BL_No")
            if not association_ok:
                add("WEIGHT_ASSOCIATION_AMBIGUOUS",
                    f"Có {len(valid)} container nhưng {len(weights)} dòng trọng lượng. Không tự chia hoặc lặp trọng lượng; cần nhập trọng lượng từng container.",
                    "error", "Weight_Value")
            elif weight is None:
                add("WEIGHT_INVALID", f"Trọng lượng thiếu hoặc không đọc được tại đúng vị trí: {raw_weight or '(trống)' }.",
                    "error", "Weight_Value")
            if not parsed.get("type"):
                add("SIZE_TYPE_MISSING", "Không xác định được kích cỡ container từ dữ liệu gốc.", "error", "Size_Type")
            if match.warning:
                add("DESCRIPTION_REVIEW", match.warning, field="Description")
            if quantity_mismatch:
                add("DESCRIPTION_QUANTITY_MISMATCH",
                    "Số lượng/kích cỡ trong mô tả hàng không khớp danh sách container; cần đối chiếu cách gán hàng.",
                    field="Description", resolution_fields=["Description", "Size_Type"])
            raw_description = match.description
            description = normalize_text(raw_description)
            description_warning, extracted = validate_container_info_description(description)
            if description_warning:
                add("DESCRIPTION_PACKING_TEXT", description_warning, field="Description")
                if extracted:
                    description = extracted
            fe_status = ("" if parsed.get("_unparsed") else
                         determine_fe(raw_description, weight, parsed.get("type"), weight_kind=weight_kind))
            type_value = str(parsed.get("type") or "").upper()
            tare = TANK_TARE_WEIGHTS_TONS.get(type_value, TARE_WEIGHTS_TONS.get(type_value[:2]))
            if is_explicit_empty(raw_description) and weight and weight_kind == "cargo" and weight["value"] > 0:
                add("EMPTY_CARGO_WEIGHT_CONFLICT",
                    "Mô tả ghi EMPTY nhưng trọng lượng hàng lớn hơn 0; cần xác nhận F/E và trọng lượng từ nguồn.",
                    "error", resolution_fields=["FE_Status", "Weight_Value"])
            elif is_explicit_empty(raw_description) and weight and weight_kind != "cargo" and tare is not None and weight["value"] > tare + SAFETY_MARGIN_TONS:
                add("EMPTY_WEIGHT_CONFLICT",
                    "Mô tả ghi EMPTY nhưng trọng lượng cao hơn ngưỡng suy luận. Giữ E theo khai báo; cần đối chiếu trọng lượng gốc.",
                    field="FE_Status")
            tank_warning = validate_tank_weight_warning(
                type_value, weight.get("value") if weight else None, fe_status
            ) if weight_kind != "cargo" else None
            if tank_warning:
                add("TANK_WEIGHT_REVIEW", tank_warning, field="FE_Status")
            if (not parsed.get("_unparsed") and weight
                    and settings.get("weight_kind", "unknown") == "unknown"
                    and not is_explicit_empty(raw_description)):
                add("FE_WEIGHT_KIND_UNCONFIRMED",
                    "F/E đang theo quy tắc suy luận trọng lượng của mẫu VOSCO. Chưa xác nhận trọng lượng nguồn là hàng hay tổng; cần đối chiếu F/E.",
                    field="FE_Status")
            seal = parsed.get("seal")
            if seal and not (seal.isdigit() and len(seal) == 6):
                add("VOSCO_SEAL_FORMAT", "Số niêm chì khác quy tắc 6 chữ số của mẫu VOSCO; cần đối chiếu.", field="Seal_No")
            consignee = party_values.get("Consignee", "")
            cleaned_consignee = clean_consignee_name(consignee)
            if not cleaned_consignee:
                add("CONSIGNEE_MISSING", "Thiếu tên chủ hàng; container vẫn được giữ lại.",
                    field="Cleaned_Consignee_Name_For_Output")
            notify = party_values.get("Notify", "")
            if "SAME AS CONSIGNEE" in notify.upper():
                notify = cleaned_consignee or consignee
            record = {
                "record_id": record_id, "BL_No": context["BL_No"],
                "Master_BL_Group_ID": context["Master_BL_Group_ID"],
                "Container_No": parsed["no"], "Seal_No": seal or "",
                "Size_Type": parsed.get("type") or "", "Operator": parsed.get("operator"),
                "FE_Status": fe_status, "Weight_Value": weight["value"] if weight else None,
                "Weight_Unit": "TONS" if weight else None,
                "Weight_Kind": settings.get("weight_kind", "unknown"),
                "Description": description,
                "Shipper": party_values.get("Shipper", ""), "Consignee": consignee,
                "Notify": notify, "Cleaned_Consignee_Name_For_Output": cleaned_consignee,
                "Confidence": min(match.confidence, 50) if quantity_mismatch or parsed.get("_unparsed") else match.confidence,
                "Warning": " | ".join(entry["message"] for entry in record_issues),
                "source_file": source_file, "source_sheet": sheet, "source_row": source_row,
                "raw": {
                    "BL_No": context["raw_bl"], "container_cell": container_cell,
                    "container_line": raw_line, "container_line_number": line_number,
                    "weight_cell": weight_cell, "weight_line": raw_weight,
                    "weight_cell_value": native_weight_value,
                    "weight_source_unit": weight.get("source_unit") if weight else None,
                    "description_cell": description_cell, "matched_description": raw_description,
                    "description_line_evidence": classify_description_lines(description_cell),
                    "description_source_lines": list(match.source_lines),
                    "description_match_type": match.match_type,
                    "Size_Type": parsed.get("type"), "is_soc": parsed.get("is_soc", False),
                    "party_values": dict(party_values),
                    "row_values": [text_value(value) for value in row],
                },
                "rules": ["vosco.fixed-column-blocks", "vosco.party-markers",
                          "vosco.operator-soc-coc", "vosco.port-mappings",
                          f"vosco.description.{match.match_type.lower()}",
                          "weight.normalized-tonnes" if weight else "weight.unresolved",
                          "fe.explicit-empty" if is_explicit_empty(raw_description) else
                          "fe.cargo-mass-no-tare" if weight_kind == "cargo" else "fe.vosco-legacy-inference"],
            }
            records.append(refresh_derived_fields(record, settings))
            unresolved = parsed.get("_unparsed") or any(entry["severity"] == "error" for entry in record_issues)
            source_fragments.append({
                "source_sheet": sheet, "source_row": source_row,
                "source_column": COL_CONTAINER + 1, "source_line": line_number,
                "text": raw_line, "record_id": record_id,
                "status": "unresolved" if unresolved else "parsed",
                "reason": "unparsed" if parsed.get("_unparsed") else "container_record_requires_review" if unresolved else "container_record",
            })

    if records:
        # This is the last transformation used by the operational VOSCO export.
        # It does not replace every E description with EMPTY.
        refined = refine_description_column(pd.DataFrame({
            "Hàng hóa": [record["Description"] for record in records],
            "Kích cỡ": [record["Size_Type"] for record in records],
        }))
        for record, description in zip(records, refined["Hàng hóa"]):
            record["raw"]["description_before_final_refinement"] = record["Description"]
            record["Description"] = description
            record["rules"].append("vosco.final-description-refinement")
    else:
        # Show evidence when a container occurs outside the expected column.
        misplaced = []
        for row_number, row in enumerate(rows, start=1):
            for column, value in enumerate(row, start=1):
                if column == COL_CONTAINER + 1:
                    continue
                if any(parsed for _, _, parsed in _parsed_lines(text_value(value))):
                    misplaced.append(f"dòng {row_number}, cột {column}")
        detail = (" Có mã container ở " + "; ".join(misplaced[:5]) + ".") if misplaced else ""
        issues.append(issue(
            "VOSCO_LAYOUT_NOT_RECOGNIZED",
            "Không tìm thấy container trong cột K của mẫu VOSCO." + detail + " Cần chọn đúng hãng/mẫu hoặc kiểm tra bố cục file.",
            severity="error", source_sheet=sheet,
        ))
    metadata.update({"record_count": len(records), "detected_container_count": candidate_count,
                     "first_container_row": min((r["source_row"] for r in records), default=None),
                     "source_fragments": source_fragments,
                     "coverage_scope": "Candidate container lines in column K, excluded non-cargo description lines and quantity evidence in column O on candidate rows; parse-time snapshot, not a whole-workbook accuracy measure.",
                     "coverage": {"source_fragments": len(source_fragments),
                                  **{f"{status}_fragments": sum(item["status"] == status for item in source_fragments)
                                     for status in ("parsed", "unresolved", "ignored", "corroborating")}}})
    return {"records": records, "issues": issues, "metadata": metadata}
