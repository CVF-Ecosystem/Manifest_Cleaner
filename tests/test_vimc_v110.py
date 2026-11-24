"""Independent audit regressions: damaged source rows and party boundaries."""
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from manifest_cleaner.engine import process_manifest
from manifest_cleaner.carriers.vimc.adapter import parse_manifest
from manifest_cleaner.carriers.vimc.parsers import split_container_segments
from manifest_cleaner.exporter import build_port_rows


HEADER = ["PARTICULARS FURNISHED BY SHIPPER", "MARKS & NUMBERS", "B/L", "DISCRIPTION OF GOODS"]
PARTY = "1) TEST SHIPPER\n2) TEST CONSIGNEE\n3) SAME AS CONSIGNEE"
GOOD = "CAIU6448632 123456 20GP 20 THEP DAY"


class Vimc110Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, rows, other_sheets=None):
        book = Workbook()
        sheet = book.active
        sheet.title = "Manifest"
        sheet.append(HEADER)
        for row in rows:
            sheet.append(row)
        for name, extra_rows in (other_sheets or {}).items():
            other = book.create_sheet(name)
            for row in extra_rows:
                other.append(row)
        path = self.root / "manifest.xlsx"
        book.save(path)
        book.close()
        return path

    def standard(self, lines):
        return self.workbook([["B/L NO:", "", "BL-TEST", "COC LADEN"], [PARTY, "", "", ""],
                              *[["", "", "", line] for line in lines]])

    def test_audited_damaged_identifiers_retained_and_block_export(self):
        for identifier in ("VIMU 2300126", "VIMU-2300126", "VIM2300126"):
            with self.subTest(identifier=identifier):
                raw = f"{identifier} 654321 20GP 25 STEEL"
                session = process_manifest(self.standard([GOOD, raw]), "VIMC")
                self.assertEqual(len(session.records), 2)
                bad = session.records[1]
                self.assertEqual(bad["Container_No"], identifier)
                self.assertEqual(bad["raw"]["text"], raw)
                self.assertEqual(bad["Description"], "STEEL")
                self.assertEqual(bad["Weight_Value"], 25)
                self.assertTrue(any(i["code"] == "VIMC_CONTAINER_FORMAT" for i in session.validate()))
                with self.assertRaises(ValueError):
                    build_port_rows(session)
                session.update_record(bad["record_id"], {"Container_No": "VIMU2300126"}, "Đã đọc mã container từ manifest gốc")
                self.assertEqual(len(build_port_rows(session)[1]), 2)
                self.assertEqual(bad["raw"]["text"], raw)

    def test_malformed_marks_retained(self):
        path = self.workbook([["B/L NO:", "", "BL-TEST", "SOC EMPTY"], [PARTY, "VIMU-2300126/20GP", "", ""]])
        session = process_manifest(path, "VIMC")
        self.assertEqual(len(session.records), 1)
        self.assertEqual(session.records[0]["Container_No"], "VIMU-2300126")
        self.assertTrue(any(i["code"] == "VIMC_CONTAINER_FORMAT" for i in session.validate()))

    def test_three_letter_seal_not_split_into_container(self):
        line = "VNLU3097432 VMC1234567 20DC GACH MEN 27000"
        result = parse_manifest(self.standard([line]))
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["Seal_No"], "VMC1234567")

    def test_headings_summaries_and_contact_numbers_not_containers(self):
        for text in ("TOTAL 1234567 20GP", "SEAL 1234567 20GP", "PHONE 1234567 20GP",
                     "(2) X20GP COC", "COC LADEN", "SHIP 1234567 VOYAGE", "GACH MEN"):
            with self.subTest(text=text):
                self.assertEqual(split_container_segments(text), [])
        result = parse_manifest(self.standard([GOOD, "TOTAL 1234567 20GP", "(2) X20GP COC"]))
        self.assertEqual(len(result["records"]), 1)
        self.assertTrue(any(item["text"] == "TOTAL 1234567 20GP" for item in result["metadata"]["source_fragments"]))

    def test_malformed_second_segment_in_same_cell_survives(self):
        line = GOOD + " ; VIMU-2300126 654321 20GP 25 STEEL"
        result = parse_manifest(self.standard([line]))
        self.assertEqual([r["Container_No"] for r in result["records"]], ["CAIU6448632", "VIMU-2300126"])

    def test_coverage_counts_correspond_to_source_fragments(self):
        result = parse_manifest(self.standard([GOOD, "VIMU-2300126 654321 20GP 25 STEEL", "COC LADEN"]))
        coverage = result["metadata"]["coverage"]
        self.assertEqual(coverage["source_fragments"], len(result["metadata"]["source_fragments"]))
        self.assertEqual(coverage["source_fragments"], sum(coverage[f"{s}_fragments"] for s in ("parsed", "unresolved", "ignored", "corroborating")))
        self.assertEqual(coverage["unresolved_fragments"], 1)

    def test_party_continues_to_next_excel_row_and_stops_at_container(self):
        path = self.workbook([
            ["B/L NO:", "", "BL-1", "COC LADEN"], ["1) TEST SHIPPER", "", "", ""],
            ["2)", "", "", ""], ["FULL CONSIGNEE COMPANY LIMITED", "", "", ""],
            ["ADDRESS: HAIPHONG", "", "", ""], ["3) SAME AS CONSIGNEE", "", "", ""],
            ["NOT A PARTY CONTINUATION", "", "", GOOD], ["LATE FOOTNOTE", "", "", ""],
        ])
        result = parse_manifest(path)
        record = result["records"][0]
        self.assertEqual(record["Cleaned_Consignee_Name_For_Output"], "FULL CONSIGNEE COMPANY LIMITED")
        self.assertEqual(record["Consignee"], "FULL CONSIGNEE COMPANY LIMITED\nADDRESS: HAIPHONG")
        self.assertEqual(record["Notify"], record["Consignee"])
        self.assertNotIn("FOOTNOTE", str(record["raw"]["party_evidence"]))
        self.assertTrue(any(item["source_row"] == 5 for item in record["raw"]["party_evidence"]))

    def test_party_does_not_leak_across_bl(self):
        path = self.workbook([
            ["B/L NO:", "", "BL-1", "COC LADEN"], ["2) FIRST COMPANY", "", "", ""], ["", "", "", GOOD],
            ["B/L NO:", "", "BL-2", "COC LADEN"], ["UNMARKED SECOND COMPANY", "", "", ""],
            ["", "", "", "VIMU2300126 654321 20GP 25 STEEL"],
        ])
        result = parse_manifest(path)
        self.assertEqual(result["records"][0]["Consignee"], "FIRST COMPANY")
        self.assertEqual(result["records"][1]["Consignee"], "")
        self.assertTrue(any(i["code"] == "VIMC_CONSIGNEE_MISSING" for i in result["issues"]))

    def test_selected_sheet_limits_scope_and_invalid_sheet_is_clear(self):
        other_rows = [HEADER, ["B/L NO:", "", "BL-2", "COC LADEN"], [PARTY, "", "", ""],
                      ["", "", "", "VIMU2300126 654321 20GP 25 STEEL"]]
        path = self.workbook([["B/L NO:", "", "BL-1", "COC LADEN"], [PARTY, "", "", GOOD]], {"Other": other_rows})
        result = parse_manifest(path, settings={"selected_sheet": "Other"})
        self.assertEqual([r["Container_No"] for r in result["records"]], ["VIMU2300126"])
        self.assertEqual(result["metadata"]["available_sheets"], ["Manifest", "Other"])
        with self.assertRaisesRegex(ValueError, "Không tìm thấy sheet VIMC"):
            parse_manifest(path, settings={"selected_sheet": "Missing"})


if __name__ == "__main__":
    unittest.main()
