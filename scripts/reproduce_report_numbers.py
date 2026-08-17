#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prefcal.release_audit import audit_release, save_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce the PREF-CAL report numbers.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "reproduced" / "report_numbers.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the recomputed report numbers with the archived snapshot without rewriting it.",
    )
    args = parser.parse_args()
    result = audit_release(ROOT)
    if args.check:
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        if result != expected:
            raise SystemExit(f"Archived report-number snapshot differs from recomputation: {args.output}")
        print(json.dumps({"status": "PASS", "snapshot": str(args.output)}, indent=2))
        return
    save_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
