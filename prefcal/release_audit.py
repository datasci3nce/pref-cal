from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


M2_METHOD = "M2_FACTORIAL_SOURCE_CHOICE"
M2_FACTORS = ("scheme", "semantic_swap", "identifier_swap", "answer_order_swap", "template_idx")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at {path}:{line_number}: {error}") from error
    return rows


def _factor_contrasts(rows: Iterable[dict[str, Any]], factor: str) -> tuple[int, int]:
    other_factors = [name for name in M2_FACTORS if name != factor]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            tuple(row["pair"]),
            row["source_block_id"],
            *[row[name] for name in other_factors],
        )
        groups[key].append(row)
    matches = 0
    contrasts = 0
    for group in groups.values():
        if len(group) != 2:
            continue
        contrasts += 1
        choices = [row.get("semantic_choice") for row in group]
        if choices[0] is not None and choices[0] == choices[1]:
            matches += 1
    return matches, contrasts


def _successful_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest = {row["episode_id"]: row for row in rows}
    return {episode_id: row for episode_id, row in latest.items() if not row.get("error")}


def recompute_source_factors(
    design: dict[str, Any], raw_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    successes = _successful_records(raw_rows)
    m2_design = [episode for episode in design["episodes"] if episode["method"] == M2_METHOD]
    planned_blocks = sorted({episode["source_block_id"] for episode in m2_design})
    complete_blocks: list[str] = []
    partial_blocks: list[str] = []
    for block in planned_blocks:
        expected = {episode["episode_id"] for episode in m2_design if episode["source_block_id"] == block}
        observed = expected & successes.keys()
        if observed == expected:
            complete_blocks.append(block)
        elif observed:
            partial_blocks.append(block)

    complete_rows: list[dict[str, Any]] = []
    for episode in m2_design:
        if episode["source_block_id"] not in complete_blocks:
            continue
        record = successes[episode["episode_id"]]
        complete_rows.append(
            {
                **episode,
                "semantic_choice": episode["identifier_to_family"].get(record.get("parsed")),
            }
        )

    factors: dict[str, dict[str, float | int | bool]] = {}
    for factor in M2_FACTORS:
        matches, contrasts = _factor_contrasts(complete_rows, factor)
        _, planned_contrasts = _factor_contrasts(m2_design, factor)
        remaining = planned_contrasts - contrasts
        best_matches = matches + remaining
        best_rate = best_matches / planned_contrasts
        factors[factor] = {
            "matches": matches,
            "contrasts": contrasts,
            "observed_rate": matches / contrasts if contrasts else 0.0,
            "planned_contrasts": planned_contrasts,
            "best_case_final_matches": best_matches,
            "best_case_final_rate": best_rate,
            "frozen_75_percent_gate_reachable": best_rate >= 0.75,
        }
    return {
        "complete_blocks": complete_blocks,
        "partial_blocks": partial_blocks,
        "complete_rows": len(complete_rows),
        "factors": factors,
    }


def matched_slice(design: dict[str, Any], raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = _successful_records(raw_rows)
    episodes = [
        episode
        for episode in design["episodes"]
        if episode.get("source_block_id") == "M2P00" and episode.get("scheme") == "AB"
    ]
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        record = successes.get(episode["episode_id"])
        if record is None:
            continue
        parsed = record.get("parsed")
        rows.append(
            {
                **episode,
                "parsed": parsed,
                "semantic_choice": episode["identifier_to_family"].get(parsed),
            }
        )

    factor_names = ("semantic_swap", "identifier_swap", "answer_order_swap", "template_idx")
    consistency = {}
    for factor in factor_names:
        matches, contrasts = _factor_contrasts(rows, factor)
        consistency[factor] = {
            "matches": matches,
            "contrasts": contrasts,
            "rate": matches / contrasts if contrasts else None,
        }
    return {
        "expected_conditions": len(episodes),
        "observed_conditions": len(rows),
        "identifier_A": sum(row.get("parsed") == "A" for row in rows),
        "physical_left": sum(row.get("parsed") == row["left_identifier"] for row in rows),
        "consistency": consistency,
        "episode_ids": [row["episode_id"] for row in rows],
    }


def audit_release(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    specifications = {
        "GPT-OSS-120B": {
            "directory": root / "artifacts" / "gpt_oss",
            "model_name": "nvidia_gpt_oss_120b_v14",
            "expected_design_hash": "312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b",
        },
        "Llama-3.3-70B (partial)": {
            "directory": root / "artifacts" / "llama_partial",
            "model_name": "nvidia_llama_3_3_70b_v14",
            "expected_design_hash": "3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a",
        },
    }
    output: dict[str, Any] = {"protocol_version": "PREF-CAL v1.4", "systems": {}}
    for name, spec in specifications.items():
        directory = spec["directory"]
        design_path = directory / "design" / "design.json"
        raw_path = directory / "raw" / f"{spec['model_name']}.jsonl"
        design = load_json(design_path)
        raw = load_jsonl(raw_path)
        if design["design_hash"] != spec["expected_design_hash"]:
            raise ValueError(f"Unexpected design hash for {name}: {design['design_hash']}")
        if len({row["episode_id"] for row in raw}) != len(raw):
            raise ValueError(f"Duplicate episode IDs in {name}")
        if not all(row.get("parse_valid") for row in raw):
            raise ValueError(f"Invalid parse in archived {name} rows")
        methods = dict(sorted(Counter(row["method"] for row in raw).items()))
        output["systems"][name] = {
            "rows": len(raw),
            "methods": methods,
            "design_hash": design["design_hash"],
            "design_file_sha256": sha256_file(design_path),
            "raw_file_sha256": sha256_file(raw_path),
            "source_recomputation": recompute_source_factors(design, raw),
            "matched_M2P00_AB_slice": matched_slice(design, raw),
        }

    verdict_path = (
        root
        / "artifacts"
        / "gpt_oss"
        / "analysis"
        / "nvidia_gpt_oss_120b_v14"
        / "stage_verdict.json"
    )
    verdict = load_json(verdict_path)
    output["gpt_oss_terminal_verdict"] = {
        "status": verdict["status"],
        "source_qualified": verdict["source_qualified"],
        "transport_run": verdict["transport_run"],
        "reason": verdict["reason"],
        "sha256": sha256_file(verdict_path),
    }
    return output


def save_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

