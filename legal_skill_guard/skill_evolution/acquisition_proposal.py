"""Compile an actual teacher acquisition proposal through the shared checks."""
import ast
from copy import deepcopy
import json

from .open_acquisition import compile_update
from .objects import digest
from .scoped_grammar import constructors
from .semantic_operations import validate_operations
from .source_composition import validate_template_constructors
from .source_effect_update import function_update
from .source_observations import signatures
from .span_compiler import occurrences, validate_procedure


def _functions(modules):
    result = []
    for module in modules:
        tree = ast.parse(module)
        if any(not isinstance(n, ast.FunctionDef) for n in tree.body):
            raise ValueError('Only complete pure functions')
        pieces=[ast.get_source_segment(module,n) for n in tree.body]
        if ast.dump(ast.parse('\n\n'.join(pieces)),include_attributes=False)!=ast.dump(tree,include_attributes=False):
            raise ValueError('Function extraction changed the actual supplied AST')
        result.extend(pieces)
    return result


def compile_proposal(previous, proposal, arm, training_sources, *, source_functions=()):
    """Use exactly the same schema meanings, provenance and runtime for both arms.

    Wire-schema validation and any explicit format adaptation belong to the
    caller and remain recorded separately from this semantic compilation.
    """
    if arm not in ('ConstraintAcquire', 'FreeUpdate'):
        raise ValueError('Explicit acquisition architecture required')
    texts = {k: source['views'][0]['public']['source_text'] for k, source in training_sources.items()}
    inherited = {}
    for operation in proposal['operations']:
        for example in operation['examples']:
            if example['source'] in texts:
                continue
            matches = [s for s in previous['spec']['seeds'] if s['source'] == example['source']
                       and occurrences(s['quote'], example['quote'])]
            if not matches:
                raise ValueError('An example needs current text or a genuinely supplied inherited TRAIN quote')
            inherited.setdefault(example['source'], []).append(matches[0]['quote'])
    texts.update({source: '\n\n'.join(dict.fromkeys(quotes)) for source, quotes in inherited.items()})
    validate_operations(proposal['operations'], texts)
    contracts = {r['operation']: r for r in proposal['reading_contracts']}
    if (len(contracts) != len(proposal['reading_contracts'])
            or set(contracts) != {o['name'] for o in proposal['operations']}):
        raise ValueError('Declare every actual operation contract exactly once')
    for op in proposal['operations']:
        contract = contracts[op['name']]
        if contract['scope'] not in ('window', 'focus_last'):
            raise ValueError('Explicit acquired reading scope required')
        absence = contract['complete_source_absence_choices']
        if len(set(absence)) != len(absence) or not set(absence) <= {c['name'] for c in op['choices']}:
            raise ValueError('Absence policies must name acquired choices')
        if absence and contract['scope'] != 'window':
            raise ValueError('Complete-source absence requires window scope')
    planner = _functions(proposal['planner_functions']); decisions = _functions(proposal['decision_functions'])
    source_parts = _functions(source_functions)
    identities = {v for k, source in training_sources.items() for v in (k, source['parent_id'])}
    for code in planner + decisions + source_parts + ([proposal['composition']] if arm == 'FreeUpdate' else []):
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in identities
               for n in ast.walk(ast.parse(code))):
            raise ValueError('A source identity is not an applicability guard')
    scalar_declarations = deepcopy(previous['spec'].get('scalar_sorts', {}))
    if arm == 'ConstraintAcquire':
        language = json.loads(proposal['composition'])
        language['signatures'] = {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'},
                                  **language['signatures']}
        if any(language['constants'].get(s) for s in ('unit', 'term', 'query', 'json_node')):
            raise ValueError('Current opaque identities cannot be vocabulary')
        # Relational scalar sorts and term structural sorts are distinct type
        # layers. Preserve a finite acquired scalar domain rather than erase a
        # recipient-role/choice type to unrestricted text or invent wrapper IR.
        structural = {c['sort'] for c in previous['spec']['constructors'] + proposal['new_constructors']}
        for ctor in proposal['new_constructors']:
            for sort in ctor['arguments']:
                if sort == 'text' or sort in structural or sort not in language['constants']:
                    continue
                domain = language['constants'][sort]
                if any(not isinstance(value, str) for value in domain):
                    raise ValueError('Term scalar declarations need actual acquired string values')
                scalar_declarations[sort] = sorted(set(scalar_declarations.get(sort, []) + domain))
        semantic = {'constructors': proposal['new_constructors'], 'decision_functions': decisions}
        if scalar_declarations: semantic['scalar_sorts'] = scalar_declarations
        library = compile_update(previous, {**proposal, 'scope': 'window', 'planner_functions': planner,
            'language': language, 'renderers': json.loads(proposal['renderers_json'])}, texts,
            semantic_update=semantic)
        if not set(proposal['suggested_rule_ids']) <= {r['id'] for r in language['rules']}:
            raise ValueError('NoFit selected an unproposed rule')
        library['suggested_rule_ids'] = proposal['suggested_rule_ids']
        validate_template_constructors(library['renderers'], library['spec'])
    else:
        validate_procedure(proposal['composition'], allow_helpers=True)
        spec = deepcopy(previous['spec']); spec['constructors'].extend(deepcopy(proposal['new_constructors']))
        spec['decision_program'] = function_update(spec['decision_program'], decisions); constructors(spec)
        library = {'operations': proposal['operations'],
            'planner_program': function_update(previous['planner_program'], planner), 'scope': 'window',
            'composition_program': proposal['composition'], 'spec': spec}
    library['operation_scopes'] = {n: r['scope'] for n, r in contracts.items()}
    library['complete_source_absence_choices'] = {n: r['complete_source_absence_choices']
        for n, r in contracts.items() if r['complete_source_absence_choices']}
    if source_functions:
        program = function_update(previous['source_program'], source_parts)
        validate_procedure(program, allow_helpers=True)
        library['source_program'] = program
    elif 'source_program' in previous:
        library['source_program'] = previous['source_program']
    if 'source_program' in library:
        old={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(previous['source_program']).body}
        new={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(library['source_program']).body}
        library['source_program_update']={
            'previous_program_sha256':digest(previous['source_program']),
            'program_sha256':digest(library['source_program']),
            'changed_function_names':sorted(n for n in set(old)|set(new) if old.get(n)!=new.get(n)),
            'structural_change_is_not_method_credit':True}
    return library, {'source_to_actual_supplied_seed_quotes': inherited,
        'finite_scalar_sorts_from_actual_acquired_vocabulary': scalar_declarations,
        'source_functions_installed': len(source_functions),
        'new_source_text_or_labels_supplied': False, 'new_physical_requests': 0}
