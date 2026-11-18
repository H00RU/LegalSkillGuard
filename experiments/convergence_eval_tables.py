"""Render paper tables from a completed fixed cohort and its independent audits."""

import argparse
import math

from experiments.convergence_eval_cost_audit import completed_stage
from experiments.convergence_formal_curves import COMPARISONS
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha


ARM_NAMES = {
    'common_teacher_skill_learning': 'Ordinary',
    'method_one_only': 'M1',
    'method_two_only': 'M2',
    'both': 'M1 + M2',
    'strongest_matched_external_baseline': 'PARSE',
    'static_initial_reference': 'B0 reference',
}
METRICS = (
    ('OpenExempt', 'EC', 'OpenExempt EC F1'),
    ('OpenExempt', 'EV', 'OpenExempt EV F1'),
    ('LegalBench_Diversity', 'all', 'Diversity accuracy'),
    ('LegalBench_Diversity', 'balanced_accuracy', 'Diversity balanced accuracy'),
    ('ContractNLI', 'all', 'ContractNLI classification accuracy'),
    ('ContractNLI', 'evidence_f1', 'ContractNLI evidence F1'),
    ('RuleArena_Airline', 'all', 'Airline exact total cost'),
    ('MAUD', 'Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)',
     'MAUD ordinary-course covenant'),
    ('MAUD', 'Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)',
     'MAUD negative-interim covenant'),
    ('MAUD', 'Knowledge Definition-Answer', 'MAUD knowledge definition'),
)
DATASETS = {
    'OpenExempt': 'OpenExempt',
    'LegalBench_Diversity': 'Diversity',
    'ContractNLI': 'ContractNLI',
    'RuleArena_Airline': 'Airline',
    'MAUD': 'MAUD',
}


def _value(report, dataset, view):
    native = report['native'][dataset]
    if view == 'balanced_accuracy':
        return native[view]
    if view == 'evidence_f1':
        return native[view]['mean']
    return native['views'][view]['native_utility']


def _percent(value):
    return 'Unavailable' if value is None else f'{100 * value:.2f}'


def _effect(values):
    delta, interval = values['mean_change'], values['paired_source_bootstrap_95']
    if delta is None:
        return 'Unavailable'
    point = f'{100 * delta:+.2f}' if abs(delta) > 0.00005 else '0.00'
    return point if interval is None else f'{point} [{100 * interval[0]:.2f}, {100 * interval[1]:.2f}]'


def _table(headers, rows):
    return '\n'.join(' | '.join(('', *(str(cell) for cell in row), ''))
                     for row in (headers, ('---', *(['---:'] * (len(headers) - 1))), *rows))


def render(partition, batch, terminal, effects, costs):
    reports = dict(terminal['per_arm'])
    serialized_costs = dict(costs['arms'])
    if partition == 'test':
        reports['static_initial_reference'] = terminal['static_initial_reference']
        serialized_costs['static_initial_reference'] = costs['static_initial_reference']
    if reports.keys() != serialized_costs.keys() or set(reports) - ARM_NAMES.keys():
        raise ValueError('Every score and physical-usage row must identify the same arm')

    arms = [a for a in ARM_NAMES if a in reports]
    comparisons = effects['paired_metric_intervals']
    comparison_ids = [later + '_minus_' + earlier for earlier, later in COMPARISONS]
    if comparisons.keys() != set(comparison_ids):
        raise ValueError('Use all five fixed pair comparisons')
    names = [ARM_NAMES[later] + ' − ' + ARM_NAMES[earlier] for earlier, later in COMPARISONS]
    absolute, changes, parents = [], [], []
    for dataset, view, label in METRICS:
        scores = {arm: _value(reports[arm], dataset, view) for arm in arms}
        absolute.append((label, *map(_percent, scores.values())))
        cells = []
        for (earlier, later), identity in zip(COMPARISONS, comparison_ids, strict=True):
            row = comparisons[identity][dataset][view]
            for side, arm in (('before', earlier), ('after', later)):
                expected, observed = scores[arm], row[side]
                if not (expected is observed is None or expected is not None and observed is not None
                        and math.isclose(expected, observed, abs_tol=1e-12)):
                    raise ValueError('A paired estimate disagrees with the absolute native score')
            cells.append(_effect(row))
        changes.append((label, *cells))

    for dataset, label in DATASETS.items():
        mothers = [reports[arm]['official_OpenExempt']['both_views_exact_matches'] if dataset == 'OpenExempt'
                   else reports[arm]['native'][dataset]['complete_mothers'] for arm in arms]
        parents.append((label, *mothers))
    usage_rows = []
    for arm in arms:
        row = serialized_costs[arm]['referenced_physical']
        usage_rows.append((ARM_NAMES[arm], f"{row['physical_calls']:,}", f"{row['executor_tokens']:,}",
                           f"{row['executor_elapsed_seconds']:,.1f}"))
    usage = costs['new_physical_usage']
    return '\n\n'.join([
        f'# B{batch} {partition.upper()} results',
        f"Each arm evaluates {effects['mothers_per_arm']} fixed source mothers. Scores are percentages. "
        'Changes and 95% paired mother bootstrap intervals are in percentage points.',
        '## Native scores',
        _table(('Metric', *(ARM_NAMES[arm] for arm in arms)), absolute),
        '## Paired effects',
        _table(('Metric', *names), changes),
        '## Complete source mothers',
        'OpenExempt counts exact matches on both native views. ContractNLI counts mothers with all classification '
        'answers correct and reports evidence F1 in the native scores table.',
        _table(('Dataset', *(ARM_NAMES[arm] for arm in arms)), parents),
        '## Referenced physical executor usage',
        _table(('Arm', 'Physical calls', 'Tokens', 'Executor seconds'), usage_rows),
        f"The stage added {usage['physical_calls']:,} distinct calls, {usage['executor_tokens']:,} tokens, "
        f"and {usage['executor_elapsed_seconds']:,.1f} executor seconds. Shared physical calls can appear in "
        'more than one arm row. The local service has no per-request API invoice.',
    ]) + '\n'


def run(partition, batch):
    stage, _, terminal, arm_seals = completed_stage(partition, batch)
    audit_prefix = f'{partition.upper()}_B{batch}'
    effect_path = ROOT / read(HANDOFF / f'{audit_prefix}_native_effects_20261118.json')['receipt']
    cost_path = ROOT / read(HANDOFF / f'{audit_prefix}_physical_cost_audit_20261118.json')['receipt']
    effects, costs = read(effect_path), read(cost_path)
    terminal_sha = sha(stage / 'terminal.json')
    if (any((receipt['partition'], receipt['batch'], receipt['terminal_sha256']) !=
            (partition, batch, terminal_sha) for receipt in (effects, costs))
            or set(arm_seals) != set(costs['arms'])
            or effects['mothers_per_arm'] != terminal['mothers_per_arm' if partition == 'test' else 'DEV_mothers']):
        raise ValueError('Only audits of this exact completed evaluation can enter the tables')
    body = render(partition, batch, terminal, effects, costs)
    output = BASE / 'evaluation_tables' / partition / f'B{batch}' / terminal_sha / 'tables.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if output.read_text() != body:
            raise ValueError('The archived tables differ from the exact recomputation')
    else:
        with output.open('x') as stream:
            stream.write(body)
    print(output.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partition', choices=('dev', 'test'), required=True)
    parser.add_argument('--batch', type=int, choices=(4, 8), required=True)
    args = parser.parse_args()
    if args.partition == 'test' and args.batch != 8:
        parser.error('the fixed TEST checkpoint is B8')
    run(args.partition, args.batch)
