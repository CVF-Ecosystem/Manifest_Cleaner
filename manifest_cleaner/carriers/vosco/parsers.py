"""Regex patterns and parsing functions for manifest data.

This module contains all regex patterns and functions for parsing
container lines, weight information, and other manifest data.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .mappings import SIZE_TO_VTOS
from ...common import parse_weight


# --- Regex Patterns ---

# Bill of Lading pattern: 3-6 uppercase letters followed by 6+ digits
BL_PATTERN = re.compile(r"^[A-Z]{3,6}\d{6,}$")

# Container number pattern: 4 uppercase letters + 7 digits
CONT_NO_PATTERN = re.compile(r"^([A-Z]{4}\d{7})(?![A-Z0-9])")

# Size/Type pattern: 2 digits + 1-4 alphanumeric chars (e.g., 40HC, 20GP)
SIZE_TYPE_PATTERN = re.compile(r"(\d{2}[A-Z0-9]{1,4})")

# SOC/COC marker at end of line: -S or -C
MARKER_PATTERN = re.compile(r"-([CS])$", re.IGNORECASE)

# Weight pattern: number followed by TONS or KGS
WEIGHT_PATTERN = re.compile(r"([\d.,]+)\s*(TONS?|KGS?)", re.IGNORECASE)

# Summary line pattern: (n) x 40HC COC format
SUMMARY_LINE_PATTERN = re.compile(
    r"\(\d+\)\s*x\s*\d{2}[A-Z0-9]{1,4}\s*(COC|SOC)", 
    re.IGNORECASE
)

# Empty container description pattern
EMPTY_DESC_PATTERN = re.compile(r"EMPTY", re.IGNORECASE)

# Stop keywords for consignee name cleaning
STOP_KEYWORDS_PATTERN = re.compile(
    r"(?:Mail\s*:|Tel\s*:|Fax\s*:|Địa chỉ\s*:|SĐT\s*:|Email\s*:|"
    r"Số CCCD\s*:|Tại\s*:|Chức vụ\s*:|Tài khoản\s*:|Đ/C\s*:|MST\s*:|"
    r"Phone\s*:|Email\s*\:|Điện thoại\s*:)",
    re.IGNORECASE | re.UNICODE,
)

# Single item parse pattern for description refinement
SINGLE_ITEM_PARSE_PATTERN = re.compile(
    r"([\w\sÀ-ỹ/\-.()']+?)"
    r"(?:\s*\(\s*\d+\s*\)\s*x\s*(\d{2}'?[A-Z0-9]{2,4})\s*(?:COC|SOC))?$"
)


# --- Parsing Functions ---

def parse_container_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a container line and extract container information.
    
    Args:
        line: Raw container line from manifest (e.g., "ABCD1234567/123456 40HC-C")
        
    Returns:
        Dictionary with keys: no, seal, type, operator, is_soc
        Returns None if line doesn't contain valid container number.
        
    Example:
        >>> parse_container_line("MSCU1234567/654321 40HC-C")
        {'no': 'MSCU1234567', 'seal': '654321', 'type': '40HC', 'operator': 'VOC', 'is_soc': False}
    """
    line = str(line).strip()
    cont_match = CONT_NO_PATTERN.match(line)
    if not cont_match:
        return None

    container_no = cont_match.group(1)
    remaining_part = line[len(container_no):].strip()

    size_type: Optional[str] = None
    seal_no: Optional[str] = None
    suffix_marker: str = ""
    is_soc = False

    # Check for SOC/COC marker at end
    suffix_marker_match = MARKER_PATTERN.search(remaining_part)
    if suffix_marker_match:
        suffix_marker = suffix_marker_match.group(1).upper()
        part_before_suffix = remaining_part[:suffix_marker_match.start()].strip()
        if part_before_suffix.endswith("-"):
            part_before_suffix = part_before_suffix[:-1].strip()
    else:
        part_before_suffix = remaining_part

    # Extract size/type
    # A numeric seal alone is not a container type.
    size_type_matches = [value for value in SIZE_TYPE_PATTERN.findall(part_before_suffix)
                         if any(char.isalpha() for char in value)]
    if size_type_matches:
        size_type = size_type_matches[-1].upper()
        size_type_start_index = part_before_suffix.rfind(size_type)
        if size_type_start_index != -1:
            seal_part_candidate = part_before_suffix[:size_type_start_index].strip()
            # Clean seal number
            if seal_part_candidate.endswith("/"):
                seal_part_candidate = seal_part_candidate[:-1].strip()
            if seal_part_candidate.startswith("/"):
                seal_part_candidate = seal_part_candidate[1:].strip()
            seal_no = seal_part_candidate or None
    elif part_before_suffix.startswith("/"):
        seal_no = part_before_suffix[1:].strip() if part_before_suffix[1:] else None

    # SOC detection
    if suffix_marker == "S":
        is_soc = True
    elif seal_no is None and "//" in line and not size_type_matches:
        is_soc = True

    # Validate size_type format
    if size_type and not re.fullmatch(r"\d{2}[A-Z0-9]{1,4}", size_type):
        size_type = None

    operator = "SVC" if is_soc else "VOC"
    
    return {
        "no": container_no,
        "seal": seal_no,
        "type": size_type,
        "operator": operator,
        "is_soc": is_soc
    }


def parse_weight_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse weight information from a line.
    
    Args:
        line: Raw weight line (e.g., "25.5 TONS" or "25,500 KGS")
        
    Returns:
        Dictionary with keys: value (float), unit (str)
        Returns None if no valid weight found.
        
    Example:
        >>> parse_weight_line("25.5 TONS")
        {'value': 25.5, 'unit': 'TONS'}
    """
    # Normalise mass before any F/E rule or export; retain original evidence.
    return parse_weight(line, default_unit="TONS", number_format="legacy")



def get_vtos_size(size_type: Optional[str]) -> Optional[str]:
    """Convert size/type to VTOS standard format.
    
    Args:
        size_type: Container size/type code (e.g., "40GP", "20RF")
        
    Returns:
        VTOS standardized code, or original if no mapping exists.
        
    Example:
        >>> get_vtos_size("40GP")
        '40HC'
    """
    if not size_type:
        return None
    st = str(size_type).upper().strip()
    return SIZE_TO_VTOS.get(st, st)


def get_iso_size(size_type: Optional[str]) -> Optional[str]:
    """Alias for get_vtos_size for backward compatibility."""
    return get_vtos_size(size_type)


def is_summary_line(text: str) -> bool:
    """Check if text is a summary line (e.g., '(1) x 40HC COC').
    
    Args:
        text: Text to check
        
    Returns:
        True if text matches summary line pattern.
    """
    return bool(SUMMARY_LINE_PATTERN.search(str(text)))


def is_valid_bl(text: str) -> bool:
    """Check if text is a valid Bill of Lading number.
    
    Args:
        text: Text to check
        
    Returns:
        True if text matches BL pattern (e.g., 'VOSCO123456').
    """
    return bool(BL_PATTERN.fullmatch(str(text).strip()))

