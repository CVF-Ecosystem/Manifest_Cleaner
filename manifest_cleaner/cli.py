"""Local CLI useful for automation and reproducing a single manifest result."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import CARRIERS, load_review, load_settings, process_manifest
from .exporter import export_port_bundle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Xử lý một manifest của một hãng tàu, không phân loại theo tên tàu.")
    parser.add_argument("input", type=Path, nargs="?", help="File manifest XLS/XLSX/XLSM")
    parser.add_argument("--carrier", choices=CARRIERS)
    parser.add_argument("--resume", type=Path, help="Mở lại phiên đối chiếu v2 đã lưu, giữ các chỉnh sửa")
    parser.add_argument("--source", type=Path, help="Đường dẫn mới của đúng manifest nguồn khi mở lại phiên")
    parser.add_argument("--output", type=Path, help="File Excel nhập Cảng")
    parser.add_argument("--review", type=Path, help="Lưu JSON đối chiếu gồm dữ liệu gốc và lỗi")
    parser.add_argument("--settings", type=Path, help="Cấu hình hãng tàu JSON")
    parser.add_argument("--sheet", help="Chọn một sheet nguồn cụ thể")
    parser.add_argument("--no-review", action="store_true", help="Chỉ xuất Excel; mặc định xuất kèm .review.json")
    parser.add_argument("--overwrite", action="store_true", help="Cho phép ghi đè file xuất đã có, không ghi đè nguồn")
    args = parser.parse_args(argv)
    if args.resume:
        if args.input or args.carrier or args.settings or args.sheet:
            parser.error("--resume dùng đúng hãng/cấu hình đã lưu; không kết hợp input, --carrier, --settings hoặc --sheet.")
    elif not args.input or not args.carrier:
        parser.error("Cần một input và --carrier, hoặc dùng --resume.")
    if args.source and not args.resume:
        parser.error("--source chỉ dùng để nối lại nguồn của --resume.")
    if args.no_review and args.review:
        parser.error("Không kết hợp --no-review với --review.")
    if args.output and args.output.suffix.lower() != ".xlsx":
        parser.error("--output phải là file .xlsx.")
    if args.review and args.review.suffix.lower() != ".json":
        parser.error("--review phải là file .json.")
    if args.input and any(p and p.resolve() == args.input.resolve() for p in (args.output, args.review)):
        parser.error("Không ghi đè manifest nguồn bằng file xuất hoặc đối chiếu.")
    try:
        if args.resume:
            session = load_review(args.resume, source_path=args.source)
        else:
            config = load_settings(args.settings)[args.carrier]
            if args.sheet:
                config["selected_sheet"] = args.sheet
            session = process_manifest(args.input, args.carrier, settings=config)
            session.metadata["settings_source"] = str(args.settings.resolve()) if args.settings else "defaults"
        stats = session.statistics()
        print(json.dumps({"carrier": session.carrier, "session_id": session.metadata.get("session_id"),
                          "effective_settings": session.settings, "used_sheets": session.metadata.get("used_sheets", []),
                          "statistics": stats, "issues": session.validate()}, ensure_ascii=False, indent=2))
        if args.output:
            if stats["errors"]:
                review_target = None if args.no_review else (args.review or args.output.with_suffix(".review.json"))
                # A failed export must not split an existing Excel/review pair.
                # --overwrite authorises replacing a valid bundle, not just its
                # review when blocking errors prevent producing the Excel.
                if args.output.exists() or (review_target and review_target.exists()):
                    raise ValueError(
                        f"Còn {stats['errors']} lỗi nên chưa thể xuất Excel. "
                        "File đích Excel hoặc đối chiếu đã tồn tại; giữ nguyên toàn bộ file đích "
                        "kể cả khi có --overwrite. Muốn lưu báo cáo lỗi, chạy riêng --review "
                        "với tên file mới và bỏ --output."
                    )
                if args.review:
                    # Preserve the first-time error-report workflow. Never
                    # overwrite a report as a side effect of a failed export.
                    session.save_review(args.review, overwrite=False)
                raise ValueError(
                    f"Còn {stats['errors']} lỗi cần xử lý trước khi xuất file nhập Cảng. "
                    + ("Đã lưu bản đối chiếu JSON theo đường dẫn --review." if args.review
                       else "Có thể lưu bản đối chiếu JSON bằng --review với tên file mới.")
                )
            result = export_port_bundle(session, args.output, overwrite=args.overwrite,
                                        include_review=not args.no_review, review_path=args.review)
            print(json.dumps({name: str(value) if value else None for name, value in result.items()}, ensure_ascii=False))
        elif args.review:
            session.save_review(args.review, overwrite=args.overwrite)
        return 2 if stats["errors"] else 0
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
