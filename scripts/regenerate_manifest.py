#!/usr/bin/env python3
"""Regenerate or verify the repository SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"

EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".synctex.gz"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    return (
        path.is_file()
        and path != MANIFEST
        and not any(part in EXCLUDED_PARTS for part in rel.parts)
        and not any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)
    )


def render_manifest() -> str:
    lines: list[str] = []
    for path in sorted((p for p in ROOT.rglob("*") if included(p)), key=lambda p: p.as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"{digest}  ./{rel}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if MANIFEST.sha256 is stale.")
    args = parser.parse_args()
    expected = render_manifest()
    if args.check:
        actual = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if actual != expected:
            raise SystemExit("MANIFEST.sha256 is stale; run scripts/regenerate_manifest.py")
        print("MANIFEST CHECK: PASS")
        return
    MANIFEST.write_text(expected, encoding="utf-8")
    print(f"Wrote {MANIFEST} with {len(expected.splitlines())} entries")


if __name__ == "__main__":
    main()
