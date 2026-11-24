"""Regression tests for real GUI callbacks without a display server.

Fake widgets replace rendering only; session validation, file IO, source hash
checks, carrier parsing and GUI save/action callbacks remain real.
"""
from __future__ import annotations

import ast
import copy
import csv
import io
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
                     "open_button", "issue_panel", "issue_list", "issue_detail_toggle", "issue_edit_button",
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
        self.assertEqual(app.status.get(), f"Đã đọc {len(session.records)} bản ghi. Có thể xuất. Mở từng dòng để xem bằng chứng từ nguồn.")
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
        self.assertEqual(app.status.get(), f"Đã đọc {len(session.records)} bản ghi.")

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
        self.assertIn("Có thể xuất", app.status.get())
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
            with patch.object(gui, "load_settings", side_effect=lambda *_: load_settings()):
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
                widgets = (app.open_button, app.resume_button, app.search_entry, app.tabs,
                           app.edit_button, app.ack_button, app.exclude_button, app.review_button,
                           app.export_button, app.export_hint_label, app.json_check, app.status_label, app.progress)
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
                app.tabs.select(1)
                root.update()
                for widget in (app.issue_tree, app.issue_detail_text, app.issue_edit_button,
                               app.issue_ack_button, app.issue_source_button):
                    self.assertTrue(widget.winfo_viewable(), str(widget))
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         root.winfo_rootx() + root.winfo_width(), str(widget))
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         root.winfo_rooty() + root.winfo_height(), str(widget))

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
            self.assertEqual(copied[:3], ["1 lỗi", "DEMU0000002", "001235"])
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
        with patch.object(gui.filedialog, "asksaveasfilename", return_value=str(output)), patch.object(gui.messagebox, "askyesno", return_value=True), patch.object(gui.messagebox, "showinfo"), patch.object(gui.messagebox, "showerror") as error:
            app.export()
        error.assert_not_called()
        self.assertTrue(output.is_file())
        review = output.with_suffix(".review.json")
        self.assertTrue(review.is_file())
        self.assertEqual(load_review(review).records[0]["Container_No"], session.records[0]["Container_No"])
        self.assertFalse(app.dirty)

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


if __name__ == "__main__":
    unittest.main()
