"""Execute the current acquired φ ABI on actual current-source neural reads.

The code is extracted from the current C acquisition path. Typed fragments,
producing queries, evidence scope and the ban on whole-Norm fragments stay the
same. This module contains no experiment path or source lookup.
"""
from copy import deepcopy

from .objects import digest
from .scoped_grammar import constructors, term_sort
from .semantic_operations import validate_queries
from .source_observations import encode_source_observations, fact
from .span_compiler import execute_json
from .unit_evidence import ground_selected_units


def _typed(observation, spec):
    value = deepcopy(observation); schema = constructors(spec)
    for identity, node in value['term_nodes'].items():
        if isinstance(node, list):
            value['context']['facts'].append(fact('term_type', identity, schema[node[0]]['sort']))
    value['public_type_annotation'] = {'source': 'unchanged common constructor types', 'new_legal_semantics': False}
    return value


def convert(library, raw):
    if 'source_concept_program' not in library:
        return _typed(raw, library['spec'])
    v = raw['visible_inputs']
    value = execute_json(library['source_concept_program'], {
        'source_text': v['source_text'], 'source_spans': v['units'],
        'source_output': v['source_output'], 'semantic_answers': v['answers']}, {}, allow_helpers=True)
    refinement = None
    if library.get('source_refinement_program'):
        from .source_local_refinement import concepts
        delta = execute_json(library['source_refinement_program'], {'source_text': v['source_text'],
            'source_spans': v['units'], 'semantic_answers': v['answers'], 'previous_output': deepcopy(value)},
            {}, allow_helpers=True)
        value, refinement = concepts(value, delta, v)
    assert set(value) == {'queries', 'answers', 'fragments', 'unresolved'}
    queries = validate_queries(value['queries'], library['operations'], v['units'])
    answers = {a['id']: a for a in value['answers']}
    assert len(answers) == len(value['answers']) and set(answers) == {q['id'] for q in queries}
    assert not set(answers) & {q['id'] for q in v['queries']}
    grounded = []
    for query in queries:
        answer = answers[query['id']]
        assert set(answer) == {'id', 'choice', 'evidence_unit_ids'}
        assert answer['choice'] not in library['complete_source_absence_choices'].get(query['operation'], [])
        grounded += ground_selected_units(library['operations'], [query], v['units'], {'answers': {
            query['id']: {k: answer[k] for k in ('choice', 'evidence_unit_ids')}}},
            scope=library['operation_scopes'][query['operation']],
            complete_source_absence_choices=library['complete_source_absence_choices'])
    all_answers = v['answers'] + grounded; by_id = {a['id']: a for a in all_answers}
    shape = constructors(library['spec']); rows = []
    def check_part(term):
        if isinstance(term, list):
            assert shape[term[0]]['sort'] in {'Participant', 'Information', 'Action', 'Trigger',
                                           'Condition', 'Exception', 'ExceptionSet'}
            for child in term[1:]: check_part(child)
    for fragment in value['fragments']:
        assert set(fragment) == {'term', 'support_ids', 'query_ids'} and fragment['support_ids'] and fragment['query_ids']
        term_sort(fragment['term'], shape); check_part(fragment['term'])
        assert all(q in by_id and by_id[q]['choice'] != 'unknown' for q in fragment['query_ids'])
        assert set(fragment['support_ids']) <= {w['unit_id'] for q in fragment['query_ids'] for w in by_id[q]['evidence']}
        rows.append({'term': fragment['term'], 'support_ids': fragment['support_ids']})
    all_queries = v['queries'] + queries
    encoded = encode_source_observations(raw['context']['id'], source_text=v['source_text'], units=v['units'],
        source_output={'statements': rows, 'complete': False, 'unresolved': value['unresolved']},
        operations=library['operations'], queries=all_queries, answers=all_answers, scope=v['scope'],
        query_scopes={q['id']: library['operation_scopes'][q['operation']] for q in all_queries},
        complete_source_absence_choices=library['complete_source_absence_choices'], query_aliases=v.get('query_aliases'))
    encoded['source_concept_execution'] = {'program_sha256': digest(library['source_concept_program']),
        'program_output': value, 'neural_query_ids': [q['id'] for q in v['queries']],
        'program_query_ids': [q['id'] for q in queries], 'program_answers_are_not_neural_readings': True,
        'whole_norms_forbidden': True, 'new_model_requests': 0}
    encoded = _typed(encoded, library['spec'])
    if refinement:
        retired = set(refinement['retired_neural_query_ids'])
        encoded['context']['facts'] = [f for f in encoded['context']['facts']
            if not (f['predicate'] in ('reader_query', 'query_choice', 'evidence_unit') and f['arguments'][0] in retired)]
        encoded['source_concept_execution']['learned_refinement'] = refinement
        encoded['source_concept_execution']['refinement_program_sha256'] = digest(library['source_refinement_program'])
    links = []
    for fragment in value['fragments']:
        for identity, root in encoded['legacy_roots'].items():
            if root['term'] == fragment['term']:
                for query in fragment['query_ids']:
                    edge = fact('fragment_query', identity, query)
                    if edge not in links: links.append(edge)
    encoded['context']['facts'] += links
    encoded['fragment_query_provenance'] = {'edges': links, 'from_actual_program_output': True,
                                          'new_legal_semantics': False}
    return encoded
