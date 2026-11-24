"""Regression cases for weight warnings using synthetic workbooks."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from manifest_cleaner.common import parse_weight
from manifest_cleaner.engine import load_review, process_manifest
from manifest_cleaner.exporter import build_port_rows
from scripts.create_samples import CREATORS


BELOW_TARE = "GROSS_WEIGHT_BELOW_TARE"
DOT_GROUPING = "KGS_DOT_GROUPING"


class WeightWarningTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def session(self, carrier, weight, settings=None):
        path = CREATORS[carrier](self.folder / f"{carrier}.xlsx", weight=weight)
        return process_manifest(path, carrier, settings=settings)

    def vimc_kg(self, weight):
        path = CREATORS["VIMC"](self.folder / "vimc_kg.xlsx")
        book = load_workbook(path)
        try:
            book.active["D5"] = f"DEMU0000002 001235 20GP THEP DEMO {weight}"
            book.save(path)
        finally:
            book.close()
        return process_manifest(path, "VIMC")

    def weight_warnings(self, session):
        return {item["code"]: item for item in session.validate()
                if item["code"] in {BELOW_TARE, DOT_GROUPING}}

    def test_single_dot_kg_keeps_legacy_value_and_warns_from_each_carrier(self):
        sessions = [
            (self.vimc_kg("12.500"), "D5"),
            (self.session("VOSCO", "12.500 KGS"), "S17"),
            (self.session("VINAFCO", "12.500", {"default_weight_unit": "KGS"}), "G5"),
        ]
        self.assertEqual(parse_weight("12.500 KGS")["value"], 0.0125)
        for session, cell in sessions:
            with self.subTest(carrier=session.carrier):
                row, = session.records
                self.assertEqual(row["Weight_Value"], 0.0125)
                warning = self.weight_warnings(session)[DOT_GROUPING]
                self.assertEqual((warning["severity"], warning["field"], warning["source_cell"]),
                                 ("warning", "Weight_Value", cell))
                for expected in ("12.500", "12.5 tấn", "0.0125 tấn", row["Container_No"]):
                    self.assertIn(expected, warning["message"])
                self.assertEqual(len(build_port_rows(session)[1]), 1)

    def test_multi_dot_kg_keeps_grouped_value_and_explains_invalid_decimal(self):
        session = self.session("VOSCO", "1.234.567 KGS")
        self.assertEqual(session.records[0]["Weight_Value"], 1234.567)
        warning = self.weight_warnings(session)[DOT_GROUPING]
        self.assertIn("1234.567 tấn", warning["message"])
        self.assertIn("dấu thập phân không hợp lệ", warning["message"])

    def test_comma_native_excel_and_explicit_number_format_skip_dot_warning(self):
        kg = {"default_weight_unit": "KGS"}
        for carrier in ("VOSCO", "VINAFCO"):
            for weight, settings, expected in (("12,500 KGS", None, 12.5), (12.501, kg, 0.012501),
                    ("12.500 KGS", {"number_format": "decimal_comma"}, 12.5),
                    ("12.500 KGS", {"number_format": "decimal_dot"}, 0.0125), ("12.500 TONS", None, 12.5)):
                with self.subTest(carrier=carrier, weight=weight, settings=settings):
                    session = self.session(carrier, weight, settings)
                    self.assertEqual(session.records[0]["Weight_Value"], expected)
                    self.assertNotIn(DOT_GROUPING, self.weight_warnings(session))

    def test_only_positive_gross_full_below_reference_is_flagged(self):
        session = self.vimc_kg("12.500")
        row, = session.records
        warning = self.weight_warnings(session)[BELOW_TARE]
        for part in ("0.0125 tấn", "2.5 tấn", "12.500", "D5"):
            self.assertIn(part, warning["message"])
        session.update_record(row["record_id"], {"Weight_Value": 2.5}, "Bằng vỏ tham chiếu")
        self.assertNotIn(BELOW_TARE, self.weight_warnings(session))
        session.update_record(row["record_id"], {"FE_Status": "E", "Weight_Value": 1}, "Dòng khai rỗng")
        self.assertNotIn(BELOW_TARE, self.weight_warnings(session))
        session.update_record(row["record_id"], {"FE_Status": "F", "Weight_Value": 0}, "Dòng khai 0")
        self.assertNotIn(BELOW_TARE, self.weight_warnings(session))
        self.assertIn("ZERO_FULL_WEIGHT", {item["code"] for item in session.validate()})

    def test_carrier_reference_tables_and_unknown_reference(self):
        for carrier, size, limit, settings in [
            ("VOSCO", "20TK", 5.5, None),
            ("VIMC", "45G1", 4.3, None),
            ("VINAFCO", "20RF", 3.2, {"tare_20rf_empty_vgm": 3.2}),
        ]:
            with self.subTest(carrier=carrier):
                session = self.session(carrier, 12, settings)
                row, = session.records
                session.update_record(row["record_id"], {"Size_Type": size, "Weight_Value": limit - 0.1}, "Test")
                self.assertIn(f"{limit:g} tấn", self.weight_warnings(session)[BELOW_TARE]["message"])
        session = self.session("VIMC", 12, {"size_to_vtos": {"CUSTOM": "PORT"}})
        session.update_record(session.records[0]["record_id"], {"Size_Type": "CUSTOM", "Weight_Value": 1}, "No tare")
        self.assertFalse(session.validate())  # Supported port mapping, but no established tare.

    def test_edits_and_field_verification_recompute_each_warning(self):
        session = self.vimc_kg("12.500")
        rid = session.records[0]["record_id"]
        self.assertEqual(set(self.weight_warnings(session)), {BELOW_TARE, DOT_GROUPING})
        session.update_record(rid, {"Seal_No": "0099"}, "Chỉ sửa seal")
        self.assertEqual(set(self.weight_warnings(session)), {BELOW_TARE, DOT_GROUPING})
        session.update_record(rid, {}, "Đã đối chiếu trọng lượng", verified_fields=["Weight_Value"])
        self.assertFalse(self.weight_warnings(session))
        session.update_record(rid, {"Weight_Value": 1}, "Giá trị mới vẫn dưới ngưỡng")
        self.assertEqual(set(self.weight_warnings(session)), {BELOW_TARE})
        session.update_record(rid, {"Weight_Value": 12.5}, "Số đã sửa theo nguồn")
        self.assertFalse(self.weight_warnings(session))

    def test_row_acknowledgment_confirms_weight_warnings_until_next_edit(self):
        session = self.vimc_kg("12.500")
        rid = session.records[0]["record_id"]
        self.assertEqual(set(self.weight_warnings(session)), {BELOW_TARE, DOT_GROUPING})
        session.acknowledge_record(rid, "Đã đối chiếu manifest gốc")
        self.assertFalse(self.weight_warnings(session))
        path = self.folder / "acknowledged.review.json"
        session.save_review(path)
        session = load_review(path)
        self.assertFalse(self.weight_warnings(session))
        session.update_record(rid, {"Weight_Value": 1}, "Giá trị mới vẫn dưới ngưỡng")
        self.assertEqual(set(self.weight_warnings(session)), {BELOW_TARE})

    def test_review_v2_preserves_source_evidence_verified_and_edited_weights(self):
        session = self.vimc_kg("12.500")
        rid = session.records[0]["record_id"]
        path = self.folder / "session.review.json"
        with patch("manifest_cleaner.engine.__version__", "1.2.5"):
            session.save_review(path)
        resumed = load_review(path)
        self.assertEqual(set(self.weight_warnings(resumed)), {BELOW_TARE, DOT_GROUPING})
        for changes, verified in (({}, ["Weight_Value"]), ({"Weight_Value": 12.5}, [])):
            resumed.update_record(rid, changes, "Đã đối chiếu nguồn", verified_fields=verified)
            resumed.save_review(path)
            resumed = load_review(path)
            self.assertFalse(self.weight_warnings(resumed))
            self.assertEqual(resumed.records[0]["raw"]["weight"], "12.500")

    def test_old_vinafco_review_can_open_without_native_cell_type(self):
        session = self.session("VINAFCO", 12.501, {"default_weight_unit": "KGS"})
        session.records[0]["raw"].pop("weight_cell_is_text")
        path = self.folder / "old.review.json"
        with patch("manifest_cleaner.engine.__version__", "1.2.5"):
            session.save_review(path)
        reopened = load_review(path)
        self.assertEqual(reopened.records[0]["Weight_Value"], 0.012501)
        self.assertNotIn(DOT_GROUPING, self.weight_warnings(reopened))
