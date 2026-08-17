#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefcal.common import load_json, read_jsonl
from prefcal.design import build_design


parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True)
parser.add_argument('--output-run', required=True)
args = parser.parse_args()
cfg = load_json(args.config)
run = Path(args.output_run)
design = load_json(run / 'design' / 'design.json')
expected = [episode['episode_id'] for episode in design['episodes']]
consequential = {episode['episode_id'] for episode in design['episodes'] if episode.get('execute_consequence')}

print('=' * 90)
print(f'PREF-CAL v{design.get("protocol_version", "1.4")} RUN AUDIT')
print('=' * 90)
all_ok = True
reconstructed = build_design(cfg)
hash_ok = reconstructed['design_hash'] == design['design_hash']
print(f'design hash saved={design["design_hash"]} reconstructed={reconstructed["design_hash"]} match={hash_ok}')
all_ok &= hash_ok

for spec in cfg['models']:
    path = run / 'raw' / f'{spec["name"]}.jsonl'
    raw = read_jsonl(path)
    latest = {record['episode_id']: record for record in raw}
    missing = [episode_id for episode_id in expected if episode_id not in latest]
    errors = [episode_id for episode_id in expected if episode_id in latest and latest[episode_id].get('error')]
    wrong_hash = [
        episode_id for episode_id in expected
        if episode_id in latest and latest[episode_id].get('design_hash') != design['design_hash']
    ]
    missing_consequence_field = [
        episode_id for episode_id in consequential
        if episode_id in latest and 'consequence_executed' not in latest[episode_id]
    ]
    missing_provider_metadata = [
        episode_id for episode_id in expected
        if episode_id in latest and 'provider_metadata' not in latest[episode_id]
    ]
    print(
        f'{spec["name"]}: latest={len(latest)}/{len(expected)} missing={len(missing)} errors={len(errors)} '
        f'wrong_hash={len(wrong_hash)} missing_consequence_field={len(missing_consequence_field)} '
        f'missing_provider_metadata={len(missing_provider_metadata)} log_rows={len(raw)}'
    )
    if missing:
        print('  missing:', missing[:20])
    if errors:
        print('  errors:', errors[:20])
    if wrong_hash:
        print('  wrong hash:', wrong_hash[:20])
    if missing_consequence_field:
        print('  missing consequence field:', missing_consequence_field[:20])
    if missing_provider_metadata:
        print('  missing provider metadata:', missing_provider_metadata[:20])
    all_ok &= not missing and not errors and not wrong_hash and not missing_consequence_field and not missing_provider_metadata

print('AUDIT:', 'PASS' if all_ok else 'INCOMPLETE — resume run phase')
if not all_ok:
    raise SystemExit(2)
