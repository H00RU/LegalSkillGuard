"""Acquire source-neutral relation schemas, source-bound instances and code.

All legal concepts, binding meanings and consequence rules are acquired.
The host checks types/provenance/unknown handling, not missing legal semantics.
"""
import ast
import jsonschema

from .native import record_schema, source_spans
from .source_schema import LABELS, TASKS
from .span_compiler import validate_procedure, execute


FIELD = record_schema({'name': {'type': 'string'}, 'meaning': {'type': 'string'},
    'type': {'type': 'string', 'enum': ['string', 'array']},
    'domain': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'items': {'type': 'string'}}})
FRAME = record_schema({'name': {'type': 'string'}, 'meaning': {'type': 'string'},
    'fields': {'type': 'array', 'minItems': 1, 'maxItems': 7, 'items': FIELD}})
EXAMPLE = record_schema({'source': {'type': 'string'}, 'quote': {'type': 'string'}})
SCHEMA = record_schema({'kind': {'type': 'string', 'enum': ['relational_rule', 'program', 'text_policy']},
    'rationale': {'type': 'string'}, 'frames': {'type': 'array', 'maxItems': 4, 'items': FRAME},
    'source_examples': {'type': 'array', 'maxItems': 8, 'items': EXAMPLE},
    'procedure': {'type': ['string', 'null']}, 'policy_text': {'type': ['string', 'null']}})


def compile_skill(spec, materials, restricted=False, *, allow_helpers=False):
    from .span_compiler import locate
    jsonschema.validate(spec, SCHEMA)
    if restricted and spec['kind'] != 'relational_rule':raise ValueError('Acquire a source-neutral relational skill')
    for example in spec['source_examples']:
        if example['source'] not in materials:raise ValueError('Non-TRAIN acquisition example')
        locate(materials[example['source']], example['quote'])
    if spec['kind'] == 'text_policy':
        if not spec['policy_text'] or spec['procedure'] is not None or spec['frames']:raise ValueError('One text policy')
        return spec
    validate_procedure(spec['procedure'], allow_helpers=allow_helpers)
    if spec['policy_text'] is not None:raise ValueError('No alternate hidden policy')
    if spec['kind'] == 'program':
        if spec['frames']:raise ValueError('Raw programs receive source_text directly')
        return spec
    if not spec['frames']:raise ValueError('At least one acquired relation frame')
    names = [f['name'] for f in spec['frames']]
    if len(set(names)) != len(names) or any(not n.isidentifier() for n in names):raise ValueError('Unique relation identifiers')
    for frame in spec['frames']:
        names = [f['name'] for f in frame['fields']]
        if len(set(names)) != len(names) or any(not n.isidentifier() for n in names):raise ValueError('Unique field identifiers')
        for f in frame['fields']:
            if len(set(f['domain'])) != len(f['domain']) or any(not s.isidentifier() or s in LABELS for s in f['domain']):
                raise ValueError('Finite semantic concepts, not source quotes or native labels')
    declared={f['name'] for frame in spec['frames'] for f in frame['fields']}
    tree=ast.parse(spec['procedure']);aliases=set()
    def source_values_expression(value):
        return (isinstance(value,ast.Subscript) and isinstance(value.slice,ast.Constant) and value.slice.value=='values') or (
            isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute) and value.func.attr=='get'
            and value.args and isinstance(value.args[0],ast.Constant) and value.args[0].value=='values')
    for _ in range(len(list(ast.walk(tree)))+1):
        previous=set(aliases)
        for node in ast.walk(tree):
            if not isinstance(node,ast.Assign):continue
            value=node.value
            source_values=source_values_expression(value)
            if source_values or (isinstance(value,ast.Name) and value.id in aliases):
                aliases.update(t.id for t in node.targets if isinstance(t,ast.Name))
        if previous==aliases:break
    for node in ast.walk(tree):
        name=None
        if (isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant)
                and ((isinstance(node.value,ast.Name) and node.value.id in aliases) or source_values_expression(node.value))):name=node.slice.value
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                and ((isinstance(node.func.value,ast.Name) and node.func.value.id in aliases) or source_values_expression(node.func.value))
                and node.func.attr=='get' and node.args and isinstance(node.args[0],ast.Constant)):name=node.args[0].value
        if isinstance(name,str) and name not in declared:raise ValueError('Procedure accesses an undeclared source field: '+name)
    return spec


def spans_for(source):
    text = source['views'][0]['public']['source_text']
    if any(v['public']['source_text'] != text for v in source['views']):raise ValueError('Per-material source reading required')
    return source_spans({'source_text': text, 'sentence_spans': source['views'][0]['public']['sentence_spans']})


def read_schema(spec, spans):
    ids = {'type': 'array', 'maxItems': len(spans), 'uniqueItems': True,
        'items': {'type': 'integer', 'minimum': 0, 'maximum': len(spans)-1}}
    frames = {}
    for frame in spec['frames']:
        fields = {}
        for f in frame['fields']:
            value = ({'type': ['string', 'null'], 'enum': [None, *f['domain']]} if f['type'] == 'string' else
                {'type': ['array', 'null'], 'maxItems': len(f['domain']), 'uniqueItems': True,
                    'items': {'type': 'string', 'enum': f['domain']}})
            fields[f['name']] = record_schema({'value': value, 'support_ids': ids})
        frames[frame['name']] = {'type': 'array', 'maxItems': 12,
            'items': record_schema({'support_ids': ids, 'fields': record_schema(fields)})}
    return record_schema(frames)


def bind_records(spec, spans, returned):
    jsonschema.validate(returned, read_schema(spec, spans));records = []
    for frame in spec['frames']:
        for item in returned[frame['name']]:
            parent = set(item['support_ids'])
            if not parent:raise ValueError('Relation instance has no current-source support')
            values, unresolved, witnesses = {}, [], {}
            for field in frame['fields']:
                name = field['name'];r = item['fields'][name];ids = set(r['support_ids'])
                if not ids <= parent:raise ValueError('A field witness lies outside its relation evidence scope')
                if r['value'] is None:
                    unresolved.append(name)
                else:
                    if not ids:raise ValueError('Known relation field lacks current evidence')
                    values[name] = r['value']
                witnesses[name] = sorted(ids)
            records.append({'kind': frame['name'], 'values': values, 'unresolved_fields': unresolved,
                'support_ids': sorted(parent), 'field_support_ids': witnesses,
                'source_evidence': [spans[i] for i in sorted(parent)],
                'relation_semantics_verified': False})
    return records


def read_records(reads, source, spec):
    spans = spans_for(source)
    response, event = reads.generate(source, source['views'][0],
        system='Read instances of the acquired semantic relation frames from the complete CURRENT legal source. No old source examples are present. Frame meanings and field vocabularies are reusable concepts, not current facts. Each instance describes a coherent legal action and participant scope, with its current source span IDs. Keep the direct recipient and that recipient owner separate from parties mentioned in nested qualifications or other actions. Resolve only source-supported references; do not import omitted permissions, classes or conditions. Field support IDs must be within that instance support IDs. A source span may support multiple semantic claims when it actually states them; this is evidence containment, not disjoint substring capture. Use null for an unresolved field; use [] only for an explicitly established empty set. Return [] for a frame with no supported instance, but do not infer absence or a negative legal conclusion from that. Do not output a native hypothesis label.',
        content={'acquired_relation_frames': spec['frames'],
            'current_source_spans': [{k:v for k,v in s.items() if k!='public_sentence_id'} for s in spans]},
        schema=read_schema(spec, spans), purpose='skill_replay')
    records = bind_records(spec, spans, response)
    return records, {**event, 'kind': 'READ_SOURCE_NEUTRAL_RELATIONS', 'returned': response,
        'source_examples_exposed_at_runtime': False}


def apply(spec, source, view, records, *, allow_helpers=False):
    premises = {'records': records} if spec['kind'] == 'relational_rule' else {'source_text': source['views'][0]['public']['source_text']}
    return execute(spec['procedure'], {'task_id': view['id'], 'question': view['public']['question']}, premises,
        allow_helpers=allow_helpers)


def text_policy(reads, source, spec):
    spans = spans_for(source)
    schema = record_schema({v['id']: record_schema({'answer': {'type':['string','null'], 'enum':[None,*LABELS]},
        'support_ids': {'type':'array','maxItems':len(spans),'uniqueItems':True,
            'items':{'type':'integer','minimum':0,'maximum':len(spans)-1}}}) for v in source['views'] if v['id'] in TASKS})
    return reads.generate(source, source['views'][0],
        system='Apply the independently acquired reusable skill to the current full legal source and native hypotheses. Preserve participants, recipient ownership, action scope, conditions and exceptions. Use null if unresolved and cite current supporting spans. Prior examples are not current facts. Definitions, other actions or another owner do not by themselves prove the requested permission.',
        content={'learned_policy':spec['policy_text'],
            'current_source_spans':[{k:v for k,v in s.items() if k!='public_sentence_id'} for s in spans],
            'tasks':{v['id']:v['public']['question'] for v in source['views'] if v['id'] in TASKS}},
        schema=schema,purpose='skill_actor')
