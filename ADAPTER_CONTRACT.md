# Internal adapter and session contract — 1.1.0

## Scope and entry points

One carrier and one workbook per session. Select VOSCO, VIMC or VINAFCO explicitly; never dispatch by vessel name. Carrier code lives under `manifest_cleaner/carriers/<carrier>/` and must remain independent of Tkinter and networking.

`adapter.parse_manifest(path, *, settings=None, progress=None)` returns a dictionary containing `records`, `issues` and `metadata`. Application callers should use `engine.process_manifest()` so settings validation, source hashes and workbook formula checks are applied. Direct adapter entry points are intended for carrier development and focused tests.

`process_manifest(path, carrier, *, settings=None, progress=None)` returns a `ManifestSession`. Settings are canonicalized by `validate_carrier_settings`: known keys only; `number_format` is `legacy`, `decimal_comma` or `decimal_dot`; `weight_kind` is `gross`, `cargo` or `unknown`; optional `selected_sheet` is an exact sheet name. Existing VOSCO `sheet_name` and VINAFCO `target_sheet_name` aliases remain accepted. `load_settings(None)` loads defaults; an explicitly missing or malformed file fails.

## Records and evidence

Records use `record_id` (unique within the input), `BL_No`, `Master_BL_Group_ID`, `Container_No`, `Seal_No`, `Size_Type` (source type), `VTOS_Size` (port mapping), `Operator`, `FE_Status`, `Weight_Value` (tonnes, float or None), `Weight_Unit` (TONS or None), `Weight_Kind`, `Description`, `Cargo_Type`, `Shipper`, `Consignee`, `Notify`, `Cleaned_Consignee_Name_For_Output`, `Confidence`, `Warning`, `source_file`, `source_sheet`, `source_row`, `raw` and `rules`.

`source_row`, `source_column` and `source_line` in evidence are 1-based. Missing values remain empty/None and produce the appropriate issue. Do not discard an identified container candidate because its B/L, consignee, type or weight is missing. Preserve original strings and positions under `raw`; normalization applies to output values. `raw.weight_source_unit` records the actual parsed source unit, including explicit per-cell overrides.

`Confidence` remains a legacy rule/completeness score for output compatibility. It is not measured accuracy or a probability of correctness.

`metadata.source_fragments` contains recorded source evidence with `source_sheet`, `source_row`, optional `source_column`/`source_line`, `text`, `status`, `reason` and optional `record_id`. Status is `parsed`, `unresolved`, `ignored` or `corroborating`. `metadata.coverage` counts those fragments at parse time. It is not a denominator for whole-workbook accuracy and must not be silently rewritten after manual edits. Carrier scopes differ; VOSCO records candidate lines and excluded/quantity description evidence, VIMC records extracted structural fragments, VINAFCO records table rows and header boundaries.

Return every recognised table sheet in `metadata.sheets_used` or the chosen single sheet in `metadata.source_sheet`. A recognised sheet that yields no records still needs formula/cache validation. `process_manifest` combines this information with record locations, unless `selected_sheet` explicitly limits the scope.

## Issues and manual correction

Issues contain `code`, `severity` (`error`, `warning`, `info`), Vietnamese `message`, optional `record_id`, `field`, `source_row` and `source_sheet`. Missing required values, unresolved container candidates and unsafe weight association are errors. File-level errors have no record ID and cannot be resolved by editing/excluding an unrelated record.

Coupled issues declare `resolution_fields`, for example `['Weight_Value', 'Description']`. All those fields must be changed or explicitly verified. `ManifestSession.update_record(record_id, changes, reason, *, verified_fields=None)` tracks actual changes separately from explicit verification. Submitting unchanged fields is a no-op unless they are listed in `verified_fields`. Reasons are required. Validate the complete proposed update before mutating the original record.

`acknowledge_record()` records a general review reason and does not dismiss unresolved errors. `set_excluded()` keeps the record and evidence, records a reason and excludes the row from export. `refresh_derived_fields(record, settings=None)` recomputes mappings after edits without re-inferring F/E or replacing cargo descriptions. `is_supported_size_type()` validates accepted source/port aliases and configured mappings.

## Source integrity and session files

`common.inspect_workbook_source()` inspects XLSX/XLSM XML for formula cells with missing/error cached results, without evaluating formulas. Relevant-sheet failures are file-level errors. XLS is supported for parsing, but equivalent formula-cache completeness inspection is unavailable and recorded as such.

`ManifestSession.save_review(path, *, overwrite=True)` writes JSON through a temporary file and atomic per-file replacement. Callers exposing an overwrite decision must pass it explicitly or obtain it through the Save As dialog.

`engine.load_review(path, *, source_path=None)` restores version 2 sessions without reparsing the manifest or dropping manual corrections. Format is `manifest-cleaner-review-v2`, `schema_version=2`. It checks payload SHA-256, record structure and the source workbook SHA-256. Relative source paths are resolved beside the review JSON; ordinary user sessions store absolute paths. `source_path` allows relocation only when bytes match. Review JSON from version 1.0 is a report, not a supported resumable session; open the original manifest in 1.1 instead.

The payload hash detects accidental corruption or inconsistent saves. It is not a signature proving who edited a file. Resume uses the settings stored with the processed session and clears a pending-settings-change marker; the GUI restores those saved settings without rewriting `settings.json`.

## Export contract

`exporter.build_port_rows(session)` validates before producing the carrier's existing 16-column schema. `preview_record_for_export(session, record)` uses the same field mapping, quantity scope and rounding while allowing inspection of an unfinished row. Preview never disables the real export gate.

`export_port_excel(session, path, *, overwrite=False)` writes one workbook, checks source integrity and preserves text identifiers such as seal numbers. Strings are written as text; they are not evaluated as formulas. VIMC/VINAFCO round weight at export to two decimals with the existing pandas convention. VOSCO keeps its established precision. Existing VTOS/operator/cargo mappings, Master B/L grouping and EMPTY output rules remain carrier-specific.

`export_port_bundle(session, path, *, overwrite=False, include_review=True, review_path=None)` is the normal GUI/CLI path. Default review name is `<output-stem>.review.json`; a custom JSON destination may be in a different directory. It stages both files, checks both destinations, backs up existing outputs separately from prepared files, then commits. Caught commit failures trigger rollback; failed rollback retains recovery copies and reports their locations. Replacement is atomic per file, not a filesystem-wide or power-loss-safe transaction across two files.

Excel custom properties contain app version, carrier, session ID and source hash. Review metadata records the exported Excel hash, allowing the pair to be checked without adding visible columns or worksheets.

## Maintenance and tests

Use unittest; tests may build synthetic workbooks. Frozen golden expectations in `tests/fixtures/golden_v110` were authored separately from parser/exporter outputs. Do not regenerate them from application output. `scripts/create_samples.py` generates interactive demo outputs and is deliberately separate from the independent golden corpus.

Change business mappings only with an explicit source/business decision and a regression case. Run the relevant tests while developing and the full suite before packaging. See `docs/VALIDATION_REPORT.md` for the actual release run and `docs/WINDOWS_RELEASE_CHECKLIST.md` for work that still requires a Windows/port environment.
