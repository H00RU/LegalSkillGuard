"""Complete-cohort mother-level native metrics and D0-only fixed-plan choice."""
from collections import defaultdict
import math


def mother_scores(rows):
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        identity = (row['source'], row['view'])
        if identity in identities:
            raise ValueError('A mother/native-view score was counted twice')
        identities.add(identity)
        grade = row['grade']
        if type(grade) not in (int, float) or not math.isfinite(grade) or not 0 <= grade <= 1:
            raise ValueError('Native grading is incomplete or outside its declared range')
        groups[row['source']].append(grade)
    return {source: math.fsum(values) / len(values) for source, values in groups.items()}


def summarize(rows, expected_views):
    if {(row['source'], row['view']) for row in rows} != set(expected_views):
        raise ValueError('Every fixed native task, including failures, must remain in the denominator')
    scores = mother_scores(rows)
    if not scores:
        raise ValueError('A reported cohort must be nonempty')
    return {'mothers': len(scores), 'native_tasks': len(rows),
            'mother_macro': math.fsum(scores.values()) / len(scores),
            'handled_native_tasks': sum(bool(row['handled']) for row in rows),
            'unresolved_or_failed_native_tasks': sum(not row['handled'] for row in rows),
            'per_mother': scores, 'all_fixed_native_tasks_in_denominator': True}


def select_fixed_plans(rows, lock_rows, plan_orders, source_view_ids):
    """Candidate order is frozen; calibration/evaluation rows never affect it."""
    selections = {}
    for dataset, plans in plan_orders.items():
        sources = {row['key'] for row in lock_rows
                   if row['dataset'] == dataset and row['role'] == 'development'}
        expected = {(source, view) for source in sources for view in source_view_ids[source]}
        if not expected:
            raise ValueError('A fixed library needs original D0 sources')
        reports = []
        for index, plan in enumerate(plans):
            selected = [row for row in rows if row['source'] in sources and row['plan'] == plan]
            if any(row['role'] != 'development' or row['dataset'] != dataset for row in selected):
                raise ValueError('A score lost its fixed D0 source/role binding')
            reports.append({'plan': plan, 'candidate_index': index,
                            **summarize(selected, expected)})
        best = max(reports, key=lambda row: (row['mother_macro'], -row['candidate_index']))
        selections[dataset] = {'plan': best['plan'], 'candidate_index': best['candidate_index'],
            'development_mother_macro': best['mother_macro'], 'development_sources': sorted(sources),
            'candidate_development_metrics': reports,
            'calibration_or_structure_evaluation_grades_used': False}
    return selections
