"""Reproducible synthetic manifest inputs; contains no real shipping records."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import Workbook
from manifest_cleaner.carriers.vinafco.profile import INPUT_COLUMNS


def create_vosco(path, *, weight="16.055 TONS", description="GẠO DEMO", consignee="DEMO CONSIGNEE"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Manifest"
    for index in range(16):
        row = [""] * 19
        row[0] = "DU LIEU GIA LAP - KHONG PHAI MANIFEST THUC" if index == 0 else f"HEADER {index + 1}"
        if index == 15:
            row[10] = "Container and seal number"
        sheet.append(row)
    row = [""] * 19
    row[0], row[1], row[5] = "(C)", consignee, "VOSCO900001"
    row[10], row[14], row[18] = "DEMU0000001/001234 40GP-C", description, weight
    sheet.append(row)
    book.save(path)
    book.close()
    return path


def create_vimc(path, *, weight=16.055, description="THEP DEMO", consignee="DEMO CONSIGNEE", extra_lines=()):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Manifest"
    sheet.append(["DU LIEU GIA LAP - KHONG PHAI MANIFEST THUC"])
    sheet.append(["PARTICULARS FURNISHED BY SHIPPER", "MARKS & NUMBERS", "B/L", "DISCRIPTION OF GOODS"])
    sheet.append(["B/L NO:", "", "DEMO-VIMC-001", "COC LADEN"])
    sheet.append([f"1) DEMO SHIPPER\n2) {consignee}\n3) SAME AS CONSIGNEE", "", "", ""])
    sheet.append(["", "", "", f"DEMU0000002 001235 20GP {weight} {description}"])
    for line in extra_lines:
        sheet.append(["", "", "", line])
    book.save(path)
    book.close()
    return path


def create_vinafco(path, *, weight=16.055, description="GẠCH DEMO", consignee="DEMO CONSIGNEE"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Manifest"
    sheet.append(["DU LIEU GIA LAP - KHONG PHAI MANIFEST THUC"])
    sheet.append(list(INPUT_COLUMNS.values()))
    fields = list(INPUT_COLUMNS)
    def row(**values):
        return [values.get(field, "") for field in fields]
    sheet.append(row(party_raw="(S) DEMO SHIPPER", bill_no="DEMO-VINAFCO-001"))
    sheet.append(row(party_raw="(C) " + consignee))
    sheet.append(row(container_no="DEMU0000003", seal="001236", type="20DC", comm=description, gw=weight))
    book.save(path)
    book.close()
    return path


CREATORS = {"VOSCO": create_vosco, "VIMC": create_vimc, "VINAFCO": create_vinafco}


def create_samples(destination):
    from manifest_cleaner.engine import process_manifest
    from manifest_cleaner.exporter import export_port_excel
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for carrier, create in CREATORS.items():
        options = {}
        if carrier == "VIMC":
            options["extra_lines"] = (
                "DEMU0000004 001237 40HC VO LON DEMO 8000",
                "DEMU0000005 001238 20DC GACH MEN DEMO 27,000",
            )
        source = create(destination / f"DEMO_{carrier}_INPUT.xlsx", **options)
        session = process_manifest(source, carrier)
        export_port_excel(session, destination / f"DEMO_{carrier}_EXPECTED.xlsx", overwrite=True)
        # Keep the bundled demos portable. Normal user sessions keep the full
        # source path and can be relocated with the GUI/CLI when necessary.
        session.metadata["source_path"] = source.name
        session.save_review(destination / f"DEMO_{carrier}_REVIEW.json")
    source = create_vimc(destination / "DEMO_VIMC_NEEDS_REVIEW.xlsx", consignee="",
                         extra_lines=("DEMU0000006 001239 20GP 20 STEEL DEMO 12000",))
    session = process_manifest(source, "VIMC")
    session.metadata["source_path"] = source.name
    session.save_review(destination / "DEMO_VIMC_NEEDS_REVIEW.json")
    (destination / "README.txt").write_text(
        "TAT CA FILE TRONG THU MUC NAY LA DU LIEU GIA LAP, KHONG CO KHACH HANG THUC.\n\n"
        "1. Mo ung dung, chon hang VOSCO/VIMC/VINAFCO.\n"
        "2. Chon dung DEMO_<HANG>_INPUT.xlsx; moi lan chi xu ly mot manifest.\n"
        "3. Xem bang ket qua; xuat voi ten moi va so sanh DEMO_<HANG>_EXPECTED.xlsx.\n"
        "4. VIMC demo co ca dang trong luong truoc (tan) va sau (kg), khong chon ten tau.\n"
        "5. DEMO_VIMC_NEEDS_REVIEW.xlsx co chu y thieu chu hang va mot dong mo ho.\n"
        "   Ung dung phai giu cac dong, hien loi va yeu cau kiem tra truoc khi xuat.\n"
        "6. File REVIEW.json v2 mo lai duoc bang Mo phien da luu; giu file INPUT.xlsx cung thu muc.\n"
        "   File JSON luu bang chung nguon va lich su; khong dung de import vao Cang.\n"
        "7. EXPECTED.xlsx o thu muc samples duoc tao bang chinh chuong trinh, chi de thu thao tac.\n"
        "   Golden kiem chung doc lap nam o tests/fixtures/golden_v110 (ky vong viet tay).\n"
        "   Ca hai bo deu la du lieu tong hop, chua duoc he thong Cang xac nhan.\n\n"
        "Tao lai bo demo: python scripts/create_samples.py --output samples\n",
        encoding="utf-8")
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "samples")
    args = parser.parse_args(argv)
    print(create_samples(args.output).resolve())


if __name__ == "__main__":
    main()
