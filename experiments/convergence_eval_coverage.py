"""Report native score coverage and supplementary OpenExempt metrics."""

import argparse
from collections import Counter, defaultdict

from experiments.convergence_eval_cost_audit import completed_stage
from experiments.convergence_eval_native_effects import _rows
from experiments.convergence_eval_tables import ARM_NAMES, DATASETS, _percent, _table
from experiments.convergence_formal_b1_dev import _routes
from experiments.convergence_formal_test import INITIAL_ARM, POINTER
from experiments.convergence_oe_metrics import summarize as summarize_openexempt
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json


ROUTES = {
    'synthesized_interface': 'Synthesized interface',
    'learned_external_schema': 'Adapted schema',
    'common_program': 'Common program',
    'common_compiled_fees': 'Compiled fee rules',
}


def summarize_cell(rows, report, directory, mothers_per_dataset):
    cohort, grouped = {}, defaultdict(list)
    for row in rows:
        key, dataset = row['source'], row['dataset']
        if cohort.setdefault(key, dataset) != dataset:
            raise ValueError('A native source cannot belong to multiple datasets')
        grouped[dataset].append(row)
    if Counter(cohort.values()) != {dataset: mothers_per_dataset for dataset in DATASETS}:
        raise ValueError('Coverage must follow the balanced fixed cohort')
    routes = _routes(directory, [{'key': key, 'dataset': d} for key, d in cohort.items()])
    if routes != report['routes']:
        raise ValueError('Predicted routes disagree with the sealed evaluation summary')
    if any(set(counts) - ROUTES.keys() for counts in routes.values()):
        raise ValueError('Every observed route must appear in the paper table')
    coverage = {}
    for dataset, group in grouped.items():
        native = report['native'][dataset]['views']
        views = {}
        for view, stats in native.items():
            selected = [r for r in group if view == 'all' or r['view'] == view]
            handled = sum(r['handled'] for r in selected)
            if len(selected) != stats['native_units'] or handled != stats['handled']:
                raise ValueError('The original denominators and handling counts must reconcile')
            views[view] = {'native_units': len(selected), 'handled': handled,
                           'valid': sum(r['native_metrics'].get('valid') is True for r in selected),
                           'fallback': sum(r['fallback_executed'] for r in selected)}
        coverage[dataset] = {'views': views, 'routes_by_source': routes[dataset],
                             'sources_with_unhandled_units': len({r['source'] for r in group if not r['handled']})}
    official = summarize_openexempt(rows)
    if official != report['official_OpenExempt']:
        raise ValueError('Native OpenExempt metrics must reproduce the original scorer exactly')
    return {'coverage': coverage, 'OpenExempt': official}


def render(partition, arms, mothers_per_dataset):
    native, executed, statuses = [], [], []
    for arm in ARM_NAMES:
        if arm not in arms:
            continue
        label = ARM_NAMES[arm]
        for dataset, display in DATASETS.items():
            record = arms[arm]['coverage'][dataset]
            views = record['views'].values()
            totals = {key: sum(v[key] for v in views) for key in ('handled', 'valid', 'native_units', 'fallback')}
            executed.append((label, display, f"{totals['handled']}/{totals['native_units']}",
                             f"{totals['valid']}/{totals['native_units']}", totals['fallback'],
                             record['sources_with_unhandled_units']))
        for view in ('EC', 'EV'):
            summary = arms[arm]['OpenExempt']['views'][view]
            cells = []
            for metric in ('precision', 'recall', 'f1', 'mare'):
                result = summary['official_only'].get(metric)
                if result is None:
                    cells.append('Unavailable')
                else:
                    value = f"{result['mean']:.3f}" if metric == 'mare' else _percent(result['mean'])
                    cells.append(f"{value} ({result['available']}/{mothers_per_dataset})")
            native.append((label, view, *cells))
            statuses.append((label, view, ', '.join(f"{k} {n}" for k, n in sorted(summary['official_statuses'].items()))))
    route_rows = []
    for arm in ARM_NAMES:
        if arm not in arms:
            continue
        for dataset, display in DATASETS.items():
            routes = arms[arm]['coverage'][dataset]['routes_by_source']
            route_rows.append((ARM_NAMES[arm], display, *(routes.get(route, 0) for route in ROUTES)))
    return '\n\n'.join([
        f'# B8 {partition.upper()} coverage and OpenExempt metrics',
        f'Each dataset has {mothers_per_dataset} source mothers per arm. '
        'OpenExempt percentages and mean absolute relative error use only the cases with that official metric available. '
        'The parenthetical counts give the number of available scores. The primary score table uses the fixed cohort.',
        _table(('Arm', 'View', 'Precision (%)', 'Recall (%)', 'F1 (%)', 'MARE'), native),
        '## Official OpenExempt scoring status',
        _table(('Arm', 'View', 'Source count by status'), statuses),
        '## Native output coverage',
        _table(('Arm', 'Dataset', 'Handled units', 'Valid units', 'Fallback units',
                'Mothers with unhandled units'), executed),
        '## Executed routes by source',
        _table(('Arm', 'Dataset', *ROUTES.values()), route_rows),
    ]) + '\n'


def run(partition):
    if partition == 'test' and read(POINTER)['status'] != 'completed_fixed_B8_TEST':
        raise ValueError('Wait for the terminal TEST result with all five arms and the static reference')
    stage, root, terminal, seals = completed_stage(partition, 8)
    mothers = terminal['mothers_per_arm' if partition == 'test' else 'DEV_mothers']
    reports = {arm: (root / partition / 'B8' / arm, terminal['per_arm'][arm], cell, arm)
               for arm, cell in seals.items()}
    if partition == 'test':
        reference = terminal['static_initial_reference']
        reports['static_initial_reference'] = (stage / 'initial_reference/test/B8' / INITIAL_ARM,
                                               reference, reference['cell_sha256'], INITIAL_ARM)
    arms = {}
    for name, (directory, report, seal, arm) in reports.items():
        rows = _rows(directory, seal, partition, 8, arm, mothers)
        arms[name] = summarize_cell(rows, report, directory, mothers // len(DATASETS))
    stage_hash = sha(stage / 'terminal.json')
    out = BASE / 'evaluation_coverage' / partition / stage_hash
    table = out / 'tables.md'
    text = render(partition, arms, mothers // len(DATASETS))
    if table.exists():
        if table.read_text() != text:
            raise ValueError('The saved coverage table must match the sealed results')
    else:
        out.mkdir(parents=True, exist_ok=True)
        with table.open('x') as stream:
            stream.write(text)
    receipt = {'terminal_sha256': stage_hash, 'mothers_per_arm': mothers, 'arms': arms,
               'table': str(table.relative_to(ROOT)), 'table_sha256': sha(table),
               'new_model_requests': 0, 'native_annotations_accessed': False}
    immutable_json(out / 'terminal.json', receipt)
    immutable_json(HANDOFF / f'{partition.upper()}_B8_coverage.json',
                   {'receipt': str((out / 'terminal.json').relative_to(ROOT))})
    print(table.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partition', choices=('dev', 'test'), required=True)
    run(parser.parse_args().partition)
