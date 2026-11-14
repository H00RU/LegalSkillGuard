"""Fixed compact author-event representation for the generic-view control.

This is shared serialization infrastructure, not an acquired skill. Unary event
types and binary attribute roles come directly from the author vocabulary; no
statutory test, role inversion, unstated fact or legal conclusion is supplied.
"""
from copy import deepcopy

import jsonschema

from .case_observation_contract import checked_witnesses
from .native import record_schema
from .sara_statute_kernel import GIVENS, input_schema


PROMPT = '''Extract the stated facts into the fixed compact native event view.
Read the complete finite current case. Each event/entity record has an ID, ONE
author unary kind, and its stated binary attributes. Pick the stated event's
kind, not the list of allowed vocabulary. If one entity has several explicitly
stated kinds, use several records with the SAME explicit ID, one kind each.
Attribute values
are the second native argument; the host supplies only the event ID as first.
Do not put a person's name where a service/payment/marriage event ID belongs.
agent_/patient_ direction follows the supplied common native event encoding.
Use a query's event identifier only to NAME a fact actually supported by the
case, never to assert that the queried legal claim is true. Dates and amounts
must be stated/faithfully normalized; do not invent end dates or deaths. Question
witnesses cannot establish a positive event. Every event and explicit statutory
given needs a nonempty verbatim facts witness. No quoted statute as case proof.
Use status=unread if relevant extraction is unresolved; complete means this
finite case was read, not that the real world contains no other facts. A past
onset is a valid event without asserting a future interval or inventing an end.
Only explicitly stated intermediate statutory givens go in givens, in their
original argument order/polarity. Their signatures are supplied by the same
public native case interface. Do not emit a target applicability answer.
'''


def schema_for(kernel):
    vocabulary = {p: arity for p, arity in kernel['fact_arities'].items() if p not in GIVENS}
    unary = [p for p, arity in vocabulary.items() if arity == 1]
    binary = [p for p, arity in vocabulary.items() if arity == 2]
    witness = {'type': 'array', 'minItems': 1, 'items': record_schema({
        'field': {'type': 'string', 'enum': ['facts']}, 'quote': {'type': 'string', 'minLength': 1}})}
    attributes = {'oneOf': [record_schema({'predicate': {'type': 'string', 'enum': [p]},
        'value': {'type': 'number' if p == 'amount_' else 'string'}}) for p in binary]}
    given = {'oneOf': [record_schema({'predicate': {'type': 'string', 'enum': [name]},
        'arguments': {'type': 'array', 'prefixItems': [{'type': arg['type']} for arg in types],
            'items': False, 'minItems': len(types), 'maxItems': len(types)},
        'positive': {'type': 'boolean'}, 'witnesses': witness}) for name, types in sorted(GIVENS.items())]}
    return record_schema({'status': {'type': 'string', 'enum': ['complete', 'unread']},
        'events': {'type': 'array', 'items': record_schema({
            'id': {'type': 'string', 'minLength': 1},
            'kind': {'type': 'string', 'enum': unary},
            'attributes': {'type': 'array', 'items': attributes}, 'witnesses': witness})},
        'givens': {'type': 'array', 'items': given}})


def lower(value, kernel, public):
    jsonschema.validate(value, schema_for(kernel))
    if value['status'] == 'unread':
        return {'bindings': [], 'unresolved': ['Generic event observation is unread']}
    facts, negatives, witnesses, seen = [], [], [], set()
    def add_fact(row):
        key = (row['predicate'], tuple(row['arguments']))
        if key not in seen:
            facts.append(row)
            seen.add(key)
    for event in value['events']:
        witnesses.extend(checked_witnesses(event['witnesses'], public))
        add_fact({'predicate': event['kind'], 'arguments': [event['id']]})
        for attribute in event['attributes']:
            add_fact({'predicate': attribute['predicate'], 'arguments': [event['id'], attribute['value']]})
    for given in value['givens']:
        witnesses.extend(checked_witnesses(given['witnesses'], public))
        row = {'predicate': given['predicate'], 'arguments': deepcopy(given['arguments'])}
        if given['positive']:
            add_fact(row)
        elif row not in negatives:
            negatives.append(row)
    # The source text itself witnesses a successfully completed empty finite
    # read; no event or negative fact is fabricated from that witness.
    if not witnesses:
        witnesses = checked_witnesses([{'field': 'facts', 'quote': public['facts']}], public)
    binding = {'facts': facts, 'negative_givens': negatives, 'extraction_status': 'complete'}
    jsonschema.validate(binding, input_schema(kernel))
    return {'bindings': [{'inputs': binding, 'witnesses': deepcopy(witnesses)}], 'unresolved': []}
