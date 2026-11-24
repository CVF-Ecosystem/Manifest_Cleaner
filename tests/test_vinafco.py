"""VINAFCO regressions using generated XLSX workbooks, not private shipping data."""

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from manifest_cleaner.carriers.vinafco.adapter import is_supported_size_type, parse_manifest, refresh_derived_fields
from manifest_cleaner.carriers.vinafco.profile import INPUT_COLUMNS


class VinafcoAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.fields = list(INPUT_COLUMNS)

    def row(self, **values):
        return [values.get(field, "") for field in self.fields]

    def manifest_rows(self, **container):
        return [
            self.row(party_raw="(S) SHIPPER", bill_no="BL-001"),
            self.row(party_raw="(C) CÔNG TY ABC Tel: 0901234567"),
            self.row(**{"container_no": "MSCU1234567", "seal": "001234", "type": "20DC",
                        "comm": "GẠCH MEN", "gw": 25, **container}),
        ]

    def workbook(self, rows, *, name="anything.xlsx", headers=None, pad=0, leading=0, extra=None):
        book = Workbook()
        sheet = book.active
        sheet.title = "MANIFEST"
        for _ in range(leading):
            sheet.append(["Cover text"])
        sheet.append([""] * pad + (headers or list(INPUT_COLUMNS.values())))
        for row in rows:
            sheet.append([""] * pad + row)
        if extra:
            other = book.create_sheet(extra)
            other.append(list(INPUT_COLUMNS.values()))
            for row in rows:
                other.append(row)
        path = self.folder / name
        book.save(path)
        book.close()
        return path

    def codes(self, result):
        return {item["code"] for item in result["issues"]}

    def test_weight_formats_and_bill_on_shipper_row(self):
        rows = [self.row(party_raw="(S) SHIPPER", bill_no="000123"),
                self.row(party_raw="(C) CONSIGNEE")]
        for i, weight in enumerate(["25,000 KGS", "25.000,50 KGS", "25,000.50 KGS"]):
            rows.append(self.row(container_no=f"ABCU123456{i}", type="20DC", comm="CARGO", gw=weight))
        result = parse_manifest(self.workbook(rows))
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual([r["BL_No"] for r in result["records"]], ["000123"] * 3)
        self.assertEqual([r["Weight_Value"] for r in result["records"]], [25.0, 25.0005, 25.0005])
        self.assertTrue(all(r["Weight_Unit"] == "TONS" for r in result["records"]))

    def test_missing_consignee_does_not_drop_container_or_fill_from_previous_group(self):
        rows = self.manifest_rows()
        rows += [self.row(party_raw="(S) SECOND SHIPPER", bill_no="BL-002"),
                 self.row(container_no="ABCU7654321", type="20DC", comm="CARGO", gw=10)]
        result = parse_manifest(self.workbook(rows))
        self.assertEqual(len(result["records"]), 2)
        second = result["records"][1]
        self.assertEqual(second["Cleaned_Consignee_Name_For_Output"], "")
        self.assertEqual(second["BL_No"], "BL-002")
        self.assertIn("VINAFCO_CONSIGNEE_MISSING", self.codes(result))
        self.assertLess(second["Confidence"], 100)

    def test_relocated_multiline_header_and_source_evidence(self):
        headers = list(INPUT_COLUMNS.values())
        headers[0] = headers[0].replace(",", ",\n ")
        result = parse_manifest(self.workbook(self.manifest_rows(), headers=headers, pad=2, leading=4))
        record = result["records"][0]
        self.assertEqual(record["source_row"], 8)
        self.assertEqual(record["source_sheet"], "MANIFEST")
        self.assertEqual(record["raw"]["comm"], "GẠCH MEN")
        self.assertEqual(record["Description"], "GACH MEN")
        self.assertEqual(record["Cleaned_Consignee_Name_For_Output"], "CÔNG TY ABC")
        self.assertEqual(result["metadata"]["header_row"], 5)

    def test_configuration_reaches_weight_tare_operators_and_mapping(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("remarks")] = "S.O.C"
        path = self.workbook(rows)
        base = parse_manifest(path)["records"][0]
        self.assertEqual((base["Weight_Value"], base["FE_Status"], base["Operator"]), (25, "F", "SVF"))
        adjusted = parse_manifest(path, settings={
            "tare_20ft": 99, "operator_soc": "CUSTOM_SOC",
            "size_to_iso": {"20DC": "PORT20"}, "cargo_type_mapping": {"20DC": "TANK"},
        })["records"][0]
        self.assertEqual((adjusted["FE_Status"], adjusted["Operator"], adjusted["VTOS_Size"], adjusted["Cargo_Type"]),
                         ("E", "CUSTOM_SOC", "PORT20", "EMPTY TANK"))
        in_kg = parse_manifest(path, settings={"default_weight_unit_if_missing": "KGS"})["records"][0]
        self.assertEqual(in_kg["Weight_Value"], 0.025)
        self.assertEqual(in_kg["FE_Status"], "E")

    def test_weight_header_unit_takes_precedence_and_numeric_cell_is_not_reparsed(self):
        headers = list(INPUT_COLUMNS.values())
        headers[self.fields.index("gw")] = "GW (KGS)"
        result = parse_manifest(self.workbook(self.manifest_rows(), headers=headers),
                                settings={"number_format": "decimal_comma", "default_weight_unit": "TONS"})
        self.assertEqual(result["records"][0]["Weight_Value"], 0.025)
        self.assertEqual(result["metadata"]["default_weight_unit"], "KGS")

    def test_accented_empty_and_goods_containing_empty_are_distinct(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("comm")] = "RỖNG"
        rows[-1][self.fields.index("gw")] = ""
        result = parse_manifest(self.workbook(rows, name="empty.xlsx"))
        self.assertEqual(result["records"][0]["FE_Status"], "E")
        self.assertEqual(result["records"][0]["Description"], "RONG")
        self.assertEqual(result["records"][0]["raw"]["comm"], "RỖNG")
        self.assertIn("VINAFCO_WEIGHT_INVALID", self.codes(result))
        rows[-1][self.fields.index("comm")] = "EMPTY BOTTLES"
        rows[-1][self.fields.index("gw")] = 25
        bottles = parse_manifest(self.workbook(rows, name="bottles.xlsx"))["records"][0]
        self.assertEqual(bottles["FE_Status"], "F")
        self.assertEqual(bottles["Description"], "EMPTY BOTTLES")

    def test_conflicting_status_is_an_error_and_description_is_preserved(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("comm")] = "EMPTY CONTAINER"
        result = parse_manifest(self.workbook(rows))
        record = result["records"][0]
        self.assertEqual(record["FE_Status"], "E")
        self.assertEqual(record["Description"], "EMPTY CONTAINER")
        self.assertTrue(any(x["code"] == "VINAFCO_FE_CONFLICT" and x["severity"] == "error" for x in result["issues"]))
        conflict = next(x for x in result["issues"] if x["code"] == "VINAFCO_FE_CONFLICT")
        self.assertEqual(conflict["resolution_fields"], ["FE_Status", "Weight_Value"])
        self.assertLess(record["Confidence"], 100)

    def test_reefer_mapping_and_manual_refresh_do_not_reinfer_status(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("type")] = "22R1"
        result = parse_manifest(self.workbook(rows))
        record = result["records"][0]
        self.assertEqual((record["VTOS_Size"], record["Cargo_Type"]), ("22R0", "REEFER"))
        record.update({"Size_Type": "20RF", "FE_Status": "E", "Description": "FROZEN FISH", "Operator": "USER_OP"})
        refreshed = refresh_derived_fields(record)
        self.assertEqual((refreshed["VTOS_Size"], refreshed["Cargo_Type"]), ("22R0", "EMPTY REEFER"))
        self.assertEqual(refreshed["FE_Status"], "E")
        self.assertEqual(refreshed["Description"], "FROZEN FISH")
        self.assertEqual(refreshed["Operator"], "USER_OP")

    def test_invalid_and_duplicate_identifiers_are_retained_for_shared_validation(self):
        rows = self.manifest_rows()
        rows += [list(rows[-1])]
        bad = list(rows[-1])
        bad[self.fields.index("container_no")] = "MSCU1234567 trailing text"
        rows.append(bad)
        result = parse_manifest(self.workbook(rows))
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(result["records"][0]["Container_No"], result["records"][1]["Container_No"])
        self.assertEqual(result["records"][2]["Container_No"], "MSCU1234567 trailing text")
        self.assertIn("VINAFCO_CONTAINER_UNPARSED", self.codes(result))

    def test_multiple_sheets_require_explicit_selection(self):
        path = self.workbook(self.manifest_rows(), extra="Second Manifest")
        result = parse_manifest(path)
        self.assertEqual(result["records"], [])
        self.assertIn("VINAFCO_MULTIPLE_TABLES", self.codes(result))
        selected = parse_manifest(path, settings={"target_sheet_name": "Second Manifest"})
        self.assertEqual(len(selected["records"]), 1)
        self.assertEqual(selected["records"][0]["source_sheet"], "Second Manifest")

    def test_xlsx_content_with_xls_extension_and_zero_padded_identifiers(self):
        path = self.workbook(self.manifest_rows())
        from openpyxl import load_workbook
        book = load_workbook(path)
        sheet = book.active
        sheet.cell(2, self.fields.index("bill_no") + 1, 123).number_format = "000000"
        sheet.cell(4, self.fields.index("seal") + 1, 1234).number_format = "000000"
        book.save(path)
        book.close()
        renamed = path.with_suffix(".xls")
        path.rename(renamed)
        record = parse_manifest(renamed)["records"][0]
        self.assertEqual(record["BL_No"], "000123")
        self.assertEqual(record["Seal_No"], "001234")

    def test_bill_after_container_only_backfills_unambiguous_group(self):
        rows = [self.row(party_raw="(S) SHIPPER"), self.row(party_raw="(C) CONSIGNEE"),
                self.row(container_no="ABCU1234567", type="20DC", comm="CARGO", gw=25),
                self.row(bill_no="BL-LATE")]
        result = parse_manifest(self.workbook(rows, name="late.xlsx"))
        self.assertEqual(result["records"][0]["BL_No"], "BL-LATE")
        rows.append(self.row(bill_no="BL-OTHER"))
        ambiguous = parse_manifest(self.workbook(rows, name="ambiguous.xlsx"))
        self.assertEqual(ambiguous["records"][0]["BL_No"], "")
        self.assertIn("VINAFCO_BL_MISSING", self.codes(ambiguous))

    def test_safety_margin_legacy_alias_and_size_column_configuration(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("gw")] = 2.5
        headers = list(INPUT_COLUMNS.values())
        headers[self.fields.index("type")] = "MY CUSTOM SIZE"
        path = self.workbook(rows, headers=headers)
        result = parse_manifest(path, settings={"col_type": "MY CUSTOM SIZE", "tare_20ft_empty_vgm": 3.0})
        self.assertEqual(result["records"][0]["FE_Status"], "E")
        self.assertEqual(result["records"][0]["VTOS_Size"], "20DC")

    def test_invalid_weight_never_becomes_zero(self):
        rows = self.manifest_rows()
        rows[-1][self.fields.index("gw")] = "unreadable"
        result = parse_manifest(self.workbook(rows))
        self.assertIsNone(result["records"][0]["Weight_Value"])
        self.assertIn("VINAFCO_WEIGHT_INVALID", self.codes(result))

    def test_blank_template_sheet_does_not_make_manifest_ambiguous(self):
        path = self.workbook(self.manifest_rows())
        from openpyxl import load_workbook
        book = load_workbook(path)
        book.create_sheet("Blank Template").append(list(INPUT_COLUMNS.values()))
        book.save(path)
        book.close()
        result = parse_manifest(path)
        self.assertEqual(len(result["records"]), 1)
        self.assertNotIn("VINAFCO_MULTIPLE_TABLES", self.codes(result))

    def test_supported_sizes_include_aliases_and_configured_mapping_only(self):
        self.assertTrue(is_supported_size_type("20'DC"))
        self.assertTrue(is_supported_size_type("22R0"))
        self.assertFalse(is_supported_size_type("BANANA"))
        self.assertFalse(is_supported_size_type(""))
        self.assertTrue(is_supported_size_type("CUSTOM20", {"size_to_vtos": {"CUSTOM20": "20DC"}}))
        self.assertFalse(is_supported_size_type("CUSTOM20", {"size_to_vtos": {"CUSTOM20": "UNMAPPED"}}))


if __name__ == "__main__":
    unittest.main()
