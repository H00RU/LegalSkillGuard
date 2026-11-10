"""Constructed syntax software fixtures over preserved TRAIN source text.

These are not model outputs or independent legal samples. Real reader
availability and semantic generalization require separate recorded requests.
"""
import json
from pathlib import Path

from legal_skill_guard.rr.predicate_norm_learning import enrich, fit, predict, transduce

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
