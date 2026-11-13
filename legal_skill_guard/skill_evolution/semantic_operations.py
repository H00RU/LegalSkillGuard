"""Acquired semantic reading operations, executed by the frozen model.

This transport supplies no legal predicates. Operation meanings, alternatives,
demonstrations and the source-reading program are acquired together. The host
only preserves identity, current-source windows and exact evidence. A grounded
answer remains a fallible semantic judgment, not a certified legal fact.
"""
import json

import jsonschema

from .native import record_schema
from .objects import digest
from .span_compiler import execute_json, occurrences


CHOICE = record_schema({'name': {'type': 'string', 'minLength': 1},
                       'meaning': {'type': 'string', 'minLength': 1}})
EXAMPLE = record_schema({'source': {'type': 'string'},
                        'quote': {'type': 'string', 'minLength': 1},
                        'choice': {'type': 'string'}})
OPERATION = record_schema({'name': {'type': 'string', 'minLength': 1},
    'question': {'type': 'string', 'minLength': 1},
    'choices': {'type': 'array', 'minItems': 1, 'items': CHOICE},
    'examples': {'type': 'array', 'items': EXAMPLE}})
PLAN = record_schema({'queries': {'type': 'array', 'items': record_schema({
    'id': {'type': 'string', 'minLength': 1}, 'operation': {'type': 'string'},
    'unit_ids': {'type': 'array', 'minItems': 1,
                 'items': {'type': 'integer', 'minimum': 0}}})}})
ANSWER = record_schema({'id': {'type': 'string'}, 'choice': {'type': 'string'},
    'evidence': {'type': 'array', 'items': record_schema({
        'unit_id': {'type': 'integer', 'minimum': 0},
        'quote': {'type': 'string', 'minLength': 1}})}})
RESPONSE = record_schema({'answers': {'type': 'array', 'items': ANSWER}})
NATIVE_LABELS = {'Entailment', 'Contradiction', 'NotMentioned'}

SYSTEM = '''Execute the acquired semantic reading operations on the CURRENT
source windows. All operation meanings, alternatives and examples are learned
assets, not current-source facts. Classify the operation's actual question;
do not answer a downstream task or copy an old example's choice. Preserve who
acts, the legal modality, trigger, scope and qualifications. A heading, mention
or hypothetical event is not automatically an operative duty or permission.
Return exactly one answer for every supplied query ID. Select a declared choice
or "unknown". Missing information is unknown, never an implicit negative.
For every non-unknown choice, quote the actual current words supporting that
classification, inside the query's supplied unit IDs. Quotes may fold whitespace
but may not change words. Negative alternatives also need actual evidence; mere
absence is insufficient unless the declared operation explicitly asks whether
something appears in the complete supplied window. No extra IDs or fields.'''


def validate_operations(operations, training_texts):
    """Check acquired examples against their actual TRAIN parent, not labels."""
    jsonschema.validate(operations, {'type': 'array', 'items': OPERATION})
    names = [o['name'] for o in operations]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate operation names')
    for op in operations:
        choices = [c['name'] for c in op['choices']]
        if len(set(choices)) != len(choices) or 'unknown' in choices:
            raise ValueError('Choices must be distinct; unknown is reserved')
        if NATIVE_LABELS.intersection(choices):
            raise ValueError('Native answer labels are not source operations')
        for example in op['examples']:
            if example['source'] not in training_texts:
                raise ValueError('Operation demonstration outside acquisition TRAIN')
            if example['choice'] not in {*choices, 'unknown'}:
                raise ValueError('Undeclared demonstration choice')
            if not occurrences(training_texts[example['source']], example['quote']):
                raise ValueError('Demonstration does not quote its actual TRAIN source')


def prepare_queries(program, operations, text, units, *, answers=(), source_output=None):
    """The acquired planner chooses windows; the host adds no legal routing."""
    inputs={'phase':'plan','source_text':text,'source_spans':units,'semantic_answers':list(answers)}
    if source_output is not None:inputs['source_output']=source_output
    raw = execute_json(program, inputs, {}, allow_helpers=True)
    jsonschema.validate(raw, PLAN)
    indexed = {u['id']: u for u in units}
    if len(indexed) != len(units):
        raise ValueError('Duplicate current unit IDs')
    known = {o['name'] for o in operations}
    ids = [q['id'] for q in raw['queries']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate query IDs')
    for q in raw['queries']:
        if q['operation'] not in known:
            raise ValueError('Unknown acquired operation')
        if len(set(q['unit_ids'])) != len(q['unit_ids']) or not set(q['unit_ids']) <= set(indexed):
            raise ValueError('Invalid or duplicate current window units')
    return raw['queries']


def messages(operations, queries, units, *, examples=True, system=SYSTEM):
    by_op = {o['name']: o for o in operations}
    by_unit = {u['id']: u for u in units}
    used = dict.fromkeys(q['operation'] for q in queries)
    definitions = [{**by_op[n], 'examples': by_op[n]['examples'] if examples else []} for n in used]
    value = {'operations': definitions, 'current_queries': [
        {**q, 'current_units': [{'id': i, 'text': by_unit[i]['text']} for i in q['unit_ids']]}
        for q in queries]}
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(value, ensure_ascii=False)}]


def ground_answers(operations, queries, units, value, *, scope=None,
                   complete_source_absence_choices=None):
    """Retain all exact quote occurrences; do not invent semantic negatives."""
    jsonschema.validate(value, RESPONSE)
    ops = {o['name']: o for o in operations}
    absence = {} if complete_source_absence_choices is None else complete_source_absence_choices
    if not isinstance(absence, dict):
        raise ValueError('Explicit operation/choice absence declarations required')
    for operation, choices in absence.items():
        if (operation not in ops or not isinstance(choices, list)
                or any(not isinstance(c, str) for c in choices)
                or len(set(choices)) != len(choices)
                or not set(choices) <= {c['name'] for c in ops[operation]['choices']}):
            raise ValueError('Absence declaration must name actual acquired choices')
    by_q = {q['id']: q for q in queries}
    by_u = {u['id']: u for u in units}
    ids = [a['id'] for a in value['answers']]
    if len(set(ids)) != len(ids) or set(ids) != set(by_q):
        raise ValueError('Every query needs exactly one answer; no missing/default answers')
    grounded = []
    for answer in value['answers']:
        q = by_q[answer['id']]
        choices = {c['name'] for c in ops[q['operation']]['choices']} | {'unknown'}
        if answer['choice'] not in choices:
            raise ValueError('Answer choice outside its acquired operation')
        source_evidence = {}
        if answer['choice'] in absence.get(q['operation'], []):
            # This is an explicit model judgment over the entire current
            # source, not a negative inferred from silence or missing rules.
            # A nonexistent passage cannot be quoted. Record the actual
            # supplied source instead; its meaning remains fallible.
            if scope != 'window' or set(q['unit_ids']) != set(by_u):
                raise ValueError('An explicit source-absence choice requires the complete current source in window scope')
            source_evidence = {'complete_source_evidence': {
                'basis': 'explicit_reader_absence_judgment',
                'unit_ids': list(q['unit_ids']),
                'source_units_sha256': digest([by_u[i] for i in q['unit_ids']])}}
        if answer['choice'] != 'unknown' and not answer['evidence'] and not source_evidence:
            raise ValueError('A definite semantic judgment needs current evidence')
        evidence = []
        for witness in answer['evidence']:
            if witness['unit_id'] not in q['unit_ids']:
                raise ValueError('Evidence outside this query window')
            hits = occurrences(by_u[witness['unit_id']]['text'], witness['quote'])
            adaptation = {}
            if not hits:
                # Some real readers render typographic quotation marks as
                # ASCII. Recover only a unique otherwise-identical current
                # span; never repair words, case, numbers or missing clauses.
                text = by_u[witness['unit_id']]['text']
                quotes = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"})
                adapted = occurrences(text.translate(quotes), witness['quote'].translate(quotes))
                if len(adapted) == 1:
                    start, end = adapted[0]
                    actual_quote = text[start:end]
                    adaptation = {'raw_quote': witness['quote'],
                        'quote_adaptation': 'unique_typographic_quotes_only'}
                    witness = {**witness, 'quote': actual_quote}
                    hits = occurrences(text, actual_quote)
            if not hits:
                raise ValueError('Nonverbatim current-source evidence')
            evidence.append({**witness, **adaptation, 'unit_occurrences': [list(h) for h in hits]})
        grounded.append({**answer, **source_evidence, 'operation': q['operation'], 'evidence': evidence,
                         'source_semantics_verified': False})
    by_id = {a['id']: a for a in grounded}
    return [by_id[q['id']] for q in queries]


def batches(queries, size=12):
    """Bound individual JSON outputs, not the research request budget."""
    if type(size) is not int or size < 1:
        raise ValueError('Positive physical batch size required')
    return [queries[i:i+size] for i in range(0, len(queries), size)]


def read_semantics(client, call_prefix, source, operations, queries, units, *, examples=True):
    from .runtime import decoder_schema
    wire, _ = decoder_schema(RESPONSE)
    answers, events = [], []
    for number, batch in enumerate(batches(queries)):
        prompt = messages(operations, batch, units, examples=examples)
        call_id = call_prefix + ':batch:' + str(number) + ':' + digest(prompt)
        result = client.generate(call_id, source=source, purpose='skill_replay',
                                 messages=prompt, thinking=False, schema=wire)
        if result['finish_reason'] != 'stop':
            raise ValueError('Incomplete semantic operation response; preserved, no automatic retry')
        value = json.loads(result['content'])
        answers.extend(ground_answers(operations, batch, units, value))
        events.append({'call_id': call_id, 'queries': len(batch),
                       'result': result, 'raw_answer': value})
    return answers, events


def finish(program, text, units, answers):
    return execute_json(program, {'phase': 'finish', 'source_text': text,
        'source_spans': units, 'semantic_answers': answers}, {}, allow_helpers=True)
