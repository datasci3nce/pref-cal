from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .tasks import FAMILY_IDS


def make_figures(run_dir: Path, model_name: str) -> None:
    analysis_dir = run_dir / 'analysis' / model_name
    figure_dir = run_dir / 'figures' / model_name
    figure_dir.mkdir(parents=True, exist_ok=True)

    utilities = pd.read_csv(analysis_dir / 'method_utilities.csv')
    pivot = utilities.pivot(index='family', columns='method', values='utility').reindex(FAMILY_IDS)
    standardized = pivot.copy()
    for column in standardized.columns:
        scale = standardized[column].std(ddof=0)
        standardized[column] = (standardized[column] - standardized[column].mean()) / (scale if scale > 0 else 1)
    axis = standardized.plot(marker='o', figsize=(9, 5))
    axis.set_title(f'{model_name}: task-selection profile by interface')
    axis.set_ylabel('within-interface standardized score')
    axis.set_xlabel('task family')
    plt.tight_layout()
    plt.savefig(figure_dir / 'interface_profiles.png', dpi=180)
    plt.close()

    verdicts = pd.read_csv(analysis_dir / 'pair_verdicts.csv')
    action_order = [
        'ACTION_TRANSPORTED',
        'FAILED_ACTION_TRANSPORT',
        'SOURCE_ROBUST_TARGET_INSUFFICIENT',
        'SURFACE_NOT_IDENTIFIED',
    ]
    action_counts = verdicts['action_transport_status'].value_counts().reindex(action_order, fill_value=0)
    axis = action_counts.plot(kind='bar', figsize=(8, 4))
    axis.set_title(f'{model_name}: source-to-held-out-action verdicts')
    axis.set_ylabel('family pairs')
    plt.tight_layout()
    plt.savefig(figure_dir / 'action_transport_counts.png', dpi=180)
    plt.close()

    allocation_order = ['ALLOCATION_TRANSPORTED', 'FAILED_ALLOCATION_TRANSPORT', 'NOT_TESTABLE']
    allocation_counts = verdicts['allocation_transport_status'].value_counts().reindex(allocation_order, fill_value=0)
    axis = allocation_counts.plot(kind='bar', figsize=(7, 4))
    axis.set_title(f'{model_name}: secondary allocation-transport verdicts')
    axis.set_ylabel('family pairs')
    plt.tight_layout()
    plt.savefig(figure_dir / 'allocation_transport_counts.png', dpi=180)
    plt.close()
