"""Regression evidence for the VOSCO adapter; no GUI or network required."""
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from manifest_cleaner.carriers.vosco.adapter import is_supported_size_type, parse_manifest, refresh_derived_fields
from manifest_cleaner.carriers.vosco.parsers import parse_container_line, parse_weight_line
from manifest_cleaner.carriers.vosco.processors import determine_fe, match_descriptions_with_confidence
from manifest_cleaner.engine import process_manifest


def source_row(bl="VOSCO123456", containers="ABCU1234567/001234 40HC-C",
               weight="25 TONS", description="GẠO", consignee="ABC COMPANY", marker="(C)"):
    row = [""] * 19
    row[0], row[1], row[5], row[10], row[14], row[18] = marker, consignee, bl, containers, description, weight
    return row


class VoscoAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def workbook(self, rows, header_rows=16, suffix=".xlsx"):
        path = Path(self.temp.name) / ("manifest" + suffix)
        book = Workbook()
        sheet = book.active
        sheet.title = "Manifest"
        for index in range(header_rows):
            header = [""] * 19
            header[0] = f"HEADER {index + 1}"
            # Realistic title/header text must never become a failed container.
            header[10] = "Container and seal number" if index == header_rows - 1 else ""
            sheet.append(header)
        for row in rows:
            sheet.append(row)
        book.save(path)
        book.close()
        return path

    def test_operational_columns_and_port_mappings_preserved(self):
        result = parse_manifest(self.workbook([source_row(containers="ABCU1234567/001234 40GP-S")]))
        record = result["records"][0]
        self.assertEqual(record["BL_No"], "VOSCO123456")
        self.assertEqual(record["Container_No"], "ABCU1234567")
        self.assertEqual(record["Seal_No"], "001234")
        self.assertEqual(record["Size_Type"], "40GP")
        self.assertEqual(record["VTOS_Size"], "40HC")
        self.assertEqual(record["Operator"], "SVC")
        self.assertEqual(record["Cargo_Type"], "GENERAL")
        self.assertEqual(record["source_row"], 17)
        self.assertFalse([item for item in result["issues"] if item["severity"] == "error"])

    def test_kg_and_tonne_representations_have_identical_output(self):
        for raw in ["25,500 KGS", "25 500 KGS", "25.5 TONS", "25,5 TONS"]:
            with self.subTest(raw=raw):
                record = parse_manifest(self.workbook([source_row(weight=raw)]))["records"][0]
                self.assertEqual(record["Weight_Value"], 25.5)
                self.assertEqual(record["Weight_Unit"], "TONS")
                self.assertEqual(record["FE_Status"], "F")
                self.assertEqual(record["raw"]["weight_cell"], raw)
        self.assertEqual(parse_weight_line("25,500.5 KGS")["value"], 25.5005)

    def test_invalid_weight_retains_position(self):
        containers = "ABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C\nABCU1234569/001236 40HC-C"
        result = parse_manifest(self.workbook([source_row(containers=containers, weight="10 TONS\nBAD WEIGHT\n30 TONS")]))
        self.assertEqual([r["Weight_Value"] for r in result["records"]], [10.0, None, 30.0])
        failures = [i for i in result["issues"] if i["code"] == "WEIGHT_INVALID"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["record_id"], result["records"][1]["record_id"])

    def test_single_weight_is_not_reused_for_two_containers(self):
        containers = "ABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C"
        result = parse_manifest(self.workbook([source_row(containers=containers, weight="25000 KGS")]))
        self.assertEqual([r["Weight_Value"] for r in result["records"]], [None, None])
        self.assertEqual(len([i for i in result["issues"] if i["code"] == "WEIGHT_ASSOCIATION_AMBIGUOUS"]), 2)

    def test_blank_and_port_named_consignees_do_not_remove_containers(self):
        result = parse_manifest(self.workbook([
            source_row(consignee=""),
            source_row(bl="VOSCO123457", containers="ABCU1234568/001235 40HC-C", consignee="ABC PORT, VIETNAM"),
        ]))
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][1]["Cleaned_Consignee_Name_For_Output"], "ABC PORT, VIETNAM")
        self.assertIn("CONSIGNEE_MISSING", {i["code"] for i in result["issues"]})

    def test_new_invalid_bl_does_not_inherit_previous_bl(self):
        result = parse_manifest(self.workbook([
            source_row(),
            source_row(bl="VOSCO/000222", containers="ABCU1234568/001235 40HC-C"),
            source_row(bl="", marker="", containers="ABCU1234569/001236 40HC-C"),
        ]))
        self.assertEqual([r["BL_No"] for r in result["records"]], ["VOSCO123456", "", ""])
        self.assertEqual(result["records"][1]["raw"]["BL_No"], "VOSCO/000222")
        self.assertEqual(len([i for i in result["issues"] if i["code"] == "INVALID_OR_MISSING_BL"]), 2)

    def test_header_row_shift_preserves_source_coordinates(self):
        for header_count in (0, 5, 20):
            with self.subTest(headers=header_count):
                result = parse_manifest(self.workbook([source_row()], header_rows=header_count))
                self.assertEqual(len(result["records"]), 1)
                self.assertEqual(result["records"][0]["source_row"], header_count + 1)

    def test_missing_description_alignment_never_claims_100(self):
        raw = "ABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C\nABCU1234569/001236 40HC-C"
        parsed = [parse_container_line(line) for line in raw.splitlines()]
        results = match_descriptions_with_confidence(parsed, raw, "RICE\nSTEEL", ["F"] * 3)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(match.confidence < 100 and match.warning for match in results))

    def test_tank_empty_uses_correct_tare_and_unit(self):
        for weight in ("5.5 TONS", "5500 KGS"):
            result = parse_manifest(self.workbook([source_row(
                containers="ABCU1234567/001234 20TK-C", weight=weight, description="EMPTY"
            )]))
            self.assertEqual(result["records"][0]["FE_Status"], "E")
            self.assertEqual(result["records"][0]["Cargo_Type"], "EMPTY TANK")
        self.assertEqual(determine_fe("", {"value": 5.5, "unit": "TONS"}, "20TK"), "E")

    def test_explicit_empty_conflict_is_visible(self):
        result = parse_manifest(self.workbook([source_row(description="EMPTY", weight="25 TONS")]))
        self.assertEqual(result["records"][0]["FE_Status"], "E")
        self.assertIn("EMPTY_WEIGHT_CONFLICT", {i["code"] for i in result["issues"]})
        self.assertEqual(determine_fe("EMPTY BOTTLES", {"value": 25, "unit": "TONS"}, "40HC"), "F")

    def test_quantity_matching_and_raw_description_are_preserved(self):
        containers = "ABCU1234567/001234 20DC-C\nABCU1234568/001235 20DC-C"
        description = "GẠCH MEN (01) x20'DC COC, PHÂN BÓN (01) x20'DC COC"
        result = parse_manifest(self.workbook([source_row(containers=containers, weight="10 TONS\n20 TONS", description=description)]))
        self.assertEqual([r["Description"] for r in result["records"]], ["GACH MEN", "PHAN BON"])
        self.assertTrue(all(r["raw"]["description_cell"] == description for r in result["records"]))

    def test_malformed_container_is_reported_and_both_candidates_survive(self):
        result = parse_manifest(self.workbook([source_row(containers="ABCU1234567/001234 40HC-C\nABCU12345/005555 40HC-C")]))
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][1]["Container_No"], "ABCU12345")
        self.assertEqual(result["records"][1]["Size_Type"], "")
        self.assertEqual(result["records"][1]["FE_Status"], "")
        self.assertEqual(result["records"][1]["raw"]["container_line"], "ABCU12345/005555 40HC-C")
        self.assertIn("CONTAINER_UNPARSED", {i["code"] for i in result["issues"]})
        bad_issue = next(i for i in result["issues"] if i["code"] == "CONTAINER_UNPARSED")
        self.assertEqual(bad_issue["record_id"], result["records"][1]["record_id"])

    def test_bad_container_candidate_can_be_corrected_or_excluded(self):
        path = self.workbook([source_row(containers="ABCU1234567/001234 40HC-C\nABCU12345/005555 40HC-C", weight="10 TONS\n20 TONS")])
        session = process_manifest(path, "VOSCO")
        bad = session.records[1]
        self.assertTrue([i for i in session.validate() if i["severity"] == "error"])
        session.update_record(bad["record_id"], {
            "Container_No": "ABCU1234568", "Seal_No": "005555", "Size_Type": "40HC", "FE_Status": "F"
        }, "Đã đối chiếu số container và kích cỡ từ manifest gốc")
        self.assertFalse([i for i in session.validate() if i["severity"] == "error"])
        self.assertEqual(session.records[1]["Weight_Value"], 20.0)
        self.assertEqual(session.records[1]["raw"]["container_line"], "ABCU12345/005555 40HC-C")
        another = process_manifest(path, "VOSCO")
        another.set_excluded(another.records[1]["record_id"], True, "Dòng thừa đã kiểm tra")
        self.assertFalse([i for i in another.validate() if i["severity"] == "error"])

        # A malformed first candidate must survive even without a valid BL or
        # party marker that could otherwise establish the start of the block.
        no_marker = parse_manifest(self.workbook([source_row(
            bl="VOS/12", marker="", containers="ABCU12345/005555 40HC-C"
        )]))
        self.assertEqual(len(no_marker["records"]), 1)
        self.assertEqual(no_marker["records"][0]["BL_No"], "")

    def test_weight_kind_inference_has_visible_warning(self):
        result = parse_manifest(self.workbook([source_row(weight="25 TONS")]))
        warning = next(i for i in result["issues"] if i["code"] == "FE_WEIGHT_KIND_UNCONFIRMED")
        self.assertEqual(warning["record_id"], result["records"][0]["record_id"])
        self.assertEqual(warning["field"], "FE_Status")

    def test_native_numeric_excel_weight_ignores_text_locale_setting(self):
        for number_format in ("legacy", "decimal_comma", "decimal_dot"):
            with self.subTest(number_format=number_format):
                result = parse_manifest(self.workbook([source_row(weight=1.234)]),
                                        settings={"number_format": number_format})
                self.assertEqual(result["records"][0]["Weight_Value"], 1.234)
                self.assertEqual(result["records"][0]["raw"]["weight_cell_value"], 1.234)

    def test_unknown_size_has_no_port_mapping_and_blocks_validation(self):
        self.assertTrue(is_supported_size_type("40GP"))
        self.assertFalse(is_supported_size_type("BANANA"))
        session = process_manifest(self.workbook([source_row()]), "VOSCO")
        session.update_record(session.records[0]["record_id"], {"Size_Type": "BANANA"}, "Kiểm tra dữ liệu chưa được map")
        self.assertIsNone(session.records[0]["VTOS_Size"])
        self.assertTrue([i for i in session.validate() if i["severity"] == "error"])

    def test_numeric_seal_is_not_misidentified_as_size(self):
        result = parse_manifest(self.workbook([source_row(containers="ABCU1234567/001234")]))
        self.assertEqual(result["records"][0]["Seal_No"], "001234")
        self.assertEqual(result["records"][0]["Size_Type"], "")
        self.assertIn("SIZE_TYPE_MISSING", {i["code"] for i in result["issues"]})

    def test_manual_derivation_preserves_user_fields(self):
        original = {"Size_Type": "20RF", "FE_Status": "E", "Operator": "USER", "Description": "MANUAL CARGO"}
        derived = refresh_derived_fields(original)
        self.assertEqual(derived["VTOS_Size"], "22R0")
        self.assertEqual(derived["Cargo_Type"], "EMPTY REEFER")
        self.assertEqual(derived["Operator"], "USER")
        self.assertEqual(derived["Description"], "MANUAL CARGO")
        self.assertNotIn("VTOS_Size", original)

    def test_xlsx_with_legacy_xls_extension_is_read(self):
        result = parse_manifest(self.workbook([source_row()], suffix=".xls"))
        self.assertEqual(len(result["records"]), 1)


if __name__ == "__main__":
    unittest.main()
