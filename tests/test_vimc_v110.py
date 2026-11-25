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

    def test_detail_preserves_exact_seal_case_punctuation_and_spacing(self):
        seals = ("00aB-7;  cD/09", "/MiXeD\t\t00--2", "NA", "N/A", "-")
        lines = [f"DEMU000000{idx} {seal} 20GP 25 STEEL" for idx, seal in enumerate(seals, 1)]
        result = parse_manifest(self.standard(lines))
        self.assertEqual(tuple(record["Seal_No"] for record in result["records"]), seals)
        self.assertEqual(tuple(record["raw"]["seal"] for record in result["records"]), seals)
        self.assertEqual({record["Weight_Kind"] for record in result["records"]}, {"gross"})
        self.assertEqual({record["Weight_Value"] for record in result["records"]}, {25})
        self.assertEqual({record["FE_Status"] for record in result["records"]}, {"F"})

    def test_container_shaped_seal_retains_its_slot_and_subsequent_detail(self):
        first = "DEMU1111111 abCd0000123 20GP 25 STEEL"
        second = "DEMU2222222 001234 40HC 26 STEEL"
        path = self.standard([f"{first} ; {second}"])
        records = parse_manifest(path)["records"]
        self.assertEqual([record["Container_No"] for record in records], ["DEMU1111111", "DEMU2222222"])
        self.assertEqual([record["Seal_No"] for record in records], ["abCd0000123", "001234"])

    def test_marks_keep_two_adjacent_ids_as_separate_detail_candidates(self):
        path = self.workbook([
            ["B/L NO:", "", "BL-1", "COC LADEN"], [PARTY, "", "", ""],
            ["", "DEMU1111111/20GP DEMU2222222/20GP", "", "DEMU1111111 DEMU2222222 20GP 25 STEEL"],
        ])
        result = parse_manifest(path)
        self.assertEqual([record["Container_No"] for record in result["records"]], ["DEMU1111111", "DEMU2222222"])
        self.assertIsNone(result["records"][1]["Seal_No"])
        self.assertTrue(any(finding["code"] == "VIMC_CONTAINER_UNPARSED" for finding in result["issues"]))

    def test_competing_detail_rows_are_not_absorbed_as_a_seal_without_marks(self):
        for line in ("DEMU1111111 123456 DEMU2222222 654321 20GP 25 STEEL",
                     "DEMU1111111 DEMU2222222 654321 20GP 25 STEEL",
                     "DEMU1111111 123456 DEMU2222222 20GP 25 STEEL",
                     "DEMU1111111 DEMU2222222 40HC 20GP 25 STEEL"):
            with self.subTest(line=line):
                result = parse_manifest(self.standard([line]))
                self.assertEqual([record["Container_No"] for record in result["records"]],
                                 ["DEMU1111111", "DEMU2222222"])
                self.assertTrue(any(finding["code"] == "VIMC_CONTAINER_UNPARSED" for finding in result["issues"]))

    def test_known_weighted_size_is_preferred_over_size_shaped_seal_text(self):
        lines = ["DEMU1111111 00ax  /77  20GP 25 STEEL", "DEMU2222222 Seal-001 99WT 27 STEEL"]
        first, second = parse_manifest(self.standard(lines))["records"]
        self.assertEqual((first["Seal_No"], first["Size_Type"], first["Weight_Value"]), ("00ax  /77", "20GP", 25))
        self.assertEqual((second["Seal_No"], second["Size_Type"], second["Weight_Value"]), ("Seal-001", "99WT", 27))

    def test_adjacent_supported_size_candidates_require_review_even_with_same_weight(self):
        line = "DEMU1111111 40HC 20GP STEEL 25000"
        session = process_manifest(self.standard([line]), "VIMC")
        record, = session.records
        alternatives = record["raw"]["ambiguous_candidates"]
        self.assertEqual([(c["seal_no"], c["size_type"], c["description"]) for c in alternatives],
                         [(None, "40HC", "20GP STEEL"), ("40HC", "20GP", "STEEL")])
        self.assertEqual(record["raw"]["text"], line)
        self.assertEqual(record["Weight_Value"], 25)
        issue = next(i for i in session.validate() if i["code"] == "VIMC_SEAL_TYPE_AMBIGUOUS")
        self.assertEqual(issue["resolution_fields"], ["Seal_No", "Size_Type", "Description"])
        self.assertEqual(session.metadata["coverage"]["unresolved_fragments"], 1)
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.update_record(record["record_id"], {}, "Verified type and goods but omitted seal",
                              verified_fields=["Size_Type", "Description"])
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.update_record(record["record_id"], {}, "Verified blank seal", verified_fields=["Seal_No"])
        cols, rows = build_port_rows(session)
        self.assertEqual(rows[0][cols.index("Số niêm chì")], "")

    def test_adjacent_size_candidates_do_not_hide_alternate_weight_layout(self):
        line = "DEMU1111111 40HC 20GP 25 STEEL 25000"
        session = process_manifest(self.standard([line]), "VIMC")
        record, = session.records
        self.assertIsNone(record["Weight_Value"])
        alternatives = record["raw"]["ambiguous_candidates"]
        self.assertEqual([(c["size_type"], c["weight_raw"], c["source_unit"]) for c in alternatives],
                         [("40HC", "25000", "KGS"), ("20GP", "25", "TONS"), ("20GP", "25000", "KGS")])
        issue = next(i for i in session.validate() if i["code"] == "VIMC_SEAL_TYPE_AMBIGUOUS")
        self.assertEqual(issue["resolution_fields"], ["Seal_No", "Size_Type", "Description", "Weight_Value"])
        session.update_record(record["record_id"], {"Seal_No": "40HC", "Size_Type": "20GP", "Description": "STEEL"},
                              "Verified seal, size and goods")
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.update_record(record["record_id"], {"Weight_Value": 25}, "Verified weight")
        self.assertEqual(len(build_port_rows(session)[1]), 1)

    def test_weight_kind_override_still_available_to_direct_adapter(self):
        path = self.standard([GOOD])
        for kind in ("cargo", "unknown"):
            with self.subTest(kind=kind):
                record, = parse_manifest(path, settings={"weight_kind": kind})["records"]
                self.assertEqual(record["Weight_Kind"], kind)
                self.assertEqual(record["Weight_Value"], 20)

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
        self.assertEqual(result["metadata"]["profile_version"], "vimc-1.3.3")
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

    def test_empty_total_matches_marks_on_both_pages(self):
        marks = "DEMU1234567/20RF\nDEMU1234568/40RF"
        for total, operator in (("TOTAL: 1X20RF+2X40RF, COC EMPTY", "VMC"),
                                ("TOTAL: 1X20RF & 2X40RF SOC RF EMPTY", "SVM")):
            with self.subTest(total=total):
                session = process_manifest(self.workbook([
                    ["B/L NO:", marks, "BL-1", total],
                    [PARTY, "", "", ""],
                    ["", "DEMU1234569/40RF", "", ""],
                    ["B/L NO:", "", "BL-2", ""],
                    [PARTY, "", "", GOOD],
                ]), "VIMC")
                self.assertEqual([(r["FE_Status"], r["Operator"], r["Weight_Value"]) for r in session.records],
                                 [("E", operator, None)] * 3 + [("F", "VMC", 20)])
                self.assertEqual(session.statistics()["errors"], 0)
                evidence = session.records[2]["raw"]["empty_total_evidence"]
                self.assertEqual((evidence["source_row"], evidence["source_column"], evidence["declared_sizes"]),
                                 (2, 4, {"20RF": 1, "40RF": 2}))

    def test_empty_total_must_match_entire_marks_list(self):
        for description in ("TOTAL: 2X20RF, SOC EMPTY", "TOTAL: 1X40RF, SOC EMPTY",
                            "TOTAL: 1X20RF, SOC EMPTY\nCOC LADEN",
                            "TOTAL: 1X20RF, SOC EMPTY\nTOTAL: 1X20RF, SOC EMPTY"):
            with self.subTest(description=description):
                session = process_manifest(self.workbook([
                    ["B/L NO:", "DEMU1234567/20RF", "BL-1", description],
                    [PARTY, "", "", ""],
                ]), "VIMC")
                record, = session.records
                self.assertNotEqual(record["FE_Status"], "E")
                self.assertNotIn("empty_total_evidence", record["raw"])
                self.assertGreater(session.statistics()["errors"], 0)

    def test_rf_empty_is_exact_status_on_detail(self):
        session = process_manifest(self.standard([
            "DEMU1234567 001237 40RF 4.3 SOC RF EMPTY",
            "DEMU1234568 001238 40RF 25 EMPTY BOTTLES",
        ]), "VIMC")
        empty, full = session.records
        self.assertEqual((empty["FE_Status"], empty["Weight_Value"], full["FE_Status"]), ("E", 4.3, "F"))
        self.assertNotIn("VIMC_STATUS_GOODS_CONFLICT", {issue["code"] for issue in session.validate()})

    def test_hc_height_and_reefer_evidence_resolve_to_exportable_warning(self):
        marks = "DEMU1234567/40RF"
        line = "DEMU1234567 001237 40HC 20 RF TEST -18OC"
        session = process_manifest(self.workbook([
            ["B/L NO:", marks, "BL-1", line], [PARTY, "", "", ""],
        ]), "VIMC")
        record, = session.records
        self.assertEqual((record["Size_Type"], record["Physical_ISO_Size"], record["FE_Status"]),
                         ("40RH", "45R1", "F"))
        self.assertEqual(record["raw"]["size_type"], "40HC")
        self.assertEqual(record["raw"]["marks_evidence"][0]["size_type"], "40RF")
        self.assertEqual([(i["code"], i["severity"]) for i in session.validate()],
                         [("VIMC_REEFER_SIZE_REVIEW", "warning")])
        columns, (row,) = build_port_rows(session)
        self.assertEqual(row[columns.index("Loại Container")], "40RH")
        self.assertEqual(row[columns.index("Loại hàng")], "REEFER")
        self.assertEqual(row[columns.index("Số niêm chì")], "001237")
        self.assertIn("MARKS ghi 40RF", row[columns.index("Ghi chú")])
        review = self.root / "reefer.review.json"
        session.save_review(review)
        self.assertEqual(build_port_rows(load_review(review)), (columns, [row]))

    def test_marks_conflict_stays_blocking_without_consistent_cold_evidence(self):
        for marks, line in (
            ("DEMU1234567/40RF", "DEMU1234567 001237 40HC 20 STEEL"),
            ("DEMU1234567/20RF", "DEMU1234567 001237 40HC 20 RF TEST"),
            ("DEMU1234567/40RF\nDEMU1234567/20RF", "DEMU1234567 001237 40HC 20 RF TEST"),
        ):
            with self.subTest(marks=marks, line=line):
                session = process_manifest(self.workbook([
                    ["B/L NO:", marks, "BL-1", line], [PARTY, "", "", ""],
                ]), "VIMC")
                self.assertEqual(session.records[0]["Size_Type"], "40HC")
                self.assertIn(("VIMC_MARKS_SIZE_CONFLICT", "error"),
                              {(i["code"], i["severity"]) for i in session.validate()})
                with self.assertRaises(ValueError):
                    build_port_rows(session)

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
