"""Read-only native summaries and paired, source-clustered uncertainty.

No model access, skill updates, held-out source selection or tuning lives here.
"""
from collections import Counter, defaultdict
import math
import numpy as np

DATASETS = ('OpenExempt', 'SARA_v2_Binary', 'ContractNLI', 'RuleArena_Airline', 'MAUD')
CONTRASTS = ('LiftOnly', 'CoRevOnly', 'Lift+GenericJoint', 'AllPorts+CoRev')


def average(values):
    return sum(values) / len(values) if values and all(v is not None for v in values) else None


def source_rows(results):
    rows, seen = [], set()
    for parent in results:
        key = parent['source']
        if key in seen:raise ValueError('Duplicate independent parent: ' + key)
        seen.add(key)
        views = [v for v in parent['views'] if not v['controlled']]
        if not views or len({v['view'] for v in views}) != len(views):
            raise ValueError('Missing or duplicated native view')
        grades = [v['score']['grade'] for v in views]
        if any(v is not None and (not math.isfinite(v) or not 0 <= v <= 1) for v in grades):
            raise ValueError('A native grade must be in [0,1] or explicitly unknown')
        grade = average(grades)
        if grade != parent['native_grade'] and not (grade is not None and parent['native_grade'] is not None
                and math.isclose(grade, parent['native_grade'], rel_tol=0, abs_tol=1e-12)):
            raise ValueError('Stored native parent mean differs from the actual views')
        counts, per_view = Counter(), {}
        for view in views:
            execution, score = view['execution'], view['score']
            core, fallback = bool(execution['core_executed']), bool(execution['fallback'])
            if core and fallback:raise ValueError('Core and fallback cannot both own the final answer')
            counts['native_views'] += 1
            counts['core_views'] += core
            counts['fallback_views'] += fallback
            counts['unresolved_views'] += not core and not fallback
            counts['fully_correct_core_views'] += core and bool(score['correct'])
            counts['known_core_grade_sum'] += score['grade'] * core if score['grade'] is not None else 0
            counts['unknown_grade_views'] += score['grade'] is None
            per_view[view['view']] = score['grade']
        rows.append({'source': key, 'dataset': parent['dataset'], 'native_grade': grade,
                     'per_view_grade': per_view, 'path_counts': dict(counts)})
    return rows


def summarize(results):
    rows = source_rows(results)
    by_dataset = {}
    for dataset in DATASETS:
        selected = [r for r in rows if r['dataset'] == dataset]
        paths, view_scores = Counter(), defaultdict(list)
        for row in selected:
            paths.update(row['path_counts'])
            for view, grade in row['per_view_grade'].items():view_scores[view].append(grade)
        by_dataset[dataset] = {'parent_count': len(selected),
            'native_parent_mean': average([r['native_grade'] for r in selected]),
            'native_per_view_means': {k: average(v) for k, v in view_scores.items()},
            'path_counts': dict(paths),
            'core_execution_view_rate': paths['core_views'] / paths['native_views'] if paths['native_views'] else None,
            'fallback_view_rate': paths['fallback_views'] / paths['native_views'] if paths['native_views'] else None}
    return {'source_rows': rows, 'datasets': by_dataset,
        'equal_five_dataset_macro': average([by_dataset[d]['native_parent_mean'] for d in DATASETS]),
        'aggregation': 'native view grades -> mean within independent parent -> mean per dataset -> equal five-dataset macro',
        'unknown_grades_dropped': False, 'fallback_correct_not_counted_as_core': True}


def paired_source_bootstrap(left_results, right_results, *, draws=10000, seed=20261111):
    """One statistical RNG, not another training seed or model experiment."""
    left, right = source_rows(left_results), source_rows(right_results)
    left = {r['source']: r for r in left}
    right = {r['source']: r for r in right}
    if set(left) != set(right):raise ValueError('Comparison requires identical parent sets')
    if any(set(left[k]['per_view_grade']) != set(right[k]['per_view_grade']) for k in left):
        raise ValueError('Comparison requires the same native views within every parent')
    generator = np.random.default_rng(seed)
    replicated = np.zeros(draws)
    effects, counts = {}, {}
    for dataset in DATASETS:
        keys = sorted(k for k in left if left[k]['dataset'] == dataset)
        if not keys:raise ValueError('A five-dataset comparison cannot omit a dataset')
        if any(right[k]['dataset'] != dataset for k in keys):raise ValueError('Dataset identity changed')
        if any(left[k]['native_grade'] is None or right[k]['native_grade'] is None for k in keys):
            raise ValueError('Unknown native grades cannot be dropped or imputed for an interval')
        difference = np.array([left[k]['native_grade'] - right[k]['native_grade'] for k in keys], dtype=float)
        indices = generator.integers(0, len(keys), size=(draws, len(keys)))
        replicated += difference[indices].mean(axis=1) / len(DATASETS)
        effects[dataset], counts[dataset] = float(difference.mean()), len(keys)
    return {'equal_dataset_macro_difference': sum(effects.values()) / len(DATASETS),
        'dataset_differences': effects, 'independent_parents_per_dataset': counts,
        'paired_source_bootstrap_95_percent_interval': np.quantile(replicated, [.025, .975]).tolist(),
        'four_contrast_Bonferroni_98_75_percent_interval': np.quantile(replicated, [.00625, .99375]).tolist(),
        'bootstrap_draws': draws, 'statistical_resampling_seed': seed,
        'resampling_unit': 'independent parent, stratified by dataset; all native views remain grouped',
        'independent_training_seed_uncertainty_claimed': False, 'new_model_calls': 0}


def source_mean_intervals(results, *, draws=10000, seed=20261111):
    rows = source_rows(results)
    rng = np.random.default_rng(seed)
    macro = np.zeros(draws)
    intervals = {}
    for dataset in DATASETS:
        selected = sorted((r for r in rows if r['dataset'] == dataset), key=lambda r: r['source'])
        if not selected or any(r['native_grade'] is None for r in selected):
            raise ValueError('Source uncertainty requires the complete scored five-dataset cohort')
        values = np.array([r['native_grade'] for r in selected], dtype=float)
        means = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
        intervals[dataset] = np.quantile(means, [.025, .975]).tolist()
        macro += means / len(DATASETS)
    intervals['equal_five_dataset_macro'] = np.quantile(macro, [.025, .975]).tolist()
    return {'intervals_95_percent': intervals, 'unit': 'independent parent stratified by dataset',
        'bootstrap_draws': draws, 'statistical_resampling_seed': seed,
        'training_seed_variability': False, 'new_model_calls': 0}


def nli_metrics(results, annotations):
    """Native three-label macro-F1; invalid answers retain false negatives."""
    labels = ('Entailment', 'Contradiction', 'NotMentioned')
    confusion = {truth: Counter() for truth in labels}
    evidence, missing = [], 0
    for parent in results:
        if parent['dataset'] != 'ContractNLI':continue
        for view in parent['views']:
            if view['controlled']:continue
            gold = annotations[parent['source']][view['view']]
            truth = gold['answer']
            prediction = view['execution']['answer']
            if truth not in labels:raise ValueError('Unexpected native ContractNLI label')
            valid = prediction if isinstance(prediction, str) and prediction in labels else '<invalid>'
            confusion[truth][valid] += 1
            if gold.get('evidence') is not None:
                if 'evidence_f1' in view['score']:
                    evidence.append(view['score']['evidence_f1'])
                else:
                    # Missing execution/evidence is a scored failure, not a
                    # smaller favorable evidence-only evaluation denominator.
                    evidence.append(0.0)
                    missing += 1
    f1 = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[t][label] for t in labels if t != label)
        fn = sum(n for prediction, n in confusion[label].items() if prediction != label)
        f1[label] = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return {'native_label_confusion': {k: dict(v) for k, v in confusion.items()},
        'label_f1': f1, 'three_label_macro_f1': sum(f1.values()) / len(labels),
        'evidence_f1_on_all_annotated_views': average(evidence), 'annotated_evidence_view_count': len(evidence),
        'failed_execution_or_missing_evidence_views_scored_zero': missing,
        'NotMentioned_without_evidence_annotation_excluded_only_from_evidence_metric': True}
