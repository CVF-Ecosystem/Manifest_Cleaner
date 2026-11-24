"""Verify a delivered source kit without changing it or downloading anything.

Default: verify SHA-256 entries in PACKAGE_MANIFEST.sha256.
--runtime-only: verify the selected Python, tkinter and pinned dependencies.
--tests: verify checksums/runtime, then run the existing regression suite.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import os
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def verify_manifest(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    manifest = root / "PACKAGE_MANIFEST.sha256"
    if not manifest.is_file():
        return 0, ["Missing PACKAGE_MANIFEST.sha256; verify the complete extracted source kit."]
    checked = 0
    failures = []
    seen = set()
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-fA-F0-9]{64})  (.+)", line)
        if not match:
            failures.append(f"Invalid manifest line {line_number}.")
            continue
        expected, relative = match.groups()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or Path(relative).is_absolute():
            failures.append(f"Unsafe manifest path at line {line_number}.")
            continue
        if path in seen:
            failures.append(f"Duplicate manifest entry: {relative}")
            continue
        seen.add(path)
        if not path.is_file():
            failures.append(f"Missing file: {relative}")
            continue
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            failures.append(f"Cannot read {relative}: {exc}")
            continue
        checked += 1
        if digest.hexdigest() != expected.lower():
            failures.append(f"Changed bytes: {relative}")
    if not checked and not failures:
        failures.append("The package manifest is empty.")
    return checked, failures


def verify_runtime(root: Path) -> list[str]:
    failures = []
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        failures.append("Use Python 3.10-3.13; the source kit recommends Python 3.12.")
    if struct.calcsize("P") != 8:
        failures.append("Use a 64-bit Python installation.")
    for module in ("tkinter", "pandas", "openpyxl", "xlsxwriter", "xlrd"):
        try:
            importlib.import_module(module)
        except Exception as exc:
            failures.append(f"Cannot import {module}: {exc}")
    requirements = root / "requirements.txt"
    if not requirements.is_file():
        failures.append("Missing requirements.txt.")
        return failures
    for line in requirements.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            failures.append(f"Unrecognized pinned dependency line: {line}")
            continue
        name, expected = match.groups()
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"Missing dependency: {name}=={expected}")
            continue
        if actual != expected:
            failures.append(f"Dependency mismatch: {name}=={actual}; expected {expected}")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Extracted source-kit directory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--runtime-only", action="store_true", help="Check Python/imports/pins without checksums or display access")
    modes.add_argument("--tests", action="store_true", help="After successful checksum/runtime checks, run unittest discovery")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    failures = []
    if not args.runtime_only:
        checked, failures = verify_manifest(root)
        print(f"Checksum entries read: {checked}")
    if args.runtime_only or args.tests:
        failures.extend(verify_runtime(root))
        print(f"Python: {sys.version.split()[0]} ({struct.calcsize('P') * 8}-bit)")
    if failures:
        for failure in failures:
            print("FAIL:", failure, file=sys.stderr)
        return 1
    print("PASS: requested source-kit/runtime checks completed.")
    if args.tests:
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                              cwd=root, env=environment, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
