"""VIMC row grammars, derived from the existing 03e0d34 implementation.

The input carrier is chosen by the user. Row layouts are recognized from their
structure, never the input filename or vessel name. Legacy regex exports are
retained for compatibility tests; the adapter uses the stricter structural parser.
"""
from __future__ import annotations

import re
from .mappings import SIZE_TO_ISO, SIZE_TO_VTOS
from ...common import parse_weight

CONTAINER_PATTERN = re.compile(r"^[A-Z]{4}\d{4,7}$", re.I)
CONTAINER_CANDIDATE = re.compile(r"(?<![A-Z0-9])[A-Z]{4}\d{4,10}(?![A-Z0-9])", re.I)
# Candidate discovery is deliberately broader than identifier validation. A
# damaged identifier must remain editable, not vanish before validation runs.
_LOOSE_CONTAINER_CANDIDATE = re.compile(
    r"(?<![A-Z0-9])(?P<prefix>[A-Z]{3,5})(?P<separator>[ \t-]*)(?P<digits>\d{4,10})(?![A-Z0-9])", re.I)
_NON_CONTAINER_PREFIXES = {"TOTAL", "TONG", "SEAL", "BILL", "GROSS", "CARGO", "PORT", "DATE", "PHONE", "FAX", "TEL"}
MARINER_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"
    r"(?:(?P<seal_no>[A-Z0-9]+)\s+)?"
    r"(?P<size_type>[A-Z0-9\']{2,5})\s+"
    r"(?P<description>.+?)\s+(?P<weight>[\d\.,]+)\s*$", re.I | re.U)
PIONEER_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"
    r"(?:(?P<seal_no>.+?)\s+)?"
    r"(?P<size_type>[A-Z0-9\']{2,5})(?=\s+[\d\.,])"
    r"\s+(?P<weight>[\d\.,]+)\s+(?P<description>.+)$", re.I | re.U)
DANANG_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"
    r"(?P<seal_no>[A-Z0-9]+)\s+"
    r"(?P<size_type>(?:20|40|45)(?:DC|GP|HC|HQ|TK|RF|RH|OT|FR))\s+"
    r"(?P<description>.+?)\s+(?P<weight>\d{3,})\s*$", re.I | re.U)
STOP_KEYWORDS_PATTERN = re.compile(r"\b(ADD(?:RESS)?|TEL|FAX|EMAIL|PHONE|MOBILE|CONTACT)\b", re.I)
_KNOWN_TYPES = set(SIZE_TO_ISO) | set(SIZE_TO_VTOS)
_SIZE_SHAPE = re.compile(r"(?:\d{2}'?[A-Z]{1,4}|(?:[24][245]|L5)[A-Z]\d|20|40|45)$", re.I)
_NUMBER = re.compile(r"[+-]?\d[\d.,]*(?:KGS?|KILOGRAMS?|TONNES?|TONS?|MT|T)?$", re.I)
_UNIT = re.compile(r"(?:KGS?|KILOGRAMS?|TONNES?|TONS?|MT|T)$", re.I)


def is_valid_container(value):
    return bool(value and CONTAINER_PATTERN.fullmatch(str(value).strip()))


def clean_seal_number(value):
    text = str(value).strip().upper() if value is not None else ""
    return None if text in {"", "N/A", "NA", "-"} else text


def _legacy_match(pattern, line, unit):
    match = pattern.match((line or "").strip())
    if not match:
        return None
    data = match.groupdict()
    return {"container_no": data["container_no"].upper(),
            "seal_no": clean_seal_number(data.get("seal_no")),
            "size_type": data["size_type"].upper(), "description": data["description"].strip(),
            "weight_raw": data["weight"].strip(), "weight_unit": unit}


def parse_mariner_container_detail(line):
    return _legacy_match(MARINER_CONTAINER_DETAIL_PATTERN, line, "KGS")


def parse_pioneer_container_detail(line):
    return _legacy_match(PIONEER_CONTAINER_DETAIL_PATTERN, line, "TONS")


def parse_danang_container_detail(line):
    return _legacy_match(DANANG_CONTAINER_DETAIL_PATTERN, line, "KGS")


def parse_weight_kg(value):
    result = parse_weight(value, default_unit="KGS")
    return result["value"] if result is not None else None


def parse_weight_tons(value):
    result = parse_weight(value, default_unit="TONS")
    return result["value"] if result is not None else None


def is_size_token(value):
    value = str(value).strip(" ,;:/").upper()
    return value in _KNOWN_TYPES or bool(_SIZE_SHAPE.fullmatch(value))


def _strong_size(text):
    return any(is_size_token(token) and any(char.isalpha() for char in token)
               for token in re.split(r"[\s/]+", text)[:6])


def _container_matches(text):
    """Find strict identifiers and structurally supported damaged candidates.

    Loose matches need a nearby size and a row/segment boundary. This keeps a
    three-letter seal (VMC1234567) inside a good container row from becoming a
    second container. No damaged identifier is silently repaired here.
    """
    matches = []
    for match in _LOOSE_CONTAINER_CANDIDATE.finditer(text):
        raw = match.group()
        if CONTAINER_CANDIDATE.fullmatch(raw):
            matches.append(match)
            continue
        prefix = match.group("prefix").upper()
        if prefix in _NON_CONTAINER_PREFIXES:
            continue
        if len(match.group("digits")) != 7:
            continue
        before = text[:match.start()].strip()
        at_boundary = not before or before.endswith((";", "|"))
        if matches:
            at_boundary = at_boundary or _strong_size(text[matches[-1].end():match.start()])
        if at_boundary and _strong_size(text[match.end():].lstrip(" /;|\t")):
            matches.append(match)
    return matches


def split_container_segments(text):
    """Keep strict and structurally recognizable damaged container candidates."""
    matches = _container_matches(text or "")
    return [(match.group().upper(), (text[match.start():matches[i + 1].start()]
             if i + 1 < len(matches) else text[match.start():]).strip(" ;|"))
            for i, match in enumerate(matches)]


def parse_marks_container(line):
    output = []
    for container, segment in split_container_segments(line):
        tail = segment[len(container):].strip(" /;|\t")
        tokens = re.split(r"[\s/]+", tail)
        size = next((token.upper().strip(" ,;:") for token in tokens if is_size_token(token)), None)
        output.append({"container_no": container, "size_type": size, "raw": segment})
    return output


def _weight_edge(tokens, first):
    if not tokens:
        return None
    if first:
        if _NUMBER.fullmatch(tokens[0]):
            count = 2 if len(tokens) > 1 and _UNIT.fullmatch(tokens[1]) else 1
            return " ".join(tokens[:count]), tokens[count:]
    else:
        if _NUMBER.fullmatch(tokens[-1]):
            return tokens[-1], tokens[:-1]
        if len(tokens) > 1 and _UNIT.fullmatch(tokens[-1]) and _NUMBER.fullmatch(tokens[-2]):
            return " ".join(tokens[-2:]), tokens[:-2]
    return None


def parse_structured_line(line):
    """Return source fields plus layout/ambiguity, without discarding failures.

    Numeric values at both ends of the goods/weight tail are ambiguous: the
    weight-first-tonnes and description-first-kg layouts both fit. No vessel
    hint resolves this case and no weight is guessed.
    """
    candidates = split_container_segments(line)
    if not candidates:
        return None
    container, segment = candidates[0]
    tokens = segment[len(container):].strip(" /\t").split()
    size_index = next((i for i, token in enumerate(tokens[:6]) if is_size_token(token)), None)
    result = {"container_no": container, "seal_no": None, "size_type": None,
              "description": "", "weight_raw": None, "weight_unit": None,
              "layout": "unparsed", "raw_line": line, "ambiguous_candidates": []}
    if size_index is None:
        return result
    result["size_type"] = tokens[size_index].strip(" ,;:/").upper()
    result["seal_no"] = clean_seal_number(" ".join(tokens[:size_index]))
    tail = tokens[size_index + 1:]
    first = _weight_edge(tail, True)
    last = _weight_edge(tail, False)
    # A single numeric token is an incomplete line, not two viable layouts.
    first_valid = first is not None and bool(first[1])
    last_valid = last is not None and bool(last[1])
    if first_valid and last_valid:
        result["layout"] = "ambiguous"
        result["description"] = " ".join(tail)
        result["ambiguous_candidates"] = [
            {"layout": "weight_first_tons", "weight_raw": first[0], "source_unit": "TONS", "description": " ".join(first[1])},
            {"layout": "description_first_kg", "weight_raw": last[0], "source_unit": "KGS", "description": " ".join(last[1])},
        ]
    elif first_valid:
        result.update(layout="weight_first_tons", weight_raw=first[0], weight_unit="TONS", description=" ".join(first[1]))
    elif last_valid:
        result.update(layout="description_first_kg", weight_raw=last[0], weight_unit="KGS", description=" ".join(last[1]))
    else:
        result["description"] = " ".join(tail)
    return result
