"""VINAFCO defaults retained from legacy commit e743b73.

These are port import mappings, not a claim that every value is an ISO code.
They are deliberately local to this carrier profile.
"""

from .. import CARRIER_PROFILES

SIZE_TO_VTOS = {
    "20DC": "20DC", "20GP": "20DC", "40DC": "40DC", "40GP": "40HC",
    "40HC": "40HC", "40HQ": "40HC", "45GP": "45HC", "45HC": "45HC",
    "45HQ": "45HC", "22G1": "20DC", "42G1": "40DC", "45G1": "40HC",
    "45R1": "45RH", "22R1": "22R0", "25G1": "20HC", "42R1": "40RH",
    "20RF": "22R0", "20RH": "22R0", "40RF": "40RH", "40RH": "40RH",
    "45RF": "45RH", "45RH": "45RH", "20TK": "20TK", "40TK": "40TK",
    "20FR": "20FL", "40FR": "40FL", "20OT": "20OT", "40OT": "40OT",
    # Accept the profile's own output labels as input as well.
    "22R0": "22R0", "20HC": "20HC", "20FL": "20FL", "40FL": "40FL",
}

CARGO_TYPES = {
    **{x: "GENERAL" for x in (
        "20DC", "20GP", "20HC", "40DC", "40GP", "40HC", "40HQ", "45HC",
        "45GP", "45HQ", "22G1", "25G1", "42G1", "45G1",
    )},
    **{x: "REEFER" for x in (
        "20RF", "20RH", "40RF", "40RH", "45RF", "45RH", "22R0", "22R1",
        "42R1", "45R1",
    )},
    "20TK": "TANK", "40TK": "TANK", "20FR": "FLATRACK", "40FR": "FLATRACK",
    "20FL": "FLATRACK", "40FL": "FLATRACK", "20OT": "OPENTOP", "40OT": "OPENTOP",
}

INPUT_COLUMNS = {
    "party_raw": "(S) SHIPPER,(C) CONSIGNEE,(N)NOTIFY PARTY",
    "bill_no": "Bill No", "container_no": "CONTAINER No.", "seal": "SEAL",
    "type": "TYPE", "comm": "COM.M", "gw": "GW", "remarks": "REMARKS",
}

HEADER_ALIASES = {
    "party_raw": [INPUT_COLUMNS["party_raw"], "SHIPPER CONSIGNEE NOTIFY PARTY"],
    "bill_no": ["Bill No", "B/L No", "BL No", "Bill Number"],
    "container_no": ["CONTAINER No.", "CONTAINER NUMBER", "CONT NO"],
    "seal": ["SEAL", "SEAL NO", "SEAL NUMBER"],
    "type": ["TYPE", "SIZE/TYPE", "SIZE TYPE", "CONTAINER TYPE"],
    "comm": ["COM.M", "COMMODITY", "DESCRIPTION OF GOODS", "DESCRIPTION"],
    "gw": ["GW", "GROSS WEIGHT", "GROSS WT"],
    "remarks": ["REMARKS", "REMARK", "NOTES"],
}

_CARRIER = CARRIER_PROFILES["VINAFCO"]
DEFAULTS = {
    **_CARRIER.defaults(),
    "operator_soc": _CARRIER.operator(True), "operator_coc": _CARRIER.operator(),
    "peek_rows": 80, "tare_20ft": 2.3, "tare_40ft": 3.8, "tare_45ft": 4.5,
    "tare_20rf": 3.0, "tare_40rf": 4.8, "tare_45rf": 4.0,
    "min_payload": 0.1, "safety_margin": 0.1, "cargo_weight_empty_threshold": 0.05,
}
