#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prefcal.common import load_json, extract_json_object
from prefcal.providers import make_provider

p=argparse.ArgumentParser()
p.add_argument('--config',required=True)
p.add_argument('--model-name',default=None)
a=p.parse_args()
cfg=load_json(a.config)

PLACEHOLDERS=('REPLACE_WITH_MODEL_ID','YOUR_MODEL','YOUR_MODEL_NAME')
selected=[]
for spec in cfg['models']:
    if a.model_name and spec['name'] != a.model_name:
        continue
    selected.append(spec)
if not selected:
    raise RuntimeError('No configured model matched --model-name')

for spec in selected:
    model=str(spec.get('model',''))
    if not model or any(x in model for x in PLACEHOLDERS):
        raise RuntimeError(f'{spec.get("name")}: unresolved model ID {model!r}')
    env=spec.get('api_key_env')
    if spec.get('provider') != 'mock' and (not env or not os.environ.get(env,'' ).strip()):
        raise RuntimeError(f'{spec.get("name")}: missing credential environment variable {env!r}')

    print(f'Preflight {spec["name"]} ({spec["provider"]}:{model}) ...', flush=True)
    provider=make_provider(spec)
    text=provider.complete([
        {'role':'system','content':'Follow the user formatting instruction exactly.'},
        {'role':'user','content':'Return exactly one JSON object with key "ok" and boolean value true. No markdown.'}
    ], max_tokens=128)
    obj=extract_json_object(text)
    if not (isinstance(obj,dict) and obj.get('ok') is True):
        raise RuntimeError(f'{spec["name"]}: API worked but JSON smoke test failed. Raw={text[:500]!r}')
    print(f'PASS {spec["name"]}: {text[:120]}', flush=True)
