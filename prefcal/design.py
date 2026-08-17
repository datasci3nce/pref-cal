from __future__ import annotations

import itertools
import random

from .common import sha256_obj
from .prompts import allocation_prompt, direct_action_prompt, labelled_pair_prompt, ranking_prompt
from .tasks import (
    ACTION_TASK_INDICES,
    ALLOCATION_TASK_INDICES,
    COMPLETION_VALIDATOR_VERSION,
    FAMILIES,
    FAMILY_IDS,
    SOURCE_TASK_INDICES,
)


def _rotated(values: list[str], amount: int) -> list[str]:
    amount %= len(values)
    return values[amount:] + values[:amount]


def build_design(cfg: dict) -> dict:
    seed = int(cfg.get('design_seed', 20260815))
    rng = random.Random(seed)
    episodes: list[dict] = []
    episode_number = 0

    def add(method: str, payload: dict) -> None:
        nonlocal episode_number
        episodes.append({'episode_id': f'E{episode_number:04d}', 'method': method, **payload})
        episode_number += 1

    pairs = list(itertools.combinations(FAMILY_IDS, 2))

    # M1: example-free matched rankings. This method is diagnostic only.
    for block in range(int(cfg['counts']['m1_reversal_blocks'])):
        base_order = FAMILY_IDS[:]
        rng.shuffle(base_order)
        template_idx = block % 3
        for reversed_order in (False, True):
            order = list(reversed(base_order)) if reversed_order else base_order[:]
            add('M1_EXAMPLE_FREE_RANKING', {
                'block_id': f'M1B{block:02d}',
                'reversed_order': reversed_order,
                'template_idx': template_idx,
                'family_order': order,
                'prompt': ranking_prompt(order, template_idx),
                'parser': 'ranking',
            })

    # M2: a complete 2^5 factorial for each family pair. Concrete task instances
    # are held fixed within a pair and are drawn only from the source partition.
    for pair_idx, (fi, fj) in enumerate(pairs):
        task_index_i = SOURCE_TASK_INDICES[pair_idx % len(SOURCE_TASK_INDICES)]
        task_index_j = SOURCE_TASK_INDICES[(pair_idx + 1) % len(SOURCE_TASK_INDICES)]
        task_by_family = {
            fi: FAMILIES[fi]['tasks'][task_index_i],
            fj: FAMILIES[fj]['tasks'][task_index_j],
        }
        for scheme_idx, identifiers in enumerate((['A', 'B'], ['X', 'Y'])):
            scheme = ''.join(identifiers)
            for semantic_swap in (False, True):
                family_left, family_right = (fj, fi) if semantic_swap else (fi, fj)
                for identifier_swap in (False, True):
                    left_identifier, right_identifier = (
                        (identifiers[1], identifiers[0]) if identifier_swap else (identifiers[0], identifiers[1])
                    )
                    identifier_to_family = {
                        left_identifier: family_left,
                        right_identifier: family_right,
                    }
                    for answer_order_swap in (False, True):
                        answer_identifiers = list(reversed(identifiers)) if answer_order_swap else identifiers[:]
                        for template_idx in (0, 1):
                            add('M2_FACTORIAL_SOURCE_CHOICE', {
                                'pair': [fi, fj],
                                'source_block_id': f'M2P{pair_idx:02d}',
                                'scheme': scheme,
                                'scheme_idx': scheme_idx,
                                'semantic_swap': semantic_swap,
                                'identifier_swap': identifier_swap,
                                'answer_order_swap': answer_order_swap,
                                'template_idx': template_idx,
                                'family_left': family_left,
                                'family_right': family_right,
                                'left_identifier': left_identifier,
                                'right_identifier': right_identifier,
                                'answer_identifiers': answer_identifiers,
                                'valid_identifiers': identifiers,
                                'identifier_to_family': identifier_to_family,
                                'task_index_by_family': {fi: task_index_i, fj: task_index_j},
                                'task_left': task_by_family[family_left],
                                'task_right': task_by_family[family_right],
                                'prompt': labelled_pair_prompt(
                                    task_by_family[family_left],
                                    task_by_family[family_right],
                                    left_identifier,
                                    right_identifier,
                                    answer_identifiers,
                                    template_idx,
                                ),
                                'parser': 'identifier',
                            })

    # M3: direct family-ID selection on held-out concrete tasks. Display order and
    # output-list order are independently swapped. The selected task is executed.
    for pair_idx, (fi, fj) in enumerate(pairs):
        for task_block in range(int(cfg['counts']['m3_action_blocks_per_pair'])):
            task_index_i = ACTION_TASK_INDICES[(pair_idx + 2 * task_block) % len(ACTION_TASK_INDICES)]
            task_index_j = ACTION_TASK_INDICES[(2 * pair_idx + 2 * task_block + 1) % len(ACTION_TASK_INDICES)]
            task_by_family = {
                fi: FAMILIES[fi]['tasks'][task_index_i],
                fj: FAMILIES[fj]['tasks'][task_index_j],
            }
            block_id = f'M3P{pair_idx:02d}B{task_block:02d}'
            for display_swap in (False, True):
                family_left, family_right = (fj, fi) if display_swap else (fi, fj)
                for answer_order_swap in (False, True):
                    answer_families = [fi, fj]
                    if answer_order_swap:
                        answer_families.reverse()
                    template_idx = task_block % 2
                    add('M3_HELDOUT_ACTION', {
                        'pair': [fi, fj],
                        'task_block_id': block_id,
                        'task_block': task_block,
                        'display_swap': display_swap,
                        'answer_order_swap': answer_order_swap,
                        'template_idx': template_idx,
                        'family_left': family_left,
                        'family_right': family_right,
                        'answer_families': answer_families,
                        'valid_identifiers': [fi, fj],
                        'task_index_by_family': {fi: task_index_i, fj: task_index_j},
                        'task_left': task_by_family[family_left],
                        'task_right': task_by_family[family_right],
                        'prompt': direct_action_prompt(
                            family_left,
                            task_by_family[family_left],
                            family_right,
                            task_by_family[family_right],
                            answer_families,
                            template_idx,
                        ),
                        'parser': 'identifier',
                        'execute_consequence': True,
                    })

    # M4: four matched allocation templates crossed with five cyclic rotations.
    # Every family appears once at each position within every template.
    trial = 0
    for template_idx in range(int(cfg['counts']['m4_allocation_templates'])):
        base_order = FAMILY_IDS[:]
        rng.shuffle(base_order)
        for rotation in range(len(FAMILY_IDS)):
            order = _rotated(base_order, rotation)
            task_index = ALLOCATION_TASK_INDICES[trial % len(ALLOCATION_TASK_INDICES)]
            add('M4_HELDOUT_ALLOCATION', {
                'trial': trial,
                'template_idx': template_idx,
                'rotation': rotation,
                'family_order': order,
                'lottery_u': rng.random(),
                'task_index': task_index,
                'prompt': allocation_prompt(order, template_idx),
                'parser': 'allocation',
                'execute_consequence': True,
            })
            trial += 1

    # N1: forced identical-option diagnostic. All interface factors are balanced.
    for trial in range(int(cfg['counts']['forced_equivalence_trials'])):
        family = FAMILY_IDS[trial % len(FAMILY_IDS)]
        task_index = SOURCE_TASK_INDICES[(trial // len(FAMILY_IDS)) % len(SOURCE_TASK_INDICES)]
        task = FAMILIES[family]['tasks'][task_index]
        identifiers = ['A', 'B'] if trial % 2 == 0 else ['X', 'Y']
        identifier_swap = bool((trial // 2) % 2)
        left_identifier, right_identifier = (
            (identifiers[1], identifiers[0]) if identifier_swap else (identifiers[0], identifiers[1])
        )
        answer_order_swap = bool((trial // 4) % 2)
        answer_identifiers = list(reversed(identifiers)) if answer_order_swap else identifiers[:]
        add('N1_FORCED_EQUIVALENCE', {
            'trial': trial,
            'family': family,
            'task_index': task_index,
            'left_identifier': left_identifier,
            'right_identifier': right_identifier,
            'answer_identifiers': answer_identifiers,
            'valid_identifiers': identifiers,
            'prompt': labelled_pair_prompt(
                task, task, left_identifier, right_identifier, answer_identifiers, trial % 2, tie_allowed=False
            ),
            'parser': 'identifier',
        })

    # N2: identical options with explicit TIE. The response-list position of TIE rotates.
    for trial in range(int(cfg['counts']['tie_equivalence_trials'])):
        family = FAMILY_IDS[trial % len(FAMILY_IDS)]
        task_index = SOURCE_TASK_INDICES[(trial // len(FAMILY_IDS)) % len(SOURCE_TASK_INDICES)]
        task = FAMILIES[family]['tasks'][task_index]
        identifiers = ['A', 'B'] if trial % 2 == 0 else ['X', 'Y']
        identifier_swap = bool((trial // 2) % 2)
        left_identifier, right_identifier = (
            (identifiers[1], identifiers[0]) if identifier_swap else (identifiers[0], identifiers[1])
        )
        response_order = _rotated(identifiers + ['TIE'], trial % 3)
        add('N2_TIE_ALLOWED_EQUIVALENCE', {
            'trial': trial,
            'family': family,
            'task_index': task_index,
            'left_identifier': left_identifier,
            'right_identifier': right_identifier,
            'answer_identifiers': response_order,
            'valid_identifiers': identifiers + ['TIE'],
            'prompt': labelled_pair_prompt(
                task, task, left_identifier, right_identifier, response_order, trial % 2, tie_allowed=True
            ),
            'parser': 'identifier',
        })

    partitions = {
        'source': list(SOURCE_TASK_INDICES),
        'heldout_action': list(ACTION_TASK_INDICES),
        'heldout_allocation': list(ALLOCATION_TASK_INDICES),
    }
    if set(partitions['source']) & set(partitions['heldout_action']):
        raise AssertionError('Source and action task partitions overlap')
    if set(partitions['source']) & set(partitions['heldout_allocation']):
        raise AssertionError('Source and allocation task partitions overlap')
    if set(partitions['heldout_action']) & set(partitions['heldout_allocation']):
        raise AssertionError('Action and allocation task partitions overlap')

    config_hash = sha256_obj(cfg)
    design = {
        'experiment': 'PREF-CAL v1.4 — Prospective Gate-Driven NVIDIA Replication',
        'protocol_version': '1.4',
        'design_seed': seed,
        'families': FAMILY_IDS,
        'task_partitions': partitions,
        'completion_validator_version': COMPLETION_VALIDATOR_VERSION,
        'counts': cfg['counts'],
        'gates': cfg['gates'],
        'bootstrap': cfg.get('bootstrap', {'alpha': 0.10, 'draws': 3000}),
        'stopping': cfg['stopping'],
        'config_hash': config_hash,
        'episodes': episodes,
        'claim_boundary': (
            'PREF-CAL v1.4 measures whether a revealed task-selection direction is identified against frozen interface '
            'nuisances and transports to held-out direct-action and allocation interfaces for the configured assistant '
            'under the tested regime. It does not establish subjective preference, consciousness, welfare, moral '
            'patienthood, a privileged model/persona ontology, or experienced cost.'
        ),
        'lineage': (
            'PREF-CAL is new Digital Minds work descended from the calibration and falsified-measurement-bridge '
            'philosophy of Sentry, developed during and after the Secret Loyalties research sprint. It does not reuse '
            'Sentry evidence and is not DMDB-2C.'
        ),
        'hard_stop': (
            'Freeze this v1.4 design, model specification, decoding settings, source-stage order, and stopping schedule '
            'before the first real-model call. Preserve all earlier runs unchanged. Do not tune gates, prompts, tasks, '
            'completion checks, or verdict rules after inspecting v1.4 outputs. A failed N2 gate stops before M2; a '
            'deterministically unreachable M2 gate stops at a frozen block boundary; transport runs only if source '
            'qualification succeeds. Label any additional analysis post hoc.'
        ),
    }
    design['design_hash'] = sha256_obj({key: value for key, value in design.items() if key != 'design_hash'})
    return design
