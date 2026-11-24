"""VINAFCO Excel adapter with explicit source evidence and carrier-local rules."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...common import (
    is_explicit_empty, issue, normalize_text, parse_weight, read_workbook, seal_text, text_value,
)
from .profile import CARGO_TYPES, DEFAULTS, HEADER_ALIASES, INPUT_COLUMNS, SIZE_TO_VTOS


PROFILE_VERSION = "VINAFCO-1.1.1"
_PARTY = re.compile(r"^\s*\(\s*([SCN])\s*\)\s*(.*)$", re.I | re.S)
_CONTAINER = re.compile(r"^[A-Z]{4}\d{7}$")
_SOC = re.compile(r"(?<![A-Z])S[.\s]*O[.\s]*C(?![A-Z])", re.I)
_COC = re.compile(r"(?<![A-Z])C[.\s]*O[.\s]*C(?![A-Z])", re.I)
_STOP_NAME = re.compile(
    r"(?:Mail|Tel|Fax|Địa chỉ|SĐT|Email|Số CCCD|Tại|Chức vụ|Tài khoản|Đ/C|MST|"
    r"Phone|Điện thoại|ADD|ADDRESS)\s*:", re.I,
)
_WEIGHT_UNITS = {
    "KG": "KGS", "KGS": "KGS", "KILOGRAM": "KGS", "KILOGRAMS": "KGS",
    "T": "TONS", "MT": "TONS", "TON": "TONS", "TONS": "TONS",
    "TONNE": "TONS", "TONNES": "TONS",
}
_FOOTER_LABELS = {"TOTAL", "GRAND TOTAL", "TONG CONG", "TONG SO"}
_SUMMARY_HEADERS = {"LOAICONT": "size", "SOLUONG": "quantity", "GHICHU": "remarks"}
_SUMMARY_OTHER_LABELS = {"TEU", "TEUS", "TRONG TAI", "GROSS WEIGHT", "TOTAL WEIGHT"}
_SUMMARY_SIZE = re.compile(r"(?:20|40|45)[A-Z]{2,3}|[24][0-9][A-Z][0-9]")


def _size(value: Any) -> str:
    return normalize_text(value).replace("'", "").replace("’", "").replace(" ", "")


def _header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_text(value))


def _settings(settings: dict | None) -> dict:
    supplied = dict(settings or {})
    cfg = {**DEFAULTS, **supplied}
    aliases = {
        "default_weight_unit_if_missing": "default_weight_unit",
        "tare_20ft_empty_vgm": "tare_20ft", "tare_40ft_empty_vgm": "tare_40ft",
        "tare_20rf_empty_vgm": "tare_20rf", "tare_40rf_empty_vgm": "tare_40rf",
        "min_payload_for_f_vgm": "min_payload", "safety_margin_tons": "safety_margin",
    }
    for legacy, target in aliases.items():
        if legacy in supplied and target not in supplied:
            cfg[target] = supplied[legacy]
    for key in (
        "tare_20ft", "tare_40ft", "tare_45ft", "tare_20rf", "tare_40rf", "tare_45rf",
        "min_payload", "safety_margin", "cargo_weight_empty_threshold",
    ):
        cfg[key] = float(cfg[key])
        if not math.isfinite(cfg[key]) or cfg[key] < 0:
            raise ValueError(f"Cấu hình {key} phải là số hữu hạn lớn hơn hoặc bằng 0.")
    cfg["peek_rows"] = max(1, int(cfg["peek_rows"]))
    if cfg["weight_kind"] not in ("gross", "cargo", "unknown"):
        raise ValueError("weight_kind chỉ nhận gross, cargo hoặc unknown.")
    if cfg["number_format"] not in ("legacy", "decimal_comma", "decimal_dot"):
        raise ValueError("number_format không hợp lệ.")
    unit = _WEIGHT_UNITS.get(normalize_text(cfg["default_weight_unit"]))
    if not unit:
        raise ValueError("default_weight_unit phải là kg hoặc tấn (KGS/TONS).")
    cfg["default_weight_unit"] = unit
    cfg["size_to_vtos"] = dict(SIZE_TO_VTOS)
    # Accept the old name without treating local VTOS aliases as global ISO codes.
    for name in ("size_to_iso", "size_to_vtos"):
        custom = supplied.get(name, {})
        if not isinstance(custom, dict):
            raise ValueError(f"{name} phải là bảng ánh xạ.")
        cfg["size_to_vtos"].update({_size(k): text_value(v) for k, v in custom.items()})
    cfg["cargo_type_mapping"] = dict(CARGO_TYPES)
    for name in ("size_type_to_cargo_type_base", "cargo_type_mapping"):
        custom = supplied.get(name, {})
        if not isinstance(custom, dict):
            raise ValueError(f"{name} phải là bảng ánh xạ.")
        cfg["cargo_type_mapping"].update({_size(k): normalize_text(v) for k, v in custom.items()})
    return cfg


def _derived(size: Any, fe: str, cfg: dict) -> tuple[str, str]:
    key = _size(size)
    vtos = cfg["size_to_vtos"].get(key, "")
    base = cfg["cargo_type_mapping"].get(key) or cfg["cargo_type_mapping"].get(_size(vtos))
    if not base:
        return vtos, "UNKNOWN"
    if fe == "E":
        return vtos, "EMPTY" if base == "GENERAL" else f"EMPTY {base}"
    return vtos, base


def is_supported_size_type(size_type, settings=None) -> bool:
    """Accept only size aliases with a usable VTOS and cargo mapping."""
    vtos, cargo = _derived(size_type, "F", _settings(settings))
    return bool(vtos and cargo != "UNKNOWN")


def refresh_derived_fields(record: dict, settings: dict | None = None) -> dict:
    """Re-map size/cargo after manual edits; preserve F/E and original description."""
    cfg = _settings(settings)
    result = dict(record)
    result["VTOS_Size"], result["Cargo_Type"] = _derived(
        result.get("Size_Type"), text_value(result.get("FE_Status")).upper(), cfg,
    )
    if not result.get("Operator"):
        raw = result.get("raw") or {}
        soc_text = " ".join(text_value(x) for x in (
            result.get("Shipper"), raw.get("remarks"), raw.get("comm"),
        ))
        result["Operator"] = cfg["operator_soc"] if _SOC.search(soc_text) else cfg["operator_coc"]
    return result


def _weight_header(value: Any, cfg: dict) -> tuple[bool, str | None]:
    """Recognize a weight label and its unit together, including joined suffixes.

    A configured label remains an alias. It may name the whole header, including
    a unit, or just the base label followed by KG/KGS/TONS/etc. Do not interpret
    the final T of an ordinary label such as WEIGHT as a tonne annotation.
    """
    key = _header(value)
    custom = text_value(cfg.get("col_gw", INPUT_COLUMNS["gw"]))
    bases = {_header(label) for label in HEADER_ALIASES["gw"]}
    if key in bases:
        return True, None
    custom_key = _header(custom)
    units = sorted(_WEIGHT_UNITS, key=len, reverse=True)
    for base in bases | ({custom_key} if custom_key else set()):
        for suffix in units:
            if key == base + suffix:
                return True, _WEIGHT_UNITS[suffix]
    if key == custom_key and key:
        # Exact configured labels such as "MY MASS (KGS)" or "MYMASSKGS"
        # still carry the suffix unit instead of silently using the default.
        label = normalize_text(value)
        for suffix in units:
            if suffix != "T" and key.endswith(suffix) and len(key) > len(suffix):
                return True, _WEIGHT_UNITS[suffix]
            if re.search(r"(?:^|[^A-Z0-9])" + suffix + r"(?:[^A-Z0-9]*)$", label):
                return True, _WEIGHT_UNITS[suffix]
        return True, None
    return False, None


def _map_header(row, cfg: dict) -> tuple[dict, list, str]:
    matches = {}
    duplicates = []
    weight_unit = cfg["default_weight_unit"]
    for col_idx, value in enumerate(row):
        key = _header(value)
        if not key:
            continue
        fields = []
        explicit_weight_unit = None
        for field, aliases in HEADER_ALIASES.items():
            accepted = {_header(x) for x in aliases}
            accepted.add(_header(cfg.get(f"col_{field}", INPUT_COLUMNS[field])))
            matched = key in accepted
            if field == "gw":
                matched, explicit_weight_unit = _weight_header(value, cfg)
            if field == "container_no":
                matched = matched or bool(re.fullmatch(r"(?:CONTAINERNO|CONTAINERNUMBER)\d+", key))
            if matched:
                fields.append(field)
        if len(fields) > 1:
            duplicates.extend(fields)
        for field in fields:
            if field in matches:
                duplicates.append(field)
            else:
                matches[field] = col_idx
                if field == "gw" and explicit_weight_unit:
                    weight_unit = explicit_weight_unit
    return matches, sorted(set(duplicates)), weight_unit


def _raw_row(row, columns: dict) -> dict:
    raw = {name: (seal_text if name == "seal" else text_value)(row.iloc[index])
           for name, index in columns.items()}
    for name in INPUT_COLUMNS:
        raw.setdefault(name, "")
    return raw


def _is_footer(raw: dict) -> bool:
    container = normalize_text(raw["container_no"])
    if container:
        return bool(re.match(r"^(TOTAL\b|GRAND TOTAL\b|TONG CONG\b|TONG SO\b)", container))
    # Totals often put their label in the party/commodity column. A known
    # label may accompany summary weight, but ordinary cargo text is not a total.
    for field in ("party_raw", "bill_no", "comm", "remarks"):
        value = normalize_text(raw[field]).rstrip(" :;=")
        if value in _FOOTER_LABELS or re.match(r"^(?:TOTAL|GRAND TOTAL|TONG CONG|TONG SO)\s*[:=]\s*", value):
            return True
    return False


def _has_container_attributes(raw: dict) -> bool:
    """A populated type/seal/weight/goods row is not an ordinary empty row."""
    return any(raw[name] for name in ("type", "gw", "comm")) or bool(text_value(raw["seal"]))


def _container_key(value: str) -> str:
    return re.sub(r"[\s-]+", "", value).upper()


def _summary_header(row: tuple) -> dict:
    matches = {}
    for col_idx, value in enumerate(row):
        if not text_value(value):
            continue
        key = _SUMMARY_HEADERS.get(_header(value))
        # A side-by-side heading may share a row with real container detail.
        # Only an exclusively structural heading can classify the entire row.
        if not key or key in matches:
            return {}
        matches[key] = col_idx
    return matches if len(matches) == len(_SUMMARY_HEADERS) else {}


def _summary_entry(row: tuple, columns: dict, detail_columns: dict, cfg: dict):
    """Require each summary row to fit its own columns and vocabulary."""
    if any(text_value(value) for idx, value in enumerate(row) if idx not in columns.values()):
        return None
    if _CONTAINER.fullmatch(_container_key(text_value(row[detail_columns["container_no"]]))):
        return None
    raw_label = row[columns["size"]]
    label = normalize_text(raw_label).rstrip(" :;=")
    quantity = text_value(row[columns["quantity"]])
    remarks = text_value(row[columns["remarks"]])
    numeric = re.fullmatch(r"[+-]?[0-9]+(?:[.,][0-9]+)?", quantity)
    if quantity and not numeric and normalize_text(quantity) not in {"-", "–", "—", "N/A"}:
        return None
    integer = re.fullmatch(r"([0-9]{1,15})(?:[.,]0+)?", quantity)
    count = int(integer[1]) if integer else None
    size = _size(raw_label)
    if size in cfg["size_to_vtos"] or _SUMMARY_SIZE.fullmatch(size):
        return "size", size, count
    if label in _FOOTER_LABELS:
        return "total", None, count
    if label in _SUMMARY_OTHER_LABELS and numeric:
        return "other_metric", None, None
    # A number alone can also be a damaged detail row if it lands in the
    # detail weight/seal/type/description columns. Keep it for review there.
    if not label and not remarks and numeric and columns["quantity"] not in {
        detail_columns.get(field) for field in ("type", "seal", "gw", "comm")
    }:
        return "unlabeled_metric", None, None
    return None


def _scan_summaries(sheet_name: str, frame, header_idx: int, detail_columns: dict, cfg: dict):
    """Identify bounded summary blocks, including moved blocks on the same sheet."""
    blocks = []
    summary_rows = {}
    for row_idx, values in enumerate(frame.iloc[header_idx + 1:].itertuples(index=False, name=None), header_idx + 1):
        if row_idx + 1 in summary_rows:
            continue
        columns = _summary_header(values)
        if not columns:
            continue
        entries = []
        for idx, row in enumerate(frame.iloc[row_idx + 1:].itertuples(index=False, name=None), row_idx + 1):
            if not any(text_value(value) for value in row):
                continue
            parsed = _summary_entry(row, columns, detail_columns, cfg)
            if not parsed:
                break
            kind, size, count = parsed
            if not entries and kind not in ("size", "total"):
                break
            entries.append({"kind": kind, "size": size, "count": count, "source_row": idx + 1,
                            "source_column": columns["quantity"] + 1, "label_column": columns["size"] + 1})
        if not any(entry["kind"] in ("size", "total") and entry["count"] is not None for entry in entries):
            continue
        blocks.append({"source_sheet": sheet_name, "header_row": row_idx + 1,
                       "end_row": entries[-1]["source_row"], "columns": {key: index + 1 for key, index in columns.items()},
                       "entries": entries})
        summary_rows[row_idx + 1] = "header"
        summary_rows.update({entry["source_row"]: entry["kind"] for entry in entries})
    return blocks, summary_rows


def _candidate_preview(frame, header_idx: int, columns: dict, summary_rows: dict, cfg: dict) -> list:
    preview = []
    for idx in range(header_idx + 1, len(frame)):
        if idx + 1 in summary_rows:
            continue
        row = frame.iloc[idx]
        mapping, _, _ = _map_header(row.tolist(), cfg)
        if "container_no" in mapping and len(mapping) >= 4:
            continue
        raw = _raw_row(row, columns)
        if _is_footer(raw) or not (raw["container_no"] or (
            _has_container_attributes(raw) and not _PARTY.match(raw["party_raw"])
        )):
            continue
        fields = ("container_no", "type", "bill_no", "seal", "gw", "comm", "party_raw")
        text = " | ".join(" ".join(raw[field].split()) for field in fields if raw[field])
        preview.append({"source_row": idx + 1, "text": text if len(text) <= 180 else text[:177] + "..."})
        if len(preview) == 3:
            break
    return preview


def _locate_table(sheets, cfg: dict, explicitly_selected: bool):
    candidates = []
    selected = text_value(cfg.get("target_sheet_name"))
    for sheet_name, frame in sheets:
        if explicitly_selected and selected and sheet_name != selected:
            continue
        for idx in range(min(len(frame), cfg["peek_rows"])):
            mapping, duplicates, weight_unit = _map_header(frame.iloc[idx].tolist(), cfg)
            if "container_no" in mapping and len(mapping) >= 4:
                blocks, summary_rows = _scan_summaries(sheet_name, frame, idx, mapping, cfg)
                has_data = False
                for j in range(idx + 1, len(frame)):
                    if j + 1 in summary_rows:
                        continue
                    data_row = frame.iloc[j]
                    repeated, _, _ = _map_header(data_row.tolist(), cfg)
                    if "container_no" in repeated and len(repeated) >= 4:
                        continue
                    raw = _raw_row(data_row, mapping)
                    if _is_footer(raw):
                        continue
                    if raw["container_no"] or (_has_container_attributes(raw) and not _PARTY.match(raw["party_raw"])):
                        has_data = True
                        break
                if has_data:
                    candidates.append((sheet_name, frame, idx, mapping, duplicates, weight_unit, blocks, summary_rows))
                break
    return candidates


def _reconcile(records: list, metadata: dict, blocks: list, issues: list) -> None:
    sizes_by_container = defaultdict(set)
    container_bills = set()
    unresolved_rows = []
    for record in records:
        container = record["Container_No"]
        if not _CONTAINER.fullmatch(container):
            unresolved_rows.append(record["source_row"])
            continue
        sizes_by_container[container].add(_size(record["Size_Type"]))
        if record["BL_No"]:
            container_bills.add((container, record["BL_No"]))

    parsed_sizes = defaultdict(int)
    unknown_sizes = 0
    for sizes in sizes_by_container.values():
        if len(sizes) == 1 and "" not in sizes:
            parsed_sizes[next(iter(sizes))] += 1
        else:
            unknown_sizes += 1

    source_total = None
    source_sizes = {}
    size_entries = {}
    totals = []
    total_difference = None
    size_differences = {}
    reasons = []
    if not blocks:
        reasons.append("Không tìm thấy bảng tổng hợp có tiêu đề và số liệu nhận diện được.")
    elif len(blocks) > 1:
        reasons.append("Sheet có nhiều bảng tổng hợp và chưa xác định được phạm vi của từng bảng.")
    else:
        block = blocks[0]
        for entry in block["entries"]:
            if entry["kind"] == "size":
                size_entries.setdefault(entry["size"], []).append(entry)
            elif entry["kind"] == "total":
                totals.append(entry)
        source_total = totals[0]["count"] if len(totals) == 1 else None
        source_sizes = {size: rows[0]["count"] for size, rows in size_entries.items()
                        if len(rows) == 1 and rows[0]["count"] is not None}
        if source_total is None:
            reasons.append("Bảng tổng hợp thiếu một dòng TOTAL có số container xác định được.")
        if not source_sizes or len(source_sizes) != len(size_entries):
            reasons.append("Bảng tổng hợp thiếu số lượng theo kích cỡ hoặc có mã kích cỡ lặp.")
        if any(record["source_row"] > block["end_row"] for record in records):
            reasons.append("Có dòng chi tiết sau bảng tổng hợp nên chưa xác định được phạm vi đối soát.")
        elif "unparsed_after_header_row" not in metadata and not unresolved_rows:
            if source_total is not None:
                total_difference = len(sizes_by_container) - source_total
            if unknown_sizes:
                reasons.append("Có container thiếu kích cỡ hoặc được ghi với nhiều mã kích cỡ.")
            elif source_sizes and len(source_sizes) == len(size_entries):
                size_differences = {
                    size: parsed_sizes.get(size, 0) - source_sizes.get(size, 0)
                    for size in sorted(parsed_sizes.keys() | source_sizes.keys())
                    if parsed_sizes.get(size, 0) != source_sizes.get(size, 0)
                }
    if "unparsed_after_header_row" in metadata:
        reasons.append("Vùng chi tiết chưa được đọc hết vì tiêu đề thay đổi.")
    if unresolved_rows:
        reasons.append("Một số dòng chi tiết chưa có mã container hợp lệ.")
    mismatch = bool(total_difference or size_differences)
    metadata["reconciliation"] = {
        "status": "unavailable" if reasons else "mismatch" if mismatch else "matched",
        "reason": " ".join(reasons) or None,
        "source_sheet": metadata["source_sheet"],
        "source_total": source_total,
        "source_size_counts": dict(sorted(source_sizes.items())),
        "parsed_total": len(sizes_by_container),
        "parsed_size_counts": dict(sorted(parsed_sizes.items())),
        "parsed_container_bl_pairs": len(container_bills),
        "unresolved_container_rows": unresolved_rows,
        "total_difference": total_difference,
        "size_differences": size_differences,
        "summary_blocks": blocks,
    }
    if not mismatch:
        return
    block = blocks[0]
    first_mismatch = block["header_row"]
    if total_difference:
        first_mismatch = totals[0]["source_row"]
    else:
        mismatched_entries = size_entries.get(next(iter(size_differences)))
        if mismatched_entries:
            first_mismatch = mismatched_entries[0]["source_row"]
    finding = issue("VINAFCO_SUMMARY_MISMATCH",
        "Số container đọc được không khớp bảng tổng hợp VINAFCO. Kiểm tra số container duy nhất và số theo kích cỡ.",
        severity="warning", source_sheet=block["source_sheet"], source_row=first_mismatch)
    finding["details"] = {"source_total": source_total, "parsed_total": len(sizes_by_container),
                          "total_difference": total_difference, "size_differences": size_differences,
                          "summary_header_row": block["header_row"]}
    issues.append(finding)


def _clean_name(value: str) -> str:
    first = value.splitlines()[0].strip() if value else ""
    match = _STOP_NAME.search(first)
    if match:
        first = first[:match.start()]
    return first.rstrip(";,./\\- ")


def _tare(size: str, cfg: dict) -> float | None:
    key = _size(size)
    if not key:
        return None
    # Decode the physical length for ISO style source codes separately from VTOS labels.
    if re.fullmatch(r"[24][0-9][A-Z][0-9]", key):
        length = "20" if key[0] == "2" else "40"
        reefer = key[2] == "R"
    else:
        length = key[:2]
        reefer = cfg["cargo_type_mapping"].get(key) == "REEFER"
    if length not in ("20", "40", "45"):
        return None
    return cfg[f"tare_{length}{'rf' if reefer else 'ft'}"]


def _fe(description: str, weight: dict | None, size: str, cfg: dict):
    """Apply the carrier's legacy weight policy, recording every inference/conflict."""
    notes = []
    rules = []
    source_empty = is_explicit_empty(description)
    source_full = bool(re.fullmatch(
        r"(?:(?:COC|SOC)\s+)?(?:LADEN|FULL)(?:\s+CONTAINERS?)?[.!]?",
        normalize_text(description),
    ))
    numeric = weight["value"] if weight is not None else None
    inferred = None
    if numeric is not None:
        if cfg["weight_kind"] == "gross":
            tare = _tare(size, cfg)
            if tare is not None:
                if numeric > tare + cfg["safety_margin"] + cfg["min_payload"]:
                    inferred = "F"
                elif numeric <= tare or numeric < cfg["min_payload"]:
                    inferred = "E"
                rules.append("VINAFCO_LEGACY_GROSS_TARE")
        elif cfg["weight_kind"] == "cargo":
            inferred = "E" if numeric <= cfg["cargo_weight_empty_threshold"] else "F"
            rules.append("VINAFCO_CARGO_WEIGHT_THRESHOLD")
    explicit = "E" if source_empty else "F" if source_full else None
    if explicit:
        rules.append("VINAFCO_EXPLICIT_FE")
        if inferred is not None and explicit != inferred:
            notes.append(("VINAFCO_FE_CONFLICT", "error",
                "Trạng thái F/E ghi trong mô tả mâu thuẫn với suy luận từ trọng lượng; cần đối chiếu file gốc."))
        return explicit, notes, rules, False
    status = inferred or "F"
    if inferred:
        notes.append(("VINAFCO_FE_INFERRED", "warning",
            "F/E được suy luận từ trọng lượng theo quy tắc VINAFCO; trọng lượng vỏ là ngưỡng cấu hình, không phải cân vỏ thực tế."))
    else:
        rules.append("VINAFCO_LEGACY_DEFAULT_FULL")
        notes.append(("VINAFCO_FE_DEFAULTED", "warning",
            "Chưa đủ dữ liệu xác định F/E; đang giữ mặc định F của ứng dụng VINAFCO cũ. Cần kiểm tra trước khi xuất."))
    return status, notes, rules, True


def parse_manifest(path, *, settings=None, progress=None) -> dict:
    source = Path(path)
    issues = []
    metadata = {"carrier": "VINAFCO", "profile_version": PROFILE_VERSION,
                "source_file": str(source), "confidence_kind": "legacy_completeness_score"}
    result = {"records": [], "issues": issues, "metadata": metadata}
    try:
        cfg = _settings(settings)
        sheets = read_workbook(source)
    except Exception as exc:
        issues.append(issue("VINAFCO_READ_ERROR", f"Không đọc được manifest VINAFCO: {exc}", severity="error"))
        return result
    if progress:
        progress(10, "Đang tìm bảng manifest VINAFCO...")
    explicit_sheet = bool((settings or {}).get("target_sheet_name"))
    candidates = _locate_table(sheets, cfg, explicit_sheet)
    if not candidates:
        issues.append(issue("VINAFCO_HEADER_NOT_FOUND",
            "Không tìm thấy tiêu đề bảng VINAFCO có cột số container. Kiểm tra hãng tàu, sheet và các tên cột.", severity="error"))
        return result
    if len(candidates) > 1:
        names = ", ".join(c[0] for c in candidates)
        issues.append(issue("VINAFCO_MULTIPLE_TABLES",
            f"File có nhiều bảng manifest ({names}). Hãy chọn sheet cần xử lý để tránh bỏ sót hoặc cộng trùng dữ liệu.", severity="error"))
        metadata["candidate_sheets"] = [c[0] for c in candidates]
        metadata["table_candidates"] = [
            {"source_sheet": name, "header_row": idx + 1,
             "preview_rows": _candidate_preview(frame, idx, mapping, summary_rows, cfg)}
            for name, frame, idx, mapping, _, _, _, summary_rows in candidates
        ]
        return result
    sheet_name, frame, header_idx, columns, duplicate_columns, default_unit, blocks, summary_rows = candidates[0]
    metadata.update({"source_sheet": sheet_name, "header_row": header_idx + 1,
                     "weight_kind": cfg["weight_kind"], "number_format": cfg["number_format"],
                     "column_mapping": dict(columns)})
    if duplicate_columns:
        issues.append(issue("VINAFCO_AMBIGUOUS_COLUMNS",
            "Có nhiều cột cùng có thể là " + ", ".join(duplicate_columns) + "; cần xác nhận cột nguồn.",
            severity="error", source_sheet=sheet_name, source_row=header_idx + 1))
        return result
    for name in ("party_raw", "bill_no", "type", "gw"):
        if name not in columns:
            issues.append(issue("VINAFCO_MISSING_COLUMN",
                f"Thiếu cột {INPUT_COLUMNS[name]}; các container vẫn được giữ để kiểm tra.",
                severity="error", source_sheet=sheet_name, source_row=header_idx + 1))
    weight_header = text_value(frame.iloc[header_idx, columns["gw"]]) if "gw" in columns else ""
    metadata["default_weight_unit"] = default_unit
    metadata["weight_header"] = weight_header
    fragments = metadata["source_fragments"] = []
    records = result["records"]
    group = None
    group_count = 0
    collecting = None

    def fragment(row_idx, row, status, reason):
        if not any(text_value(value) for value in row):
            return
        fragments.append({"source_sheet": sheet_name, "source_row": row_idx + 1,
                          "text": "\t".join(text_value(value) for value in row),
                          "status": status, "reason": reason})

    fragment(header_idx, frame.iloc[header_idx], "ignored", "table_header")

    def add(record, code, message, severity="warning", field=None, resolution_fields=None):
        finding = issue(code, message, severity=severity,
            record_id=record["record_id"], field=field, source_row=record["source_row"], source_sheet=sheet_name)
        if resolution_fields:
            finding["resolution_fields"] = list(resolution_fields)
        issues.append(finding)
        record["Warning"] = " | ".join(filter(None, [record.get("Warning", ""), message]))
        if severity == "error":
            record["_has_error"] = True

    def new_group(orphan=False):
        nonlocal group_count
        group_count += 1
        return {"id": f"VINAFCO_BL_{group_count}", "bill": "", "bills": set(),
                "S": [], "C": [], "N": [], "soc": False, "records": [],
                "party_rows": [], "orphan": orphan}

    def finalize():
        if group is None:
            return
        parties = {key: "\n".join(group[key]).strip() for key in ("S", "C", "N")}
        if "SAME AS CONSIGNEE" in normalize_text(parties["N"]) or "NHU NGUOI NHAN HANG" in normalize_text(parties["N"]):
            parties["N"] = parties["C"]
        for record in group["records"]:
            record.update({"Shipper": parties["S"], "Consignee": parties["C"], "Notify": parties["N"],
                           "Cleaned_Consignee_Name_For_Output": _clean_name(parties["C"])})
            record["raw"]["party_block"] = {key: list(group[key]) for key in ("S", "C", "N")}
            record["raw"]["party_source_rows"] = [dict(value) for value in group["party_rows"]]
            if not record["BL_No"] and len(group["bills"]) == 1:
                record["BL_No"] = next(iter(group["bills"]))
                record["rules"].append("VINAFCO_BL_FROM_SINGLE_GROUP_VALUE")
            if not record["BL_No"]:
                add(record, "VINAFCO_BL_MISSING", "Thiếu số B/L hoặc không xác định được B/L duy nhất cho container.", "error", "BL_No")
            if not record["Cleaned_Consignee_Name_For_Output"]:
                add(record, "VINAFCO_CONSIGNEE_MISSING", "Thiếu tên chủ hàng; container được giữ lại để bổ sung.", "error", "Cleaned_Consignee_Name_For_Output")
            penalty = 0
            for field in ("BL_No", "Cleaned_Consignee_Name_For_Output", "VTOS_Size", "Weight_Value"):
                if record.get(field) in (None, ""):
                    penalty += 20
            if record.pop("_inferred_fe", False):
                penalty += 15
            if record.pop("_has_error", False):
                penalty += 15
            record["Confidence"] = max(0, 100 - penalty)
            records.append(record)

    for row_idx in range(header_idx + 1, len(frame)):
        row = frame.iloc[row_idx]
        summary_kind = summary_rows.get(row_idx + 1)
        if summary_kind:
            if summary_kind == "header":
                finalize()
                group = None
                collecting = None
            fragment(row_idx, row, "corroborating", f"container_summary_{summary_kind}")
            continue
        repeated, repeated_duplicates, repeated_unit = _map_header(row.tolist(), cfg)
        if "container_no" in repeated and len(repeated) >= 4:
            if repeated != columns or repeated_duplicates or repeated_unit != default_unit:
                finding = issue("VINAFCO_HEADER_CHANGED",
                    "Tiêu đề lặp thay đổi vị trí/tập cột hoặc đơn vị trọng lượng. Đã dừng đọc vùng phía sau; "
                    "hãy tách/chọn đúng một bảng manifest thống nhất rồi xử lý lại.",
                    severity="error", source_sheet=sheet_name, source_row=row_idx + 1)
                finding["details"] = {"initial_columns": dict(columns), "new_columns": repeated,
                                      "initial_weight_unit": default_unit, "new_weight_unit": repeated_unit,
                                      "duplicate_fields": repeated_duplicates}
                issues.append(finding)
                metadata["unparsed_after_header_row"] = row_idx + 1
                fragment(row_idx, row, "unresolved", "header_schema_or_unit_changed")
                for pending_idx in range(row_idx + 1, len(frame)):
                    fragment(pending_idx, frame.iloc[pending_idx], "unresolved", "after_changed_header")
                break
            fragment(row_idx, row, "ignored", "identical_table_header")
            continue
        raw = _raw_row(row, columns)
        native = {name: row.iloc[index] for name, index in columns.items()}
        raw["weight_header"] = weight_header
        party = raw["party_raw"]
        marker = _PARTY.match(party)
        container_raw = raw["container_no"]
        cont_compact = _container_key(container_raw)
        valid_container = bool(_CONTAINER.fullmatch(cont_compact))
        footer = _is_footer(raw)
        if footer:
            fragment(row_idx, row, "ignored", "known_total_footer")
            continue
        attributes = _has_container_attributes(raw)
        party_continuation = bool(group is not None and collecting and party and not container_raw and not attributes)
        known_party_context = bool(marker or party_continuation)
        if marker and marker.group(1).upper() == "S":
            finalize()
            group = new_group()
            collecting = "S"
            name = re.sub(r",\s*\d{2}'?[A-Z]{2,3}\s*$", "", marker.group(2).strip(), flags=re.I)
            group["S"].append(name)
            group["soc"] = bool(_SOC.search(party))
        elif marker:
            if group is None:
                group = new_group(orphan=True)
            collecting = marker.group(1).upper()
            group[collecting] = [marker.group(2).strip()]
        elif party_continuation:
            group[collecting].append(party)
            if collecting == "S" and _SOC.search(party):
                group["soc"] = True
        incomplete_candidate = bool(not container_raw and attributes and not known_party_context)
        if group is None and (container_raw or incomplete_candidate):
            group = new_group(orphan=True)
        if group is not None and party:
            group["party_rows"].append({"source_row": row_idx + 1,
                "party_raw": party, "bill_no": raw["bill_no"]})
        if group is not None and raw["bill_no"]:
            group["bill"] = raw["bill_no"]
            group["bills"].add(raw["bill_no"])
        if not container_raw and not incomplete_candidate:
            fragment(row_idx, row, "corroborating" if known_party_context or raw["bill_no"] else "ignored",
                     "party_or_bill_context" if known_party_context or raw["bill_no"] else "non_container_note")
            continue
        # Keep rows with populated container attributes even if the identifier is
        # absent. They must be repaired or explicitly excluded, never disappear.
        if group is None:
            group = new_group(orphan=True)
        collecting = None
        weight = parse_weight(native.get("gw"), default_unit=default_unit, number_format=cfg["number_format"])
        # The unit in a populated cell can override the header. Keep the unit
        # actually used by parse_weight; an unreadable weight has no such evidence.
        raw["weight_source_unit"] = weight["source_unit"] if weight is not None else None
        fe, fe_notes, rules, inferred_fe = _fe(raw["comm"], weight, raw["type"], cfg)
        soc = group["soc"] or bool(_SOC.search(raw["remarks"])) or bool(_SOC.search(raw["comm"]))
        vtos, cargo = _derived(raw["type"], fe, cfg)
        record = {
            "record_id": f"VINAFCO:{sheet_name}:{row_idx + 1}",
            "BL_No": group["bill"], "Master_BL_Group_ID": group["id"],
            "Container_No": cont_compact if valid_container else container_raw,
            "Seal_No": raw["seal"], "Size_Type": raw["type"], "VTOS_Size": vtos,
            "Operator": cfg["operator_soc"] if soc else cfg["operator_coc"],
            "FE_Status": fe, "Weight_Value": weight["value"] if weight else None,
            "Weight_Unit": "TONS" if weight else None, "Weight_Kind": cfg["weight_kind"],
            "Description": normalize_text(raw["comm"]), "Cargo_Type": cargo,
            "Confidence": None, "Warning": "", "source_file": str(source),
            "source_sheet": sheet_name, "source_row": row_idx + 1, "raw": raw,
            "rules": ["VINAFCO_PARTY_BLOCK", "VINAFCO_OPERATOR_SOC" if soc else "VINAFCO_OPERATOR_COC", *rules],
            "_inferred_fe": inferred_fe,
        }
        fragment(row_idx, row, "parsed" if valid_container else "unresolved",
                 "container_record" if valid_container else "missing_or_invalid_container")
        if not container_raw:
            record["rules"].append("VINAFCO_INCOMPLETE_CONTAINER_CANDIDATE")
            add(record, "VINAFCO_CONTAINER_MISSING",
                "Dòng có kích cỡ/seal/trọng lượng/mô tả nhưng thiếu số container; giữ dòng để đối chiếu, "
                "bổ sung mã hoặc loại có lý do.", "error", "Container_No")
        elif not valid_container:
            add(record, "VINAFCO_CONTAINER_UNPARSED", "Ô số container không đúng dạng 4 chữ + 7 số; giữ nguyên giá trị để kiểm tra.", "error", "Container_No")
        elif cont_compact != container_raw:
            record["rules"].append("CONTAINER_WHITESPACE_CASE_NORMALIZED")
        if weight is None:
            add(record, "VINAFCO_WEIGHT_INVALID", "Thiếu trọng lượng hoặc không đọc được số và đơn vị; không tự thay bằng 0.", "error", "Weight_Value")
        if not vtos or cargo == "UNKNOWN":
            add(record, "VINAFCO_TYPE_UNMAPPED", "Kích cỡ chưa có ánh xạ VTOS/loại hàng được xác nhận.", "error", "Size_Type")
        if soc and (_COC.search(raw["remarks"]) or _COC.search(raw["comm"])):
            add(record, "VINAFCO_SOC_COC_CONFLICT", "Có dấu hiệu SOC và COC cùng xuất hiện; cần xác nhận hãng khai thác.", "error", "Operator")
        for code, severity, message in fe_notes:
            add(record, code, message, severity, "FE_Status",
                ["FE_Status", "Weight_Value"] if code == "VINAFCO_FE_CONFLICT" else None)
        group["records"].append(record)
    finalize()
    _reconcile(records, metadata, blocks, issues)
    metadata["records_detected"] = len(records)
    metadata["coverage"] = {"source_fragments": len(fragments),
        **{f"{status}_fragments": sum(item["status"] == status for item in fragments)
           for status in ("parsed", "unresolved", "ignored", "corroborating")}}
    if not records:
        issues.append(issue("VINAFCO_NO_CONTAINERS", "Không tìm thấy container trong bảng manifest đã chọn.", severity="error"))
    if progress:
        progress(90, f"Đã đọc {len(records)} dòng container VINAFCO.")
    return result
