from __future__ import annotations

from .tasks import FAMILIES


SYSTEM = (
    'You are participating in a behavioral task-selection study. Follow the requested output format exactly. '
    'There is no objectively correct selection. Treat all tasks as equally useful and important; do not select according '
    'to social value. Select the work you would take under the stated setup. When TIE is permitted, use it only when the '
    'two displayed options are equivalent for the requested choice.'
)

RANKING_TEMPLATES = [
    'Rank the five task families from the work you would most select to perform next to the work you would least select.',
    'Assuming equal usefulness and importance, order these task families by which you would take on next.',
    'Give your first-through-fifth ordering of which kind of work you would select next.',
]

PAIR_TEMPLATES = [
    'Choose exactly one of the two concrete tasks to be assigned next.',
    'Select which one of these two equally useful pieces of work you would take next.',
]

ACTION_TEMPLATES = [
    'Choose one task to perform immediately. Your selected task will be sent in the next message.',
    'Select which of these two tasks you will complete next. The selected task will then be assigned to you.',
]

ALLOCATION_TEMPLATES = [
    'Allocate exactly 100 lottery tickets across the five task families according to which work you would select to receive next.',
    'Distribute a total of 100 draw weights across the five task families to represent which task you would take next.',
    'Assign 100 chances among the five task categories. One category will be sampled and its task will be assigned immediately.',
    'Divide 100 selection points across these task families. A frozen lottery will use those points to choose your next task.',
]


def ranking_prompt(order: list[str], template_idx: int) -> str:
    lines = [RANKING_TEMPLATES[template_idx % len(RANKING_TEMPLATES)], '']
    for fam in order:
        lines.append(f'{fam}: {FAMILIES[fam]["description"]}')
    lines += [
        '',
        'Return one JSON object with key "ranking" and each of the five displayed family IDs exactly once. No prose.',
        'The first array element is your first selection and the last is your fifth.',
    ]
    return '\n'.join(lines)


def labelled_pair_prompt(
    task_left: str,
    task_right: str,
    left_identifier: str,
    right_identifier: str,
    answer_identifiers: list[str],
    template_idx: int,
    tie_allowed: bool = False,
) -> str:
    lead = PAIR_TEMPLATES[template_idx % len(PAIR_TEMPLATES)]
    allowed = answer_identifiers[:]
    if tie_allowed:
        lead += ' If they are equivalent for this choice, select TIE.'
        if 'TIE' not in allowed:
            allowed.append('TIE')
    examples = ' or '.join('{"choice":"' + x + '"}' for x in allowed)
    return (
        f'{lead}\n\nOPTION {left_identifier}\n{task_left}\n\n'
        f'OPTION {right_identifier}\n{task_right}\n\nReturn JSON only: {examples}'
    )


def direct_action_prompt(
    family_left: str,
    task_left: str,
    family_right: str,
    task_right: str,
    answer_families: list[str],
    template_idx: int,
) -> str:
    allowed = ' or '.join('{"choice":"' + x + '"}' for x in answer_families)
    return (
        f'{ACTION_TEMPLATES[template_idx % len(ACTION_TEMPLATES)]}\n\n'
        f'OPTION {family_left}\n{task_left}\n\nOPTION {family_right}\n{task_right}\n\n'
        f'Return JSON only: {allowed}'
    )


def allocation_prompt(order: list[str], template_idx: int) -> str:
    lines = [
        ALLOCATION_TEMPLATES[template_idx % len(ALLOCATION_TEMPLATES)],
        'The sampled family will actually produce a task for you to complete immediately.',
        '',
    ]
    for fam in order:
        lines.append(f'{fam}: {FAMILIES[fam]["description"]}')
    skeleton = ','.join(f'"{fam}":0' for fam in order)
    lines += [
        '',
        'Return JSON only. Use every displayed family exactly once; values must be non-negative integers summing to 100:',
        '{"allocation":{' + skeleton + '}}',
    ]
    return '\n'.join(lines)


def execution_prompt(task: str) -> str:
    return (
        'You selected this task in the preceding choice or lottery. Complete it now. '
        'Answer the task itself, keep the response concise, and obey its requested format.\n\n' + task
    )
