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


def rank_external_pilot(candidates, fixed_pilot, source_view_ids, eligible_families):
    """Apply the locked equal-library utility and logical-cost ordering."""
    by_source = {row['source']: row['dataset'] for row in fixed_pilot}
    libraries = sorted(set(by_source.values()))
    if (len(fixed_pilot) != 20 or len(by_source) != 20 or len(libraries) != 5
            or any(list(by_source.values()).count(library) != 4 for library in libraries)
            or set(source_view_ids) != set(by_source)
            or any(not views or len(views) != len(set(views)) for views in source_view_ids.values())):
        raise ValueError('External comparison requires the complete locked five-library TRAIN pilot')
    families = {candidate['family'] for candidate in candidates}
    if len(families) != len(candidates) or families != set(eligible_families) or not families:
        raise ValueError('Every eligible prespecified external family needs one comparison')

    records = []
    for candidate in candidates:
        rows = candidate['rows']
        condition = candidate['matched_public_conditions_sha256']
        tokens = candidate['comparison_logical_tokens']
        if (type(tokens) is not int or tokens < 0 or len(condition) != 64
                or any(by_source.get(row['source']) != row['dataset'] for row in rows)):
            raise ValueError('An external candidate lost its comparison scope or cost')
        per_library = {}
        for library in libraries:
            expected = {(source, task) for source, dataset in by_source.items() if dataset == library
                        for task in source_view_ids[source]}
            family_rows = [row for row in rows if row['dataset'] == library]
            per_library[library] = summarize(family_rows, expected)['mother_macro']
        records.append({
            'family': candidate['family'], 'per_library_selection_utility': per_library,
            'equal_library_selection_utility': math.fsum(per_library.values()) / len(per_library),
            'comparison_logical_tokens': tokens,
            'matched_public_conditions_sha256': condition,
        })
    if len({row['matched_public_conditions_sha256'] for row in records}) != 1:
        raise ValueError('External pilot readers must share source information, model and comparison budget')
    order = sorted(records, key=lambda row: (-row['equal_library_selection_utility'],
                                              row['comparison_logical_tokens'], row['family']))
    return {'selected_family': order[0]['family'], 'ranked_candidates': order,
            'selection_only_not_a_headline_metric': True, 'includes_all_twenty_TRAIN_sources': True}
