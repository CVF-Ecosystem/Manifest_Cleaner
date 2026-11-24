"""VOSCO manifest profile, preserving the existing port mappings."""
from .adapter import is_supported_size_type, parse_manifest, refresh_derived_fields

__all__ = ["parse_manifest", "refresh_derived_fields", "is_supported_size_type"]
