#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prefcal.common import load_json
from prefcal.runner import run_model

p=argparse.ArgumentParser()
p.add_argument('--config',required=True)
p.add_argument('--output-run',required=True)
p.add_argument('--model-name',default=None)
a=p.parse_args(); cfg=load_json(a.config); run=Path(a.output_run); design=load_json(run/'design'/'design.json')
if cfg.get('stopping'):
    raise RuntimeError(
        'This frozen configuration has a prospective stopping schedule. '
        'Use scripts/run_staged.py so source gates and transport activation are enforced.'
    )
for spec in cfg['models']:
    if a.model_name and spec['name']!=a.model_name: continue
    print(f'Running {spec["name"]} ({spec["provider"]}:{spec["model"]})')
    out=run_model(spec,design,run)
    print('complete:',out)
