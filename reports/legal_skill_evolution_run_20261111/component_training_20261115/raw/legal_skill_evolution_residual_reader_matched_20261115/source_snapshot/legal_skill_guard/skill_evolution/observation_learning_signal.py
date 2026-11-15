"""Separate legal execution, source validity and observed learning progress.

Raw native scores remain available. Unresolved extraction, a source-invalid
answer, public calculation and a learned-path success are distinct feedback.
"""


def signal(row, score, source_review):
    handled=bool(row['execution']['handled'])
    correct=handled and bool(score['correct'])
    errors=source_review['failures']
    public=bool(row.get('shared_public_calculation') or row.get('not_learned_observation_success'))
    if 'used_observation_families' in row['execution'] and not row['execution']['used_observation_families']:
        public=True
    error=row.get('error') or ''
    if 'MissingPaidRead:' in error or 'OfflineReadUnavailable:' in error:
        state='missing_offline_evidence'
    elif errors:state='known_source_semantic_failure'
    elif row.get('unresolved_proposal'):state='missing_declared_observation_coverage'
    elif error:state='observation_or_runtime_failure'
    elif not handled:state='unresolved_inputs'
    elif not correct:state='executed_wrong'
    elif public:state='public_calculation_correct'
    else:state='learned_path_correct'
    return {'state':state,'raw_native_correct':correct,
        'native_correct_after_supplied_source_checks':correct and not errors,
        'learned_path_correct':correct and not errors and not public,
        'handled_wrong_after_source_checks':handled and not correct and not errors,
        'source_check_failures':errors,'evidence_available':state!='missing_offline_evidence',
        'source_truth_beyond_supplied_checks_not_certified':True}


def metrics(rows):
    if any(not r['learning_signal']['evidence_available'] for r in rows):
        raise ValueError('Missing offline evidence cannot be scored as a model failure')
    return {'partial_source_failures':sum(r['learning_signal']['source_check_failures'] for r in rows),
        'raw_native_correct':sum(r['learning_signal']['raw_native_correct'] for r in rows),
        'native_correct':sum(r['learning_signal']['native_correct_after_supplied_source_checks'] for r in rows),
        'learned_path_correct':sum(r['learning_signal']['learned_path_correct'] for r in rows),
        'handled_wrong':sum(r['learning_signal']['handled_wrong_after_source_checks'] for r in rows),
        'unresolved':sum(not r['execution']['handled'] for r in rows),
        'logical_component_reads':sum(len(r['reads']) for r in rows),
        'logical_neural_reads':sum(read.get('read_backend')!='learned_source_program'
            for r in rows for read in r['reads'])}


def rank(value):
    # On equal correct counts, fewer unresolved answers would mean MORE wrong
    # answers. Penalize handled errors instead. A cache hit does not make the
    # intrinsic neural read free relative to an independently evaluated rival.
    return (value['partial_source_failures'],-value['native_correct'],value['handled_wrong'],
        value['logical_neural_reads'],value['logical_component_reads'])
