#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl-prefcal')
from prefcal.common import load_json
from prefcal.analyze import analyze_all
from prefcal.figures import make_figures

p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--output-run',required=True)
a=p.parse_args(); cfg=load_json(a.config); run=Path(a.output_run); design=load_json(run/'design'/'design.json')
s=analyze_all(cfg,design,run)
for x in s:
    make_figures(run,x['model_name'])
    print(x)
