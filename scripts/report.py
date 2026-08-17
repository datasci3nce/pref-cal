#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefcal.common import load_json


parser = argparse.ArgumentParser()
parser.add_argument('--output-run', required=True)
args = parser.parse_args()
run = Path(args.output_run)
final = load_json(run / 'analysis' / 'final_summary.json')

lines = [
    f'# PREF-CAL v{final.get("protocol_version", "1.4")} results',
    '',
    f'**Design hash:** `{final["design_hash"]}`',
    '',
    final['claim_boundary'],
    '',
    f'**Lineage:** {final["lineage"]}',
    '',
    '## Model summaries',
    '',
]
for model in final['models']:
    controls = model['method_controls']
    action_counts = model['action_transport_counts']
    allocation_counts = model['allocation_transport_counts']
    lines += [
        f'### {model["model_name"]}',
        '',
        f'- Qualified controls/interfaces: `{model["method_qualified"]}`',
        f'- Action transported: **{action_counts.get("ACTION_TRANSPORTED", 0)}/10**',
        f'- Failed action transport: **{action_counts.get("FAILED_ACTION_TRANSPORT", 0)}/10**',
        f'- Source robust, target insufficient: **{action_counts.get("SOURCE_ROBUST_TARGET_INSUFFICIENT", 0)}/10**',
        f'- Surface not identified: **{action_counts.get("SURFACE_NOT_IDENTIFIED", 0)}/10**',
        f'- Allocation transported: **{allocation_counts.get("ALLOCATION_TRANSPORTED", 0)}/10**',
        f'- Failed allocation transport: **{allocation_counts.get("FAILED_ALLOCATION_TRANSPORT", 0)}/10**',
        f'- M1 reversal tau: **{controls["M1"]["reversal_tau_mean"]:.3f}** (diagnostic only)',
        f'- M2 tie-equivalence rate: **{controls["M2"]["tie_equivalence_rate"]:.3f}**',
        f'- M3 completion-valid rate: **{controls["M3"]["completion_valid_rate"]:.3f}**',
        f'- M4 median template tau: **{controls["M4"]["template_pair_median_tau"]:.3f}**',
        f'- M4 mean template total variation: **{controls["M4"]["template_pair_mean_total_variation"]:.3f}**',
        '',
        'M2 matched-factor consistency:',
        '',
        '| Factor | Rate | 90% CI |',
        '|---|---:|---:|',
    ]
    for factor, values in controls['M2']['factor_consistency'].items():
        lines.append(f'| {factor} | {values["rate"]:.3f} | [{values["ci"][0]:.3f}, {values["ci"][1]:.3f}] |')
    lines += [
        '',
        'Pair-level bridge verdicts:',
        '',
        '| Pair | Source | Action | Allocation | Action verdict | Allocation verdict |',
        '|---|---:|---:|---:|---|---|',
    ]
    verdicts = pd.read_csv(run / 'analysis' / model['model_name'] / 'pair_verdicts.csv')
    for _, row in verdicts.iterrows():
        lines.append(
            f'| {row.pair_i} vs {row.pair_j} | {row.source_m2_direction} | '
            f'{row.heldout_action_m3_direction} | {row.allocation_m4_direction} | '
            f'{row.action_transport_status} | {row.allocation_transport_status} |'
        )
    lines += ['', f'Figures: `figures/{model["model_name"]}/`', '']

lines += [
    '## Interpretation rule',
    '',
    'M2 is the calibrated source surface. M3 is the primary held-out executed-action target. M4 is a secondary '
    'allocation target and is usable only if its matched-template invariance gate passes. M1 is diagnostic. A gate '
    'failure produces abstention; it is not repaired by agreement elsewhere.',
    '',
    '## Hard stop',
    '',
    final['hard_stop'],
    '',
]
(run / 'analysis' / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
print(run / 'analysis' / 'REPORT.md')
