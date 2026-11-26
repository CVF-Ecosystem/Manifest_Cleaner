"""Roadmap MC3: one TOS export form for every carrier, and the separate B/L change.

All inputs are synthetic. The review sessions under fixtures/review_v2_16col were
saved by version 1.1.0, when each carrier had its own 16-column layout.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

import xlsxwriter
from openpyxl import Workbook, load_workbook

from manifest_cleaner import bl_change, exporter, gui
from manifest_cleaner.engine import load_review, load_settings, process_manifest
from scripts.create_samples import CREATORS
from tests.test_integration import EXPECTED_TOS

LEGACY = Path(__file__).parent / "fixtures" / "review_v2_16col"
GREEN, YELLOW = "E2EFDA", "FFFF00"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fill_of(cell):
    return cell.fill.fgColor.rgb[-6:] if cell.fill and cell.fill.fill_type == "solid" else None


def write_tos(path, rows, carrier="TEST"):
    """A TOS file laid out as step one writes it; rows are dicts of TOS header -> value."""
    with xlsxwriter.Workbook(path) as book:
        book.set_custom_property("carrier", carrier)
        book.set_custom_property("source_name", f"{carrier}.xlsx")
        exporter._write_tos_sheet(book, [[row.get(name) for name in EXPECTED_TOS] for row in rows],
                                  [(None, {})] * len(rows), "General")
    return path


def tos(container, bl, **values):
    row = {"Số lượng": 1, "Số BL": bl, "Số Container": container, "Hãng khai thác": "VOC", "Kích cỡ": "40HC",
           "Kích cỡ ISO": "45G0", "F/E": "F", "TL hàng": 20, "Số niêm chì": "001", "Số niêm chì 1": "001",
           "Chủ hàng": "OWNER", "Loại hàng": "GP", "Loại hàng ": "General", "Hàng hóa": "GOODS"}
    row.update(values)
    return row


class TosFormTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_cargo_names_use_tos_spelling_and_unknown_codes_stay_blank(self):
        self.assertEqual(exporter.tos_cargo("GENERAL"), ("GP", "General"))
        self.assertEqual(exporter.tos_cargo("empty reefer"), ("ER", "Empty Reefer"))
        self.assertEqual(exporter.tos_cargo("EMPTY TANK"), ("ET", "EMPTY TANK"))
        self.assertEqual(exporter.tos_cargo("REEFER"), ("", "REEFER"))
        self.assertEqual(exporter.tos_cargo(None), ("", ""))

    def test_size_is_vtos_and_iso_only_for_codes_seen_in_the_tos_form(self):
        session = process_manifest(CREATORS["VOSCO"](self.root / "vosco.xlsx"), "VOSCO")
        record = session.records[0]
        session.update_record(record["record_id"], {"Size_Type": "20RF", "FE_Status": "E", "Weight_Value": 3},
                              "Đối chiếu container rỗng lạnh")
        preview = exporter.preview_record_for_export(session, record)
        self.assertEqual(preview["Kích cỡ"], record["VTOS_Size"])
        self.assertNotIn(preview["Kích cỡ"], exporter.VTOS_TO_TOS_ISO)
        self.assertEqual(preview["Kích cỡ ISO"], "")
        self.assertEqual((preview["Loại hàng"], preview["Loại hàng "]), ("ER", "Empty Reefer"))

    def test_review_v2_saved_by_the_16_column_build_reopens_and_exports_the_tos_form(self):
        for carrier in ("VOSCO", "VIMC", "VINAFCO"):
            with self.subTest(carrier=carrier):
                saved = LEGACY / f"DEMO_{carrier}_REVIEW.json"
                self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["app_version"], "1.1.0")
                before = sha(saved)
                session = load_review(saved, source_path=LEGACY / f"DEMO_{carrier}_INPUT.xlsx")
                result = exporter.export_port_bundle(session, self.root / f"{carrier}.xlsx")
                book = load_workbook(result["excel"])
                try:
                    sheet = book.active
                    self.assertEqual([cell.value for cell in sheet[1]], EXPECTED_TOS)
                    row = dict(zip(EXPECTED_TOS, (cell.value for cell in sheet[2])))
                    record = session.active_records()[0]
                    self.assertEqual(row["Số Container"], record["Container_No"])
                    self.assertEqual(row["Số BL"], record["BL_No"])
                    self.assertEqual(row["Kích cỡ"], record["VTOS_Size"])
                    self.assertIsNone(row["Ghi chú"])
                finally:
                    book.close()
                self.assertEqual(sha(saved), before)
                load_review(result["review"], source_path=LEGACY / f"DEMO_{carrier}_INPUT.xlsx")


class BlChangeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def exported_pair(self):
        """A VOSCO vessel file and a VIMC file for the same container, both from step one."""
        vessel_session = process_manifest(CREATORS["VOSCO"](self.root / "vosco_in.xlsx"), "VOSCO")
        vessel = exporter.export_port_excel(vessel_session, self.root / "vessel.xlsx")
        partner_session = process_manifest(CREATORS["VIMC"](self.root / "vimc_in.xlsx"), "VIMC")
        container = vessel_session.records[0]["Container_No"]
        partner_session.update_record(partner_session.records[0]["record_id"], {"Container_No": container},
                                      "Cùng container trên tàu VOSCO")
        partner = exporter.export_port_excel(partner_session, self.root / "partner.xlsx")
        return vessel, partner, vessel_session

    def test_six_fields_come_from_the_shipping_line_and_differences_keep_the_vessel_value(self):
        vessel_path, partner_path, vessel_session = self.exported_pair()
        sources = {path: sha(path) for path in (vessel_path, partner_path)}
        vessel, partner = bl_change.read_tos_file(vessel_path), bl_change.read_tos_file(partner_path)
        self.assertEqual((vessel.carrier, partner.carrier), ("VOSCO", "VIMC"))
        plan = bl_change.plan_bl_change(vessel, partner)
        change, = plan["changes"]
        self.assertEqual(set(change["fields"]), {"Số BL", "Hãng khai thác", "TL hàng", "Hàng hóa"})
        self.assertEqual(change["fields"]["Số BL"], {"old": "VOSCO900001", "new": "DEMO-VIMC-001"})
        self.assertEqual({item["field"] for item in plan["conflicts"]}, {"Kích cỡ", "Số niêm chì", "Số niêm chì 1"})
        result = bl_change.write_bl_change(vessel, partner, plan, self.root / "changed.xlsx")
        book = load_workbook(result["excel"])
        try:
            sheet = book.active
            self.assertEqual([cell.value for cell in sheet[1]], EXPECTED_TOS)
            row = {name: sheet.cell(2, index + 1) for index, name in enumerate(EXPECTED_TOS)}
            self.assertEqual(row["Số BL"].value, "DEMO-VIMC-001")
            self.assertEqual(row["Hãng khai thác"].value, "VMC")
            self.assertEqual(row["TL hàng"].value, 16.06)
            self.assertEqual(row["TL hàng"].data_type, "n")
            self.assertEqual(row["Hàng hóa"].value, "THEP DEMO")
            self.assertEqual(row["Kích cỡ"].value, "40HC")
            self.assertEqual(row["Số niêm chì"].value, "001234")
            for name in ("Số BL", "Hãng khai thác", "TL hàng", "Hàng hóa"):
                self.assertEqual(fill_of(row[name]), GREEN, name)
            for name in ("Kích cỡ", "Số niêm chì", "Số niêm chì 1"):
                self.assertEqual(fill_of(row[name]), YELLOW, name)
            self.assertIsNone(fill_of(row["Chủ hàng"]))
            properties = {prop.name: prop.value for prop in book.custom_doc_props.props}
            self.assertEqual(properties["session_id"], vessel_session.metadata["session_id"])
            self.assertEqual(properties["bl_change_partner_sha256"], partner.sha256)
        finally:
            book.close()
        trace = json.loads(result["trace"].read_text(encoding="utf-8"))
        self.assertEqual(trace["vessel"]["sha256"], sources[vessel_path])
        self.assertEqual(trace["partner"]["sha256"], sources[partner_path])
        self.assertEqual(trace["output"]["sha256"], sha(result["excel"]))
        self.assertEqual(trace["changes"][0]["fields"]["Hãng khai thác"], {"old": "VOC", "new": "VMC"})
        self.assertEqual({path: sha(path) for path in sources}, sources)

    def test_blank_values_partial_bls_and_containers_not_on_the_vessel_are_reported(self):
        vessel = write_tos(self.root / "vessel.xlsx", [tos("AAAU0000001", "VOS1", **{"TL hàng": 30}),
                                                       tos("AAAU0000002", "VOS1")])
        partner = write_tos(self.root / "partner.xlsx", [
            tos("AAAU0000001", "VIM1", **{"TL hàng": None, "Hãng khai thác": "VMC", "Chủ hàng": "REAL OWNER"}),
            tos("BBBU0000009", "VIM2")])
        plan = bl_change.plan_bl_change(bl_change.read_tos_file(vessel), bl_change.read_tos_file(partner))
        change, = plan["changes"]
        self.assertNotIn("TL hàng", change["fields"])
        self.assertEqual(plan["kept_vessel_value_when_partner_blank"],
                         [{"container": "AAAU0000001", "field": "TL hàng", "vessel": 30}])
        self.assertEqual(plan["partner_only"], ["BBBU0000009"])
        self.assertEqual(plan["partial_bls"], [{"bl": "VOS1", "total": 2, "matched": 1, "remaining": ["AAAU0000002"]}])
        self.assertEqual(plan["summary"]["matched"], 1)

    def test_wrong_inputs_stop_before_anything_is_written(self):
        vessel = write_tos(self.root / "vessel.xlsx", [tos("AAAU0000001", "VOS1")])
        other = write_tos(self.root / "other.xlsx", [tos("CCCU0000003", "VIM1")])
        duplicate = write_tos(self.root / "duplicate.xlsx", [tos("AAAU0000001", "A"), tos("aaau0000001 ", "B")])
        legacy = self.root / "legacy.xlsx"
        book = Workbook()
        book.active.append(["STT", "Số Vận Đơn", "Số Container"])
        book.active.append([1, "BL", "AAAU0000001"])
        book.save(legacy)
        with self.assertRaisesRegex(ValueError, "mẫu TOS"):
            bl_change.read_tos_file(legacy)
        with self.assertRaisesRegex(ValueError, "trùng"):
            bl_change.read_tos_file(duplicate)
        item = bl_change.read_tos_file(vessel)
        with self.assertRaisesRegex(ValueError, "cùng một file"):
            bl_change.plan_bl_change(item, bl_change.read_tos_file(vessel))
        with self.assertRaisesRegex(ValueError, "không có container chung"):
            bl_change.plan_bl_change(item, bl_change.read_tos_file(other))
        partner_path = write_tos(self.root / "partner.xlsx", [tos("AAAU0000001", "VIM1")])
        partner = bl_change.read_tos_file(partner_path)
        plan = bl_change.plan_bl_change(item, partner)
        with self.assertRaisesRegex(ValueError, "hai file nguồn"):
            bl_change.write_bl_change(item, partner, plan, vessel)
        target = self.root / "out.xlsx"
        target.write_bytes(b"previous")
        with self.assertRaises(FileExistsError):
            bl_change.write_bl_change(item, partner, plan, target)
        self.assertEqual(target.read_bytes(), b"previous")
        write_tos(partner_path, [tos("AAAU0000001", "VIM9")])
        with self.assertRaisesRegex(ValueError, "đã thay đổi"):
            bl_change.write_bl_change(item, partner, plan, self.root / "new.xlsx")
        self.assertFalse((self.root / "new.xlsx").exists())


@unittest.skipUnless(sys.platform == "win32", "Windows Tk")
class BlChangeTabTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    @contextmanager
    def live_app(self, scale=1.25):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        try:
            root.tk.call("tk", "scaling", 96 / 72 * scale)
            recent = self.root / gui.RECENT_FILE
            with patch.object(gui, "load_settings", side_effect=lambda *_: load_settings()), \
                    patch.object(gui, "_recent_file_path", return_value=recent):
                yield gui.ManifestApp(root)
        finally:
            for callback in root.tk.splitlist(root.tk.call("after", "info")):
                root.after_cancel(callback)
            root.destroy()

    def test_file_choice_and_export_stay_visible_at_the_minimum_window_size(self):
        # Review finding 26-11-2026: the first layout hid the export button at the minimum size.
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale), self.live_app(scale) as app:
                root = app.root
                width, height = root.minsize()
                root.geometry(f"{width}x{height}")
                app.tabs.select(2)
                app.bl_summary.set("36 container chung, 36 container đổi giá trị. 0 khác biệt, "
                                   "0 container không có trên tàu, 0 B/L gom còn sót.")
                root.update()
                choosers = [widget for widget in app.bl_tab.winfo_children()[0].winfo_children()
                            if isinstance(widget, tk.ttk.Entry) or str(widget.cget("text")) == "Chọn…"
                            if isinstance(widget, (tk.ttk.Button, tk.ttk.Entry))]
                self.assertEqual(len(choosers), 4)
                for widget in (app.bl_export_button, app.bl_guide_button, *choosers):
                    self.assertTrue(widget.winfo_viewable(), str(widget))
                    self.assertGreater(widget.winfo_height(), 10, str(widget))
                    right = widget.winfo_rootx() - root.winfo_rootx() + widget.winfo_width()
                    bottom = widget.winfo_rooty() - root.winfo_rooty() + widget.winfo_height()
                    self.assertLessEqual(right, root.winfo_width(), str(widget))
                    self.assertLessEqual(bottom, root.winfo_height(), str(widget))

    def test_tab_works_without_a_session_and_writes_the_changed_file(self):
        vessel = write_tos(self.root / "vessel.xlsx", [tos("AAAU0000001", "VOS1"), tos("AAAU0000002", "VOS2")],
                           carrier="VOSCO")
        partner = write_tos(self.root / "partner.xlsx", [tos("AAAU0000001", "VIM1", **{"Hãng khai thác": "VMC"})],
                            carrier="VIMC")
        target = self.root / "vessel_DOI_BL.xlsx"
        with self.live_app() as app:
            self.assertEqual([app.tabs.tab(tab, "text") for tab in app.tabs.tabs()],
                             ["Container", "Cần kiểm tra", "Đổi B/L"])
            app.tabs.select(2)
            app.root.update()
            self.assertIsNone(app.session)
            self.assertEqual(str(app.bl_export_button.cget("state")), "disabled")
            choosers = [widget for widget in app.bl_tab.winfo_children()[0].winfo_children()
                        if isinstance(widget, tk.ttk.Button) and str(widget.cget("text")) == "Chọn…"]
            self.assertEqual(len(choosers), 2)
            with patch.object(gui.filedialog, "askopenfilename", side_effect=[str(vessel), str(partner)]):
                for button in choosers:
                    button.invoke()
            self.assertIn("1 container chung, 1 container đổi giá trị", app.bl_summary.get())
            self.assertEqual(str(app.bl_export_button.cget("state")), "normal")
            self.assertEqual(len(app.bl_tree.get_children()), 1)
            with patch.object(gui.filedialog, "asksaveasfilename", return_value=str(target)), \
                    patch.object(gui.messagebox, "showinfo") as shown:
                app.bl_export_button.invoke()
            shown.assert_called_once()
        book = load_workbook(target)
        try:
            sheet = book.active
            self.assertEqual((sheet["D2"].value, sheet["F2"].value, sheet["D3"].value), ("VIM1", "VMC", "VOS2"))
        finally:
            book.close()
        self.assertTrue(target.with_suffix(".bl_change.json").is_file())

    def test_a_raw_manifest_is_listed_and_the_user_is_told_to_export_it_first(self):
        raw = self.root / "MNF FF2643S_VIMC.xls"
        raw.write_bytes(b"not read: the extension already says it is a raw manifest")
        legacy = self.root / "BILL GOC VMC.xlsx"
        book = Workbook()
        book.active.append(["STT", "Số Vận Đơn", "Số Container"])
        book.save(legacy)
        with self.live_app() as app:
            app.tabs.select(2)
            app.root.update()
            partner = [widget for widget in app.bl_tab.winfo_children()[0].winfo_children()
                       if isinstance(widget, tk.ttk.Button) and str(widget.cget("text")) == "Chọn…"][1]
            for chosen in (raw, legacy):
                with self.subTest(chosen=chosen.name),                         patch.object(gui.filedialog, "askopenfilename", return_value=str(chosen)) as ask,                         patch.object(gui.messagebox, "showwarning") as warned:
                    partner.invoke()
                patterns = dict(ask.call_args.kwargs["filetypes"])["Excel"].split()
                self.assertIn("*.xls", patterns)
                title, message = warned.call_args.args
                self.assertEqual(title, "Chưa phải file đã xuất")
                for expected in (chosen.name, "B2", "Mở manifest…", "Xuất file Manifest…"):
                    self.assertIn(expected, message)
            self.assertIsNone(app.bl_state["partner"])
            self.assertIn("B1", gui.BL_CHANGE_GUIDE)
            self.assertIn("_DOI_BL", gui.BL_CHANGE_GUIDE)
            with patch.object(gui.messagebox, "showinfo") as shown:
                app.bl_guide_button.invoke()
            self.assertEqual(shown.call_args.args, ("Hướng dẫn Đổi B/L", gui.BL_CHANGE_GUIDE))


if __name__ == "__main__":
    unittest.main()
