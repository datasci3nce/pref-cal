#!/usr/bin/env python3
"""Build the current public GitHub release archive after all integrity checks pass."""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "PREF-CAL"
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".synctex.gz"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    return (
        path.is_file()
        and not any(part in EXCLUDED_PARTS for part in rel.parts)
        and not any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)
    )


def run_checks() -> None:
    commands = [
        [sys.executable, "scripts/regenerate_manifest.py", "--check"],
        [sys.executable, "scripts/verify_release.py"],
        [sys.executable, "scripts/reproduce_report_numbers.py", "--check"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "PREF_CAL_GitHub_Release_2026-08-17_FIXED.zip",
    )
    args = parser.parse_args()
    run_checks()
    files = sorted((p for p in ROOT.rglob("*") if included(p)), key=lambda p: p.as_posix())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, arcname=f"{ARCHIVE_ROOT}/{path.relative_to(ROOT).as_posix()}")
    print(args.output)
    print(f"{len(files)} files, {args.output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
