"""Read semantic choices and select actual source units without copying prose.

The model still makes every semantic judgment. The host retrieves the selected
units verbatim and records their origin; retrieval is not a semantic check.
The historical quote transport remains strict and is never silently accepted
as this different wire protocol.
"""
import jsonschema

from .native import record_schema
from .semantic_execution import focused_messages, strict_json
from .semantic_operations import ground_answers


TRANSPORT = 'selected_source_units_v1'
SYSTEM = '''Execute the acquired semantic reading operations on the CURRENT
source windows. All operation meanings, alternatives and examples are learned
assets, not current-source facts. Classify the operation's actual question;
do not answer a downstream task or copy an old example's choice. Preserve who
acts, the legal modality, trigger, scope and qualifications. A heading, mention
or hypothetical event is not automatically an operative duty or permission.
Return exactly one answer for every supplied query ID. Select a declared choice
or "unknown". Missing information is unknown, never an implicit negative.
Return {"answers": {query_id: {"choice": choice, "evidence_unit_ids": [unit_id]}}}.
Select the IDs of the current supplied units that support your classification.
The host retrieves those units exactly. Do not copy, rewrite or repair quotes.
Select all units needed to resolve actors, conditions and cross-references.
Every definite classification needs supporting units. Only an explicitly
declared alternative meaning absence after inspecting the complete supplied
source may have no supporting unit. Unknown may have no evidence. Demonstration
quotes belong to their original sources, never the current source. No extra IDs
or fields. Selecting a unit does not make its interpretation automatically true.'''


def answer_schema(operations, queries):
    ops = {o['name']: o for o in operations}
    if len({q['id'] for q in queries}) != len(queries):
        raise ValueError('Distinct query identities required')
    fields = {}
    for q in queries:
        if not q['unit_ids'] or any(type(i) is not int or i < 0 for i in q['unit_ids']):
            raise ValueError('Actual current unit IDs required')
        fields[q['id']] = record_schema({
            'choice': {'type': 'string', 'enum': [c['name'] for c in ops[q['operation']]['choices']] + ['unknown']},
            'evidence_unit_ids': {'type': 'array', 'uniqueItems': True,
                'items': {'type': 'integer', 'enum': q['unit_ids']}}})
    return record_schema({'answers': record_schema(fields)})


def reading_messages(operations, queries, units, *, scope, examples=True):
    return focused_messages(operations, queries, units, scope=scope,
                            examples=examples, system=SYSTEM)


def ground_selected_units(operations, queries, units, value, *, scope,
                          complete_source_absence_choices=None):
    jsonschema.validate(value, answer_schema(operations, queries))
    by_unit = {u['id']: u for u in units}
    if len(by_unit) != len(units):
        raise ValueError('Distinct current source units required')
    canonical = {'answers': []}
    for q in queries:
        row = value['answers'][q['id']]
        if not set(q['unit_ids']) <= set(by_unit):
            raise ValueError('Query refers to a noncurrent unit')
        canonical['answers'].append({'id': q['id'], 'choice': row['choice'],
            'evidence': [{'unit_id': i, 'quote': by_unit[i]['text']} for i in row['evidence_unit_ids']]})
    grounded = ground_answers(operations, queries, units, canonical, scope=scope,
        complete_source_absence_choices=complete_source_absence_choices)
    for answer in grounded:
        answer['evidence_transport'] = TRANSPORT
        answer['selected_evidence_unit_ids'] = list(value['answers'][answer['id']]['evidence_unit_ids'])
        for witness in answer['evidence']:
            witness['quote_origin'] = 'host_retrieved_model_selected_current_unit'
    return grounded


def decode_answers(operations, queries, units, content, *, scope,
                   complete_source_absence_choices=None):
    value = strict_json(content)
    return value, ground_selected_units(operations, queries, units, value, scope=scope,
        complete_source_absence_choices=complete_source_absence_choices)
