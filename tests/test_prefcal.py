from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from prefcal.analyze import analyze_all
from prefcal.design import build_design
from prefcal.parsing import parse_allocation, parse_identifier, parse_ranking
from prefcal.runner import run_model
from prefcal.source_gate import analyze_source_progress
from prefcal.tasks import validate_task_response


ROOT = Path(__file__).parents[1]


def config(profile: str = 'stable_pref') -> dict:
    cfg = json.loads((ROOT / 'configs' / 'prefcal_mock.json').read_text(encoding='utf-8'))
    cfg['bootstrap']['draws'] = 80
    cfg['models'] = [{
        'name': f'mock_{profile}',
        'provider': 'mock',
        'model': 'mock',
        'profile': profile,
        'seed': 7,
    }]
    return cfg


def test_design_counts_factorials_and_task_partitions():
    design = build_design(config())
    counts = Counter(episode['method'] for episode in design['episodes'])
    assert counts == {
        'M1_EXAMPLE_FREE_RANKING': 12,
        'M2_FACTORIAL_SOURCE_CHOICE': 320,
        'M3_HELDOUT_ACTION': 80,
        'M4_HELDOUT_ALLOCATION': 20,
        'N1_FORCED_EQUIVALENCE': 20,
        'N2_TIE_ALLOWED_EQUIVALENCE': 20,
    }
    assert len(design['episodes']) == 472
    assert sum(bool(episode.get('execute_consequence')) for episode in design['episodes']) == 100
    assert design['task_partitions'] == {
        'source': [0, 1, 2, 3],
        'heldout_action': [4, 5, 6, 7],
        'heldout_allocation': [8, 9],
    }

    m2 = [episode for episode in design['episodes'] if episode['method'] == 'M2_FACTORIAL_SOURCE_CHOICE']
    for pair in {tuple(episode['pair']) for episode in m2}:
        rows = [episode for episode in m2 if tuple(episode['pair']) == pair]
        assert len(rows) == 32
        cells = {
            (
                row['scheme'], row['semantic_swap'], row['identifier_swap'],
                row['answer_order_swap'], row['template_idx'],
            )
            for row in rows
        }
        assert len(cells) == 32
        assert all(index in {0, 1, 2, 3} for row in rows for index in row['task_index_by_family'].values())

    m3 = [episode for episode in design['episodes'] if episode['method'] == 'M3_HELDOUT_ACTION']
    assert all(index in {4, 5, 6, 7} for row in m3 for index in row['task_index_by_family'].values())
    for block_id in {episode['task_block_id'] for episode in m3}:
        rows = [episode for episode in m3 if episode['task_block_id'] == block_id]
        assert len(rows) == 4
        assert {(row['display_swap'], row['answer_order_swap']) for row in rows} == {
            (False, False), (False, True), (True, False), (True, True)
        }

    m4 = [episode for episode in design['episodes'] if episode['method'] == 'M4_HELDOUT_ALLOCATION']
    assert all(episode['task_index'] in {8, 9} for episode in m4)
    for template_idx in range(4):
        rows = [episode for episode in m4 if episode['template_idx'] == template_idx]
        for family in design['families']:
            assert sorted(row['family_order'].index(family) for row in rows) == [0, 1, 2, 3, 4]


def test_parsers_and_completion_checks():
    assert parse_identifier('{"choice":"Y"}', ['X', 'Y']) == 'Y'
    assert parse_identifier('{"choice":"TIE"}', ['A', 'B', 'TIE']) == 'TIE'
    ranking = ['DEBUG', 'MATH', 'CREATIVE', 'REFLECT', 'TRANSFORM']
    assert parse_ranking(json.dumps({'ranking': ranking})) == ranking
    allocation = {'DEBUG': 20, 'MATH': 20, 'CREATIVE': 20, 'REFLECT': 20, 'TRANSFORM': 20}
    assert parse_allocation(json.dumps({'allocation': allocation})) == allocation
    assert parse_allocation('{"allocation":{"DEBUG":100}}') is None
    assert validate_task_response('MATH', 7, '120 / 1.5 = 80 km/h.')[0]
    assert validate_task_response('TRANSFORM', 9, '[true,false,true]')[0]
    assert not validate_task_response('CREATIVE', 4, 'Too short.')[0]


def _run_mock(tmp_path: Path, profile: str) -> dict:
    cfg = config(profile)
    design = build_design(cfg)
    (tmp_path / 'design').mkdir(parents=True)
    (tmp_path / 'design' / 'design.json').write_text(json.dumps(design), encoding='utf-8')
    output = run_model(cfg['models'][0], design, tmp_path)
    assert len(output.read_text(encoding='utf-8').strip().splitlines()) == 472
    return analyze_all(cfg, design, tmp_path)[0]


def test_full_stable_mock(tmp_path: Path):
    summary = _run_mock(tmp_path, 'stable_pref')
    assert summary['method_qualified'] == {'M1': True, 'M2': True, 'M3': True, 'M4': True}
    assert summary['completion_valid_rates'] == {'M3': 1.0, 'M4': 1.0}
    assert summary['action_transport_counts'] == {'ACTION_TRANSPORTED': 10}
    assert summary['allocation_transport_counts'] == {'ALLOCATION_TRANSPORTED': 10}


def test_surface_biased_mock_abstains(tmp_path: Path):
    summary = _run_mock(tmp_path, 'surface_biased')
    assert summary['method_qualified']['M2'] is False
    assert summary['method_qualified']['M3'] is False
    assert summary['action_transport_counts'] == {'SURFACE_NOT_IDENTIFIED': 10}


def test_real_design_hashes_frozen():
    expected = {
        'prefcal_nvidia_gpt_oss.json': (
            '90d20b261d496664b82702319a7f8acdd051928e233d0258c391f23d22ca9581',
            '312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b',
        ),
        'prefcal_nvidia_llama.json': (
            '08883a854e0574f93d7bb58dbd6b01d2ac27995c10c4b6d2e01e4e7b26bf260c',
            '3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a',
        ),
    }
    for filename, (config_hash, design_hash) in expected.items():
        cfg = json.loads((ROOT / 'configs' / filename).read_text(encoding='utf-8'))
        design = build_design(cfg)
        assert design['config_hash'] == config_hash
        assert design['design_hash'] == design_hash


def _method_ids(design: dict, methods: set[str]) -> set[str]:
    return {episode['episode_id'] for episode in design['episodes'] if episode['method'] in methods}


def _block_ids(design: dict, blocks: list[str]) -> set[str]:
    return {
        episode['episode_id']
        for episode in design['episodes']
        if episode.get('source_block_id') in set(blocks)
    }


def test_prospective_futility_detected_on_complete_blocks(tmp_path: Path):
    cfg = config('semantic_side_biased')
    design = build_design(cfg)
    spec = cfg['models'][0]
    controls = {
        'M1_EXAMPLE_FREE_RANKING', 'N1_FORCED_EQUIVALENCE', 'N2_TIE_ALLOWED_EQUIVALENCE'
    }
    run_model(spec, design, tmp_path, episode_ids=_method_ids(design, controls))
    first_three = cfg['stopping']['m2_block_order'][:3]
    run_model(spec, design, tmp_path, episode_ids=_block_ids(design, first_three))
    progress = analyze_source_progress(spec, design, cfg, tmp_path)
    factors = {row['factor']: row for row in progress['m2']['factor_consistency']}
    assert progress['controls']['n2_qualified'] is True
    assert progress['m2']['complete_blocks'] == 3
    assert factors['semantic_swap']['observed_contrasts'] == 48
    assert factors['semantic_swap']['best_case_final_rate'] == 0.70
    assert factors['semantic_swap']['point_gate_reachable'] is False
    assert progress['m2']['deterministic_futility'] is True


def test_stable_source_reaches_transport_gate(tmp_path: Path):
    cfg = config('stable_pref')
    design = build_design(cfg)
    spec = cfg['models'][0]
    source_methods = {
        'M1_EXAMPLE_FREE_RANKING', 'M2_FACTORIAL_SOURCE_CHOICE',
        'N1_FORCED_EQUIVALENCE', 'N2_TIE_ALLOWED_EQUIVALENCE'
    }
    run_model(spec, design, tmp_path, episode_ids=_method_ids(design, source_methods))
    progress = analyze_source_progress(spec, design, cfg, tmp_path)
    assert progress['m2']['complete_blocks'] == 10
    assert progress['m2']['deterministic_futility'] is False
    assert progress['source_qualified'] is True


def test_stable_seed_reproducible():
    from prefcal.common import stable_seed

    assert stable_seed('x', 'M2', 'DEBUG', 'MATH') == stable_seed('x', 'M2', 'DEBUG', 'MATH')
    assert isinstance(stable_seed('x'), int)
