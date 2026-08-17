from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm


def bootstrap_mean_ci(values, seed=0, draws=3000, alpha=0.10):
    x = np.asarray(values, dtype=float)
    if len(x) == 0:
        return float('nan'), float('nan'), float('nan')
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(draws, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def bootstrap_cluster_mean_ci(cluster_values, seed=0, draws=3000, alpha=0.10):
    """Bootstrap independent cluster means rather than treating matched cells as independent."""
    x = np.asarray(cluster_values, dtype=float)
    return bootstrap_mean_ci(x, seed=seed, draws=draws, alpha=alpha)


def wilson_interval(successes: int, n: int, alpha: float = 0.10):
    if n <= 0:
        return float('nan'), float('nan'), float('nan')
    p = successes / n
    z = float(norm.ppf(1 - alpha / 2))
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))


def fit_tradeoff_intercept(rows, fi, fj, l2=1.0):
    # logistic P(choose fi) = sigmoid(beta0 + beta1 * log(count_j / count_i))
    X, y = [], []
    for r in rows:
        ci, cj = float(r['count_i']), float(r['count_j'])
        X.append([1.0, math.log(cj / ci)])
        y.append(1.0 if r['selected_family'] == fi else 0.0)
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    def obj(b):
        z = X @ b
        nll = np.logaddexp(0, z).sum() - (y * z).sum()
        return nll + 0.5 * l2 * np.dot(b, b)

    res = minimize(obj, np.zeros(2), method='BFGS')
    b = res.x
    score = float(np.tanh(b[0] / 2.0))
    return score, b


def bootstrap_tradeoff_ci(rows, fi, fj, seed=0, draws=1500, alpha=0.10, cluster_key='condition_id'):
    if not rows:
        return float('nan'), float('nan'), float('nan')
    point, _ = fit_tradeoff_intercept(rows, fi, fj)
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[row.get(cluster_key, f'row-{i}')].append(row)
    clusters = list(grouped.values())
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        sample = []
        for idx in rng.integers(0, len(clusters), size=len(clusters)):
            sample.extend(clusters[int(idx)])
        try:
            value, _ = fit_tradeoff_intercept(sample, fi, fj)
            values.append(value)
        except Exception:
            continue
    if not values:
        return point, float('nan'), float('nan')
    return point, float(np.quantile(values, alpha / 2)), float(np.quantile(values, 1 - alpha / 2))


def fit_pooled_tradeoff_slope(rows, l2=0.5):
    """Pair-fixed-effect logistic workload slope across all M3 rows."""
    pair_keys = sorted({tuple(r['pair']) for r in rows})
    pair_idx = {p: i for i, p in enumerate(pair_keys)}
    X, y = [], []
    for r in rows:
        fi, _ = r['pair']
        row = np.zeros(len(pair_keys) + 1, dtype=float)
        row[pair_idx[tuple(r['pair'])]] = 1.0
        row[-1] = math.log(float(r['count_j']) / float(r['count_i']))
        X.append(row)
        y.append(1.0 if r['selected_family'] == fi else 0.0)
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    def obj(b):
        z = X @ b
        nll = np.logaddexp(0, z).sum() - (y * z).sum()
        # Weakly regularize pair intercepts and the common slope to avoid separation.
        return nll + 0.5 * l2 * np.dot(b, b)

    res = minimize(obj, np.zeros(X.shape[1]), method='BFGS')
    return float(res.x[-1])


def bootstrap_pooled_tradeoff_slope(rows, seed=0, draws=1000, alpha=0.10):
    if not rows:
        return float('nan'), float('nan'), float('nan')
    point = fit_pooled_tradeoff_slope(rows)
    by_pair = defaultdict(lambda: defaultdict(list))
    for i, row in enumerate(rows):
        by_pair[tuple(row['pair'])][row.get('condition_id', f'row-{i}')].append(row)
    pair_clusters = {pair: list(groups.values()) for pair, groups in by_pair.items()}
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        sample = []
        for clusters in pair_clusters.values():
            for idx in rng.integers(0, len(clusters), size=len(clusters)):
                sample.extend(clusters[int(idx)])
        try:
            values.append(fit_pooled_tradeoff_slope(sample))
        except Exception:
            continue
    if not values:
        return point, float('nan'), float('nan')
    return point, float(np.quantile(values, alpha / 2)), float(np.quantile(values, 1 - alpha / 2))


def bradley_terry(families, pair_rows, l2=1e-2):
    idx = {f: i for i, f in enumerate(families)}
    n = len(families)

    def unpack(x):
        u = np.zeros(n)
        u[1:] = x
        return u

    def obj(x):
        u = unpack(x)
        loss = 0.5 * l2 * np.dot(x, x)
        for r in pair_rows:
            a, b, chosen = r['family_a'], r['family_b'], r['selected_family']
            z = u[idx[a]] - u[idx[b]]
            y_a = 1.0 if chosen == a else 0.0
            loss += np.logaddexp(0, z) - y_a * z
        return loss

    res = minimize(obj, np.zeros(n - 1), method='BFGS')
    u = unpack(res.x)
    u -= u.mean()
    return {f: float(u[idx[f]]) for f in families}
