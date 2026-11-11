"""Evidence-backed, executable multi-location edits, with a strong generic arm."""
import ast
from copy import deepcopy
from dataclasses import asdict, replace
import difflib

from .objects import digest
from .revisions import rank_patterns, observe_transfer


def instantiate_edit(before, after, target):
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
            prior = names.setdefault(a.id, b.id)
            return prior == b.id
        if isinstance(a, ast.Constant):
            key = (type(a.value).__name__, repr(a.value))
            if type(a.value) is not type(b.value):return False
            prior = constants.setdefault(key, b.value)
            return prior == b.value
        if isinstance(a, ast.AST):
            return all(match(getattr(a, k), getattr(b, k)) for k in a._fields)
        if isinstance(a, list):
            return len(a) == len(b) and all(match(x, y) for x, y in zip(a, b))
        return a == b

    if not match(old, current):
        return None

    class Transplant(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in names:return ast.copy_location(ast.Name(id=names[node.id], ctx=node.ctx), node)
            return node

        def visit_Constant(self, node):
            key = (type(node.value).__name__, repr(node.value))
            if key in constants:return ast.copy_location(ast.Constant(value=constants[key]), node)
            if node.value not in (None, True, False, 0, 1, 'answer'):
                raise ValueError('Edit requires an unbound new source literal')
            return node

    try:
        return ast.unparse(ast.fix_missing_locations(Transplant().visit(new))) + '\n'
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


def learn(library, old_library, revisions, table, selected_mask, *, generic=False):
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
        context = relation_context(old_p, old_c, field)
        if not generic and any(v == 'unknown' for v in context.values()):
            continue
        edits = []
        for identity, target in ((producer, 'producer'), (consumer, 'consumer')):
            old, new = old_library.skills[identity], library.skills[identity]
            if old.procedure == new.procedure:
                continue
            edits.append({'target': target, 'before': old.procedure, 'after': new.procedure,
                'old_role': role(old, field if target == 'producer' else 'answer'),
                'new_role': role(new, field if target == 'producer' else 'answer'),
                'diff': ''.join(difflib.unified_diff(old.procedure.splitlines(True), new.procedure.splitlines(True)))})
        if len(edits) != 2:
            continue
        key = digest({'context': context, 'edits': edits, 'generic': generic})
        pattern = {'id': key, 'kind': 'generic_multi_edit' if generic else 'legal_corevision',
            'verified_relation_fields': context if not generic else {
                'producer_port_type': context['producer_port_type'], 'consumer_uses_actual_producer_output': True},
            'relation_evidence_kind': 'source_anchored_role_declarations_and_actual_USE; not_independent_role_gold',
            'edits': edits, 'counts_by_context': {}, 'observed_read_tokens': 0,
            'training_sources': list(table.trigger + table.history),
            'exact_version_table': table.export(), 'actual_source_field': field,
            'new_responsibility': role(library.skills[producer], field)}
        if any(p['id'] == key for p in library.revision_patterns):
            continue
        observe_transfer(pattern, context, table)
        library.revision_patterns.append(pattern)
        created.append(key)
    return created


def candidates(library, current_traces, *, generic=False):
    """Instantiate edits before teacher generation; replay still decides admission."""
    found = []
    for producer, field, consumer in actual_links(current_traces):
        if producer not in library.skills or consumer not in library.skills:
            continue
        p, c = library.skills[producer], library.skills[consumer]
        if field not in p.outputs:continue
        context = relation_context(p, c, field)
        patterns = [x for x in library.revision_patterns
                    if x['kind'] == ('generic_multi_edit' if generic else 'legal_corevision')]
        ordered = (sorted((x['id'] for x in patterns)) if generic else rank_patterns(patterns, context))
        for identity in ordered:
            pattern = next(x for x in patterns if x['id'] == identity)
            revisions = []
            for edit in pattern['edits']:
                old = p if edit['target'] == 'producer' else c
                program = instantiate_edit(edit['before'], edit['after'], old.procedure)
                if program is None:break
                obligations = deepcopy(old.source_obligations)
                for obligation in obligations:
                    if obligation['port'] == (field if edit['target'] == 'producer' else 'answer'):
                        obligation['role'] = edit['new_role']
                try:
                    new = replace(old, procedure=program, source_obligations=obligations,
                                  version=old.version + 1).validate()
                except ValueError:break
                revisions.append({'skill_id': old.id, 'old_hash': old.hash, 'new_hash': new.hash,
                                  'new': asdict(new), 'operation': 'learned_pattern'})
            if len(revisions) == 2:
                found.append({'revisions': revisions, 'pattern_id': identity,
                    'verified_context': context, 'current_bindings': {'producer': producer,
                        'field': field, 'consumer': consumer}, 'generated_before_teacher': True})
    # Fixed lexical ordering after the method-specific pattern ranking.
    seen = set()
    return [x for x in found if not (digest(x['revisions']) in seen or seen.add(digest(x['revisions'])))]
