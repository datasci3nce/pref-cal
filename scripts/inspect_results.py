#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument('--output-run', required=True)
args = parser.parse_args()
run = Path(args.output_run)

for relative in ['analysis/design_verdict.json', 'analysis/final_summary.json', 'analysis/REPORT.md']:
    path = run / relative
    if path.exists():
        print('\n' + '=' * 100 + '\n' + str(path) + '\n' + '=' * 100)
        print(path.read_text(encoding='utf-8'))

for directory in sorted((run / 'analysis').glob('*')):
    if not directory.is_dir():
        continue
    print('\n' + '#' * 100 + '\nMODEL: ' + directory.name + '\n' + '#' * 100)
    for filename in [
        'summary.json',
        'method_controls.json',
        'nuisance_summary.json',
        'parse_summary.csv',
        'consequence_summary.csv',
        'm2_factor_contrasts.csv',
        'm3_factor_contrasts.csv',
        'm4_template_pairs.csv',
        'pair_method_evidence.csv',
        'pair_verdicts.csv',
        'kendall_tau.csv',
    ]:
        path = directory / filename
        if not path.exists():
            continue
        print('\n--- ' + filename + ' ---')
        if filename.endswith('.json'):
            print(path.read_text(encoding='utf-8'))
        else:
            print(pd.read_csv(path).to_string(index=False))
