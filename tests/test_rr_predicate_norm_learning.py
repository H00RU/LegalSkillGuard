"""Constructed syntax software fixtures over preserved TRAIN source text.

These are not model outputs or independent legal samples. Real reader
availability and semantic generalization require separate recorded requests.
"""
import json
from pathlib import Path
import jsonschema
import pytest

from legal_skill_guard.rr.predicate_norm_learning import action, enrich, fit, predict, transduce

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110'


def node(key, predicate, modal='', negation='', actor='', obj=''):
    return {'id': key, 'predicate_quote': predicate, 'modal_quote': modal,
            'negation_quote': negation, 'actor_quote': actor, 'object_quote': obj}


def software_units():
    source = {r['training_key']: r for r in json.loads((BASE / 'author_checked_partial_source_feedback.json').read_text())['annotations']}
    data = [
        {'key': 'p15', 'text': source['p15']['support_spans'][0], 'syntax': {
            'nodes': [node('h', 'prohibited', actor='Volunteer'), node('a', 'disclosing'), node('r', 'provided')],
            'edges': [{'parent': 'h', 'child': 'a', 'relation': 'complement', 'quote': 'prohibited from disclosing'},
                      {'parent': 'h', 'child': 'r', 'relation': 'reference', 'quote': 'Except as provided herein'}]}},
        {'key': 'p20', 'text': source['p20']['support_spans'][0], 'syntax': {
            'nodes': [node('h', 'breached', modal='shall', negation='not'), node('a', 'disclosed')],
            'edges': [{'parent': 'h', 'child': 'a', 'relation': 'condition', 'quote': 'if the Confidential Information is disclosed'}]}},
        {'key': 'p111', 'text': source['p111']['support_spans'][0], 'syntax': {
            'nodes': [node('a', 'return', modal='shall', actor='Recipient', obj='all copies of such Discloser’s Confidential Information'),
                      node('b', 'retain', modal='may', actor='Recipient', obj='a copy of such Confidential Information')],
            'edges': [{'parent': 'a', 'child': 'b', 'relation': 'exception',
                       'quote': 'except that Recipient may retain a copy of such Confidential Information solely for archival purpose'}]}}
    ]
    return [enrich(u) for u in data]


def test_exact_induction_learns_typed_modal_scope_from_existing_feedback():
    units = software_units();library = fit(units)
    assert library['accepted'] and len(library['states']) == 1
    state = library['states'][0]
    assert state['heads'] == {'breached': 'BREACH', 'prohibited': 'F'}
    assert state['modals']['shall:Action'] == 'O'
    assert state['modals']['shall:Consequence'] == 'IDENTITY'
    assert state['modals']['may:Action'] == 'P'
    assert state['negations']['not'] == 'NOT'
    frames = predict(units[1], library)['frames']
    assert frames[0]['formula'] == ['NOT', ['BREACH', 'A']]


def test_missing_lexeme_stays_unresolved_instead_of_gaining_permission():
    unit = software_units()[1]
    state = {'heads': {}, 'negations': {'not': 'NOT'}, 'modals': {'shall:Action': 'O'}, 'bind_exceptions': False}
    frame = transduce(unit, state)['frames'][0]
    assert frame['formula'] is None
    assert frame['missing_parameters'] == ['head:breached']


def test_binding_needs_actual_agreement_and_learned_relation():
    unit = software_units()[2]
    state = {'heads': {}, 'negations': {}, 'modals': {'shall:Action': 'O', 'may:Action': 'P'}, 'bind_exceptions': True}
    assert transduce(unit, state)['frames'][1]['exception_target'] == 'a'
    unit['syntax']['nodes'][1]['actor_quote'] = ''
    assert transduce(unit, state)['frames'][1]['exception_target'] is None


def test_actual_v1_response_rejected_by_source_token_schema():
    from experiments.rr_v2_predicate_norm_learning import source_schema
    p = ROOT / 'artifacts/rr_method_redesign_20261109/predicate_norm_learning_v1_20261110/p20_syntax.json'
    real = json.loads(p.read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(json.loads(real['wire']['content']), source_schema(real['unit']))
    with pytest.raises(ValueError, match='single lexical'):
        enrich(real['acquired'])


def test_real_111_bad_operands_are_not_source_action_aliases():
    p = ROOT / 'artifacts/rr_method_redesign_20261109/source_attachment_learning_v4_20261110/p111_forest.json'
    raw = json.loads(json.loads(p.read_text())['wire']['content'])
    assert 'O(copy)' in [r['program'] for r in raw['rule-6']]
    assert 'F(destroy)' in [r['program'] for r in raw['rule-5']]
    assert action('copy') is None and action('destroy') is None
    real = json.loads((ROOT / 'artifacts/rr_method_redesign_20261109/predicate_norm_learning_spacy_v1_20261110/source_syntax_raw.json').read_text())
    unit = next(u for u in real['results'] if u['key'] == 'p111')
    assert any(t['text'] == 'Discloser' for t in unit['tokens'])
    assert action('Discloser') is None
