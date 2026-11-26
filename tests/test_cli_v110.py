"""End-to-end CLI contracts for export bundles and resumed review sessions."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from manifest_cleaner import exporter
from manifest_cleaner.cli import main
from manifest_cleaner.engine import load_review, process_manifest
from scripts.create_samples import create_vimc


class Cli110Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_cli_redirected_cp1252_and_utf8_streams(self):
        for encoding, args, expected in (("cp1252", ["--help"], 0),
                                         ("cp1252", [], 2),
                                         ("cp1252", ["missing.xlsx", "--carrier", "VIMC"], 1),
                                         ("utf-8", ["--help"], 0)):
            with self.subTest(encoding=encoding, args=args):
                env = dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8="0", PYTHONDONTWRITEBYTECODE="1")
                result = subprocess.run([sys.executable, "-m", "manifest_cleaner.cli", *args],
                                        capture_output=True, env=env)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn(b"UnicodeEncodeError", result.stderr)
                output = (result.stdout + result.stderr).decode(encoding)
                self.assertTrue(output)
                if encoding == "utf-8" and args == ["--help"]:
                    self.assertIn("Xử lý", output)

    def test_cp1252_redirected_json_preserves_exit_and_parseable_output(self):
        source = self.source()
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-m", "manifest_cleaner.cli", str(source), "--carrier", "VIMC"],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.decode("cp1252"))
        self.assertEqual(payload["carrier"], "VIMC")

    def test_cp1252_json_round_trips_non_bmp_output_path(self):
        source = self.source()
        output = self.folder / "port_😀.xlsx"
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-m", "manifest_cleaner.cli", str(source),
                                 "--carrier", "VIMC", "--output", str(output)],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = result.stdout.decode("cp1252")
        _, end = json.JSONDecoder().raw_decode(text)
        exported = json.loads(text[end:].strip())
        self.assertEqual(Path(exported["excel"]), output.resolve())

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main([str(argument) for argument in args])
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def source(self, **kwargs):
        return create_vimc(self.folder / "input.xlsx", **kwargs)

    def edited_review(self):
        source = self.source()
        session = process_manifest(source, "VIMC")
        session.update_record(session.records[0]["record_id"], {"Seal_No": "009999", "Weight_Value": 18.5},
                              "Đã đối chiếu để tiếp tục phiên bằng CLI")
        review = self.folder / "saved_session.json"
        session.save_review(review)
        return source, review

    def output_row(self, path):
        book = load_workbook(path, data_only=False)
        try:
            sheet = book[exporter.SHEET_NAME]
            headers = [cell.value for cell in sheet[1]]
            row = dict(zip(headers, [cell.value for cell in sheet[2]]))
            properties = {prop.name: prop.value for prop in book.custom_doc_props}
            return row, properties
        finally:
            book.close()

    def test_output_creates_matching_excel_and_review_by_default(self):
        source = self.source()
        output = self.folder / "port.xlsx"
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output)
        self.assertEqual(code, 0, error)
        review = output.with_suffix(".review.json")
        self.assertTrue(output.is_file())
        self.assertTrue(review.is_file())
        row, properties = self.output_row(output)
        data = json.loads(review.read_text(encoding="utf-8"))
        expected_source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual(len(row), 46)
        self.assertEqual(data["metadata"]["source_sha256"], expected_source_hash)
        self.assertEqual(properties["source_sha256"], expected_source_hash)
        self.assertEqual(properties["session_id"], data["metadata"]["session_id"])
        self.assertEqual(data["metadata"]["last_export"]["excel_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual(len(load_review(review).records), 1)

    def test_no_review_creates_excel_only(self):
        source = self.source()
        output = self.folder / "excel_only.xlsx"
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output, "--no-review")
        self.assertEqual(code, 0, error)
        self.assertTrue(output.is_file())
        self.assertFalse(output.with_suffix(".review.json").exists())
        self.assertEqual(list(self.folder.glob("*.json")), [])

    def test_custom_review_in_another_directory_keeps_bundle_and_source_hash(self):
        source = self.source()
        output = self.folder / "exports" / "port.xlsx"
        review = self.folder / "evidence" / "custom_session.json"
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output, "--review", review)
        self.assertEqual(code, 0, error)
        self.assertTrue(output.is_file())
        self.assertTrue(review.is_file())
        self.assertFalse(output.with_suffix(".review.json").exists())
        data = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["last_export"]["excel_path"], str(output.resolve()))
        self.assertEqual(data["metadata"]["last_export"]["review_path"], str(review.resolve()))
        self.assertEqual(load_review(review).metadata["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_resume_keeps_edits_and_history_when_exporting_new_targets(self):
        _, saved = self.edited_review()
        original_json = saved.read_bytes()
        output = self.folder / "resumed.xlsx"
        review = self.folder / "resumed_review.json"
        code, _, error = self.invoke("--resume", saved, "--output", output, "--review", review)
        self.assertEqual(code, 0, error)
        row, _ = self.output_row(output)
        self.assertEqual(row["Số niêm chì"], "009999")
        self.assertEqual(row["TL hàng"], 18.5)
        resumed = load_review(review)
        self.assertEqual(resumed.corrections, json.loads(original_json)["corrections"])
        self.assertEqual(saved.read_bytes(), original_json)

    def test_resume_source_relocation_requires_matching_original_bytes(self):
        source, saved = self.edited_review()
        moved = self.folder / "relocated.xlsx"
        source.rename(moved)
        output = self.folder / "relocated_export.xlsx"
        failed, _, _ = self.invoke("--resume", saved, "--output", output)
        self.assertNotEqual(failed, 0)
        self.assertFalse(output.exists())
        code, _, error = self.invoke("--resume", saved, "--source", moved, "--output", output)
        self.assertEqual(code, 0, error)
        row, _ = self.output_row(output)
        self.assertEqual(row["Số niêm chì"], "009999")
        self.assertEqual(load_review(output.with_suffix(".review.json")).metadata["source_path"], str(moved.resolve()))

    def test_resume_rejects_new_input_settings_carrier_and_sheet_before_writing(self):
        source, review = self.edited_review()
        settings = self.folder / "settings.json"
        settings.write_text('{"VIMC": {"number_format": "decimal_dot"}}', encoding="utf-8")
        before = review.read_bytes()
        for extra in ([source], ["--settings", settings], ["--carrier", "VIMC"], ["--sheet", "Manifest"]):
            with self.subTest(extra=extra):
                output = self.folder / "should_not_exist.xlsx"
                code, _, error = self.invoke("--resume", review, "--output", output, *extra)
                self.assertNotEqual(code, 0)
                self.assertIn("--resume", error)
                self.assertFalse(output.exists())
                self.assertEqual(review.read_bytes(), before)

    def test_missing_settings_does_not_create_either_requested_output(self):
        source = self.source()
        output = self.folder / "port.xlsx"
        review = self.folder / "review.json"
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--settings", self.folder / "missing.json",
                                     "--output", output, "--review", review)
        self.assertNotEqual(code, 0)
        self.assertIn("missing.json", error)
        self.assertFalse(output.exists())
        self.assertFalse(review.exists())

    def test_identical_excel_and_review_paths_cannot_clobber_existing_file(self):
        source = self.source()
        same = self.folder / "same.xlsx"
        same.write_bytes(b"existing user output")
        before = same.read_bytes()
        source_before = source.read_bytes()
        code, _, _ = self.invoke(source, "--carrier", "VIMC", "--output", same, "--review", same, "--overwrite")
        self.assertNotEqual(code, 0)
        self.assertEqual(same.read_bytes(), before)
        self.assertEqual(source.read_bytes(), source_before)

    def test_error_report_branch_validates_same_output_path_before_any_write(self):
        source = self.source(consignee="")
        same = self.folder / "same.json"
        same.write_text('{"existing": "user evidence"}', encoding="utf-8")
        before = same.read_bytes()
        code, _, _ = self.invoke(source, "--carrier", "VIMC", "--output", same, "--review", same, "--overwrite")
        self.assertNotEqual(code, 0)
        self.assertEqual(same.read_bytes(), before)

    def test_source_path_is_protected_from_excel_and_review_overwrite(self):
        source = self.source()
        before = source.read_bytes()
        for options in (["--output", source], ["--review", source],
                        ["--output", source, "--review", source]):
            with self.subTest(options=options):
                code, _, _ = self.invoke(source, "--carrier", "VIMC", *options, "--overwrite")
                self.assertNotEqual(code, 0)
                self.assertEqual(source.read_bytes(), before)

    def test_blocking_errors_write_requested_review_without_creating_import_excel(self):
        source = self.source(consignee="")
        output = self.folder / "blocked.xlsx"
        review = self.folder / "blocked_review.json"
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output, "--review", review)
        self.assertNotEqual(code, 0)
        self.assertFalse(output.exists())
        self.assertTrue(review.is_file(), error)
        resumed = load_review(review)
        self.assertEqual(len(resumed.records), 1)
        self.assertTrue(any(item["severity"] == "error" for item in resumed.validate()))

    def test_existing_either_bundle_target_requires_explicit_overwrite(self):
        source = self.source()
        for existing in ("excel", "review"):
            with self.subTest(existing=existing):
                output = self.folder / f"{existing}.xlsx"
                review = output.with_suffix(".review.json")
                present, absent = (output, review) if existing == "excel" else (review, output)
                present.write_bytes(b"previous user artifact")
                before = present.read_bytes()
                code, _, _ = self.invoke(source, "--carrier", "VIMC", "--output", output)
                self.assertNotEqual(code, 0)
                self.assertEqual(present.read_bytes(), before)
                self.assertFalse(absent.exists())
                code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output, "--overwrite")
                self.assertEqual(code, 0, error)
                self.assertEqual(len(load_review(review).records), 1)
                self.assertEqual(self.output_row(output)[0]["Số Container"], "DEMU0000002")

    def test_explicit_overwrite_replaces_both_excel_and_custom_review(self):
        source = self.source()
        output = self.folder / "both.xlsx"
        review = self.folder / "both.json"
        output.write_bytes(b"old excel")
        review.write_bytes(b"old json")
        code, _, error = self.invoke(source, "--carrier", "VIMC", "--output", output, "--review", review, "--overwrite")
        self.assertEqual(code, 0, error)
        self.assertEqual(self.output_row(output)[0]["Số niêm chì"], "001235")
        self.assertEqual(len(load_review(review).records), 1)


if __name__ == "__main__":
    unittest.main()
