"""Attribute the B8 admission difference without using DEV labels."""

import sqlite3
from itertools import combinations

from experiments import convergence_revision6_oe_b8_screened_dev as paired
from experiments.convergence_pilot_b0 import HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import convergence_oe_portfolio as portfolio
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def gates(groups, route):
    """Count evidence for the composition and its changed single-task readers."""
    singles = {
        portfolio.PORTS[index]: tuple(reader if j == index else portfolio.ENTERING
                                      for j in range(len(portfolio.PORTS)))
        for index, reader in portfolio.changed_ports(route)
    }
    return {
        'refuted_positions': [i for i, row in sorted(groups.items()) if portfolio.candidates.refuted(row[route])],
        'required_repair_positions_by_task': {
            task: [i for i, row in sorted(groups.items()) if row[single]['signed_repairs'] > 0]
            for task, single in singles.items()
        },
    }


def run():
    fit = paired.fit
    spec, terminal, routes = paired.programs()
    folder = ROOT / read(fit.POINTER)['artifact_root']
    train = read(folder / 'predictions.json')['TRAIN']['after']
    categories = {key: {task: fit.common.categories.source_proof(view) for task, view in row['views'].items()}
                  for key, row in train.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        _, physical, (location, tag), proof = fit.b8_materials(db)
    path = ROOT / location
    if 'train' not in path.parts or sha(path) != tag or spec['provenance'] != proof:
        raise ValueError('Use the exact original four TRAIN grades and five reader versions')
    labels = read(path)
    analysis = fit.signed.fit_choices(train, fit.ROLES, categories, {key: labels[key] for key in train})
    if analysis['signed'] != terminal['fit']['after']['signed']:
        raise ValueError('Reconstruct the exact prior B8 fit before attributing its gate')
    groups = {i: {tuple(route.split('+')): row for route, row in by_route.items()}
              for i, by_route in analysis['groups'].items()}
    picked = tuple(routes['native_fit_only'])
    observed = gates(groups, picked)
    budget = fit.common.prior.GROUP_BUDGET
    selections = list(combinations(sorted(groups), budget))
    admitted_with_witness_gate = [group for group in selections if portfolio.admissible(groups, group, picked)]
    admitted_with_refutation_only = [group for group in selections
                                     if not set(group).intersection(observed['refuted_positions'])]
    record = {
        'partition': 'TRAIN', 'binding_sha256': digest(spec), 'fit_terminal_sha256': terminal['terminal_sha256'],
        'TRAIN_grade_sha256': tag, 'physical_calls_sha256': digest(sorted(physical)), 'archived_TRAIN_reads': len(physical),
        'native_fit_route': list(picked), 'native_fit_mean_gain': analysis['native_fit_gain']['+'.join(picked)],
        'source_positions_zero_based': True, **observed, 'matched_group_combinations': len(selections),
        'admitted_with_witness_gate': admitted_with_witness_gate,
        'admitted_with_refutation_only': admitted_with_refutation_only,
        'new_model_requests': 0, 'DEV_or_TEST_labels_read': False,
    }
    target = HANDOFF / 'revision6_oe_b8_gate_attribution_20261120.json'
    hash_ = immutable_json(target, record)
    print(target, hash_)
    print('required repairs by task', observed['required_repair_positions_by_task'])
    print('refutation positions', observed['refuted_positions'])
    print('admitted with witness gate', len(admitted_with_witness_gate), '/', len(selections))
    print('admitted with refutation only', len(admitted_with_refutation_only), '/', len(selections))


if __name__ == '__main__':
    run()
