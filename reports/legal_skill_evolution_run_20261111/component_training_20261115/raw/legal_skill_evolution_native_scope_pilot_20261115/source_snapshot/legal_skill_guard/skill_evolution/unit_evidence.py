"""Read semantic choices and select actual source units without copying prose.

The model still makes every semantic judgment. The host retrieves the selected
units verbatim and records their origin; retrieval is not a semantic check.
The historical quote transport remains strict and is never silently accepted
as this different wire protocol.
"""
import jsonschema
from copy import deepcopy

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


def context_batches(client, operations, queries, units, *, scope, checks):
    """Split only before generation, using the actual serving tokenizer.

    Every query keeps its exact meaning, units and order. Tokenization is the
    existing non-generating utility endpoint; no generation is reserved here.
    """
    prompt = reading_messages(operations, queries, units, scope=scope)
    count = client.tokenize(prompt, thinking=False)['count']
    cfg = client.config
    fits = count + cfg['max_tokens'] <= cfg['context_tokens']
    checks.append({'query_ids': [q['id'] for q in queries], 'input_tokens': count,
        'reserved_output_tokens': cfg['max_tokens'], 'context_tokens': cfg['context_tokens'],
        'fits': fits, 'generation_requests_during_check': 0})
    if fits:
        return [(queries, prompt, checks[-1])]
    if len(queries) == 1:
        raise ValueError('Complete current query exceeds fixed context without truncation: ' + queries[0]['id'])
    middle = len(queries) // 2
    return (context_batches(client, operations, queries[:middle], units, scope=scope, checks=checks)
            + context_batches(client, operations, queries[middle:], units, scope=scope, checks=checks))


def ground_selected_units(operations, queries, units, value, *, scope,
                          complete_source_absence_choices=None):
    schema = answer_schema(operations, queries)
    # Evidence IDs denote a set, not vote counts or repeated legal assertions.
    # Check every other wire requirement before the single idempotent recovery;
    # the model still receives the strict uniqueItems schema.
    raw_schema = deepcopy(schema)
    for q in queries:
        del raw_schema['properties']['answers']['properties'][q['id']]['properties']['evidence_unit_ids']['uniqueItems']
    jsonschema.validate(value, raw_schema)
    raw = value; value = deepcopy(value)
    for row in value['answers'].values():
        row['evidence_unit_ids'] = list(dict.fromkeys(row['evidence_unit_ids']))
    jsonschema.validate(value, schema)
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
        original_ids = raw['answers'][answer['id']]['evidence_unit_ids']
        if original_ids != answer['selected_evidence_unit_ids']:
            answer['raw_selected_evidence_unit_ids'] = list(original_ids)
            answer['selection_adaptation'] = 'idempotent_identical_evidence_ID_set_only'
            answer['raw_wire_uniqueItems_valid'] = False
        for witness in answer['evidence']:
            witness['quote_origin'] = 'host_retrieved_model_selected_current_unit'
    return grounded


def decode_answers(operations, queries, units, content, *, scope,
                   complete_source_absence_choices=None):
    value = strict_json(content)
    return value, ground_selected_units(operations, queries, units, value, scope=scope,
        complete_source_absence_choices=complete_source_absence_choices)
