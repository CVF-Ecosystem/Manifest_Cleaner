"""Observable session-resume, review-gate, settings and formula safety regressions."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
import xlsxwriter

from manifest_cleaner.cli import main as cli_main
from manifest_cleaner.engine import (
    EDITABLE_FIELDS, ReviewSourceError, load_review, load_settings, process_manifest,
    validate_carrier_settings,
)
from manifest_cleaner.exporter import build_port_rows
from manifest_cleaner.carriers.vinafco.profile import INPUT_COLUMNS
from scripts.create_samples import create_vimc


class Session110Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def session(self, **kwargs):
        source = create_vimc(self.folder / "input.xlsx", **kwargs)
        return process_manifest(source, "VIMC")

    def save(self, session, filename="review.json"):
        path = self.folder / filename
        session.save_review(path)
        return path

    def conflict(self):
        source = create_vimc(self.folder / "conflict.xlsx", description="STEEL")
        book = load_workbook(source)
        book.active["D3"] = "COC EMPTY"
        book.save(source)
        book.close()
        return process_manifest(source, "VIMC")

    @staticmethod
    def codes(session):
        return {item["code"] for item in session.validate()}

    def test_submitting_unchanged_fields_does_not_verify_an_existing_error(self):
        session = self.conflict()
        record = session.records[0]
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(session))
        values = {key: record.get(key) for key in EDITABLE_FIELDS}
        session.update_record(record["record_id"], values, "Chỉ lưu lại các giá trị đang hiển thị")
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(session))
        self.assertEqual(session.corrections, [])
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_full_form_submission_with_only_seal_changed_keeps_fe_error(self):
        session = self.conflict()
        record = session.records[0]
        values = {key: record.get(key) for key in EDITABLE_FIELDS}
        values["Seal_No"] = "009999"
        session.update_record(record["record_id"], values, "Chỉ sửa số seal")
        self.assertEqual(record["Seal_No"], "009999")
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(session))
        self.assertEqual(session.corrections[-1]["changed_fields"], ["Seal_No"])
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_explicit_field_verification_can_resolve_unchanged_fe_after_review(self):
        session = self.conflict()
        record = session.records[0]
        session.update_record(record["record_id"], {}, "Đã đối chiếu F/E với chứng từ nguồn", verified_fields=["FE_Status"])
        self.assertNotIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(session))
        self.assertEqual(record["FE_Status"], "E")
        self.assertEqual(record["Description"], "STEEL")
        _, rows = build_port_rows(session)
        self.assertEqual(len(rows), 1)
        self.assertEqual(session.corrections[-1]["verified_fields"], ["FE_Status"])

    def test_ambiguous_layout_requires_review_of_both_weight_and_description(self):
        session = self.session(weight=20, description="STEEL DEMO 12000")
        record = session.records[0]
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", self.codes(session))
        session.update_record(record["record_id"], {"Weight_Value": 12}, "Xác nhận riêng trọng lượng")
        self.assertIn("VIMC_LAYOUT_AMBIGUOUS", self.codes(session))
        with self.assertRaises(ValueError):
            build_port_rows(session)
        session.update_record(record["record_id"], {"Description": "STEEL DEMO"}, "Đối chiếu và sửa riêng mô tả hàng")
        self.assertNotIn("VIMC_LAYOUT_AMBIGUOUS", self.codes(session))
        columns, rows = build_port_rows(session)
        self.assertEqual(rows[0][columns.index("TL hàng")], 12)
        self.assertEqual(rows[0][columns.index("Hàng hóa")], "STEEL DEMO")

    def test_round_trip_preserves_edits_exclusions_history_raw_and_export(self):
        session = self.session(extra_lines=("DEMU0000004 001237 40HC 25 THEP DEMO",))
        first, second = session.records
        raw = [copy.deepcopy(record["raw"]) for record in session.records]
        session.update_record(first["record_id"], {"Seal_No": "000999", "Weight_Value": 18.5}, "Đã đối chiếu seal và cân")
        session.update_record(first["record_id"], {}, "Đã đối chiếu mô tả", verified_fields=["Description"])
        session.set_excluded(second["record_id"], True, "Dòng không thuộc manifest cần xuất")
        session.acknowledge_record(first["record_id"], "Hoàn tất kiểm tra chứng từ")
        expected_rows = build_port_rows(session)
        expected_history = copy.deepcopy(session.corrections)
        resumed = load_review(self.save(session))
        self.assertEqual(len(resumed.records), 2)
        self.assertEqual(len(resumed.active_records()), 1)
        self.assertEqual(resumed.records[0]["Seal_No"], "000999")
        self.assertEqual(resumed.records[0]["Weight_Value"], 18.5)
        self.assertTrue(resumed.records[1]["_excluded"])
        self.assertEqual([record["raw"] for record in resumed.records], raw)
        self.assertEqual(resumed.corrections, expected_history)
        self.assertEqual(build_port_rows(resumed), expected_rows)

    def test_round_trip_does_not_clear_an_unresolved_error(self):
        session = self.conflict()
        resumed = load_review(self.save(session))
        self.assertIn("VIMC_STATUS_GOODS_CONFLICT", self.codes(resumed))
        with self.assertRaises(ValueError):
            build_port_rows(resumed)

    def test_json_payload_change_without_updated_integrity_value_is_rejected(self):
        path = self.save(self.session())
        data = json.loads(path.read_text(encoding="utf-8"))
        data["records"][0]["Weight_Value"] = 999
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mã kiểm tra"):
            load_review(path)

    def test_duplicate_record_ids_are_rejected_even_in_a_fully_written_session(self):
        session = self.session()
        session.records.append(copy.deepcopy(session.records[0]))
        with self.assertRaisesRegex(ValueError, "trùng"):
            load_review(self.save(session))

    def test_changed_source_is_rejected_without_replacing_saved_edits(self):
        session = self.session()
        session.update_record(session.records[0]["record_id"], {"Seal_No": "009999"}, "Seal đã đối chiếu")
        review = self.save(session)
        source = Path(session.metadata["source_path"])
        book = load_workbook(source)
        book.active["A1"] = "Source changed after review"
        book.save(source)
        book.close()
        with self.assertRaises(ReviewSourceError) as raised:
            load_review(review)
        self.assertEqual(raised.exception.code, "source_changed")
        saved = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(saved["records"][0]["Seal_No"], "009999")

    def test_missing_source_can_be_relocated_only_when_its_bytes_match(self):
        session = self.session()
        session.update_record(session.records[0]["record_id"], {"Seal_No": "000888"}, "Đối chiếu trước khi di chuyển file")
        review = self.save(session)
        moved = self.folder / "thu_muc_moi" / "nguon_da_chuyen.xlsx"
        moved.parent.mkdir()
        Path(session.metadata["source_path"]).rename(moved)
        with self.assertRaises(ReviewSourceError) as raised:
            load_review(review)
        self.assertEqual(raised.exception.code, "source_missing")
        resumed = load_review(review, source_path=moved)
        self.assertEqual(resumed.records[0]["Seal_No"], "000888")
        self.assertEqual(Path(resumed.metadata["source_path"]), moved.resolve())
        _, rows = build_port_rows(resumed)
        self.assertEqual(len(rows), 1)
        wrong = create_vimc(self.folder / "wrong.xlsx", weight=30)
        with self.assertRaises(ReviewSourceError) as wrong_source:
            load_review(review, source_path=wrong)
        self.assertEqual(wrong_source.exception.code, "source_changed")

    def test_version_one_report_is_rejected_with_a_clear_upgrade_instruction(self):
        path = self.folder / "v1_report.json"
        path.write_text(json.dumps({"format": "manifest-cleaner-review-v1", "records": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "1.0.*1.1"):
            load_review(path)

    def test_relative_source_is_resolved_beside_review_after_folder_is_moved(self):
        session = self.session()
        source = Path(session.metadata["source_path"])
        session.update_record(session.records[0]["record_id"], {"Seal_No": "000444"}, "Đối chiếu trước khi chuyển cả thư mục")
        session.metadata["source_path"] = source.name
        review = self.save(session)
        moved = self.folder / "portable"
        moved.mkdir()
        source.rename(moved / source.name)
        review.rename(moved / review.name)
        resumed = load_review(moved / review.name)
        self.assertEqual(resumed.records[0]["Seal_No"], "000444")
        self.assertEqual(Path(resumed.metadata["source_path"]), (moved / source.name).resolve())
        self.assertEqual(len(build_port_rows(resumed)[1]), 1)

    def test_failed_atomic_save_keeps_previous_valid_session(self):
        session = self.session()
        review = self.save(session)
        before = review.read_bytes()
        original_seal = session.records[0]["Seal_No"]
        session.update_record(session.records[0]["record_id"], {"Seal_No": "000777"}, "Thay đổi chưa lưu thành công")
        with patch("manifest_cleaner.engine.os.replace", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                session.save_review(review)
        self.assertEqual(review.read_bytes(), before)
        self.assertEqual(load_review(review).records[0]["Seal_No"], original_seal)

    def test_explicit_missing_settings_file_fails_without_creating_export(self):
        source = create_vimc(self.folder / "input.xlsx")
        missing = self.folder / "missing_settings.json"
        output = self.folder / "must_not_exist.xlsx"
        with self.assertRaises(FileNotFoundError):
            load_settings(missing)
        error_stream = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(error_stream):
            result = cli_main([str(source), "--carrier", "VIMC", "--settings", str(missing), "--output", str(output)])
        self.assertNotEqual(result, 0)
        self.assertIn("missing_settings.json", error_stream.getvalue())
        self.assertFalse(output.exists())
        self.assertEqual(load_settings()["VIMC"]["number_format"], "legacy")

    def test_invalid_setting_enums_mappings_and_unknown_keys_are_rejected(self):
        invalid = [
            {"number_format": "decimal_typo"}, {"weight_kind": "cargo_typo"},
            {"size_to_vtos": ["20GP", "20DC"]}, {"size_to_vtos": {"20GP": ""}},
            {"size_to_vtos": {"20GP": 20}}, {"number_fomat": "decimal_comma"},
            {"default_weight_unit": "LB"}, {"peek_rows": True}, {"tare_20ft": -1},
        ]
        for settings in invalid:
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    validate_carrier_settings("VINAFCO", settings)

    def test_invalid_enum_container_type_has_a_configuration_error(self):
        with self.assertRaises(ValueError):
            validate_carrier_settings("VIMC", {"number_format": ["decimal_comma"]})

    def test_explicit_null_carrier_settings_are_not_treated_as_omitted_defaults(self):
        path = self.folder / "null_settings.json"
        path.write_text('{"VINAFCO": null}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(path)

    def test_settings_merge_defaults_canonicalise_aliases_and_do_not_share_mutable_state(self):
        path = self.folder / "settings.json"
        path.write_text(json.dumps({"VINAFCO": {"default_weight_unit_if_missing": "KG", "target_sheet_name": "Manifest",
                                               "size_to_vtos": {"CUSTOM": "20DC"}}}), encoding="utf-8")
        settings = load_settings(path)
        self.assertEqual(settings["VINAFCO"]["default_weight_unit"], "KGS")
        self.assertEqual(settings["VINAFCO"]["weight_kind"], "gross")
        self.assertEqual(settings["VINAFCO"]["selected_sheet"], "Manifest")
        settings["VINAFCO"]["size_to_vtos"]["CUSTOM"] = "40HC"
        self.assertEqual(load_settings(path)["VINAFCO"]["size_to_vtos"]["CUSTOM"], "20DC")

    def test_new_read_uses_gross_but_legacy_review_retains_saved_weight_rule(self):
        settings_path = self.folder / "settings.json"
        settings_path.write_text('{"VOSCO":{"weight_kind":"cargo"},"VIMC":{"weight_kind":"unknown"}}', encoding="utf-8")
        self.assertTrue(all(settings["weight_kind"] == "gross" for settings in load_settings(settings_path).values()))
        source = create_vimc(self.folder / "legacy-input.xlsx")
        session = process_manifest(source, "VIMC", settings={"weight_kind": "cargo"})
        self.assertEqual(session.settings["weight_kind"], "gross")
        self.assertEqual(session.records[0]["Weight_Kind"], "gross")
        session.settings["weight_kind"] = "cargo"
        session.records[0]["Weight_Kind"] = "cargo"
        review = self.folder / "legacy.review.json"
        session.save_review(review)
        resumed = load_review(review)
        self.assertEqual(resumed.settings["weight_kind"], "cargo")
        self.assertEqual(resumed.records[0]["Weight_Kind"], "cargo")
        self.assertEqual(process_manifest(source, "VIMC", settings=resumed.settings).settings["weight_kind"], "gross")

    def test_uncached_formula_on_used_sheet_blocks_export_even_if_its_record_was_skipped(self):
        source = create_vimc(self.folder / "uncached.xlsx")
        book = load_workbook(source)
        book.active["D6"] = '="DEMU0000004 001237 20GP 25 STEEL"'
        book.save(source)
        book.close()
        session = process_manifest(source, "VIMC")
        self.assertEqual(len(session.records), 1)
        formula = next(i for i in session.validate() if i["code"] == "SOURCE_FORMULA_UNCALCULATED")
        self.assertEqual(formula["source_sheet"], "Manifest")
        self.assertEqual(formula["source_cell"], "D6")
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_recognised_second_sheet_with_only_uncached_formula_blocks_partial_export(self):
        source = create_vimc(self.folder / "two_sheets.xlsx")
        book = load_workbook(source)
        second = book.copy_worksheet(book.active)
        second.title = "Manifest 2"
        second["C3"] = "DEMO-VIMC-002"
        second["D5"] = '=\"DEMU0000004 001237 20GP 25 STEEL\"'
        book.save(source)
        book.close()
        session = process_manifest(source, "VIMC")
        self.assertEqual(len(session.records), 1)
        self.assertEqual(session.metadata["used_sheets"], ["Manifest", "Manifest 2"])
        formula = next(i for i in session.validate() if i["code"] == "SOURCE_FORMULA_UNCALCULATED")
        self.assertEqual((formula["source_sheet"], formula["source_cell"]), ("Manifest 2", "D5"))
        with self.assertRaises(ValueError):
            build_port_rows(session)

    def test_unrelated_cover_formula_does_not_block_explicitly_selected_manifest(self):
        source = create_vimc(self.folder / "cover.xlsx")
        book = load_workbook(source)
        cover = book.create_sheet("Cover")
        cover["A1"] = "=1+1"
        book.save(source)
        book.close()
        session = process_manifest(source, "VIMC", settings={"selected_sheet": "Manifest"})
        self.assertNotIn("SOURCE_FORMULA_UNCALCULATED", self.codes(session))
        self.assertIn("Cover", session.metadata["available_sheets"])
        _, rows = build_port_rows(session)
        self.assertEqual(len(rows), 1)

    def test_valid_cached_container_and_weight_formulas_are_accepted(self):
        source = self.folder / "cached.xlsx"
        fields = list(INPUT_COLUMNS)
        with xlsxwriter.Workbook(source) as book:
            sheet = book.add_worksheet("Manifest")
            sheet.write_row(0, 0, list(INPUT_COLUMNS.values()))
            sheet.write(1, fields.index("party_raw"), "(S) SHIPPER")
            sheet.write(1, fields.index("bill_no"), "BL-001")
            sheet.write(2, fields.index("party_raw"), "(C) CONSIGNEE")
            sheet.write_formula(3, fields.index("container_no"), '="MSCU1234567"', None, "MSCU1234567")
            sheet.write(3, fields.index("seal"), "001234")
            sheet.write(3, fields.index("type"), "20DC")
            sheet.write(3, fields.index("comm"), "STEEL")
            sheet.write_formula(3, fields.index("gw"), "=20+5", None, 25)
        session = process_manifest(source, "VINAFCO")
        self.assertNotIn("SOURCE_FORMULA_UNCALCULATED", self.codes(session))
        self.assertEqual(session.records[0]["Container_No"], "MSCU1234567")
        self.assertEqual(session.records[0]["Weight_Value"], 25)
        _, rows = build_port_rows(session)
        self.assertEqual(len(rows), 1)

    def test_cached_excel_formula_error_blocks_export(self):
        source = self.folder / "cached_error.xlsx"
        fields = list(INPUT_COLUMNS)
        with xlsxwriter.Workbook(source) as book:
            sheet = book.add_worksheet("Manifest")
            sheet.write_row(0, 0, list(INPUT_COLUMNS.values()))
            sheet.write(1, fields.index("party_raw"), "(S) SHIPPER")
            sheet.write(1, fields.index("bill_no"), "BL-001")
            sheet.write(2, fields.index("party_raw"), "(C) CONSIGNEE")
            sheet.write(3, fields.index("container_no"), "MSCU1234567")
            sheet.write(3, fields.index("seal"), "001234")
            sheet.write(3, fields.index("type"), "20DC")
            sheet.write(3, fields.index("comm"), "STEEL")
            sheet.write_formula(3, fields.index("gw"), "=1/0", None, "#DIV/0!")
        session = process_manifest(source, "VINAFCO")
        self.assertIn("SOURCE_FORMULA_ERROR", self.codes(session))
        with self.assertRaises(ValueError):
            build_port_rows(session)


if __name__ == "__main__":
    unittest.main()
