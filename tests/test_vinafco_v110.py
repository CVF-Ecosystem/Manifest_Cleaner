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


if __name__ == "__main__":
    unittest.main()
