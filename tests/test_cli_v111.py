"""Regression for failed exports overwriting one half of an existing bundle."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from manifest_cleaner.cli import main
from manifest_cleaner.engine import load_review, process_manifest
from scripts.create_samples import create_vimc


class Cli111Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.good = create_vimc(self.folder / "good.xlsx")
        self.bad = create_vimc(self.folder / "bad.xlsx", consignee="")

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main([str(argument) for argument in args])
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def pair(self, stem="port", custom_review=False):
        output = self.folder / f"{stem}.xlsx"
        review = (self.folder / "evidence" / f"{stem}_custom.json" if custom_review
                  else output.with_suffix(".review.json"))
        code, _, error = self.invoke(self.good, "--carrier", "VIMC", "--output", output, "--review", review)
        self.assertEqual(code, 0, error)
        return output, review

    def assert_protected_failure(self, code, error):
        self.assertNotEqual(code, 0)
        self.assertIn("giữ nguyên", error)
        self.assertIn("--review", error)
        self.assertIn("tên file mới", error)
        self.assertIn("bỏ --output", error)

    def assert_bytes_unchanged(self, before):
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents, str(path))

    def test_invalid_export_preserves_explicit_existing_pair_even_with_overwrite(self):
        output, review = self.pair()
        before = {path: path.read_bytes() for path in (output, review, self.good, self.bad)}
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                             "--review", review, *flags)
                self.assert_bytes_unchanged(before)
                self.assert_protected_failure(code, error)

    def test_invalid_export_preserves_implicit_existing_pair_even_with_overwrite(self):
        output, review = self.pair()
        before = {path: path.read_bytes() for path in (output, review)}
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output, *flags)
                self.assert_protected_failure(code, error)
                self.assert_bytes_unchanged(before)

    def test_invalid_export_preserves_custom_review_pair_in_another_directory(self):
        output, review = self.pair(custom_review=True)
        before = {path: path.read_bytes() for path in (output, review)}
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                             "--review", review, *flags)
                self.assert_protected_failure(code, error)
                self.assert_bytes_unchanged(before)
                self.assertFalse(output.with_suffix(".review.json").exists())

    def test_existing_orphan_review_is_preserved_when_excel_is_missing(self):
        for explicit in (False, True):
            output, review = self.pair(f"orphan_{explicit}", custom_review=explicit)
            output.unlink()
            before = review.read_bytes()
            for flags in ([], ["--overwrite"]):
                with self.subTest(explicit=explicit, flags=flags):
                    options = ["--review", review] if explicit else []
                    code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                                 *options, *flags)
                    self.assert_protected_failure(code, error)
                    self.assertFalse(output.exists())
                    self.assertEqual(review.read_bytes(), before)

    def test_existing_excel_with_fresh_review_destination_rejects_before_any_write(self):
        output, old_review = self.pair()
        before = {path: path.read_bytes() for path in (output, old_review)}
        fresh = self.folder / "not_created" / "new_report.json"
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                             "--review", fresh, *flags)
                self.assert_protected_failure(code, error)
                self.assert_bytes_unchanged(before)
                self.assertFalse(fresh.exists())
                self.assertFalse(fresh.parent.exists())

    def test_invalid_excel_only_export_keeps_existing_excel_and_sidecar(self):
        output, review = self.pair()
        before = {path: path.read_bytes() for path in (output, review)}
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                             "--no-review", *flags)
                self.assert_protected_failure(code, error)
                self.assert_bytes_unchanged(before)

    def test_resume_with_blocking_errors_cannot_replace_existing_pair(self):
        output, review = self.pair()
        saved = self.folder / "blocked_session.json"
        process_manifest(self.bad, "VIMC").save_review(saved)
        before = {path: path.read_bytes() for path in (output, review, saved)}
        for flags in ([], ["--overwrite"]):
            with self.subTest(flags=flags):
                code, _, error = self.invoke("--resume", saved, "--output", output,
                                             "--review", review, *flags)
                self.assert_protected_failure(code, error)
                self.assert_bytes_unchanged(before)

    def test_first_invalid_export_saves_explicit_fresh_review_without_excel(self):
        for overwrite in (False, True):
            with self.subTest(overwrite=overwrite):
                output = self.folder / f"new_{overwrite}.xlsx"
                review = self.folder / "fresh_evidence" / f"new_{overwrite}.json"
                flags = ["--overwrite"] if overwrite else []
                code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output,
                                             "--review", review, *flags)
                self.assertNotEqual(code, 0)
                self.assertIn("Đã lưu", error)
                self.assertFalse(output.exists())
                self.assertTrue(review.is_file())
                resumed = load_review(review)
                self.assertGreater(resumed.statistics()["errors"], 0)
                self.assertEqual(resumed.metadata["source_path"], str(self.bad.resolve()))
                self.assertFalse(output.with_suffix(".review.json").exists())

    def test_first_invalid_export_without_explicit_review_creates_no_outputs(self):
        output = self.folder / "new.xlsx"
        code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--output", output, "--overwrite")
        self.assertNotEqual(code, 0)
        self.assertIn("--review", error)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".review.json").exists())

    def test_review_only_keeps_explicit_save_and_overwrite_semantics(self):
        review = self.folder / "standalone_error_report.json"
        code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--review", review)
        self.assertEqual(code, 2, error)
        self.assertGreater(load_review(review).statistics()["errors"], 0)
        original = review.read_bytes()
        code, _, _ = self.invoke(self.bad, "--carrier", "VIMC", "--review", review)
        self.assertNotEqual(code, 0)
        self.assertEqual(review.read_bytes(), original)
        code, _, error = self.invoke(self.bad, "--carrier", "VIMC", "--review", review, "--overwrite")
        self.assertEqual(code, 2, error)
        self.assertNotEqual(review.read_bytes(), original)
        self.assertGreater(load_review(review).statistics()["errors"], 0)

    def test_valid_overwrite_still_replaces_excel_and_review_as_a_matching_pair(self):
        output, review = self.pair(custom_review=True)
        before = {path: path.read_bytes() for path in (output, review)}
        replacement = create_vimc(self.folder / "replacement.xlsx", weight=30)
        code, _, error = self.invoke(replacement, "--carrier", "VIMC", "--output", output,
                                     "--review", review, "--overwrite")
        self.assertEqual(code, 0, error)
        self.assertNotEqual(output.read_bytes(), before[output])
        self.assertNotEqual(review.read_bytes(), before[review])
        data = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["last_export"]["excel_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        book = load_workbook(output)
        try:
            properties = {prop.name: prop.value for prop in book.custom_doc_props}
            self.assertEqual(properties["session_id"], data["metadata"]["session_id"])
            sheet = book["Processed_Manifest"]
            headers = [cell.value for cell in sheet[1]]
            self.assertEqual(sheet.cell(2, headers.index("Trọng lượng (Tấn)") + 1).value, 30)
        finally:
            book.close()


if __name__ == "__main__":
    unittest.main()
