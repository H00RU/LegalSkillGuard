"""Apply acquired, explicit source-local deltas to actual current productions.

The editor chooses new semantics; the host validates identity, provenance and
preservation. No legal interpretation or answer is supplied by this transport.
"""
from copy import deepcopy

from .source_composition import statement_fingerprint


GROUP_OPERATIONS = {'source_clause_kind', 'source_retention_scope'}


def concepts(previous, delta, visible):
    expected = {'retire_group_query_ids', 'retire_neural_query_ids', 'queries', 'answers', 'fragments', 'unresolved'}
    if set(delta) != expected:
        raise ValueError('A concept refinement declares exact retired scopes and complete new productions')
    old_queries = {q['id']: q for q in previous['queries']}
    groups = {q for q, value in old_queries.items() if value['operation'] in GROUP_OPERATIONS}
    retired = set(delta['retire_group_query_ids'])
    if len(retired) != len(delta['retire_group_query_ids']) or not retired <= groups:
        raise ValueError('Only actual acquired producing-group queries may be retired')
    neural = {q['id']: q for q in visible['queries']}
    retired_neural = set(delta['retire_neural_query_ids'])
    if len(retired_neural) != len(delta['retire_neural_query_ids']) or not retired_neural <= set(neural):
        raise ValueError('A refinement may supersede only actual current neural query identities')
    audits = visible.get('complete_source_absence_choices', {})
    if any(neural[q]['operation'] in audits for q in retired_neural):
        raise ValueError('A local source patch cannot invent or supersede a whole-source absence audit')
    fresh = {q['id'] for q in delta['queries']}
    if len(fresh) != len(delta['queries']) or fresh & (set(old_queries) | set(neural)):
        raise ValueError('New source concepts have fresh query identities')
    if (retired or retired_neural) and (not fresh or not delta['fragments']):
        raise ValueError('Retiring a claim needs an actual new source-concept production')
    new_units = {u for q in delta['queries'] for u in q['unit_ids']}
    for q in retired:
        if not set(old_queries[q]['unit_ids']) & new_units:
            raise ValueError('A retired group needs overlapping new current-source evidence')
    for q in retired_neural:
        if not set(neural[q]['unit_ids']) & new_units:
            raise ValueError('A superseded neural reading needs overlapping new source evidence')
    kept = []; untouched = []
    for index, fragment in enumerate(previous['fragments']):
        producers = set(fragment['query_ids']) & groups
        if producers and producers <= retired:
            continue
        if set(fragment['query_ids']) & retired_neural:
            raise ValueError('A superseded neural reading is still used by an untouched source frame')
        row = deepcopy(fragment)
        row['query_ids'] = [q for q in row['query_ids'] if q not in retired and q not in retired_neural]
        if not row['query_ids']:
            raise ValueError('A preserved fragment cannot lose all actual producing evidence')
        if row == fragment:
            untouched.append(index)
        kept.append(row)
    result = {'queries': [deepcopy(q) for q in previous['queries'] if q['id'] not in retired] + deepcopy(delta['queries']),
        'answers': [deepcopy(a) for a in previous['answers'] if a['id'] not in retired] + deepcopy(delta['answers']),
        'fragments': kept + deepcopy(delta['fragments']), 'unresolved': deepcopy(previous['unresolved'])}
    for reason in delta['unresolved']:
        if reason not in result['unresolved']: result['unresolved'].append(reason)
    return result, {'retired_group_query_ids': sorted(retired), 'retired_neural_query_ids': sorted(retired_neural),
        'unchanged_fragment_indices': untouched, 'original_response_not_overwritten': True,
        'retired_queries': [deepcopy(old_queries[q]) for q in sorted(retired)],
        'new_source_meaning_is_learned_not_a_semantic_adapter': True}


def statements(previous, delta, visible):
    if set(delta) != {'retire_statement_indices', 'statements', 'unresolved'}:
        raise ValueError('An ordinary source refinement declares exact retired and new statements')
    actual = dict(enumerate(previous['statements']))
    retired = set(delta['retire_statement_indices'])
    if (len(retired) != len(delta['retire_statement_indices']) or not retired <= set(actual)
            or any(type(i) is not int for i in retired)):
        raise ValueError('Only actual current statements may be retired')
    units = {u['id'] for u in visible['units']}
    for row in delta['statements']:
        if not row['support_ids'] or not set(row['support_ids']) <= units:
            raise ValueError('New statements need actual current-source unit identities')
        if row['term'][0].startswith('complete_source_') and row not in previous['statements']:
            raise ValueError('A local refinement cannot invent a whole-source absence certificate')
    new_units = {u for row in delta['statements'] for u in row['support_ids']}
    if any(not set(actual[key]['support_ids']) & new_units for key in retired):
        raise ValueError('A retired statement needs a replacement supported in its current source scope')
    rows = [deepcopy(r) for index, r in actual.items() if index not in retired]
    known = {statement_fingerprint(r) for r in rows}
    for row in delta['statements']:
        if statement_fingerprint(row) not in known:
            rows.append(deepcopy(row)); known.add(statement_fingerprint(row))
    unresolved = deepcopy(previous['unresolved'])
    for reason in delta['unresolved']:
        if reason not in unresolved: unresolved.append(reason)
    return {**deepcopy(previous), 'statements': rows, 'unresolved': unresolved,
        'complete': bool(previous['complete'] and not unresolved)}, {
        'retired_statement_indices': sorted(retired), 'untouched_statements_preserved': True,
        'new_source_meaning_is_learned_not_a_semantic_adapter': True}
