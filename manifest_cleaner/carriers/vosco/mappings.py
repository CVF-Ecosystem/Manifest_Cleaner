"""Size/Type mappings for container classification.

This module contains all mapping dictionaries used for converting
container size/type codes to standard formats and cargo type classification.
"""

from typing import Dict


# --- Mapping: Size/Type -> VTOS/ISO ---
# Converts various container size codes to standardized VTOS format.
# Add new mappings here when new container types are encountered.

SIZE_TO_VTOS: Dict[str, str] = {
    # Standard Dry Containers
    "20DC": "20DC",
    "20GP": "20DC",
    "40DC": "40DC",
    "40GP": "40HC",
    "40HC": "40HC",
    "45GP": "45HC",
    "45HC": "45HC",
    
    # Reefer Containers
    "20RF": "22R0",
    "40RF": "40RH",
    "45RF": "45RH",
    "20RH": "22R0",
    "40RH": "40RH",
    "45RH": "45RH",
    
    # Tank Containers
    "20TK": "20TK",
    
    # Flat Rack Containers
    "20FR": "20FL",
    "40FR": "40FL",
    
    # Open Top Containers
    "20OT": "20OT",
    "40OT": "40OT",
}


# --- Mapping: Size/Type -> Base Cargo Type ---
# Used to determine the cargo type based on container size/type.
# GENERAL is the default for standard dry containers.

SIZE_TYPE_TO_CARGO_TYPE_BASE: Dict[str, str] = {
    # Tank
    "20TK": "TANK",
    
    # General (Dry Containers)
    "20DC": "GENERAL",
    "40DC": "GENERAL",
    "40HC": "GENERAL",
    "45HC": "GENERAL",
    "20GP": "GENERAL",
    "40GP": "GENERAL",
    "45GP": "GENERAL",
    
    # Reefer
    "20RF": "REEFER",
    "40RF": "REEFER",
    "40RH": "REEFER",
    "45RF": "REEFER",
    "45RH": "REEFER",
    "20RH": "REEFER",
    
    # Flat Rack
    "20FR": "FLATRACK",
    "40FR": "FLATRACK",
    
    # Open Top
    "20OT": "OPENTOP",
    "40OT": "OPENTOP",
}


# --- Tare Weights (for F/E determination) ---
# Standard tare weights in TONS for different container sizes.
# Used to determine if a container is Full or Empty based on gross weight.

TARE_WEIGHTS_TONS: Dict[str, float] = {
    "20": 2.5,   # 20ft containers
    "40": 4.3,   # 40ft containers
    "45": 4.9,   # 45ft containers
}

# Safety margin (in TONS) added to tare weight when determining F/E status
SAFETY_MARGIN_TONS: float = 0.5


# --- Tank Container Configuration ---
# Tank containers have higher tare weight than standard containers
# and need special handling to avoid misclassification

TANK_TARE_WEIGHTS_TONS: Dict[str, float] = {
    "20TK": 5.5,   # 20ft tank container tare ~5.5 tons
}

# Weight range (in tons) where tank empty might be misclassified as Full
# If weight is within this range, we should warn user to verify
TANK_WEIGHT_WARNING_RANGE: Dict[str, tuple] = {
    "20TK": (5.0, 12.0),  # 20ft tank: 5-12 tons might be empty
}

