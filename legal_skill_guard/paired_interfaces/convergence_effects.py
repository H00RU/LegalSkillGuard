"""Paired native score effects with source-level dependence preserved."""

from collections import Counter, defaultdict

import numpy as np

from legal_skill_guard.paired_interfaces.pilot_metrics import mother_scores


def paired_source_effect(before, after, *, strata=None, seed=45, replicates=20000, native_unit_weighted=False):
    """Keep native view identities, then resample whole matched mothers."""
    before_units = {(row['source'], row['view']) for row in before}
    after_units = {(row['source'], row['view']) for row in after}
    if before_units != after_units or not before_units:
        raise ValueError('Before and after must include the same complete native tasks')
    if type(replicates) is not int or replicates < 1:
        raise ValueError('Use a positive paired bootstrap replication count')
    initial, revised = mother_scores(before), mother_scores(after)
    if strata is not None and set(strata) != set(initial):
        raise ValueError('Stratification must bind every measured mother')
    grouped = defaultdict(list)
    weights = defaultdict(list)
    units_per_source = Counter(source for source, _ in before_units) if native_unit_weighted else None
    for source in sorted(initial):
        group = strata[source] if strata is not None else 'all'
        grouped[group].append(revised[source] - initial[source])
        if native_unit_weighted:
            weights[group].append(units_per_source[source])
    point_estimates = [np.average(values, weights=weights.get(group)) for group, values in grouped.items()]
    interval = None
    if all(len(values) > 1 for values in grouped.values()):
        rng = np.random.default_rng(seed)
        draws = []
        for group, values in grouped.items():
            sampled = rng.integers(0, len(values), size=(replicates, len(values)))
            sampled_values = np.asarray(values, dtype=float)[sampled]
            sampled_weights = np.asarray(weights[group])[sampled] if native_unit_weighted else None
            draws.append(np.average(sampled_values, axis=1, weights=sampled_weights))
        interval = np.quantile(np.mean(draws, axis=0), [.025, .975]).tolist()
    return {'mothers': len(initial), 'native_units': len(before_units),
            'mean_change': float(np.mean(point_estimates)), 'paired_source_bootstrap_95': interval,
            'stratum_sizes': {str(key): len(values) for key, values in grouped.items()},
            'bootstrap_seed': seed, 'bootstrap_replicates': replicates,
            'whole_mothers_resampled': True,
            **({'native_unit_weighted': True} if native_unit_weighted else {})}
