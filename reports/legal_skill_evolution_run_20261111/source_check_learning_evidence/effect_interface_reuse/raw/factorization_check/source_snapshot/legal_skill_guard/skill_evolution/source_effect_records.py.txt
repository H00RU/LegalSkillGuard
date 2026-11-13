"""Named source facts, lowered to the already acquired legal constructor terms.

All legal choices and links are model observations. No source-text classifier,
default actor, inferred trigger, or inferred exception is used by the compiler.
"""
import json

import jsonschema

from .native import record_schema
from .scoped_grammar import constructors, term_sort
from .semantic_execution import strict_json


INFO = {
    'confidential_information': ['confidential_information'],
    'copies_of_confidential_information': ['copies_of', ['confidential_information']],
    'confidential_information_and_copies': ['information_bundle', ['confidential_information'],
                                         ['copies_of', ['confidential_information']]],
    'copies_and_derivatives': ['information_bundle', ['copies_of', ['confidential_information']],
                              ['derivative_materials_of', ['confidential_information']]],
    'derivatives': ['derivative_materials_of', ['confidential_information']],
}
TRIGGERS = ('request', 'agreement_termination', 'service_termination', 'purpose_completion')


def schema(unit_ids):
    string = {'type': 'string'}
    literal = {'type': 'string', 'minLength': 1}
    support = {'type': 'array', 'minItems': 1,
               'items': {'type': 'integer', 'enum': list(unit_ids)}}
    info = {'type': 'string', 'enum': list(INFO)}
    retention = record_schema({
        'mode': {'type': 'string', 'enum': ['permission', 'prohibition']},
        'actor_phrase': literal, 'information_scope': info,
        'restriction_phrase': string,
        'restriction_status': {'type': 'string', 'enum': ['source_scoped', 'none']},
        'applies_after_return_or_destruction': {'type': 'boolean'}, 'support_ids': support})
    trigger = record_schema({'kind': {'type': 'string', 'enum': list(TRIGGERS)},
                             'requester_phrase': string})
    exception = record_schema({'kind': {'type': 'string', 'enum': ['authorization', 'purpose', 'cross_reference']},
                               'phrase': literal})
    duty = record_schema({
        'actor_phrase': literal, 'action': {'type': 'string', 'enum': ['return', 'destroy', 'return_or_destroy']},
        'information_scope': info, 'return_recipient_phrase': string,
        'alternative_triggers': {'type': 'array', 'minItems': 1, 'items': trigger},
        'retention_exception_indices': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}},
        'other_exceptions': {'type': 'array', 'items': exception}, 'support_ids': support})
    return record_schema({'return_or_destruction_duties': {'type': 'array', 'items': duty},
                          'post_disposal_retention': {'type': 'array', 'items': retention},
                          'unresolved': {'type': 'array', 'items': string}})


def messages(units, focus_ids):
    return [{'role': 'system', 'content':
        'Extract source facts about return/destruction duties and permission/prohibition '
        'to retain information after that process. Read only effects asserted by the focus; '
        'other units are context. Copy actor, recipient, requester and restriction phrases '
        'verbatim from cited source units. Different effects keep their own actors. '
        'Do not fill every possible category: empty lists are correct if no such effect '
        'is asserted. A heading, information definition, signature copy or postal return '
        'receipt is not a disposal/retention norm. Do not invent a duty, destruction '
        'option, termination trigger, retained-copy prohibition, or actor. '
        'information_scope identifies the exact semantic scope, not a keyword match: '
        'confidential_information; copies_of_confidential_information; '
        'confidential_information_and_copies; copies_and_derivatives; derivatives. '
        'For each duty give its action, actual return recipient, alternative triggers, '
        'and explicit exceptions. requester_phrase is used only for a request trigger. '
        'retention_exception_indices links that duty to actual permission records in '
        'post_disposal_retention, numbered from0. Empty exceptions assert that no '
        'exception limits this duty; if unresolved, omit the duty and explain instead. '
        'For a retention permission, restriction_phrase must retain ALL stated quantity, '
        'purpose, location and legal conditions, using an exact continuous source phrase; '
        'source_scoped means that phrase is supplied, none means no additional condition. '
        'A prohibition is not an exception or permission. State whether the retention '
        'effect applies after return/destruction. If the supplied fields cannot express '
        'an effect faithfully, put the issue in unresolved, do not force a category. '
        'These are current-source facts, not answers to a legal test question. '
        'Cite a focus unit in every record. Return only the response schema.'},
        {'role': 'user', 'content': json.dumps({'focus_unit_ids': list(focus_ids),
            'current_source_units': [{'id': u['id'], 'text': u['text']} for u in units]},
            ensure_ascii=False, separators=(',', ':'))}]


def decode(spec, units, focus_ids, content):
    from copy import deepcopy
    value = strict_json(content)
    texts = {u['id']: u['text'] for u in units}
    jsonschema.validate(value, schema(texts))
    if not focus_ids or not set(focus_ids) <= set(texts):
        raise ValueError('Actual source focus required')
    bank = constructors(spec)
    rows, retention = [], []

    def evidence(row):
        ids = row['support_ids']
        if len(set(ids)) != len(ids) or not set(ids).intersection(focus_ids):
            raise ValueError('Distinct current focus evidence required')
        return ' '.join(texts[i] for i in ids)

    def literal(phrase, source):
        if not phrase or phrase not in source:
            raise ValueError('Required current-source literal phrase absent')
        return phrase

    def actor(phrase, source):
        return ['named_recipient', literal(phrase, source)]

    def add(term, ids):
        if term_sort(term, bank) != 'Norm':
            raise ValueError('Acquired Norm type required')
        rows.append({'term': term, 'support_ids': list(ids)})

    for row in value['post_disposal_retention']:
        source = evidence(row)
        if not row['applies_after_return_or_destruction']:
            raise ValueError('The acquired retention type requires post-disposal scope')
        owner = actor(row['actor_phrase'], source)
        info = deepcopy(INFO[row['information_scope']])
        if row['mode'] == 'permission':
            if row['restriction_status'] == 'source_scoped':
                cond = ['retention_condition', literal(row['restriction_phrase'], source)]
            else:
                if row['restriction_phrase']:
                    raise ValueError('Unrestricted status conflicts with stated condition')
                cond = ['no_condition']
            term = ['retention_permission', owner, info, ['after_disposal'], cond]
        else:
            if row['restriction_phrase'] or row['restriction_status'] != 'none':
                raise ValueError('Conditional prohibition is unrepresentable by the acquired type')
            term = ['retention_prohibition', owner, info, ['after_disposal']]
        add(term, row['support_ids'])
        retention.append((term, row['support_ids']))

    for row in value['return_or_destruction_duties']:
        source = evidence(row)
        owner = actor(row['actor_phrase'], source)
        info = deepcopy(INFO[row['information_scope']])
        returned = None
        if row['action'] != 'destroy':
            returned = ['return_to', info, actor(row['return_recipient_phrase'], source)]
        elif row['return_recipient_phrase']:
            raise ValueError('Destruction-only duty cannot supply a return recipient')
        action = (returned if row['action'] == 'return' else ['destroy', info]
                  if row['action'] == 'destroy' else ['action_alternative', returned, ['destroy', info]])
        triggers = []
        for t in row['alternative_triggers']:
            if t['kind'] == 'request':
                triggers.append(['request_by', actor(t['requester_phrase'], source)])
            else:
                if t['requester_phrase']:
                    raise ValueError('Only a request trigger can have a requester')
                triggers.append([t['kind']])
        trigger = triggers[0]
        for t in triggers[1:]: trigger = ['trigger_alternative', trigger, t]
        exceptions, ids = [], list(row['support_ids'])
        seen = set()
        for idx in row['retention_exception_indices']:
            if idx in seen or idx >= len(retention):
                raise ValueError('Invalid or duplicate explicit retention exception link')
            seen.add(idx)
            term, supports = retention[idx]
            if term[0] != 'retention_permission':
                raise ValueError('A retention prohibition cannot grant a disposal exception')
            exceptions.append(['retention_exception', term[1], term[2], term[4]])
            ids.extend(i for i in supports if i not in ids)
        for item in row['other_exceptions']:
            exceptions.append([item['kind']+'_exception', literal(item['phrase'], source)])
        ex = ['no_exceptions']
        if exceptions:
            ex = ['exception_set', exceptions[0]]
            for item in exceptions[1:]: ex = ['add_exception', ex, item]
        add(['disposal_obligation', owner, action, trigger, ex], ids)
    return {'statements': rows, 'complete': not value['unresolved'], 'unresolved': value['unresolved']}, value
