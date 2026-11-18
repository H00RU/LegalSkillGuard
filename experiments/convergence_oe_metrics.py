"""Aggregate all official OpenExempt metrics from already sealed native scores."""

from collections import Counter, defaultdict
import math

from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def summarize(rows):
    selected = [row for row in rows if row['dataset'] == 'OpenExempt']
    paired = defaultdict(dict)
    views = {}
    for family in ('EC', 'EV'):
        cohort = [row for row in selected if row['view'] == family]
        if not cohort:
            raise ValueError('The complete OpenExempt cohort needs both EC and EV')
        statuses = Counter()
        values = defaultdict(list)
        for row in cohort:
            if family in paired[row['source']]:
                raise ValueError('A fixed OpenExempt mother cannot have repeated native views')
            detail = row['native_metrics']
            official = detail.get('official_metrics', {})
            status = official.get('status', 'unhandled_or_failed')
            statuses[status] += 1
            paired[row['source']][family] = detail.get('correct') is True
            metrics = official.get('metrics') or {}
            for metric in ('precision', 'recall', 'f1', 'mare'):
                value = metrics.get(metric)
                if type(value) in (int, float) and math.isfinite(value):
                    values[metric].append(value)
        views[family] = {'native_mothers': len(cohort), 'official_statuses': dict(statuses),
            'target_exact_matches': sum(paired[row['source']][family] for row in cohort),
            'official_only': {metric: {'available': len(valid), 'mean': math.fsum(valid) / len(valid)}
                              for metric, valid in values.items()},
            'native_f1_with_unhandled_in_denominator': math.fsum(row['grade'] or 0.0 for row in cohort) / len(cohort)}
    if any(set(views) != {'EC', 'EV'} for views in paired.values()):
        raise ValueError('Source-level exact match needs both native outputs on all mothers')
    return {'views': views, 'mothers': len(paired), 'both_views_exact_matches': sum(all(row.values()) for row in paired.values())}


def run():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    evidence = {}
    for batch in (0, 1):
        evidence[batch] = {}
        for arm in ConvergenceEvaluation.arms:
            cell = verify(read(root / 'dev' / f'B{batch}' / arm / 'scores.json'), 'cell_sha256')
            evidence[batch][arm] = {'cell_sha256': cell['cell_sha256'], **summarize(cell['source_scores'])}
    receipt = {'sealed_DEV_metrics': evidence, 'new_physical_calls': 0, 'TEST_opened': False}
    path = BASE / 'official_openexempt_DEV_metrics' / digest(receipt) / 'terminal.json'
    immutable_json(path, receipt)
    immutable_json(HANDOFF / 'B1_openexempt_official_metrics_20261118.json', {'receipt': str(path.relative_to(ROOT))})
    for arm, result in evidence[1].items():
        print(arm, result['views']['EV']['official_only'].get('mare'), result['both_views_exact_matches'])


if __name__ == '__main__':
    run()
