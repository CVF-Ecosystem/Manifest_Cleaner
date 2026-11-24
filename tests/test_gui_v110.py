"""Regression tests for real GUI callbacks without a display server.

Fake widgets replace rendering only; session validation, file IO, source hash
checks, carrier parsing and GUI save/action callbacks remain real.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openpyxl import load_workbook

from manifest_cleaner import gui
from manifest_cleaner.engine import EDITABLE_FIELDS, load_review, load_settings, process_manifest
from manifest_cleaner.exporter import build_port_rows
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
        self.selected = ()

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get_children(self):
        return tuple(self.rows)

    def delete(self, *items):
        for item in items:
            self.rows.pop(item, None)

    def insert(self, *args, iid=None, values=(), tags=(), **kwargs):
        iid = iid or f"row-{len(self.rows)}"
        self.rows[iid] = values
        return iid

    def selection(self):
        return self.selected

    def selection_set(self, *items):
        self.selected = tuple(items)

    def exists(self, item):
        return item in self.rows


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
        stack.enter_context(patch.multiple(gui.tk, Toplevel=RenderWidget, StringVar=String, BooleanVar=Boolean, Text=RenderWidget))
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
        app.tabs = SimpleNamespace(select=lambda: "issues", index=lambda _: 1, tab=lambda *a, **k: None)
        app.tree = Widget()
        app.issue_tree = Widget()
        app.issue_records = {}
        app.issue_keys = {}
        for name in ("edit_button", "ack_button", "exclude_button", "reload_button", "export_button", "review_button"):
            setattr(app, name, Widget())
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

    def test_source_preview_shows_conflicting_goods_before_export(self):
        session = self.session(status="COC EMPTY")
        app = self.app(session)
        with fake_dialog() as dialog:
            app.edit_record(session.records[0]["record_id"])
            comparison = next(w for w in dialog.widgets if w.options.get("columns") == ("field", "source", "output"))
            goods = next(row for row in comparison.rows.values() if row[0] == "Hàng hóa")
            self.assertIn("STEEL DEMO", goods[1])
            self.assertEqual(goods[2], "EMPTY")

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
