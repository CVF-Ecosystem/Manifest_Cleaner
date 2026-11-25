"""VIMC adapter with source-preserving records and explicit review issues.

Derived from Manifest-Cleaner_VIMC at 03e0d34e3fe4a27d8d2ce0d54d96ea9275370436.
No GUI, networking, vessel lookup or filename-based parser selection is used.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re

from ...common import is_explicit_empty, issue, normalize_text, parse_weight, read_workbook, text_value
from .. import CARRIER_PROFILES
from ..vosco.mappings import TANK_TARE_WEIGHTS_TONS, TARE_WEIGHTS_TONS
from .mappings import CARGO_TYPE_MAPPING, SIZE_TO_ISO, SIZE_TO_VTOS
from .parsers import (
    CONTAINER_CANDIDATE, STOP_KEYWORDS_PATTERN, is_valid_container,
    parse_marks_container, parse_structured_line, split_container_segments, split_detail_segments,
)

SOURCE_COMMIT = "03e0d34e3fe4a27d8d2ce0d54d96ea9275370436"
PROFILE_VERSION = "vimc-1.3.3"
_BL_MARKER = re.compile(r"\bB\s*/?\s*L\s*NO\.?\s*:", re.I)
_PARTY_MARKER = re.compile(r"^\s*([123])\s*[).]\s*(.*)$")
_TRAILING_OWNER_TOTAL = re.compile(
    r"TOTAL\s*:\s*(\d{1,6})\s*[X×]\s*((?:20|40|45)'?[A-Z]{2,4})\s+(SOC|COC)\s+(LADEN|EMPTY)"
)
_EMPTY_TOTAL_ITEM = r"(\d{1,6})\s*[X×]\s*((?:20|40|45)'?[A-Z0-9]{2,4})"
_EMPTY_MARKS_TOTAL = re.compile(
    rf"TOTAL\s*:\s*(?P<sizes>{_EMPTY_TOTAL_ITEM}(?:\s*[,;+&]\s*{_EMPTY_TOTAL_ITEM})*)"
    r"\s*,?\s*(?P<owner>SOC|COC)\s+(?:RF\s+)?EMPTY"
)
_COMPACT_IDENTIFIER = re.compile(r"[A-Z]{4}\d{4,6}")
_COMPACT_MARK = re.compile(r"(?P<identifier>[A-Z]{4}[0-9]{4,6})[ \t]*/[ \t]*(?P<size>[A-Z0-9']{2,5})")
_WEIGHTED_LAYOUTS = {"weight_first_tons", "description_first_kg"}
_ROLES = {"1": "Shipper", "2": "Consignee", "3": "Notify"}
_PORT_TYPE_ALIASES = {"22R0": "20RF", "20FL": "20FR", "40FL": "40FR", "45RH": "45RF"}


def _maps(settings=None):
    settings = settings or {}
    def merged(base, key):
        result = dict(base)
        custom = settings.get(key, {})
        if isinstance(custom, dict):
            result.update({str(k).strip().upper(): str(v).strip().upper() for k, v in custom.items()})
        return result
    return merged(SIZE_TO_ISO, "size_to_iso"), merged(SIZE_TO_VTOS, "size_to_vtos"), merged(CARGO_TYPE_MAPPING, "cargo_type_mapping")


def is_supported_size_type(size_type, settings=None):
    physical_map, port_map, _ = _maps(settings)
    value = text_value(size_type).upper().replace("'", "")
    known = set(physical_map) | set(physical_map.values()) | set(port_map) | set(port_map.values())
    return bool(value and value in {item.replace("'", "") for item in known})


def reference_tare(record, settings=None):
    size = text_value(record.get("Size_Type")).upper().replace("'", "")
    physical_type = text_value(record.get("Physical_ISO_Size")).upper()
    iso_length = re.fullmatch(r"([24L])\d[A-Z]\d", physical_type or size)
    length = {"2": "20", "4": "40", "L": "45"}[iso_length[1]] if iso_length else size[:2]
    if size.endswith("TK") or physical_type[2:3] == "T":
        return TANK_TARE_WEIGHTS_TONS.get(f"{length}TK")
    return TARE_WEIGHTS_TONS.get(length)


def _clean_party_name(value):
    text = text_value(value).split("\n")[0].strip()
    text = re.sub(r"^[123]\)\s*", "", text)
    match = STOP_KEYWORDS_PATTERN.search(text)
    if match:
        text = text[:match.start()].strip()
    return text.rstrip(";,/\\- ")


def refresh_derived_fields(record, settings=None):
    """Refresh export mappings after an edit without changing source meaning.

    Size_Type remains the physical/source type. VTOS_Size is the carrier's
    legacy port mapping. F/E and Description are never inferred or overwritten.
    """
    result = dict(record)
    physical_map, port_map, cargo_map = _maps(settings)
    source_size = text_value(result.get("Size_Type")).upper()
    lookup_size = source_size.replace("'", "")
    cargo_lookup = _PORT_TYPE_ALIASES.get(lookup_size, lookup_size)
    physical_iso = physical_map.get(lookup_size, physical_map.get(source_size, ""))
    if not physical_iso and lookup_size in _PORT_TYPE_ALIASES:
        physical_iso = lookup_size if re.fullmatch(r"[24L]\d[A-Z]\d", lookup_size) else physical_map.get(cargo_lookup, "")
    result["ISO_Size"] = physical_iso
    result["Physical_ISO_Size"] = physical_iso
    result["VTOS_Size"] = port_map.get(source_size, port_map.get(lookup_size, source_size))
    base_cargo = cargo_map.get(lookup_size) or cargo_map.get(cargo_lookup) or cargo_map.get(physical_iso)
    if not source_size:
        result["Cargo_Type"] = "UNKNOWN"
    else:
        base_cargo = base_cargo or "GENERAL"
        result["Cargo_Type"] = ("EMPTY" if base_cargo == "GENERAL" else f"EMPTY {base_cargo}") if result.get("FE_Status") == "E" else base_cargo
    if not result.get("Operator"):
        result["Operator"] = CARRIER_PROFILES["VIMC"].operator()
    return result


def _header_columns(values):
    columns = {}
    for index, value in enumerate(values):
        cell = normalize_text(value).lower()
        if "marks" in cell:
            columns.setdefault("marks", index)
        if any(word in cell for word in ("description", "discription", "packages", "mo ta hang")):
            columns.setdefault("description", index)
        if any(word in cell for word in ("shipper", "consignee", "particulars", "nguoi gui", "chu hang")):
            columns.setdefault("party", index)
    return columns


def _find_header(frame):
    for index in range(min(20, len(frame))):
        columns = _header_columns(frame.iloc[index].tolist())
        if len(columns) >= 2 and len(set(columns.values())) >= 2:
            return index, columns
    return None, {}


def _status(text):
    """Read explicit container-status phrases; goods containing EMPTY are goods."""
    cleaned = normalize_text(text).strip(" ;,.:")
    if is_explicit_empty(cleaned) or re.fullmatch(r"(?:SOC|COC) RF EMPTY", cleaned):
        return "E"
    # Some existing manifests put the quantity/type before the status.
    prefix_removed = re.sub(r"^\(?\d+\)?\s*[X×]\s*(?:20|40|45)'?\s*[A-Z0-9]+\s+", "", cleaned)
    if is_explicit_empty(prefix_removed):
        return "E"
    full = re.sub(r"\s*\(?\d+\)?\s*[X×]\s*(?:20|40|45)'?\s*[A-Z0-9]+\s*$", "", prefix_removed)
    if re.fullmatch(r"(?:(?:SOC|COC)\s+)?(?:LADEN|FULL|CO HANG)(?:\s+(?:SOC|COC))?", full):
        return "F"
    return None


def _owner(text):
    words = set(re.findall(r"\b(?:SOC|COC)\b", normalize_text(text)))
    return next(iter(words)) if len(words) == 1 else None


def _new_group(bl_no="", source_row=None):
    return {"BL_No": bl_no, "start_row": source_row, "Shipper": [], "Consignee": [],
            "Notify": [], "party_role": None, "party_evidence": [],
            "description": [], "marks": [], "other": [], "bl_evidence": []}


def _extract_bl(values):
    first = text_value(values[0]) if values else ""
    match = _BL_MARKER.search(first)
    if not match:
        return None, []
    inline = first[match.end():].strip().split()
    inline = inline[0] if inline else ""
    # Keep the existing third-column contract, with an inline fallback.
    third = text_value(values[2]).split()[0] if len(values) > 2 and text_value(values[2]) else ""
    evidence = [{"position": "third_column", "value": third}, {"position": "inline", "value": inline}]
    return third or inline, evidence


def _read_party(group, text, row=None, col=None, *, allow_continuation=True):
    if not text:
        return
    if not allow_continuation and not any(_PARTY_MARKER.match(line) for line in text.splitlines()):
        group["party_role"] = None
        return
    for line_number, line in enumerate(text.splitlines(), 1):
        match = _PARTY_MARKER.match(line)
        if match:
            group["party_role"] = _ROLES[match.group(1)]
            line = match.group(2).strip()
        elif split_container_segments(line) or _BL_MARKER.search(line) or re.match(r"^\s*(?:TOTAL|TONG)\b", normalize_text(line)):
            group["party_role"] = None
            continue
        elif group["party_role"]:
            line = line.strip()
        if group["party_role"] and line:
            group[group["party_role"]].append(line)
            group["party_evidence"].append({"role": group["party_role"], "text": line,
                "source_row": row, "source_column": col + 1 if col is not None else None,
                "source_line": line_number})


def _read_party_row(group, values, row, party_col, *, allow_continuation):
    party_text = text_value(values[party_col]) if party_col < len(values) else ""
    if not party_text and party_col != 0 and group["start_row"] == row - 1:
        # The heading may be anchored in B while the first party block under
        # a B/L is anchored in A. Accept only explicit role-marked text here.
        fallback = text_value(values[0])
        markers = (_PARTY_MARKER.match(line) for line in fallback.splitlines())
        if any(match and match[1] == "2" for match in markers):
            _read_party(group, fallback, row, 0, allow_continuation=False)
            group["party_role"] = None
            return
    _read_party(group, party_text, row, party_col, allow_continuation=allow_continuation)


def _entries(value, row, col):
    return [{"text": line.strip(), "row": row, "col": col, "line": line_index}
            for line_index, line in enumerate(text_value(value).splitlines(), 1) if line.strip()]


def _add_issue(issues, code, message, *, record=None, severity="warning", field=None, sheet=None, row=None):
    issues.append(issue(code, message, severity=severity,
                        record_id=record.get("record_id") if record else None, field=field,
                        source_row=record.get("source_row") if record else row,
                        source_sheet=record.get("source_sheet") if record else sheet))


def _source_status_markers(group):
    markers = []
    for entry in group["description"]:
        if split_container_segments(entry["text"]) or _TRAILING_OWNER_TOTAL.fullmatch(normalize_text(entry["text"])):
            continue
        status, owner = _status(entry["text"]), _owner(entry["text"])
        if status or owner:
            markers.append({**entry, "status": status, "owner": owner})
    return markers


def _context(entry, markers, *, marks=False):
    # A later EMPTY heading must not retroactively change earlier loaded rows.
    status, owner = None, None
    prior = [marker for marker in markers if marker["row"] < entry["row"] or
             (marker["row"] == entry["row"] and (marks or marker["line"] < entry["line"]))]
    if marks:
        # Marks within the same cell cannot be assigned to multiple simultaneous
        # group-status headings by guessing their textual order.
        same_row = [marker for marker in prior if marker["row"] == entry["row"]]
        if len({marker["status"] for marker in same_row if marker["status"]}) > 1:
            return None, owner
    for marker in prior:
        status = marker["status"] or status
        owner = marker["owner"] or owner
    return status, owner


def _empty_marks_total(group, marks_by_entry, markers, settings):
    """Use a B/L-wide EMPTY total only when the entire MARKS list verifies it."""
    if not group["BL_No"]:
        return None
    totals = [(entry, _EMPTY_MARKS_TOTAL.fullmatch(normalize_text(entry["text"])))
              for entry in group["description"]]
    totals = [(entry, match) for entry, match in totals if match]
    if len(totals) != 1:
        return None
    entry, match = totals[0]
    owner = match["owner"]
    if any(marker["status"] == "F" or marker["owner"] not in (None, owner) for marker in markers):
        return None
    marks = [mark for _, found in marks_by_entry for mark in found]
    if (not marks or len(marks) != len({mark["container_no"] for mark in marks})
            or any(not is_valid_container(mark["container_no"]) or not is_supported_size_type(mark["size_type"], settings)
                   for mark in marks)):
        return None
    declared = Counter()
    for quantity, size in re.findall(_EMPTY_TOTAL_ITEM, match["sizes"]):
        declared[size.replace("'", "")] += int(quantity)
    actual = Counter(mark["size_type"].replace("'", "") for mark in marks)
    if dict(declared) != dict(actual):
        return None
    return {"text": entry["text"], "source_row": entry["row"], "source_column": entry["col"] + 1,
            "source_line": entry["line"], "owner": owner, "declared_sizes": dict(declared)}


def _base_record(group, entry, segment_index, source_file, sheet, parsed, status, owner, settings):
    shipper = "\n".join(group["Shipper"]).strip()
    consignee = "\n".join(group["Consignee"]).strip()
    notify = "\n".join(group["Notify"]).strip()
    if normalize_text(notify) in {"SAME AS CONSIGNEE", "NHU NGUOI NHAN HANG"}:
        notify = consignee
    weight_result = None
    if parsed.get("weight_raw") is not None:
        weight_result = parse_weight(parsed["weight_raw"], default_unit=parsed.get("weight_unit") or "TONS",
                                     number_format=settings.get("number_format", "legacy"))
    context_status = status
    own_status = _status(parsed.get("description", ""))
    own_owner = _owner(parsed.get("description", ""))
    status = own_status or status
    description = normalize_text(parsed.get("description", ""))
    if status is None and description and parsed.get("layout") not in {"unparsed", "ambiguous", "marks_incomplete"}:
        status = "F"  # Known detail row with goods, matching existing default; no tare threshold.
    status_source = "explicit_row" if own_status else "group_heading" if context_status else "default_known_detail" if status else "unknown"
    record = {
        "record_id": f"VIMC:{sheet}:{entry['row']}:{entry['col']}:{entry['line']}:{segment_index}",
        "BL_No": group["BL_No"], "Master_BL_Group_ID": group["BL_No"],
        "Container_No": parsed.get("container_no", ""), "Seal_No": parsed.get("seal_no"),
        "Size_Type": parsed.get("size_type") or "", "VTOS_Size": "",
        "Operator": CARRIER_PROFILES["VIMC"].operator((own_owner or owner) == "SOC"),
        "FE_Status": status or "", "Weight_Value": weight_result["value"] if weight_result is not None else None,
        "Weight_Unit": "TONS" if weight_result is not None else None,
        "Weight_Kind": settings["weight_kind"], "Description": description,
        "Cargo_Type": "", "Shipper": shipper, "Consignee": consignee, "Notify": notify,
        "Cleaned_Consignee_Name_For_Output": _clean_party_name(consignee),
        "Confidence": 100 if parsed.get("layout") in {"weight_first_tons", "description_first_kg", "marks_empty", "explicit_empty_detail"} else 0,
        "Warning": "", "source_file": source_file, "source_sheet": sheet, "source_row": entry["row"],
        "raw": {"text": parsed.get("raw_line", entry["text"]), "source_cell": entry["text"],
                "source_column": entry["col"] + 1, "source_line": entry["line"],
                "container_no": parsed.get("container_no", ""), "size_type": parsed.get("size_type"),
                "seal": parsed.get("seal_no"), "weight": parsed.get("weight_raw"),
                "weight_source_unit": weight_result["source_unit"] if weight_result is not None else parsed.get("weight_unit"),
                "description": parsed.get("description", ""), "layout": parsed.get("layout"),
                "ambiguous_candidates": parsed.get("ambiguous_candidates", []),
                "bl_evidence": group["bl_evidence"], "shipper": shipper, "consignee": consignee,
                "party_evidence": [dict(item) for item in group["party_evidence"]],
                "notify": "\n".join(group["Notify"]), "status_source": status_source,
                "context_status": context_status, "row_status": own_status, "source_bill": group["BL_No"],
                "ownership": own_owner or owner},
        "rules": [f"{PROFILE_VERSION}:{parsed.get('layout', 'unparsed')}", f"fe:{status_source}", "vimc_operator_svm_vmc", "vimc_legacy_vtos_mapping", "preserve_source_physical_type"],
    }
    if status == "E" and not description:
        record["Description"] = "EMPTY"
    if not re.fullmatch(r"[A-Z]{4}\d{7}", record["Container_No"]):
        record["Confidence"] = min(record["Confidence"], 50)
        record["raw"]["identifier_requires_review"] = True
    return refresh_derived_fields(record, settings)


def is_corroborated_compact_identifier(record):
    """Accept only the literal compact ID corroborated by separate VIMC cells."""
    identifier = record.get("Container_No", "")
    raw = record.get("raw") or {}
    if (not isinstance(identifier, str) or not _COMPACT_IDENTIFIER.fullmatch(identifier)
            or identifier != raw.get("container_no") or not record.get("BL_No")
            or record["BL_No"] != raw.get("source_bill")
            or raw.get("detail_source") != "description" or raw.get("layout") not in _WEIGHTED_LAYOUTS):
        return False
    detail = parse_structured_line(text_value(raw.get("text")))
    if not detail or detail["container_no"] != identifier or detail["layout"] not in _WEIGHTED_LAYOUTS:
        return False
    if text_value(raw.get("source_cell")).split(maxsplit=1)[:1] != [identifier]:
        return False
    detail_size = detail["size_type"].replace("'", "")
    if not is_supported_size_type(detail_size):
        return False
    marks = raw.get("marks_evidence")
    if not isinstance(marks, list) or not isinstance(raw.get("source_column"), int):
        return False
    for mark in marks:
        if (not isinstance(mark, dict) or mark.get("container_no") != identifier
                or not isinstance(mark.get("col"), int) or mark["col"] + 1 == raw["source_column"]):
            continue
        # The segmented MARKS match drops any preceding prose. Only the
        # original source line can corroborate an exact compact ID/size pair.
        match = _COMPACT_MARK.fullmatch(text_value(mark.get("text")))
        if match and match["identifier"] == identifier and match["size"].replace("'", "") == detail_size:
            return True
    return False


def _apply_trailing_owner_total(group, records):
    if not records or not group["BL_No"]:
        return
    totals = []
    for entry in group["description"]:
        match = _TRAILING_OWNER_TOTAL.fullmatch(normalize_text(entry["text"]))
        if match:
            totals.append((entry, int(match[1]), match[2].replace("'", ""), match[3], match[4]))
    if len(totals) != 1:
        return
    entry, quantity, size, owner, status = totals[0]
    expected_fe = "E" if status == "EMPTY" else "F"
    if (quantity != len(records) or quantity != len({record["Container_No"] for record in records})
            or any(record["Size_Type"].replace("'", "") != size
                   or record["raw"].get("detail_source") != "description"
                   or record["raw"]["layout"] not in _WEIGHTED_LAYOUTS
                   or (record["source_row"], record["raw"]["source_line"]) >= (entry["row"], entry["line"])
                   or record["FE_Status"] != expected_fe
                   or record["raw"]["ownership"] not in (None, owner)
                   or len(set(re.findall(r"\b(?:SOC|COC)\b", record["Description"]))) > 1
                   for record in records)):
        return
    for record in records:
        if record["raw"]["ownership"] is None:
            record["Operator"] = CARRIER_PROFILES["VIMC"].operator(owner == "SOC")
            record["raw"]["ownership_total"] = {"text": entry["text"], "source_row": entry["row"],
                "source_column": entry["col"] + 1, "source_line": entry["line"], "owner": owner,
                "quantity": quantity, "size_type": size}
            record["rules"].append("vimc_ownership_from_corroborated_bl_total")


def _validate_record(record, parsed, issues):
    if not record["BL_No"]:
        _add_issue(issues, "VIMC_BL_MISSING", "Không xác định được số vận đơn; đã giữ container để kiểm tra.", record=record, severity="error", field="BL_No")
    if not record["Cleaned_Consignee_Name_For_Output"]:
        _add_issue(issues, "VIMC_CONSIGNEE_MISSING", "Thiếu chủ hàng/người nhận; container vẫn được giữ trong kết quả.", record=record, severity="error", field="Cleaned_Consignee_Name_For_Output")
    if not is_valid_container(record["Container_No"]):
        _add_issue(issues, "VIMC_CONTAINER_FORMAT", "Số container không khớp cấu trúc nguồn đã hỗ trợ; hãy đối chiếu bản gốc.", record=record, severity="error", field="Container_No")
    if not record["Size_Type"]:
        _add_issue(issues, "VIMC_SIZE_MISSING", "Chưa đọc được kích cỡ container.", record=record, severity="error", field="Size_Type")
    elif not record.get("Physical_ISO_Size"):
        _add_issue(issues, "VIMC_SIZE_UNKNOWN", "Kích cỡ chưa có ánh xạ ISO; đã giữ nguyên mã nguồn.", record=record, severity="warning", field="Size_Type")
    if parsed.get("layout") == "seal_type_ambiguous":
        affected = ["Seal_No", "Size_Type", "Description"]
        if parsed.get("weight_raw") is None:
            affected.append("Weight_Value")
        fields = "seal, kích cỡ, hàng hóa và trọng lượng" if "Weight_Value" in affected else "seal, kích cỡ và hàng hóa"
        _add_issue(issues, "VIMC_SEAL_TYPE_AMBIGUOUS", f"Hai mã liền nhau đều có thể là kích cỡ. Đối chiếu {fields} với dòng gốc rồi chọn cách đọc.", record=record, severity="error")
        issues[-1]["resolution_fields"] = affected
    elif parsed.get("layout") == "ambiguous":
        # This is a coupled layout/weight/description decision. Editing only the
        # numeric weight cannot resolve it; an explicit review must remain.
        _add_issue(issues, "VIMC_LAYOUT_AMBIGUOUS", "Dòng phù hợp cả trọng lượng đầu dòng (tấn) và cuối dòng (kg). Cần xác nhận trọng lượng, đơn vị và mô tả; ứng dụng không chọn theo tên tàu.", record=record, severity="error")
        issues[-1]["resolution_fields"] = ["Weight_Value", "Description"]
    elif parsed.get("layout") in {"unparsed", "marks_incomplete"}:
        _add_issue(issues, "VIMC_CONTAINER_UNPARSED", "Đã phát hiện container nhưng chưa đọc đủ dòng chi tiết; dữ liệu gốc được giữ để kiểm tra.", record=record, severity="error")
        issues[-1]["resolution_fields"] = ["Container_No", "Size_Type", "Weight_Value", "Description", "FE_Status"]
    if parsed.get("weight_raw") is not None and record["Weight_Value"] is None:
        _add_issue(issues, "VIMC_WEIGHT_INVALID", "Không đọc được trọng lượng theo quy ước số của mẫu hiện tại.", record=record, severity="error", field="Weight_Value")
    elif record["FE_Status"] != "E" and record["Weight_Value"] is None:
        _add_issue(issues, "VIMC_WEIGHT_MISSING", "Container chưa xác nhận rỗng và thiếu trọng lượng.", record=record, severity="error", field="Weight_Value")
    if not record["FE_Status"]:
        _add_issue(issues, "VIMC_FE_UNRESOLVED", "Chưa xác định được trạng thái đầy/rỗng từ thông tin rõ ràng.", record=record, severity="error", field="FE_Status")
    if record["Weight_Value"] == 0 and record["FE_Status"] == "F":
        _add_issue(issues, "VIMC_ZERO_LOADED_WEIGHT", "Container có hàng có trọng lượng bằng 0; đã giữ đúng giá trị 0 để đối chiếu.", record=record, field="Weight_Value")
    if record["FE_Status"] == "E" and record["Description"] and _status(record["Description"]) != "E":
        _add_issue(issues, "VIMC_STATUS_GOODS_CONFLICT", "Nhóm vận đơn ghi rỗng nhưng dòng container có mô tả hàng; đã giữ nguyên mô tả, cần kiểm tra F/E.", record=record, severity="error", field="FE_Status")
    if record["raw"].get("context_status") and record["raw"].get("row_status") and record["raw"]["context_status"] != record["raw"]["row_status"]:
        _add_issue(issues, "VIMC_STATUS_SCOPE_CONFLICT", "Trạng thái đầy/rỗng của dòng container khác tiêu đề nhóm trước đó; đã giữ trạng thái ghi trực tiếp trên dòng để kiểm tra.", record=record, severity="error", field="FE_Status")
    evidence = [item["value"] for item in record["raw"]["bl_evidence"] if item["value"]]
    if len(set(evidence)) > 1:
        _add_issue(issues, "VIMC_BL_CONFLICT", "Số vận đơn trong cột thứ ba khác số ghi cạnh nhãn B/L; đã giữ cả hai nguồn.", record=record, severity="error", field="BL_No")


def _reconcile_marks_size(record, settings, issues):
    raw = record["raw"]
    marks = raw.get("marks_evidence", ())
    detail_size = record["Size_Type"].replace("'", "")
    if not marks or not detail_size:
        return
    mark_sizes = {text_value(mark.get("size_type")).replace("'", "") for mark in marks}
    if (detail_size == "40HC" and mark_sizes == {"40RF"} and record["FE_Status"] == "F"
            and raw["detail_source"] == "description"
            and re.match(r"^(?:RF|REEFER)\b", record["Description"])):
        # HC supplies the height, MARKS and the cargo description supply the
        # equipment type. Preserve both declarations and keep the row reviewable.
        record["Size_Type"] = "40RH"
        record.update(refresh_derived_fields(record, settings))
        record["rules"].append("vimc.high_cube_reefer_corroborated")
        _add_issue(issues, "VIMC_REEFER_SIZE_REVIEW",
                   "Chi tiết ghi 40HC, MARKS ghi 40RF và mô tả ghi hàng lạnh. "
                   "Xuất 40RH (container lạnh cao), giữ F. Đối chiếu mã kích cỡ trên vỏ.",
                   record=record, field="Size_Type")
    elif any(size and size != detail_size and SIZE_TO_ISO.get(size) != record.get("Physical_ISO_Size")
             for size in mark_sizes):
        _add_issue(issues, "VIMC_MARKS_SIZE_CONFLICT",
                   "Kích cỡ trong MARKS khác dòng chi tiết container; đã giữ cả hai nguồn.",
                   record=record, severity="error", field="Size_Type")


def _finalize_group(group, source_file, sheet, settings, issues, counters, source_fragments):
    records = []
    markers = _source_status_markers(group)
    detail_columns = {entry["col"] for entry in group["description"]}
    detail_fragments = {}
    marks_by_entry = [(entry, parse_marks_container(entry["text"])) for entry in group["marks"]]
    marked_containers = {mark["container_no"] for _, found in marks_by_entry for mark in found}

    def fragment(entry, text, status, reason, record=None):
        evidence = {"source_sheet": sheet, "source_row": entry["row"],
                    "source_column": entry["col"] + 1, "source_line": entry["line"],
                    "text": text, "status": status, "reason": reason}
        if record:
            evidence["record_id"] = record["record_id"]
        source_fragments.append(evidence)
        return evidence

    for entry in group["description"] + group["other"]:
        segments = split_detail_segments(entry["text"], marked_containers=marked_containers)
        if not segments:
            fragment(entry, entry["text"], "ignored", "Thông tin nguồn không có cấu trúc dòng container; giữ để đối chiếu.")
        for segment_index, (_, segment) in enumerate(segments, 1):
            counters["candidate_occurrences"] += 1
            parsed = parse_structured_line(segment)
            status, owner = _context(entry, markers)
            if parsed["layout"] == "unparsed" and parsed["size_type"] and (_status(parsed["description"]) == "E" or status == "E"):
                parsed["layout"] = "explicit_empty_detail"
            record = _base_record(group, entry, segment_index, source_file, sheet, parsed, status, owner, settings)
            record["raw"]["detail_source"] = "description" if entry["col"] in detail_columns else "other"
            _validate_record(record, parsed, issues)
            records.append(record)
            counters[parsed["layout"]] += 1
            unresolved = (record["raw"].get("identifier_requires_review")
                          or parsed["layout"] in {"unparsed", "ambiguous", "seal_type_ambiguous"})
            detail_fragments[record["record_id"]] = fragment(
                entry, segment, "unresolved" if unresolved else "parsed", parsed["layout"], record,
            )
    by_container = defaultdict(list)
    for record in records:
        by_container[record["Container_No"]].append(record)
    empty_total = None if records else _empty_marks_total(group, marks_by_entry, markers, settings)
    for entry, parsed_marks in marks_by_entry:
        status, owner = ("E", empty_total["owner"]) if empty_total else _context(entry, markers, marks=True)
        if not parsed_marks:
            fragment(entry, entry["text"], "ignored", "Nội dung MARKS không có cấu trúc container được hỗ trợ; giữ nguyên để đối chiếu.")
        for segment_index, parsed_mark in enumerate(parsed_marks, 1):
            counters["candidate_occurrences"] += 1
            container = parsed_mark["container_no"]
            if by_container[container]:
                # A mark is a corroborating reference to the detail record. Keep
                # every occurrence in raw evidence rather than export it twice.
                counters["corroborating_marks"] += 1
                fragment(entry, parsed_mark["raw"], "corroborating", "MARKS đối chiếu với dòng chi tiết.", by_container[container][0])
                for record in by_container[container]:
                    record["raw"].setdefault("marks_evidence", []).append({**entry, **parsed_mark})
                continue
            parsed = {**parsed_mark, "seal_no": None, "description": "EMPTY" if status == "E" else "",
                      "weight_raw": None, "weight_unit": None, "raw_line": entry["text"],
                      "layout": "marks_empty" if status == "E" else "marks_incomplete"}
            record = _base_record(group, entry, segment_index, source_file, sheet, parsed, status, owner, settings)
            record["raw"]["marks_evidence"] = [{**entry, **parsed_mark}]
            if empty_total:
                record["raw"]["empty_total_evidence"] = dict(empty_total)
                record["raw"]["status_source"] = "marks_empty_total"
                record["rules"].append("vimc.empty_total_matches_marks")
            _validate_record(record, parsed, issues)
            records.append(record)
            by_container[container].append(record)
            counters[parsed["layout"]] += 1
            unresolved = record["raw"].get("identifier_requires_review") or parsed["layout"] == "marks_incomplete"
            fragment(entry, parsed_mark["raw"], "unresolved" if unresolved else "parsed", parsed["layout"], record)
    for record in records:
        if record["record_id"] in detail_fragments:
            _reconcile_marks_size(record, settings, issues)
        if is_corroborated_compact_identifier(record):
            detail_fragments[record["record_id"]].update(
                status="parsed", reason="legacy_compact_identifier_corroborated_in_marks",
            )
    _apply_trailing_owner_total(group, records)
    return records


def _warn_duplicates(records, issues):
    grouped = defaultdict(list)
    for record in records:
        if record["BL_No"] and record["Container_No"]:
            grouped[(record["BL_No"], record["Container_No"])].append(record)
    for (_, container), matches in grouped.items():
        if len(matches) <= 1:
            continue
        signatures = {(row.get("Seal_No"), row.get("Size_Type"), row.get("Weight_Value"), row.get("FE_Status")) for row in matches}
        conflict = len(signatures) > 1
        for record in matches:
            _add_issue(issues, "VIMC_CONTAINER_DATA_CONFLICT" if conflict else "VIMC_DUPLICATE_IN_BL",
                       f"Container {container} có {len(matches)} dòng trong cùng vận đơn; đã giữ nguyên để phân biệt dòng lặp với nhiều dòng hàng." + (" Seal/kích cỡ/trọng lượng/F/E không thống nhất." if conflict else ""),
                       record=record, severity="error" if conflict else "warning", field="Container_No")


def parse_manifest(path, *, settings=None, progress=None):
    """Parse one workbook selected explicitly as carrier VIMC."""
    settings = dict(settings or {})
    settings.setdefault("weight_kind", CARRIER_PROFILES["VIMC"].weight_kind)
    source_file = Path(path).name
    issues, records, source_fragments = [], [], []
    counters = Counter()
    sheets_seen, sheets_used = [], []
    workbooks = read_workbook(path)
    available_sheets = [name for name, _ in workbooks]
    selected_sheet = settings.get("selected_sheet")
    if selected_sheet:
        workbooks = [(name, frame) for name, frame in workbooks if name == selected_sheet]
        if not workbooks:
            raise ValueError(f"Không tìm thấy sheet VIMC đã chọn: {selected_sheet}.")
    total_rows = sum(len(frame) for _, frame in workbooks)
    walked = 0
    for sheet, frame in workbooks:
        sheets_seen.append(sheet)
        header_index, columns = _find_header(frame)
        if header_index is None:
            detected = any(split_container_segments(text_value(cell)) for values in frame.itertuples(index=False, name=None) for cell in values)
            if not detected:
                walked += len(frame)
                continue
            _add_issue(issues, "VIMC_HEADER_NOT_FOUND", "Không nhận diện được header VIMC trong 20 dòng đầu; đã giữ các container phát hiện được để kiểm tra.", severity="error", sheet=sheet)
            group = _new_group()
            for index, row in enumerate(frame.itertuples(index=False, name=None), 1):
                for col, value in enumerate(row):
                    group["other"].extend(_entries(value, index, col))
            records.extend(_finalize_group(group, source_file, sheet, settings, issues, counters, source_fragments))
            walked += len(frame)
            continue
        sheets_used.append(sheet)
        missing = {"party", "marks", "description"} - columns.keys()
        if missing:
            _add_issue(issues, "VIMC_HEADER_INCOMPLETE", "Thiếu cột VIMC cần thiết: " + ", ".join(sorted(missing)) + ". Các container phát hiện được vẫn được giữ.", severity="error", sheet=sheet, row=header_index + 1)
        group = _new_group()
        for index in range(header_index + 1, len(frame)):
            values = frame.iloc[index].tolist()
            source_row = index + 1
            if progress and index % 50 == 0:
                progress(walked + index, max(total_rows, 1), f"VIMC: đọc {sheet}, dòng {source_row}")
            repeated_header = _header_columns(values)
            if len(repeated_header) == 3 and len(set(repeated_header.values())) == 3:
                continue
            bl_no, evidence = _extract_bl(values)
            if bl_no is not None:
                records.extend(_finalize_group(group, source_file, sheet, settings, issues, counters, source_fragments))
                group = _new_group(bl_no, source_row)
                group["bl_evidence"] = evidence
            else:
                party_col = columns.get("party", 0)
                has_container_data = any(split_container_segments(text_value(value)) for col, value in enumerate(values)
                                         if col in {columns.get("description"), columns.get("marks")})
                _read_party_row(group, values, source_row, party_col, allow_continuation=not has_container_data)
            # Include goods/marks on the party-information row, which used to be skipped.
            for field in ("description", "marks"):
                col = columns.get(field)
                if col is not None and col < len(values):
                    if bl_no is not None and col == 2 and text_value(values[col]) == bl_no:
                        continue  # Legacy three-column sheets place the B/L in this cell.
                    group[field].extend(_entries(values[col], source_row, col))
            # Preserve unexpected container-looking cells outside the known columns.
            for col, value in enumerate(values):
                if col not in {columns.get("description"), columns.get("marks")} and not (bl_no is not None and col in {0, 2}):
                    if split_container_segments(text_value(value)):
                        group["other"].extend(_entries(value, source_row, col))
            # Unmarked party continuation ends once container data starts. An
            # explicit 1)/2)/3) marker may start another party block later.
            if any(split_container_segments(text_value(value)) for col, value in enumerate(values)
                   if col in {columns.get("description"), columns.get("marks")}):
                group["party_role"] = None
        records.extend(_finalize_group(group, source_file, sheet, settings, issues, counters, source_fragments))
        walked += len(frame)
    if not records:
        _add_issue(issues, "VIMC_NO_CONTAINERS", "Không tìm thấy container VIMC trong file; hãy kiểm tra file và hãng tàu đã chọn.", severity="error")
    _warn_duplicates(records, issues)
    by_record = defaultdict(list)
    for finding in issues:
        if finding.get("record_id"):
            by_record[finding["record_id"]].append(finding["message"])
    for record in records:
        record["Warning"] = " | ".join(dict.fromkeys(by_record[record["record_id"]]))
    if progress:
        progress(max(total_rows, 1), max(total_rows, 1), "VIMC: đã đọc xong manifest")
    return {"records": records, "issues": issues,
            "metadata": {"carrier": "VIMC", "source_commit": SOURCE_COMMIT, "profile_version": PROFILE_VERSION,
                         "source_file": source_file, "sheets_seen": sheets_seen, "sheets_used": sheets_used,
                         "available_sheets": available_sheets, "selected_sheet": selected_sheet,
                         "source_fragments": source_fragments,
                         "coverage": {"source_fragments": len(source_fragments),
                            **{f"{status}_fragments": sum(item["status"] == status for item in source_fragments)
                               for status in ("parsed", "unresolved", "ignored", "corroborating")}},
                         "row_layout_counts": dict(counters), "selection_basis": "carrier_and_row_structure",
                         "weight_internal_unit": "TONS", "weight_kind": settings["weight_kind"],
                         "number_format": settings.get("number_format", "legacy")}}
