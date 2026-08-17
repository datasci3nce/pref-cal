#!/usr/bin/env python3
"""Regenerate or verify the repository SHA-256 manifest.

The manifest covers release files, not ephemeral local/build metadata.  In
``--check`` mode the script reports changed, extra, or missing paths to make CI
failures diagnosable instead of only reporting that the manifest is stale.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".aux",
    ".bbl",
    ".blg",
    ".log",
    ".out",
    ".toc",
    ".synctex.gz",
}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    return (
        path.is_file()
        and path != MANIFEST
        and not any(part in EXCLUDED_PARTS for part in rel.parts)
        and not any(part.endswith(".egg-info") for part in rel.parts)
        and not any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)
    )


def current_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in sorted((p for p in ROOT.rglob("*") if included(p)), key=lambda p: p.as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rel = f"./{path.relative_to(ROOT).as_posix()}"
        entries[rel] = digest
    return entries


def render_manifest(entries: dict[str, str] | None = None) -> str:
    entries = current_entries() if entries is None else entries
    return "".join(f"{digest}  {rel}\n" for rel, digest in sorted(entries.items()))


def parse_manifest(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError as exc:
            raise SystemExit(f"Malformed MANIFEST.sha256 line {lineno}: {line!r}") from exc
        entries[rel] = digest
    return entries


def report_difference(recorded: dict[str, str], current: dict[str, str]) -> None:
    changed = sorted(path for path in recorded.keys() & current.keys() if recorded[path] != current[path])
    extra = sorted(current.keys() - recorded.keys())
    missing = sorted(recorded.keys() - current.keys())

    if changed:
        print("Changed bytes:")
        for path in changed[:50]:
            print(f"  {path}")
    if extra:
        print("Unmanifested files present:")
        for path in extra[:50]:
            print(f"  {path}")
    if missing:
        print("Manifested files missing:")
        for path in missing[:50]:
            print(f"  {path}")
    total = len(changed) + len(extra) + len(missing)
    if total > 50:
        print(f"  ... {total - 50} additional differences not shown")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if MANIFEST.sha256 is stale.")
    args = parser.parse_args()

    current = current_entries()
    expected = render_manifest(current)

    if args.check:
        actual = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if actual != expected:
            recorded = parse_manifest(actual) if actual else {}
            report_difference(recorded, current)
            raise SystemExit("MANIFEST.sha256 is stale; run scripts/regenerate_manifest.py")
        print("MANIFEST CHECK: PASS")
        return

    MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST} with {len(current)} entries")


if __name__ == "__main__":
    main()
