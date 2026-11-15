"""Learned semantic source records and independently acquired free policies.

Effect separation is the candidate inductive bias. Extraction, execution,
unknown handling, native scoring and the model transport are shared tools.
"""
import ast

import jsonschema

from .native import record_schema, source_spans
from .objects import Skill, digest, premise_uses
from .runtime import execute_helper

LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
TASKS = ('nda-5', 'nda-7')
FIELD_SCHEMA = record_schema({'name': {'type': 'string'},
    'type': {'type': 'string', 'enum': ['boolean', 'integer', 'number', 'string', 'array', 'raw_text', 'raw_spans']},
    'question': {'type': 'string'}, 'domain': {'type': 'array', 'items': {'type': 'string'}}})
SCHEMA = record_schema({'kind': {'type': 'string', 'enum': ['typed_rule', 'raw_rule', 'text_policy']},
    'rationale': {'type': 'string'}, 'scope_tasks': {'type': 'array', 'items': {'type': 'string', 'enum': list(TASKS)}},
    'read_question': {'type': ['string', 'null']},
    'source_fields': {'type': 'array', 'maxItems': 8, 'items': FIELD_SCHEMA},
    'procedure': {'type': ['string', 'null']}, 'policy_text': {'type': ['string', 'null']}})


def source_material(source):
    public = source['views'][0]['public']
    if any(v['public']['source_text'] != public['source_text'] for v in source['views']):
        raise ValueError('This acquisition is per identical current source material')
    return source_spans({'source_text': public['source_text'], 'sentence_spans': public['sentence_spans']})


def compile_schema(value, *, restricted):
    jsonschema.validate(value, SCHEMA)
    if set(value['scope_tasks']) != set(TASKS) or len(value['scope_tasks']) != len(TASKS):
        raise ValueError('Both fixed native public tasks must remain in scope')
    if restricted and value['kind'] != 'typed_rule':
        raise ValueError('The candidate learns a typed semantic source schema')
    if value['kind'] == 'text_policy':
        if not value['policy_text'] or value['source_fields'] or value['procedure'] is not None:
            raise ValueError('One learned text policy, without hidden program/fields')
        return value
    if not value['procedure'] or value['policy_text'] is not None or not value['read_question']:
        raise ValueError('Explicit reading instruction and complete program required')
    fields = {f['name']: f for f in value['source_fields']}
    if len(fields) != len(value['source_fields']):raise ValueError('Duplicate source field')
    if not fields:raise ValueError('A source-grounded rule needs an actually used source field')
    for f in fields.values():
        if not f['name'].isidentifier():raise ValueError('Source field name must be a Python identifier')
        if len(set(f['domain'])) != len(f['domain']) or any(not x for x in f['domain']):
            raise ValueError('Canonical categories must be distinct and nonempty')
        if set(f['domain']) & set(LABELS):raise ValueError('Source fields cannot encode the native label domain')
        if restricted and any(not x.isidentifier() or len(x) > 64 for x in f['domain']):
            raise ValueError('Semantic categories are named concepts, not quoted source sentences')
        if restricted and f['type'] in ('raw_text', 'raw_spans'):
            raise ValueError('Raw source text cannot flow into this candidate rule program')
        if restricted and f['type'] in ('string', 'array') and not f['domain']:
            raise ValueError('A semantic string/list field requires its learned finite vocabulary')
        if f['type'] not in ('raw_text', 'raw_spans') and not f['question'].strip():
            raise ValueError('Every semantic field needs a source-local meaning')
    if set(premise_uses(value['procedure'])) != set(fields):
        raise ValueError('All and only declared source fields must be used')
    make_skill(value).validate()
    if restricted:
        # No raw values can reach the program. Source-dependent string tests
        # must use the vocabulary learned for the semantic source interface.
        tree = ast.parse(value['procedure'])
        taints = {}
        def dependencies(node):
            found = set()
            for n in ast.walk(node):
                if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                        and n.value.id == 'premises' and isinstance(n.slice, ast.Constant)):
                    found.add(n.slice.value)
                if isinstance(n, ast.Name):found.update(taints.get(n.id, ()))
            return found
        for _ in range(len(list(ast.walk(tree))) + 1):
            previous = {k: set(v) for k, v in taints.items()}
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign):
                    for target in n.targets:
                        if isinstance(target, ast.Name):taints.setdefault(target.id, set()).update(dependencies(n.value))
                if isinstance(n, ast.For) and isinstance(n.target, ast.Name):
                    taints.setdefault(n.target.id, set()).update(dependencies(n.iter))
            if previous == taints:break
        for n in ast.walk(tree):
            if not isinstance(n, ast.Compare):continue
            used = dependencies(n)
            if not used:continue
            vocabulary = set().union(*(set(fields[f]['domain']) for f in used))
            for token in (x.value for x in ast.walk(n) if isinstance(x, ast.Constant) and isinstance(x.value, str)):
                if token in fields:continue  # Literal premise indexing, not a compared source phrase.
                if token not in vocabulary:raise ValueError('Undeclared source-dependent phrase: ' + token)
    return value


def partial_conflicts(observations):
    """A successful read-only partial program is invariant under completion.

    Compatible partial records with different targets cannot both be answered
    correctly by such a program. The witness concerns observed inputs, not
    semantic gold: it permits reader repair as well as predicate invention.
    """
    witnesses = []
    for i, a in enumerate(observations):
        for b in observations[i + 1:]:
            if a['query'] != b['query'] or a['target'] == b['target']:continue
            if set(a['declared_fields']) != set(b['declared_fields']):continue
            shared = set(a['known']) & set(b['known'])
            if any(digest(a['known'][n]) != digest(b['known'][n]) for n in shared):continue
            witnesses.append({'left': a['source'], 'right': b['source'], 'query': a['query'],
                'left_target': a['target'], 'right_target': b['target'],
                'shared_known': {n: a['known'][n] for n in sorted(shared)},
                'left_unresolved': sorted(set(a['declared_fields']) - set(a['known'])),
                'right_unresolved': sorted(set(b['declared_fields']) - set(b['known'])),
                'common_completion': {**a['known'], **b['known']},
                'completion_is_a_logical_witness_not_acquired_source_values': True,
                'procedure_only_can_resolve_both_under_current_observations': False,
                'allowed_remedies': ['repair_reader', 'learn_additional_source_predicate'],
                'true_source_semantic_insufficiency_not_inferred': True})
    return witnesses


def make_skill(value):
    fields = {f['name']: f for f in value['source_fields']}
    def kind(f):return {'raw_text': 'string', 'raw_spans': 'array'}.get(f['type'], f['type'])
    return Skill(id='acquired_rule_' + digest(value)[:16], intent=value['rationale'], procedure=value['procedure'],
        inputs={n: {'mode': 'argument', 'type': 'string', 'field': n, 'question': '', 'skill_id': None, 'arguments': {}}
                for n in ('task_id', 'question')},
        outputs={'answer': {'type': 'string', 'public_tasks': value['scope_tasks'], 'query_clauses': []}},
        premises={n: {'mode': 'read', 'type': kind(f), 'read_id': 'source_schema', 'field': n}
                  for n, f in fields.items()},
        reads=({'id': 'source_schema', 'fields': {n: {'type': kind(f), 'question': f['question']}
            for n, f in fields.items()}},), semantic_records=(), source_obligations=(), source_provenance=())


def read_semantic_record(reads, source, spec):
    spans = source_material(source)
    fields = {f['name']: f for f in spec['source_fields']}
    values, schemas, raw = {}, {}, {}
    for name, f in fields.items():
        if f['type'] == 'raw_text':
            values[name] = source['views'][0]['public']['source_text'];raw[name] = 'complete original source_text';continue
        if f['type'] == 'raw_spans':
            values[name] = [s['text'] for s in spans];raw[name] = 'all exact original source spans';continue
        wire = {'type': [f['type'], 'null']}
        if f['type'] == 'string' and f['domain']:wire['enum'] = [None, *f['domain']]
        if f['type'] == 'array':
            wire['items'] = {'type': 'string'}
            if f['domain']:wire.update(items={'type': 'string', 'enum': f['domain']}, uniqueItems=True, maxItems=len(f['domain']))
        schemas[name] = record_schema({'status': {'type': 'string', 'enum': ['known', 'unknown']},
            'value': wire, 'support_ids': {'type': 'array', 'maxItems': len(spans),
                'items': {'type': 'integer', 'minimum': 0, 'maximum': len(spans) - 1}}})
    if not schemas:return values, {'kind': 'BIND_RAW_RULE_SOURCE', 'raw_bindings': raw, 'new_model_calls': 0}
    returned, event = reads.generate(source, source['views'][0],
        system='Read the learned semantic source fields from the complete current rule material. Preserve roles, direction, clause scope and qualifications. Do not give any native hypothesis label or import old-source values. Use unknown with value null when the requested parameter cannot be established; extraction uncertainty is not False, an empty list or absence. Known fields require current-source supporting span IDs. The declared canonical vocabulary describes meanings, not words that must literally occur. Keep actor/recipient classes separate from protected information, conditions and examples.',
        content={'source_spans': [{k: v for k, v in s.items() if k != 'public_sentence_id'} for s in spans],
            'read_question': spec['read_question'], 'fields': {n: f for n, f in fields.items() if n in schemas}},
        schema=record_schema(schemas), purpose='skill_replay')
    event = {**event, 'kind': 'READ_SEMANTIC_SOURCE', 'fields': returned, 'raw_bindings': raw}
    for name, field in returned.items():
        if field['status'] == 'unknown' and field['value'] is None:continue
        if field['status'] != 'known' or field['value'] is None or not field['support_ids']:
            raise ValueError('Inconsistent status/value or unsupported source parameter: ' + name)
        values[name] = field['value']
    event['unresolved_fields'] = sorted(set(schemas) - set(values))
    return values, event


def execute_schema(spec, source, view, values):
    skill = make_skill(spec)
    output = execute_helper(skill, {'task_id': view['id'], 'question': view['public']['question']}, values,
        unresolved_premises=set(skill.premises) - set(values))
    if output['answer'] not in LABELS:raise ValueError('Learned program returned an invalid native label')
    return output['answer']


def execute_text_policy(reads, source, spec):
    spans = source_material(source)
    properties = {v['id']: record_schema({'answer': {'type': ['string', 'null'], 'enum': [None, *LABELS]},
        'support_ids': {'type': 'array', 'maxItems': len(spans), 'uniqueItems': True,
            'items': {'type': 'integer', 'minimum': 0, 'maximum': len(spans) - 1}}})
        for v in source['views'] if v['id'] in spec['scope_tasks']}
    return reads.generate(source, source['views'][0], system='Apply the acquired reusable legal procedure to the current material and supplied hypotheses. Respect role, scope and conditions; do not import training-source facts. Use a null answer if unresolved. Cite current source span IDs where relevant.',
        content={'learned_policy': spec['policy_text'], 'source_spans': [{k: v for k, v in s.items() if k != 'public_sentence_id'} for s in spans],
            'tasks': {v['id']: v['public']['question'] for v in source['views'] if v['id'] in spec['scope_tasks']}},
        schema=record_schema(properties), purpose='skill_actor')
