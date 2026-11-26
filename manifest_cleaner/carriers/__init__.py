"""Carrier adapters. Vessel names never select a parser."""

from dataclasses import dataclass


# The Port TOS import form (Manifest/Vtos.xlsx, 2026-11-26): 46 headers in TOS order.
# Four names repeat with a trailing space; TOS uses them for the name beside a code.
TOS_COLUMNS = (
    "Xác nhận", "ĐTTT", "Số lượng", "Số BL", "Số Container", "Hãng khai thác", "Kích cỡ",
    "Kích cỡ ISO", "F/E", "TL hàng", "VGM", "Nhóm TL", "Số niêm chì", "Số niêm chì 1",
    "Cảng xếp", "Cảng dỡ", "Cảng đích", "Phương Án", "Phương Án ", "Phương Thức Giao Nhận",
    "Phương Thức Giao Nhận ", "Chủ hàng", "Loại hàng", "Loại hàng ", "Hàng hóa", "CLASS",
    "UNNO", "Nhiệt độ", "Vent", "Vent_Unit", "Cntr Class", "CntrClass", "Hàng nội/ngoại",
    "Hàng nội/ngoại ", "Ghi chú", "OOG_TOP", "OOG_LEFT", "OOG_RIGHT", "OOG_BACK",
    "OOG_FRONT", "Term", "Số thứ tự", "Transist", "Cảng chuyển", "Cảng giao nhận",
    "Chỉ dẫn xếp dỡ",
)
# The template's Excel Table has one more column after the 46 headers; it is always blank.
TOS_EXTRA_COLUMN = "Column1"
TOS_EXPORT_COLUMNS = TOS_COLUMNS + (TOS_EXTRA_COLUMN,)
# The columns the app fills, in TOS order, for every carrier. STT and Ghi chú are
# shown in the app only; the Excel file leaves Ghi chú blank and has no STT.
PORT_COLUMNS = (
    "STT", "Số lượng", "Số BL", "Số Container", "Hãng khai thác", "Kích cỡ", "Kích cỡ ISO",
    "F/E", "TL hàng", "Số niêm chì", "Số niêm chì 1", "Chủ hàng", "Loại hàng", "Loại hàng ",
    "Hàng hóa", "Ghi chú",
)
APP_ONLY_COLUMNS = frozenset({"STT", "Ghi chú"})
# Operator decision 2026-11-26, after a successful TOS import: every exported data row of every
# carrier (all are domestic vessels) carries these fixed values, in upper case as given. They are
# not app data, so they are not in PORT_COLUMNS. Hàng nội/ngoại (no trailing space) and Cntr Class
# stay blank. Change a value here and nowhere else.
TOS_FIXED_VALUES = {
    "Phương Án": "NTAU",
    "Phương Án ": "NHẬP TÀU",
    "Phương Thức Giao Nhận": "TAU-BAI",
    "Phương Thức Giao Nhận ": "GIAO NHẬN TÀU <=> BÃI",
    "CntrClass": "IMPORT",
    "Hàng nội/ngoại ": "HÀNG NỘI",
}
# Only pairs seen in the TOS form. Other codes stay blank until a TOS import confirms them.
VTOS_TO_TOS_ISO = {"20DC": "22G0", "40HC": "45G0", "45HC": "L5G0", "40RH": "45R0", "20TK": "22T0"}
CARGO_TO_TOS = {"GENERAL": ("GP", "General"), "EMPTY REEFER": ("ER", "Empty Reefer"),
                "EMPTY TANK": ("ET", "EMPTY TANK")}
MAPPING_SETTINGS = frozenset({"size_to_iso", "size_to_vtos", "cargo_type_mapping"})
TARE_SETTINGS = frozenset({
    "tare_20ft", "tare_40ft", "tare_45ft", "tare_20rf", "tare_40rf", "tare_45rf",
    "min_payload", "safety_margin", "cargo_weight_empty_threshold",
    "tare_20ft_empty_vgm", "tare_40ft_empty_vgm", "tare_20rf_empty_vgm", "tare_40rf_empty_vgm",
    "min_payload_for_f_vgm", "safety_margin_tons",
})


@dataclass(frozen=True)
class PortExportProfile:
    group_quantity_by_master_bl: bool = False
    weight_digits: int | None = None
    weight_format: str = "General"
    empty_description: str | None = None
    seal_reference_lengths: tuple[int, ...] = ()


@dataclass(frozen=True)
class CarrierProfile:
    adapter: str
    operators: tuple[str, str]
    export: PortExportProfile = PortExportProfile()
    weight_kind: str = "gross"
    default_weight_unit: str | None = None
    sheet_alias: str | None = None
    weight_unit_alias: str | None = None
    extra_settings: frozenset[str] = frozenset()

    def operator(self, is_soc: bool = False) -> str:
        return self.operators[1 if is_soc else 0]

    def defaults(self) -> dict[str, str]:
        settings = {"number_format": "legacy", "weight_kind": self.weight_kind}
        if self.default_weight_unit is not None:
            settings["default_weight_unit"] = self.default_weight_unit
        return settings


CARRIER_PROFILES = {
    "VOSCO": CarrierProfile(
        adapter="manifest_cleaner.carriers.vosco.adapter",
        operators=("VOC", "SVC"),
        default_weight_unit="TONS",
        sheet_alias="sheet_name",
        export=PortExportProfile(seal_reference_lengths=(6,)),
    ),
    "VIMC": CarrierProfile(
        adapter="manifest_cleaner.carriers.vimc.adapter",
        operators=("VMC", "SVM"),
        extra_settings=MAPPING_SETTINGS,
        export=PortExportProfile(
            group_quantity_by_master_bl=True, weight_digits=2, weight_format="0.00",
            empty_description="EMPTY", seal_reference_lengths=(6, 7),
        ),
    ),
    "VINAFCO": CarrierProfile(
        adapter="manifest_cleaner.carriers.vinafco.adapter",
        operators=("VFC", "SVF"),
        default_weight_unit="TONS",
        sheet_alias="target_sheet_name",
        weight_unit_alias="default_weight_unit_if_missing",
        extra_settings=MAPPING_SETTINGS | TARE_SETTINGS | {
            "operator_soc", "operator_coc", "default_weight_unit_if_missing",
            "peek_rows", "size_type_to_cargo_type_base", "col_party_raw", "col_bill_no",
            "col_container_no", "col_seal", "col_type", "col_comm", "col_gw", "col_remarks",
        },
        export=PortExportProfile(
            group_quantity_by_master_bl=True, weight_digits=2,
            weight_format="0.00", empty_description="EMPTY", seal_reference_lengths=(6, 7),
        ),
    ),
}
CARRIERS = tuple(CARRIER_PROFILES)
