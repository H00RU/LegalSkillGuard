"""Current-source neural bindings for genuinely acquired relation frames.

The parser cannot invent fields or roles, and every binding is inside its
actual source clause.  Legal relation recognition is still a fallible model
step; passing these structural checks does not certify its legal meaning.
"""
import jsonschema

from .native import record_schema
from .objects import digest
from .span_compiler import align_slots, locate, recognize_terms


def frames_from_rules(spec, rules):
    return [{'id': r['id'], 'kind': r['kind'], 'constants': r['constants'],
        'slots': [{'name': s['name'], 'lexicon': s['lexicon']} for s in r['slots']],
        'example': {'quote': r['seed_quotes'][0],
            'slots': [{'name': s['name'], 'quote': s['quote']} for s in r['slots']]}}
        for r in rules]


def binding_schema(frames):
    return record_schema({'records': {'type': 'array', 'maxItems': 12,
        'items': record_schema({'frame_id': {'type': 'string', 'enum': [f['id'] for f in frames]},
            'quote': {'type': 'string', 'minLength': 1, 'maxLength': 1800},
            'slots': {'type': 'array', 'maxItems': 5, 'items': record_schema({
                'name': {'type': 'string'}, 'quote': {'type': 'string', 'minLength': 1, 'maxLength': 1500}})}})}})


def bind_records(spec, frames, text, response):
    jsonschema.validate(response, binding_schema(frames))
    indexed = {f['id']: f for f in frames};lexicons = {x['name']: x for x in spec['lexicons']}
    glue = {x.lower() for x in spec['glue_words']};records, rejected = [], []
    for index, item in enumerate(response['records']):
        try:
            frame = indexed[item['frame_id']]
            slots = {x['name']: x for x in frame['slots']}
            names = [s['name'] for s in item['slots']]
            if len(names) != len(set(names)) or set(names) != set(slots):
                raise ValueError('All and only acquired frame slots must be explicitly bound')
            a, b = locate(text, item['quote']);quote = text[a:b]
            aligned = align_slots(quote, item['slots'])
            values = dict(frame['constants']);surface, lexical = {}, {}
            for start, end, slot in aligned:
                name = slot['name'];raw = quote[start:end];surface[name] = raw
                lexicon = slots[name]['lexicon']
                if lexicon is None:values[name] = raw
                else:
                    lex = recognize_terms(raw, lexicons[lexicon], glue)
                    lexical[name] = lex
                    values[name] = lex['symbols'] if lex['symbols'] and not lex['ambiguous'] else None
            record = {'kind': frame['kind'], 'values': values, 'surface': surface,
                'lexical': lexical, 'span': [a, b], 'production': frame['id'],
                'binding': digest(item), 'relation_semantics_verified': False}
            if record not in records:records.append(record)
        except ValueError as error:
            rejected.append({'record_index': index, 'error': str(error), 'raw_record': item})
    return sorted(records, key=lambda r: (r['span'], r['production'])), rejected


def read_records(reads, source, spec, frames):
    text = source['views'][0]['public']['source_text']
    if any(v['public']['source_text'] != text for v in source['views']):
        raise ValueError('Bind the actual material for each task; do not share different contexts')
    response, event = reads.generate(source, source['views'][0],
        system='Instantiate the acquired relation frames in the COMPLETE CURRENT source. The old example is a demonstration of a legal relation, not a literal wording pattern and not current evidence. Recognize equivalent legal meaning despite new wording, while preserving every frame constant, actor/recipient direction, action, restriction and exception scope. Return current source clauses and exact nonoverlapping slot quotes within each clause. Do not copy old facts, infer roles from unrelated mentions, or treat an information definition, no-contact duty or copy restriction as a disclosure authorization. A frame applies only when the current operative clause supports its legal relation and constants. A recipient definition may instantiate a separate group-link frame when its actual relationship is supported. Include the clause qualifications; quote a coherent current clause, not a whole agreement or a misleading fragment. Bind all and only the selected frame slots. Do not output native task labels. If no acquired frame fits, return records=[]; absence of a record is unresolved.',
        content={'current_source_text': text, 'acquired_frames': frames,
            'acquired_lexicons': spec['lexicons'], 'glue_words': spec['glue_words'],
            'instruction': 'Return all current clauses matching these acquired relations, without answering a downstream hypothesis.'},
        schema=binding_schema(frames), purpose='skill_replay')
    records, rejected = bind_records(spec, frames, text, response)
    return records, {**event, 'kind': 'READ_CURRENT_RELATION_BINDINGS',
        'bindings': response, 'rejected_bindings': rejected,
        'legal_relation_recognition_remains_fallible': True}


def joint_control(reads, source, spec, frames, tasks):
    """Same acquired information; full-source direct execution remains free."""
    schema = record_schema({v['id']: record_schema({'answer': {
        'type': ['string', 'null'], 'enum': [None, 'Entailment', 'Contradiction', 'NotMentioned']},
        'source_quotes': {'type': 'array', 'maxItems': 12, 'items': {'type': 'string'}}})
        for v in source['views'] if v['id'] in tasks})
    response, event = reads.generate(source, source['views'][0],
        system='Apply the acquired reusable legal skill to the complete current source and the supplied hypotheses. You may reason directly over the full source, interpret the acquired Python procedure, use the acquired relation examples, or combine these freely. The examples illustrate meanings; do not require literal wording equality or import their old facts. Preserve actor/recipient direction, operative versus descriptive scope, qualifications and exception relationships. Cite actual current source quotes supporting your answer. Definitions or unrelated actions do not by themselves establish a disclosure permission. Do not force an acquired frame that does not fit. A missing parse is not evidence of a legal absence. Use null if unresolved.',
        content={'current_source_text': source['views'][0]['public']['source_text'],
            'acquired_frames': frames, 'acquired_lexicons': spec['lexicons'],
            'glue_words': spec['glue_words'], 'acquired_procedure': spec['procedure'],
            'tasks': {v['id']: v['public']['question'] for v in source['views'] if v['id'] in tasks}},
        schema=schema, purpose='skill_actor')
    return response, {**event, 'kind': 'SAME_INFORMATION_JOINT_CONTROL', 'result': response}
