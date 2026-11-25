"""Regression tests for real GUI callbacks without a display server.

Fake widgets replace rendering only; session validation, file IO, source hash
checks, carrier parsing and GUI save/action callbacks remain real.
"""
from __future__ import annotations

import ast
import copy
import csv
import io
import json
import shutil
from contextlib import ExitStack, contextmanager
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from openpyxl import load_workbook

from manifest_cleaner import gui
from manifest_cleaner.engine import EDITABLE_FIELDS, load_review, load_settings, process_manifest
from manifest_cleaner.exporter import build_port_rows, export_port_bundle
from manifest_cleaner.issue_display import ISSUE_TITLES, issue_location, issue_title
from scripts.create_samples import create_vimc, create_vinafco


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def trace_add(self, *args):
        return None


class Widget:
    def __init__(self, *args, **kwargs):
        self.options = kwargs
        self.rows = {}
        self.parents = {}
        self.properties = {}
        self.selected = ()

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get_children(self, parent=""):
        return tuple(row for row in self.rows if self.parents[row] == parent)

    def winfo_fpixels(self, _):
        return 96

    def delete(self, *items):
        for item in items:
            self.delete(*self.get_children(item))
            self.rows.pop(item, None)
            self.parents.pop(item, None)
            self.properties.pop(item, None)
        self.selected = tuple(item for item in self.selected if item in self.rows)

    def insert(self, parent, _index, *, iid=None, values=(), tags=(), **kwargs):
        iid = iid or f"row-{len(self.rows)}"
        self.rows[iid] = values
        self.parents[iid] = parent
        self.properties[iid] = dict(kwargs, values=values, tags=tags)
        return iid

    def parent(self, row):
        return self.parents[row]

    def item(self, iid, option=None):
        data = self.properties[iid]
        return data.get(option) if option else data

    def selection(self):
        return self.selected

    def selection_set(self, *items):
        self.selected = tuple(items)

    def exists(self, item):
        return item in self.rows

    def index(self, _value):
        return 0


@contextmanager
def fake_dialog():
    strings, bools, buttons, widgets = [], [], {}, []

    class String(Variable):
        def __init__(self, value=""):
            super().__init__(value)
            strings.append(self)

    class Boolean(Variable):
        def __init__(self, value=False):
            super().__init__(value)
            bools.append(self)

    class RenderWidget(Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            widgets.append(self)
            if "command" in kwargs:
                buttons[kwargs.get("text")] = kwargs["command"]

    with ExitStack() as stack:
        stack.enter_context(patch.multiple(gui.tk, Toplevel=RenderWidget, StringVar=String, BooleanVar=Boolean,
                                           Text=RenderWidget, Canvas=RenderWidget))
        stack.enter_context(patch.object(gui, "_monitor_work_area", return_value=(0, 0, 1000, 700)))
        stack.enter_context(patch.object(gui.tkfont, "Font",
                                         return_value=SimpleNamespace(measure=lambda text: len(text) * 7)))
        stack.enter_context(patch.multiple(gui.ttk, **{name: RenderWidget for name in
            ("Frame", "Label", "Entry", "Combobox", "Button", "Checkbutton", "Notebook", "Treeview", "Scrollbar")}))
        info = stack.enter_context(patch.object(gui.messagebox, "showinfo"))
        error = stack.enter_context(patch.object(gui.messagebox, "showerror"))
        stack.enter_context(patch.object(gui.messagebox, "showwarning"))
        yield SimpleNamespace(strings=strings, bools=bools, buttons=buttons, widgets=widgets, info=info, error=error)


class GUIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def session(self, *, extra_lines=(), weight=16.055, description="STEEL DEMO", status="COC LADEN"):
        path = create_vimc(self.folder / "input.xlsx", extra_lines=extra_lines, weight=weight, description=description)
        if status != "COC LADEN":
            book = load_workbook(path)
            book.active["D3"] = status
            book.save(path)
            book.close()
        return process_manifest(path, "VIMC")

    def app(self, session):
        app = gui.ManifestApp.__new__(gui.ManifestApp)
        app.root = Widget()
        app.session = session
        app.settings = load_settings()
        app.settings[session.carrier] = copy.deepcopy(session.settings)
        app.selected_path = Path(session.metadata["source_path"])
        app.config_path = self.folder / "settings.json"
        app.recent_path = self.folder / gui.RECENT_FILE
        app.recent = []
        app.busy = False
        app.dirty = False
        app.carrier = Variable(session.carrier)
        app.search = Variable("")
        app.only_issues = Variable(False)
        app.show_excluded = Variable(False)
        app.include_review = Variable(True)
        app.status = Variable()
        app.file_label = Variable()
        app.summary = Variable()
        app.configuration = Variable()
        app.filter_status = Variable()
        app.export_hint = Variable()
        app.severity_filter = None
        app.count_labels = {}
        app.table_counts = (0, 0)
        app.issue_count = 0
        app.issue_detail_open = True
        app.export_directory = None
        app.empty_labels = [Widget(), Widget()]
        app.tabs = SimpleNamespace(select=lambda: "issues", index=lambda _: 1, tab=lambda *a, **k: None)
        app.tree = Widget()
        app.issue_tree = Widget()
        app.issue_records = {}
        app.issue_items = {}
        app.issue_groups = {}
        app.issue_locations = {}
        app.issue_keys = {}
        for name in ("edit_button", "ack_button", "exclude_button", "reload_button", "export_button", "review_button",
                     "open_button", "preview_button", "issue_panel", "issue_list", "issue_detail_toggle", "issue_edit_button",
                     "issue_ack_button", "issue_source_button", "issue_detail_title", "issue_detail_text",
                     "export_folder_button"):
            setattr(app, name, Widget())
        app._set_issue_panel = Mock()
        app.refresh = Mock()
        return app

    def save_editor(self, app, edits, *, verified=(), reason="Đã đối chiếu đúng trường được ghi nhận"):
        with fake_dialog() as dialog:
            app.edit_record(app.session.records[0]["record_id"])
            for name, value in edits.items():
                dialog.strings[EDITABLE_FIELDS.index(name)].set(value)
            for name in verified:
                dialog.bools[EDITABLE_FIELDS.index(name)].set(True)
            dialog.strings[-1].set(reason)
            dialog.buttons["Lưu chỉnh sửa / xác nhận"]()
            return dialog

    def test_container_grid_shows_current_seal_with_leading_zeros(self):
        session = self.session()
        app = self.app(session)
        app.sort_field = None
        app.refresh = gui.ManifestApp.refresh.__get__(app)
        with fake_dialog(), patch.multiple(gui.tk, Frame=Widget, Label=Widget), patch.object(gui.ttk, "Progressbar", Widget):
            app._build()
            app.refresh()

        fields = app.tree.options["columns"]
        seal_index = fields.index("Seal_No")
        self.assertEqual(fields[seal_index - 1:seal_index + 2], ("Container_No", "Seal_No", "BL_No"))
        rid = session.records[0]["record_id"]
        self.assertEqual(app.tree.rows[rid][seal_index], "001235")

        session.update_record(rid, {"Seal_No": "000017"}, "Đối chiếu seal")
        app.refresh()
        self.assertEqual(app.tree.rows[rid][seal_index], "000017")

    def test_ambiguous_vinafco_sheet_prompts_and_restarts_only_on_explicit_choice(self):
        path = create_vinafco(self.folder / "multiple.xlsx")
        with path.open("rb") as source:
            book = load_workbook(source)
            book.copy_worksheet(book.active).title = "Bản phụ"
            book.save(path.with_suffix(".tmp.xlsx"))
            book.close()
        path.with_suffix(".tmp.xlsx").replace(path)
        session = process_manifest(path, "VINAFCO")
        self.assertFalse(session.records)
        names = session.metadata["candidate_sheets"]
        self.assertEqual(len(names), 2)
        app = self.app(session)
        with patch.object(app, "_start") as restart, patch.object(app, "_choose_sheet", return_value=None) as choose:
            app._complete_read(session)
            candidates = choose.call_args.args[0]
            self.assertEqual([item["source_sheet"] for item in candidates], names)
            self.assertTrue(all(candidate["header_row"] > 0 and candidate["preview_rows"] for candidate in candidates))
            restart.assert_not_called()
            self.assertIn("Chưa chọn sheet", app.status.get())
            choose.return_value = "Bản phụ"
            app._complete_read(session)
            restart.assert_called_once_with(path, sheet="Bản phụ", read_settings=app.settings["VINAFCO"])
        selected = process_manifest(path, "VINAFCO", settings={"selected_sheet": "Bản phụ"})
        with patch.object(app, "_choose_sheet") as choose:
            app._complete_read(selected)
            choose.assert_not_called()
        self.assertTrue(selected.records)
        app.read_override = ("VINAFCO", path, selected.settings)
        self.assertEqual(app._read_settings(), selected.settings)
        self.assertNotIn("selected_sheet", app.settings["VINAFCO"])
        self.assertFalse(app.config_path.exists())
        review = self.folder / "chosen.review.json"
        selected.save_review(review)
        with patch.object(gui.filedialog, "askopenfilename", return_value=str(review)):
            app.choose_review()
        self.assertEqual(app._read_settings()["selected_sheet"], "Bản phụ")
        with fake_dialog() as dialog:
            app.number_settings()
            dialog.strings[0].set("Dấu chấm thập phân: 25,000.50")
            dialog.buttons["Lưu cấu hình"]()
        self.assertEqual(app._read_settings()["selected_sheet"], "Bản phụ")
        self.assertNotIn("selected_sheet", load_settings(app.config_path)["VINAFCO"])
        app.selected_path = self.folder / "other.xlsx"
        self.assertNotIn("selected_sheet", app._read_settings())

    def test_reconciliation_display_distinguishes_unavailable_from_zero_difference(self):
        session = self.session()
        session.metadata["reconciliation"] = {
            "source_total": 57, "parsed_total": 57, "total_difference": 0, "size_differences": {},
        }
        self.assertIn("nguồn khai 57 · đọc được 57 · chênh lệch 0", gui._reconciliation_description(session))
        session.metadata["reconciliation"].update(
            source_total=None, parsed_total=4, total_difference=None, reason="Thiếu nhãn TOTAL.",
        )
        display = gui._reconciliation_description(session)
        self.assertIn("Thiếu nhãn TOTAL.", display)
        self.assertNotIn("chênh lệch 0", display)

    def test_summary_names_only_non_default_reading_settings(self):
        session = self.session()
        app = self.app(session)
        app.sort_field = None
        app.refresh = gui.ManifestApp.refresh.__get__(app)
        app.refresh()
        self.assertNotIn("Đang dùng", app.summary.get() + app.configuration.get())
        self.assertNotIn("Trọng lượng:", app.summary.get())
        self.assertEqual(app.configuration.get(), "")
        self.assertEqual(app.status.get(), "")
        session.settings["weight_kind"] = "cargo"
        session.metadata["effective_settings"] = dict(session.settings)
        app.refresh()
        self.assertIn("Trọng lượng: Trọng lượng hàng (phiên cũ)", app.summary.get())

    def test_blocking_errors_status_does_not_repeat_export_reason(self):
        session = self.session(weight=None)
        app = self.app(session)
        app.sort_field = None
        app.refresh = gui.ManifestApp.refresh.__get__(app)
        app.refresh()
        self.assertGreater(session.statistics()["errors"], 0)
        self.assertEqual(app.status.get(), "")
        self.assertIn("lỗi chặn xuất", app.export_hint.get())

    def test_seal_edit_does_not_clear_unrelated_fe_conflict(self):
        session = self.session(status="COC EMPTY")
        app = self.app(session)
        dialog = self.save_editor(app, {"Seal_No": "009999"}, reason="Chỉ sửa seal; chưa xác nhận F/E")
        dialog.error.assert_not_called()
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", {i["code"] for i in session.validate()})
        self.assertNotIn("FE_Status", session.records[0].get("_verified_fields", []))
        self.assertEqual(session.records[0]["_edited_fields"], ["Seal_No"])
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_weight_edit_keeps_coupled_description_error(self):
        session = self.session(weight=20, description="STEEL DEMO 12000")
        app = self.app(session)
        self.save_editor(app, {"Weight_Value": "12"})
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", {i["code"] for i in session.validate()})
        self.assertEqual(session.records[0]["Description"], "20 STEEL DEMO 12000")

    def test_explicit_field_verification_is_separate_from_changes(self):
        session = self.session(status="COC EMPTY")
        app = self.app(session)
        self.save_editor(app, {}, verified=("FE_Status",), reason="Đã xác nhận container rỗng với người cung cấp manifest")
        self.assertNotIn("VIMC_STATUS_GOODS_CONFLICT", {i["code"] for i in session.validate()})
        self.assertIn("FE_Status", session.records[0]["_verified_fields"])
        self.assertNotIn("Description", session.records[0]["_verified_fields"])

    def test_open_and_save_without_change_does_not_verify_any_field(self):
        session = self.session(status="COC EMPTY")
        app = self.app(session)
        dialog = self.save_editor(app, {})
        self.assertFalse(app.dirty)
        self.assertFalse(session.corrections)
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", {i["code"] for i in session.validate()})
        dialog.info.assert_called_once()

    def test_information_does_not_make_record_require_review(self):
        session = self.session()
        rid = session.records[0]["record_id"]
        session.base_issues.append({"severity": "info", "code": "SOURCE_INFORMATION",
                                    "message": "Đã ghi quy tắc đối soát", "record_id": rid})
        app = self.app(session)
        app.sort_field = None
        app.only_issues.set(True)
        app.refresh = gui.ManifestApp.refresh.__get__(app)
        app.refresh()
        self.assertFalse(app.tree.rows)
        self.assertFalse(app.issue_tree.rows)
        self.assertEqual(app.export_hint.get(), "")
        with fake_dialog() as dialog:
            app.edit_record(rid)
            self.assertFalse(any("Đã ghi quy tắc đối soát" in w.options.get("text", "") for w in dialog.widgets))

    def test_search_uses_live_issues_and_excludes_stale_record_warning(self):
        session = self.session()
        rid = session.records[0]["record_id"]
        session.records[0]["Warning"] = "Old superseded note"
        session.base_issues.append({"severity": "warning", "code": "SOURCE_WARNING",
                                    "message": "Current source finding", "record_id": rid})
        app = self.app(session)
        app.sort_field = None
        app.refresh = gui.ManifestApp.refresh.__get__(app)
        app.search.set("Old superseded note")
        app.refresh()
        self.assertFalse(app.tree.rows)
        app.search.set("Current source finding")
        app.refresh()
        self.assertEqual(tuple(app.tree.rows), (rid,))

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk work-area regression")
    def test_tk_high_dpi_small_work_area_keeps_save_and_reason_reachable(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(root.destroy)
        root.geometry("760x480+0+0")
        root.tk.call("tk", "scaling", 2.0)
        session = self.session(weight=20, description="STEEL DEMO 12000")
        app = self.app(session)
        app.root = root
        app._style()
        with patch.object(gui, "_monitor_work_area", return_value=(0, 0, 595, 430)):
            app.edit_record(session.records[0]["record_id"])
        root.update()
        dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        widgets = list(descendants(dialog))
        save = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "Lưu chỉnh sửa / xác nhận")
        cancel = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "Hủy")
        reason = next(w for w in save.master.master.winfo_children() if isinstance(w, ttk.Entry))
        self.assertLessEqual(dialog.winfo_rooty() + dialog.winfo_height(), 430)
        self.assertTrue(dialog.bind("<Control-s>"))
        self.assertTrue(dialog.bind("<Control-Return>"))
        for widget in (reason, save, cancel):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), dialog.winfo_rooty() + dialog.winfo_height())
        form_entry = next(w for w in widgets if isinstance(w, ttk.Entry) and w.get() == "20 STEEL DEMO 12000")
        canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
        self.assertEqual(canvas.yview()[0], 0)
        form_entry.focus_force()
        root.update()
        self.assertGreater(canvas.yview()[0], 0)
        self.assertGreaterEqual(form_entry.winfo_rooty(), canvas.winfo_rooty())
        self.assertLessEqual(form_entry.winfo_rooty() + form_entry.winfo_height(), canvas.winfo_rooty() + canvas.winfo_height() + 1)
        form_entry.delete(0, "end")
        form_entry.insert(0, "UPDATED GOODS")
        reason.insert(0, "Verified on source")
        reason.focus_force()
        root.update()
        reason.event_generate("<Return>")
        root.update()
        self.assertFalse(dialog.winfo_exists())
        self.assertEqual(session.records[0]["Description"], "UPDATED GOODS")
        self.assertTrue(app.dirty)
        self.assertIn("Lưu đối chiếu", app.status.get())
        with patch.object(gui, "_monitor_work_area", return_value=(0, 0, 595, 430)):
            app.edit_record(session.records[0]["record_id"])
        root.update()
        reopened = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
        reopened.focus_force()
        reopened.event_generate("<Escape>")
        root.update()
        self.assertFalse(reopened.winfo_exists())
        self.assertEqual(len(session.corrections), 1)

    @contextmanager
    def live_app(self, scale=1.25):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        try:
            root.tk.call("tk", "scaling", 96 / 72 * scale)
            # Keep the developer's real recent list out of the tests, and the tests out of it.
            recent = Path(tempfile.mkdtemp(dir=self.folder)) / gui.RECENT_FILE
            with patch.object(gui, "load_settings", side_effect=lambda *_: load_settings()), \
                    patch.object(gui, "_recent_file_path", return_value=recent):
                app = gui.ManifestApp(root)
            yield app
        finally:
            for callback in root.tk.splitlist(root.tk.call("after", "info")):
                root.after_cancel(callback)
            root.destroy()

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk geometry")
    def test_main_actions_and_footer_fit_at_minimum_size(self):
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale), self.live_app(scale) as app:
                root = app.root
                app.session = self.session(status="COC EMPTY")
                app.carrier.set("VIMC")
                app.selected_path = Path(app.session.metadata["source_path"])
                app.refresh()
                width, height = root.minsize()
                root.geometry(f"{width}x{height}")
                root.update()
                toolbar = app.reload_button.master.master
                extras = toolbar.grid_slaves(row=0, column=2)[0]
                widgets = (app.open_button, app.resume_button, app.search_entry, app.tabs,
                           app.edit_button, app.ack_button, app.exclude_button, app.review_button,
                           app.export_button, app.preview_button, app.json_check, app.author_label, app.file_name_label,
                           app.status_label, app.progress, *extras.winfo_children())
                for widget in widgets:
                    x = widget.winfo_rootx() - root.winfo_rootx()
                    y = widget.winfo_rooty() - root.winfo_rooty()
                    self.assertTrue(widget.winfo_viewable(), str(widget))
                    self.assertGreater(widget.winfo_width(), 1, str(widget))
                    self.assertGreater(widget.winfo_height(), 1, str(widget))
                    self.assertGreaterEqual(min(x, y), 0, str(widget))
                    self.assertLessEqual(x + widget.winfo_width(), root.winfo_width(), str(widget))
                    self.assertLessEqual(y + widget.winfo_height(), root.winfo_height(), str(widget))
                self.assertIn("lỗi chặn xuất", app.export_hint.get())
                self.assertEqual(root.title(), f"Manifest Cleaner {gui.__version__}")
                self.assertEqual(app.author_label.cget("text"), "Tien - Tan Thuan Port @2026")
                app.tabs.select(1)
                root.update()
                for widget in (app.issue_tree, app.issue_detail_text, app.issue_edit_button,
                               app.issue_ack_button, app.issue_source_button):
                    self.assertTrue(widget.winfo_viewable(), str(widget))
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         root.winfo_rootx() + root.winfo_width(), str(widget))
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         root.winfo_rooty() + root.winfo_height(), str(widget))

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk geometry")
    def test_author_stays_centered_in_footer_when_resizing(self):
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale), self.live_app(scale) as app:
                root = app.root
                self.assertEqual(app.status.get(), "")
                minimum_width, minimum_height = root.minsize()
                wide_width = min(root.winfo_screenwidth() - 20, gui._pixels(root, 1240))
                label = app.author_label
                # The JSON option sits beside the export it controls; the author keeps the footer centre.
                self.assertIs(app.json_check.master, app.export_button.master)
                self.assertIsNot(label.master, app.json_check.master)
                for width in (minimum_width, wide_width):
                    with self.subTest(width=width):
                        root.geometry(f"{width}x{minimum_height}")
                        root.update()
                        self.assertTrue(label.winfo_viewable())
                        label_center = label.winfo_rootx() + label.winfo_width() / 2
                        self.assertAlmostEqual(label_center, root.winfo_rootx() + root.winfo_width() / 2, delta=2)
                        self.assertLessEqual(app.json_check.winfo_rootx() + app.json_check.winfo_width(),
                                             app.review_button.winfo_rootx())
                        self.assertGreaterEqual(label.winfo_rooty(), app.json_check.winfo_rooty() + app.json_check.winfo_height())
                        self.assertGreaterEqual(label.winfo_rooty(), app.actionbar.winfo_rooty() + app.actionbar.winfo_height())
                        # Status and progress share the file-name row above the summary cards.
                        for widget in (app.status_label, app.progress):
                            self.assertEqual(widget.master, app.file_name_label.master)
                            self.assertLess(widget.winfo_rooty(), app.tabs.winfo_rooty())
                        self.assertFalse(hasattr(app, "export_hint_label"))

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk action bindings")
    def test_summary_buttons_filter_issue_tab_and_clear_restores_rows(self):
        with self.live_app() as app:
            app.session = self.session(status="COC EMPTY")
            app.carrier.set("VIMC")
            app.selected_path = Path(app.session.metadata["source_path"])
            rid = app.session.records[0]["record_id"]
            app.session.base_issues.append({"code": "TEST_WARNING", "message": "Cảnh báo mẫu",
                                            "severity": "warning", "record_id": rid})
            app.refresh()

            def buttons(parent):
                for widget in parent.winfo_children():
                    if isinstance(widget, ttk.Button):
                        yield widget
                    yield from buttons(widget)

            actions = {button.cget("text"): button for button in buttons(app.root)}
            total = len(app.issue_items)
            for label, expected in (("Lỗi chặn", "Lỗi"), ("Cảnh báo", "Cảnh báo")):
                actions[label].invoke()
                app.root.update()
                self.assertEqual(app.tabs.index(app.tabs.select()), 1)
                children = tuple(app.issue_items)
                self.assertTrue(children)
                self.assertEqual({app.issue_tree.item(row, "values")[0] for row in children}, {expected})
                self.assertIn(f"{len(children)} / {total} kết quả", app.filter_status.get())
            app.search.set("không có gì khớp")
            app.root.update()
            self.assertIn("Không có kết quả", app.empty_labels[1].cget("text"))
            actions["Xóa bộ lọc"].invoke()
            self.assertEqual(len(app.issue_items), total)
            self.assertEqual(app.search.get(), "")
            self.assertIsNone(app.severity_filter)

    def test_issue_titles_cover_codes_emitted_by_engine_and_adapters(self):
        project = Path(gui.__file__).parent
        emitted = set()

        def constants(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                emitted.add(node.value)
            elif isinstance(node, ast.IfExp):
                constants(node.body)
                constants(node.orelse)

        for path in (project / "engine.py", *(project / "carriers").glob("*/adapter.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    name = node.func.id
                    if name in {"add", "add_finding", "finding", "issue", "_add_issue"}:
                        issue_arg = int(name == "_add_issue" or (name == "add" and path.parent.name == "vinafco"))
                        constants(node.args[issue_arg])
                if (isinstance(node, ast.Tuple) and len(node.elts) == 3
                        and isinstance(node.elts[1], ast.Constant)
                        and node.elts[1].value in {"error", "warning", "info"}):
                    constants(node.elts[0])
                if (path.name == "engine.py" and isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == "required" for target in node.targets)):
                    emitted.update(f"MISSING_{field.upper()}" for field in ast.literal_eval(node.value))
        self.assertEqual(emitted, ISSUE_TITLES.keys())
        for title in ISSUE_TITLES.values():
            self.assertGreater(len(title), 0)
            self.assertLessEqual(len(title.split()), 6)
        self.assertEqual(issue_title({"code": "NEW_CODE", "field": "BL_No"}), "Kiểm tra số b/l")

    def test_issue_locators_use_column_evidence_and_keep_unknown_row(self):
        record = {"source_sheet": "Chi tiết", "source_row": 4, "raw": {
            "weight_source_row": 8, "weight_source_column": 12,
        }}
        self.assertEqual(issue_location({"field": "Weight_Value"}, record, "VOSCO", {}), "Chi tiết!L8")
        self.assertEqual(issue_location({"source_row": 5, "details": {"source_column": 19}},
                                        record, "VOSCO", {}), "Chi tiết!S5")
        self.assertEqual(issue_location({}, record, "VOSCO", {}), "Chi tiết · dòng 4")
        self.assertEqual(issue_location({"field": "Seal_No"}, record, "VINAFCO",
                                        {"column_mapping": {"seal": 4}}), "Chi tiết!E4")

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk column metrics")
    def test_identifier_columns_fit_long_bill_and_seal_numbers(self):
        sample = Path(gui.__file__).resolve().parent.parent / "samples" / "DEMO_VIMC_NEEDS_REVIEW.xlsx"
        with self.live_app() as app:
            app.selected_path = sample
            app.carrier.set("VIMC")
            app.session = process_manifest(sample, "VIMC")
            bill, seal = "VMCHCMHPH251100123", "0012345 / 0098765"
            app.session.records[0]["BL_No"] = bill
            app.session.records[0]["Seal_No"] = seal
            app.refresh()
            app.root.update()
            font = gui.tkfont.Font(root=app.root, font=gui.FONT)
            self.assertGreater(app.tree.column("BL_No", "width"), font.measure(bill))
            self.assertGreater(app.tree.column("Seal_No", "width"), font.measure(seal))
            self.assertEqual(app.tree.set(app.session.records[0]["record_id"], "Seal_No"), seal)

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk issue view and clipboard")
    def test_group_selection_details_actions_and_tsv(self):
        sample = Path(gui.__file__).resolve().parent.parent / "samples" / "DEMO_VIMC_NEEDS_REVIEW.xlsx"
        with self.live_app() as app:
            root = app.root
            app.selected_path = sample
            app.carrier.set("VIMC")
            app.session = process_manifest(sample, "VIMC")
            app.refresh()
            app.tabs.select(1)
            root.update()
            group = "group-VIMC_CONSIGNEE_MISSING"
            self.assertEqual(app.issue_tree.item(group, "text"), "Thiếu chủ hàng (2)")
            self.assertEqual(len(app.issue_tree.get_children(group)), 2)
            app.issue_tree.selection_set(group)
            root.update()
            self.assertIn("2 vấn đề", app.issue_detail_text.get("1.0", "end"))
            self.assertTrue(app.issue_edit_button.instate(["disabled"]))
            leaf = app.issue_tree.get_children("group-VIMC_LAYOUT_AMBIGUOUS")[0]
            app.issue_tree.selection_set(leaf)
            root.update()
            body = app.issue_detail_text.get("1.0", "end")
            original = app.issue_items[leaf]["message"]
            self.assertIn(original, body)
            self.assertIn("Manifest!D6", body)
            self.assertIn("Giá trị nguồn", body)
            self.assertTrue(app.issue_edit_button.instate(["!disabled"]))
            self.assertTrue(app.issue_ack_button.instate(["!disabled"]))
            self.assertTrue(app.issue_source_button.instate(["!disabled"]))
            self.assertTrue(app.issue_tree.bind("<Control-c>"))
            self.assertTrue(app.tree.bind("<Control-c>"))
            app.issue_source_button.invoke()
            root.update()
            source_window = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            source_frame = source_window.winfo_children()[0]
            self.assertTrue(any("Manifest!D6" in w.cget("text")
                                for w in source_frame.winfo_children() if isinstance(w, ttk.Label)))
            source_window.destroy()
            self.assertEqual(app._copy_table_row(app.issue_tree, hierarchical=True), "break")
            copied = next(csv.reader(io.StringIO(root.clipboard_get()), dialect="excel-tab"))
            self.assertEqual(copied, ["DEMU0000006", "Lỗi", "Trọng lượng, Hàng hóa", "Manifest!D6"])
            app.tabs.select(0)
            root.update()
            self.assertEqual(app._copy_table_row(app.tree), "break")
            copied = next(csv.reader(io.StringIO(root.clipboard_get()), dialect="excel-tab"))
            self.assertEqual(copied[:3], ["✕ 1 lỗi", "DEMU0000002", "001235"])
            self.assertEqual(copied[7], "16.055")
            self.assertEqual(app.tree.set(app.tree.selection()[0], "Weight_Value"), "16.055" + gui.WEIGHT_PAD)
            self.assertEqual(next(item for item in app.session.validate() if item["code"] == "VIMC_LAYOUT_AMBIGUOUS")["message"],
                             original)

    def test_all_demo_exports_preserve_cell_bytes_and_open_unicode_folder(self):
        samples = Path(gui.__file__).resolve().parent.parent / "samples"
        folder = self.folder / "Hồ sơ thử tiếng Việt"
        folder.mkdir()
        parts = ("xl/worksheets/sheet1.xml", "xl/sharedStrings.xml")
        warning = "Thông báo đầy đủ, có dấu và khoảng trắng để kiểm thử cột ghi chú."
        for carrier in ("VIMC", "VOSCO", "VINAFCO"):
            with self.subTest(carrier=carrier):
                source = folder / f"Mẫu tổng hợp {carrier}.xlsx"
                shutil.copyfile(samples / f"DEMO_{carrier}_INPUT.xlsx", source)
                session = process_manifest(source, carrier)
                finding = {"code": "UI_TEST_WARNING", "message": warning, "severity": "warning",
                           "record_id": session.records[0]["record_id"], "field": "Description"}
                session.base_issues.append(finding)
                expected = folder / f"Đối chứng {carrier}.xlsx"
                output = folder / f"Kết quả {carrier}.xlsx"
                export_port_bundle(session, expected, include_review=False)
                app = self.app(session)
                app.sort_field = None
                gui.ManifestApp.refresh(app)
                with (
                    patch.object(gui.filedialog, "asksaveasfilename", return_value=str(output)),
                    patch.object(gui.messagebox, "askyesno", return_value=True),
                    patch.object(gui.messagebox, "showinfo"),
                    patch.object(gui.messagebox, "showerror") as error,
                    patch.object(gui.os, "startfile", create=True) as opener,
                ):
                    app.export()
                    error.assert_not_called()
                    app.open_export_folder()
                    opener.assert_called_once_with(str(folder.resolve()))
                with ZipFile(expected) as before, ZipFile(output) as after:
                    for part in parts:
                        self.assertEqual(before.read(part), after.read(part), part)
                self.assertEqual(load_review(output.with_suffix(".review.json")).base_issues[-1]["message"], warning)

    def test_candidate_picker_requires_choice_and_reason(self):
        session = self.session(weight=20, description="STEEL DEMO 12000")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.edit_record(session.records[0]["record_id"])
            choose = dialog.buttons["Điền và xác nhận 2 trường"]
            choose()
            self.assertIsNone(session.records[0]["Weight_Value"])
            picker = next(w for w in dialog.widgets if isinstance(w.options.get("values"), list) and
                          w.options["values"] and str(w.options["values"][0]).startswith("1. "))
            picker.options["textvariable"].set(picker.options["values"][1])
            choose()
            self.assertEqual(dialog.strings[EDITABLE_FIELDS.index("Weight_Value")].get(), "12")
            self.assertEqual(dialog.strings[EDITABLE_FIELDS.index("Description")].get(), "20 STEEL DEMO")
            dialog.buttons["Lưu chỉnh sửa / xác nhận"]()
            dialog.error.assert_called_once()
            self.assertIsNone(session.records[0]["Weight_Value"])
            dialog.strings[-1].set("Đối chiếu nguồn: 12000 kg, mô tả 20 STEEL DEMO")
            dialog.buttons["Lưu chỉnh sửa / xác nhận"]()
            self.assertEqual(session.records[0]["Weight_Value"], 12)
            self.assertNotIn("VIMC_LAYOUT_AMBIGUOUS", {i["code"] for i in session.validate()})

    def test_equal_weight_candidate_leaves_unrelated_weight_edit_and_hides_after_resolution(self):
        session = self.session(extra_lines=("DEMU1111111 40HC 20GP STEEL 25000",))
        record = next(r for r in session.records if r["Container_No"] == "DEMU1111111")
        session.update_record(record["record_id"], {"Weight_Value": 27}, "Separate weight correction")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.edit_record(record["record_id"])
            button = dialog.buttons["Điền và xác nhận 3 trường"]
            picker = next(w for w in dialog.widgets if isinstance(w.options.get("values"), list) and
                          w.options["values"] and str(w.options["values"][0]).startswith("1. "))
            picker.options["textvariable"].set(picker.options["values"][1])
            button()
            weight_index = EDITABLE_FIELDS.index("Weight_Value")
            self.assertEqual(dialog.strings[weight_index].get(), "27")
            self.assertFalse(dialog.bools[weight_index].get())
            dialog.strings[-1].set("Confirmed alternate seal and size")
            dialog.buttons["Lưu chỉnh sửa / xác nhận"]()
        self.assertEqual((record["Seal_No"], record["Size_Type"], record["Weight_Value"]), ("40HC", "20GP", 27))
        self.assertTrue(record["raw"]["ambiguous_candidates"])
        with fake_dialog() as reopened:
            app.edit_record(record["record_id"])
            self.assertFalse(any(str(label).startswith("Điền và xác nhận") for label in reopened.buttons))

    def test_ambiguous_weight_candidate_fills_and_confirms_conflicting_weight(self):
        session = self.session(extra_lines=("DEMU1111111 40HC 20GP 28 STEEL 25000",))
        record = next(r for r in session.records if r["Container_No"] == "DEMU1111111")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.edit_record(record["record_id"])
            picker = next(w for w in dialog.widgets if isinstance(w.options.get("values"), list) and
                          w.options["values"] and str(w.options["values"][0]).startswith("1. "))
            picker.options["textvariable"].set(picker.options["values"][1])
            dialog.buttons["Điền và xác nhận 4 trường"]()
            weight_index = EDITABLE_FIELDS.index("Weight_Value")
            self.assertEqual(dialog.strings[weight_index].get(), "28")
            self.assertTrue(dialog.bools[weight_index].get())

    def issue_selected_app(self):
        session = self.session(extra_lines=("DEMU0000004 009998 20GP 0 THEP DEMO",))
        app = self.app(session)
        app.tree.selection_set(session.records[0]["record_id"])
        app.issue_tree.selection_set("issue-B")
        app.issue_records["issue-B"] = session.records[1]["record_id"]
        return app

    def test_exclude_targets_current_issue_and_names_container_in_dialog(self):
        app = self.issue_selected_app()
        with patch.object(gui.simpledialog, "askstring", return_value="Đã đối chiếu dòng cần loại") as ask:
            app.exclude()
        self.assertFalse(app.session.records[0].get("_excluded"))
        self.assertTrue(app.session.records[1]["_excluded"])
        prompt = ask.call_args.args[1]
        self.assertIn("DEMU0000004", prompt)
        self.assertIn("B/L:", prompt)
        self.assertNotIn("DEMU0000002", prompt)

    def test_acknowledge_and_edit_target_current_issue(self):
        app = self.issue_selected_app()
        with patch.object(gui.simpledialog, "askstring", return_value="Đối chiếu container B"):
            app.acknowledge()
        self.assertFalse(app.session.records[0].get("_manual_review_reason"))
        self.assertEqual(app.session.records[1]["_manual_review_reason"], "Đối chiếu container B")
        app.edit_record = Mock()
        app.edit_selected()
        app.edit_record.assert_called_once_with(app.session.records[1]["record_id"])

    def test_global_issue_disables_row_actions_and_cannot_exclude_hidden_selection(self):
        app = self.issue_selected_app()
        app.issue_records["issue-B"] = None
        app._update_row_actions()
        for button in (app.edit_button, app.ack_button, app.exclude_button):
            self.assertEqual(button.options["state"], "disabled")
        with patch.object(gui.messagebox, "showinfo"), patch.object(gui.simpledialog, "askstring") as ask:
            app.exclude()
        ask.assert_not_called()
        self.assertFalse(any(r.get("_excluded") for r in app.session.records))

    def test_resume_preserves_edits_and_uses_saved_settings_without_reparsing(self):
        session = self.session()
        session.update_record(session.records[0]["record_id"], {"Seal_No": "009999"}, "Sửa seal theo nguồn")
        review = self.folder / "saved.review.json"
        session.save_review(review)
        app = self.app(session)
        with patch.object(gui.filedialog, "askopenfilename", return_value=str(review)), patch.object(gui, "process_manifest", side_effect=AssertionError("Must not reparse")), patch.object(gui.messagebox, "showerror") as error:
            app.choose_review()
        error.assert_not_called()
        self.assertEqual(app.session.records[0]["Seal_No"], "009999")
        self.assertTrue(app.session.corrections)
        self.assertEqual(app._read_settings(), app.session.settings)
        self.assertFalse(app.dirty)

    def test_resume_can_relocate_unchanged_original_file(self):
        session = self.session()
        session.update_record(session.records[0]["record_id"], {"Seal_No": "009999"}, "Đối chiếu seal")
        review = self.folder / "saved.review.json"
        session.save_review(review)
        relocated = self.folder / "moved_original.xlsx"
        Path(session.metadata["source_path"]).rename(relocated)
        app = self.app(session)
        with patch.object(gui.filedialog, "askopenfilename", side_effect=[str(review), str(relocated)]), patch.object(gui.messagebox, "askyesno", return_value=True), patch.object(gui.messagebox, "showerror") as error:
            app.choose_review()
        error.assert_not_called()
        self.assertEqual(app.selected_path, relocated.resolve())
        self.assertEqual(app.session.records[0]["Seal_No"], "009999")

    def test_bad_review_preserves_existing_session_and_never_prompts_source_relocation(self):
        session = self.session()
        app = self.app(session)
        review = self.folder / "bad.json"
        review.write_text('{"format":"not-a-review"}', encoding="utf-8")
        with patch.object(gui.filedialog, "askopenfilename", return_value=str(review)), patch.object(gui.messagebox, "askyesno") as ask, patch.object(gui.messagebox, "showerror") as error:
            app.choose_review()
        ask.assert_not_called()
        error.assert_called_once()
        self.assertIs(app.session, session)

    def test_export_bundle_saves_resumable_review_and_clears_dirty(self):
        session = self.session()
        app = self.app(session)
        app.dirty = True
        output = self.folder / "port.xlsx"
        with patch.object(gui.filedialog, "asksaveasfilename", return_value=str(output)) as ask, patch.object(gui.messagebox, "askyesno", return_value=True), patch.object(gui.messagebox, "showinfo"), patch.object(gui.messagebox, "showerror") as error:
            app.export()
        error.assert_not_called()
        self.assertEqual(ask.call_args.kwargs["title"], "Xuất file Manifest")
        self.assertEqual(ask.call_args.kwargs["initialdir"], str(app.selected_path.parent))
        self.assertTrue(output.is_file())
        review = output.with_suffix(".review.json")
        self.assertTrue(review.is_file())
        self.assertEqual(load_review(review).records[0]["Container_No"], session.records[0]["Container_No"])
        self.assertFalse(app.dirty)

    def test_save_dialogs_start_beside_the_manifest_in_use(self):
        session = self.session()
        app = self.app(session)
        review = self.folder / "phiên.json"
        with patch.object(gui.filedialog, "asksaveasfilename", return_value=str(review)) as ask, patch.object(gui.messagebox, "showerror") as error:
            app.save_review()
        error.assert_not_called()
        self.assertEqual(ask.call_args.kwargs["initialdir"], str(Path(session.metadata["source_path"]).parent))
        self.assertTrue(review.is_file())
        app.selected_path = self.folder / "đã xóa" / "input.xlsx"
        self.assertIsNone(app._output_directory())

    def test_settings_noop_does_not_invalidate_session(self):
        session = self.session()
        app = self.app(session)
        with fake_dialog() as dialog:
            app.number_settings()
            dialog.buttons["Lưu cấu hình"]()
        self.assertFalse(session.metadata.get("settings_changed"))
        self.assertFalse(app.dirty)
        self.assertFalse(app.config_path.exists())

    def test_gui_applies_migrated_gross_setting_after_reprocessing_legacy_review(self):
        session = self.session()
        app = self.app(session)
        app.read_override = (session.carrier, app.selected_path, {**session.settings, "weight_kind": "unknown"})
        app._complete_read(session)
        self.assertEqual(app._read_settings()["weight_kind"], "gross")

    def test_source_preview_shows_conflicting_goods_before_export(self):
        session = self.session(status="COC EMPTY")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.edit_record(session.records[0]["record_id"])
            comparison = next(w for w in dialog.widgets if w.options.get("columns") == ("field", "source", "output"))
            goods = next(row for row in comparison.rows.values() if row[0] == "Hàng hóa")
            self.assertIn("STEEL DEMO", goods[1])
            self.assertEqual(goods[2], "EMPTY")

    def test_source_weight_preview_shows_the_continuation_cell(self):
        record = {"source_sheet": "Manifest", "source_row": 4, "Weight_Value": 12.75,
                  "raw": {"weight_source_row": 36, "weight_source_column": 19,
                          "weight_source_line": 2, "weight_line": "11.25 TONS"}}
        self.assertEqual(gui._source_field(record, "Weight_Value"),
                         "Manifest!S36 · dòng 2 trong ô · 11.25 TONS")

    def test_unsaved_preview_uses_current_form_values_without_mutating_session(self):
        session = self.session()
        app = self.app(session)
        before = copy.deepcopy(session.records)
        with fake_dialog() as dialog:
            app.edit_record(session.records[0]["record_id"])
            for field, value in {"Seal_No": "009999", "Weight_Value": "27.1234", "Description": "NEW GOODS", "Size_Type": "40GP"}.items():
                dialog.strings[EDITABLE_FIELDS.index(field)].set(value)
            dialog.buttons["Cập nhật xem trước theo các ô đang sửa"]()
            comparison = next(w for w in dialog.widgets if w.options.get("columns") == ("field", "source", "output"))
            values = {row[0]: row[2] for row in comparison.rows.values()}
            self.assertEqual(values["Số niêm chì"], "009999")
            self.assertEqual(values["Trọng lượng (Tấn)"], "27.12")
            self.assertEqual(values["Hàng hóa"], "NEW GOODS")
            self.assertEqual(values["Kích cỡ"], "40HC")
        self.assertEqual(session.records, before)
        self.assertFalse(session.corrections)

    def test_preview_uses_saved_correction_history_and_only_an_entered_new_reason(self):
        session = self.session()
        rid = session.records[0]["record_id"]
        session.update_record(rid, {"Seal_No": "001119"}, "Saved reason")
        app = self.app(session)
        with fake_dialog() as dialog, patch.object(gui, "preview_record_for_export", return_value={}) as preview:
            app.edit_record(rid)
            dialog.strings[EDITABLE_FIELDS.index("Seal_No")].set("001120")
            dialog.buttons["Cập nhật xem trước theo các ô đang sửa"]()
            self.assertEqual([item["reason"] for item in preview.call_args.args[0].corrections], ["Saved reason"])
            self.assertTrue(any("Chưa nhập lý do" in w.options.get("text", "") for w in dialog.widgets))
            dialog.strings[-1].set("Typed reason")
            dialog.buttons["Cập nhật xem trước theo các ô đang sửa"]()
            self.assertEqual([item["reason"] for item in preview.call_args.args[0].corrections],
                             ["Saved reason", "Typed reason"])
            self.assertFalse(any("Chưa nhập lý do" in w.options.get("text", "") for w in dialog.widgets))
        self.assertEqual([item["reason"] for item in session.corrections], ["Saved reason"])
        self.assertEqual(session.records[0]["Seal_No"], "001119")

    def test_source_trace_is_labelled_as_parse_time_snapshot_after_correction(self):
        session = self.session(weight=20, description="STEEL DEMO 12000")
        session.update_record(session.records[0]["record_id"], {"Weight_Value": 12, "Description": "20 STEEL DEMO"}, "Đã xác nhận trọng lượng cuối dòng là kg")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.show_source_coverage()
            table = next(w for w in dialog.widgets if w.options.get("columns") == ("source", "status", "reason", "text"))
            self.assertTrue(any(row[1] == "Cần đối chiếu lúc đọc" for row in table.rows.values()))
            self.assertTrue(any("tình trạng tại lần đọc nguồn" in w.options.get("text", "") for w in dialog.widgets))
        self.assertNotIn("VIMC_LAYOUT_AMBIGUOUS", {i["code"] for i in session.validate()})

    def test_container_length_follows_vtos_code(self):
        for code, expected in (("20DC", "20"), ("22G1", "20"), ("25G1", "20"), ("20TK", "20"), ("40HC", "40"),
                               (" 42g1 ", "40"), ("40RH", "40"), ("45HC", "45"), ("45RH", "45"), ("L5G1", "45"),
                               ("", ""), (None, ""), ("RF", "")):
            with self.subTest(code=code):
                self.assertEqual(gui._size_class(code), expected)

    def test_size_cards_split_20_and_40_and_keep_45_and_unknown_apart(self):
        records = [{"Container_No": "AAAU0000001", "VTOS_Size": "20DC", "FE_Status": "F"},
                   {"Container_No": "AAAU0000001", "VTOS_Size": "20DC", "FE_Status": "F"},
                   {"Container_No": "AAAU0000002", "VTOS_Size": "40HC", "FE_Status": "F"},
                   {"Container_No": "AAAU0000003", "VTOS_Size": "42G1", "FE_Status": "E"},
                   {"Container_No": "AAAU0000004", "VTOS_Size": "45HC", "FE_Status": "F"},
                   {"Container_No": "AAAU0000005", "VTOS_Size": "", "FE_Status": "E"},
                   {"Container_No": "", "VTOS_Size": "20DC", "FE_Status": "?"}]
        sizes = gui._size_breakdown(records)
        # Port order 20'/40', with a third 45' figure only when 45' boxes exist.
        self.assertEqual(gui._size_display("full", 4, sizes["full"]), ("2 / 1 / 1", "20'/40'/45'"))
        self.assertEqual(gui._size_display("empty", 2, sizes["empty"]), ("0 / 1", "20'/40' · chưa rõ cỡ 1"))
        self.assertEqual(gui._size_display("containers", 5, sizes["containers"]),
                         ("5", "20'/40'/45': 1/2/1 · chưa rõ cỡ 1"))
        self.assertEqual(gui._size_display("full", 0, gui._size_breakdown([])["full"]), ("0 / 0", "20'/40'"))

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk rendering")
    def test_cards_rows_and_progress_show_sizes_alert_colours_and_stripes(self):
        with self.live_app() as app:
            session = self.session()
            template = session.records[0]
            for index, (number, size, status) in enumerate((("DEMU0000101", "40HC", "F"), ("DEMU0000102", "40HC", "E"),
                                                            ("DEMU0000103", "45HC", "F"))):
                record = copy.deepcopy(template)
                record.update(record_id=f"extra-{index}", Container_No=number, VTOS_Size=size, FE_Status=status)
                session.records.append(record)
            session.base_issues.append({"code": "TEST_WARNING", "message": "Cảnh báo mẫu",
                                        "severity": "warning", "record_id": "extra-1"})
            app.session = session
            app.carrier.set(session.carrier)
            app.selected_path = Path(session.metadata["source_path"])
            self.assertEqual(app.progress.cget("style"), "Idle.Horizontal.TProgressbar")
            app.refresh()
            app.root.update()
            stats = session.statistics()
            sizes = gui._size_breakdown(session.active_records())
            self.assertEqual(app.count_labels["full"].get(),
                             " / ".join(str(sizes["full"].get(length, 0)) for length in ("20", "40", "45")))
            self.assertEqual(app.count_captions["full"].get(), "20'/40'/45'")
            self.assertEqual(app.count_labels["empty"].get(),
                             f"{sizes['empty'].get('20', 0)} / {sizes['empty'].get('40', 0)}")
            self.assertEqual(app.count_labels["containers"].get(), str(stats["containers"]))
            self.assertEqual(sum(sizes["full"].values()), stats["full"])
            self.assertEqual(sum(sizes["empty"].values()), stats["empty"])
            self.assertEqual((stats["errors"], stats["warnings"]), (0, 1))
            self.assertEqual(app.tree.item("extra-1", "values")[0], "▲ 1 cảnh báo")
            for key, variant in (("errors", "Error"), ("warnings", "Warning")):
                expected = variant if stats[key] else "Muted"
                self.assertEqual(app.count_numbers[key].cget("style"), f"{expected}.Number.TLabel")
                self.assertEqual(app.count_stripes[key].cget("bg"), gui.STRIPES[expected])
            rows = app.tree.get_children()
            plain = [row for row in rows if app.tree.item(row, "values")[0] == "✓"]
            for position, row in enumerate(rows):
                tags = app.tree.item(row, "tags")
                if row in plain:
                    self.assertEqual("odd" in tags, position % 2 == 1, row)
                else:
                    self.assertTrue({"error", "warning", "excluded"} & set(tags), row)
            self.assertIn("Box.indicator", ttk.Style(app.root).layout("TCheckbutton")[0][1]["children"][0])

    def test_recent_list_ignores_damaged_files_and_keeps_five_unique_newest_first(self):
        path = self.folder / gui.RECENT_FILE
        self.assertEqual(gui._load_recent(path), [])
        for text in ("", "{not json", "[]", '{"items": 5}', '{"items": [1, "x", {"path": 3}]}'):
            path.write_text(text, encoding="utf-8")
            self.assertEqual(gui._load_recent(path), [], text)
        path.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(gui._load_recent(path), [])
        # Unknown hãng, empty paths and bad counts are dropped or normalised instead of failing the app.
        path.write_text(json.dumps({"items": [
            {"path": "a.xls", "carrier": "NOPE", "containers": 1}, {"path": " ", "carrier": "VOSCO"},
            {"path": "b.xls", "carrier": "VIMC", "containers": True, "opened": 5},
            {"path": "c.xls", "carrier": "VOSCO", "containers": -2, "opened": "2026-11-25T10:00"}]}), encoding="utf-8")
        self.assertEqual([(i["path"], i["carrier"], i["containers"], i["opened"]) for i in gui._load_recent(path)],
                         [("b.xls", "VIMC", None, ""), ("c.xls", "VOSCO", None, "2026-11-25T10:00")])
        items = []
        for number in range(7):
            items = gui._remember_recent(items, self.folder / f"m{number}.xls", "VOSCO", number, "2026-11-25T10:00")
        self.assertEqual([Path(i["path"]).name for i in items], ["m6.xls", "m5.xls", "m4.xls", "m3.xls", "m2.xls"])
        # The same file is listed once, moves to the top and takes the hãng it was last read with.
        items = gui._remember_recent(items, self.folder / "m3.xls", "VIMC", 99, "2026-11-26T09:30")
        self.assertEqual([Path(i["path"]).name for i in items], ["m3.xls", "m6.xls", "m5.xls", "m4.xls", "m2.xls"])
        self.assertEqual((items[0]["carrier"], items[0]["containers"]), ("VIMC", 99))
        self.assertTrue(gui._save_recent(path, items))
        self.assertEqual(gui._load_recent(path), items)
        self.assertFalse(path.with_name(path.name + ".tmp").exists())
        self.assertEqual(gui._recent_caption(items[0]), "VIMC · 99 cont · 26-11-2026")
        self.assertEqual(gui._recent_caption({"carrier": "VOSCO", "containers": None, "opened": ""}), "VOSCO")

    def test_recent_list_write_failure_is_silent(self):
        with patch.object(Path, "write_text", side_effect=PermissionError("read-only folder")):
            self.assertFalse(gui._save_recent(self.folder / gui.RECENT_FILE, []))

    def test_recent_file_is_beside_settings_and_not_tracked_by_git(self):
        self.assertEqual(gui._recent_file_path(Path("C:/App/settings.json")), Path("C:/App/recent_files.json"))
        ignored = (Path(gui.__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8").split()
        self.assertIn("recent_files.json", ignored)
        # settings.json must stay free of this data, because load_settings rejects any key that is not a hãng.
        with self.assertRaises(ValueError):
            gui.load_settings(self._write_settings({"recent_files": []}))

    def _write_settings(self, data):
        path = self.folder / "settings-check.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_reading_a_manifest_remembers_it_but_not_while_a_sheet_is_still_to_be_chosen(self):
        session = self.session()
        app = self.app(session)
        app._complete_read(session)
        self.assertEqual([(Path(i["path"]).name, i["carrier"], i["containers"]) for i in app.recent],
                         [("input.xlsx", "VIMC", session.statistics()["containers"])])
        self.assertEqual(gui._load_recent(app.recent_path), app.recent)
        pending = self.app(session)
        pending.recent_path = self.folder / "pending" / gui.RECENT_FILE
        pending.recent_path.parent.mkdir()
        session.metadata["table_candidates"] = [{"source_sheet": "A"}]
        with patch.object(pending, "_choose_sheet", return_value=None), patch.object(pending, "_start"):
            pending._complete_read(session)
        self.assertEqual(pending.recent, [])
        self.assertFalse(pending.recent_path.exists())

    def _recent_items(self, count=5):
        items = []
        for number, carrier in zip(range(count), ("VOSCO", "VIMC", "VINAFCO", "VOSCO", "VIMC")):
            path = self.folder / f"tàu {number}.xls"
            path.write_bytes(b"x")
            items = gui._remember_recent(items, path, carrier, 100 + number, "2026-11-25T10:00")
        return items

    def test_open_recent_uses_the_saved_hang_and_drops_a_missing_file(self):
        app = self.app(self.session())
        app.recent = self._recent_items()
        app._confirm_discard = Mock(return_value=True)
        app._start = Mock()
        app._update_table_states = Mock()
        newest = app.recent[0]
        app.carrier = Variable("VINAFCO")
        app.open_recent(newest)
        self.assertEqual(app.carrier.get(), newest["carrier"])
        app._start.assert_called_once_with(Path(newest["path"]))
        app._start.reset_mock()
        Path(newest["path"]).unlink()
        with patch.object(gui.messagebox, "showwarning") as warn:
            app.open_recent(newest)
        warn.assert_called_once()
        self.assertIn("không tìm thấy", warn.call_args.args[0].lower())
        app._start.assert_not_called()
        self.assertNotIn(newest["path"], [i["path"] for i in app.recent])
        self.assertEqual(len(gui._load_recent(app.recent_path)), 4)
        app.busy = True
        app.open_recent(app.recent[0])
        app._start.assert_not_called()
        app.busy, app.dirty = False, True
        app._confirm_discard.return_value = False
        app.open_recent(app.recent[0])
        app._start.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk rendering")
    def test_recent_panel_lists_all_hang_before_a_file_is_open_and_fits_the_minimum_size(self):
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale), self.live_app(scale) as app:
                root = app.root
                items = self._recent_items()
                gui._save_recent(app.recent_path, items)
                app.recent = gui._load_recent(app.recent_path)
                self.assertFalse(app.recent_panel.winfo_manager())
                app._update_table_states()
                width, height = root.minsize()
                root.geometry(f"{width}x{height}")
                root.update()
                self.assertEqual(app.recent_panel.winfo_manager(), "place")
                self.assertIn("Mở manifest", app.recent_message.cget("text"))
                table = app.tree.master
                visible = [row for row, _, _ in app.recent_rows if row.winfo_manager()]
                self.assertGreaterEqual(len(visible), 1)
                for row in visible:
                    self.assertTrue(row.winfo_viewable())
                    self.assertLessEqual(row.winfo_rooty() + row.winfo_height(), table.winfo_rooty() + table.winfo_height())
                self.assertTrue(app.recent_clear_button.winfo_viewable())
                # A taller window shows more rows, newest first. The screen may cap the height at high scaling,
                # so all five are required only when the table area is tall enough to hold them.
                root.geometry(f"{width}x{min(height + gui._pixels(root, 330), root.winfo_screenheight() - gui._pixels(root, 90))}")
                root.update()
                visible = [(b.cget("text"), d.cget("text")) for row, b, d in app.recent_rows if row.winfo_manager()]
                roomy = table.winfo_height() >= gui._pixels(root, 320)
                self.assertGreaterEqual(len(visible), 5 if roomy else 1)
                self.assertEqual(visible[0][0], "tàu 4.xls")
                self.assertIn("104 cont", visible[0][1])
                if roomy:
                    self.assertEqual({detail.split(" · ")[0] for _, detail in visible}, {"VOSCO", "VIMC", "VINAFCO"})
                # The list is the only guidance while no session exists, and the empty label steps aside.
                self.assertFalse(app.empty_labels[0].winfo_manager())
                self.assertEqual(app.empty_labels[1].winfo_manager(), "place")
                with patch.object(app, "_start") as start:
                    app.recent_rows[0][1].invoke()
                    start.assert_called_once_with(Path(items[0]["path"]))
                self.assertEqual(app.carrier.get(), items[0]["carrier"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk rendering")
    def test_recent_panel_hides_with_a_session_when_busy_and_after_clearing(self):
        with self.live_app() as app:
            gui._save_recent(app.recent_path, self._recent_items(2))
            app.recent = gui._load_recent(app.recent_path)
            app._update_table_states()
            self.assertEqual(app.recent_panel.winfo_manager(), "place")
            app.busy = True
            app._update_table_states()
            self.assertFalse(app.recent_panel.winfo_manager())
            self.assertEqual(app.empty_labels[0].winfo_manager(), "place")
            app.busy = False
            app._update_table_states()
            self.assertEqual(app.recent_panel.winfo_manager(), "place")
            app.session = self.session()
            app.refresh()
            self.assertFalse(app.recent_panel.winfo_manager())
            app.session = None
            app.tree.delete(*app.tree.get_children())
            app.issue_tree.delete(*app.issue_tree.get_children())
            app._update_table_states()
            self.assertEqual(app.recent_panel.winfo_manager(), "place")
            app.recent_clear_button.invoke()
            self.assertEqual(app.recent, [])
            self.assertEqual(gui._load_recent(app.recent_path), [])
            self.assertFalse(app.recent_panel.winfo_manager())
            self.assertEqual(app.empty_labels[0].winfo_manager(), "place")

    def _sample_session(self, carrier):
        """A copy of the synthetic sample, so the repository file is never the export source."""
        source = self.folder / f"src-{carrier}.xlsx"
        shutil.copyfile(Path(gui.__file__).resolve().parents[1] / "samples" / f"DEMO_{carrier}_INPUT.xlsx", source)
        return process_manifest(source, carrier)

    def test_ownership_counts_follow_each_carrier_operator_codes(self):
        rows = lambda *codes: [{"Operator": code} for code in codes]
        for carrier, coc, soc in (("VOSCO", "VOC", "SVC"), ("VIMC", "VMC", "SVM"), ("VINAFCO", "VFC", "SVF")):
            with self.subTest(carrier=carrier):
                counts = gui._ownership_counts(rows(soc, coc, coc.lower(), "XYZ", None), carrier)
                self.assertEqual((counts["soc"], counts["coc"], counts["other"]), (1, 2, 2))
        # Configured codes win over the carrier defaults.
        counts = gui._ownership_counts(rows("ABC", "VFC", "abc"), "VINAFCO", {"operator_soc": "abc", "operator_coc": "VFC"})
        self.assertEqual((counts["soc"], counts["coc"], counts["other"]), (2, 1, 0))
        # Identical codes cannot tell SOC from COC, so those rows are not assigned to either side.
        counts = gui._ownership_counts(rows("VFC"), "VINAFCO", {"operator_soc": "VFC", "operator_coc": "VFC"})
        self.assertEqual(gui._ownership_display(counts), ("0 / 0", "khác 1"))
        self.assertEqual(gui._ownership_display(gui.Counter(soc=81, coc=236)), ("81 / 236", ""))

    def test_preview_marks_rows_like_the_workbook_and_blocking_rows_first(self):
        columns = ["STT", "F/E", "Số Container", "Trọng lượng (Tấn)"]
        rows = [[1, "F", "A", 9.0], [2, "E", "B", 2.5], [3, "E", "C", None], [4, "F", "D", 16.06]]
        table = gui._preview_table(columns, rows, {None: [3, 4], "Số Container": [2]}, "0.00", errors=[4])
        self.assertEqual([tags for _, tags in table], [(), ("empty", "identifier"), ("warning",), ("error",)])
        self.assertEqual(table[0][0], ["1", "F", "A", "9.00"])
        self.assertEqual(table[2][0][3], "")
        self.assertEqual(gui._preview_cell("Trọng lượng (Tấn)", 16.055, "General"), "16.055")
        self.assertEqual(gui._preview_cell("TL hàng", 9.0, "General"), "9")
        self.assertEqual(gui._preview_cell("Số niêm chì", "001234"), "001234")

    def test_preview_rows_match_the_exported_workbook_cell_for_cell(self):
        for carrier in ("VOSCO", "VIMC", "VINAFCO"):
            with self.subTest(carrier=carrier):
                session = self._sample_session(carrier)
                columns, rows, highlights = gui.preview_port_rows(session)
                weight_format = gui.CARRIER_PROFILES[carrier].export.weight_format
                table = gui._preview_table(columns, rows, highlights, weight_format)
                result = export_port_bundle(session, self.folder / f"out-{carrier}.xlsx", include_review=False)
                book = load_workbook(result["excel"], read_only=True)
                try:
                    exported = [list(row) for row in book.worksheets[0].iter_rows(values_only=True)]
                finally:
                    book.close()
                self.assertEqual([str(value) for value in exported[0]], columns)
                self.assertEqual(len(exported) - 1, len(table))
                for (values, _), cells in zip(table, exported[1:]):
                    shown = [gui._preview_cell(column, cell, weight_format) for column, cell in zip(columns, cells)]
                    self.assertEqual(values, shown)

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk rendering")
    def test_preview_dialog_filters_locks_export_on_errors_and_copies_plain_values(self):
        with self.live_app() as app:
            root = app.root
            self.assertEqual(str(app.preview_button.cget("state")), "disabled")
            app.session = self.session(weight=None)
            app.carrier.set(app.session.carrier)
            app.selected_path = Path(app.session.metadata["source_path"])
            app.refresh()
            self.assertGreater(app.session.statistics()["errors"], 0)
            self.assertEqual(str(app.export_button.cget("state")), "disabled")
            self.assertEqual(str(app.preview_button.cget("state")), "normal")
            app.preview_button.invoke()
            root.update()
            tree = app.preview_tree
            rows = tree.get_children()
            self.assertEqual(len(rows), len(app.session.active_records()))
            self.assertEqual(str(app.preview_export_button.cget("state")), "disabled")
            self.assertIn("Chưa xuất được", app.preview_note.cget("text"))
            self.assertTrue(any("error" in tree.item(row, "tags") for row in rows))
            container = str(app.session.active_records()[0]["Container_No"])
            app.preview_query.set(container.lower())
            root.update()
            self.assertEqual(len(tree.get_children()), 1)
            self.assertIn("Đang hiện 1", app.preview_counts.get())
            app.preview_query.set("không có dòng nào khớp")
            self.assertEqual(tree.get_children(), ())
            app.preview_query.set("")
            tree.selection_set(tree.get_children()[0])
            app._copy_table_row(tree)
            copied = root.clipboard_get()
            self.assertNotIn(gui.WEIGHT_PAD, copied)
            self.assertTrue(copied.startswith("1\t"))
            app.preview_dialog.event_generate("<Escape>")
            root.update()
            self.assertFalse(app.preview_dialog.winfo_exists())
            # Without blocking errors the preview hands over to the normal export flow.
            app.session = self._sample_session("VOSCO")
            app.carrier.set("VOSCO")
            app.selected_path = Path(app.session.metadata["source_path"])
            app.refresh()
            app.preview_button.invoke()
            root.update()
            self.assertEqual(str(app.preview_export_button.cget("state")), "normal")
            with patch.object(app, "export") as export:
                app.preview_export_button.invoke()
            export.assert_called_once_with()
            self.assertFalse(app.preview_dialog.winfo_exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows Tk geometry")
    def test_seven_cards_fit_soc_coc_and_long_split_figures_at_minimum_size(self):
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale), self.live_app(scale) as app:
                root = app.root
                app.session = self._sample_session("VOSCO")
                app.carrier.set("VOSCO")
                app.selected_path = Path(app.session.metadata["source_path"])
                width, height = root.minsize()
                root.geometry(f"{width}x{height}")
                root.update()
                app.refresh()
                root.update()
                counts = gui._ownership_counts(app.session.active_records(), "VOSCO", app.session.settings)
                self.assertEqual(app.count_labels["ownership"].get(), f"{counts['soc']} / {counts['coc']}")
                self.assertEqual(counts["soc"] + counts["coc"] + counts["other"], app.session.statistics()["active_records"])
                # Realistic worst cases: three-figure F counts with 45' boxes, and four-figure totals.
                for key, text in (("full", "450 / 500 / 20"), ("empty", "120 / 380 / 12"),
                                  ("ownership", "218 / 1272"), ("containers", "1490")):
                    app.count_labels[key].set(text)
                    app._fit_card_number(key)
                root.update()
                for key in gui.SPLIT_CARDS:
                    number, card = app.count_numbers[key], app.count_cards[key]
                    self.assertLessEqual(number.winfo_reqwidth(), card.winfo_width(), (key, scale))
                    self.assertTrue(number.winfo_viewable())

    def test_every_dialog_offers_maximize(self):
        """Each function that opens a Toplevel also restores its maximize button."""
        tree = ast.parse(Path(gui.__file__).read_text(encoding="utf-8"))
        opened, missing = 0, []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            calls = {ast.unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)}
            if "tk.Toplevel" in calls:
                opened += 1
                if "_allow_maximize" not in calls:
                    missing.append(node.name)
        self.assertGreaterEqual(opened, 6)
        self.assertEqual(missing, [])

    @staticmethod
    def _caption_style(window):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32")
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        return user32.GetWindowLongW(user32.GetParent(window.winfo_id()), -16)

    @unittest.skipUnless(sys.platform == "win32", "Windows caption buttons")
    def test_dialog_maximize_button_maximizes_and_restores_without_minimize(self):
        with self.live_app() as app:
            root = app.root
            app.session = self._sample_session("VOSCO")
            app.carrier.set("VOSCO")
            app.selected_path = Path(app.session.metadata["source_path"])
            app.refresh()
            app.preview_button.invoke()
            root.update()
            dialog = app.preview_dialog
            style = self._caption_style(dialog)
            self.assertTrue(style & 0x00010000, "WS_MAXIMIZEBOX")
            self.assertFalse(style & 0x00020000, "WS_MINIMIZEBOX must stay off for a modal dialog")
            normal_width = dialog.winfo_width()
            dialog.state("zoomed")
            root.update()
            self.assertEqual(dialog.state(), "zoomed")
            self.assertGreater(dialog.winfo_width(), normal_width)
            dialog.state("normal")
            root.update()
            self.assertEqual(dialog.state(), "normal")
            dialog.destroy()
            # A plain transient Toplevel shown later gets the button once mapped.
            other = tk.Toplevel(root)
            other.transient(root)
            gui._allow_maximize(other)
            root.update()
            self.assertTrue(self._caption_style(other) & 0x00010000)
            other.destroy()
        # Test doubles are ignored instead of failing.
        gui._allow_maximize(Widget())


if __name__ == "__main__":
    unittest.main()
