"""Vietnamese labels and source locators for the desktop issue view."""
from __future__ import annotations

from xlsxwriter.utility import xl_col_to_name

from .common import text_value
from .engine import FIELD_LABELS


ISSUE_TITLES = {
    "ADDITIONAL_MANIFEST_SHEET": "Có thêm sheet manifest",
    "CONSIGNEE_MISSING": "Thiếu chủ hàng",
    "CONTAINER_MULTIPLE_BL": "Container có nhiều B/L",
    "CONTAINER_UNPARSED": "Chưa đọc dòng container",
    "DESCRIPTION_PACKING_TEXT": "Lẫn quy cách đóng gói",
    "DESCRIPTION_QUANTITY_MISMATCH": "Số lượng không khớp",
    "DESCRIPTION_QUANTITY_SCOPE_UNCLEAR": "Chưa rõ phạm vi đếm",
    "DESCRIPTION_REVIEW": "Kiểm tra mô tả",
    "DUPLICATE_CONTAINER_BL": "Trùng container trong B/L",
    "EMPTY_CARGO_WEIGHT_CONFLICT": "Rỗng nhưng có hàng",
    "EMPTY_WEIGHT_CONFLICT": "Container rỗng vượt ngưỡng",
    "FE_WEIGHT_KIND_UNCONFIRMED": "Chưa rõ loại trọng lượng",
    "GROSS_WEIGHT_BELOW_TARE": "Dưới vỏ tham chiếu",
    "INVALID_CONTAINER": "Sai số container",
    "INVALID_FE": "Sai trạng thái F/E",
    "INVALID_OR_MISSING_BL": "B/L thiếu hoặc sai",
    "INVALID_WEIGHT": "Trọng lượng không hợp lệ",
    "KGS_DOT_GROUPING": "Dấu chấm trong kg",
    "MISSING_BL": "Thiếu số B/L",
    "MISSING_BL_NO": "Thiếu số B/L",
    "MISSING_CARGO_TYPE": "Thiếu loại hàng",
    "MISSING_CLEANED_CONSIGNEE_NAME_FOR_OUTPUT": "Thiếu chủ hàng",
    "MISSING_CONTAINER_NO": "Thiếu số container",
    "MISSING_DESCRIPTION": "Thiếu mô tả hàng",
    "MISSING_FE_STATUS": "Thiếu trạng thái F/E",
    "MISSING_OPERATOR": "Thiếu hãng khai thác",
    "MISSING_SIZE_TYPE": "Thiếu kích cỡ",
    "MISSING_VTOS_SIZE": "Thiếu kích cỡ VTOS",
    "MISSING_WEIGHT": "Thiếu trọng lượng",
    "NO_ACTIVE_RECORDS": "Không còn dòng xuất",
    "NO_SHEETS": "Không có sheet",
    "SETTINGS_CHANGED": "Cấu hình đã đổi",
    "SHEET_NOT_FOUND": "Không tìm thấy sheet",
    "SIZE_TYPE_MISSING": "Thiếu kích cỡ",
    "SOURCE_FORMULA_ERROR": "Ô nguồn lỗi công thức",
    "SOURCE_FORMULA_UNCALCULATED": "Công thức chưa tính",
    "TANK_WEIGHT_REVIEW": "Kiểm trọng lượng bồn",
    "UNKNOWN_OPERATOR": "Chưa nhận diện hãng",
    "UNKNOWN_SIZE_TYPE": "Kích cỡ chưa quy đổi",
    "VIMC_BL_CONFLICT": "Số B/L không khớp",
    "VIMC_BL_MISSING": "Thiếu số B/L",
    "VIMC_CONSIGNEE_MISSING": "Thiếu chủ hàng",
    "VIMC_CONTAINER_DATA_CONFLICT": "Dữ liệu trùng khác nhau",
    "VIMC_CONTAINER_FORMAT": "Sai định dạng container",
    "VIMC_CONTAINER_UNPARSED": "Chưa đọc dòng container",
    "VIMC_DUPLICATE_IN_BL": "Trùng container trong B/L",
    "VIMC_FE_UNRESOLVED": "Chưa rõ F/E",
    "VIMC_HEADER_INCOMPLETE": "Thiếu cột tiêu đề",
    "VIMC_HEADER_NOT_FOUND": "Chưa nhận diện tiêu đề",
    "VIMC_LAYOUT_AMBIGUOUS": "Trọng lượng chưa rõ đơn vị",
    "VIMC_LEGACY_COMPACT_CONTAINER": "Mã container dạng ngắn",
    "VIMC_MARKS_SIZE_CONFLICT": "Kích cỡ không khớp",
    "VIMC_REEFER_SIZE_REVIEW": "Đối chiếu kích cỡ lạnh",
    "VIMC_NO_CONTAINERS": "Không có container",
    "VIMC_SEAL_TYPE_AMBIGUOUS": "Chưa rõ seal, cỡ",
    "VIMC_SIZE_MISSING": "Thiếu kích cỡ",
    "VIMC_SIZE_UNKNOWN": "Kích cỡ chưa quy đổi",
    "VIMC_STATUS_GOODS_CONFLICT": "F/E khác mô tả",
    "VIMC_STATUS_SCOPE_CONFLICT": "F/E khác tiêu đề",
    "VIMC_WEIGHT_INVALID": "Không đọc được trọng lượng",
    "VIMC_WEIGHT_MISSING": "Thiếu trọng lượng",
    "VIMC_ZERO_LOADED_WEIGHT": "Trọng lượng bằng 0",
    "VINAFCO_AMBIGUOUS_COLUMNS": "Cột nguồn chưa rõ",
    "VINAFCO_BL_MISSING": "Thiếu số B/L",
    "VINAFCO_CONSIGNEE_MISSING": "Thiếu chủ hàng",
    "VINAFCO_CONTAINER_MISSING": "Thiếu số container",
    "VINAFCO_CONTAINER_UNPARSED": "Chưa đọc số container",
    "VINAFCO_FE_CONFLICT": "F/E không khớp",
    "VINAFCO_FE_DEFAULTED": "F/E dùng mặc định",
    "VINAFCO_FE_INFERRED": "F/E suy từ cân nặng",
    "VINAFCO_HEADER_CHANGED": "Tiêu đề đã đổi",
    "VINAFCO_HEADER_NOT_FOUND": "Chưa nhận diện tiêu đề",
    "VINAFCO_MISSING_COLUMN": "Thiếu cột nguồn",
    "VINAFCO_MULTIPLE_TABLES": "Cần chọn bảng",
    "VINAFCO_NO_CONTAINERS": "Không có container",
    "VINAFCO_READ_ERROR": "Không đọc được file",
    "VINAFCO_SOC_COC_CONFLICT": "SOC và COC xung đột",
    "VINAFCO_SUMMARY_MISMATCH": "Bảng tổng hợp lệch",
    "VINAFCO_TYPE_UNMAPPED": "Kích cỡ chưa quy đổi",
    "VINAFCO_WEIGHT_INVALID": "Không đọc được trọng lượng",
    "VOSCO_ADJACENT_CONTAINER_CANDIDATE": "Container ở cột bên",
    "VOSCO_LAYOUT_NOT_RECOGNIZED": "Chưa nhận diện bố cục",
    "WEIGHT_ASSOCIATION_AMBIGUOUS": "Chưa ghép được trọng lượng",
    "WEIGHT_INVALID": "Không đọc được trọng lượng",
    "ZERO_FULL_WEIGHT": "Trọng lượng bằng 0",
}

SOURCE_KEYS = {
    "BL_No": ("BL_No", "bill_no"),
    "Container_No": ("container_no", "container_line", "container_cell"),
    "Seal_No": ("seal", "seal_no"),
    "Size_Type": ("size_type", "Size_Type", "type"),
    "VTOS_Size": ("size_type", "Size_Type", "type"),
    "Weight_Value": ("weight", "gw", "weight_line", "weight_cell_value", "weight_cell"),
    "Description": ("description", "comm", "matched_description", "description_cell"),
    "Cleaned_Consignee_Name_For_Output": ("consignee",),
    "FE_Status": ("row_status", "context_status", "comm", "matched_description", "description"),
    "Operator": ("remarks", "comm"),
}

VINAFCO_COLUMNS = {
    "BL_No": "bill_no", "Container_No": "container_no", "Seal_No": "seal", "Size_Type": "type",
    "VTOS_Size": "type", "Weight_Value": "gw", "Description": "comm", "FE_Status": "comm",
    "Cleaned_Consignee_Name_For_Output": "party_raw", "Operator": "remarks",
}


def issue_field(item, *, compact=False):
    if item.get("field"):
        return FIELD_LABELS.get(item["field"], item["field"])
    if item.get("resolution_fields"):
        fields = [FIELD_LABELS.get(field, field) for field in item["resolution_fields"]]
        if compact:
            fields = [field.removesuffix(" (tấn)") for field in fields]
        return ", ".join(fields)
    return "Dòng container" if item.get("record_id") else "Toàn file"


def issue_title(item):
    return ISSUE_TITLES.get(item.get("code")) or (
        f"Kiểm tra {issue_field(item).lower()}" if item.get("field") else "Cần đối chiếu thêm")


def issue_location(item, record, carrier, metadata):
    """Prefer the issue's evidence. Use a row locator when the column is unknown."""
    raw = record.get("raw") or {}
    details = item.get("details") or {}
    sheet = item.get("source_sheet") or record.get("source_sheet")
    row = item.get("source_row") or record.get("source_row")
    cell = item.get("source_cell")
    column = item.get("source_column") or details.get("source_column")
    field = item.get("field")
    if not cell and not column and sheet == record.get("source_sheet") and row == record.get("source_row"):
        if field == "Weight_Value" and raw.get("weight_source_column"):
            row = raw.get("weight_source_row") or row
            column = raw["weight_source_column"]
        elif carrier == "VIMC":
            column = raw.get("source_column")
        elif carrier == "VINAFCO" and field != "Cleaned_Consignee_Name_For_Output":
            mapped = (metadata.get("column_mapping") or {}).get(VINAFCO_COLUMNS.get(field))
            if isinstance(mapped, int):
                column = mapped + 1
    if not cell and row and isinstance(column, int) and column > 0:
        cell = f"{xl_col_to_name(column - 1)}{row}"
    if cell:
        return f"{sheet}!{cell}" if sheet else cell
    return " · ".join(part for part in (sheet, f"dòng {row}" if row else None) if part) or "—"


def issue_raw_value(item, record):
    raw = record.get("raw") or {}
    field = item.get("field")
    if item.get("formula"):
        return item["formula"]
    if (item.get("source_row") and item["source_row"] != record.get("source_row")
            and not (field == "Weight_Value" and item["source_row"] == raw.get("weight_source_row"))):
        return ""
    if field == "Cleaned_Consignee_Name_For_Output":
        return text_value(raw.get("consignee") or (raw.get("party_values") or {}).get("Consignee"))
    for key in SOURCE_KEYS.get(field, ("text", "source_cell", "container_line", "container_cell")):
        value = raw.get(key)
        if text_value(value) != "":
            return value if isinstance(value, str) else text_value(value)
    return ""
