"""Independent audit regressions: damaged source rows and party boundaries."""
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from manifest_cleaner.engine import load_review, process_manifest
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

    def workbook(self, rows, other_sheets=None, *, header=HEADER):
        book = Workbook()
        sheet = book.active
        sheet.title = "Manifest"
        sheet.append(header)
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

    def test_first_scoped_party_block_can_use_column_a_when_header_is_in_b(self):
        path = self.workbook([
            ["B/L NO:", "", "BL-1", "", ""], [PARTY, "", "", "", GOOD],
            ["B/L NO:", "", "BL-2", "", ""], ["NO EXPLICIT ROLE", "", "", "", ""],
            ["2) UNRELATED TEXT", "", "", "", "DEMU2222222 123456 20GP 25 STEEL"],
            ["B/L NO:", "", "BL-3", "", ""],
            ["2) CONFLICTING A", "2) MAPPED CONSIGNEE", "", "", "DEMU3333333 123456 20GP 25 STEEL"],
        ], header=["", HEADER[0], "B/L", HEADER[1], HEADER[3]])
        result = parse_manifest(path)
        a, missing, b = result["records"]
        self.assertEqual(result["metadata"]["profile_version"], "vimc-1.2")
        self.assertEqual([record["Cleaned_Consignee_Name_For_Output"] for record in (a, missing, b)],
                         ["TEST CONSIGNEE", "", "MAPPED CONSIGNEE"])
        evidence = next(entry for entry in a["raw"]["party_evidence"] if entry["role"] == "Consignee")
        self.assertEqual((evidence["source_row"], evidence["source_column"], evidence["source_line"]), (3, 1, 2))
        self.assertEqual(a["Notify"], a["Consignee"])
        self.assertEqual(a["Weight_Value"], 20)
        self.assertEqual(a["raw"]["source_column"], 5)

    def test_trailing_owner_total_is_scoped_without_reassigning_fe(self):
        path = self.workbook([
            ["B/L NO:", "", "BL-1", "SOC LADEN"], [PARTY, "", "", ""], ["", "", "", GOOD],
            ["B/L NO:", "", "BL-2", ""], [PARTY, "", "", ""],
            ["", "", "", "DEMU2222222 123456 20GP 25 STEEL\nDEMU3333333 123456 20GP 24 STEEL\nTOTAL: 02X20GP SOC LADEN"],
            ["B/L NO:", "", "BL-3", ""], [PARTY, "", "", GOOD],
        ])
        records = process_manifest(path, "VIMC").records
        self.assertEqual([(r["Operator"], r["FE_Status"]) for r in records],
                         [("SVM", "F"), ("SVM", "F"), ("SVM", "F"), ("VMC", "F")])
        evidence = records[1]["raw"]["ownership_total"]
        self.assertEqual((evidence["source_row"], evidence["source_column"], evidence["source_line"]), (7, 4, 3))
        self.assertEqual((evidence["owner"], evidence["quantity"], evidence["size_type"]), ("SOC", 2, "20GP"))
        self.assertNotIn("ownership_total", records[-1]["raw"])

    def test_trailing_owner_total_requires_order_quantity_type_and_consistent_fe(self):
        cases = [
            [GOOD, "TOTAL: 02X20GP SOC LADEN"],
            [GOOD, "TOTAL: 01X40HC SOC LADEN"],
            [GOOD, "TOTAL: 01X20GP SOC EMPTY"],
            ["TOTAL: 01X20GP SOC LADEN", GOOD],
            [GOOD, "TOTAL: 01X20GP SOC LADEN", "TOTAL: 01X20GP COC LADEN"],
            [GOOD + " COC", "TOTAL: 01X20GP SOC LADEN"],
        ]
        for lines in cases:
            with self.subTest(lines=lines):
                path = self.workbook([["B/L NO:", "", "BL-1", ""], [PARTY, "", "", ""],
                                      *[["", "", "", line] for line in lines]])
                record, = process_manifest(path, "VIMC").records
                self.assertEqual((record["Operator"], record["FE_Status"]), ("VMC", "F"))
                self.assertNotIn("ownership_total", record["raw"])

    def test_compact_id_preserved_only_when_separate_marks_corrobates_same_bill(self):
        compact = "DEMU1234"
        detail = f"{compact} 123456 20GP 25 STEEL"
        path = self.workbook([["B/L NO:", "", "BL-1", ""], [PARTY, "", "", ""],
                              ["", f"{compact}/20GP", "", detail]])
        session = process_manifest(path, "VIMC")
        self.assertEqual([(i["code"], i["severity"]) for i in session.validate()],
                         [("VIMC_LEGACY_COMPACT_CONTAINER", "warning")])
        columns, rows = build_port_rows(session)
        self.assertEqual(rows[0][columns.index("Số Container")], compact)
        self.assertEqual(session.metadata["coverage"]["unresolved_fragments"], 0)
        review = self.root / "review.json"
        session.save_review(review)
        resumed = load_review(review)
        self.assertEqual(build_port_rows(resumed), (columns, rows))
        record, = resumed.records
        for override in ({"Container_No": "DEMU4321"}, {"BL_No": "BL-2"}):
            with self.subTest(override=override):
                edited = load_review(review)
                edited.update_record(record["record_id"], override, "Test manual override")
                self.assertIn("INVALID_CONTAINER", {i["code"] for i in edited.validate()})
                with self.assertRaises(ValueError):
                    build_port_rows(edited)

    def test_compact_id_without_independent_marks_remains_blocking(self):
        compact = "DEMU1234"
        detail = f"{compact} 123456 20GP 25 STEEL"
        cases = [
            [["", "", "", detail]],
            [["", f"{compact}/20GP", "", "EMPTY"]],
            [["", "", "", detail], ["B/L NO:", "", "BL-2", ""],
             [PARTY, f"{compact}/20GP", "", "EMPTY"]],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                path = self.workbook([["B/L NO:", "", "BL-1", ""], [PARTY, "", "", ""], *rows])
                session = process_manifest(path, "VIMC")
                self.assertIn("INVALID_CONTAINER", {i["code"] for i in session.validate()})
                with self.assertRaises(ValueError):
                    build_port_rows(session)

    def test_compact_id_needs_an_exact_marks_line_with_the_same_size(self):
        compact = "DEMU1234"
        detail = f"{compact} 123456 20GP 25 STEEL"
        for marks in (f"REFERENCE ONLY - {compact} NOT A CONTAINER", f"REFERENCE ONLY - {compact}/20GP",
                      f"{compact}/20GP REFERENCE ONLY", f"{compact}/40HC", compact):
            with self.subTest(marks=marks):
                path = self.workbook([["B/L NO:", "", "BL-1", ""], [PARTY, "", "", ""], ["", marks, "", detail]])
                session = process_manifest(path, "VIMC")
                self.assertEqual(len(session.records), 1)
                self.assertEqual(session.records[0]["raw"]["marks_evidence"][0]["text"], marks)
                codes = {i["code"] for i in session.validate()}
                self.assertIn("INVALID_CONTAINER", codes)
                self.assertNotIn("VIMC_LEGACY_COMPACT_CONTAINER", codes)
                with self.assertRaises(ValueError):
                    build_port_rows(session)

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
