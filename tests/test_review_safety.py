"""Regressions for independent integration-review findings."""
import copy
import tempfile
import unittest
from pathlib import Path

from manifest_cleaner.common import read_workbook
from manifest_cleaner.engine import ManifestSession, process_manifest
from manifest_cleaner.exporter import build_port_rows, export_port_excel
from scripts.create_samples import create_vimc


class ReviewSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def session(self):
        return process_manifest(create_vimc(self.root / "input.xlsx"), "VIMC")

    def test_changed_settings_block_export_until_reprocessing(self):
        session = self.session()
        self.assertEqual(session.statistics()["errors"], 0)
        session.metadata["settings_changed"] = True
        with self.assertRaises(ValueError):
            export_port_excel(session, self.root / "bad.xlsx")
        fresh = process_manifest(self.root / "input.xlsx", "VIMC", settings={"number_format": "decimal_dot"})
        self.assertFalse(fresh.metadata.get("settings_changed"))
        export_port_excel(fresh, self.root / "good.xlsx")

    def test_acknowledgement_does_not_remove_unresolved_weight_error(self):
        session = self.session()
        record = session.records[0]
        record.update(FE_Status="E", Weight_Value=None)
        session.base_issues.append({"code": "WEIGHT_ASSOCIATION_AMBIGUOUS", "severity": "error",
                                    "message": "Chưa xác định trọng lượng riêng.", "record_id": record["record_id"], "field": "Weight_Value"})
        session.acknowledge_record(record["record_id"], "Đã mở nguồn")
        self.assertTrue(any(i["code"] == "WEIGHT_ASSOCIATION_AMBIGUOUS" for i in session.validate()))
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_manual_operator_must_belong_to_carrier_configuration(self):
        session = self.session()
        session.update_record(session.records[0]["record_id"], {"Operator": "OTHER"}, "Kiểm tra trường hợp nhập sai")
        self.assertTrue(any(i["code"] == "UNKNOWN_OPERATOR" for i in session.validate()))

    def test_legacy_master_group_quantity_is_preserved_without_counting_copies(self):
        session = self.session()
        first = session.records[0]
        first["Master_BL_Group_ID"] = "GROUP"
        other = copy.deepcopy(first)
        other.update(record_id="SECOND", Container_No="DEMU0000099", BL_No="SECOND-BL")
        session.records.append(other)
        columns, rows = build_port_rows(session)
        self.assertEqual([row[columns.index("Số lượng")] for row in rows], [2, 2])

    def test_verifying_one_field_cannot_clear_coupled_error(self):
        session = self.session()
        record = session.records[0]
        session.base_issues.append({"code": "COUPLED", "severity": "error", "message": "Đối chiếu hai trường.",
                                    "record_id": record["record_id"], "resolution_fields": ["Description", "Weight_Value"]})
        session.update_record(record["record_id"], {"Weight_Value": 15}, "Đã kiểm tra khối lượng")
        self.assertTrue(any(i["code"] == "COUPLED" for i in session.validate()))
        session.update_record(record["record_id"], {"Description": "THEP DA DOI CHIEU"}, "Đã kiểm tra mô tả")
        self.assertFalse(any(i["code"] == "COUPLED" for i in session.validate()))

    def test_true_xls_preserves_formatted_identifier_and_native_number(self):
        source = Path(__file__).parent / "fixtures" / "padded_identifiers.xls"
        name, data = read_workbook(source)[0]
        self.assertEqual(name, "Manifest")
        self.assertEqual(data.iloc[0, 0], "000042")
        self.assertEqual(data.iloc[0, 1], 1.234)


if __name__ == "__main__":
    unittest.main()
