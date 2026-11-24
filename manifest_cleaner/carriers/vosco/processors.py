"""Data processing functions for manifest data.

This module contains functions for processing and transforming
manifest data, including F/E determination, name cleaning, and
description refinement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .mappings import (
    SIZE_TYPE_TO_CARGO_TYPE_BASE,
    TARE_WEIGHTS_TONS,
    SAFETY_MARGIN_TONS,
    TANK_TARE_WEIGHTS_TONS,
    TANK_WEIGHT_WARNING_RANGE,
)
from .parsers import (
    EMPTY_DESC_PATTERN,
    STOP_KEYWORDS_PATTERN,
    SINGLE_ITEM_PARSE_PATTERN,
)

from ...common import is_explicit_empty

logger = logging.getLogger(__name__)


class StructureType(Enum):
    """Enum for different manifest description structure types."""
    LINE_ALIGNED = auto()    # Each container line maps 1-1 to description line
    QUANTITY_BASED = auto()  # Description has quantity pattern like "(01) x20'DC"
    SHARED_SINGLE = auto()   # Single shared description for all containers


@dataclass
class DescriptionMatch:
    """Result of description matching with confidence and warning info."""
    description: str           # Matched description text
    confidence: int            # Confidence score: 100=exact, 80=quantity, 50=fallback
    warning: str = ""          # Warning message if any issue detected
    match_type: str = ""       # "LINE_ALIGNED", "QUANTITY_BASED", "SHARED", "FALLBACK"
    source_lines: tuple[int, ...] = ()  # 1-based lines within the original source cell



# Pattern to match "EMPTY" as standalone item in comma-separated list
EMPTY_ITEM_PATTERN = re.compile(r'\bEMPTY\b', re.IGNORECASE)

# Pattern to match cargo item with quantity and container type
# Example: "GACH MEN (01) x20'DC COC" -> ("GACH MEN", 1, "20DC")
CARGO_QTY_PATTERN = re.compile(
    r"([A-Za-zÀ-ỹ\s\-/\.()]+?)"  # Cargo name (including Vietnamese chars)
    r"\s*\((\d+)\)\s*"           # Quantity in parentheses like (01)
    r"x?\s*(\d{2})'?([A-Z0-9]{1,4})"  # Container type: xNN'XX or xNNXX
    r"\s*(?:COC|SOC)?",           # Optional COC/SOC marker
    re.IGNORECASE | re.UNICODE
)

# Pattern to match quantity-only segments (no cargo name)
# Example: "(01) X40'HC SOC" -> (1, "40HC")
QTY_ONLY_PATTERN = re.compile(
    r"^\s*\((\d+)\)\s*"           # Quantity in parentheses like (01)
    r"x?\s*(\d{2})'?([A-Z0-9]{1,4})"  # Container type: xNN'XX or xNNXX
    r"\s*(?:COC|SOC)?\s*$",       # Optional COC/SOC marker
    re.IGNORECASE
)

# Header lines to skip when counting containers
CONTAINER_HEADER_PATTERNS = ['FCL/FCL', 'CY-CY', 'CY/CY', 'FCL/CY', 'CY/FCL']

# Pattern to detect container info in description (not actual cargo description)
# Example: "VAN EP (02) X20'DC SOC", "EMPTY (04) X40'RF SOC"
# This indicates the description contains container packing info, not cargo
CONTAINER_INFO_DESC_PATTERN = re.compile(
    r"""
    (?:
        # Match patterns like: "VAN EP (02) X20'DC SOC" or "EMPTY (04) X40'RF SOC"
        [A-Za-zÀ-ỹ\s]+                    # Cargo name (VAN EP, EMPTY, etc.)
        \s*\(\d{1,2}\)\s*                 # Quantity (01), (02), etc.
        x?\s*\d{2}'?[A-Z]{2,4}            # Container type: X20'DC, 40'RF, etc.
        \s*(?:SOC|COC)?                   # Optional SOC/COC marker
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.UNICODE
)

# Keywords that indicate description is container packing info, not cargo
CONTAINER_PACKING_KEYWORDS = ['SOC', 'COC', "X20'", "X40'", "X45'"]


def classify_description_lines(description_text: str) -> List[dict]:
    """One source-preserving classification for counting and assigning cargo.

    Do not test 'PORT ' as an arbitrary substring: TRANSPORT EQUIPMENT is cargo.
    Metadata lines remain in the evidence even when excluded from assignment.
    """
    entries = []
    for number, raw_line in enumerate((description_text or "").splitlines(), 1):
        text = raw_line.strip()
        if not text:
            kind = "blank"
        elif re.match(r"^(?:PORT(?:\s+OF\s+(?:LOADING|DISCHARGE))?|POL|POD)(?:\s|[:,])", text, re.I):
            kind = "port"
        elif re.match(r"^(?:GRAND\s+)?TOTAL(?:\s|:|$)", text, re.I):
            kind = "total"
        elif re.match(r"^(?:SEE\s+)?ATTACHED\s+LIST\b", text, re.I):
            kind = "attachment"
        elif CARGO_QTY_PATTERN.search(text):
            kind = "quantity"
        else:
            kind = "cargo"
        entries.append({"source_line": number, "text": raw_line, "kind": kind})
    return entries


def detect_description_structure(
    container_text: str,
    description_text: str
) -> StructureType:
    """Detect the structure type of manifest description.
    
    Analyzes container and description text to determine how they are organized:
    - LINE_ALIGNED: Each container line maps 1-1 to a description line
    - QUANTITY_BASED: Description has quantity pattern like "(01) x20'DC"
    - SHARED_SINGLE: Single description shared by all containers
    
    Detection priority:
    1. LINE_ALIGNED - if container and description line counts match (most explicit)
    2. QUANTITY_BASED - if quantity pattern exists (e.g., "(01) x20'DC COC")
    3. SHARED_SINGLE - fallback
    
    Args:
        container_text: Multi-line container text from manifest
        description_text: Description text from manifest
        
    Returns:
        StructureType enum value
    """
    if not container_text or not description_text:
        return StructureType.SHARED_SINGLE
    
    # Split and count container lines (excluding headers)
    container_lines = [
        ln.strip() for ln in container_text.split('\n') 
        if ln.strip() and ln.strip() not in CONTAINER_HEADER_PATTERNS
    ]
    
    entries = classify_description_lines(description_text)
    description_lines = [entry["text"].strip() for entry in entries if entry["kind"] == "cargo"]
    
    container_count = len(container_lines)
    desc_count = len(description_lines)
    
    # FIRST: Check for LINE_ALIGNED structure
    # Only equal counts establish a positional match. Never accept a ±2 gap.
    if container_count > 1 and desc_count > 1:
        if container_count == desc_count:
            return StructureType.LINE_ALIGNED
    
    # SECOND: Check for QUANTITY_BASED pattern in description
    # This is for cases like "GACH MEN (01) x20'DC COC, PHAN BON (02) x40'HC COC"
    if CARGO_QTY_PATTERN.search(description_text):
        return StructureType.QUANTITY_BASED
    
    # THIRD: Default to SHARED_SINGLE (all containers share same description)
    return StructureType.SHARED_SINGLE


def get_line_aligned_descriptions(
    container_lines: List[str],
    description_text: str,
    fe_statuses: Optional[List[str]] = None
) -> List[str]:
    """Extract descriptions aligned by line index with containers.
    
    For manifests where each container line maps 1-1 to a description line,
    this function extracts the corresponding description for each container.
    
    Args:
        container_lines: List of parsed container line strings
        description_text: Full description text from manifest
        fe_statuses: Optional list of F/E statuses for fallback handling
        
    Returns:
        List of descriptions matched to containers by line index
        
    Example:
        Container (line 1): BEAU4377577/208714/40HC-C  ->  Description (line 1): SU VE SINH
        Container (line 2): BEAU4378043/22259428/40HC-C  ->  Description (line 2): VAN EP
    """
    if not container_lines:
        return []
    
    n = len(container_lines)
    result = [""] * n
    
    if not description_text or pd.isna(description_text):
        return result
    
    entries = [entry for entry in classify_description_lines(description_text) if entry["kind"] == "cargo"]
    actual_indices = [i for i, line in enumerate(container_lines)
                      if line.strip() and line.strip().upper() not in CONTAINER_HEADER_PATTERNS]
    # Positional matching is only established by the same classified list used
    # above. A mismatch must use the explicitly labelled fallback path.
    if len(actual_indices) != len(entries):
        return result
    for index, entry in zip(actual_indices, entries):
        result[index] = entry["text"].strip()
    return result


def split_shared_description(description: str, fe_status: str) -> str:
    """Split shared description based on F/E status.
    
    When multiple containers share a line with description like "EMPTY, THIT",
    this function assigns the correct description based on F/E status:
    - If E (Empty): return "EMPTY"
    - If F (Full): return non-EMPTY items
    
    Args:
        description: Original description text (e.g., "EMPTY, THIT")
        fe_status: F/E status of the container ("F" or "E")
        
    Returns:
        Refined description appropriate for the container's F/E status
        
    Example:
        >>> split_shared_description("EMPTY, THIT", "E")
        'EMPTY'
        >>> split_shared_description("EMPTY, THIT", "F")
        'THIT'
        >>> split_shared_description("FROZEN FISH", "F")
        'FROZEN FISH'
    """
    if not description or pd.isna(description):
        return ""
    
    desc_str = str(description).strip()
    if not desc_str:
        return ""
    
    # Split by comma
    parts = [p.strip() for p in desc_str.split(",") if p.strip()]
    
    if len(parts) <= 1:
        # Single item, no splitting needed
        return desc_str
    
    # Check if "EMPTY" is one of the items
    has_empty = any(EMPTY_ITEM_PATTERN.fullmatch(p) for p in parts)
    
    if not has_empty:
        # No EMPTY in list, return as-is
        return desc_str
    
    # Has EMPTY and other items - split based on F/E status
    fe_val = str(fe_status or "").upper()
    
    if fe_val == "E":
        # Empty container: return just "EMPTY"
        return "EMPTY"
    else:
        # Full container: return non-EMPTY items
        non_empty_parts = [p for p in parts if not EMPTY_ITEM_PATTERN.fullmatch(p)]
        if non_empty_parts:
            return ", ".join(non_empty_parts)
        else:
            # Fallback if only EMPTY items
            return desc_str


def determine_fe(
    description: Optional[str],
    weight_info: Optional[Dict[str, Any]],
    size_type: Optional[str],
    *, weight_kind: str = "unknown"
) -> str:
    """Determine Full/Empty status of a container.
    
    An explicit whole EMPTY status takes precedence, with contradictory
    weights reported by the adapter. Otherwise retain VOSCO's weight/tare
    inference using normalized tonnes and the appropriate tank tare, then F.
    
    Args:
        description: Cargo description text
        weight_info: Dictionary with 'value' (float) and 'unit' (str)
        size_type: Container size/type code (e.g., "40HC")
        
    Returns:
        "F" for Full, "E" for Empty
        
    Example:
        >>> determine_fe("EMPTY CONTAINER", {"value": 4.0, "unit": "TONS"}, "40HC")
        'E'
        >>> determine_fe("FROZEN FISH", {"value": 25.0, "unit": "TONS"}, "40HC")
        'F'
    """
    if weight_kind not in ("gross", "cargo", "unknown"):
        raise ValueError("weight_kind của VOSCO chỉ nhận gross, cargo hoặc unknown.")
    # Explicit source status wins. The adapter reports contradictory mass as a
    # review warning, instead of silently changing an explicit EMPTY to FULL.
    if is_explicit_empty(description):
        return "E"

    if weight_kind == "cargo":
        # Payload is not gross mass and must never be compared with container
        # tare. Positive cargo mass implies F; a zero without explicit EMPTY is
        # kept as F for review, rather than inventing an empty declaration.
        return "F"

    if weight_info and weight_info.get("unit") == "TONS":
        gross_weight = weight_info.get("value")
        if gross_weight is not None:
            gross_weight = float(gross_weight)
            kind = str(size_type or "").upper()
            tare = TANK_TARE_WEIGHTS_TONS.get(kind,
                TARE_WEIGHTS_TONS.get(kind[:2]))
            if tare is not None and gross_weight > tare + SAFETY_MARGIN_TONS:
                return "F"
            if gross_weight < 0.1 or (tare is not None and gross_weight <= tare):
                return "E"

    # Preserve the established VOSCO fallback; adapter records the inference.
    return "F"



def clean_consignee_name(full_consignee_text: str) -> str:
    """Extract clean consignee name from full text.
    
    Removes contact information (phone, email, address, etc.)
    and keeps only the company/person name.
    
    Args:
        full_consignee_text: Full consignee text with contact info
        
    Returns:
        Cleaned consignee name
        
    Example:
        >>> clean_consignee_name("ABC COMPANY Tel: 123456 Email: a@b.com")
        'ABC COMPANY'
    """
    if not full_consignee_text or pd.isna(full_consignee_text):
        return ""
    
    first_line = full_consignee_text.split("\n")[0].strip()
    
    # Find where contact info starts
    stop_match = STOP_KEYWORDS_PATTERN.search(first_line)
    stop_index = stop_match.start() if stop_match else -1
    
    # Get name before contact info
    cleaned_name = first_line[:stop_index].strip() if stop_index != -1 else first_line
    
    # Remove trailing punctuation
    return cleaned_name.rstrip(";,./\\- ")


def get_cargo_type(size_type: str, fe_status: str) -> str:
    """Determine cargo type based on container type and F/E status.
    
    Args:
        size_type: Container size/type code (e.g., "40HC", "20RF")
        fe_status: Full/Empty status ("F" or "E")
        
    Returns:
        Cargo type string (e.g., "GENERAL", "EMPTY", "REEFER", "EMPTY REEFER")
        
    Example:
        >>> get_cargo_type("40HC", "F")
        'GENERAL'
        >>> get_cargo_type("40HC", "E")
        'EMPTY'
        >>> get_cargo_type("20RF", "F")
        'REEFER'
    """
    size_type_val = str(size_type or "").upper()
    fe_val = str(fe_status or "").upper()
    
    base = SIZE_TYPE_TO_CARGO_TYPE_BASE.get(size_type_val, "GENERAL")
    
    if base != "GENERAL":
        # Special types: TANK, REEFER, FLATRACK, OPENTOP
        return f"EMPTY {base}" if fe_val == "E" else base
    else:
        # Standard dry containers
        return "EMPTY" if fe_val == "E" else "GENERAL"


def parse_cargo_items_with_qty(description: str) -> List[tuple]:
    """Parse cargo description to extract items with quantities and container types.
    
    Args:
        description: Raw description like "GACH MEN (01) x20'DC COC, PHAN BON (01) x20'DC COC"
        
    Returns:
        List of tuples: (cargo_name, quantity, container_type)
        Example: [("GACH MEN", 1, "20DC"), ("PHAN BON", 1, "20DC")]
    """
    if not description or pd.isna(description):
        return []
    
    desc_str = str(description).strip()
    items = []
    
    # Find all matches
    for match in CARGO_QTY_PATTERN.finditer(desc_str):
        cargo_name = match.group(1).strip()
        qty = int(match.group(2))
        size_prefix = match.group(3)  # e.g., "20"
        size_suffix = match.group(4).upper()  # e.g., "DC"
        container_type = f"{size_prefix}{size_suffix}"
        
        if cargo_name:
            items.append((cargo_name, qty, container_type))
    
    return items


def match_description_by_quantity(
    containers: List[Dict[str, Any]],
    description: str,
    fe_statuses: Optional[List[str]] = None
) -> List[str]:
    """Match cargo descriptions to containers based on quantity and order.
    
    When a manifest line has multiple cargo items with quantities like:
    "GACH MEN (01) x20'DC COC, PHAN BON (01) x20'DC COC"
    
    This function assigns each cargo to containers in order:
    - First 20DC container gets "GACH MEN"
    - Second 20DC container gets "PHAN BON"
    
    Args:
        containers: List of parsed container dicts with 'type' key
        description: Raw description text from manifest
        fe_statuses: Optional list of F/E statuses corresponding to containers
        
    Returns:
        List of descriptions matched to each container in order
        
    Example:
        >>> containers = [{"type": "20DC"}, {"type": "20DC"}, {"type": "40HC"}]
        >>> desc = "GACH MEN (01) x20'DC COC, PHAN BON (01) x20'DC COC, BIA (01) x40'HC COC"
        >>> match_description_by_quantity(containers, desc)
        ['GACH MEN', 'PHAN BON', 'BIA']
    """
    if not containers:
        return []
    
    n = len(containers)
    result = [""] * n
    
    # Parse cargo items with quantities
    cargo_items = parse_cargo_items_with_qty(description)
    
    if not cargo_items:
        # No quantity info found - fallback to original behavior
        # Use split_shared_description for each container
        for i, cont in enumerate(containers):
            fe = fe_statuses[i] if fe_statuses and i < len(fe_statuses) else "F"
            result[i] = split_shared_description(description, fe)
        return result
    
    # Group containers by type with their indices
    type_to_indices: Dict[str, List[int]] = {}
    for i, cont in enumerate(containers):
        cont_type = str(cont.get("type") or "").upper()
        if cont_type not in type_to_indices:
            type_to_indices[cont_type] = []
        type_to_indices[cont_type].append(i)
    
    # Track assignment position for each container type
    type_assign_pos: Dict[str, int] = {t: 0 for t in type_to_indices}
    
    # Assign cargo to containers in order
    for cargo_name, qty, cont_type in cargo_items:
        cont_type_upper = cont_type.upper()
        if cont_type_upper not in type_to_indices:
            continue
        
        indices = type_to_indices[cont_type_upper]
        start_pos = type_assign_pos[cont_type_upper]
        
        # Assign this cargo to 'qty' containers of this type
        for _ in range(qty):
            if start_pos >= len(indices):
                break
            idx = indices[start_pos]
            if not result[idx]:  # Don't overwrite if already assigned
                result[idx] = cargo_name
            start_pos += 1
        
        type_assign_pos[cont_type_upper] = start_pos
    
    # Fill any remaining empty slots with fallback
    for i, desc in enumerate(result):
        if not desc:
            fe = fe_statuses[i] if fe_statuses and i < len(fe_statuses) else "F"
            result[i] = split_shared_description(description, fe)
    
    return result


def match_descriptions_with_confidence(
    containers: List[Dict[str, Any]],
    container_text: str,
    description_text: str,
    fe_statuses: List[str],
    bl_no: str = ""
) -> List[DescriptionMatch]:
    """Match descriptions to containers with confidence scores and hybrid fallback.
    
    This is the enhanced matching function that:
    1. Detects structure type (LINE_ALIGNED, QUANTITY_BASED, SHARED_SINGLE)
    2. Applies matching with fallback chain
    3. Returns confidence scores and warnings
    
    Fallback chain:
    - LINE_ALIGNED (100%) -> QUANTITY_BASED (80%) -> SHARED (50%)
    
    Args:
        containers: List of parsed container dicts with 'type' key
        container_text: Raw multi-line container text
        description_text: Raw description text
        fe_statuses: List of F/E statuses
        bl_no: BL number for logging
        
    Returns:
        List of DescriptionMatch objects with description, confidence, warning
    """
    n = len(containers)
    if n == 0:
        return []
    
    results: List[DescriptionMatch] = []
    source_entries = classify_description_lines(description_text)
    cargo_entries = [entry for entry in source_entries if entry["kind"] in {"cargo", "quantity"}]
    clean_description = "\n".join(entry["text"].strip() for entry in cargo_entries)
    
    # Detect structure type
    structure = detect_description_structure(container_text, description_text)
    
    # Get container lines for line-aligned matching
    container_lines = [
        ln.strip() for ln in container_text.split('\n')
        if ln.strip() and ln.strip() not in CONTAINER_HEADER_PATTERNS
    ]
    
    # Log structure detection
    logger.debug(f"BL {bl_no}: Detected structure = {structure.name}, "
                 f"containers={n}, container_lines={len(container_lines)}")
    
    # Match based on structure type
    if structure == StructureType.LINE_ALIGNED:
        line_descs = get_line_aligned_descriptions(container_lines, description_text, fe_statuses)
        
        for i in range(n):
            desc = line_descs[i] if i < len(line_descs) else ""
            
            if desc and desc.strip():
                results.append(DescriptionMatch(
                    description=desc,
                    confidence=100,
                    match_type="LINE_ALIGNED"
                ))
            else:
                # Fallback to quantity-based for empty slot
                fallback_desc = _try_quantity_fallback(containers[i], clean_description)
                if fallback_desc:
                    logger.info(f"BL {bl_no}: Container {i+1} used QUANTITY fallback")
                    results.append(DescriptionMatch(
                        description=fallback_desc,
                        confidence=80,
                        warning="⚠️ Fallback từ quantity pattern",
                        match_type="QUANTITY_FALLBACK"
                    ))
                else:
                    # Final fallback to shared
                    fe = fe_statuses[i] if i < len(fe_statuses) else "F"
                    shared_desc = split_shared_description(clean_description, fe)
                    logger.warning(f"BL {bl_no}: Container {i+1} has empty description - using shared")
                    results.append(DescriptionMatch(
                        description=shared_desc,
                        confidence=50,
                        warning="⚠️ Description có thể không chính xác",
                        match_type="SHARED_FALLBACK"
                    ))
                    
    elif structure == StructureType.QUANTITY_BASED:
        qty_descs = match_description_by_quantity(containers, clean_description, fe_statuses)
        
        for i, desc in enumerate(qty_descs):
            # Check if this was a direct match or fallback
            cargo_items = parse_cargo_items_with_qty(clean_description)
            is_direct_match = any(desc == item[0] for item in cargo_items)
            
            if is_direct_match:
                results.append(DescriptionMatch(
                    description=desc,
                    confidence=80,
                    match_type="QUANTITY_BASED"
                ))
            else:
                results.append(DescriptionMatch(
                    description=desc,
                    confidence=50,
                    warning="⚠️ Description có thể không chính xác",
                    match_type="QUANTITY_FALLBACK"
                ))
    else:
        # SHARED_SINGLE
        for i in range(n):
            fe = fe_statuses[i] if i < len(fe_statuses) else "F"
            desc = split_shared_description(clean_description, fe)
            results.append(DescriptionMatch(
                description=desc,
                confidence=50 if n > 1 else 100,
                warning=("Mô tả dùng chung cho nhiều container; cần đối chiếu bản gốc."
                         if n > 1 else ""),
                match_type="SHARED_SINGLE"
            ))
    
    positional_entries = [entry for entry in source_entries if entry["kind"] == "cargo"]
    for index, result in enumerate(results):
        if result.match_type == "LINE_ALIGNED" and index < len(positional_entries):
            result.source_lines = (positional_entries[index]["source_line"],)
        else:
            result.source_lines = tuple(entry["source_line"] for entry in cargo_entries)
    # Validation: log warnings for potential issues
    _validate_matches(results, containers, bl_no)
    
    return results


def _try_quantity_fallback(container: Dict[str, Any], description_text: str) -> str:
    """Try to match a single container using quantity pattern as fallback."""
    cont_type = str(container.get("type") or "").upper()
    cargo_items = parse_cargo_items_with_qty(description_text)
    
    for cargo_name, qty, item_type in cargo_items:
        if item_type.upper() == cont_type:
            return cargo_name
    return ""


def _validate_matches(
    results: List[DescriptionMatch],
    containers: List[Dict[str, Any]],
    bl_no: str
) -> None:
    """Validate match results and log warnings if issues detected."""
    empty_count = sum(1 for r in results if not r.description or not r.description.strip())
    if empty_count > 0:
        logger.warning(f"BL {bl_no}: {empty_count}/{len(results)} containers have empty descriptions")
    
    low_conf_count = sum(1 for r in results if r.confidence < 80)
    if low_conf_count > 0:
        logger.info(f"BL {bl_no}: {low_conf_count}/{len(results)} containers have low confidence matches")


def validate_tank_weight_warning(
    size_type: str,
    weight_value: Optional[float],
    fe_status: str
) -> Optional[str]:
    """Check if tank container might be misclassified due to high tare weight.
    
    Tank containers have higher tare weight (5-6 tons for 20TK). If a tank is marked
    as Full with weight in the suspicious range (5-12 tons), it might actually be
    an empty tank being misclassified.
    
    Args:
        size_type: Container size/type code (e.g., "20TK")
        weight_value: Gross weight in tons
        fe_status: Current F/E classification ("F" or "E")
        
    Returns:
        Warning message if suspicious, None otherwise
    """
    if not size_type or not weight_value or fe_status != "F":
        return None
    
    size_type_upper = size_type.upper()
    
    # Check if this is a tank container
    if size_type_upper not in TANK_WEIGHT_WARNING_RANGE:
        return None
    
    min_weight, max_weight = TANK_WEIGHT_WARNING_RANGE[size_type_upper]
    
    # Check if weight is in suspicious range
    if min_weight <= weight_value <= max_weight:
        return f"⚠️ Tank {weight_value}T - kiểm tra lại F/E (có thể Empty)"
    
    return None


def validate_container_info_description(description: str) -> Tuple[Optional[str], Optional[str]]:
    """Check if description contains container packing info and extract cargo name.
    
    Detects patterns like "VAN EP (02) X20'DC SOC, (01) X40'HC SOC" and:
    1. Returns a warning for user to verify
    2. Extracts the cargo name (e.g., "VAN EP") so it can be applied to all containers
    
    Args:
        description: Description text to validate
        
    Returns:
        Tuple of (warning_message, extracted_cargo_name)
        - warning_message: Warning if suspicious, None otherwise
        - extracted_cargo_name: Extracted cargo name if found, None otherwise
    """
    if not description or pd.isna(description):
        return (None, None)
    
    desc_str = str(description).strip()
    desc_upper = desc_str.upper()
    
    # Check for container packing keywords (SOC, COC, X20', X40', X45')
    has_packing_keywords = any(kw in desc_upper for kw in CONTAINER_PACKING_KEYWORDS)
    
    if not has_packing_keywords:
        return (None, None)
    
    # Check if pattern matches container info structure
    if not CONTAINER_INFO_DESC_PATTERN.search(desc_str):
        return (None, None)
    
    # Parse segments to extract cargo names
    segments = [s.strip() for s in desc_str.split(',') if s.strip()]
    cargo_names = []
    has_empty = False
    
    for segment in segments:
        # Try to match cargo + qty pattern first
        match = CARGO_QTY_PATTERN.match(segment)
        if match:
            cargo = match.group(1).strip()
            if cargo:
                if cargo.upper() == 'EMPTY':
                    has_empty = True
                else:
                    cargo_names.append(cargo)
        else:
            # Check if this is a qty-only segment (no cargo name)
            if QTY_ONLY_PATTERN.match(segment):
                # This segment has no cargo name, skip
                continue
    
    # Determine extracted cargo
    extracted_cargo = None
    if cargo_names:
        # Use the first non-empty cargo name found
        # This handles cases like "VAN EP (02) X20'DC SOC, (01) X40'HC SOC"
        # where only the first segment has cargo name
        unique_cargos = list(dict.fromkeys(cargo_names))  # Remove duplicates, keep order
        extracted_cargo = unique_cargos[0] if len(unique_cargos) == 1 else ", ".join(unique_cargos)
    elif has_empty:
        # If only EMPTY was found, return "EMPTY" as the cleaned cargo
        # This handles cases like "EMPTY (04) X40'RF SOC, (01) X45'RF SOC" -> "EMPTY"
        extracted_cargo = "EMPTY"
    
    warning = "⚠️ Description có thể không chính xác (chứa thông tin container)"
    
    return (warning, extracted_cargo)


def refine_description_column(df: pd.DataFrame) -> pd.DataFrame:
    """Refine the 'Hàng hóa' (cargo description) column.
    
    Matches cargo descriptions to container types when multiple items
    are listed for different container types.
    
    Args:
        df: DataFrame with 'Hàng hóa' and optionally 'Kích cỡ' columns
        
    Returns:
        DataFrame with refined 'Hàng hóa' column
    """
    if "Hàng hóa" not in df.columns:
        return df

    has_size_column = "Kích cỡ" in df.columns
    refined: List[str] = []

    for _, row in df.iterrows():
        original = str(row.get("Hàng hóa", "") or "")
        row_container_full_type = str(row.get("Kích cỡ", "") or "") if has_size_column else ""
        
        if not original.strip():
            refined.append("")
            continue

        # Parse items from description
        parts = [p.strip() for p in original.split(", ") if p.strip()]
        parsed_items: List[tuple[str, Optional[str]]] = []
        
        for part in parts:
            match = SINGLE_ITEM_PARSE_PATTERN.fullmatch(part)
            if match:
                item_name = (match.group(1) or "").strip()
                item_cont_type = (match.group(2) or "").strip().replace("'", "") or None
                if item_name:
                    parsed_items.append((item_name, item_cont_type))
            else:
                parsed_items.append((part, None))

        if not parsed_items:
            refined.append(original.strip())
            continue

        if len(parsed_items) == 1:
            refined.append(parsed_items[0][0])
            continue

        # Multiple items: filter by container type
        normalized_row_cont_type = row_container_full_type.replace("'", "") if row_container_full_type else ""
        selected: List[str] = []
        no_type: List[str] = []
        
        for name, cont_type in parsed_items:
            if has_size_column and normalized_row_cont_type and cont_type:
                if cont_type == normalized_row_cont_type:
                    selected.append(name)
            elif not cont_type:
                no_type.append(name)

        if selected:
            refined.append(", ".join(list(dict.fromkeys(selected))))
        elif no_type:
            refined.append(", ".join(list(dict.fromkeys(no_type))))
        else:
            refined.append(", ".join(list(dict.fromkeys([n for n, _ in parsed_items]))))

    df["Hàng hóa"] = refined
    return df


def clean_description_text(raw_description: str) -> str:
    """Clean and extract first meaningful line from description.
    
    Args:
        raw_description: Raw description text from manifest
        
    Returns:
        Cleaned first line of description, empty if PORT or summary line
    """
    if not raw_description:
        return ""
        
    stripped = raw_description.strip()
    if not stripped:
        return ""
        
    # Get first line
    first_line = stripped.split("\n")[0].strip()
    
    # Skip PORT lines
    if "PORT," in first_line.upper():
        return ""
    
    # Clean leading/trailing non-word characters
    cleaned = re.sub(r"^[^\w(]+|[^\w)]+$", "", first_line).strip()
    return cleaned

