"""Independent contracts across parser, review session, export and CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from openpyxl import load_workbook
from manifest_cleaner.engine import process_manifest
from manifest_cleaner.exporter import build_port_rows, export_port_excel
from scripts.create_samples import CREATORS, create_vimc


# Fixed expected schemas transcribed from the actual legacy export definitions.
EXPECTED_COMMON = ["STT", "Số lượng", "Số BL", "Số Container", "Hãng khai thác", "Kích cỡ",
                   "Kích cỡ VTOS", "F/E", "TL hàng", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
                   "Hàng hóa", "Loại hàng", "Độ chính xác (%)", "Ghi chú"]
EXPECTED_VIMC = ["STT", "Số Vận Đơn", "Số Container", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
                 "Kích cỡ", "Loại Container", "Hãng khai thác", "Loại hàng", "F/E", "Trọng lượng (Tấn)",
                 "Hàng hóa", "Số lượng", "Độ chính xác (%)", "Ghi chú"]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def session(self, carrier="VIMC", **kwargs):
        path = CREATORS[carrier](self.folder / f"{carrier}_input.xlsx", **kwargs)
        return process_manifest(path, carrier)

    @staticmethod
    def errors(session):
        return [item for item in session.validate() if item["severity"] == "error"]

    def read_output(self, session, filename="output.xlsx"):
        path = export_port_excel(session, self.folder / filename)
        book = load_workbook(path, data_only=False)
        self.addCleanup(book.close)
        sheet = book["Processed_Manifest"]
        headers = [cell.value for cell in sheet[1]]
        return sheet, headers, {label: sheet.cell(2, index + 1) for index, label in enumerate(headers)}

    def test_each_carrier_preserves_exact_sixteen_column_export_and_types(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = self.session(carrier)
                self.assertEqual(self.errors(session), [])
                sheet, headers, values = self.read_output(session, f"{carrier}_out.xlsx")
                self.assertEqual(headers, EXPECTED_VIMC if carrier == "VIMC" else EXPECTED_COMMON)
                self.assertEqual(sheet.max_column, 16)
                self.assertEqual(sheet.max_row, 2)
                for label in ("STT", "Số lượng", "Độ chính xác (%)"):
                    self.assertEqual(values[label].data_type, "n")
                weight_label = "Trọng lượng (Tấn)" if carrier == "VIMC" else "TL hàng"
                self.assertEqual(values[weight_label].data_type, "n")
                self.assertEqual(values["Số Container"].data_type, "s")
                self.assertEqual(values["Số niêm chì"].data_type, "s")
                self.assertTrue(values["Số niêm chì"].value.startswith("00"))
                self.assertEqual(values["Số niêm chì"].value, values["Số niêm chì 1"].value)
                self.assertEqual(values["Số lượng"].value, 1)

    def test_rounding_matches_legacy_pandas_only_at_export(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = self.session(carrier)
                original = session.records[0]["Weight_Value"]
                self.assertEqual(original, 16.055)
                _, _, values = self.read_output(session, f"{carrier}_rounding.xlsx")
                label = "Trọng lượng (Tấn)" if carrier == "VIMC" else "TL hàng"
                # Legacy pandas float64 .round(2) gives 16.06, unlike Python's
                # scalar round(16.055, 2), which gives 16.05.
                self.assertEqual(values[label].value, 16.055 if carrier == "VOSCO" else 16.06)
                self.assertEqual(session.records[0]["Weight_Value"], original)

    def test_vimc_uses_vtos_for_both_legacy_size_columns(self):
        session = self.session()
        row = session.records[0]
        session.update_record(row["record_id"], {"Size_Type": "40GP"}, "Đối chiếu kích cỡ ở nguồn demo")
        self.assertEqual(row["Size_Type"], "40GP")
        self.assertEqual(row["Physical_ISO_Size"], "42G1")
        _, _, values = self.read_output(session)
        self.assertEqual(values["Kích cỡ"].value, "40HC")
        self.assertEqual(values["Loại Container"].value, "40HC")

    def test_missing_required_data_blocks_export_then_edit_clears_resolved_issue(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = self.session(carrier, consignee="")
                self.assertEqual(len(session.records), 1)
                self.assertTrue(self.errors(session))
                with self.assertRaises(ValueError):
                    export_port_excel(session, self.folder / f"{carrier}_blocked.xlsx")
                row = session.records[0]
                raw_before = json.dumps(row["raw"], ensure_ascii=False, sort_keys=True)
                session.update_record(row["record_id"], {"Cleaned_Consignee_Name_For_Output": "VERIFIED DEMO CONSIGNEE"}, "Đối chiếu chủ hàng từ nguồn demo")
                self.assertEqual(self.errors(session), [])
                self.assertEqual(json.dumps(row["raw"], ensure_ascii=False, sort_keys=True), raw_before)
                self.assertTrue(session.corrections)
                export_port_excel(session, self.folder / f"{carrier}_fixed.xlsx")

    def test_edit_refreshes_dependent_maps_without_reinferring_goods_or_fe(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = self.session(carrier)
                row = session.records[0]
                original_description = row["Description"]
                operator = row["Operator"]
                session.update_record(row["record_id"], {"Size_Type": "20RF", "FE_Status": "E", "Weight_Value": 3.0}, "Đối chiếu container rỗng từ dữ liệu demo")
                self.assertEqual(row["VTOS_Size"], "22R0")
                self.assertEqual(row["Cargo_Type"], "EMPTY REEFER")
                self.assertEqual(row["FE_Status"], "E")
                self.assertEqual(row["Description"], original_description)
                self.assertEqual(row["Operator"], operator)

    def test_vosco_export_preserves_manually_reviewed_description_for_empty(self):
        session = self.session("VOSCO")
        row = session.records[0]
        session.update_record(row["record_id"], {"FE_Status": "E", "Weight_Value": 3.0, "Description": "EMPTY REEFER DEMO NOTE"}, "Đối chiếu mô tả riêng của nguồn demo")
        _, _, values = self.read_output(session)
        self.assertEqual(values["F/E"].value, "E")
        self.assertEqual(values["Hàng hóa"].value, "EMPTY REEFER DEMO NOTE")

    def test_same_bl_duplicate_blocks_until_explicit_exclusion(self):
        source = create_vimc(self.folder / "duplicate.xlsx", extra_lines=("DEMU0000002 001235 20GP 16.055 THEP DEMO",))
        session = process_manifest(source, "VIMC")
        self.assertEqual(len(session.records), 2)
        self.assertIn("DUPLICATE_CONTAINER_BL", {item["code"] for item in self.errors(session)})
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.set_excluded(session.records[1]["record_id"], True, "Bản sao lặp trong bộ demo")
        self.assertEqual(len(session.records), 2)
        self.assertEqual(len(session.active_records()), 1)
        self.assertEqual(self.errors(session), [])
        _, _, values = self.read_output(session)
        self.assertEqual(values["Số lượng"].value, 1)

    def test_container_shared_by_two_bl_keeps_both_relations(self):
        source = create_vimc(self.folder / "shared.xlsx")
        book = load_workbook(source)
        sheet = book.active
        sheet.append(["B/L NO:", "", "DEMO-VIMC-002", "COC LADEN"])
        sheet.append(["1) DEMO SHIPPER\n2) SECOND DEMO CONSIGNEE", "", "", ""])
        sheet.append(["", "", "", "DEMU0000002 001235 20GP 16.055 THEP DEMO"])
        book.save(source)
        book.close()
        session = process_manifest(source, "VIMC")
        self.assertEqual(len(session.records), 2)
        self.assertEqual(session.statistics()["containers"], 1)
        self.assertEqual(session.statistics()["bills"], 2)
        self.assertEqual(self.errors(session), [])
        columns, rows = build_port_rows(session)
        self.assertEqual([row[columns.index("Số lượng")] for row in rows], [1, 1])
        self.assertEqual([row[columns.index("Số Vận Đơn")] for row in rows], ["DEMO-VIMC-001", "DEMO-VIMC-002"])

    def test_ambiguous_weight_requires_description_resolution_together(self):
        session = self.session(weight=20, description="STEEL DEMO 12000")
        row = session.records[0]
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", {item["code"] for item in self.errors(session)})
        session.update_record(row["record_id"], {"Weight_Value": 12}, "Xác nhận trọng lượng cuối dòng là kg")
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", {item["code"] for item in self.errors(session)})
        session.update_record(row["record_id"], {"Description": "20 STEEL DEMO"}, "Xác nhận phần trước trọng lượng là mô tả hàng")
        self.assertEqual(self.errors(session), [])
        self.assertIn("20 STEEL DEMO 12000", row["raw"]["text"])

    def test_unknown_manual_size_cannot_bypass_validation(self):
        session = self.session()
        row = session.records[0]
        session.update_record(row["record_id"], {"Size_Type": "99ZZ"}, "Thử một kích cỡ chưa được hỗ trợ")
        self.assertTrue(self.errors(session))
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_source_overwrite_is_blocked_for_export_and_review(self):
        session = self.session()
        source = Path(session.metadata["source_path"])
        original = source.read_bytes()
        with self.assertRaises(ValueError):
            export_port_excel(session, source, overwrite=True)
        with self.assertRaises(ValueError):
            session.save_review(source)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(session.metadata["source_sha256"], hashlib.sha256(original).hexdigest())

    def test_formula_like_user_text_is_written_as_literal_string(self):
        session = self.session()
        row = session.records[0]
        formula_text = '=HYPERLINK("https://example.invalid", "DEMO")'
        session.update_record(row["record_id"], {"Description": formula_text, "Cleaned_Consignee_Name_For_Output": "+SUM(1,2)"}, "Giữ nguyên chuỗi ký tự của dữ liệu demo")
        _, _, values = self.read_output(session)
        self.assertEqual(values["Hàng hóa"].value, formula_text)
        self.assertEqual(values["Hàng hóa"].data_type, "s")
        self.assertEqual(values["Chủ hàng"].value, "+SUM(1,2)")
        self.assertEqual(values["Chủ hàng"].data_type, "s")

    def test_existing_export_needs_explicit_overwrite(self):
        session = self.session()
        target = self.folder / "output.xlsx"
        export_port_excel(session, target)
        with self.assertRaises(FileExistsError):
            export_port_excel(session, target)
        self.assertEqual(export_port_excel(session, target, overwrite=True), target.resolve())

    def test_cli_processes_one_manifest_and_saves_excel_and_review(self):
        source = create_vimc(self.folder / "cli_input.xlsx")
        output = self.folder / "cli_output.xlsx"
        review = self.folder / "cli_review.json"
        result = subprocess.run([sys.executable, "-m", "manifest_cleaner.cli", str(source), "--carrier", "VIMC", "--output", str(output), "--review", str(review)],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(output.is_file())
        data = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(data["carrier"], "VIMC")
        self.assertEqual(data["statistics"]["active_records"], 1)
        self.assertEqual(data["statistics"]["errors"], 0)
        self.assertEqual(data["metadata"]["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
