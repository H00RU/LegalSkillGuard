"""Evidence-backed, executable multi-location edits, with a strong generic arm."""
import ast
from copy import deepcopy
from dataclasses import asdict, replace
import difflib

from .objects import Skill, digest, dependency_arguments
from .revisions import rank_patterns, observe_transfer
from .responsibilities import context as responsibility_context, improved_invocations, invocations, read_cost


def instantiate_edit(before, after, target, *, declared_ports=None, allow_query_predicates=False):
    """Alpha-match old code and transplant its measured edit, without new law.

    Source literals present in the old helper must bind consistently to the
    current helper. New source-specific constants/ports are not guessed.
    """
    old, new, current = map(ast.parse, (before, after, target))
    names, constants = {}, {}

    def match(a, b):
        if type(a) is not type(b):
            return False
        if isinstance(a, ast.Name):
            if a.id in ('inputs', 'premises'):return a.id == b.id
            prior = names.setdefault(a.id, b.id)
            return prior == b.id
        if isinstance(a, ast.Constant):
            key = (type(a.value).__name__, repr(a.value))
            if type(a.value) is not type(b.value):return False
            prior = constants.setdefault(key, b.value)
            return prior == b.value
        if isinstance(a, ast.AST):
            if (isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                    and isinstance(b.func, ast.Name) and a.func.id != b.func.id):
                return False  # min/max and other primitives are operations, not local variables.
            return all(match(getattr(a, k), getattr(b, k)) for k in a._fields)
        if isinstance(a, list):
            return len(a) == len(b) and all(match(x, y) for x, y in zip(a, b))
        return a == b

    if not match(old, current):
        return None

    new_locals = {n.id for n in ast.walk(new) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} - set(names)
    occupied = set(names.values()) | new_locals | {'inputs', 'premises'}
    for local in sorted(new_locals & set(names.values())):
        index = 0
        while '_edit_local_' + str(index) in occupied:index += 1
        replacement = '_edit_local_' + str(index)
        names[local] = replacement;occupied.add(replacement)

    parents = {id(child): node for node in ast.walk(new) for child in ast.iter_child_nodes(node)}
    stores = {}
    for node in ast.walk(new):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    query_names = set()
    for node in ast.walk(new):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and stores[node.targets[0].id] == 1
                and isinstance(node.value, ast.Subscript)
                and isinstance(node.value.value, ast.Name) and node.value.value.id == 'inputs'
                and isinstance(node.value.slice, ast.Constant) and node.value.slice.value == 'current_question'):
            query_names.add(node.targets[0].id)

    def declared_literal(node):
        parent = parents.get(id(node))
        if (isinstance(parent, ast.Subscript) and parent.slice is node
                and isinstance(parent.value, ast.Name)
                and node.value in (declared_ports or {}).get(parent.value.id, ())):
            return True  # The complete template supplies its type and binding.
        return (allow_query_predicates and isinstance(parent, ast.Compare)
                and parent.left is node and len(parent.ops) == 1
                and isinstance(parent.ops[0], (ast.In, ast.NotIn))
                and isinstance(parent.comparators[0], ast.Name)
                and parent.comparators[0].id in query_names)

    class Transplant(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in names:return ast.copy_location(ast.Name(id=names[node.id], ctx=node.ctx), node)
            return node

        def visit_Constant(self, node):
            key = (type(node.value).__name__, repr(node.value))
            if key in constants:return ast.copy_location(ast.Constant(value=constants[key]), node)
            if node.value not in (None, True, False, 0, 1, 'answer') and not declared_literal(node):
                raise ValueError('Edit requires an unbound new source literal')
            return node

    try:
        return ast.unparse(ast.fix_missing_locations(Transplant().visit(new))) + '\n'
    except ValueError:
        return None


def instantiate_skill_edit(before, after, target, *, skill_ids=None):
    """Transplant measured code plus its explicit acquisition bindings.

    New law values are never filled from a witness. Unchanged constant ports
    retain the target's actual value/provenance; changed/new ports must READ.
    Unsupported interface or source-constant edits remain uninstantiable.
    """
    before.validate();after.validate();target.validate()
    for attribute in ('inputs', 'outputs', 'premises'):
        old_ports, current_ports = getattr(before, attribute), getattr(target, attribute)
        if set(old_ports) != set(current_ports):return None
        for name in old_ports:
            if old_ports[name]['type'] != current_ports[name]['type']:return None
            if attribute != 'outputs' and old_ports[name]['mode'] != current_ports[name]['mode']:return None
    if set(before.inputs) != set(after.inputs) or set(before.outputs) != set(after.outputs):return None
    if any(before.inputs[n]['type'] != after.inputs[n]['type'] or
           before.inputs[n]['mode'] != after.inputs[n]['mode'] for n in before.inputs):return None
    if any(before.outputs[n]['type'] != after.outputs[n]['type'] for n in before.outputs):return None
    for name in before.outputs:
        if any(before.outputs[name].get(k) != target.outputs[name].get(k)
               for k in ('public_tasks', 'query_clauses')):
            return None  # A different applicability identity needs an explicit binding.
    premises = {}
    readers = {r['id']: r for r in after.reads}
    for name, port in after.premises.items():
        previous = before.premises.get(name)
        if port['mode'] == 'constant':
            if (not previous or previous['mode'] != 'constant' or port['type'] != previous['type']
                    or port['value'] != previous['value']):
                return None
            premises[name] = deepcopy(target.premises[name])
        else:
            reader = readers[port['read_id']]
            if (reader.get('bindings', {}).get(name) != port['field']
                    or reader.get('fields', {}).get(port['field'], {}).get('type') != port['type']):
                return None
            premises[name] = deepcopy(port)
    query = after.inputs.get('current_question', {})
    program = instantiate_edit(before.procedure, after.procedure, target.procedure,
        declared_ports={'inputs': set(after.inputs), 'premises': set(after.premises)},
        allow_query_predicates=query.get('type') == 'string' and query.get('mode') == 'argument')
    if program is None:return None
    identifiers = {before.id: target.id, **(skill_ids or {})}
    inputs = deepcopy(after.inputs)
    for name, port in inputs.items():
        if port['mode'] == 'skill':
            expected = identifiers.get(port['skill_id'])
            if expected is None:return None
            if expected != target.inputs[name].get('skill_id'):return None
            port['skill_id'] = expected
    provenance = {digest(o): deepcopy(o) for o in (*target.source_provenance, *after.source_provenance)}
    try:
        return replace(after, id=target.id, procedure=program, inputs=inputs, premises=premises,
            source_provenance=tuple(provenance.values()), version=target.version + 1).validate()
    except ValueError:
        return None


def role(skill, port):
    declared = [o for o in skill.source_obligations if o.get('port') == port
                and o.get('origin', {}).get('quote')]
    values = {o['role'] for o in declared if o['role'] != 'unknown'}
    return next(iter(values)) if len(values) == 1 else 'unknown'


def relation_context(producer, consumer, field):
    return {'declared_producer_role': role(producer, field),
        'declared_consumer_answer_role': role(consumer, 'answer'),
        'producer_port_type': producer.outputs[field]['type'],
        'consumer_uses_actual_producer_output': True}


def actual_links(traces):
    seen = set()
    for trace in traces:
        for result in trace.get('views', []):
            for event in result.get('execution', {}).get('events', []):
                if event.get('kind') == 'USE':
                    key = event['producer'], event['field'], event['consumer']
                    if key not in seen:
                        seen.add(key)
                        yield key


def compatible_dependency_versions(old_p, new_p, old_c, new_c, field):
    """Interface breakage cannot establish semantic joint-repair necessity."""
    for consumer in (old_c, new_c):
        ports = [p for p in consumer.inputs.values() if p['mode'] == 'skill'
                 and p['skill_id'] == old_p.id]
        if not any(p['field'] == field for p in ports):
            return False
        for producer in (old_p, new_p):
            for port in ports:
                try:
                    dependency_arguments(consumer, port, {producer.id: producer})
                except (KeyError, ValueError):
                    return False
    return True


def learn(library, old_library, revisions, table, selected_mask, *, generic=False, source_records=None):
    """Compile actual accepted edits; joint necessity stays local to its table."""
    if not table.complete or selected_mask is None:
        return []
    chosen = {r['skill_id']: r for i, r in enumerate(revisions) if selected_mask & (1 << i)}
    if len(chosen) != 2:
        return []
    classification = table.classify()
    if not generic and classification != 'joint_needed':
        return []
    created = []
    for producer, field, consumer in actual_links(list(table.traces.values())):
        if producer not in chosen or consumer not in chosen:
            continue
        if producer not in old_library.skills or consumer not in old_library.skills:
            continue  # Creating two helpers is not an old-skill co-revision.
        old_p, old_c = old_library.skills[producer], old_library.skills[consumer]
        if field not in old_p.outputs:
            continue
        if not compatible_dependency_versions(old_p, library.skills[producer],
                old_c, library.skills[consumer], field):
            continue
        edits = []
        for identity, target in ((producer, 'producer'), (consumer, 'consumer')):
            old, new = old_library.skills[identity], library.skills[identity]
            if all(getattr(old, a) == getattr(new, a) for a in
                   ('procedure', 'inputs', 'outputs', 'premises', 'reads')):
                continue
            edits.append({'target': target, 'before': old.procedure, 'after': new.procedure,
                'before_skill': asdict(old), 'after_skill': asdict(new),
                'old_role': role(old, field if target == 'producer' else 'answer'),
                'new_role': role(new, field if target == 'producer' else 'answer'),
                'diff': ''.join(difflib.unified_diff(old.procedure.splitlines(True), new.procedure.splitlines(True)))})
        if len(edits) != 2:
            continue
        for unit in improved_invocations(table, selected_mask, producer, field, consumer):
            observed = responsibility_context(old_p, old_c, library.skills[producer],
                library.skills[consumer], field, unit, (source_records or {}).get(unit['source']))
            context = observed['fields']
            if not context:continue
            key = digest({'context': context, 'edits': edits, 'generic': generic})
            if any(p['id'] == key for p in library.revision_patterns):continue
            pattern = {'id': key, 'kind': 'generic_multi_edit' if generic else 'legal_corevision',
                'verified_relation_fields': context if not generic else {
                    'producer_port_type': context['producer_port_type'], 'consumer_uses_actual_producer_output': True},
                'relation_evidence_kind': 'finite_code_probes_and_literal_source_bindings; not_independent_legal_gold',
                'responsibility_evidence': observed['evidence'],
                'unknown_relation_fields': observed['unknown'],
                'declared_roles_for_interpretation_only': relation_context(old_p, old_c, field),
                'edits': edits, 'counts_by_context': {},
                'read_cost': {'before': read_cost(table, 0), 'after': read_cost(table, selected_mask)},
                'training_sources': list(table.trigger + table.history),
                'exact_version_table': table.export(), 'actual_source_field': field}
            pattern['observed_read_tokens'] = pattern['read_cost']['after']['traced_tokens']
            observe_transfer(pattern, context, table)
            library.revision_patterns.append(pattern)
            created.append(key)
    return created


def candidates(library, current_traces, *, generic=False, source_records=None):
    """Instantiate edits before teacher generation; replay still decides admission."""
    found = []
    for producer, field, consumer in actual_links(current_traces):
        if producer not in library.skills or consumer not in library.skills:
            continue
        p, c = library.skills[producer], library.skills[consumer]
        if field not in p.outputs:continue
        patterns = [x for x in library.revision_patterns
                    if x['kind'] == ('generic_multi_edit' if generic else 'legal_corevision')]
        units = [unit for trace in current_traces for unit in invocations(trace, producer, field, consumer)
                 if unit['score']['grade'] is None or unit['score']['grade'] < 1]
        for pattern in sorted(patterns, key=lambda x: x['id']):
            revisions = []
            skill_ids = {e['before_skill']['id']: p.id if e['target'] == 'producer' else c.id
                         for e in pattern['edits']}
            for edit in pattern['edits']:
                old = p if edit['target'] == 'producer' else c
                new = instantiate_skill_edit(Skill.from_dict(edit['before_skill']),
                    Skill.from_dict(edit['after_skill']), old, skill_ids=skill_ids)
                if new is None:break
                revisions.append({'skill_id': old.id, 'old_hash': old.hash, 'new_hash': new.hash,
                                  'new': asdict(new), 'operation': 'learned_pattern'})
            if len(revisions) == 2:
                after = {r['skill_id']: Skill.from_dict(r['new']) for r in revisions}
                for unit in units:
                    observed = responsibility_context(p, c, after[producer], after[consumer], field,
                        unit, (source_records or {}).get(unit['source']))
                    context = observed['fields']
                    if not context:continue
                    if not generic and not rank_patterns([pattern], context):continue
                    counts = pattern['counts_by_context'].get(digest(context),
                        {'joint_needed': 0, 'single_sufficient': 0, 'harmful_or_unresolved': 0})
                    rank = (len(pattern['verified_relation_fields']),
                        (counts['joint_needed'] + 1) / (sum(counts.values()) + 3),
                        -pattern['observed_read_tokens'] if pattern['read_cost']['after']['complete'] else -float('inf'), pattern['id'])
                    found.append({'revisions': revisions, 'pattern_id': pattern['id'],
                        'verified_context': context, 'responsibility_evidence': observed['evidence'],
                        'unknown_relation_fields': observed['unknown'],
                        'current_bindings': {'producer': producer, 'field': field, 'consumer': consumer},
                        'generated_before_teacher': True, '_rank': rank})
                    break
    found.sort(key=(lambda x: x['pattern_id']) if generic else (lambda x: x['_rank']), reverse=not generic)
    for value in found:value.pop('_rank')
    seen = set()
    return [x for x in found if not (digest(x['revisions']) in seen or seen.add(digest(x['revisions'])))]
