import json

from experiments.convergence_revision5_cni_agreement_object import compile_scope
from experiments.convergence_revision5_cni_keyed_disclosure import decode, layouts
from experiments.convergence_revision5_cni_keyed_disclosure_scope import reconcile


CASE = {'public': {'indexed_spans': [{}, {}, {}], 'groups': {'one': [0], 'two': [1]}}}
CHECKED = {'outside_scope': False, 'outside_evidence': [], 'whole_document_checked': True}


def completed(value):
    return {'content': json.dumps(value), 'finish_reason': 'stop'}


def test_disclosure_force_and_event_object_cannot_cross_group_keys():
    layouts()
    fields = ('fact_is_object', 'contains_restriction', 'contains_unrestricted_grant')
    marks = {'one': dict(zip(fields, (False, True, False), strict=True)),
             'two': dict(zip(fields, (True, False, False), strict=True))}
    rows = {key: {'fields': v, 'evidence': CASE['public']['groups'][key], 'unresolved': False} for key, v in marks.items()}
    assert decode(CASE, 'fixed', completed({**CHECKED, 'groups': rows}))[0]['answer'] == 'NotMentioned'
    rows['one']['fields']['fact_is_object'] = True
    assert decode(CASE, 'fixed', completed({**CHECKED, 'groups': rows}))[0] == {
        'answer': 'Entailment', 'evidence_sentence_ids': [0]}
    rows['one']['evidence'] = [1]
    assert decode(CASE, 'fixed', completed({**CHECKED, 'groups': rows}))[0]['answer'] is None


def test_direct_control_can_cite_an_operative_clause_outside_the_marked_groups():
    result = completed({**CHECKED, 'outside_scope': True, 'outside_evidence': [2],
                        'answer': 'Entailment', 'evidence': [2]})
    assert decode(CASE, 'direct', result) == ({'answer': 'Entailment', 'evidence_sentence_ids': [2]}, None)


def test_direct_scope_distinguishes_prohibition_grant_and_unresolved_event():
    def source(text):
        return {'public': {'source_text': text, 'sentence_spans': [[0, len(text)]]}}

    _, prohibition = compile_scope(source('Recipient shall not disclose the existence of this Agreement.'))
    _, grant = compile_scope(source('Recipient may freely publish the existence of this Agreement.'))
    assert prohibition == {'answer': 'Entailment', 'evidence_sentence_ids': [0]}
    assert grant == {'answer': 'Contradiction', 'evidence_sentence_ids': [0]}
    assert compile_scope(source('The company shall disclose technical data during negotiations.')) == ('unbound_event_cue', None)


def test_scope_normalization_requires_a_checked_document_and_only_group_local_ids():
    checked = {**CHECKED, 'outside_scope': True, 'outside_evidence': [0, 1]}
    updated, changed = reconcile(CASE, completed(checked))
    assert changed and json.loads(updated['content']) == {**checked, 'outside_scope': False}
    for extra in ({'outside_evidence': [0, 2]}, {'outside_evidence': []}, {'whole_document_checked': False}):
        raw = completed({**checked, **extra})
        assert reconcile(CASE, raw) == (raw, False)
