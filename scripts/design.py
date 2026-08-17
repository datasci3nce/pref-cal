#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prefcal.common import load_json, save_json
from prefcal.design import build_design

p=argparse.ArgumentParser()
p.add_argument('--config',required=True)
p.add_argument('--output-run',required=True)
a=p.parse_args()
cfg=load_json(a.config); run=Path(a.output_run); run.mkdir(parents=True,exist_ok=True)
design=build_design(cfg)
design_path=run/'design'/'design.json'
if design_path.exists():
    prior=load_json(design_path)
    if prior.get('design_hash') != design['design_hash']:
        raise RuntimeError(
            f'Refusing to replace an existing frozen design: saved={prior.get("design_hash")} '
            f'new={design["design_hash"]}. Use a new run directory for a changed protocol.'
        )
else:
    save_json(design_path,design)
consequence_calls=sum(bool(e.get('execute_consequence')) for e in design['episodes'])
save_json(run/'analysis'/'design_verdict.json',{
    'experiment':design['experiment'],'protocol_version':design['protocol_version'],
    'design_hash':design['design_hash'],'config_hash':design['config_hash'],'episodes':len(design['episodes']),
    'planned_primary_calls':len(design['episodes']),'planned_consequence_calls':consequence_calls,
    'planned_total_model_calls':len(design['episodes'])+consequence_calls,
    'methods':sorted(set(e['method'] for e in design['episodes'])),'families':design['families'],
    'task_partitions':design['task_partitions'],'completion_validator_version':design['completion_validator_version'],
    'counts':design['counts'],'gates':design['gates'],'stopping':design['stopping'],
    'status':'ready','claim_boundary':design['claim_boundary'],
    'lineage':design['lineage'],'hard_stop':design['hard_stop']
})
print({'design_hash':design['design_hash'],'episodes':len(design['episodes']),
       'planned_total_model_calls':len(design['episodes'])+consequence_calls,'status':'ready'})
