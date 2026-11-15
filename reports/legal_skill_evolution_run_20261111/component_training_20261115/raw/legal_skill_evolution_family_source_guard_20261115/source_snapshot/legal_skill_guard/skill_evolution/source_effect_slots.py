"""Lower model-selected effect arguments into existing executable source terms.

The model supplies every legal operator and argument. The host only preserves a
literal actor phrase, parses expressions, checks types/evidence, and assembles
the explicitly selected acquired constructor. This is a shared source frontend.
"""
import json

import jsonschema

from .native import record_schema
from .scoped_grammar import constructors, term_sort
from .scoped_reader import decode_expression
from .semantic_execution import strict_json
from .span_compiler import occurrences


EFFECTS = ('disposal_obligation', 'retention_permission', 'retention_prohibition')


def schema(spec, unit_ids):
    bank = constructors(spec)
    branches = []
    for name in EFFECTS:
        args = bank[name]['arguments']
        if args[0] != 'Participant' or bank[name]['sort'] != 'Norm':
            raise ValueError('Acquired effect signature differs')
        branches.append(record_schema({
            'constructor': {'type': 'string', 'enum': [name]},
            'actor_phrase': {'type': 'string', 'minLength': 1},
            'argument_expressions': {'type': 'array', 'minItems': len(args)-1,
                                     'maxItems': len(args)-1, 'items': {'type': 'string'}},
            'support_ids': {'type': 'array', 'minItems': 1,
                            'items': {'type': 'integer', 'enum': list(unit_ids)}}}))
    return record_schema({'statements': {'type': 'array', 'items': {'anyOf': branches}},
                          'unresolved': {'type': 'array', 'items': {'type': 'string'}}})


def messages(spec, units, focus_ids):
    return [{'role': 'system', 'content':
        'Extract the operative return/destruction and retained-copy effects asserted by '
        'the CURRENT focus clause(s). Other source units are context, not extra effects. '
        'Use ONLY the supplied acquired constructors and their meanings. A heading, '
        'description or continuing confidentiality is not a new disposal/retention effect. '
        'For EACH effect, copy its own actor_phrase verbatim from its evidence. '
        'Different effects may have different actors. The host preserves that phrase '
        'as named_recipient(actor_phrase), so do not put a constructor in actor_phrase. '
        'Choose the effect constructor, then supply its remaining positional arguments '
        'as SEPARATE short constructor expression strings, in signature order. '
        'An expression is NAME(...) with nested acquired calls; NAME() has zero arguments. '
        'No variables, choice labels or unacquired constructors. Preserve the actual '
        'information, action alternatives, trigger, exception scope, quantity and purpose. '
        'Use retention_condition with exact source wording for retention limits, rather '
        'than forcing a new source into a prior archival/law-required category. '
        'Every text argument must copy current cited wording. Do not infer a permission '
        'from absence or omit an explicit restriction. Every emitted effect must cite '
        'at least one of its focus IDs. An empty statement list can mean no target effect; '
        'put genuinely missing/unrepresentable semantics in unresolved. Do not fill '
        'unknown arguments with defaults. No task answers or native labels. Return schema.'},
        {'role': 'user', 'content': json.dumps({
            'effect_signatures': [c for c in spec['constructors'] if c['name'] in EFFECTS],
            'acquired_argument_constructors': [c for c in spec['constructors'] if c['name'] not in EFFECTS],
            'focus_unit_ids': list(focus_ids),
            'current_source_units': [{'id': u['id'], 'text': u['text']} for u in units]},
            ensure_ascii=False, separators=(',', ':'))}]


def decode(spec, units, focus_ids, content):
    value = strict_json(content)
    texts = {u['id']: u['text'] for u in units}
    if not set(focus_ids) <= set(texts) or not focus_ids:
        raise ValueError('Actual nonempty source focus required')
    jsonschema.validate(value, schema(spec, texts))
    bank = constructors(spec)
    statements, audits = [], []
    for i, row in enumerate(value['statements']):
        ids = row['support_ids']
        if len(ids) != len(set(ids)) or not set(ids).intersection(focus_ids):
            raise ValueError('Effect lacks distinct actual focus evidence at row ' + str(i))
        evidence = ' '.join(texts[uid] for uid in ids)
        actor = row['actor_phrase']
        if actor not in evidence:
            raise ValueError('Actor phrase is not literal cited source at row ' + str(i))
        term = [row['constructor'], ['named_recipient', actor]]
        for j, expression in enumerate(row['argument_expressions']):
            text_audit = []
            argument = decode_expression(expression, bank, evidence, text_audit)
            expected = bank[row['constructor']]['arguments'][j+1]
            if term_sort(argument, bank) != expected:
                raise ValueError('Wrong argument type at row ' + str(i) + ', slot ' + str(j))
            if any(not a['verbatim_in_cited_source'] for a in text_audit):
                raise ValueError('Nonliteral text argument in source-literal interface')
            term.append(argument)
            audits.append({'row': i, 'argument': j, 'text_audit': text_audit})
        if term_sort(term, bank) != 'Norm':
            raise ValueError('Wrong effect type')
        statements.append({'term': term, 'support_ids': ids})
    return {'statements': statements, 'complete': not value['unresolved'],
            'unresolved': value['unresolved']}, audits
