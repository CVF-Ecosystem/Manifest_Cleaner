"""Fixed synthetic input -> manually transcribed domain expectations.

Expected files must never be generated from application output. These cases
are regression evidence, not port approval or a measured accuracy benchmark.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from manifest_cleaner import exporter
from manifest_cleaner.engine import process_manifest
from manifest_cleaner.exporter import build_port_rows, export_port_excel
from tests.test_integration import EXPECTED_TOS


FIXTURES = Path(__file__).parent / "fixtures" / "golden_v110"


class Golden110Tests(unittest.TestCase):
    def check_case(self, name):
        expected_path = FIXTURES / f"{name}.expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        self.assertEqual(expected["fixture_kind"], "synthetic_manual_expectation")
        self.assertFalse(expected["port_approved"])
        self.assertTrue(expected["reasoning"].strip())
        source = FIXTURES / expected["input_file"]
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual(before, expected["input_sha256"], "Golden source bytes changed; review the fixture deliberately")
        session = process_manifest(source, expected["carrier"], settings=expected["settings"])
        errors = [finding for finding in session.validate() if finding["severity"] == "error"]
        self.assertEqual(errors, [])
        self.assertEqual(len(session.records), len(expected["records"]))
        for position, (actual, wanted) in enumerate(zip(session.records, expected["records"]), 1):
            for field, value in wanted.items():
                with self.subTest(record=position, field=field):
                    self.assertEqual(actual.get(field), value)
        for field, value in expected["metadata"].items():
            self.assertEqual(session.metadata.get(field), value, field)
        columns, values = build_port_rows(session)
        self.assertEqual(columns, expected["schema_columns"])
        self.assertEqual(len(columns), 16)
        self.assertEqual(len(values), len(expected["export_rows"]))
        for position, (row, wanted) in enumerate(zip(values, expected["export_rows"]), 1):
            actual = dict(zip(columns, row))
            for field, value in wanted.items():
                with self.subTest(export_row=position, field=field):
                    self.assertEqual(actual[field], value)
        # Check the written file independently, including string identifiers.
        with tempfile.TemporaryDirectory() as temp:
            output = export_port_excel(session, Path(temp) / "golden_output.xlsx")
            book = load_workbook(output, data_only=False)
            try:
                sheet = book[exporter.SHEET_NAME]
                headers = [cell.value for cell in sheet[1]]
                self.assertEqual(headers, EXPECTED_TOS)
                self.assertEqual(sheet.max_row - 1, len(expected["export_rows"]))
                for position, wanted in enumerate(expected["export_rows"], 2):
                    self.assertIsNone(sheet.cell(position, headers.index("Ghi chú") + 1).value)
                    for field, value in wanted.items():
                        if field == "STT":
                            continue  # STT is shown in the app only.
                        cell = sheet.cell(position, headers.index(field) + 1)
                        with self.subTest(excel_row=position, field=field):
                            self.assertEqual(cell.value, value)
                            self.assertEqual(cell.data_type, "s" if isinstance(value, str) else "n")
            finally:
                book.close()
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_vosco_port_line_cannot_replace_goods(self):
        self.check_case("vosco_metadata_lines")

    def test_vinafco_joined_header_defines_kg(self):
        self.check_case("vinafco_joined_kg_header")

    def test_vimc_mixed_layouts_preserve_units_mapping_and_rounding(self):
        self.check_case("vimc_mixed_layouts")


if __name__ == "__main__":
    unittest.main()
