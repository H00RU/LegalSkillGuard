"""Read each disposition effect with its own evidence using the retained consumer."""

import json
from itertools import product

import jsonschema

from legal_skill_guard.paired_interfaces import convergence_retention_interface as old
from legal_skill_guard.skill_evolution.native import record_schema

STATES = {'operative': True, 'ruled_out': False, 'unresolved': None}


def consume(grant, bar, checked):
    return old.consume({
        'retention_grant': grant, 'grant_governs_retained_information': grant,
        'disposition_bar': bar, 'bar_covers_retention_scope': bar,
        'scope_checked': checked,
    }, {})['classification']


def verify_consumer():
    module, assets = old.layouts()
    features = assets['synthesized']['features']
    for state in module.states:
        projected = old.residual.encode(features, state)
        expected = old.consume(state, {})['classification']
        if consume(*(projected[key] for key in (*old.RELATIONS, 'scope_checked'))) != expected:
            raise ValueError('The witness projection must retain all original three-valued states')
    return len(module.states)


def query(payload):
    messages, _ = old.request(payload, 'synthesized')
    evidence = {'type': 'array', 'maxItems': 12,
                'items': {'type': 'integer', 'minimum': 0, 'maximum': len(payload['indexed_spans']) - 1}}
    witness = record_schema({'state': {'enum': list(STATES)}, 'evidence': evidence})
    schema = record_schema({
        'grant': witness, 'bar': witness, 'scope_checked': {'enum': [True, False, None]},
    })
    messages[0]['content'] = (
        old.COMMON + '\nReport the positive retention grant and comprehensive disposition bar separately. '
        'An operative witness needs its own original evidence and must join the actor, protected object '
        'and post-disposition timing. For the grant, look for explicit retained material and the exception '
        'that permits keeping it after the general disposal obligation. For the bar, look for the complete '
        'obligation on the same object, rather than a rule for copying, keeping only a narrower class of '
        'records or using the information for a purpose. If the relevant effect was ruled out after review, '
        'use ruled_out and no evidence. If the language leaves the effect or its scope unsettled, '
        'use unresolved. Do not use a bar witness as evidence for the grant or infer the grant from '
        'an ongoing duty of secrecy. Preserve both effects if present.'
    )
    return messages, schema


def decode(payload, schema, raw):
    absent = {'answer': None, 'evidence': []}
    if raw['finish_reason'] != 'stop':
        return absent, raw['finish_reason']
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, schema)
        states, evidence = {}, {}
        for key in ('grant', 'bar'):
            row = value[key]
            ids = sorted(row['evidence'])
            if len(ids) != len(set(ids)):
                raise ValueError('Evidence IDs must be unique within each witness')
            status = STATES[row['state']]
            if status is True and (not ids or any(not payload['indexed_spans'][i]['text'].strip() for i in ids)):
                states[key], evidence[key] = None, []
                continue
            states[key] = status
            evidence[key] = ids if status is True else []
        answer = consume(states['grant'], states['bar'], value['scope_checked'])
        slot = {old.ENTAILMENT: 'grant', old.CONTRADICTION: 'bar'}.get(answer)
        return {'answer': answer, 'evidence': evidence[slot] if slot else []}, None
    except (ValueError, jsonschema.ValidationError):
        return absent, 'invalid_wire'


def check_truth_table():
    for grant, bar, complete in product(STATES.values(), repeat=3):
        answer = consume(grant, bar, complete)
        if grant is None and answer is not None:
            raise ValueError('An unresolved grant cannot justify a negative answer')
    return verify_consumer()
