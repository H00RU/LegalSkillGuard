from copy import deepcopy

from legal_skill_guard.skill_evolution.source_candidate_diagnosis import typed_envelope


def fixture():
    ctor = [('receiving_party', 'Participant', []), ('confidential_information', 'Information', []),
            ('disclose', 'Action', ['Information', 'Participant']), ('no_condition', 'Condition', []),
            ('permission', 'Norm', ['Participant', 'Action', 'Condition']),
            ('complete_source_no_disclosure_permission', 'Description', [])]
    library = {'spec': {'constructors': [{'name': n, 'sort': s, 'arguments': a, 'meaning': n} for n, s, a in ctor]},
        'language': {'rules': [{'head': {'predicate': 'compose'}, 'body': [
            {'predicate': 'reader_query', 'arguments': [{'var': 'Q'}, 'source_clause_kind'], 'sign': 'positive'},
            {'predicate': 'query_choice', 'arguments': [{'var': 'Q'}, 'source_permission'], 'sign': 'positive'}]}]},
        'renderers': [{'predicate': 'compose', 'term': ['permission', ['receiving_party'], {'term_argument': 0}, {'term_argument': 1}]},
                      {'predicate': 'absence', 'term': ['complete_source_no_disclosure_permission']}]}
    observed = {'queries': [{'id': 'a', 'operation': 'source_clause_kind'}, {'id': 'b', 'operation': 'source_clause_kind'}],
        'answers': [{'id': 'a', 'choice': 'source_permission'}, {'id': 'b', 'choice': 'source_permission'}],
        'fragments': [{'term': ['disclose', ['confidential_information'], ['receiving_party']], 'support_ids': [1], 'query_ids': ['a']},
                      {'term': ['no_condition'], 'support_ids': [1], 'query_ids': ['a']}], 'unresolved': []}
    return library, observed


def test_existing_scoped_parts_can_form_a_typed_candidate_but_never_an_absence():
    library, observed = fixture(); rows = typed_envelope(library, observed)
    assert len(rows) == 1 and rows[0]['statement']['term'][0] == 'permission'
    assert rows[0]['source_semantics_not_certified']


def test_source_overlap_does_not_allow_different_producers_to_mix():
    library, observed = fixture(); observed['fragments'][1]['query_ids'] = ['b']
    assert typed_envelope(library, observed) == []


def test_unknown_or_opposite_actual_choice_does_not_create_permission():
    for choice in ['unknown', 'source_prohibition']:
        library, observed = fixture(); observed['answers'][0]['choice'] = choice
        assert typed_envelope(library, observed) == []
