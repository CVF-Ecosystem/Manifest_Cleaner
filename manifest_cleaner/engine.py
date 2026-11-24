"""One carrier and one workbook per session, independent of desktop UI."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import os
import re
import tempfile
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .carriers import CARRIERS, CARRIER_PROFILES, MAPPING_SETTINGS, TARE_SETTINGS
from .common import inspect_workbook_source, issue, text_value

EDITABLE_FIELDS = ("BL_No", "Container_No", "Seal_No", "Cleaned_Consignee_Name_For_Output",
                   "Size_Type", "Operator", "FE_Status", "Weight_Value", "Description")
FIELD_LABELS = {"BL_No": "Số B/L", "Container_No": "Số container", "Seal_No": "Số niêm chì",
                "Cleaned_Consignee_Name_For_Output": "Chủ hàng", "Size_Type": "Kích cỡ khai báo",
                "VTOS_Size": "Kích cỡ VTOS", "Operator": "Hãng khai thác", "FE_Status": "F/E",
                "Weight_Value": "Trọng lượng (tấn)", "Description": "Hàng hóa", "Cargo_Type": "Loại hàng"}
DEFAULT_SETTINGS = {code: profile.defaults() for code, profile in CARRIER_PROFILES.items()}
REVIEW_FORMAT = "manifest-cleaner-review-v2"


class ReviewSourceError(ValueError):
    """The saved session needs its original, unchanged manifest to resume."""

    def __init__(self, code: str, message: str, expected_path: str):
        super().__init__(message)
        self.code = code
        self.expected_path = expected_path


def source_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_carrier_settings(carrier: str, supplied: dict | None = None) -> dict:
    """Validate known options and canonicalise sheet aliases before processing."""
    if carrier not in CARRIERS:
        raise ValueError("Hãng tàu trong cấu hình không được hỗ trợ.")
    if supplied is not None and not isinstance(supplied, dict):
        raise ValueError(f"Cấu hình {carrier} phải là một đối tượng JSON.")
    profile = CARRIER_PROFILES[carrier]
    data = copy.deepcopy(supplied or {})
    sheet_alias = profile.sheet_alias
    if sheet_alias and sheet_alias in data:
        if "selected_sheet" not in data:
            data["selected_sheet"] = data[sheet_alias]
        data.pop(sheet_alias)
    allowed = DEFAULT_SETTINGS[carrier].keys() | {"selected_sheet"} | profile.extra_settings
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Cấu hình {carrier} có tên chưa hỗ trợ: " + ", ".join(sorted(unknown)))
    # Legacy unit aliases must take effect before merging the default value.
    if profile.weight_unit_alias in data and "default_weight_unit" not in data:
        data["default_weight_unit"] = data[profile.weight_unit_alias]
    result = {**copy.deepcopy(DEFAULT_SETTINGS[carrier]), **data}
    if not isinstance(result["number_format"], str) or result["number_format"] not in {"legacy", "decimal_comma", "decimal_dot"}:
        raise ValueError(f"Quy ước số không hợp lệ cho {carrier}.")
    if not isinstance(result["weight_kind"], str) or result["weight_kind"] not in {"gross", "cargo", "unknown"}:
        raise ValueError(f"weight_kind của {carrier} chỉ nhận gross, cargo hoặc unknown.")
    if "selected_sheet" in result:
        if not isinstance(result["selected_sheet"], str):
            raise ValueError("Tên sheet phải là chuỗi ký tự.")
        result["selected_sheet"] = result["selected_sheet"].strip()
        if not result["selected_sheet"]:
            result.pop("selected_sheet")
    units = {"KG": "KGS", "KGS": "KGS", "KILOGRAM": "KGS", "KILOGRAMS": "KGS",
             "T": "TONS", "MT": "TONS", "TON": "TONS", "TONS": "TONS", "TONNE": "TONS", "TONNES": "TONS"}
    for key in ("default_weight_unit", profile.weight_unit_alias):
        if key is not None and key in result:
            unit = text_value(result[key]).upper()
            if unit not in units:
                raise ValueError(f"{key} phải là kg hoặc tấn.")
            result[key] = units[unit]
    for key in MAPPING_SETTINGS | {"size_type_to_cargo_type_base"}:
        if key in result:
            if not isinstance(result[key], dict) or any(not isinstance(k, str) or not k.strip() or
                    not isinstance(v, str) or not v.strip() for k, v in result[key].items()):
                raise ValueError(f"{key} phải là bảng ánh xạ gồm mã và giá trị chữ không rỗng.")
    for key in TARE_SETTINGS:
        if key in result:
            if isinstance(result[key], bool):
                raise ValueError(f"{key} phải là số không âm.")
            try:
                value = float(result[key])
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"{key} phải là số không âm.")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} phải là số hữu hạn không âm.")
            result[key] = value
    if "peek_rows" in result:
        value = result["peek_rows"]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
            raise ValueError("peek_rows phải là số nguyên từ 1 đến 10000.")
    for key, value in result.items():
        if key.startswith("col_") or key in {"operator_soc", "operator_coc"}:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} phải là chuỗi ký tự không rỗng.")
    return result


def _adapter(carrier: str):
    if carrier not in CARRIERS:
        raise ValueError("Chọn hãng tàu: " + ", ".join(CARRIERS) + ".")
    return importlib.import_module(CARRIER_PROFILES[carrier].adapter)


def load_settings(path: str | Path | None = None) -> dict:
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if path is None:
        return settings
    if not Path(path).is_file():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình đã chỉ định: {path}. Không tự chuyển về mặc định.")
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("File cấu hình phải là một đối tượng JSON.")
    unknown = set(data) - set(CARRIERS)
    if unknown:
        raise ValueError("Tên hãng không được hỗ trợ trong cấu hình: " + ", ".join(sorted(unknown)))
    for carrier in CARRIERS:
        if carrier in data and not isinstance(data[carrier], dict):
            raise ValueError(f"Cấu hình {carrier} phải là một đối tượng JSON, không được để null.")
        settings[carrier] = validate_carrier_settings(carrier, data.get(carrier))
    return settings


def _present(value) -> bool:
    return bool(text_value(value))


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


@dataclass
class ManifestSession:
    carrier: str
    records: list[dict]
    base_issues: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    corrections: list[dict] = field(default_factory=list)

    def active_records(self) -> list[dict]:
        return [r for r in self.records if not r.get("_excluded")]

    def get_record(self, record_id: str) -> dict:
        for record in self.records:
            if record["record_id"] == record_id:
                return record
        raise KeyError(record_id)

    def validate(self) -> list[dict]:
        """Recompute current errors after edits; retained base issues are traceable."""
        output = []
        if self.metadata.get("settings_changed"):
            output.append(issue("SETTINGS_CHANGED", "Quy ước xử lý đã thay đổi. Xử lý lại manifest trước khi xuất.", severity="error"))
        active = {r["record_id"]: r for r in self.active_records()}
        for original in self.base_issues:
            item = dict(original)
            rid = item.get("record_id")
            if rid is not None:
                record = active.get(str(rid))
                if record is None:
                    continue
                verified = set(record.get("_edited_fields", [])) | set(record.get("_verified_fields", []))
                field_name = item.get("field")
                # Resolved values still undergo independent current validation below.
                resolution_fields = item.get("resolution_fields") or ([field_name] if field_name else [])
                if resolution_fields and all(name in verified and _present(record.get(name)) for name in resolution_fields):
                    continue
                if record.get("_manual_review_reason") and item.get("severity") != "error":
                    continue
            output.append(item)
        by_container_bl = defaultdict(list)
        by_container = defaultdict(list)
        for record in active.values():
            rid = record["record_id"]
            def add(code, message, severity="error", field_name=None):
                output.append(issue(code, message, severity=severity, record_id=rid, field=field_name,
                                    source_sheet=record.get("source_sheet"), source_row=record.get("source_row")))
            required = ("BL_No", "Container_No", "Cleaned_Consignee_Name_For_Output", "Size_Type", "VTOS_Size", "Operator", "FE_Status", "Cargo_Type")
            for name in required:
                if not _present(record.get(name)) or str(record.get(name)).upper() in {"UNKNOWN", "N/A", "NONE"}:
                    add("MISSING_" + name.upper(), "Thiếu " + FIELD_LABELS.get(name, name) + ".", field_name=name)
            container = text_value(record.get("Container_No")).upper()
            if container and not re.fullmatch(r"[A-Z]{4}\d{7}", container):
                add("INVALID_CONTAINER", "Số container phải gồm 4 chữ cái và 7 chữ số.", field_name="Container_No")
            validate_size = getattr(_adapter(self.carrier), "is_supported_size_type", None)
            if _present(record.get("Size_Type")) and validate_size and not validate_size(record["Size_Type"], self.settings):
                add("UNKNOWN_SIZE_TYPE", "Kích cỡ chưa có trong bảng quy đổi của hãng; điền mã đã biết hoặc bổ sung mapping có kiểm tra.", field_name="Size_Type")
            allowed_operators = set(CARRIER_PROFILES[self.carrier].operators) | {str(self.settings[k]).upper() for k in ("operator_soc", "operator_coc") if self.settings.get(k)}
            if _present(record.get("Operator")) and text_value(record.get("Operator")).upper() not in allowed_operators:
                add("UNKNOWN_OPERATOR", "Mã hãng khai thác chưa có trong cấu hình của hãng đang chọn.", field_name="Operator")
            bl = text_value(record.get("BL_No"))
            if bl.startswith("(") and "no_bill" in bl:
                add("MISSING_BL", "Số B/L đang là giá trị tạm, cần điền số thực tế.", field_name="BL_No")
            fe = text_value(record.get("FE_Status")).upper()
            if fe and fe not in {"F", "E"}:
                add("INVALID_FE", "F/E phải là F hoặc E trước khi xuất file import.", field_name="FE_Status")
            weight = record.get("Weight_Value")
            if weight is None or text_value(weight) == "":
                if fe == "F":
                    add("MISSING_WEIGHT", "Container F chưa có trọng lượng hợp lệ.", field_name="Weight_Value")
            else:
                try:
                    number = float(weight)
                    if not math.isfinite(number) or number < 0:
                        raise ValueError
                    if fe == "F" and number == 0:
                        add("ZERO_FULL_WEIGHT", "Container F có trọng lượng bằng 0; kiểm tra lại dữ liệu.", "warning", "Weight_Value")
                except (ValueError, TypeError, OverflowError):
                    add("INVALID_WEIGHT", "Trọng lượng phải là số hữu hạn, không âm, theo đơn vị tấn.", field_name="Weight_Value")
            seal = text_value(record.get("Seal_No"))
            if seal and not re.fullmatch(r"\d{6,7}", seal):
                add("SEAL_LEGACY_RULE", "Seal khác quy tắc 6–7 chữ số của mẫu cũ; giữ nguyên giá trị để đối chiếu.", "warning", "Seal_No")
            if fe == "F" and not _present(record.get("Description")):
                add("MISSING_DESCRIPTION", "Container F chưa có mô tả hàng hóa.", "warning", "Description")
            if container:
                by_container_bl[(bl, container)].append(record)
                by_container[container].append(record)
        for (bl, container), records in by_container_bl.items():
            if len(records) > 1:
                # Distinct cargo records can be legitimate; only an explicit review
                # acknowledges this relationship. Never drop them silently.
                confirmed = all(r.get("_manual_review_reason") for r in records)
                for r in records:
                    output.append(issue("DUPLICATE_CONTAINER_BL", f"Container {container} xuất hiện {len(records)} lần trong B/L {bl}. Đối chiếu hoặc loại bản sao có lý do.",
                                        severity="warning" if confirmed else "error", record_id=r["record_id"], field="Container_No"))
        for container, records in by_container.items():
            if len({text_value(r.get("BL_No")) for r in records}) > 1:
                for r in records:
                    output.append(issue("CONTAINER_MULTIPLE_BL", f"Container {container} liên quan nhiều B/L; các quan hệ được giữ nguyên.",
                                        record_id=r["record_id"], field="Container_No"))
        if not active:
            output.append(issue("NO_ACTIVE_RECORDS", "Không có container để xuất.", severity="error"))
        # A record can receive the same issue from parser and final validation.
        unique = {}
        for item in output:
            key = (item.get("record_id"), item.get("code"), item.get("message"))
            unique[key] = item
        return list(unique.values())

    def statistics(self) -> dict:
        records = self.active_records()
        issues = self.validate()
        statuses = Counter(text_value(r.get("FE_Status")) for r in records)
        return {"detected_records": len(self.records), "active_records": len(records),
                "containers": len({text_value(r.get("Container_No")) for r in records if _present(r.get("Container_No"))}),
                "bills": len({text_value(r.get("BL_No")) for r in records if _present(r.get("BL_No"))}),
                "full": statuses.get("F", 0), "empty": statuses.get("E", 0),
                "unknown": len(records) - statuses.get("F", 0) - statuses.get("E", 0),
                "excluded": len(self.records) - len(records),
                "errors": sum(i.get("severity") == "error" for i in issues),
                "warnings": sum(i.get("severity") == "warning" for i in issues),
                "error_records": len({i["record_id"] for i in issues if i.get("record_id") and i.get("severity") == "error"}),
                "review_records": len({i["record_id"] for i in issues if i.get("record_id")}),
                "file_errors": sum(i.get("severity") == "error" and not i.get("record_id") for i in issues),
                "unresolved_source_fragments": int((self.metadata.get("coverage") or {}).get("unresolved_fragments", 0)),
                "formula_source_errors": sum(i.get("code") in {"SOURCE_FORMULA_UNCALCULATED", "SOURCE_FORMULA_ERROR"} for i in issues)}

    def update_record(self, record_id: str, changes: dict, reason: str, *, verified_fields=None) -> None:
        if not reason.strip():
            raise ValueError("Ghi lý do chỉnh sửa để có thể đối chiếu.")
        record = self.get_record(record_id)
        before = copy.deepcopy(record)
        if not isinstance(changes, dict):
            raise ValueError("Các thay đổi phải là một bảng trường và giá trị.")
        invalid = set(changes) - set(EDITABLE_FIELDS)
        if invalid:
            raise ValueError("Trường không được chỉnh sửa: " + ", ".join(sorted(invalid)))
        if verified_fields is None:
            verified_fields = []
        if not isinstance(verified_fields, (list, tuple, set)) or any(not isinstance(x, str) for x in verified_fields):
            raise ValueError("Các trường đã đối chiếu phải là một danh sách tên trường.")
        explicit = set(verified_fields)
        if explicit - set(EDITABLE_FIELDS):
            raise ValueError("Trường không được xác nhận: " + ", ".join(sorted(explicit - set(EDITABLE_FIELDS))))
        normalized = {}
        for name, value in changes.items():
            if name == "Weight_Value":
                if not _present(value):
                    value = None
                else:
                    try:
                        value = float(str(value).replace(",", "."))
                        if not math.isfinite(value) or value < 0:
                            raise ValueError
                    except (ValueError, TypeError, OverflowError):
                        raise ValueError("Nhập trọng lượng bằng tấn, dùng dấu phẩy hoặc dấu chấm thập phân.")
            else:
                value = text_value(value)
                if name in {"Container_No", "FE_Status", "Size_Type", "Operator"}:
                    value = value.upper()
            normalized[name] = value
        candidate = copy.deepcopy(record)
        edited = set(candidate.get("_edited_fields", []))
        changed_now = set()
        for name, value in normalized.items():
            if candidate.get(name) != value:
                candidate[name] = value
                edited.add(name)
                changed_now.add(name)
        # Merely submitting an unchanged field is not verification (audit F01).
        if not changed_now and not explicit:
            return
        candidate["_edited_fields"] = sorted(edited)
        candidate["_verified_fields"] = sorted(set(candidate.get("_verified_fields", [])) | explicit)
        if "Weight_Value" in changed_now:
            candidate["Weight_Unit"] = "TONS" if candidate.get("Weight_Value") is not None else None
        refresh = getattr(_adapter(self.carrier), "refresh_derived_fields", None)
        if refresh:
            candidate.update(refresh(copy.deepcopy(candidate), self.settings))
        candidate.pop("_manual_review_reason", None)
        record.clear()
        record.update(candidate)
        self.corrections.append({"action": "edit", "record_id": record_id, "reason": reason.strip(),
                                 "changed_fields": sorted(changed_now), "verified_fields": sorted(explicit),
                                 "time": datetime.now(timezone.utc).isoformat(), "before": before, "after": copy.deepcopy(record)})

    def acknowledge_record(self, record_id: str, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Ghi căn cứ đã đối chiếu manifest gốc.")
        record = self.get_record(record_id)
        record["_manual_review_reason"] = reason.strip()
        self.corrections.append({"action": "review", "record_id": record_id, "reason": reason.strip(),
                                 "time": datetime.now(timezone.utc).isoformat()})

    def set_excluded(self, record_id: str, excluded: bool, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Ghi lý do loại hoặc khôi phục bản ghi.")
        self.get_record(record_id)["_excluded"] = bool(excluded)
        self.corrections.append({"action": "exclude" if excluded else "restore", "record_id": record_id,
                                 "reason": reason.strip(), "time": datetime.now(timezone.utc).isoformat()})

    def review_data(self) -> dict:
        data = {"format": REVIEW_FORMAT, "schema_version": 2, "app_version": __version__, "carrier": self.carrier,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "records": self.records, "base_issues": self.base_issues, "current_issues": self.validate(),
                "metadata": self.metadata, "settings": self.settings, "corrections": self.corrections,
                "statistics": self.statistics()}
        data = _json_safe(data)
        data["payload_sha256"] = _payload_hash(data)
        return data

    def save_review(self, path: str | Path, *, overwrite: bool = True) -> Path:
        path = Path(path).resolve()
        source = self.metadata.get("source_path")
        if source and path.resolve() == Path(source).resolve():
            raise ValueError("Chọn tên khác với file manifest gốc.")
        if path.suffix.lower() != ".json":
            raise ValueError("Bản đối chiếu/phiên phải có đuôi .json.")
        if path.exists() and not overwrite:
            raise FileExistsError("Bản đối chiếu đã tồn tại; chọn tên mới hoặc xác nhận ghi đè.")
        data = self.review_data()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".manifest_review_", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return path


def _payload_hash(data: dict) -> str:
    payload = {k: v for k, v in data.items() if k != "payload_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_source_unchanged(session: ManifestSession, *, source_path: str | Path | None = None) -> Path | None:
    """Confirm that a resume/export still refers to exactly the processed bytes."""
    recorded = session.metadata.get("source_path")
    if not recorded:
        return None  # Unit/API-created sessions can be independent of a workbook.
    source = Path(source_path or recorded).expanduser().resolve()
    if not source.is_file():
        raise ReviewSourceError("source_missing", "Không tìm thấy manifest gốc. Chọn lại đúng file nguồn để đối chiếu mã kiểm tra.", str(source))
    expected = session.metadata.get("source_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Phiên không có mã kiểm tra nguồn hợp lệ; hãy mở manifest gốc thành phiên mới.")
    if source_sha256(source) != expected:
        raise ReviewSourceError("source_changed", "Manifest nguồn đã thay đổi so với phiên đã lưu. Chọn đúng bản nguồn cũ, hoặc mở bản thay đổi thành phiên mới.", str(source))
    return source


def load_review(path: str | Path, *, source_path: str | Path | None = None) -> ManifestSession:
    """Resume a v2 session without re-parsing or silently discarding corrections."""
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Không tìm thấy file phiên/đối chiếu.")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("File phiên vượt 50 MB.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("JSON chứa số không hữu hạn.")))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("File phiên không phải JSON hợp lệ.") from exc
    if not isinstance(data, dict):
        raise ValueError("File phiên phải chứa một đối tượng JSON.")
    if data.get("format") == "manifest-cleaner-review-v1":
        raise ValueError("Đối chiếu của bản 1.0 là báo cáo tham khảo, chưa phải phiên có thể mở lại. Hãy mở manifest gốc bằng bản 1.1 để tạo phiên mới.")
    if data.get("format") != REVIEW_FORMAT or data.get("schema_version") != 2:
        raise ValueError("Định dạng/phiên bản file phiên chưa được hỗ trợ.")
    if data.get("payload_sha256") != _payload_hash(data):
        raise ValueError("Nội dung file phiên không khớp mã kiểm tra; file có thể bị thay đổi hoặc lưu chưa đầy đủ.")
    carrier = data.get("carrier")
    if carrier not in CARRIERS:
        raise ValueError("Hãng tàu trong file phiên không hợp lệ.")
    if not isinstance(data.get("settings"), dict):
        raise ValueError("Cấu hình trong file phiên không hợp lệ.")
    settings = validate_carrier_settings(carrier, data["settings"])
    records, issues, metadata, corrections = (data.get(k) for k in ("records", "base_issues", "metadata", "corrections"))
    if not isinstance(records, list) or len(records) > 200000 or any(not isinstance(r, dict) for r in records):
        raise ValueError("Danh sách bản ghi của phiên không hợp lệ.")
    if not isinstance(issues, list) or not isinstance(metadata, dict) or not isinstance(corrections, list):
        raise ValueError("Phiên thiếu dữ liệu lỗi, nguồn hoặc lịch sử đối chiếu.")
    if not isinstance(metadata.get("source_path"), str) or not metadata["source_path"]:
        raise ValueError("Phiên thiếu đường dẫn manifest nguồn.")
    ids = set()
    for record in records:
        rid = record.get("record_id")
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError("Mã bản ghi trong phiên bị thiếu hoặc trùng.")
        ids.add(rid)
        if not isinstance(record.get("raw", {}), dict) or not isinstance(record.get("rules", []), list):
            raise ValueError("Bằng chứng nguồn hoặc danh sách quy tắc trong phiên không hợp lệ.")
        for name in EDITABLE_FIELDS:
            value = record.get(name)
            if name == "Weight_Value":
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                    raise ValueError("Trọng lượng trong file phiên không hợp lệ.")
            elif value is not None and not isinstance(value, str):
                raise ValueError(f"Trường {name} trong phiên không phải văn bản.")
        for key in ("_edited_fields", "_verified_fields"):
            fields = record.get(key, [])
            if not isinstance(fields, list) or any(not isinstance(x, str) or x not in EDITABLE_FIELDS for x in fields):
                raise ValueError("Thông tin xác minh trường trong phiên không hợp lệ.")
        if "_excluded" in record and not isinstance(record["_excluded"], bool):
            raise ValueError("Trạng thái loại dòng trong phiên không hợp lệ.")
        if "_manual_review_reason" in record and not isinstance(record["_manual_review_reason"], str):
            raise ValueError("Căn cứ đối chiếu trong phiên không hợp lệ.")
        confidence = record.get("Confidence", 100)
        if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence)):
            raise ValueError("Điểm quy tắc trong phiên không hợp lệ.")
    for item in issues:
        if not isinstance(item, dict) or item.get("severity") not in {"error", "warning", "info"} or not isinstance(item.get("code"), str):
            raise ValueError("Danh sách lỗi trong phiên không hợp lệ.")
        if item.get("record_id") is not None and str(item["record_id"]) not in ids:
            raise ValueError("Lỗi của phiên tham chiếu bản ghi không tồn tại.")
    if any(not isinstance(item, dict) for item in corrections):
        raise ValueError("Lịch sử chỉnh sửa không hợp lệ.")
    session = ManifestSession(carrier, records, issues, metadata, settings, corrections)
    recorded_source = Path(metadata["source_path"]).expanduser()
    if source_path is None and not recorded_source.is_absolute():
        source_path = path.parent / recorded_source
    source = assert_source_unchanged(session, source_path=source_path)
    session.metadata["source_path"] = str(source)
    session.metadata["source_name"] = source.name
    session.metadata["resumed_from"] = str(path)
    session.metadata["resumed_at"] = datetime.now(timezone.utc).isoformat()
    session.metadata["effective_settings"] = copy.deepcopy(settings)
    session.metadata["resumed_with_saved_settings"] = True
    if session.metadata.pop("settings_changed", False):
        session.metadata["pending_settings_discarded"] = True
    refresh = getattr(_adapter(carrier), "refresh_derived_fields", None)
    if refresh:
        for record in records:
            record.update(refresh(copy.deepcopy(record), settings))
    session.validate()
    return session


def process_manifest(path: str | Path, carrier: str, *, settings: dict | None = None, progress=None) -> ManifestSession:
    carrier = carrier.upper().strip()
    adapter = _adapter(carrier)
    source = Path(path).resolve()
    chosen_settings = validate_carrier_settings(carrier, settings)
    initial_hash = source_sha256(source)
    source_info = inspect_workbook_source(source)
    selected = chosen_settings.get("selected_sheet")
    if selected and selected not in source_info["available_sheets"]:
        raise ValueError(f"Không tìm thấy sheet '{selected}'. Có các sheet: " + ", ".join(source_info["available_sheets"]))
    adapter_settings = copy.deepcopy(chosen_settings)
    sheet_alias = CARRIER_PROFILES[carrier].sheet_alias
    if selected and sheet_alias:
        adapter_settings[sheet_alias] = selected
    result = adapter.parse_manifest(source, settings=adapter_settings, progress=progress)
    if source_sha256(source) != initial_hash:
        raise ValueError("File nguồn đã thay đổi trong khi đang xử lý. Hãy đóng file và đọc lại.")
    if not isinstance(result, dict) or not isinstance(result.get("records"), list):
        raise ValueError("Bộ đọc không trả về dữ liệu hợp lệ.")
    records = result["records"]
    identifiers = set()
    for index, record in enumerate(records, 1):
        rid = str(record.get("record_id") or f"{carrier}-{index:05d}")
        if rid in identifiers:
            raise ValueError("Bộ đọc trả về mã bản ghi bị trùng.")
        identifiers.add(rid)
        record["record_id"] = rid
        record.setdefault("source_file", source.name)
        if not record.get("VTOS_Size") and record.get("ISO_Size"):
            record["VTOS_Size"] = record["ISO_Size"]
        if not record.get("Cleaned_Consignee_Name_For_Output"):
            record["Cleaned_Consignee_Name_For_Output"] = record.get("Consignee", "")
        record.setdefault("raw", {})
        record.setdefault("rules", [])
    metadata = dict(result.get("metadata") or {})
    used = {r.get("source_sheet") for r in records if r.get("source_sheet")}
    if selected:
        used = {selected}
    else:
        # A recognised manifest sheet may contain only uncached formulas and
        # yield no records. It still belongs to the source-completeness gate.
        used.update(metadata.get("sheets_used") or [])
        if metadata.get("source_sheet"):
            used.add(metadata["source_sheet"])
        if not used:
            used = set(source_info["available_sheets"])
    source_issues = []
    for cell in source_info["formula_cells"]:
        if cell["source_sheet"] not in used:
            continue
        error = cell["status"] == "error"
        item = issue("SOURCE_FORMULA_ERROR" if error else "SOURCE_FORMULA_UNCALCULATED",
                     f"Ô {cell['source_sheet']}!{cell['source_cell']} " +
                     ("có lỗi công thức Excel." if error else "có công thức nhưng chưa có kết quả được lưu.") +
                     " Mở bằng Excel để tính lại và lưu, hoặc dùng bản chỉ chứa giá trị, rồi xử lý lại.",
                     severity="error", source_sheet=cell["source_sheet"], source_row=cell["source_row"])
        item["source_cell"] = cell["source_cell"]
        item["formula"] = cell["formula"]
        source_issues.append(item)
    metadata.update({"source_path": str(source), "source_name": source.name,
                     "source_sha256": initial_hash, "session_id": uuid.uuid4().hex,
                     "available_sheets": source_info["available_sheets"], "used_sheets": sorted(used),
                     "formula_cache_scan": source_info["formula_cache_scan"], "formula_source_cells": source_info["formula_cells"],
                     "effective_settings": copy.deepcopy(chosen_settings),
                     "source_weight_units": sorted({r.get("raw", {}).get("weight_source_unit") for r in records if r.get("raw", {}).get("weight_source_unit")}),
                     "carrier": carrier, "app_version": __version__, "processed_at": datetime.now(timezone.utc).isoformat()})
    return ManifestSession(carrier, records, list(result.get("issues", [])) + source_issues, metadata, chosen_settings)
