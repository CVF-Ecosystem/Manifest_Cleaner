"""Shared boundary behavior: units, locales, missing values and Excel identifiers."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook
from manifest_cleaner.common import is_explicit_empty, normalize_text, parse_weight, read_workbook, text_value


class CommonTests(unittest.TestCase):
    def test_equivalent_weight_formats_produce_tonnes(self):
        for raw in ["25,000 KGS", "25 000 KG", "25\u00a0000 KGS", "25 TONS", "25 MT"]:
            with self.subTest(raw=raw):
                parsed = parse_weight(raw)
                self.assertEqual(parsed["value"], 25.0)
                self.assertEqual(parsed["unit"], "TONS")
        for raw in ["25.000,50 KGS", "25,000.50 KGS"]:
            self.assertEqual(parse_weight(raw)["value"], 25.0005)

    def test_profile_locale_disambiguates_single_separator(self):
        self.assertEqual(parse_weight("1,000", "TONS", "legacy")["value"], 1.0)
        self.assertEqual(parse_weight("1,000", "KGS", "legacy")["value"], 1.0)
        self.assertEqual(parse_weight("1.000", "KGS", "decimal_comma")["value"], 1.0)
        self.assertEqual(parse_weight("1,000", "TONS", "decimal_dot")["value"], 1000.0)
        self.assertEqual(parse_weight("1.234,56", "TONS", "decimal_comma")["value"], 1234.56)
        self.assertIsNone(parse_weight("1.234,56", "TONS", "decimal_dot"))

    def test_native_excel_numbers_do_not_change_with_locale(self):
        for value in (1250.5, Decimal("1250.5")):
            for locale in ("legacy", "decimal_comma", "decimal_dot"):
                with self.subTest(value=value, locale=locale):
                    self.assertEqual(parse_weight(value, "KGS", locale)["value"], 1.2505)

    def test_invalid_values_are_missing_not_zero(self):
        for value in (None, "", True, False, -1, "-2 KGS", "NaN", "inf", "1,2,3", "1..23", "abc", "12 LB"):
            with self.subTest(value=value):
                self.assertIsNone(parse_weight(value))
        self.assertIsNone(parse_weight("25", default_unit="LB"))
        self.assertIsNone(parse_weight("25", number_format="guess"))
        self.assertEqual(parse_weight(0)["value"], 0.0)
        self.assertEqual(parse_weight("0 KGS")["unit"], "TONS")

    def test_empty_status_is_distinct_from_goods_text(self):
        for phrase in ("EMPTY", "SOC EMPTY", "COC EMPTY", "EMPTY CONTAINER", "RỖNG", "CONTAINER RỖNG", "NO CARGO"):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_explicit_empty(phrase))
        for goods in ("EMPTY BOTTLES", "EMPTY BAGS", "NO CARGO CLAIMED BUT GOODS PRESENT", "FULL", ""):
            self.assertFalse(is_explicit_empty(goods))

    def test_text_normalization_preserves_original_values(self):
        source = "  Gạch\n men ĐỎ  "
        self.assertEqual(normalize_text(source), "GACH MEN DO")
        self.assertEqual(source, "  Gạch\n men ĐỎ  ")
        self.assertEqual(text_value("001234"), "001234")
        self.assertEqual(text_value(None), "")
        self.assertEqual(text_value(float("nan")), "")
        self.assertEqual(text_value(0), "0")

    def test_excel_reader_preserves_leading_zero_and_does_not_evaluate_formula(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identifiers.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.title = "Evidence"
            sheet["A1"] = "001234"
            sheet["B1"] = 123
            sheet["B1"].number_format = "000000"
            sheet["C1"] = 12.5
            sheet["D1"] = "=1+1"
            sheet["E1"] = "=LITERAL"
            sheet["E1"].data_type = "s"
            book.save(path)
            book.close()
            name, frame = read_workbook(path)[0]
            self.assertEqual(name, "Evidence")
            self.assertEqual(frame.iloc[0, 0], "001234")
            self.assertEqual(frame.iloc[0, 1], "000123")
            self.assertEqual(frame.iloc[0, 2], 12.5)
            self.assertEqual(frame.iloc[0, 3], "")
            self.assertEqual(frame.iloc[0, 4], "=LITERAL")
            renamed = path.with_suffix(".xls")
            path.rename(renamed)
            self.assertEqual(read_workbook(renamed)[0][1].iloc[0, 1], "000123")

    def test_non_excel_file_is_rejected_by_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.xlsx"
            path.write_text("not a workbook", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_workbook(path)


if __name__ == "__main__":
    unittest.main()
