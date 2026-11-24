"""Source-regression and workbook integration tests for the VIMC adapter."""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from openpyxl import Workbook

from manifest_cleaner.carriers.vimc.adapter import is_supported_size_type, parse_manifest, refresh_derived_fields
from manifest_cleaner.carriers.vimc.parsers import (
    DANANG_CONTAINER_DETAIL_PATTERN, MARINER_CONTAINER_DETAIL_PATTERN,
    PIONEER_CONTAINER_DETAIL_PATTERN, is_valid_container, parse_marks_container,
    parse_structured_line, parse_weight_kg, parse_weight_tons,
)

HEADER = ["PARTICULARS FURNISHED BY SHIPPER", "MARKS & NUMBERS", "B/L", "DISCRIPTION OF GOODS"]
PARTY = "1) TEST SHIPPER\n2) TEST CONSIGNEE\n3) SAME AS CONSIGNEE"


class VimcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, groups, *, filename="manifest.xlsx", title="Manifest", extra_sheets=None):
        book = Workbook()
        sheet = book.active
        sheet.title = title
        sheet.append(HEADER)
        for group in groups:
            sheet.append(["B/L NO:", "", group.get("bl", "TEST-BL"), group.get("status", "")])
            sheet.append([group.get("party", PARTY), group.get("party_marks", ""), "", group.get("party_desc", "")])
            for line in group.get("lines", []):
                sheet.append(["", "", "", line])
            for line in group.get("marks", []):
                sheet.append(["", line, "", ""])
        for name, rows in (extra_sheets or {}).items():
            other = book.create_sheet(name)
            for row in rows:
                other.append(row)
        path = self.root / filename
        book.save(path)
        return path

    def parse(self, groups, **kwargs):
        return parse_manifest(self.workbook(groups, **kwargs))

    def codes(self, result):
        return {finding["code"] for finding in result["issues"]}

    def test_legacy_parser_examples(self):
        self.assertTrue(is_valid_container("ABCD1234567"))
        self.assertTrue(is_valid_container("abcd1234567"))
        self.assertFalse(is_valid_container("ABCD123"))
        self.assertFalse(is_valid_container("ABC1234567"))
        examples = [
            (MARINER_CONTAINER_DETAIL_PATTERN, "VNLU3097432 VMC134321 20DC GACH MEN 27,000", "VNLU3097432", "27,000"),
            (PIONEER_CONTAINER_DETAIL_PATTERN, "CAIU6448632 A29395250 20GP 20 THEP DAY", "CAIU6448632", "20"),
            (DANANG_CONTAINER_DETAIL_PATTERN, "VIMU6252197 A29005256 40HC VO LON 8000", "VIMU6252197", "8000"),
        ]
        for pattern, line, container, weight in examples:
            with self.subTest(line=line):
                match = pattern.match(line)
                self.assertIsNotNone(match)
                self.assertEqual(match.group("container_no"), container)
                self.assertEqual(match.group("weight"), weight)
        self.assertEqual(parse_weight_tons("27,08"), 27.08)
        self.assertEqual(parse_weight_tons("1,5"), 1.5)
        self.assertEqual(parse_weight_tons("1,000"), 1.0)
        self.assertEqual(parse_weight_kg("27,000"), 27.0)
        self.assertEqual(parse_weight_kg("8000"), 8.0)

    def test_mixed_layouts_filename_independent(self):
        groups = [{"status": "COC LADEN", "lines": [
            "VNLU3097432 VMC134321 20DC GACH MEN 27,000",
            "CAIU6448632 A29395250 20GP 20 THEP DAY",
            "VIMU6252197 A29005256 40HC VO LON 8000",
        ]}]
        first = self.parse(groups, filename="MARINER.xlsx")
        second = self.parse(groups, filename="PIONEER.xlsx")
        self.assertEqual(len(first["records"]), 3)
        for key in ("Container_No", "Weight_Value", "Size_Type", "FE_Status", "Description"):
            self.assertEqual([row[key] for row in first["records"]], [row[key] for row in second["records"]])
        self.assertEqual([row["Weight_Value"] for row in first["records"]], [27.0, 20.0, 8.0])
        self.assertFalse([item for item in first["issues"] if item["severity"] == "error"])
        self.assertEqual(first["records"][0]["Notify"], "TEST CONSIGNEE")

    def test_ambiguous_numeric_edges_retained(self):
        result = self.parse([{"lines": ["CAIU6448632 A29395250 20GP 20 STEEL 12000"]}])
        self.assertEqual(len(result["records"]), 1)
        row = result["records"][0]
        self.assertIsNone(row["Weight_Value"])
        self.assertEqual(len(row["raw"]["ambiguous_candidates"]), 2)
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", self.codes(result))
        self.assertIn("20 STEEL 12000", row["Description"])

    def test_unparsed_container_is_never_dropped(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 20GP 20 THEP DAY",
            "VIMU2300126 654321 20GP BAD_WEIGHT STEEL",
        ]}])
        self.assertEqual(len(result["records"]), 2)
        self.assertIn("VIMC_CONTAINER_UNPARSED", self.codes(result))
        self.assertEqual(result["records"][1]["raw"]["weight"], None)
        self.assertIn("BAD_WEIGHT", result["records"][1]["raw"]["text"])

    def test_missing_consignee_record_retained(self):
        result = self.parse([{"party": "1) SHIPPER ONLY", "lines": ["CAIU6448632 123456 20GP 20 THEP DAY"]}])
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("VIMC_CONSIGNEE_MISSING", self.codes(result))

    def test_empty_bottles_does_not_poison_bl(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 20GP 20 EMPTY BOTTLES",
            "VIMU2300126 654321 20GP 25 STEEL",
        ]}])
        self.assertEqual([row["FE_Status"] for row in result["records"]], ["F", "F"])
        self.assertEqual([row["Description"] for row in result["records"]], ["EMPTY BOTTLES", "STEEL"])

    def test_light_cargo_is_not_empty_by_tare_threshold(self):
        result = self.parse([{"lines": ["CAIU6448632 123456 20GP 2 LIGHT CARGO"]}])
        self.assertEqual(result["records"][0]["FE_Status"], "F")
        self.assertEqual(result["records"][0]["Description"], "LIGHT CARGO")

    def test_zero_retained_and_scoped_empty(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 20GP 0 EMPTY",
            "VIMU2300126 654321 20GP 25 STEEL",
        ]}])
        empty, loaded = result["records"]
        self.assertEqual(empty["Weight_Value"], 0.0)
        self.assertEqual(empty["Weight_Unit"], "TONS")
        self.assertEqual(empty["FE_Status"], "E")
        self.assertEqual(loaded["FE_Status"], "F")
        self.assertEqual(loaded["Description"], "STEEL")

    def test_later_empty_heading_does_not_rewrite_earlier_loaded_detail(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 20GP 25 STEEL",
            "SOC EMPTY",
            "VIMU2300126 654321 20GP 0 EMPTY",
        ]}])
        self.assertEqual([row["FE_Status"] for row in result["records"]], ["F", "E"])
        self.assertEqual(result["records"][0]["Description"], "STEEL")

    def test_later_owner_heading_does_not_rewrite_earlier_container(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 20GP 25 STEEL",
            "SOC LADEN",
            "VIMU2300126 654321 20GP 20 RICE",
        ]}])
        self.assertEqual([row["Operator"] for row in result["records"]], ["VMC", "SVM"])

    def test_empty_marks_and_multiple_containers_without_sizes(self):
        result = self.parse([{"status": "SOC EMPTY", "marks": ["VNLU3097432/20DC CAIU6448632/40HC"]}])
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual({row["Operator"] for row in result["records"]}, {"SVM"})
        self.assertEqual({row["FE_Status"] for row in result["records"]}, {"E"})
        self.assertEqual([row["Weight_Value"] for row in result["records"]], [None, None])
        marks = parse_marks_container("VNLU3097432 CAIU6448632")
        self.assertEqual([item["container_no"] for item in marks], ["VNLU3097432", "CAIU6448632"])

    def test_loaded_marks_without_detail_retained_as_error(self):
        result = self.parse([{"status": "COC LADEN", "marks": ["VNLU3097432/20DC"]}])
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("VIMC_CONTAINER_UNPARSED", self.codes(result))

    def test_duplicate_same_bl_warns_without_deletion(self):
        result = self.parse([{"lines": ["CAIU6448632 123456 20GP 20 THEP DAY"] * 2}])
        self.assertEqual(len(result["records"]), 2)
        self.assertIn("VIMC_DUPLICATE_IN_BL", self.codes(result))
        self.assertNotEqual(result["records"][0]["record_id"], result["records"][1]["record_id"])

    def test_container_shared_across_bl_not_deduplicated(self):
        line = "CAIU6448632 123456 20GP 20 THEP DAY"
        result = self.parse([{"bl": "BL-1", "lines": [line]}, {"bl": "BL-2", "lines": [line]}])
        self.assertEqual(len(result["records"]), 2)
        self.assertNotIn("VIMC_DUPLICATE_IN_BL", self.codes(result))

    def test_source_type_separate_vtos_and_tank_mapping_preserved(self):
        result = self.parse([{"lines": [
            "CAIU6448632 123456 40GP 20 GOODS",
            "VIMU2300126 654321 20TK 25 OIL",
        ]}])
        row, tank = result["records"]
        self.assertEqual(row["Size_Type"], "40GP")
        self.assertEqual(row["Physical_ISO_Size"], "42G1")
        self.assertEqual(row["VTOS_Size"], "40HC")
        self.assertEqual(row["raw"]["size_type"], "40GP")
        self.assertEqual(tank["Cargo_Type"], "GENERAL")

    def test_party_row_goods_no_longer_skipped(self):
        result = self.parse([{"party_desc": "CAIU6448632 123456 20GP 20 THEP DAY"}])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["source_row"], 3)

    def test_marks_detail_correspondence_keeps_evidence(self):
        result = self.parse([{"lines": ["CAIU6448632 123456 20GP 20 THEP DAY"], "marks": ["CAIU6448632/20GP"]}])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(result["records"][0]["raw"]["marks_evidence"]), 1)
        self.assertEqual(result["metadata"]["row_layout_counts"]["corroborating_marks"], 1)

    def test_explicit_empty_group_does_not_destroy_conflicting_goods(self):
        result = self.parse([{"status": "SOC EMPTY", "lines": ["CAIU6448632 123456 20GP 20 EMPTY BOTTLES"]}])
        self.assertEqual(result["records"][0]["Description"], "EMPTY BOTTLES")
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(result))

    def test_refresh_after_edit_never_infers_status_or_overwrites_goods(self):
        source = {"Size_Type": "20RF", "FE_Status": "E", "Description": "USER GOODS", "Operator": "SVM"}
        refreshed = refresh_derived_fields(source)
        self.assertEqual(refreshed["VTOS_Size"], "22R0")
        self.assertEqual(refreshed["Cargo_Type"], "EMPTY REEFER")
        self.assertEqual(refreshed["Description"], "USER GOODS")
        self.assertEqual(refreshed["FE_Status"], "E")
        self.assertEqual(refreshed["Operator"], "SVM")
        self.assertNotIn("VTOS_Size", source)

    def test_known_size_types_include_own_port_labels_and_configured_mappings(self):
        self.assertTrue(is_supported_size_type("40GP"))
        self.assertTrue(is_supported_size_type("22G1"))
        self.assertTrue(is_supported_size_type("22R0"))
        self.assertFalse(is_supported_size_type("99ZZ"))
        settings = {"size_to_vtos": {"CUSTOM": "PORT20"}, "cargo_type_mapping": {"CUSTOM": "REEFER"}}
        self.assertTrue(is_supported_size_type("CUSTOM", settings))
        changed = refresh_derived_fields({"Size_Type": "CUSTOM", "FE_Status": "F"}, settings)
        self.assertEqual(changed["VTOS_Size"], "PORT20")
        self.assertEqual(changed["Cargo_Type"], "REEFER")
        self.assertEqual(refresh_derived_fields({"Size_Type": "22R0", "FE_Status": "F"})["Cargo_Type"], "REEFER")

    def test_missing_header_keeps_detected_candidate(self):
        book = Workbook()
        book.active.append(["CAIU6448632 123456 20GP 20 GOODS"])
        path = self.root / "no_header.xlsx"
        book.save(path)
        result = parse_manifest(path)
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("VIMC_HEADER_NOT_FOUND", self.codes(result))
        self.assertIn("VIMC_BL_MISSING", self.codes(result))

    def test_numeric_locale_settings_and_no_early_rounding(self):
        path = self.workbook([{"lines": ["CAIU6448632 123456 20GP GOODS 27.000,50"]}])
        result = parse_manifest(path, settings={"number_format": "decimal_comma"})
        self.assertAlmostEqual(result["records"][0]["Weight_Value"], 27.0005)
        self.assertEqual(result["records"][0]["Weight_Unit"], "TONS")

    def test_renamed_xlsx_to_xls_uses_signature(self):
        path = self.workbook([{"lines": ["CAIU6448632 123456 20GP 20 GOODS"]}])
        renamed = path.with_suffix(".xls")
        path.rename(renamed)
        self.assertEqual(len(parse_manifest(renamed)["records"]), 1)

    def test_legacy_three_column_sheet_and_container_looking_bl(self):
        book = Workbook()
        sheet = book.active
        sheet.append([HEADER[0], HEADER[1], HEADER[3]])
        sheet.append(["B/L NO:", "", "ABCD1234567"])
        sheet.append([PARTY, "", "CAIU6448632 123456 20GP 20 GOODS"])
        path = self.root / "three_columns.xlsx"
        book.save(path)
        result = parse_manifest(path)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["BL_No"], "ABCD1234567")
        self.assertEqual(result["records"][0]["Container_No"], "CAIU6448632")

    def test_manifest_sheet_after_cover_sheet(self):
        path = self.workbook([{"lines": ["CAIU6448632 123456 20GP 20 GOODS"]}])
        from openpyxl import load_workbook
        book = load_workbook(path)
        cover = book.create_sheet("Cover", 0)
        cover.append(["Cover sheet without manifest data"])
        book.save(path)
        result = parse_manifest(path)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["source_sheet"], "Manifest")


if __name__ == "__main__":
    unittest.main()
