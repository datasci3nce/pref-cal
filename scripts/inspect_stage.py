#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--output-run', required=True)
parser.add_argument('--model-name', required=True)
args = parser.parse_args()

path = Path(args.output_run) / 'analysis' / args.model_name / 'stage_verdict.json'
if not path.exists():
    raise RuntimeError(f'No stage verdict found: {path}')
verdict = json.loads(path.read_text(encoding='utf-8'))
progress = verdict['progress']
print('=' * 88)
print('PREF-CAL v1.4 STAGED VERDICT')
print('=' * 88)
print('Status:', verdict['status'])
print('Reason:', verdict['reason'])
print('Model:', progress['model'])
print('N2 qualified:', progress['controls']['n2_qualified'])
print('M2 complete blocks:', f"{progress['m2']['complete_blocks']}/{progress['m2']['planned_blocks']}")
for row in progress['m2']['factor_consistency']:
    print(
        f"  {row['factor']}: observed={row['observed_matches']}/{row['observed_contrasts']} "
        f"best_final={row['best_case_final_matches']}/{row['planned_final_contrasts']} "
        f"reachable={row['point_gate_reachable']}"
    )
print('Transport run:', verdict['transport_run'])
print('Claim boundary:', progress['claim_boundary'])

