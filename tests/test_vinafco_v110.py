"""VINAFCO 1.1: independent regressions for units, schema changes and missing IDs."""
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from manifest_cleaner.carriers.vinafco.adapter import parse_manifest
from manifest_cleaner.carriers.vinafco.profile import INPUT_COLUMNS
from manifest_cleaner.engine import process_manifest
from manifest_cleaner.exporter import build_port_rows


class Vinafco110Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.fields = list(INPUT_COLUMNS)

    def row(self, **values):
        return [values.get(field, "") for field in self.fields]

    def headers(self, weight="GW"):
        headers = list(INPUT_COLUMNS.values())
        headers[self.fields.index("gw")] = weight
        return headers

    def container(self, number="MSCU1234567", **changes):
        return self.row(**{"container_no": number, "seal": "001234", "type": "20DC",
                           "comm": "CARGO", "gw": 25, **changes})

    def workbook(self, rows, *, weight="GW", filename="manifest.xlsx", prefix=None):
        book = Workbook()
        sheet = book.active
        sheet.title = "MANIFEST"
        sheet.append(self.headers(weight))
        for row in prefix if prefix is not None else [
            self.row(party_raw="(S) SHIPPER", bill_no="BL-001"),
            self.row(party_raw="(C) CONSIGNEE"),
        ]:
            sheet.append(row)
        for row in rows:
            sheet.append(row)
        path = self.folder / filename
        book.save(path)
        book.close()
        return path

    def test_joined_weight_headers_and_punctuated_headers_have_identical_units(self):
        for index, label in enumerate(("GWKGS", "GROSSWEIGHTKG", "GROSSWTKGS", "GW (KGS)", "G.W. (KILOGRAMS)")):
            with self.subTest(header=label):
                path = self.workbook([self.container(gw=25000)], weight=label, filename=f"unit_{index}.xlsx")
                session = process_manifest(path, "VINAFCO")
                self.assertEqual(session.metadata["default_weight_unit"], "KGS")
                self.assertEqual(session.records[0]["Weight_Value"], 25)
                self.assertEqual(session.records[0]["raw"]["weight_source_unit"], "KGS")
                self.assertEqual(session.metadata["source_weight_units"], ["KGS"])
                self.assertFalse([i for i in session.validate() if i["severity"] == "error"])
                columns, rows = build_port_rows(session)
                self.assertEqual(rows[0][columns.index("TL hàng")], 25)

    def test_configured_weight_aliases_carry_units_without_changing_numeric_cells(self):
        cases = [
            ("CÂN", "CANKGS", 25000, "TONS", 25, "KGS"),
            ("MY MASS (KGS)", "MY MASS (KGS)", 25000, "TONS", 25, "KGS"),
            ("MYMASSKGS", "MYMASSKGS", 25000, "TONS", 25, "KGS"),
            ("MY CUSTOM WEIGHT", "MY CUSTOM WEIGHT", 25000, "KGS", 25, "KGS"),
            ("CÂN (T)", "CÂN (T)", 25, "KGS", 25, "TONS"),
        ]
        for index, (alias, header, value, default, expected, unit) in enumerate(cases):
            with self.subTest(alias=alias, header=header):
                path = self.workbook([self.container(gw=value)], weight=header, filename=f"alias_{index}.xlsx")
                result = parse_manifest(path, settings={"col_gw": alias, "default_weight_unit": default,
                                                        "number_format": "decimal_comma"})
                self.assertEqual(result["records"][0]["Weight_Value"], expected)
                self.assertEqual(result["metadata"]["default_weight_unit"], unit)

    def test_source_weight_units_follow_each_parsed_cell_and_remain_unknown_on_failure(self):
        path = self.workbook([
            self.container(gw="25 TONS"), self.container("MSCU7654321", gw="26000 KGS"),
            self.container("MSCU7654322", gw="not a weight"),
        ], weight="GWKGS")
        session = process_manifest(path, "VINAFCO")
        self.assertEqual([record["raw"]["weight_source_unit"] for record in session.records], ["TONS", "KGS", None])
        self.assertEqual([record["Weight_Value"] for record in session.records], [25, 26, None])
        self.assertEqual(session.metadata["source_weight_units"], ["KGS", "TONS"])
        self.assertEqual(session.records[0]["raw"]["gw"], "25 TONS")

    def test_same_schema_repeated_header_with_equivalent_unit_alias_is_allowed(self):
        path = self.workbook([self.container(gw=25000), self.headers("G.W. (KG)"),
                              self.container("MSCU7654321", gw=26000)], weight="GWKGS")
        session = process_manifest(path, "VINAFCO")
        self.assertEqual([r["Weight_Value"] for r in session.records], [25, 26])
        self.assertFalse([i for i in session.validate() if i["severity"] == "error"])
        _, rows = build_port_rows(session)
        self.assertEqual(len(rows), 2)

    def test_changed_weight_unit_in_repeated_header_blocks_export_and_preserves_evidence(self):
        path = self.workbook([self.container(), self.headers("GW (KGS)"),
                              self.container("MSCU7654321", gw=25000)])
        session = process_manifest(path, "VINAFCO")
        finding = next(i for i in session.validate() if i["code"] == "VINAFCO_HEADER_CHANGED")
        self.assertEqual(finding["severity"], "error")
        self.assertEqual(finding["source_row"], 5)
        self.assertEqual(finding["details"]["initial_weight_unit"], "TONS")
        self.assertEqual(finding["details"]["new_weight_unit"], "KGS")
        self.assertEqual([r["Weight_Value"] for r in session.records], [25])
        self.assertTrue(any("MSCU7654321" in f["text"] and f["status"] == "unresolved"
                            for f in session.metadata["source_fragments"]))
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_repeated_header_reordered_columns_blocks_export(self):
        changed = self.headers()
        left, right = self.fields.index("bill_no"), self.fields.index("seal")
        changed[left], changed[right] = changed[right], changed[left]
        next_row = self.container("MSCU7654321", bill_no="002222", seal="003333")
        next_row[left], next_row[right] = next_row[right], next_row[left]
        path = self.workbook([self.container(), changed, next_row])
        session = process_manifest(path, "VINAFCO")
        self.assertIn("VINAFCO_HEADER_CHANGED", {i["code"] for i in session.validate()})
        self.assertEqual(len(session.records), 1)
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_repeated_header_with_duplicate_weight_column_blocks_export(self):
        changed = self.headers()
        changed[self.fields.index("remarks")] = "GW (KGS)"
        session = process_manifest(self.workbook([self.container(), changed,
                                                  self.container("MSCU7654321")]), "VINAFCO")
        finding = next(i for i in session.validate() if i["code"] == "VINAFCO_HEADER_CHANGED")
        self.assertIn("gw", finding["details"]["duplicate_fields"])
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_row_missing_container_is_retained_and_can_be_repaired(self):
        path = self.workbook([self.container(), self.container("", seal="001235", gw=26)])
        session = process_manifest(path, "VINAFCO")
        self.assertEqual(len(session.records), 2)
        missing = session.records[1]
        self.assertEqual(missing["Container_No"], "")
        self.assertEqual(missing["source_row"], 5)
        self.assertEqual(missing["raw"]["seal"], "001235")
        self.assertIn("VINAFCO_CONTAINER_MISSING", {i["code"] for i in session.validate()})
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.update_record(missing["record_id"], {"Container_No": "MSCU7654321"}, "Đối chiếu mã trên manifest nguồn")
        columns, rows = build_port_rows(session)
        self.assertEqual([r[columns.index("Số Container")] for r in rows], ["MSCU1234567", "MSCU7654321"])

    def test_table_with_only_incomplete_container_still_surfaces_candidate(self):
        result = parse_manifest(self.workbook([self.container("", seal="001235", gw=26)]))
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("VINAFCO_CONTAINER_MISSING", {i["code"] for i in result["issues"]})
        self.assertNotIn("VINAFCO_HEADER_NOT_FOUND", {i["code"] for i in result["issues"]})

    def test_known_party_and_footer_rows_do_not_create_phantom_containers(self):
        path = self.workbook([
            self.container(), self.row(comm="TOTAL", gw=25), self.row(party_raw="TỔNG CỘNG", gw=25),
            self.row(container_no="GRAND TOTAL", gw=25), self.row(remarks="TỔNG SỐ:", gw=25),
        ], prefix=[self.row(party_raw="(S) SHIPPER", bill_no="BL-001", type="20DC"),
                   self.row(party_raw="(C) CONSIGNEE"), self.row(party_raw="Address line")])
        session = process_manifest(path, "VINAFCO")
        self.assertEqual(len(session.records), 1)
        self.assertFalse([i for i in session.validate() if i["severity"] == "error"])
        self.assertEqual(session.records[0]["Cleaned_Consignee_Name_For_Output"], "CONSIGNEE")

    def test_goods_text_containing_total_is_not_treated_as_a_footer(self):
        result = parse_manifest(self.workbook([self.container("", comm="TOTAL QUALITY STEEL")]))
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["Description"], "TOTAL QUALITY STEEL")
        self.assertIn("VINAFCO_CONTAINER_MISSING", {i["code"] for i in result["issues"]})

    def test_coverage_accounts_for_every_nonblank_row_in_the_selected_table(self):
        result = parse_manifest(self.workbook([self.container(), self.container("", seal="001235"),
                                               self.row(), self.row(comm="TOTAL", gw=50)]))
        coverage = result["metadata"]["coverage"]
        self.assertEqual(coverage["source_fragments"], 6)
        self.assertEqual(coverage["parsed_fragments"], 1)
        self.assertEqual(coverage["unresolved_fragments"], 1)
        self.assertEqual(coverage["corroborating_fragments"], 2)
        self.assertEqual(coverage["ignored_fragments"], 2)
        self.assertEqual(coverage["source_fragments"], sum(value for key, value in coverage.items() if key != "source_fragments"))

    def test_configured_alias_cannot_assign_weight_and_type_to_the_same_column(self):
        result = parse_manifest(self.workbook([self.container()]), settings={"col_gw": "TYPE"})
        self.assertEqual(result["records"], [])
        self.assertIn("VINAFCO_AMBIGUOUS_COLUMNS", {i["code"] for i in result["issues"]})

    def summary(self, entries, *, offset=1):
        return [[""] * offset + list(entry) for entry in [
            ("LOẠI CONT", "SỐ LƯỢNG", "GHI CHÚ"), *entries,
        ]]

    def test_moved_summary_preserves_missing_id_and_records_source_coordinates(self):
        path = self.workbook([
            self.container(), self.container("", seal="001235", gw=26),
            *self.summary([("20DC", 2), ("TOTAL:", 2), ("TEUS:", 2)], offset=9),
        ])
        session = process_manifest(path, "VINAFCO")
        self.assertEqual([record["source_row"] for record in session.records], [4, 5])
        self.assertEqual(session.records[1]["raw"]["seal"], "001235")
        self.assertEqual(session.records[1]["Container_No"], "")
        reconciliation = session.metadata["reconciliation"]
        self.assertEqual(reconciliation["unresolved_container_rows"], [5])
        block, = reconciliation["summary_blocks"]
        self.assertEqual((block["source_sheet"], block["header_row"], block["end_row"]), ("MANIFEST", 6, 9))
        self.assertEqual(block["columns"], {"size": 10, "quantity": 11, "remarks": 12})
        self.assertEqual(block["entries"][0]["source_row"], 7)
        self.assertEqual(block["entries"][0]["source_column"], 11)
        fragments = session.metadata["source_fragments"]
        self.assertEqual([f["source_row"] for f in fragments if f["reason"].startswith("container_summary_")],
                         [6, 7, 8, 9])
        findings = {finding["code"]: finding for finding in session.validate()}
        self.assertEqual(findings["VINAFCO_CONTAINER_MISSING"]["source_row"], 5)
        self.assertEqual(reconciliation["status"], "unavailable")
        self.assertIsNone(reconciliation["total_difference"])
        self.assertEqual(reconciliation["size_differences"], {})

    def test_matching_valid_count_cannot_reconcile_with_an_unresolved_id(self):
        path = self.workbook([
            self.container(), self.container("", seal="001235"),
            *self.summary([("20DC", 1), ("TOTAL", 1)]),
        ])
        result = parse_manifest(path)
        reconciliation = result["metadata"]["reconciliation"]
        self.assertEqual(reconciliation["status"], "unavailable")
        self.assertIn("mã container", reconciliation["reason"])
        self.assertEqual((reconciliation["source_total"], reconciliation["parsed_total"]), (1, 1))
        self.assertEqual(reconciliation["unresolved_container_rows"], [5])
        self.assertIsNone(reconciliation["total_difference"])
        self.assertEqual(reconciliation["size_differences"], {})

    def test_sidecar_summary_header_cannot_hide_detail_on_the_same_row(self):
        for number in ("MSCU7654321", ""):
            with self.subTest(number=number):
                sidecar = self.summary([("20DC", 1), ("TOTAL", 1)], offset=len(self.fields))
                detail_with_header = self.container(number, seal="001235") + sidecar[0][len(self.fields):]
                result = parse_manifest(self.workbook([self.container(), detail_with_header, *sidecar[1:]]))
                self.assertEqual([r["source_row"] for r in result["records"]], [4, 5])
                self.assertEqual(result["records"][1]["Container_No"], number)
                self.assertEqual(result["records"][1]["raw"]["seal"], "001235")
                reconciliation = result["metadata"]["reconciliation"]
                self.assertEqual(reconciliation["summary_blocks"], [])
                self.assertEqual(reconciliation["status"], "unavailable")
                self.assertIsNone(reconciliation["total_difference"])

    def test_total_mismatch_warns_at_the_labeled_total(self):
        path = self.workbook([self.container(), *self.summary([("20DC", 2), ("TOTAL:", 2)])])
        session = process_manifest(path, "VINAFCO")
        reconciliation = session.metadata["reconciliation"]
        self.assertEqual(reconciliation["status"], "mismatch")
        self.assertEqual(reconciliation["total_difference"], -1)
        self.assertEqual(reconciliation["size_differences"], {"20DC": -1})
        warning = next(i for i in session.validate() if i["code"] == "VINAFCO_SUMMARY_MISMATCH")
        self.assertEqual((warning["severity"], warning["source_sheet"], warning["source_row"]),
                         ("warning", "MANIFEST", 7))
        self.assertIsNone(warning["record_id"])

    def test_reconciliation_counts_unique_containers_and_container_bill_pairs(self):
        path = self.workbook([
            self.container(number="mscu-1234567"), self.container(),
            self.row(party_raw="(S) OTHER", bill_no="BL-002"), self.row(party_raw="(C) OTHER"),
            self.container(), self.container(number="MSCU7654321", type="40RF"),
            *self.summary([("20DC", 1), ("40RF", 1), ("TOTAL", 2)]),
        ])
        result = parse_manifest(path)
        reconciliation = result["metadata"]["reconciliation"]
        self.assertEqual(len(result["records"]), 4)
        self.assertEqual(reconciliation["parsed_total"], 2)
        self.assertEqual(reconciliation["parsed_container_bl_pairs"], 3)
        self.assertEqual(reconciliation["source_size_counts"], {"20DC": 1, "40RF": 1})
        self.assertEqual(reconciliation["parsed_size_counts"], {"20DC": 1, "40RF": 1})
        self.assertEqual(reconciliation["status"], "matched")
        self.assertEqual(reconciliation["total_difference"], 0)

    def test_size_mismatch_warns_at_the_source_row_and_does_not_block_export(self):
        path = self.workbook([self.container(), *self.summary([("20DC", 0), ("40HC", 1), ("TOTAL", 1)])])
        session = process_manifest(path, "VINAFCO")
        reconciliation = session.metadata["reconciliation"]
        self.assertEqual(reconciliation["status"], "mismatch")
        self.assertEqual(reconciliation["total_difference"], 0)
        self.assertEqual(reconciliation["size_differences"], {"20DC": 1, "40HC": -1})
        warning = next(i for i in session.validate() if i["code"] == "VINAFCO_SUMMARY_MISMATCH")
        self.assertEqual((warning["severity"], warning["source_row"]), ("warning", 6))
        self.assertEqual(len(build_port_rows(session)[1]), 1)

    def test_unlabeled_trailer_is_evidence_without_an_inferred_total(self):
        path = self.workbook([
            self.container(), *self.summary([("20DC", 1), ("", 1), ("", 1), ("", 25.3)]),
        ])
        result = parse_manifest(path)
        self.assertEqual(len(result["records"]), 1)
        reconciliation = result["metadata"]["reconciliation"]
        self.assertEqual(reconciliation["status"], "unavailable")
        self.assertIsNone(reconciliation["source_total"])
        self.assertIsNone(reconciliation["total_difference"])
        self.assertEqual(reconciliation["source_size_counts"], {"20DC": 1})
        block, = reconciliation["summary_blocks"]
        self.assertEqual(block["end_row"], 9)
        self.assertEqual([entry["kind"] for entry in block["entries"]],
                         ["size", "unlabeled_metric", "unlabeled_metric", "unlabeled_metric"])

    def test_detail_continues_after_summary_without_reconciling_cross_scope(self):
        for second_summary in (False, True):
            with self.subTest(second_summary=second_summary):
                summary = self.summary([("20DC", 1), ("TOTAL", 1)])
                path = self.workbook([
                    self.container(), *summary, self.headers(),
                    self.row(party_raw="(S) NEXT", bill_no="BL-002"),
                    self.row(party_raw="(C) NEXT"), self.container("MSCU7654321"),
                    *(summary if second_summary else []),
                ])
                result = parse_manifest(path)
                self.assertEqual([r["source_row"] for r in result["records"]], [4, 11])
                self.assertEqual([r["BL_No"] for r in result["records"]], ["BL-001", "BL-002"])
                reconciliation = result["metadata"]["reconciliation"]
                self.assertEqual(reconciliation["status"], "unavailable")
                self.assertIsNone(reconciliation["total_difference"])
                self.assertEqual(reconciliation["size_differences"], {})
                self.assertEqual(len(reconciliation["summary_blocks"]), 2 if second_summary else 1)
                self.assertNotIn("VINAFCO_SUMMARY_MISMATCH", {i["code"] for i in result["issues"]})

    def test_multiple_sheet_candidates_expose_preview_rows_and_skip_summary_only_sheet(self):
        from openpyxl import load_workbook

        path = self.workbook([self.container()])
        book = load_workbook(path)
        other = book.create_sheet("Other")
        other.append(["Title"])
        other.append(self.headers())
        for _ in range(4):
            other.append(self.container("MSCU7654321", comm="X" * 250))
        summary_only = book.create_sheet("Summary Only")
        summary_only.append(self.headers())
        for row in self.summary([("20DC", 1), ("TOTAL", 1)]):
            summary_only.append(row)
        book.save(path)
        book.close()
        result = parse_manifest(path)
        self.assertEqual(result["records"], [])
        self.assertEqual(result["metadata"]["candidate_sheets"], ["MANIFEST", "Other"])
        candidates = result["metadata"]["table_candidates"]
        self.assertEqual([(c["source_sheet"], c["header_row"]) for c in candidates], [("MANIFEST", 1), ("Other", 2)])
        preview = candidates[1]["preview_rows"]
        self.assertEqual([r["source_row"] for r in preview], [3, 4, 5])
        self.assertIn("MSCU7654321", preview[0]["text"])
        self.assertTrue(all(len(r["text"]) <= 180 for r in preview))
        chosen = process_manifest(path, "VINAFCO", settings={"selected_sheet": "Other"})
        self.assertEqual(chosen.metadata["source_sheet"], "Other")
        self.assertEqual(len(chosen.records), 4)


if __name__ == "__main__":
    unittest.main()
