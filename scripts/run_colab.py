#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['design', 'run', 'audit', 'analyze', 'report', 'inspect', 'all'], required=True)
parser.add_argument('--config', required=True)
parser.add_argument('--output-run', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
run = Path(args.output_run)
cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))


def call(script: str, extra: list[str] | None = None) -> None:
    if script in {'inspect_results.py', 'report.py'}:
        cmd = [sys.executable, str(root / 'scripts' / script), '--output-run', args.output_run]
    else:
        cmd = [
            sys.executable,
            str(root / 'scripts' / script),
            '--config',
            args.config,
            '--output-run',
            args.output_run,
        ]
    if extra:
        cmd.extend(extra)
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def run_stages() -> None:
    for spec in cfg['models']:
        call('run_staged.py', ['--model-name', spec['name'], '--phase', 'all'])
        subprocess.run(
            [
                sys.executable,
                str(root / 'scripts' / 'inspect_stage.py'),
                '--output-run',
                args.output_run,
                '--model-name',
                spec['name'],
            ],
            check=True,
        )


def all_transport_complete() -> bool:
    statuses = []
    for spec in cfg['models']:
        path = run / 'analysis' / spec['name'] / 'stage_verdict.json'
        if not path.exists():
            return False
        statuses.append(json.loads(path.read_text(encoding='utf-8')).get('status'))
    return bool(statuses) and all(status == 'FULL_RUN_COMPLETE_ANALYSIS_PENDING' for status in statuses)


if args.phase in {'design', 'all'}:
    call('design.py')
if args.phase in {'run', 'all'}:
    run_stages()
if args.phase == 'all' and not all_transport_complete():
    print('At least one target reached a prospective source-stage stop; full transport analysis is not applicable.')
    raise SystemExit(0)
if args.phase in {'audit', 'all'}:
    call('audit_run.py')
if args.phase in {'analyze', 'all'}:
    call('analyze.py')
if args.phase in {'report', 'all'}:
    call('report.py')
if args.phase in {'inspect', 'all'}:
    call('inspect_results.py')
