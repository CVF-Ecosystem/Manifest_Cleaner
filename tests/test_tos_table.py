"""The export is the Port's TOS import template: one Excel Table named Sheet1, 46 headers plus a blank Column1.

All inputs are synthetic. The table facts below come from the operator's template
(roadmap MC3, decision 2026-11-26); tests read the package XML directly so they do
not depend on how openpyxl or the exporter describe the table.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import xlsxwriter
from openpyxl import Workbook, load_workbook
from openpyxl.packaging.custom import StringProperty

from manifest_cleaner import bl_change, exporter
from manifest_cleaner.carriers import TOS_COLUMNS, TOS_EXPORT_COLUMNS, TOS_EXTRA_COLUMN, TOS_FIXED_VALUES
from manifest_cleaner.engine import process_manifest
from scripts.create_samples import CREATORS
from tests.test_integration import EXPECTED_TOS, EXPECTED_TOS_EXPORT, FILLED, FIXED
from tests.test_tos_bl_change import tos, write_tos

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def package_xml(path, name):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read(name))


def table_names(path):
    with zipfile.ZipFile(path) as archive:
        return sorted(name for name in archive.namelist() if name.startswith("xl/tables/"))


def assert_template_table(test, path, data_rows, *, last_column="AU"):
    """Exactly one table with the template's name, style, reference and 47 columns."""
    test.assertEqual(table_names(path), ["xl/tables/table1.xml"])
    table = package_xml(path, "xl/tables/table1.xml")
    test.assertEqual(table.get("name"), "Sheet1")
    test.assertEqual(table.get("displayName"), "Sheet1")
    test.assertEqual(table.get("ref"), f"A1:{last_column}{data_rows + 1}")
    test.assertEqual(table.get("totalsRowShown"), "0")
    style = table.find("m:tableStyleInfo", NS)
    test.assertEqual(style.get("name"), "TableStyleMedium2")
    test.assertEqual(style.get("showRowStripes"), "1")
    for flag in ("showFirstColumn", "showLastColumn", "showColumnStripes"):
        test.assertEqual(style.get(flag), "0", flag)
    names = [column.get("name") for column in table.find("m:tableColumns", NS)]
    test.assertEqual(len(names), 47)
    test.assertEqual(names, list(EXPECTED_TOS_EXPORT))
    test.assertEqual(names[-1], "Column1")
    return table


class TableFormTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_export_headers_are_the_46_tos_headers_plus_column1(self):
        self.assertEqual(TOS_EXTRA_COLUMN, "Column1")
        self.assertEqual(TOS_EXPORT_COLUMNS, TOS_COLUMNS + ("Column1",))
        self.assertEqual(len(TOS_COLUMNS), 46)
        self.assertEqual(list(TOS_COLUMNS), EXPECTED_TOS)
        self.assertEqual(exporter.EXPORT_FORM, "TOS_TEMPLATE47")

    def test_each_carrier_exports_one_template_table_without_a_worksheet_autofilter(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = process_manifest(CREATORS[carrier](self.root / f"{carrier}_in.xlsx"), carrier)
                path = exporter.export_port_excel(session, self.root / f"{carrier}.xlsx")
                assert_template_table(self, path, len(session.active_records()))
                sheet = package_xml(path, "xl/worksheets/sheet1.xml")
                self.assertEqual(sheet.findall("m:autoFilter", NS), [])
                self.assertEqual(len(sheet.findall("m:tableParts/m:tablePart", NS)), 1)
                pane = sheet.find("m:sheetViews/m:sheetView/m:pane", NS)
                self.assertEqual((pane.get("ySplit"), pane.get("xSplit")), ("1", None))
                with zipfile.ZipFile(path) as archive:
                    self.assertNotIn("_xlnm._FilterDatabase", archive.read("xl/workbook.xml").decode("utf-8"))
                last = sheet.findall("m:cols/m:col", NS)[-1]
                self.assertEqual((last.get("min"), last.get("max")), ("47", "47"))
                self.assertLess(float(last.get("width")), 1)

    def test_values_types_and_blank_columns_are_unchanged(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                session = process_manifest(CREATORS[carrier](self.root / f"{carrier}_in.xlsx"), carrier)
                path = exporter.export_port_excel(session, self.root / f"{carrier}.xlsx")
                book = load_workbook(path)
                try:
                    sheet = book[exporter.SHEET_NAME]
                    self.assertEqual([cell.value for cell in sheet[1]], EXPECTED_TOS_EXPORT)
                    self.assertEqual(sheet.max_column, 47)
                    self.assertEqual(sheet.freeze_panes, "A2")
                    self.assertIsNone(sheet.auto_filter.ref)
                    self.assertEqual(sheet.tables["Sheet1"].ref, f"A1:AU{sheet.max_row}")
                    for index, record in enumerate(session.active_records(), 2):
                        row = {name: sheet.cell(index, number) for number, name in enumerate(EXPECTED_TOS_EXPORT, 1)}
                        for name in EXPECTED_TOS_EXPORT:
                            self.assertEqual(row[name].value is not None, name in FILLED | set(FIXED), name)
                        self.assertIsNone(row["Column1"].value)
                        for name in ("Số lượng", "TL hàng"):
                            self.assertEqual(row[name].data_type, "n", name)
                        for name in (FILLED - {"Số lượng", "TL hàng"}) | set(FIXED):
                            self.assertEqual(row[name].data_type, "s", name)
                        self.assertEqual(row["Số Container"].value, record["Container_No"])
                        self.assertEqual(row["Số BL"].value, record["BL_No"])
                finally:
                    book.close()

    def test_a_table_without_rows_still_has_a_header_and_one_empty_data_row(self):
        # export_port_excel refuses a session with no active record, so the writer is tested directly.
        for rows in ([], [[None] * 46]):
            with self.subTest(rows=len(rows)):
                path = self.root / f"empty_{len(rows)}.xlsx"
                with xlsxwriter.Workbook(path) as book:
                    exporter._write_tos_sheet(book, rows, [(None, {})] * len(rows), "General")
                assert_template_table(self, path, 1)
                book = load_workbook(path)
                try:
                    sheet = book.active
                    self.assertEqual([cell.value for cell in sheet[1]], EXPECTED_TOS_EXPORT)
                    self.assertEqual(sheet.tables["Sheet1"].ref, "A1:AU2")
                    self.assertTrue(all(cell.value is None for cell in sheet[2]))
                finally:
                    book.close()

    def test_the_writer_accepts_rows_of_46_or_47_values(self):
        row = tos("AAAU0000001", "BL1")
        short = [row.get(name) for name in EXPECTED_TOS]
        path = self.root / "mixed.xlsx"
        with xlsxwriter.Workbook(path) as book:
            exporter._write_tos_sheet(book, [short, short + [None]], [(None, {})] * 2, "General")
        assert_template_table(self, path, 2)
        book = load_workbook(path)
        try:
            sheet = book.active
            self.assertEqual([cell.value for cell in sheet[2]], [cell.value for cell in sheet[3]])
            self.assertEqual(sheet["E2"].value, "AAAU0000001")
        finally:
            book.close()


class FixedValueTests(unittest.TestCase):
    """Operator decision 2026-11-26: six fixed text values on every data row of every carrier."""

    BLANK = ("Hàng nội/ngoại", "Cntr Class", "Column1")

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def sheet_rows(self, path):
        book = load_workbook(path)
        self.addCleanup(book.close)
        sheet = book[exporter.SHEET_NAME]
        headers = [cell.value for cell in sheet[1]]
        return headers, [dict(zip(headers, row)) for row in sheet.iter_rows(min_row=2)]

    def test_the_fixed_values_are_exactly_the_decided_six(self):
        self.assertEqual(dict(TOS_FIXED_VALUES), FIXED)
        self.assertEqual(len(FIXED), 6)
        self.assertTrue(all(name in TOS_COLUMNS for name in FIXED))
        self.assertTrue(all(value == value.upper() for value in FIXED.values()))

    def test_every_data_row_of_every_carrier_has_the_fixed_text_cells(self):
        for carrier in CREATORS:
            with self.subTest(carrier=carrier):
                if carrier == "VIMC":
                    source = CREATORS[carrier](self.root / f"{carrier}_in.xlsx",
                                               extra_lines=("DEMU0000004 001237 40HC 25 THEP",))
                else:
                    source = CREATORS[carrier](self.root / f"{carrier}_in.xlsx")
                session = process_manifest(source, carrier)
                path = exporter.export_port_excel(session, self.root / f"{carrier}.xlsx")
                book = load_workbook(path)
                self.addCleanup(book.close)
                sheet = book[exporter.SHEET_NAME]
                headers = [cell.value for cell in sheet[1]]
                self.assertEqual(sheet.max_row - 1, len(session.active_records()))
                for cells in sheet.iter_rows(min_row=2):
                    row = dict(zip(headers, cells))
                    for name, expected in FIXED.items():
                        self.assertEqual(row[name].value, expected, name)
                        self.assertEqual(row[name].data_type, "s", name)
                        self.assertEqual(row[name].value, row[name].value.upper(), name)
                    for name in self.BLANK:
                        self.assertIsNone(row[name].value, name)
                    self.assertEqual(row["Số lượng"].data_type, "n")

    def test_the_app_view_and_preview_keep_their_16_columns(self):
        session = process_manifest(CREATORS["VIMC"](self.root / "in.xlsx"), "VIMC")
        columns, rows = exporter.build_port_rows(session)
        self.assertEqual(len(columns), 16)
        self.assertFalse(set(FIXED) & set(columns))
        self.assertEqual(list(exporter.preview_record_for_export(session, session.records[0])), list(columns))
        self.assertTrue(all(len(row) == 16 for row in rows))

    def test_the_empty_placeholder_row_stays_blank(self):
        path = self.root / "empty.xlsx"
        with xlsxwriter.Workbook(path) as book:
            exporter._write_tos_sheet(book, [], [], "General")
        assert_template_table(self, path, 1)
        book = load_workbook(path)
        self.addCleanup(book.close)
        self.assertTrue(all(cell.value is None for cell in book.active[2]))

    def test_the_writer_adds_nothing_to_hand_made_rows(self):
        path = write_tos(self.root / "plain.xlsx", [tos("AAAU0000001", "BL1")])
        _, rows = self.sheet_rows(path)
        self.assertTrue(all(rows[0][name].value is None for name in FIXED))

    def test_bl_change_keeps_the_fixed_values_and_does_not_compare_them(self):
        vessel_session = process_manifest(CREATORS["VOSCO"](self.root / "vosco_in.xlsx"), "VOSCO")
        vessel_path = exporter.export_port_excel(vessel_session, self.root / "vessel.xlsx")
        partner_session = process_manifest(CREATORS["VIMC"](self.root / "vimc_in.xlsx"), "VIMC")
        partner_session.update_record(partner_session.records[0]["record_id"],
                                      {"Container_No": vessel_session.records[0]["Container_No"]},
                                      "Cùng container trên tàu VOSCO")
        partner_path = exporter.export_port_excel(partner_session, self.root / "partner.xlsx")
        vessel, partner = bl_change.read_tos_file(vessel_path), bl_change.read_tos_file(partner_path)
        plan = bl_change.plan_bl_change(vessel, partner)
        self.assertTrue(plan["changes"])
        touched = {name for change in plan["changes"] for name in change["fields"]}
        touched |= {item["field"] for item in plan["conflicts"]}
        self.assertFalse(touched & set(FIXED))
        result = bl_change.write_bl_change(vessel, partner, plan, self.root / "changed.xlsx")
        _, rows = self.sheet_rows(result["excel"])
        self.assertEqual(len(rows), len(vessel_session.active_records()))
        for row in rows:
            for name, expected in FIXED.items():
                self.assertEqual((row[name].value, row[name].data_type), (expected, "s"), name)
            for name in self.BLANK:
                self.assertIsNone(row[name].value, name)


class BlChangeLayoutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def plain_file(self, name, rows, headers, *, carrier="TEST", extra=None):
        """A file without the Excel Table: the layout of earlier exports (46 columns) or variants."""
        path = self.root / name
        book = Workbook()
        book.active.append(list(headers))
        for row in rows:
            values = [row.get(header) for header in EXPECTED_TOS] + list(extra or [])
            book.active.append(values)
        book.custom_doc_props.append(StringProperty(name="carrier", value=carrier))
        book.save(path)
        return path

    def test_a_46_column_file_and_a_47_column_file_are_both_accepted(self):
        old = self.plain_file("old46.xlsx", [tos("AAAU0000001", "VOS1")], EXPECTED_TOS, carrier="VOSCO")
        new = write_tos(self.root / "new47.xlsx", [tos("AAAU0000001", "VIM1", **{"Hãng khai thác": "VMC"})],
                        carrier="VIMC")
        assert_template_table(self, new, 1)
        vessel, partner = bl_change.read_tos_file(old), bl_change.read_tos_file(new)
        self.assertEqual((vessel.carrier, partner.carrier), ("VOSCO", "VIMC"))
        self.assertEqual(list(partner.rows["AAAU0000001"]["values"]), list(EXPECTED_TOS))
        plan = bl_change.plan_bl_change(vessel, partner)
        self.assertEqual(plan["changes"][0]["fields"]["Số BL"], {"old": "VOS1", "new": "VIM1"})

    def test_column1_data_is_ignored(self):
        path = self.plain_file("junk.xlsx", [tos("AAAU0000001", "VOS1")], EXPECTED_TOS_EXPORT, extra=["leftover"])
        item = bl_change.read_tos_file(path)
        self.assertNotIn("Column1", item.rows["AAAU0000001"]["values"])
        self.assertEqual(item.rows["AAAU0000001"]["values"]["Số BL"], "VOS1")

    def test_trailing_blank_header_cells_are_still_tolerated(self):
        for headers in (list(EXPECTED_TOS) + [None, None], list(EXPECTED_TOS_EXPORT) + [None, ""]):
            with self.subTest(width=len(headers)):
                path = self.plain_file(f"blank{len(headers)}.xlsx", [tos("AAAU0000001", "VOS1")], headers)
                self.assertIn("AAAU0000001", bl_change.read_tos_file(path).rows)

    def test_any_other_header_layout_is_refused(self):
        rows = [tos("AAAU0000001", "VOS1")]
        cases = {"unknown extra": list(EXPECTED_TOS) + ["Column2"],
                 "extra after column1": list(EXPECTED_TOS_EXPORT) + ["Column2"],
                 "renamed 47th": list(EXPECTED_TOS) + ["Cột thừa"],
                 "missing header": EXPECTED_TOS[:-1],
                 "trailing space lost": [name.strip() for name in EXPECTED_TOS]}
        for number, (label, headers) in enumerate(cases.items()):
            with self.subTest(case=label):
                path = self.plain_file(f"bad_{number}.xlsx", rows, headers)
                with self.assertRaises(bl_change.NotExportedError):
                    bl_change.read_tos_file(path)

    def test_the_changed_file_keeps_the_table_47_columns_and_the_reference(self):
        vessel_path = write_tos(self.root / "vessel.xlsx", [tos("AAAU0000001", "VOS1"), tos("AAAU0000002", "VOS2"),
                                                            tos("AAAU0000003", "VOS3")], carrier="VOSCO")
        partner_path = write_tos(self.root / "partner.xlsx", [tos("AAAU0000001", "VIM1"), tos("AAAU0000003", "VIM3")],
                                 carrier="VIMC")
        assert_template_table(self, vessel_path, 3)
        vessel, partner = bl_change.read_tos_file(vessel_path), bl_change.read_tos_file(partner_path)
        plan = bl_change.plan_bl_change(vessel, partner)
        result = bl_change.write_bl_change(vessel, partner, plan, self.root / "changed.xlsx")
        table = assert_template_table(self, result["excel"], 3)
        self.assertEqual(table.find("m:tableStyleInfo", NS).get("name"), "TableStyleMedium2")
        book = load_workbook(result["excel"])
        try:
            sheet = book.active
            self.assertEqual(sheet.title, "Sheet1")
            self.assertEqual([cell.value for cell in sheet[1]], EXPECTED_TOS_EXPORT)
            self.assertEqual([sheet.cell(row, 4).value for row in (2, 3, 4)], ["VIM1", "VOS2", "VIM3"])
            self.assertEqual(sheet.tables["Sheet1"].ref, "A1:AU4")
            self.assertIsNone(sheet.auto_filter.ref)
        finally:
            book.close()
        xml = package_xml(result["excel"], "xl/worksheets/sheet1.xml")
        self.assertEqual(xml.findall("m:autoFilter", NS), [])

    def test_a_46_column_vessel_file_is_changed_without_adding_a_table(self):
        old = self.plain_file("old46.xlsx", [tos("AAAU0000001", "VOS1")], EXPECTED_TOS, carrier="VOSCO")
        partner_path = write_tos(self.root / "partner.xlsx", [tos("AAAU0000001", "VIM1")], carrier="VIMC")
        vessel, partner = bl_change.read_tos_file(old), bl_change.read_tos_file(partner_path)
        result = bl_change.write_bl_change(vessel, partner, bl_change.plan_bl_change(vessel, partner),
                                           self.root / "changed46.xlsx")
        self.assertEqual(table_names(result["excel"]), [])
        book = load_workbook(result["excel"])
        try:
            self.assertEqual(book.active["D2"].value, "VIM1")
            self.assertEqual(book.active.max_column, 46)
        finally:
            book.close()


if __name__ == "__main__":
    unittest.main()
