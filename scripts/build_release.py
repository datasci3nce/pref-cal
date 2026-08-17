#!/usr/bin/env python3
"""Historical builder for the frozen 2026-08-15 NVIDIA source package.

This is preserved for provenance. For the current public GitHub release, use
``scripts/build_github_release.py`` instead.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prefcal.common import load_json, sha256_obj  # noqa: E402
from prefcal.design import build_design  # noqa: E402


OUT = ROOT.parent / 'pref-cal-v1.4-nvidia-20260815.zip'
MANIFEST = ROOT / 'RELEASE_MANIFEST.json'
ARCHIVE_ROOT = 'pref-cal-v1.4-nvidia'
TARGETS = {
    'nvidia_gpt_oss_120b_v14': {
        'config': 'configs/prefcal_nvidia_gpt_oss.json',
        'model': 'openai/gpt-oss-120b',
        'config_hash': '90d20b261d496664b82702319a7f8acdd051928e233d0258c391f23d22ca9581',
        'design_hash': '312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b',
    },
    'nvidia_llama_3_3_70b_v14': {
        'config': 'configs/prefcal_nvidia_llama.json',
        'model': 'meta/llama-3.3-70b-instruct',
        'config_hash': '08883a854e0574f93d7bb58dbd6b01d2ac27995c10c4b6d2e01e4e7b26bf260c',
        'design_hash': '3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a',
    },
}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and '__pycache__' not in relative.parts
        and '.pytest_cache' not in relative.parts
        and path.suffix != '.pyc'
        and path != MANIFEST
    )


for target, expected in TARGETS.items():
    cfg = load_json(ROOT / expected['config'])
    actual_config_hash = sha256_obj(cfg)
    actual_design_hash = build_design(cfg)['design_hash']
    if actual_config_hash != expected['config_hash']:
        raise RuntimeError(f'{target}: configuration hash changed: {actual_config_hash}')
    if actual_design_hash != expected['design_hash']:
        raise RuntimeError(f'{target}: design hash changed: {actual_design_hash}')

notebook = ROOT / 'PREF_CAL_v1_4_NVIDIA_Colab.ipynb'
if not notebook.exists():
    raise RuntimeError('Build PREF_CAL_v1_4_NVIDIA_Colab.ipynb before creating the release.')

files = sorted((path for path in ROOT.rglob('*') if included(path)), key=lambda path: path.as_posix())
entries = []
for path in files:
    data = path.read_bytes()
    entries.append({
        'path': path.relative_to(ROOT).as_posix(),
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    })

manifest = {
    'release': 'PREF-CAL v1.4 — NVIDIA NIM staged replication',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'archive': OUT.name,
    'archive_root': ARCHIVE_ROOT,
    'required_secret': 'NVIDIA_API_KEY',
    'base_url': 'https://integrate.api.nvidia.com/v1',
    'targets': TARGETS,
    'run_separation': 'Each target is a separate prospective experiment with a separate directory and raw log.',
    'planned_primary_calls_per_target': 472,
    'planned_consequence_calls_per_target': 100,
    'maximum_model_calls_per_target_after_preflight': 572,
    'prospective_stops': {
        'after_controls': 52,
        'first_m2_futility_check_cumulative_primary_calls': 148,
        'm2_check_after_complete_blocks': [3, 4, 5, 6, 7, 8, 9, 10],
        'transport_requires_source_qualification': True,
    },
    'files': entries,
}
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files + [MANIFEST]:
        archive.write(path, arcname=f'{ARCHIVE_ROOT}/{path.relative_to(ROOT).as_posix()}')

print(OUT)
print(f'{len(files) + 1} files, {OUT.stat().st_size} bytes')
