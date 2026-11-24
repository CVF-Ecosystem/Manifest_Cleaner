"""Export acceptance tests: preview parity, paired files and disk failures.

The test inputs are temporary workbooks. Existing output bytes are deliberately
distinct so an interrupted overwrite cannot pass by merely leaving *a* file.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from openpyxl import load_workbook

from manifest_cleaner import exporter
from manifest_cleaner.engine import process_manifest
from scripts.create_samples import CREATORS, create_vimc


COMMON_COLUMNS = ["STT", "Số lượng", "Số BL", "Số Container", "Hãng khai thác", "Kích cỡ",
                  "Kích cỡ VTOS", "F/E", "TL hàng", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
                  "Hàng hóa", "Loại hàng", "Độ chính xác (%)", "Ghi chú"]
VIMC_COLUMNS = ["STT", "Số Vận Đơn", "Số Container", "Số niêm chì", "Số niêm chì 1", "Chủ hàng",
                "Kích cỡ", "Loại Container", "Hãng khai thác", "Loại hàng", "F/E", "Trọng lượng (Tấn)",
                "Hàng hóa", "Số lượng", "Độ chính xác (%)", "Ghi chú"]


class Export110Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.outputs = self.root / "outputs"
        self.outputs.mkdir()

    def session(self, carrier="VIMC"):
        source = CREATORS[carrier](self.root / f"{carrier}_input.xlsx")
        return process_manifest(source, carrier)

    @staticmethod
    def output_rows(path):
        book = load_workbook(path, data_only=False)
        try:
            sheet = book["Processed_Manifest"]
            headers = [cell.value for cell in sheet[1]]
            rows = [dict(zip(headers, (cell.value for cell in cells))) for cells in sheet.iter_rows(min_row=2)]
            return headers, rows
        finally:
            book.close()

    @staticmethod
    def custom_properties(path):
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("docProps/custom.xml"))
        return {item.attrib["name"]: next(iter(item)).text for item in root}

    def assert_preview_equal(self, preview, actual):
        self.assertEqual(set(preview), set(actual))
        for field, expected in preview.items():
            # Excel blank strings round-trip as None; they have the same empty
            # import meaning. Numbers remain numeric and are compared exactly.
            if expected == "" and actual[field] is None:
                continue
            self.assertEqual(actual[field], expected, field)

    def seed_outputs(self, name="manifest.xlsx", *, excel=True, review=True):
        path = self.outputs / name
        sidecar = path.with_suffix(".review.json")
        before = {}
        if excel:
            before[path] = b"previous Excel output bytes"
            path.write_bytes(before[path])
        if review:
            before[sidecar] = b'{"previous":"review output"}'
            sidecar.write_bytes(before[sidecar])
        return path, sidecar, before

    def assert_old_pair_preserved(self, before, paths):
        for path in paths:
            if path in before:
                self.assertEqual(path.read_bytes(), before[path], str(path))
            else:
                self.assertFalse(path.exists(), str(path))

    def test_preview_matches_actual_sixteen_column_export_all_carriers(self):
        for carrier in CREATORS:
            for status in ("F", "E"):
                with self.subTest(carrier=carrier, status=status):
                    session = self.session(carrier)
                    record = session.records[0]
                    session.update_record(record["record_id"], {
                        "Size_Type": "40GP", "Weight_Value": 16.055 if status == "F" else 3,
                        "FE_Status": status, "Description": "REVIEWED GOODS" if status == "F" else "REVIEWED EMPTY NOTE",
                    }, "Đối chiếu dữ liệu để kiểm tra preview và file import")
                    preview = exporter.preview_record_for_export(session, record)
                    expected_columns = VIMC_COLUMNS if carrier == "VIMC" else COMMON_COLUMNS
                    self.assertEqual(list(preview), expected_columns)
                    path = exporter.export_port_excel(session, self.outputs / f"{carrier}_{status}.xlsx")
                    headers, rows = self.output_rows(path)
                    self.assertEqual(headers, expected_columns)
                    self.assertEqual(len(rows), 1)
                    self.assert_preview_equal(preview, rows[0])
                    weight_field = "Trọng lượng (Tấn)" if carrier == "VIMC" else "TL hàng"
                    self.assertEqual(preview[weight_field], (16.055 if carrier == "VOSCO" else 16.06) if status == "F" else 3)
                    self.assertEqual(preview["Hàng hóa"], "EMPTY" if status == "E" and carrier != "VOSCO" else record["Description"])

    def test_preview_quantity_and_sequence_follow_active_records(self):
        source = create_vimc(self.root / "multiple.xlsx", extra_lines=(
            "ABCU1234567 001236 20GP 21 RICE", "ABCU7654321 001237 20GP 22 STEEL",
        ))
        session = process_manifest(source, "VIMC")
        session.set_excluded(session.records[1]["record_id"], True, "Dòng nằm ngoài phạm vi cần xuất")
        path = exporter.export_port_excel(session, self.outputs / "multiple.xlsx")
        _, rows = self.output_rows(path)
        self.assertEqual(len(rows), 2)
        for position, (record, actual) in enumerate(zip(session.active_records(), rows), 1):
            preview = exporter.preview_record_for_export(session, record)
            self.assertEqual(preview["STT"], position)
            self.assertEqual(preview["Số lượng"], 2)
            self.assert_preview_equal(preview, actual)

    def test_bundle_links_excel_and_review_v2_to_same_session(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = self.session(carrier)
                session.update_record(session.records[0]["record_id"], {"Cleaned_Consignee_Name_For_Output": "VERIFIED CONSIGNEE"}, "Kiểm tra biên bản đối chiếu đi cùng file xuất")
                path = self.outputs / f"{carrier}_bundle.xlsx"
                result = exporter.export_port_bundle(session, path)
                self.assertEqual(result["excel"], path.resolve())
                self.assertEqual(result["review"], path.with_suffix(".review.json").resolve())
                data = json.loads(result["review"].read_text(encoding="utf-8"))
                self.assertEqual(data["format"], "manifest-cleaner-review-v2")
                self.assertEqual(data["schema_version"], 2)
                self.assertEqual(data["metadata"]["session_id"], session.metadata["session_id"])
                self.assertEqual(data["corrections"], session.corrections)
                receipt = data["metadata"]["last_export"]
                self.assertEqual(receipt["session_id"], session.metadata["session_id"])
                self.assertEqual(receipt["excel_path"], str(path.resolve()))
                self.assertEqual(receipt["review_path"], str(result["review"]))
                self.assertEqual(receipt["excel_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                properties = self.custom_properties(path)
                self.assertEqual(properties["session_id"], data["metadata"]["session_id"])
                self.assertEqual(properties["source_sha256"], session.metadata["source_sha256"])
                self.assertEqual(properties["carrier"], carrier)
                self.assertEqual(properties["app_version"], data["app_version"])
                self.assertEqual(len(self.output_rows(path)[0]), 16)

    def test_existing_either_output_blocks_without_overwrite_and_preserves_both(self):
        session = self.session()
        for index, (excel, review) in enumerate(((True, False), (False, True), (True, True))):
            with self.subTest(excel=excel, review=review):
                path, sidecar, before = self.seed_outputs(f"existing_{index}.xlsx", excel=excel, review=review)
                with self.assertRaises(FileExistsError):
                    exporter.export_port_bundle(session, path)
                self.assert_old_pair_preserved(before, (path, sidecar))

    def test_explicit_overwrite_replaces_both_outputs(self):
        session = self.session()
        path, sidecar, before = self.seed_outputs()
        result = exporter.export_port_bundle(session, path, overwrite=True)
        self.assertNotEqual(path.read_bytes(), before[path])
        self.assertNotEqual(sidecar.read_bytes(), before[sidecar])
        self.assertEqual(len(self.output_rows(path)[1]), 1)
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["session_id"], session.metadata["session_id"])
        self.assertEqual(result["review"], sidecar.resolve())

    def test_excel_filename_matching_old_backup_name_keeps_new_content_and_receipt(self):
        session = self.session()
        path = self.outputs / "previous_0.xlsx"
        exporter.export_port_bundle(session, path)
        session.update_record(session.records[0]["record_id"], {"Seal_No": "009999"},
                              "Đối chiếu seal mới trước khi ghi đè bộ file")
        result = exporter.export_port_bundle(session, path, overwrite=True)
        _, rows = self.output_rows(path)
        data = json.loads(result["review"].read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["Số niêm chì"], "009999")
        self.assertEqual(data["records"][0]["Seal_No"], "009999")
        self.assertEqual(data["metadata"]["last_export"]["excel_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        properties = self.custom_properties(path)
        self.assertEqual(properties["source_sha256"], data["metadata"]["source_sha256"])
        self.assertEqual(properties["session_id"], data["metadata"]["session_id"])

    def test_custom_review_name_matching_old_backup_name_keeps_pair_consistent(self):
        session = self.session()
        path = self.outputs / "port.xlsx"
        sidecar = self.root / "separate_evidence" / "previous_1.json"
        exporter.export_port_bundle(session, path, review_path=sidecar)
        session.update_record(session.records[0]["record_id"], {"Seal_No": "008888"},
                              "Đối chiếu seal mới cho bản đối chiếu ở thư mục khác")
        result = exporter.export_port_bundle(session, path, review_path=sidecar, overwrite=True)
        self.assertEqual(result["review"], sidecar.resolve())
        _, rows = self.output_rows(path)
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["Số niêm chì"], "008888")
        self.assertEqual(data["records"][0]["Seal_No"], "008888")
        self.assertEqual(data["metadata"]["last_export"]["excel_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(data["metadata"]["last_export"]["review_path"], str(sidecar.resolve()))
        properties = self.custom_properties(path)
        self.assertEqual(properties["source_sha256"], data["metadata"]["source_sha256"])
        self.assertEqual(properties["session_id"], data["metadata"]["session_id"])

    def test_excel_only_mode_does_not_create_sidecar(self):
        session = self.session()
        path = self.outputs / "excel_only.xlsx"
        result = exporter.export_port_bundle(session, path, include_review=False)
        self.assertEqual(result["excel"], path.resolve())
        self.assertIsNone(result["review"])
        self.assertTrue(path.is_file())
        self.assertFalse(path.with_suffix(".review.json").exists())

    def test_json_staging_write_failure_preserves_existing_pair(self):
        session = self.session()
        path, sidecar, before = self.seed_outputs()
        with patch("manifest_cleaner.engine.json.dump", side_effect=OSError("TEST_JSON_WRITE_DENIED")):
            with self.assertRaises(Exception) as caught:
                exporter.export_port_bundle(session, path, overwrite=True)
        self.assertIn("TEST_JSON_WRITE_DENIED", str(caught.exception))
        self.assert_old_pair_preserved(before, (path, sidecar))

    def test_json_staging_write_failure_does_not_leave_new_excel(self):
        session = self.session()
        path, sidecar, before = self.seed_outputs(excel=False, review=False)
        with patch("manifest_cleaner.engine.json.dump", side_effect=OSError("TEST_JSON_WRITE_DENIED")):
            with self.assertRaises(Exception):
                exporter.export_port_bundle(session, path)
        self.assert_old_pair_preserved(before, (path, sidecar))

    def test_commit_failure_on_either_file_restores_previous_pair(self):
        session = self.session()
        for target in ("excel", "review"):
            with self.subTest(target=target):
                path, sidecar, before = self.seed_outputs(f"replace_{target}.xlsx")
                failed_path = path if target == "excel" else sidecar
                original_replace = os.replace
                injected = []

                def fail_once(source, destination):
                    if Path(destination).resolve() == failed_path.resolve() and not injected:
                        injected.append(True)
                        raise PermissionError("TEST_COMMIT_DENIED")
                    return original_replace(source, destination)

                with patch("manifest_cleaner.exporter.os.replace", side_effect=fail_once):
                    with self.assertRaises(Exception):
                        exporter.export_port_bundle(session, path, overwrite=True)
                self.assertEqual(injected, [True], "Commit failure injection did not reach the output path")
                self.assert_old_pair_preserved(before, (path, sidecar))

    def test_sidecar_commit_failure_removes_new_excel(self):
        session = self.session()
        path, sidecar, before = self.seed_outputs(excel=False, review=False)
        original_replace = os.replace
        injected = []

        def fail_sidecar(source, destination):
            if Path(destination).resolve() == sidecar.resolve():
                injected.append(True)
                raise PermissionError("TEST_NEW_SIDECAR_DENIED")
            return original_replace(source, destination)

        with patch("manifest_cleaner.exporter.os.replace", side_effect=fail_sidecar):
            with self.assertRaises(Exception):
                exporter.export_port_bundle(session, path)
        self.assertTrue(injected)
        self.assert_old_pair_preserved(before, (path, sidecar))

    def test_failed_rollback_reports_partial_result_and_recovery_location(self):
        session = self.session()
        path, sidecar, before = self.seed_outputs("rollback_failure.xlsx")
        original_replace = os.replace
        excel_committed = []

        def fail_commit_and_rollback(source, destination):
            destination = Path(destination).resolve()
            if destination == sidecar.resolve():
                raise PermissionError("TEST_SIDECAR_COMMIT_DENIED")
            if destination == path.resolve():
                if excel_committed:
                    raise PermissionError("TEST_EXCEL_ROLLBACK_DENIED")
                result = original_replace(source, destination)
                excel_committed.append(True)
                return result
            return original_replace(source, destination)

        with patch("manifest_cleaner.exporter.os.replace", side_effect=fail_commit_and_rollback):
            with self.assertRaises(Exception) as caught:
                exporter.export_port_bundle(session, path, overwrite=True)
        preserved = all(p.exists() and p.read_bytes() == before[p] for p in (path, sidecar))
        if not preserved:
            message = str(caught.exception).lower()
            self.assertRegex(message, r"khôi phục|phục hồi|rollback|partial|một phần")
            # A caller must be told where the surviving recovery files are,
            # not just that the OS returned PermissionError.
            recovery_dirs = [p for p in self.outputs.iterdir() if p.is_dir()]
            self.assertTrue(recovery_dirs, message)
            self.assertTrue(any(p.name.lower() in message for p in recovery_dirs), message)
            backup_bytes = [p.read_bytes() for d in recovery_dirs for p in d.rglob("*") if p.is_file()]
            self.assertIn(before[path], backup_bytes)

    def test_changed_source_blocks_export_without_touching_existing_outputs(self):
        session = self.session()
        source = Path(session.metadata["source_path"])
        book = load_workbook(source)
        book.active.cell(1, 1, "SOURCE WAS CHANGED AFTER IMPORT")
        book.save(source)
        book.close()
        path, sidecar, before = self.seed_outputs()
        with self.assertRaises(ValueError) as caught:
            exporter.export_port_bundle(session, path, overwrite=True)
        self.assertTrue("thay đổi" in str(caught.exception).lower() or getattr(caught.exception, "code", None) == "source_changed")
        self.assert_old_pair_preserved(before, (path, sidecar))

    def test_formula_like_values_are_literal_text_in_bundle(self):
        for carrier in CREATORS:
            for index, literal in enumerate(('=HYPERLINK("https://example.invalid","text")', "+1+2", "-1+2", "@SUM(A1:A2)")):
                with self.subTest(carrier=carrier, literal=literal):
                    session = self.session(carrier)
                    record = session.records[0]
                    session.update_record(record["record_id"], {"Description": literal, "Cleaned_Consignee_Name_For_Output": "https://example.invalid/owner"}, "Giữ nguyên văn dữ liệu người dùng nhập")
                    path = self.outputs / f"literal_{carrier}_{index}.xlsx"
                    result = exporter.export_port_bundle(session, path)
                    book = load_workbook(result["excel"], data_only=False)
                    try:
                        sheet = book["Processed_Manifest"]
                        headers = [cell.value for cell in sheet[1]]
                        cargo = sheet.cell(2, headers.index("Hàng hóa") + 1)
                        party = sheet.cell(2, headers.index("Chủ hàng") + 1)
                        self.assertEqual(cargo.value, literal)
                        self.assertEqual(cargo.data_type, "s")
                        self.assertIsNone(cargo.hyperlink)
                        self.assertEqual(party.data_type, "s")
                        self.assertIsNone(party.hyperlink)
                    finally:
                        book.close()


if __name__ == "__main__":
    unittest.main()
