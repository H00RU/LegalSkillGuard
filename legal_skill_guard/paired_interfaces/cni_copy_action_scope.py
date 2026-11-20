"""Compile the legal effect at each copy mention for the creation hypothesis."""

import json
from itertools import product

import jsonschema

from legal_skill_guard.paired_interfaces.cni_copy_lifecycle import ABSENT, COPY, NO, YES
from legal_skill_guard.skill_evolution.native import record_schema

ROLES = ('synthesized', 'fixed', 'direct')
EVENTS = ('new_copy', 'existing_record', 'different_action', None)
OBJECTS = (True, False, None)
EFFECTS = ('operative_grant', 'operative_bar', 'future_approval_only', 'description', None)
RELATIONS = ('copy_grant', 'copy_bar', 'approval_needed', 'nonoperative', None)


def read_relation(event, protected, condition):
    """Join the action, protected object and effect at the same occurrence."""
    if event in ('existing_record', 'different_action') or protected is False or condition == 'description':
        return 'nonoperative'
    if None in (event, protected, condition):
        return None
    return {'operative_grant': 'copy_grant', 'operative_bar': 'copy_bar',
            'future_approval_only': 'approval_needed'}[condition]


def flags(relation):
    if relation is None:
        return None, None
    return relation == 'copy_grant', relation in ('copy_bar', 'approval_needed')


def check_equivalence():
    states = tuple(product(EVENTS, OBJECTS, EFFECTS))
    for event, protected, condition in states:
        relevant = (False if event in ('existing_record', 'different_action') or protected is False
                    or condition == 'description' else None if None in (event, protected, condition) else True)
        reference = (None, None) if relevant is None else (
            relevant and condition == 'operative_grant',
            relevant and condition in ('operative_bar', 'future_approval_only'),
        )
        if flags(read_relation(event, protected, condition)) != reference:
            raise ValueError('All local states must preserve the creation consumer')
    return len(states)


def public_input(view, spans):
    mentions = {}
    for i, text in enumerate(spans):
        for event in COPY.finditer(text):
            mentions[f'm{len(mentions) + 1}'] = {'span': i, 'range_in_span': list(event.span()), 'word': event[0]}
    return {'document': view['public']['source_text'], 'mentions': mentions,
            'indexed_spans': [{'id': i, 'text': span} for i, span in enumerate(spans)],
            'question': view['public']['question']}


GUIDE = (
    'Read the complete agreement and the original question. Decide only about making a new copy or record of '
    'the disclosing party’s confidential information by the receiving party or its covered people. '
    'The mention list identifies tokens in the indexed evidence spans. A copy already in existence, keeping a '
    'record after return, delivering a copy of the agreement or a notice, and reproducing a copyright legend are '
    'different operations. Past creation, a defined object, and subsequent handling do not alone grant '
    'permission to make a new copy. A present permission may be limited to a stated purpose or eligible '
    'worker. A restriction requiring later discretionary written approval gives no present permission. '
    'When use, copying and disclosure are listed together, determine which verb any qualification actually '
    'governs. A recipient qualification for disclosure does not in itself authorize copying. Resolve actor, '
    'protected object and condition using adjacent indexed spans where the agreement links them. '
    'An operative permission that covers any instance establishes Entailment. Contradiction requires a '
    'bar on making copies and no actual permission. NotMentioned requires coverage and no operative rule '
    'of either polarity. Acknowledge unresolved scope. Use only original evidence span IDs.'
)


def request(public, role):
    evidence = {'type': 'array', 'items': {
        'type': 'integer', 'minimum': 0, 'maximum': len(public['indexed_spans']) - 1,
    }, 'maxItems': 8}
    if role == 'direct':
        detail = 'Return the native judgment with the complete original evidence.'
        schema = record_schema({'answer': {'enum': [YES, NO, ABSENT, None]}, 'evidence': evidence})
    else:
        if role == 'fixed':
            ports = {'event': {'enum': list(EVENTS)}, 'protected_object': {'enum': list(OBJECTS)},
                     'effect': {'enum': list(EFFECTS)}}
            detail = (
                'For each mention, report the referenced operation as event, whether it concerns the '
                'receiving party and the disclosing party’s protected material as protected_object, '
                'and the operative effect at that exact mention. Use null for an unresolved field.'
            )
        else:
            ports = {'scoped_effect': {'enum': list(RELATIONS)}}
            detail = (
                'For each mention, return the rule actually binding the receiving party’s new act of '
                'copying the disclosing party’s protected material. Use copy_grant for a present permission, '
                'copy_bar for a prohibition, approval_needed for a bar absent further discretionary approval, '
                'nonoperative for an existing copy, different object or descriptive mention, and null if unresolved.'
            )
        detail += (' Include the governing and object spans necessary to support an operative effect. '
                   'Set checked_coverage after reviewing the full agreement for copying authorities.')
        schema = record_schema({
            'mentions': record_schema(dict.fromkeys(public['mentions'], record_schema({**ports, 'evidence': evidence}))),
            'checked_coverage': {'type': 'boolean'},
        })
    messages = [{'role': 'system', 'content': GUIDE + '\n' + detail},
                {'role': 'user', 'content': json.dumps(public, ensure_ascii=False, sort_keys=True)}]
    return messages, schema


def consume(observations, coverage):
    evidence = {'copy_grant': set(), 'copy_bar': set(), 'approval_needed': set()}
    unknown = False
    for relation, citations in observations:
        if relation in evidence and citations:
            evidence[relation].update(citations)
        elif relation != 'nonoperative':
            unknown = True
    if evidence['copy_grant']:
        return {'answer': YES, 'evidence': sorted(evidence['copy_grant'])}
    if coverage and not unknown:
        against = evidence['copy_bar'] | evidence['approval_needed']
        return {'answer': NO, 'evidence': sorted(against)} if against else {'answer': ABSENT, 'evidence': []}
    return {'answer': None, 'evidence': []}


def decode(public, role, schema, raw):
    missing = {'answer': None, 'evidence': []}
    if raw['finish_reason'] != 'stop':
        return missing, raw['finish_reason']
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    if role == 'direct':
        if value['answer'] not in (YES, NO):
            return {'answer': value['answer'], 'evidence': []}, None
        return ({**value, 'evidence': sorted(set(value['evidence']))}, None) if value['evidence'] else (
            missing, 'missing_evidence',
        )
    observations = []
    for key, spot in public['mentions'].items():
        row = value['mentions'][key]
        relation = (read_relation(row['event'], row['protected_object'], row['effect'])
                    if role == 'fixed' else row['scoped_effect'])
        citations = row['evidence']
        observations.append((relation, citations if spot['span'] in citations else []))
    return consume(observations, value['checked_coverage']), None
