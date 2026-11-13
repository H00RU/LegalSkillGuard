"""Compile an actual teacher acquisition proposal through the shared checks."""
import ast
from copy import deepcopy
import json

from .open_acquisition import compile_update
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
        result.extend(ast.get_source_segment(module, n) for n in tree.body)
    return result


def compile_proposal(previous, proposal, arm, training_sources):
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
    identities = {v for k, source in training_sources.items() for v in (k, source['parent_id'])}
    for code in planner + decisions + ([proposal['composition']] if arm == 'FreeUpdate' else []):
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in identities
               for n in ast.walk(ast.parse(code))):
            raise ValueError('A source identity is not an applicability guard')
    if arm == 'ConstraintAcquire':
        language = json.loads(proposal['composition'])
        language['signatures'] = {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'},
                                  **language['signatures']}
        if any(language['constants'].get(s) for s in ('unit', 'term', 'query', 'json_node')):
            raise ValueError('Current opaque identities cannot be vocabulary')
        library = compile_update(previous, {**proposal, 'scope': 'window', 'planner_functions': planner,
            'language': language, 'renderers': json.loads(proposal['renderers_json'])}, texts,
            semantic_update={'constructors': proposal['new_constructors'], 'decision_functions': decisions})
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
    return library, {'source_to_actual_supplied_seed_quotes': inherited,
                     'new_source_text_or_labels_supplied': False, 'new_physical_requests': 0}
