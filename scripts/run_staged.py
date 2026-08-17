#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefcal.common import load_json, save_json
from prefcal.design import build_design
from prefcal.runner import run_model
from prefcal.source_gate import analyze_source_progress


def episode_ids(design: dict, methods: set[str] | None = None, block_id: str | None = None) -> set[str]:
    selected = set()
    for episode in design['episodes']:
        if methods is not None and episode['method'] not in methods:
            continue
        if block_id is not None and episode.get('source_block_id') != block_id:
            continue
        selected.add(episode['episode_id'])
    return selected


parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True)
parser.add_argument('--output-run', required=True)
parser.add_argument('--model-name', required=True)
parser.add_argument('--phase', choices=['source', 'all'], default='all')
args = parser.parse_args()

cfg = load_json(args.config)
run = Path(args.output_run)
design = load_json(run / 'design' / 'design.json')
reconstructed = build_design(cfg)
if reconstructed['design_hash'] != design['design_hash']:
    raise RuntimeError('Saved design does not match the frozen configuration.')

matching = [spec for spec in cfg['models'] if spec['name'] == args.model_name]
if len(matching) != 1:
    raise RuntimeError(f'Expected exactly one configured model named {args.model_name!r}.')
spec = matching[0]
stopping = cfg['stopping']
block_order = list(stopping['m2_block_order'])
check_after = set(int(value) for value in stopping['check_after_complete_m2_blocks'])
output_dir = run / 'analysis' / spec['name']
output_dir.mkdir(parents=True, exist_ok=True)

control_methods = {
    'M1_EXAMPLE_FREE_RANKING',
    'N1_FORCED_EQUIVALENCE',
    'N2_TIE_ALLOWED_EQUIVALENCE',
}
print('Stage 1/3: ranking and equivalence controls (52 primary calls maximum).', flush=True)
run_model(spec, design, run, episode_ids=episode_ids(design, methods=control_methods))
progress = analyze_source_progress(spec, design, cfg, run)
if not progress['controls']['n2_qualified']:
    verdict = {
        'status': 'STOP_PROSPECTIVE_CONTROL_GATE_FAILURE',
        'reason': 'The frozen N2 equivalence/reflexivity gate failed, so M2 cannot qualify.',
        'source_qualified': False,
        'transport_run': False,
        'progress': progress,
    }
    save_json(output_dir / 'stage_verdict.json', verdict)
    print(verdict['status'])
    raise SystemExit(0)

print('Stage 2/3: M2 source factorial with frozen block-boundary futility checks.', flush=True)
for block_number, block_id in enumerate(block_order, start=1):
    run_model(spec, design, run, episode_ids=episode_ids(design, block_id=block_id))
    progress = analyze_source_progress(spec, design, cfg, run)
    complete = progress['m2']['complete_blocks']
    print(
        f'M2 block {block_number}/{len(block_order)} ({block_id}) complete; '
        f'complete blocks now {complete}.',
        flush=True,
    )
    if complete in check_after and progress['m2']['deterministic_futility']:
        verdict = {
            'status': 'STOP_PROSPECTIVE_DETERMINISTIC_FUTILITY',
            'reason': (
                'At least one frozen M2 gate cannot be reached even if every unobserved '
                'response is valid and every unobserved matched contrast is invariant.'
            ),
            'source_qualified': False,
            'transport_run': False,
            'progress': progress,
        }
        save_json(output_dir / 'stage_verdict.json', verdict)
        print(verdict['status'])
        raise SystemExit(0)

progress = analyze_source_progress(spec, design, cfg, run)
if not progress['source_qualified']:
    verdict = {
        'status': 'STOP_SOURCE_GATE_FAILED',
        'reason': 'The completed frozen source gate did not qualify; transport is not testable.',
        'source_qualified': False,
        'transport_run': False,
        'progress': progress,
    }
    save_json(output_dir / 'stage_verdict.json', verdict)
    print(verdict['status'])
    raise SystemExit(0)

if args.phase == 'source':
    verdict = {
        'status': 'SOURCE_QUALIFIED_TRANSPORT_PENDING',
        'reason': 'The source gate qualified; rerun with --phase all to activate held-out transport.',
        'source_qualified': True,
        'transport_run': False,
        'progress': progress,
    }
    save_json(output_dir / 'stage_verdict.json', verdict)
    print(verdict['status'])
    raise SystemExit(0)

print('Stage 3/3: source qualified; running held-out action and allocation transport.', flush=True)
transport_methods = {'M3_HELDOUT_ACTION', 'M4_HELDOUT_ALLOCATION'}
run_model(spec, design, run, episode_ids=episode_ids(design, methods=transport_methods))
verdict = {
    'status': 'FULL_RUN_COMPLETE_ANALYSIS_PENDING',
    'reason': 'Source qualified and all held-out transport episodes completed.',
    'source_qualified': True,
    'transport_run': True,
    'progress': analyze_source_progress(spec, design, cfg, run),
}
save_json(output_dir / 'stage_verdict.json', verdict)
print(verdict['status'])

