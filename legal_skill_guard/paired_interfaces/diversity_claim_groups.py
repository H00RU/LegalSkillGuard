"""Share a claim observation only when one public clause binds all its pairs."""

from collections import defaultdict

from legal_skill_guard.paired_interfaces import diversity_source_binding, relational_program
from legal_skill_guard.paired_interfaces.convergence_m1_batch import diversity_unit_reviews
from legal_skill_guard.skill_evolution.objects import digest


def _groups(view):
    by_span = defaultdict(list)
    text = view['read_input']['source_text']
    for request in view['read_input']['unit_requests']:
        unit = request['source_anchor']
        if not unit.startswith('claim_pair_'):
            continue
        clause, = request['source_excerpts']
        start = text.index(clause)
        if text.find(clause, start + 1) != -1:
            raise ValueError('A claim group requires a unique literal clause in the original source')
        by_span[start, start + len(clause), request['entities']['claim_count']].append(request)
    return list(by_span.items())


def _replace_units(expression, aliases):
    if 'constant' in expression:
        return expression
    if 'local' in expression:
        name, port = expression['local']
        return {'local': [aliases.get(name, name), port]}
    for op in ('all', 'any'):
        if op in expression:
            children = [_replace_units(child, aliases) for child in expression[op]]
            return {op: list({digest(child): child for child in children}.values())}
    return {name: _replace_units(child, aliases) for name, child in expression.items()}


class Provider(diversity_source_binding.Provider):
    """Apply equality-constrained sharing equally to fixed and synthesized layouts."""

    def views(self, source):
        view, = super().views(source)
        groups = _groups(view)
        aliases = {}
        shared = {}
        for index, ((start, end, arity), requests) in enumerate(groups):
            name = f'claim_clause_{index}'
            names = [request['source_anchor'] for request in requests]
            pairs = [[request['entities']['plaintiff'], request['entities']['defendant']] for request in requests]
            aliases.update(dict.fromkeys(names, name))
            shared[name] = {'claim_count': arity, 'covered_pairs': pairs, 'original_units': names,
                            'source_span': [start, end]}
        text = view['read_input']['source_text']
        excerpts = {row['source_anchor']: row['source_excerpts'] for row in view['read_input']['unit_requests']}
        for plan in view['plans']:
            original = plan['relational_program']
            units = {key: unit for key, unit in original['units'].items() if key not in aliases}
            for name, binding in shared.items():
                first, *others = (original['units'][key] for key in binding['original_units'])
                if any(unit['asset_sha256'] != first['asset_sha256'] or unit['context'] != first['context']
                       for unit in others):
                    raise ValueError('One claim observation cannot bind different consumers or contexts')
                units[name] = {**first, 'entity_context': {key: binding[key] for key in ('claim_count', 'covered_pairs')}}
            program = relational_program.sealed({
                'units': units,
                'outputs': {key: _replace_units(value, aliases) for key, value in original['outputs'].items()},
                'diagnostics': {key: _replace_units(value, aliases) for key, value in original['diagnostics'].items()},
                'composition_certificate': {
                    **original['composition_certificate'],
                    'before_program_sha256': original['program_sha256'],
                    'shared_clause_bindings': shared,
                    'equivalence_domain': 'equal ordered claim coordinates for pairs bound by the same literal clause',
                },
            })
            plan['relational_program'] = program
            plan['schema'] = relational_program.schema(program)
            plan['system'] = (relational_program.prompt(program) + '\nUse the exact source_excerpts for each unit. '
                              'A claim clause binds the same listed claims to every covered pair. '
                              'Read the amounts or amount relation once for the clause and cite it verbatim. '
                              'Read citizenship for each named pair from its two statements, in the order shown.')
            plan['reader_template_sha256'] = relational_program.template_version(
                program, system=plan['system'], public_rules=view['read_input']['rules'],
                protocol='diversity_shared_claim_clause_v1')
            plan['version'] = digest({key: value for key, value in plan.items() if key != 'version'})
        requests = relational_program.unit_requests(view['plans'][0]['relational_program'])
        if any(relational_program.unit_requests(plan['relational_program']) != requests for plan in view['plans']):
            raise ValueError('The controls must share identical public clause and entity scope')
        for request in requests:
            name = request['source_anchor']
            if name in shared:
                start, end = shared[name]['source_span']
                request['source_excerpts'] = [text[start:end]]
            else:
                request['source_excerpts'] = excerpts[name]
        view['read_input']['unit_requests'] = requests
        return [view]


def unit_reviews(source, view):
    """Check every original pair independently before accepting the shared TRAIN coordinate."""
    original, = diversity_source_binding.Provider().views(source)
    reviews = diversity_unit_reviews(source, original)
    fixed, = (plan for plan in view['plans'] if plan['is_correct_fixed_raw_control'])
    program = fixed['relational_program']
    groups = program['composition_certificate']['shared_clause_bindings']
    merged = {name: reviews[name] for name in program['units'] if name in reviews}
    for name, group in groups.items():
        first, *rest = (reviews[unit] for unit in group['original_units'])
        if any(other['admissible_states'] != first['admissible_states'] for other in rest):
            raise ValueError('The independent source audit refutes the proposed claim observation equality')
        merged[name] = first
    return merged
