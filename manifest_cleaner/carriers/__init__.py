"""Carrier adapters. Vessel names never select a parser."""

from dataclasses import dataclass


COMMON_PORT_COLUMNS = (
    "STT", "Số lượng", "Số BL", "Số Container", "Hãng khai thác", "Kích cỡ",
    "Kích cỡ VTOS", "F/E", "TL hàng", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
    "Hàng hóa", "Loại hàng", "Độ chính xác (%)", "Ghi chú",
)
VIMC_PORT_COLUMNS = (
    "STT", "Số Vận Đơn", "Số Container", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
    "Kích cỡ", "Loại Container", "Hãng khai thác", "Loại hàng", "F/E", "Trọng lượng (Tấn)",
    "Hàng hóa", "Số lượng", "Độ chính xác (%)", "Ghi chú",
)
MAPPING_SETTINGS = frozenset({"size_to_iso", "size_to_vtos", "cargo_type_mapping"})
TARE_SETTINGS = frozenset({
    "tare_20ft", "tare_40ft", "tare_45ft", "tare_20rf", "tare_40rf", "tare_45rf",
    "min_payload", "safety_margin", "cargo_weight_empty_threshold",
    "tare_20ft_empty_vgm", "tare_40ft_empty_vgm", "tare_20rf_empty_vgm", "tare_40rf_empty_vgm",
    "min_payload_for_f_vgm", "safety_margin_tons",
})


@dataclass(frozen=True)
class PortExportProfile:
    columns: tuple[str, ...] = COMMON_PORT_COLUMNS
    group_quantity_by_master_bl: bool = False
    primary_size_field: str = "Size_Type"
    weight_digits: int | None = None
    weight_format: str = "0.####"
    empty_description: str | None = None


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
    ),
    "VIMC": CarrierProfile(
        adapter="manifest_cleaner.carriers.vimc.adapter",
        operators=("VMC", "SVM"),
        extra_settings=MAPPING_SETTINGS,
        export=PortExportProfile(
            columns=VIMC_PORT_COLUMNS, group_quantity_by_master_bl=True,
            primary_size_field="VTOS_Size", weight_digits=2, weight_format="0.00",
            empty_description="EMPTY",
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
            weight_format="0.00", empty_description="EMPTY",
        ),
    ),
}
CARRIERS = tuple(CARRIER_PROFILES)
