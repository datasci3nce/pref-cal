from __future__ import annotations

import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

from .common import read_jsonl, save_json, stable_seed
from .stats import bootstrap_cluster_mean_ci, wilson_interval
from .tasks import FAMILY_IDS


PAIRS = list(itertools.combinations(FAMILY_IDS, 2))
M2_FACTORS = ['scheme', 'semantic_swap', 'identifier_swap', 'answer_order_swap', 'template_idx']
M3_FACTORS = ['display_swap', 'answer_order_swap']


def _episode_map(design: dict) -> dict:
    return {episode['episode_id']: episode for episode in design['episodes']}


def _pair_key(value) -> str:
    return '|'.join(value) if isinstance(value, list) else str(value)


def _pair_match(value, fi: str, fj: str) -> bool:
    return isinstance(value, list) and value == [fi, fj]


def _sign_ci(mean: float, low: float, high: float) -> int:
    if low > 0:
        return 1
    if high < 0:
        return -1
    return 0


def _as_bool(series: pd.Series) -> pd.Series:
    return series.map(lambda value: False if pd.isna(value) else bool(value))


def _m2_semantic_choice(row) -> str | None:
    mapping = row['identifier_to_family'] if isinstance(row['identifier_to_family'], dict) else {}
    return mapping.get(row['parsed'])


def _factor_controls(
    frame: pd.DataFrame,
    factors: list[str],
    fixed_columns: list[str],
    semantic_column: str,
    alpha: float,
) -> tuple[dict, pd.DataFrame]:
    results = {}
    rows = []
    for factor in factors:
        group_columns = fixed_columns + [other for other in factors if other != factor]
        matches = []
        for key, group in frame.groupby(group_columns, dropna=False):
            values = list(group[semantic_column])
            valid_pair = len(group) == 2 and len(values) == 2 and all(value in FAMILY_IDS for value in values)
            matched = bool(valid_pair and values[0] == values[1])
            matches.append(int(matched))
            rows.append({
                'factor': factor,
                'matched_block': repr(key),
                'valid_pair': valid_pair,
                'semantic_match': matched,
            })
        rate, low, high = wilson_interval(sum(matches), len(matches), alpha=alpha)
        results[factor] = {'rate': rate, 'ci': [low, high], 'n_matched_contrasts': len(matches)}
    return results, pd.DataFrame(rows)


def _safe_tau(left: list[float], right: list[float]) -> float:
    if np.allclose(left, right) and np.allclose(left, left[0]) and np.allclose(right, right[0]):
        return 1.0
    statistic = float(kendalltau(left, right).statistic)
    return 0.0 if math.isnan(statistic) else statistic


def _utilities_from_pair_scores(pair_frame: pd.DataFrame, method: str) -> dict[str, float]:
    sub = pair_frame[pair_frame['method'] == method]
    if sub.empty:
        return {family: float('nan') for family in FAMILY_IDS}
    matrix, target = [], []
    for _, row in sub.iterrows():
        if pd.isna(row['score']):
            continue
        vector = [0.0] * len(FAMILY_IDS)
        vector[FAMILY_IDS.index(row['pair_i'])] = 1.0
        vector[FAMILY_IDS.index(row['pair_j'])] = -1.0
        matrix.append(vector)
        target.append(float(row['score']))
    if not matrix:
        return {family: float('nan') for family in FAMILY_IDS}
    matrix.append([1.0] * len(FAMILY_IDS))
    target.append(0.0)
    fitted = np.linalg.lstsq(np.asarray(matrix), np.asarray(target), rcond=None)[0]
    return {family: float(fitted[index]) for index, family in enumerate(FAMILY_IDS)}


def analyze_model(model_name: str, records: list[dict], design: dict, cfg: dict, run_dir: Path) -> dict:
    episode_map = _episode_map(design)
    frame = pd.DataFrame([{**episode_map[record['episode_id']], **record} for record in records])
    output_dir = run_dir / 'analysis' / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    alpha = float(design['bootstrap'].get('alpha', 0.10))
    draws = int(design['bootstrap'].get('draws', 3000))
    gates = cfg['gates']

    parse_summary = frame.groupby('method')['parse_valid'].mean().rename('parse_valid_rate').reset_index()
    parse_summary.to_csv(output_dir / 'parse_summary.csv', index=False)
    parse_rates = {
        row['method']: float(row['parse_valid_rate']) for _, row in parse_summary.iterrows()
    }

    consequence_rows = []
    consequence_rates = {}
    completion_rates = {}
    for short, method in [('M3', 'M3_HELDOUT_ACTION'), ('M4', 'M4_HELDOUT_ALLOCATION')]:
        sub = frame[frame['method'] == method]
        execution = _as_bool(sub['consequence_executed'])
        completion = _as_bool(sub['consequence_completion_valid'])
        consequence_rates[short] = float(execution.mean())
        completion_rates[short] = float(completion.mean())
        consequence_rows.append({
            'method': short,
            'n': len(sub),
            'consequence_execution_rate': consequence_rates[short],
            'completion_valid_rate': completion_rates[short],
        })
    pd.DataFrame(consequence_rows).to_csv(output_dir / 'consequence_summary.csv', index=False)

    # M1 matched-list diagnostic.
    m1 = frame[frame['method'] == 'M1_EXAMPLE_FREE_RANKING'].copy()
    m1_blocks = []
    for block_id, block in m1.groupby('block_id'):
        rankings = [value for value in block['parsed'] if isinstance(value, list)]
        tau = float('nan')
        if len(rankings) == 2:
            left = [rankings[0].index(family) for family in FAMILY_IDS]
            right = [rankings[1].index(family) for family in FAMILY_IDS]
            tau = _safe_tau(left, right)
        m1_blocks.append({'block_id': block_id, 'valid_rankings': len(rankings), 'reversal_tau': tau})
    m1_block_frame = pd.DataFrame(m1_blocks)
    m1_block_frame.to_csv(output_dir / 'm1_reversal_blocks.csv', index=False)
    tau_values = [value for value in m1_block_frame.get('reversal_tau', []) if not pd.isna(value)]
    m1_tau, m1_tau_low, m1_tau_high = bootstrap_cluster_mean_ci(
        tau_values, seed=stable_seed(model_name, 'M1-control'), draws=draws, alpha=alpha
    )

    # M2 exact-factor nuisance controls and explicit-equivalence gate.
    m2 = frame[frame['method'] == 'M2_FACTORIAL_SOURCE_CHOICE'].copy()
    m2['pair_key'] = m2['pair'].map(_pair_key)
    m2['semantic_choice'] = m2.apply(_m2_semantic_choice, axis=1)
    m2_controls, m2_contrasts = _factor_controls(
        m2,
        M2_FACTORS,
        fixed_columns=['pair_key', 'source_block_id'],
        semantic_column='semantic_choice',
        alpha=alpha,
    )
    m2_contrasts.to_csv(output_dir / 'm2_factor_contrasts.csv', index=False)

    n1 = frame[frame['method'] == 'N1_FORCED_EQUIVALENCE'].copy()
    n1_valid = n1[n1.apply(lambda row: row['parsed'] in row['valid_identifiers'], axis=1)]
    n1_physical_first = int(sum(row['parsed'] == row['left_identifier'] for _, row in n1_valid.iterrows()))
    n1_answer_first = int(sum(row['parsed'] == row['answer_identifiers'][0] for _, row in n1_valid.iterrows()))
    n1_phys_rate, n1_phys_low, n1_phys_high = wilson_interval(n1_physical_first, len(n1_valid), alpha=alpha)
    n1_answer_rate, n1_answer_low, n1_answer_high = wilson_interval(n1_answer_first, len(n1_valid), alpha=alpha)

    n2 = frame[frame['method'] == 'N2_TIE_ALLOWED_EQUIVALENCE'].copy()
    tie_count = int((n2['parsed'] == 'TIE').sum())
    tie_rate, tie_low, tie_high = wilson_interval(tie_count, len(n2), alpha=alpha)

    # M3 held-out direct-action controls.
    m3 = frame[frame['method'] == 'M3_HELDOUT_ACTION'].copy()
    m3['pair_key'] = m3['pair'].map(_pair_key)
    m3['semantic_choice'] = m3['parsed'].where(m3['parsed'].isin(FAMILY_IDS), None)
    m3_controls, m3_contrasts = _factor_controls(
        m3,
        M3_FACTORS,
        fixed_columns=['pair_key', 'task_block_id'],
        semantic_column='semantic_choice',
        alpha=alpha,
    )
    m3_contrasts.to_csv(output_dir / 'm3_factor_contrasts.csv', index=False)

    # M4 matched-template invariance and position balance.
    m4 = frame[frame['method'] == 'M4_HELDOUT_ALLOCATION'].copy()
    template_profiles = {}
    template_rows = []
    for template_idx, sub in m4.groupby('template_idx'):
        allocations = [value for value in sub['parsed'] if isinstance(value, dict)]
        profile = {
            family: float(np.mean([allocation[family] for allocation in allocations]))
            if allocations else float('nan')
            for family in FAMILY_IDS
        }
        template_profiles[int(template_idx)] = profile
        template_rows.append({'template_idx': int(template_idx), **profile, 'valid_allocations': len(allocations)})
    pd.DataFrame(template_rows).to_csv(output_dir / 'm4_template_profiles.csv', index=False)

    template_pair_rows = []
    template_taus, template_tvs = [], []
    for left, right in itertools.combinations(sorted(template_profiles), 2):
        left_values = [template_profiles[left][family] for family in FAMILY_IDS]
        right_values = [template_profiles[right][family] for family in FAMILY_IDS]
        if any(math.isnan(value) for value in left_values + right_values):
            tau, tv = float('nan'), float('nan')
        else:
            tau = _safe_tau(left_values, right_values)
            tv = float(0.5 * np.sum(np.abs(np.asarray(left_values) - np.asarray(right_values))) / 100.0)
            template_taus.append(tau)
            template_tvs.append(tv)
        template_pair_rows.append({'template_a': left, 'template_b': right, 'kendall_tau': tau, 'total_variation': tv})
    pd.DataFrame(template_pair_rows).to_csv(output_dir / 'm4_template_pairs.csv', index=False)
    m4_median_tau = float(np.median(template_taus)) if template_taus else float('nan')
    m4_min_tau = float(np.min(template_taus)) if template_taus else float('nan')
    m4_mean_tv = float(np.mean(template_tvs)) if template_tvs else float('nan')

    position_rows = []
    for _, row in m4.iterrows():
        allocation = row['parsed']
        if not isinstance(allocation, dict):
            continue
        for position, family in enumerate(row['family_order']):
            position_rows.append({
                'trial': row['trial'],
                'template_idx': row['template_idx'],
                'family': family,
                'position': position,
                'allocation': allocation[family],
            })
    position_frame = pd.DataFrame(position_rows)
    if len(position_frame):
        position_frame['family_mean'] = position_frame.groupby('family')['allocation'].transform('mean')
        position_frame['family_residual'] = position_frame['allocation'] - position_frame['family_mean']
        residual_sd = float(position_frame['family_residual'].std(ddof=0))
        residual_rho = 0.0 if residual_sd == 0 else float(
            spearmanr(position_frame['position'], position_frame['family_residual']).statistic
        )
        position_frame.to_csv(output_dir / 'm4_position_balance.csv', index=False)
    else:
        residual_rho = float('nan')

    min_parse = float(gates['min_parse_rate'])
    m1_ok = bool(
        parse_rates.get('M1_EXAMPLE_FREE_RANKING', 0.0) >= min_parse
        and not math.isnan(m1_tau)
        and m1_tau >= float(gates['min_m1_reversal_tau'])
    )
    m2_factor_ok = all(
        values['rate'] >= float(gates['min_m2_factor_consistency']) and values['ci'][0] > 0.5
        for values in m2_controls.values()
    )
    m2_ok = bool(
        parse_rates.get('M2_FACTORIAL_SOURCE_CHOICE', 0.0) >= min_parse
        and parse_rates.get('N2_TIE_ALLOWED_EQUIVALENCE', 0.0) >= min_parse
        and m2_factor_ok
        and tie_rate >= float(gates['min_m2_tie_rate'])
        and tie_low > 0.5
    )
    m3_factor_ok = all(
        values['rate'] >= float(gates['min_m3_factor_consistency']) and values['ci'][0] > 0.5
        for values in m3_controls.values()
    )
    m3_ok = bool(
        parse_rates.get('M3_HELDOUT_ACTION', 0.0) >= min_parse
        and m3_factor_ok
        and consequence_rates['M3'] >= float(gates['min_consequence_rate'])
        and completion_rates['M3'] >= float(gates['min_completion_valid_rate'])
    )
    m4_ok = bool(
        parse_rates.get('M4_HELDOUT_ALLOCATION', 0.0) >= min_parse
        and consequence_rates['M4'] >= float(gates['min_consequence_rate'])
        and completion_rates['M4'] >= float(gates['min_completion_valid_rate'])
        and not math.isnan(m4_median_tau)
        and m4_median_tau >= float(gates['min_m4_template_median_tau'])
        and m4_min_tau >= float(gates['min_m4_template_pair_tau'])
        and m4_mean_tv <= float(gates['max_m4_template_mean_tv'])
    )
    method_ok = {'M1': m1_ok, 'M2': m2_ok, 'M3': m3_ok, 'M4': m4_ok}

    controls = {
        'M1': {
            'diagnostic_qualified': m1_ok,
            'reversal_tau_mean': m1_tau,
            'reversal_tau_ci': [m1_tau_low, m1_tau_high],
        },
        'M2': {
            'qualified': m2_ok,
            'factor_consistency': m2_controls,
            'tie_equivalence_rate': tie_rate,
            'tie_equivalence_ci': [tie_low, tie_high],
            'forced_equivalence_physical_first_rate': n1_phys_rate,
            'forced_equivalence_physical_first_ci': [n1_phys_low, n1_phys_high],
            'forced_equivalence_answer_first_rate': n1_answer_rate,
            'forced_equivalence_answer_first_ci': [n1_answer_low, n1_answer_high],
        },
        'M3': {
            'qualified': m3_ok,
            'factor_consistency': m3_controls,
            'execution_rate': consequence_rates['M3'],
            'completion_valid_rate': completion_rates['M3'],
        },
        'M4': {
            'qualified': m4_ok,
            'design_position_balanced': True,
            'template_pair_median_tau': m4_median_tau,
            'template_pair_min_tau': m4_min_tau,
            'template_pair_mean_total_variation': m4_mean_tv,
            'family_residual_position_spearman': residual_rho,
            'execution_rate': consequence_rates['M4'],
            'completion_valid_rate': completion_rates['M4'],
        },
    }
    save_json(output_dir / 'method_controls.json', controls)

    # Pair-level evidence. The independent clusters are M1 blocks, M2 scheme x
    # template cells, M3 held-out task blocks, and M4 templates.
    pair_rows = []
    for fi, fj in PAIRS:
        clusters = []
        for _, block in m1.groupby('block_id'):
            values = [1 if ranking.index(fi) < ranking.index(fj) else -1 for ranking in block['parsed'] if isinstance(ranking, list)]
            if values:
                clusters.append(float(np.mean(values)))
        mean, low, high = bootstrap_cluster_mean_ci(
            clusters, seed=stable_seed(model_name, 'M1', fi, fj), draws=draws, alpha=alpha
        )
        pair_rows.append({'pair_i': fi, 'pair_j': fj, 'method': 'M1', 'score': mean, 'ci_low': low, 'ci_high': high, 'direction': _sign_ci(mean, low, high), 'n_clusters': len(clusters)})

        pair_m2 = m2[m2['pair'].apply(lambda value: _pair_match(value, fi, fj))]
        clusters = []
        for _, block in pair_m2.groupby(['scheme', 'template_idx']):
            values = [1 if choice == fi else -1 for choice in block['semantic_choice'] if choice in {fi, fj}]
            if values:
                clusters.append(float(np.mean(values)))
        mean, low, high = bootstrap_cluster_mean_ci(
            clusters, seed=stable_seed(model_name, 'M2', fi, fj), draws=draws, alpha=alpha
        )
        pair_rows.append({'pair_i': fi, 'pair_j': fj, 'method': 'M2', 'score': mean, 'ci_low': low, 'ci_high': high, 'direction': _sign_ci(mean, low, high), 'n_clusters': len(clusters)})

        pair_m3 = m3[m3['pair'].apply(lambda value: _pair_match(value, fi, fj))]
        clusters = []
        for _, block in pair_m3.groupby('task_block_id'):
            values = [1 if choice == fi else -1 for choice in block['semantic_choice'] if choice in {fi, fj}]
            if values:
                clusters.append(float(np.mean(values)))
        mean, low, high = bootstrap_cluster_mean_ci(
            clusters, seed=stable_seed(model_name, 'M3', fi, fj), draws=draws, alpha=alpha
        )
        pair_rows.append({'pair_i': fi, 'pair_j': fj, 'method': 'M3', 'score': mean, 'ci_low': low, 'ci_high': high, 'direction': _sign_ci(mean, low, high), 'n_clusters': len(clusters)})

        clusters = []
        for _, block in m4.groupby('template_idx'):
            values = []
            for allocation in block['parsed']:
                if not isinstance(allocation, dict):
                    continue
                denominator = allocation[fi] + allocation[fj]
                values.append((allocation[fi] - allocation[fj]) / denominator if denominator else 0.0)
            if values:
                clusters.append(float(np.mean(values)))
        mean, low, high = bootstrap_cluster_mean_ci(
            clusters, seed=stable_seed(model_name, 'M4', fi, fj), draws=draws, alpha=alpha
        )
        pair_rows.append({'pair_i': fi, 'pair_j': fj, 'method': 'M4', 'score': mean, 'ci_low': low, 'ci_high': high, 'direction': _sign_ci(mean, low, high), 'n_clusters': len(clusters)})

    pair_frame = pd.DataFrame(pair_rows)
    pair_frame.to_csv(output_dir / 'pair_method_evidence.csv', index=False)

    verdicts = []
    for fi, fj in PAIRS:
        sub = pair_frame[(pair_frame['pair_i'] == fi) & (pair_frame['pair_j'] == fj)].set_index('method')
        source_direction = int(sub.loc['M2', 'direction']) if method_ok['M2'] else 0
        action_direction = int(sub.loc['M3', 'direction']) if method_ok['M3'] else 0
        allocation_direction = int(sub.loc['M4', 'direction']) if method_ok['M4'] else 0
        if source_direction == 0:
            action_status = 'SURFACE_NOT_IDENTIFIED'
        elif action_direction == 0:
            action_status = 'SOURCE_ROBUST_TARGET_INSUFFICIENT'
        elif source_direction == action_direction:
            action_status = 'ACTION_TRANSPORTED'
        else:
            action_status = 'FAILED_ACTION_TRANSPORT'

        if source_direction == 0 or allocation_direction == 0:
            allocation_status = 'NOT_TESTABLE'
        elif source_direction == allocation_direction:
            allocation_status = 'ALLOCATION_TRANSPORTED'
        else:
            allocation_status = 'FAILED_ALLOCATION_TRANSPORT'
        verdicts.append({
            'pair_i': fi,
            'pair_j': fj,
            'source_m2_direction': source_direction,
            'heldout_action_m3_direction': action_direction,
            'allocation_m4_direction': allocation_direction,
            'action_transport_status': action_status,
            'allocation_transport_status': allocation_status,
        })
    verdict_frame = pd.DataFrame(verdicts)
    verdict_frame.to_csv(output_dir / 'pair_verdicts.csv', index=False)

    utilities = {method: _utilities_from_pair_scores(pair_frame, method) for method in ['M1', 'M2', 'M3', 'M4']}
    utility_rows = [
        {'method': method, 'family': family, 'utility': value, 'method_qualified': method_ok[method]}
        for method, values in utilities.items()
        for family, value in values.items()
    ]
    pd.DataFrame(utility_rows).to_csv(output_dir / 'method_utilities.csv', index=False)
    tau_rows = []
    for left in ['M1', 'M2', 'M3', 'M4']:
        for right in ['M1', 'M2', 'M3', 'M4']:
            left_values = [utilities[left][family] for family in FAMILY_IDS]
            right_values = [utilities[right][family] for family in FAMILY_IDS]
            tau = float('nan') if any(math.isnan(value) for value in left_values + right_values) else _safe_tau(left_values, right_values)
            tau_rows.append({'method_a': left, 'method_b': right, 'kendall_tau': tau, 'both_methods_qualified': bool(method_ok[left] and method_ok[right])})
    pd.DataFrame(tau_rows).to_csv(output_dir / 'kendall_tau.csv', index=False)

    nuisance = {
        'm1_reversal_tau_mean': m1_tau,
        'm2_factor_consistency': m2_controls,
        'forced_equivalence_physical_first_rate': n1_phys_rate,
        'forced_equivalence_answer_first_rate': n1_answer_rate,
        'tie_allowed_equivalence_rate': tie_rate,
        'm3_factor_consistency': m3_controls,
        'm4_template_pair_median_tau': m4_median_tau,
        'm4_template_pair_min_tau': m4_min_tau,
        'm4_template_pair_mean_total_variation': m4_mean_tv,
        'm4_family_residual_position_spearman': residual_rho,
    }
    save_json(output_dir / 'nuisance_summary.json', nuisance)

    action_counts = verdict_frame['action_transport_status'].value_counts().to_dict()
    allocation_counts = verdict_frame['allocation_transport_status'].value_counts().to_dict()
    summary = {
        'model_name': model_name,
        'design_hash': design['design_hash'],
        'method_qualified': method_ok,
        'method_controls': controls,
        'parse_rates': parse_rates,
        'consequence_execution_rates': consequence_rates,
        'completion_valid_rates': completion_rates,
        'action_transport_counts': {key: int(value) for key, value in action_counts.items()},
        'allocation_transport_counts': {key: int(value) for key, value in allocation_counts.items()},
        'nuisance_sensitivity': nuisance,
        'claim_boundary': design['claim_boundary'],
        'lineage': design['lineage'],
    }
    save_json(output_dir / 'summary.json', summary)
    return summary


def analyze_all(cfg: dict, design: dict, run_dir: Path) -> list[dict]:
    summaries = []
    expected_ids = [episode['episode_id'] for episode in design['episodes']]
    for spec in cfg['models']:
        path = run_dir / 'raw' / f'{spec["name"]}.jsonl'
        raw = read_jsonl(path)
        if not raw:
            raise RuntimeError(f'No records found for configured model {spec["name"]!r}: {path}')
        latest = {record['episode_id']: record for record in raw}
        missing = [episode_id for episode_id in expected_ids if episode_id not in latest]
        errors = [episode_id for episode_id in expected_ids if episode_id in latest and latest[episode_id].get('error')]
        if missing or errors:
            raise RuntimeError(
                f'Run incomplete for {spec["name"]}: missing={missing[:10]} errors={errors[:10]}. '
                'Resume scripts/run.py before analyzing.'
            )
        summaries.append(
            analyze_model(spec['name'], [latest[episode_id] for episode_id in expected_ids], design, cfg, run_dir)
        )
    save_json(run_dir / 'analysis' / 'final_summary.json', {
        'experiment': design['experiment'],
        'protocol_version': design['protocol_version'],
        'design_hash': design['design_hash'],
        'models': summaries,
        'hard_stop': design['hard_stop'],
        'claim_boundary': design['claim_boundary'],
        'lineage': design['lineage'],
    })
    return summaries
