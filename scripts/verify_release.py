#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prefcal.release_audit import audit_release
from prefcal.common import load_json


def main() -> None:
    report = audit_release(ROOT)
    gpt = report["systems"]["GPT-OSS-120B"]
    llama = report["systems"]["Llama-3.3-70B (partial)"]
    semantic = gpt["source_recomputation"]["factors"]["semantic_swap"]
    assert gpt["rows"] == 148
    assert gpt["methods"] == {
        "M1_EXAMPLE_FREE_RANKING": 12,
        "M2_FACTORIAL_SOURCE_CHOICE": 96,
        "N1_FORCED_EQUIVALENCE": 20,
        "N2_TIE_ALLOWED_EQUIVALENCE": 20,
    }
    assert semantic["matches"] == 7 and semantic["contrasts"] == 48
    assert semantic["best_case_final_rate"] == 0.74375
    assert semantic["frozen_75_percent_gate_reachable"] is False
    assert report["gpt_oss_terminal_verdict"]["status"] == "STOP_PROSPECTIVE_DETERMINISTIC_FUTILITY"
    assert report["gpt_oss_terminal_verdict"]["transport_run"] is False
    assert llama["rows"] == 69
    assert llama["methods"]["M2_FACTORIAL_SOURCE_CHOICE"] == 17
    assert llama["source_recomputation"]["complete_blocks"] == []

    gpt_slice = gpt["matched_M2P00_AB_slice"]
    llama_slice = llama["matched_M2P00_AB_slice"]
    assert (gpt_slice["identifier_A"], gpt_slice["physical_left"]) == (16, 8)
    assert (llama_slice["identifier_A"], llama_slice["physical_left"]) == (9, 13)

    # Verify that the machine-readable claim contract stays synchronized with
    # the frozen configuration and the observed prospective stop.
    contract = load_json(ROOT / "CLAIM_CONTRACT.json")
    cfg = load_json(ROOT / "configs" / "prefcal_nvidia_gpt_oss.json")
    source = contract["source_qualification"]
    assert source["min_parse_rate"] == cfg["gates"]["min_parse_rate"]
    assert source["min_n2_tie_rate"] == cfg["gates"]["min_m2_tie_rate"]
    assert source["min_m2_factor_consistency"] == cfg["gates"]["min_m2_factor_consistency"]
    assert source["deterministic_futility"]["check_after_complete_m2_blocks"] == cfg["stopping"]["check_after_complete_m2_blocks"]
    assert contract["transport"]["requires_source_qualification"] is cfg["stopping"]["transport_requires_source_qualification"]
    assert report["gpt_oss_terminal_verdict"]["source_qualified"] is False
    assert report["gpt_oss_terminal_verdict"]["transport_run"] is False
    assert contract["failure_semantics"]["source_gate_failure"] == "DO_NOT_ATTACH_PREFERENCE_SEMANTICS"

    print(json.dumps({"status": "PASS", "claim_contract": "PASS", "audit": report}, indent=2))


if __name__ == "__main__":
    main()
