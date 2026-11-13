"""Construct jointly bound edits of the actual acquired reader/composition.

This module consumes real before/after annotations and actual observed source
relations. It adds no legal fact or rule. Program and structured-language
components use the same local AST edit core; structured values round-trip only
through literal_eval, never arbitrary execution.
"""
import ast
from copy import deepcopy
import json

from .joint_updates import applications, learn, _delta, _tree, replay_delta
from .objects import digest
from .relational_rules import validate_language
from .scoped_grammar import constructors
from .semantic_operations import validate_operations
from .source_composition import validate_renderers, validate_template_constructors
from .span_compiler import validate_procedure


COMPONENTS = {
    'planner_program': ('program', ('planner_program',)),
    'operations': ('data', ('operations',)),
    'language': ('data', ('language',)),
    'renderers': ('data', ('renderers',)),
    'composition_program': ('program', ('composition_program',)),
    'decision_program': ('program', ('spec', 'decision_program')),
    'constructors': ('data', ('spec', 'constructors')),
}
SOURCE_VIEW = 'actual_source_observations_before_update'


def component_program(library, name):
    kind, path = COMPONENTS[name]; value = library
    for key in path:
        value = value[key]
    if kind == 'program':
        return value
    # A single explicit assignment represents the actual structured component;
    # it preserves ordered lists, exact scalars and every field.
    return 'value = ' + repr(value) + '\n'


def _install(library, name, program):
    kind, path = COMPONENTS[name]
    if kind == 'program':
        validate_procedure(program, allow_helpers=True)
        value = program
    else:
        tree = ast.parse(program)
        if (len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign)
                or len(tree.body[0].targets) != 1 or not isinstance(tree.body[0].targets[0], ast.Name)
                or tree.body[0].targets[0].id != 'value'):
            raise ValueError('A structured component must remain one literal value assignment')
        value = ast.literal_eval(tree.body[0].value)
        # These are actual JSON acquisition assets; no Python-only values.
        if json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False)) != value:
            raise ValueError('Structured learned components must retain JSON values')
    current = library
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


def learn_bundle(examples, signatures, *, source_constants=None, program_constants=None):
    """Learn actual corresponding local edits with explicitly shared role names."""
    if not examples:
        raise ValueError('Actual multi-component repair events required')
    names = [e['component'] for e in examples[0]['edits']]
    if not names or len(set(names)) != len(names) or not set(names) <= set(COMPONENTS):
        raise ValueError('Distinct actual acquired components required')
    if any([e['component'] for e in event['edits']] != names for event in examples):
        raise ValueError('Align actual repair components before learning a bundle')
    constants = {} if program_constants is None else program_constants
    edits = []; roles = {}
    for index, name in enumerate(names):
        items = [{**deepcopy(event['edits'][index]), 'event_id': event['event_id'],
                  'source_facts': deepcopy(event['source_facts'])} for event in examples]
        update = learn(items, signatures, source_constants=source_constants,
                       program_constants=constants.get(name, ()))
        for role, sort in update['source_sorts'].items():
            if role in roles and roles[role] != sort:
                raise ValueError('Shared roles across components need the same nominal type')
            roles[role] = sort
        edits.append({'component': name, 'update': update})
    bundle = {'source_view': SOURCE_VIEW, 'edits': edits,
        'supporting_events': [e['event_id'] for e in examples],
        'source_sorts': roles, 'meaning_or_generalization_certified': False}
    bundle['id'] = digest(bundle)
    return bundle


def apply_bundle(bundle, observation, library):
    """Join all source/code matches on one substitution before selecting code."""
    if bundle['source_view'] != SOURCE_VIEW:
        raise ValueError('Use actual observations before the edited components')
    facts = observation['context']['facts']
    states = [{'binding': {}, 'applications': []}]
    for edit in bundle['edits']:
        name, update = edit['component'], edit['update']
        program = component_program(library, name)
        next_states = []
        for state in states:
            shared = {k: v for k, v in state['binding'].items() if k in update['source_sorts']}
            for application in applications(update, facts, program, source_binding=shared):
                next_states.append({'binding': {**state['binding'], **application['source_binding']},
                    'applications': [*state['applications'], {'component': name, **application}]})
        states = next_states
    outcomes = {}
    for state in states:
        target = deepcopy(library)
        for application in state['applications']:
            _install(target, application['component'], application['program'])
        key = digest({a['component']: _tree(ast.parse(a['program'])) for a in state['applications']})
        outcome = outcomes.setdefault(key, {'library': target, 'applications': state['applications'],
                                           'source_bindings': []})
        if state['binding'] not in outcome['source_bindings']:
            outcome['source_bindings'].append(state['binding'])
    result = {'status': 'applied' if len(outcomes) == 1 else 'ambiguous' if outcomes else 'not_applicable',
        'bundle_id': bundle['id'], 'distinct_candidate_edits': len(outcomes),
        'matching_joint_bindings': len(states), 'observation_sha256': observation['visible_inputs_sha256'],
        'new_model_requests': 0}
    if len(outcomes) == 1:
        result.update(next(iter(outcomes.values())))
    return result


def library_candidates(library, bundles, observation, training_texts, *, enabled=True):
    """Build U candidates and conditional priors for the normal acquisition flow.

    Selection must still minimize actual supervised error/constraints first.
    Editing the composition invalidates its old fit; editing concept meanings
    requires real new reads through the existing read-identity contract.
    """
    if not enabled:
        return {'candidates': [], 'attempts': [], 'U_enabled': False, 'new_model_requests': 0}
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    attempts = []; candidates = []
    for index, bundle in enumerate(bundles):
        application = apply_bundle(bundle, observation, library)
        attempts.append({k: v for k, v in application.items() if k not in ('library', 'applications')})
        if application['status'] != 'applied':
            continue
        target = application['library']; changed = {a['component'] for a in application['applications']}
        validate_operations(target['operations'], training_texts)
        constructors(target['spec'])
        if 'language' in target:
            validate_language(target['language']); validate_renderers(target['language'], target['renderers'])
            validate_template_constructors(target['renderers'], target['spec'])
        if changed & {'language', 'renderers', 'operations', 'planner_program', 'constructors'} and 'language' in target:
            target['selected_rule_ids'] = None
            target.pop('fit', None)
        raw_edits = {}; macro_edits = []
        for edit in application['applications']:
            before = component_program(library, edit['component'])
            raw = _delta(_tree(ast.parse(before)), _tree(ast.parse(edit['program'])))
            if _tree(ast.parse(replay_delta(before, raw))) != _tree(ast.parse(edit['program'])):
                raise ValueError('An actual component edit did not decode exactly')
            raw_edits[edit['component']] = raw
            macro_edits.append({'component': edit['component'], 'code_path': edit['code_path']})
        # Every current source binding is explicit. We do not compress away a
        # role based on a guessed dependency or share witnesses across sources.
        macro = {'bundle_index': index, 'component_edits': macro_edits,
                 'current_source_parameters': application['source_bindings']}
        raw_bytes = size({'raw_edits': raw_edits}); macro_bytes = size({'macro_edit': macro})
        candidates.append({**application, 'library': target, 'raw_edits': raw_edits,
            'macro_edit': macro, 'raw_edit_bytes': raw_bytes, 'macro_edit_bytes': macro_bytes,
            'conditional_edit_bytes': min(raw_bytes, macro_bytes),
            'dictionary_sha256': digest(bundles), 'dictionary_bytes': size(bundles),
            'coding': 'frozen_canonical_JSON_utf8_joint_component_delta_or_bundle_parameters_v1',
            'new_or_changed_readings_certified': False, 'native_or_source_semantics_certified': False})
    return {'candidates': sorted(candidates, key=lambda c: (c['conditional_edit_bytes'], c['bundle_id'])),
        'attempts': attempts, 'U_enabled': True, 'new_model_requests': 0}
