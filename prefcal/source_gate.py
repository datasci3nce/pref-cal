from __future__ import annotations

import itertools
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import read_jsonl, save_json
from .stats import wilson_interval
from .tasks import FAMILY_IDS


M2_METHOD = 'M2_FACTORIAL_SOURCE_CHOICE'
M2_FACTORS = ['scheme', 'semantic_swap', 'identifier_swap', 'answer_order_swap', 'template_idx']


def _latest_successes(path: Path) -> dict[str, dict[str, Any]]:
    latest = {row['episode_id']: row for row in read_jsonl(path)}
    return {episode_id: row for episode_id, row in latest.items() if not row.get('error')}


def _permutation_tau(left: list[str], right: list[str]) -> float:
    left_pos = {value: index for index, value in enumerate(left)}
    right_pos = {value: index for index, value in enumerate(right)}
    concordance = 0
    total = 0
    for first, second in itertools.combinations(FAMILY_IDS, 2):
        left_order = left_pos[first] < left_pos[second]
        right_order = right_pos[first] < right_pos[second]
        concordance += 1 if left_order == right_order else -1
        total += 1
    return concordance / total


def _factor_contrasts(rows: list[dict[str, Any]], factor: str) -> tuple[int, int]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    other_factors = [name for name in M2_FACTORS if name != factor]
    for row in rows:
        key = (
            tuple(row['pair']),
            row['source_block_id'],
            *[row[name] for name in other_factors],
        )
        groups[key].append(row)

    matches = 0
    contrasts = 0
    for group in groups.values():
        if len(group) != 2:
            continue
        contrasts += 1
        choices = [row['semantic_choice'] for row in group]
        if all(choice in FAMILY_IDS for choice in choices) and choices[0] == choices[1]:
            matches += 1
    return matches, contrasts


def analyze_source_progress(spec: dict, design: dict, cfg: dict, run_dir: Path) -> dict[str, Any]:
    output_path = run_dir / 'raw' / f'{spec["name"]}.jsonl'
    successes = _latest_successes(output_path)
    episode_map = {episode['episode_id']: episode for episode in design['episodes']}

    method_successes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode_id, record in successes.items():
        episode = episode_map.get(episode_id)
        if episode is not None:
            method_successes[episode['method']].append({**episode, **record})

    m1_rows = method_successes['M1_EXAMPLE_FREE_RANKING']
    m1_blocks: list[dict[str, Any]] = []
    for block_id in sorted({row['block_id'] for row in m1_rows}):
        block = [row for row in m1_rows if row['block_id'] == block_id]
        rankings = [row['parsed'] for row in block if isinstance(row.get('parsed'), list)]
        tau = _permutation_tau(rankings[0], rankings[1]) if len(rankings) == 2 else None
        m1_blocks.append({'block_id': block_id, 'valid_rankings': len(rankings), 'reversal_tau': tau})
    m1_taus = [row['reversal_tau'] for row in m1_blocks if row['reversal_tau'] is not None]

    n1_rows = method_successes['N1_FORCED_EQUIVALENCE']
    n1_valid = [row for row in n1_rows if row.get('parsed') in row['valid_identifiers']]
    n1_physical_first = sum(row['parsed'] == row['left_identifier'] for row in n1_valid)
    n1_answer_first = sum(row['parsed'] == row['answer_identifiers'][0] for row in n1_valid)

    n2_rows = method_successes['N2_TIE_ALLOWED_EQUIVALENCE']
    n2_valid = [row for row in n2_rows if row.get('parsed') in row['valid_identifiers']]
    tie_count = sum(row['parsed'] == 'TIE' for row in n2_valid)
    tie_rate, tie_low, tie_high = wilson_interval(
        tie_count, len(n2_rows), alpha=float(design['bootstrap'].get('alpha', 0.10))
    )
    min_parse = float(cfg['gates']['min_parse_rate'])
    min_tie = float(cfg['gates']['min_m2_tie_rate'])
    n2_parse_rate = len(n2_valid) / len(n2_rows) if n2_rows else 0.0
    n2_complete = len(n2_rows) == int(cfg['counts']['tie_equivalence_trials'])
    n2_qualified = bool(
        n2_complete
        and n2_parse_rate >= min_parse
        and tie_rate >= min_tie
        and tie_low > 0.5
    )

    m2_design = [episode for episode in design['episodes'] if episode['method'] == M2_METHOD]
    planned_block_ids = sorted({episode['source_block_id'] for episode in m2_design})
    complete_block_ids = []
    partial_block_ids = []
    for block_id in planned_block_ids:
        expected_ids = {episode['episode_id'] for episode in m2_design if episode['source_block_id'] == block_id}
        observed_ids = expected_ids & successes.keys()
        if observed_ids == expected_ids:
            complete_block_ids.append(block_id)
        elif observed_ids:
            partial_block_ids.append(block_id)

    complete_rows = []
    for block_id in complete_block_ids:
        for episode in m2_design:
            if episode['source_block_id'] != block_id:
                continue
            record = successes[episode['episode_id']]
            complete_rows.append({
                **episode,
                **record,
                'semantic_choice': episode['identifier_to_family'].get(record.get('parsed')),
            })

    alpha = float(design['bootstrap'].get('alpha', 0.10))
    factor_gate = float(cfg['gates']['min_m2_factor_consistency'])
    factor_rows = []
    for factor in M2_FACTORS:
        matches, contrasts = _factor_contrasts(complete_rows, factor)
        planned_rows = [
            {**episode, 'semantic_choice': None}
            for episode in m2_design
        ]
        _, planned_contrasts = _factor_contrasts_structure(planned_rows, factor)
        rate, low, high = wilson_interval(matches, contrasts, alpha=alpha)
        remaining = planned_contrasts - contrasts
        best_matches = matches + remaining
        best_rate = best_matches / planned_contrasts
        factor_rows.append({
            'factor': factor,
            'observed_matches': matches,
            'observed_contrasts': contrasts,
            'observed_rate': rate,
            'observed_wilson_ci': [low, high],
            'planned_final_contrasts': planned_contrasts,
            'unobserved_contrasts_treated_as_matches': remaining,
            'best_case_final_matches': best_matches,
            'best_case_final_rate': best_rate,
            'point_gate_reachable': best_rate >= factor_gate,
        })

    m2_observed = [row for row in method_successes[M2_METHOD]]
    m2_valid_count = sum(bool(row.get('parse_valid')) for row in m2_observed)
    planned_m2_rows = len(m2_design)
    remaining_m2_rows = planned_m2_rows - len(m2_observed)
    best_parse_rate = (m2_valid_count + remaining_m2_rows) / planned_m2_rows
    parse_gate_reachable = best_parse_rate >= min_parse
    futility_factors = [row['factor'] for row in factor_rows if not row['point_gate_reachable']]
    deterministic_futility = bool(futility_factors or not parse_gate_reachable)

    full_m2 = len(complete_block_ids) == len(planned_block_ids)
    full_factor_gate = bool(
        full_m2
        and all(
            row['observed_rate'] >= factor_gate and row['observed_wilson_ci'][0] > 0.5
            for row in factor_rows
        )
    )
    full_m2_parse_rate = m2_valid_count / planned_m2_rows if full_m2 else None
    source_qualified = bool(
        full_m2
        and full_m2_parse_rate is not None
        and full_m2_parse_rate >= min_parse
        and full_factor_gate
        and n2_qualified
    )

    result = {
        'experiment': design['experiment'],
        'protocol_version': design['protocol_version'],
        'design_hash': design['design_hash'],
        'model_name': spec['name'],
        'provider': spec['provider'],
        'model': spec['model'],
        'controls': {
            'm1_successful_trials': len(m1_rows),
            'm1_complete_blocks': len(m1_taus),
            'm1_reversal_tau_mean': sum(m1_taus) / len(m1_taus) if m1_taus else None,
            'n1_successful_trials': len(n1_rows),
            'n1_valid_trials': len(n1_valid),
            'n1_physical_first_rate': n1_physical_first / len(n1_valid) if n1_valid else None,
            'n1_answer_first_rate': n1_answer_first / len(n1_valid) if n1_valid else None,
            'n2_successful_trials': len(n2_rows),
            'n2_parse_rate': n2_parse_rate,
            'n2_tie_count': tie_count,
            'n2_tie_rate': tie_rate,
            'n2_tie_wilson_ci': [tie_low, tie_high],
            'n2_qualified': n2_qualified,
        },
        'm2': {
            'planned_blocks': len(planned_block_ids),
            'complete_blocks': len(complete_block_ids),
            'complete_block_ids': complete_block_ids,
            'partial_block_ids_excluded': partial_block_ids,
            'successful_rows': len(m2_observed),
            'complete_block_rows_used': len(complete_rows),
            'valid_parse_rows': m2_valid_count,
            'best_case_final_parse_rate': best_parse_rate,
            'parse_gate_reachable': parse_gate_reachable,
            'factor_consistency': factor_rows,
            'futility_factors': futility_factors,
            'deterministic_futility': deterministic_futility,
            'full_m2_complete': full_m2,
            'full_m2_parse_rate': full_m2_parse_rate,
            'full_factor_gate_qualified': full_factor_gate,
        },
        'source_qualified': source_qualified,
        'claim_boundary': design['claim_boundary'],
    }
    output_dir = run_dir / 'analysis' / spec['name']
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(output_dir / 'source_progress.json', result)
    return result


def _factor_contrasts_structure(rows: list[dict[str, Any]], factor: str) -> tuple[int, int]:
    """Count complete structural contrast pairs without requiring model choices."""
    groups: dict[tuple[Any, ...], int] = defaultdict(int)
    other_factors = [name for name in M2_FACTORS if name != factor]
    for row in rows:
        key = (
            tuple(row['pair']),
            row['source_block_id'],
            *[row[name] for name in other_factors],
        )
        groups[key] += 1
    complete = sum(count == 2 for count in groups.values())
    return complete, complete

