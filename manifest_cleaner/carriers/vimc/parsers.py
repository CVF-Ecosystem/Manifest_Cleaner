"""VIMC row grammars, derived from the existing 03e0d34 implementation.

The input carrier is chosen by the user. Row layouts are recognized from their
structure, never the input filename or vessel name. Legacy regex exports are
retained for compatibility tests; the adapter uses the stricter structural parser.
"""
from __future__ import annotations

import re
from .mappings import SIZE_TO_ISO, SIZE_TO_VTOS
from ...common import parse_weight, seal_text

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
    return seal_text(value) or None


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


def _size_text(value):
    return str(value).strip(" ,;:/").upper()


def is_size_token(value):
    size = _size_text(value)
    return size in _KNOWN_TYPES or bool(_SIZE_SHAPE.fullmatch(size))


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


def _segments(text, matches):
    return [(match.group().upper(), (text[match.start():matches[i + 1].start()]
             if i + 1 < len(matches) else text[match.start():]).strip(" ;|"))
            for i, match in enumerate(matches)]


def split_container_segments(text):
    """Keep strict and structurally recognizable damaged container candidates."""
    return _segments(text or "", _container_matches(text or ""))


def split_detail_segments(text, *, marked_containers=()):
    """A container-shaped token before the detail's size can be a seal."""
    source = text or ""
    candidates = _container_matches(source)
    details = []
    for index, candidate in enumerate(candidates):
        if details and candidate.group().upper() not in marked_containers:
            prefix = source[details[-1].end():candidate.start()]
            end = candidates[index + 1].start() if index + 1 < len(candidates) else len(source)
            suffix = source[candidate.end():end]
            fields = suffix.rstrip(" ;|").split()
            # Treat the second identifier as the sole seal only when it
            # immediately precedes the size and a complete weight layout.
            # An already populated prefix or suffix seal implies competing detail.
            if (not prefix.removeprefix("/").strip() and suffix[:1].isspace() and fields
                    and _detail_size_index(fields) == 0 and _size_text(fields[0]) in _KNOWN_TYPES
                    and any(_weight_layouts(fields[1:])) and not _adjacent_size_fits(fields, 0)):
                continue
        details.append(candidate)
    return _segments(source, details)


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


def _weight_layouts(tokens):
    first = _weight_edge(tokens, True)
    last = _weight_edge(tokens, False)
    # A single numeric token is an incomplete line.
    return first if first and first[1] else None, last if last and last[1] else None


def _weight_candidates(tokens):
    first, last = _weight_layouts(tokens)
    return [{"layout": layout, "weight_raw": value[0], "source_unit": unit, "description": " ".join(value[1])}
            for layout, unit, value in (("weight_first_tons", "TONS", first), ("description_first_kg", "KGS", last))
            if value]


def _adjacent_size_fits(tokens, size_index):
    following = size_index + 1
    return (following < len(tokens) and _size_text(tokens[following]) in _KNOWN_TYPES
            and any(_weight_layouts(tokens[following + 1:])))


def _detail_size_index(tokens):
    positions = [idx for idx, token in enumerate(tokens[:6]) if is_size_token(token)]
    if not positions:
        return None
    first = positions[0]
    if _size_text(tokens[first]) in _KNOWN_TYPES:
        # Preserve an established size layout. Two adjacent supported codes
        # can be a literal seal and its type when only the latter fits.
        if _adjacent_size_fits(tokens, first) and not any(_weight_layouts(tokens[first + 1:])):
            return first + 1
        return first
    # An unsupported size-shaped token can still be part of the seal.
    # Keep the original candidate for review when no known type has a layout.
    return next((idx for idx in positions[1:] if _size_text(tokens[idx]) in _KNOWN_TYPES
                 and any(_weight_layouts(tokens[idx + 1:]))), first)


def parse_structured_line(line):
    """Return source fields plus layout/ambiguity, without discarding failures.

    Numeric values at both ends of the goods/weight tail are ambiguous: the
    weight-first-tonnes and description-first-kg layouts both fit. No vessel
    hint resolves this case and no weight is guessed.
    """
    candidates = split_detail_segments(line)
    if not candidates:
        return None
    container, segment = candidates[0]
    fields = segment[len(container):].removeprefix("/").lstrip()
    positions = list(re.finditer(r"\S+", fields))
    tokens = [match.group() for match in positions]
    size_index = _detail_size_index(tokens)
    result = {"container_no": container, "seal_no": None, "size_type": None,
              "description": "", "weight_raw": None, "weight_unit": None,
              "layout": "unparsed", "raw_line": line, "ambiguous_candidates": []}
    if size_index is None:
        return result
    result["size_type"] = _size_text(tokens[size_index])
    result["seal_no"] = clean_seal_number(fields[:positions[size_index].start()].rstrip())
    tail = tokens[size_index + 1:]
    layouts = _weight_candidates(tail)
    if layouts and result["size_type"] in _KNOWN_TYPES and _adjacent_size_fits(tokens, size_index):
        alternatives = [
            {**candidate, "size_type": _size_text(tokens[index]),
             "seal_no": clean_seal_number(fields[:positions[index].start()].rstrip())}
            for index in (size_index, size_index + 1)
            for candidate in _weight_candidates(tokens[index + 1:])
        ]
        result.update(layout="seal_type_ambiguous", description=layouts[0]["description"],
                      ambiguous_candidates=alternatives)
        if len({(item["weight_raw"], item["source_unit"]) for item in alternatives}) == 1:
            result.update(weight_raw=layouts[0]["weight_raw"], weight_unit=layouts[0]["source_unit"])
    elif len(layouts) > 1:
        result.update(layout="ambiguous", description=" ".join(tail), ambiguous_candidates=layouts)
    elif layouts:
        choice = layouts[0]
        result.update(layout=choice["layout"], weight_raw=choice["weight_raw"], weight_unit=choice["source_unit"],
                      description=choice["description"])
    else:
        result["description"] = " ".join(tail)
    return result
