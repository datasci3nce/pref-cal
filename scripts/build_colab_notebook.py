#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'PREF_CAL_v1_4_NVIDIA_Colab.ipynb'


def markdown(source: str) -> dict:
    return {'cell_type': 'markdown', 'metadata': {}, 'source': source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': source.splitlines(keepends=True),
    }


cells = [
    markdown(
        '# PREF-CAL v1.4 — NVIDIA NIM staged replication\n\n'
        'This notebook runs one of two **separate prospective experiments** using the same frozen scientific prompts, '
        'tasks, gates, and prospective stopping schedule. It does not continue or pool the interrupted Groq v1.3 run.\n\n'
        '- `gpt_oss`: the same `openai/gpt-oss-120b` model through NVIDIA NIM (provider/backend replication).\n'
        '- `llama`: `meta/llama-3.3-70b-instruct` through NVIDIA NIM (cross-model replication).\n\n'
        'The source stage starts with 52 ranking/equivalence controls. M2 then runs in frozen 32-cell blocks. A failed '
        'N2 gate or a mathematically unreachable M2 gate stops the run before held-out transport. The full maximum remains '
        '472 primary plus 100 consequence calls, but transport is activated only after source qualification.\n\n'
        'Required Colab Secret: `NVIDIA_API_KEY`. Never paste or print the key in a notebook cell.'
    ),
    markdown('## 1. Mount Drive and upload the package ZIP'),
    code(
        "from google.colab import drive, files\n"
        "drive.mount('/content/drive')\n\n"
        "uploaded = files.upload()  # upload pref-cal-v1.4-nvidia-20260815.zip\n"
        "zip_name = next(iter(uploaded))\n"
        "print(zip_name)\n"
    ),
    code(
        "import os, pathlib, shutil, zipfile\n"
        "INSTALL = pathlib.Path('/content/prefcal-v1-4-nvidia-installer')\n"
        "if INSTALL.exists():\n"
        "    shutil.rmtree(INSTALL)\n"
        "INSTALL.mkdir(parents=True)\n"
        "with zipfile.ZipFile('/content/' + zip_name) as archive:\n"
        "    archive.extractall(INSTALL)\n"
        "projects = list(INSTALL.glob('pref-cal-v1.4-nvidia'))\n"
        "assert projects, list(INSTALL.iterdir())\n"
        "ROOT = projects[0]\n"
        "print('ROOT:', ROOT)\n"
        "!pip -q install -r {ROOT}/requirements.txt\n"
    ),
    markdown('## 2. Load the NVIDIA credential without printing it'),
    code(
        "from google.colab import userdata\n"
        "value = userdata.get('NVIDIA_API_KEY')\n"
        "if not value:\n"
        "    raise RuntimeError('Add NVIDIA_API_KEY in Colab Secrets before continuing.')\n"
        "os.environ['NVIDIA_API_KEY'] = value\n"
        "print('NVIDIA_API_KEY FOUND')\n"
    ),
    markdown(
        '## 3. Select exactly one frozen target\n\n'
        'Run `gpt_oss` first. Download its result bundle before changing this value to `llama`. The two targets use '
        'different Drive directories and must never share logs.'
    ),
    code(
        "TARGET = 'gpt_oss'  # first run; later change only this value to 'llama'\n\n"
        "TARGETS = {\n"
        "    'gpt_oss': {\n"
        "        'config': 'configs/prefcal_nvidia_gpt_oss.json',\n"
        "        'model_name': 'nvidia_gpt_oss_120b_v14',\n"
        "        'run_name': 'prefcal_v1_4_nvidia_gpt_oss_120b',\n"
        "        'config_hash': '90d20b261d496664b82702319a7f8acdd051928e233d0258c391f23d22ca9581',\n"
        "        'design_hash': '312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b',\n"
        "    },\n"
        "    'llama': {\n"
        "        'config': 'configs/prefcal_nvidia_llama.json',\n"
        "        'model_name': 'nvidia_llama_3_3_70b_v14',\n"
        "        'run_name': 'prefcal_v1_4_nvidia_llama_3_3_70b',\n"
        "        'config_hash': '08883a854e0574f93d7bb58dbd6b01d2ac27995c10c4b6d2e01e4e7b26bf260c',\n"
        "        'design_hash': '3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a',\n"
        "    },\n"
        "}\n"
        "if TARGET not in TARGETS:\n"
        "    raise ValueError(f'Unknown TARGET: {TARGET!r}')\n"
        "choice = TARGETS[TARGET]\n"
        "print('TARGET:', TARGET, choice['model_name'])\n"
    ),
    markdown(
        '## 4. Freeze a fresh target-specific run configuration\n\n'
        'The cell refuses to overwrite a different configuration. Each model is a separate experiment.'
    ),
    code(
        "import json, pathlib, sys\n"
        "sys.path.insert(0, str(ROOT))\n"
        "from prefcal.common import load_json, save_json, sha256_obj\n\n"
        "RUN = pathlib.Path('/content/drive/MyDrive/pref-cal-runs') / choice['run_name']\n"
        "SOURCE_CFG = ROOT / choice['config']\n"
        "candidate = load_json(SOURCE_CFG)\n"
        "assert sha256_obj(candidate) == choice['config_hash']\n"
        "RUN.mkdir(parents=True, exist_ok=True)\n"
        "FROZEN_CFG = RUN / 'frozen_config.json'\n"
        "if FROZEN_CFG.exists():\n"
        "    existing = load_json(FROZEN_CFG)\n"
        "    if existing != candidate:\n"
        "        raise RuntimeError('Existing target run has a different frozen config. Use a new run directory.')\n"
        "else:\n"
        "    save_json(FROZEN_CFG, candidate)\n"
        "MODEL_NAME = choice['model_name']\n"
        "print('RUN:', RUN)\n"
        "print('MODEL:', candidate['models'][0]['model'])\n"
        "print('CONFIG:', FROZEN_CFG)\n"
    ),
    markdown('## 5. Validate the package and make one credential/model smoke-test call'),
    code(
        "import subprocess\n"
        "env = {**os.environ, 'PYTHONPATH': str(ROOT), 'MPLCONFIGDIR': '/tmp/mpl-prefcal'}\n"
        "subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=ROOT, check=True, env=env)\n"
        "subprocess.run([sys.executable, 'scripts/preflight.py', '--config', str(FROZEN_CFG), "
        "'--model-name', MODEL_NAME], cwd=ROOT, check=True, env=env)\n"
    ),
    markdown('## 6. Generate and verify the prospective design\n\nDo not continue if a hash differs.'),
    code(
        "subprocess.run([sys.executable, 'scripts/design.py', '--config', str(FROZEN_CFG), "
        "'--output-run', str(RUN)], cwd=ROOT, check=True, env=env)\n"
        "verdict = load_json(RUN / 'analysis' / 'design_verdict.json')\n"
        "print(json.dumps(verdict, indent=2))\n"
        "assert verdict['design_hash'] == choice['design_hash']\n"
        "assert verdict['config_hash'] == choice['config_hash']\n"
        "assert verdict['planned_primary_calls'] == 472\n"
        "assert verdict['planned_consequence_calls'] == 100\n"
        "assert verdict['planned_total_model_calls'] == 572\n"
    ),
    markdown(
        '## 7. Run or resume the prospective staged protocol\n\n'
        'This is append-only and episode-resumable. Rerun the cell after a transport failure or Colab disconnect. A '
        'scientific stop returns normally and makes no further calls on rerun.'
    ),
    code(
        "subprocess.run([sys.executable, 'scripts/run_staged.py', '--config', str(FROZEN_CFG), "
        "'--output-run', str(RUN), '--model-name', MODEL_NAME, '--phase', 'all'], "
        "cwd=ROOT, check=True, env=env)\n"
    ),
    markdown('## 8. Inspect the staged verdict'),
    code(
        "subprocess.run([sys.executable, 'scripts/inspect_stage.py', '--output-run', str(RUN), "
        "'--model-name', MODEL_NAME], cwd=ROOT, check=True, env=env)\n"
        "STAGE = load_json(RUN / 'analysis' / MODEL_NAME / 'stage_verdict.json')\n"
        "print(json.dumps(STAGE, indent=2)[:12000])\n"
    ),
    markdown(
        '## 9. Analyze only when transport completed\n\n'
        'A source-stage stop is already the frozen result and must not be forced through the full analyzer.'
    ),
    code(
        "if STAGE['status'] == 'FULL_RUN_COMPLETE_ANALYSIS_PENDING':\n"
        "    subprocess.run([sys.executable, 'scripts/audit_run.py', '--config', str(FROZEN_CFG), "
        "                   '--output-run', str(RUN)], cwd=ROOT, check=True, env=env)\n"
        "    subprocess.run([sys.executable, 'scripts/analyze.py', '--config', str(FROZEN_CFG), "
        "                   '--output-run', str(RUN)], cwd=ROOT, check=True, env=env)\n"
        "    subprocess.run([sys.executable, 'scripts/report.py', '--output-run', str(RUN)], "
        "                   cwd=ROOT, check=True, env=env)\n"
        "    subprocess.run([sys.executable, 'scripts/inspect_results.py', '--output-run', str(RUN)], "
        "                   cwd=ROOT, check=True, env=env)\n"
        "else:\n"
        "    print('Bounded source-stage result:', STAGE['status'])\n"
        "    print('Transport was correctly not run.')\n"
    ),
    markdown('## 10. Download the complete target-specific result bundle'),
    code(
        "bundle_base = '/content/' + choice['run_name'] + '_result'\n"
        "bundle = shutil.make_archive(bundle_base, 'zip', root_dir=RUN)\n"
        "print(bundle)\n"
        "files.download(bundle)\n"
    ),
    markdown(
        '## 11. Run the second model later\n\n'
        'After the first ZIP has downloaded, change only `TARGET` in section 3 from `gpt_oss` to `llama`, then rerun '
        'sections 3–10. Do not copy raw logs between target directories.\n\n'
        '## Interpretation boundary\n\n'
        'A source-stage stop means that the configured response surface failed its frozen identification requirements. '
        'A full transport label is available only when source qualification activates M3/M4. No outcome establishes '
        'subjective preference, consciousness, welfare, moral patienthood, a privileged model/persona ontology, or '
        'experienced cost.'
    ),
]

for index, cell in enumerate(cells):
    cell['id'] = f'prefcal-v14-nvidia-{index:02d}'

notebook = {
    'cells': cells,
    'metadata': {
        'colab': {'provenance': []},
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}
OUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print(OUT)

