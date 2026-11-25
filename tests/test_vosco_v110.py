"""Independent audit regressions: cargo line alignment and weight semantics."""
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from manifest_cleaner.engine import process_manifest
from manifest_cleaner.exporter import build_port_rows
from manifest_cleaner.carriers.vosco.adapter import parse_manifest, current_weight_issues, _aligned_partial_weights, _parsed_lines
from manifest_cleaner.carriers.vosco.processors import determine_fe


CONTAINERS = "ABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C"


class Vosco110Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, description, *, containers=CONTAINERS, weight="25 TONS\n25 TONS"):
        book = Workbook()
        sheet = book.active
        sheet.title = "Manifest"
        row = [""] * 19
        row[0], row[1], row[5], row[10], row[14], row[18] = "(C)", "TEST CONSIGNEE", "VOSCO123456", containers, description, weight
        sheet.append(row)
        path = self.root / "manifest.xlsx"
        book.save(path)
        book.close()
        return path

    def test_adjacent_column_audit_detects_detail_but_not_narrative_or_trailer(self):
        book = Workbook()
        sheet = book.active
        row = [""] * 19
        row[0], row[1], row[5], row[10], row[14], row[18] = ("(C)", "TEST", "VOSCO123456",
            "ABCU1234567/001234 40HC-C", "CARGO", "25 TONS")
        sheet.append(row)
        shifted = [""] * 19
        shifted[11], shifted[14], shifted[18] = "ABCU1234568/001235 40HC-C", "CARGO", "25 TONS"
        sheet.append(shifted)
        narrative = [""] * 19
        narrative[11], narrative[18] = "Reference ABCU1234569/001236 40HC-C", "25 TONS"
        sheet.append(narrative)
        trailer = [""] * 19
        trailer[0], trailer[11], trailer[18] = "TOTAL", "ABCU1234570/001237 40HC-C", "25 TONS"
        sheet.append(trailer)
        path = self.root / "adjacent.xlsx"
        book.save(path)
        book.close()
        result = parse_manifest(path)
        findings = [i for i in result["issues"] if i["code"] == "VOSCO_ADJACENT_CONTAINER_CANDIDATE"]
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["source_row"], findings[0]["source_column"], findings[0]["severity"]), (2, 12, "error"))
        self.assertTrue(any(f["source_row"] == 2 and f["source_column"] == 12 and f["status"] == "unresolved"
                            for f in result["metadata"]["source_fragments"]))

    def test_adjacent_audit_starts_at_bill_and_ignores_total_in_cargo_text(self):
        book = Workbook()
        sheet = book.active
        leading = [""] * 19
        leading[0], leading[1], leading[5], leading[11] = "(C)", "TEST", "VOSCO123456", CONTAINERS.splitlines()[0]
        sheet.append(leading)
        main = [""] * 19
        main[10], main[14], main[18] = CONTAINERS.splitlines()[1], "TOTAL QUALITY STEEL", "25 TONS"
        sheet.append(main)
        shifted = [""] * 19
        shifted[9] = "ABCU1234569/001236 40HC-C"
        sheet.append(shifted)
        path = self.root / "adjacent_before_and_after.xlsx"
        book.save(path)
        book.close()
        session = process_manifest(path, "VOSCO")
        self.assertEqual(len(session.records), 1)
        findings = [i for i in session.validate() if i["code"] == "VOSCO_ADJACENT_CONTAINER_CANDIDATE"]
        self.assertEqual([(i["source_row"], i["source_column"]) for i in findings], [(1, 12), (3, 10)])

    def test_delivery_mode_annotations_do_not_create_container_or_shift_quantity(self):
        book = Workbook()
        sheet = book.active
        row = [""] * 19
        row[0], row[1], row[5], row[10], row[14], row[18] = (
            "(C)", "TEST", "VOSCO123456", "ABCU1234567/001234 40HC-C", "CARGO", "25 TONS")
        sheet.append(row)
        for label in ("DOOR-DOOR", "DOOR/OTI", "OTI/OTI", "OTI/DOOR", "DB-CY", "OTI-CY"):
            note = [""] * 19
            note[10] = label
            sheet.append(note)
        path = self.root / "delivery_modes.xlsx"
        book.save(path)
        book.close()
        session = process_manifest(path, "VOSCO")
        self.assertEqual(len(session.records), 1)
        self.assertFalse(any(i["code"] == "CONTAINER_UNPARSED" for i in session.validate()))
        self.assertEqual(len([f for f in session.metadata["source_fragments"]
                              if f["reason"] == "delivery_mode_annotation"]), 6)
        columns, rows = build_port_rows(session)
        self.assertEqual(rows[0][columns.index("Số lượng")], 1)

    def test_partial_weights_require_matching_physical_lines(self):
        containers = "FCL/FCL\nABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C\nABCU1234569/001236 40HC-C"
        description = "\nRICE\nSTEEL\nWOOD"
        aligned = parse_manifest(self.workbook(description, containers=containers, weight="\n25 TONS\n26 TONS\n"))
        self.assertEqual([r["Weight_Value"] for r in aligned["records"]], [25, 26, None])
        self.assertEqual([r["raw"]["weight_source_line"] for r in aligned["records"]], [2, 3, None])
        self.assertEqual([r["raw"]["weight_expected_source_line"] for r in aligned["records"]], [2, 3, 4])
        self.assertEqual(aligned["records"][-1]["raw"]["weight_alignment"], "trailing_source_weight_missing")
        raw_crlf = containers.replace("\n", "\r\n")
        crlf = _aligned_partial_weights(raw_crlf, description.replace("\n", "\r\n"),
                                         "\r\n25 TONS\r\n26 TONS\r\n", _parsed_lines(raw_crlf), {})
        self.assertEqual([w["value"] if w else None for w in crlf[0]], [25, 26, None])
        self.assertEqual(sum(i["code"] == "WEIGHT_INVALID" for i in aligned["issues"]), 1)
        self.assertFalse(any(i["code"] == "WEIGHT_ASSOCIATION_AMBIGUOUS" for i in aligned["issues"]))
        negatives = [
            (description, "25 TONS\n26 TONS", containers),
            ("RICE\nSTEEL\nWOOD", "\n25 TONS\n26 TONS", containers),
            (description, "\n25 TONS\n\n26 TONS", containers),
            (description, "\n25 TONS\nunknown", containers),
            (description, "\n25 TONS\n26 TONS", containers.replace("FCL/FCL", "unknown")),
            (description, "\n25 TONS\n26 TONS", containers.replace("ABCU1234568", "ABCU1234567")),
        ]
        for desc, weight, source in negatives:
            with self.subTest(desc=desc, weight=weight, source=source):
                result = parse_manifest(self.workbook(desc, containers=source, weight=weight))
                self.assertTrue(any(i["code"] == "WEIGHT_ASSOCIATION_AMBIGUOUS" for i in result["issues"]))
                self.assertTrue(all(r["Weight_Value"] is None for r in result["records"]))

    def continuation_workbook(self, *, continuation="27 TONS\nTotal:78 TONS", before=None, after=None):
        book = Workbook()
        sheet = book.active
        row = [""] * 19
        row[0], row[1], row[5] = "(C)", "TEST", "VOSCO123456"
        row[10] = "FCL/FCL\nABCU1234567/001234 40HC-C\nABCU1234568/001235 40HC-C\nABCU1234569/001236 40HC-C"
        row[14], row[18] = "\nRICE\nSTEEL\nWOOD", "\n25 TONS\n26 TONS\n"
        sheet.append(row)
        for _ in range(4): sheet.append([""] * 19)
        party = [""] * 19
        party[0], party[1] = "(N)", "TEST NOTIFY"
        sheet.append(party)
        for item in before or []: sheet.append(item)
        row = [""] * 19
        row[18] = continuation
        sheet.append(row)
        for item in after or []: sheet.append(item)
        path = self.root / "continuation.xlsx"
        book.save(path)
        book.close()
        return path

    def test_continuation_weights_use_same_bill_exact_count_and_total(self):
        result = parse_manifest(self.continuation_workbook(continuation="27 TONS\nTotal:78\nTONS"))
        self.assertEqual([r["Weight_Value"] for r in result["records"]], [25, 26, 27])
        last = result["records"][-1]
        self.assertEqual((last["source_row"], last["raw"]["weight_source_row"],
                          last["raw"]["weight_source_column"], last["raw"]["weight_source_line"]), (1, 7, 19, 1))
        self.assertEqual(last["raw"]["weight_alignment"], "continuation_total_matched")
        self.assertEqual((last["raw"]["weight_total_source_row"], last["raw"]["weight_total_source_column"],
                          last["raw"]["weight_total_source_line"]), (7, 19, 2))
        self.assertIn("vosco.weight.continuation-total", last["rules"])
        self.assertFalse(any(i["code"] == "WEIGHT_INVALID" for i in result["issues"]))

    def test_continuation_can_start_with_previous_weight_unit(self):
        from openpyxl import load_workbook
        for header, expected in (("KGS", [25, 26, 27]), ("TONS", [25, 26000, None])):
            with self.subTest(header=header):
                path = self.continuation_workbook(continuation=f"{header}\n27 TONS\nTotal:78\nTONS")
                book = load_workbook(path)
                book.active.cell(1, 19).value = "\n25 TONS\n26000"
                book.save(path)
                book.close()
                result = parse_manifest(path)
                self.assertEqual([r["Weight_Value"] for r in result["records"]], expected)
                if header == "KGS":
                    before, last = result["records"][1:]
                    self.assertEqual(before["raw"]["weight_unit_evidence"],
                                     {"source_row": 7, "source_column": 19, "source_line": 1, "text": "KGS"})
                    self.assertEqual((last["raw"]["weight_source_line"], last["raw"]["weight_total_source_line"]),
                                     (2, 3))

    def test_continuation_must_be_unique_scoped_and_total_checked(self):
        next_bill = [""] * 19
        next_bill[5] = "VOSCO654321"
        extra = [""] * 19
        extra[18] = "27 TONS\nTotal:78 TONS"
        detail = [""] * 19
        detail[10] = "ABCU1234570/001237 40HC-C"
        for name, kwargs in [
            ("wrong total", {"continuation": "27 TONS\nTotal:79 TONS"}),
            ("missing unit", {"continuation": "27 TONS\nTotal:78"}),
            ("wrong count", {"continuation": "27 TONS\n28 TONS\nTotal:106 TONS"}),
            ("bad weight", {"continuation": "junk\nTotal:78 TONS"}),
            ("next bill", {"before": [next_bill]}),
            ("next detail", {"before": [detail]}),
            ("two candidates", {"after": [extra]}),
        ]:
            with self.subTest(case=name):
                result = parse_manifest(self.continuation_workbook(**kwargs))
                original = result["records"][:3]
                self.assertEqual([r["Weight_Value"] for r in original], [25, 26, None])
                self.assertTrue(any(i["code"] == "WEIGHT_INVALID" and i["record_id"] == original[-1]["record_id"]
                                    for i in result["issues"]))

    def test_continuation_requires_unit_prefix_and_weight_only_candidate(self):
        from openpyxl import load_workbook
        for case in ("unitless prefix", "party on continuation", "earlier detail", "earlier weight", "later detail", "adjacent detail"):
            with self.subTest(case=case):
                path = self.continuation_workbook()
                book = load_workbook(path)
                sheet = book.active
                if case == "unitless prefix":
                    sheet.cell(1, 19).value = "\n25\n26\n"
                elif case == "party on continuation":
                    sheet.cell(7, 1).value = "(N)"
                    sheet.cell(7, 2).value = "TEST NOTIFY"
                elif case == "earlier detail":
                    sheet.insert_rows(1)
                    sheet.cell(1, 6).value = "VOSCO123456"
                    sheet.cell(1, 11).value = "ABCU1234571/001237 40HC-C"
                    sheet.cell(2, 6).value = None
                elif case == "earlier weight":
                    sheet.insert_rows(1)
                    sheet.cell(1, 6).value = "VOSCO123456"
                    sheet.cell(1, 19).value = "9 TONS"
                    sheet.cell(2, 6).value = None
                elif case == "later detail":
                    sheet.cell(8, 11).value = "ABCU1234571/001237 40HC-C"
                else:
                    sheet.cell(8, 12).value = "ABCU1234571/001237 40HC-C"
                book.save(path)
                book.close()
                result = parse_manifest(path)
                initial = next(r for r in result["records"] if r["Container_No"] == "ABCU1234569")
                self.assertIsNone(initial["Weight_Value"])
                self.assertTrue(any(i["code"] == "WEIGHT_INVALID" and i["record_id"] == initial["record_id"]
                                    for i in result["issues"]))

    def test_numeric_description_does_not_crash_partial_weight_audit(self):
        result = parse_manifest(self.workbook(123, containers=CONTAINERS, weight="25 TONS"))
        self.assertEqual(len(result["records"]), 2)
        self.assertTrue(any(i["code"] == "WEIGHT_ASSOCIATION_AMBIGUOUS" for i in result["issues"]))

    def test_unknown_short_text_and_malformed_container_remain_review_candidates(self):
        result = parse_manifest(self.workbook("CARGO", containers="ABCU1234567/001234 40HC-C\nABCU12345\nUNEXPECTED-TEXT", weight="25 TONS"))
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(sum(i["code"] == "CONTAINER_UNPARSED" for i in result["issues"]), 2)

    def test_port_metadata_before_between_after_goods_never_shifts_cargo(self):
        for description, expected_source_lines in (
            ("PORT HAIPHONG\nRICE\nSTEEL", [2, 3]),
            ("RICE\nPORT HAIPHONG\nSTEEL", [1, 3]),
            ("RICE\nSTEEL\nPORT HAIPHONG", [1, 2]),
        ):
            with self.subTest(description=description):
                session = process_manifest(self.workbook(description), "VOSCO", settings={"weight_kind": "gross"})
                self.assertEqual([r["Description"] for r in session.records], ["RICE", "STEEL"])
                self.assertEqual([r["raw"]["description_source_lines"] for r in session.records], [[n] for n in expected_source_lines])
                self.assertTrue(all(any(e["kind"] == "port" for e in r["raw"]["description_line_evidence"]) for r in session.records))
                columns, rows = build_port_rows(session)
                self.assertEqual([r[columns.index("Hàng hóa")] for r in rows], ["RICE", "STEEL"])

    def test_other_boilerplate_uses_same_alignment_evidence(self):
        description = "RICE\n\nTotal: 2 containers\nATTACHED LIST\nSTEEL"
        result = parse_manifest(self.workbook(description))
        self.assertEqual([r["Description"] for r in result["records"]], ["RICE", "STEEL"])
        self.assertEqual(result["records"][1]["raw"]["description_source_lines"], [5])

    def test_source_snapshot_keeps_ignored_description_and_unresolved_container(self):
        containers = CONTAINERS.splitlines()[0] + "\nABC 1234568/001235 40HC-C"
        session = process_manifest(self.workbook("RICE\nPORT HAIPHONG\nSTEEL", containers=containers), "VOSCO", settings={"weight_kind": "gross"})
        fragments = session.metadata["source_fragments"]
        ignored = next(item for item in fragments if item["status"] == "ignored")
        self.assertEqual((ignored["text"], ignored["source_column"], ignored["source_line"]), ("PORT HAIPHONG", 15, 2))
        unresolved = next(item for item in fragments if item["status"] == "unresolved")
        self.assertEqual(unresolved["text"], "ABC 1234568/001235 40HC-C")
        self.assertIn(unresolved["record_id"], {record["record_id"] for record in session.records})
        self.assertEqual(session.metadata["coverage"], {"source_fragments": 3, "parsed_fragments": 1, "unresolved_fragments": 1, "ignored_fragments": 1, "corroborating_fragments": 0})
        session.update_record(unresolved["record_id"], {"Container_No": "ABCU1234568", "Size_Type": "40HC", "Seal_No": "001235", "FE_Status": "F"}, "Đối chiếu và nhập lại dòng lỗi")
        self.assertEqual(session.metadata["coverage"]["unresolved_fragments"], 1)

    def test_mixed_type_quantity_declaration_compares_every_type(self):
        containers = "ABCU1234567/001234 20DC-C\nABCU1234568/001235 40HC-C"
        result = parse_manifest(self.workbook("CARGO (01) x20'DC COC, (01) x40'HC COC", containers=containers))
        self.assertFalse(any(i["code"] == "DESCRIPTION_QUANTITY_MISMATCH" for i in result["issues"]))
        mismatch = parse_manifest(self.workbook("CARGO (01) x20'DC COC, (02) x40'HC COC", containers=containers))
        finding = next(i for i in mismatch["issues"] if i["code"] == "DESCRIPTION_QUANTITY_MISMATCH")
        self.assertEqual(finding["details"]["declared"], {"20DC": 1, "40HC": 2})
        self.assertEqual(finding["details"]["row_counts"], {"20DC": 1, "40HC": 1})
        self.assertEqual((finding["source_row"], finding["details"]["source_column"], finding["details"]["quantity_lines"]), (1, 15, [1]))
        self.assertIn("40HC: khai 2, dòng 1, B/L 1", finding["message"])

    def test_quantity_compares_contiguous_bill_occurrence_not_one_row_or_later_repeat(self):
        book = Workbook()
        sheet = book.active
        for number, bill, description in (("ABCU1234567", "VOSCO123456", "CARGO"),
                                          ("ABCU1234568", "", "CARGO (02) x40'HC COC"),
                                          ("ABCU1234569", "VOSCO123456", "CARGO")):
            row = [""] * 19
            row[0], row[1], row[5], row[10], row[14], row[18] = "(C)", "TEST", bill, number + "/001234 40HC-C", description, "25 TONS"
            sheet.append(row)
        path = self.root / "bill_scope.xlsx"
        book.save(path)
        book.close()
        result = parse_manifest(path)
        self.assertFalse(any(i["code"] == "DESCRIPTION_QUANTITY_MISMATCH" for i in result["issues"]))

    def test_row_only_quantity_match_with_larger_bill_stays_ambiguous(self):
        from openpyxl import load_workbook
        path = self.workbook("CARGO (01) x40'HC COC", containers=CONTAINERS.splitlines()[0], weight="25 TONS")
        book = load_workbook(path)
        row = [""] * 19
        row[10], row[14], row[18] = "ABCU1234568/001235 40HC-C", "CARGO", "25 TONS"
        book.active.append(row)
        book.save(path)
        book.close()
        result = parse_manifest(path)
        finding = next(i for i in result["issues"] if i["code"] == "DESCRIPTION_QUANTITY_SCOPE_UNCLEAR")
        self.assertEqual((finding["details"]["row_counts"], finding["details"]["bill_counts"]), ({"40HC": 1}, {"40HC": 2}))

    def test_separate_total_row_reports_its_actual_location(self):
        from openpyxl import load_workbook
        path = self.workbook("STEEL", containers=CONTAINERS.splitlines()[0], weight="25 TONS")
        book = load_workbook(path)
        row = [""] * 19
        row[14] = "TOTAL: (2) x 40HC"
        book.active.append(row)
        book.save(path)
        book.close()
        result = parse_manifest(path)
        finding = next(i for i in result["issues"] if i["code"] == "DESCRIPTION_QUANTITY_MISMATCH")
        self.assertEqual((finding["source_row"], finding["details"]["source_column"], finding["details"]["record_source_row"]), (2, 15, 1))
        self.assertEqual(finding["details"]["declared"], {"40HC": 2})

    def test_multiple_totals_keep_distinct_source_cells(self):
        from openpyxl import load_workbook
        path = self.workbook("STEEL", containers=CONTAINERS.splitlines()[0], weight="25 TONS")
        book = load_workbook(path)
        for label in ("TOTAL: (2) x 40HC", "TOTAL: (3) x 40HC"):
            row = [""] * 19
            row[14] = label
            book.active.append(row)
        book.save(path)
        book.close()
        session = process_manifest(path, "VOSCO")
        findings = [i for i in session.validate() if i["code"] == "DESCRIPTION_QUANTITY_MISMATCH"]
        self.assertEqual([i["source_row"] for i in findings], [2, 3])
        self.assertIn("Ô O2", findings[0]["message"])
        self.assertIn("Ô O3", findings[1]["message"])
        self.assertEqual([i["details"]["source_column"] for i in findings], [15, 15])

    def test_grand_total_omitted_size_is_zero_but_subtotal_is_not(self):
        from openpyxl import load_workbook
        containers = "ABCU1234567/001234 20DC-C\nABCU1234568/001235 40HC-C"
        for label, expected in (("GRAND TOTAL: (1) x20DC", True), ("TOTAL: (1) x20DC", False),
                                ("GRAND TOTAL: (1) x20DC, (1) x40HC", False)):
            with self.subTest(label=label):
                path = self.workbook("STEEL", containers=containers)
                book = load_workbook(path)
                row = [""] * 19
                row[14] = label
                book.active.append(row)
                book.save(path)
                book.close()
                result = parse_manifest(path)
                findings = [i for i in result["issues"] if i["code"] == "DESCRIPTION_QUANTITY_MISMATCH"]
                self.assertEqual(bool(findings), expected)
                if expected:
                    self.assertIn("Ô O2", findings[0]["message"])
                    self.assertIn("40HC: khai 0, B/L 1", findings[0]["message"])
                    self.assertTrue(findings[0]["details"]["grand_total"])

    def test_mass_quantity_and_unrelated_tail_are_not_container_totals(self):
        from openpyxl import load_workbook
        for desc, tail in (("PARTS (2) x 40KG", ""), ("STEEL", "REFERENCE (2) x 40HC")):
            with self.subTest(description=desc, tail=tail):
                path = self.workbook(desc, containers=CONTAINERS.splitlines()[0], weight="25 TONS")
                book = load_workbook(path)
                row = [""] * 19
                row[14] = tail
                book.active.append(row)
                book.save(path)
                book.close()
                result = parse_manifest(path)
                self.assertFalse([i for i in result["issues"] if i["code"].startswith("DESCRIPTION_QUANTITY_")])
                self.assertFalse([i for i in result["issues"] if i["code"] == "DESCRIPTION_REVIEW"])
                self.assertEqual(result["records"][0]["Description"], desc.upper())
                self.assertEqual(result["records"][0]["raw"]["description_cell"], desc)

    def test_unparsed_container_makes_quantity_scope_unclear(self):
        result = parse_manifest(self.workbook("CARGO (02) x40'HC COC", containers="ABCU1234567/001234 40HC-C\nABCU12345/001235 40HC-C"))
        findings = [i for i in result["issues"] if i["code"] == "DESCRIPTION_QUANTITY_SCOPE_UNCLEAR"]
        self.assertTrue(findings)
        self.assertFalse(any(i["code"] == "DESCRIPTION_QUANTITY_MISMATCH" for i in result["issues"]))

    def test_transport_word_is_cargo_not_port_metadata(self):
        result = parse_manifest(self.workbook("TRANSPORT EQUIPMENT\nSTEEL"))
        self.assertEqual([r["Description"] for r in result["records"]], ["TRANSPORT EQUIPMENT", "STEEL"])

    def test_single_container_also_excludes_port_metadata(self):
        result = parse_manifest(self.workbook("PORT HAIPHONG\nRICE", containers=CONTAINERS.splitlines()[0], weight="25 TONS"))
        self.assertEqual(result["records"][0]["Description"], "RICE")
        self.assertEqual(result["records"][0]["raw"]["description_source_lines"], [2])

    def test_insufficient_goods_lines_still_warn_instead_of_claiming_exact(self):
        result = parse_manifest(self.workbook("PORT HAIPHONG\nRICE"))
        self.assertEqual(len(result["records"]), 2)
        self.assertTrue(all(r["Confidence"] < 100 for r in result["records"]))
        self.assertTrue(any(i["code"] == "DESCRIPTION_REVIEW" for i in result["issues"]))

    def test_legacy_low_level_cargo_and_normal_gross(self):
        for weight, expected in (("2 TONS", 2), ("2000 KGS", 2), ("0.01 TONS", 0.01)):
            with self.subTest(weight=weight):
                path = self.workbook("LIGHT CARGO", containers=CONTAINERS.splitlines()[0], weight=weight)
                legacy = parse_manifest(path, settings={"weight_kind": "cargo"})
                self.assertEqual(legacy["records"][0]["FE_Status"], "F")
                session = process_manifest(path, "VOSCO", settings={"weight_kind": "cargo"})
                self.assertEqual(session.records[0]["Weight_Kind"], "gross")
                self.assertEqual(session.records[0]["Weight_Value"], expected)
                self.assertEqual(session.records[0]["FE_Status"], "E")
                columns, rows = build_port_rows(session)
                self.assertEqual(rows[0][columns.index("TL hàng")], expected)

    def test_unknown_keeps_legacy_inference_with_visible_warning(self):
        result = parse_manifest(self.workbook("LIGHT CARGO", containers=CONTAINERS.splitlines()[0], weight="2 TONS"), settings={"weight_kind": "unknown"})
        self.assertEqual(result["records"][0]["FE_Status"], "E")
        self.assertTrue(any(i["code"] == "FE_WEIGHT_KIND_UNCONFIRMED" for i in result["issues"]))
        self.assertEqual(determine_fe("LIGHT CARGO", {"value": 2, "unit": "TONS"}, "40HC", weight_kind="gross"), "E")

    def test_invalid_weight_kind_rejected_including_wrong_type(self):
        path = self.workbook("RICE\nSTEEL")
        for value in ("typo", "CARGO", None, []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "weight_kind"):
                    parse_manifest(path, settings={"weight_kind": value})

    def test_weight_issues_recompute_current_values_and_show_thresholds(self):
        record = {"record_id": "synthetic", "source_row": 5, "source_sheet": "Manifest",
                  "Size_Type": "40HC", "Weight_Value": 7, "Weight_Kind": "gross",
                  "FE_Status": "E", "Description": "EMPTY"}
        warning = current_weight_issues(record)[0]
        self.assertEqual(warning["code"], "EMPTY_WEIGHT_CONFLICT")
        self.assertEqual(warning["resolution_fields"], ["FE_Status", "Weight_Value"])
        self.assertEqual(warning["details"]["weight_tons"], 7)
        self.assertEqual(warning["details"]["threshold_tons"], 4.8)
        self.assertIn("7 tấn", warning["message"])
        self.assertIn("4.8 tấn", warning["message"])
        self.assertIn("vỏ tham chiếu", warning["message"])
        self.assertIn("không phải trọng lượng vỏ thực tế", warning["message"])
        for changes in ({"Weight_Value": 4}, {"FE_Status": "F"}, {"Size_Type": "20TK", "Weight_Value": 5.9},
                        {"Description": "CARGO"}, {"Weight_Value": None}):
            with self.subTest(changes=changes):
                self.assertFalse(current_weight_issues({**record, **changes}))
        self.assertEqual(current_weight_issues({**record, "Size_Type": "20TK"})[0]["details"]["threshold_tons"], 6)
        tank = {**record, "Size_Type": "20TK", "Weight_Value": 7, "FE_Status": "F", "Description": "CARGO"}
        tank_warning = current_weight_issues(tank)[0]
        self.assertEqual(tank_warning["code"], "TANK_WEIGHT_REVIEW")
        self.assertEqual(tank_warning["resolution_fields"], ["FE_Status", "Weight_Value"])
        self.assertEqual((tank_warning["details"]["minimum_tons"], tank_warning["details"]["maximum_tons"]), (5, 12))
        self.assertFalse(current_weight_issues({**tank, "Size_Type": "40HC"}))
        self.assertFalse(current_weight_issues({**tank, "Weight_Value": 13}))
        self.assertFalse(current_weight_issues({**tank, "Weight_Kind": "cargo"}))

    def test_parse_weight_finding_uses_same_current_evaluator(self):
        result = parse_manifest(self.workbook("EMPTY", containers=CONTAINERS.splitlines()[0], weight="25 TONS"))
        record = result["records"][0]
        existing = [i for i in result["issues"] if i["code"] == "EMPTY_WEIGHT_CONFLICT"]
        self.assertEqual(existing, current_weight_issues(record))
        self.assertEqual(record["FE_Status"], "E")

    def test_declared_empty_40ft_reefer_uses_reefer_reference_for_warning(self):
        for size in ("40RF", "40RH"):
            container = f"ABCU1234567/001234 {size}-S"
            for weight, warned in ((5, False), (5.3, False), (5.31, True)):
                with self.subTest(size=size, weight=weight):
                    session = process_manifest(self.workbook("EMPTY", containers=container,
                                                             weight=f"{weight} TONS"), "VOSCO")
                    record, = session.records
                    self.assertEqual((record["FE_Status"], record["Weight_Value"]), ("E", weight))
                    findings = [i for i in session.validate() if i["code"] == "EMPTY_WEIGHT_CONFLICT"]
                    self.assertEqual(bool(findings), warned)
                    if warned:
                        self.assertEqual(findings[0]["details"]["threshold_tons"], 5.3)
                    build_port_rows(session)
        dry = {"Size_Type": "40HC", "FE_Status": "E", "Description": "EMPTY", "Weight_Value": 5}
        self.assertEqual(current_weight_issues(dry)[0]["details"]["threshold_tons"], 4.8)
        tank = {**dry, "Size_Type": "20TK"}
        self.assertFalse(current_weight_issues(tank))
        self.assertEqual(current_weight_issues({**tank, "Weight_Value": 11})[0]["details"]["threshold_tons"], 6)

    def test_legacy_explicit_empty_and_cargo_conflict_remains_visible(self):
        result = parse_manifest(self.workbook("EMPTY", containers=CONTAINERS.splitlines()[0], weight="2 TONS"),
                                settings={"weight_kind": "cargo"})
        self.assertEqual(result["records"][0]["FE_Status"], "E")
        self.assertTrue(any(i["code"] == "EMPTY_CARGO_WEIGHT_CONFLICT" for i in result["issues"]))

    def test_legacy_zero_cargo_and_new_gross_interpretation(self):
        path = self.workbook("LIGHT CARGO", containers=CONTAINERS.splitlines()[0], weight="0 TONS")
        result = parse_manifest(path, settings={"weight_kind": "cargo"})
        self.assertEqual(result["records"][0]["FE_Status"], "F")
        session = process_manifest(path, "VOSCO", settings={"weight_kind": "cargo"})
        self.assertEqual(session.records[0]["Weight_Kind"], "gross")
        self.assertEqual(session.records[0]["Weight_Value"], 0)
        self.assertEqual(session.records[0]["FE_Status"], "E")


if __name__ == "__main__":
    unittest.main()
