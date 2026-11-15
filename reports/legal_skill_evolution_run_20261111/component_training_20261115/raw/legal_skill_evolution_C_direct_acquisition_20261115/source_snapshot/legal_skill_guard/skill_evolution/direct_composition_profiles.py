"""Exact native-loss profiles for the current direct, fully observed G.

A selected direct rule emits all of its grounded heads together. Enumerating
arbitrary individual-head subsets is an unnecessary exponential relaxation.
This enumerates unions of actual per-rule outputs, preserving every argument
and provenance. It is complete for the actual G choices, not the more permissive
representation diagnostic. It adds no observation, source rule or model call.
"""
from copy import deepcopy
import time

from .objects import digest
from .relational_learning import execute_composition
from .relational_rules import canonical, context_identity, language_identity, validate_context
from .source_composition import render_composition, validate_renderers


def admissible_direct_compositions(library, observation, check_native, *, timeout_seconds=30):
    language = library['language']; context = observation['context']
    validate_context(context, language); validate_renderers(language, library['renderers'])
    if context['unknown_groups']:
        raise ValueError('Direct profile enumeration requires actual fully observed inputs; unknown is not filled')
    if any(language['signatures'][atom['predicate']]['kind'] != 'observed'
           for rule in language['rules'] for atom in rule['body']):
        raise ValueError('Direct profiles require observed rule bodies, not recursive or derived dependencies')
    if timeout_seconds <= 0:
        raise ValueError('Positive finite learning time allowance required')
    started = time.monotonic(); deadline = started + timeout_seconds
    base = {'language_sha256': language_identity(language), 'context_sha256': context_identity(context),
        'enumeration_scope': 'outputs_reachable_by_subsets_of_current_direct_rules',
        'not_a_complete_relaxed_representation_diagnostic': True, 'new_model_requests': 0}
    def normalize(result):
        return [{k: deepcopy(v) for k, v in atom.items() if k != 'context_index'}
                for atom in result['certain_outputs']]
    def solve(selected):
        return execute_composition(language, selected, context,
                                   timeout_seconds=max(.001, deadline - time.monotonic()))
    all_outputs = solve([r['id'] for r in language['rules']])
    if not all_outputs['complete']:
        return {**base, 'status': 'timeout', 'allowed_theories': None, 'evaluations': []}
    vocabulary = sorted(normalize(all_outputs), key=canonical)
    universe = {canonical(a): a for a in vocabulary}
    states = {(): []}; single_rules = []
    for rule in language['rules']:
        if time.monotonic() >= deadline:
            return {**base, 'status': 'timeout', 'vocabulary': vocabulary, 'allowed_theories': None, 'evaluations': []}
        actual = solve([rule['id']])
        if not actual['complete']:
            return {**base, 'status': 'timeout', 'vocabulary': vocabulary, 'allowed_theories': None, 'evaluations': []}
        atoms = normalize(actual); keys = {canonical(a) for a in atoms}
        if not keys <= set(universe):
            raise ValueError('A direct rule emitted a head outside the frozen actual vocabulary')
        single_rules.append({'rule_id': rule['id'], 'actual_outputs': atoms})
        for previous, witness in list(states.items()):
            combined = tuple(sorted(set(previous) | keys))
            states.setdefault(combined, [*witness, rule['id']])
    if set().union(*(set(canonical(a) for a in r['actual_outputs']) for r in single_rules)) != set(universe):
        raise ValueError('Actual direct-rule union differs from full G; do not assume independence')
    required = {canonical(a) for a in context['required']}; forbidden = {canonical(a) for a in context['forbidden']}
    evaluations = []; allowed = []
    for index, (keys, witness) in enumerate(sorted(states.items())):
        if time.monotonic() >= deadline:
            return {**base, 'status': 'timeout', 'vocabulary': vocabulary, 'allowed_theories': None,
                'evaluations': evaluations, 'reachable_theory_count': len(states)}
        theory = [deepcopy(universe[k]) for k in keys]
        record = {'theory_index': index, 'theory': theory, 'witness_rule_ids': witness,
                  'partial_source_constraints_satisfied': required <= set(keys) and not forbidden.intersection(keys)}
        if not record['partial_source_constraints_satisfied']:
            record.update({'admissible': False, 'reason': 'explicit_partial_source_constraint'})
        else:
            candidate = {**all_outputs, 'certain_outputs': [{**a, 'context_index': 0} for a in theory],
                         'possible_outputs': [{**a, 'context_index': 0} for a in theory]}
            try:
                output = render_composition(language, library['renderers'], observation, candidate, library['spec'])
            except (ValueError, KeyError, TypeError) as error:
                record.update({'admissible': False, 'reason': 'type_or_provenance_failure',
                               'error': type(error).__name__ + ': ' + str(error)})
            else:
                feedback = check_native(output)
                if type(feedback['accepted']) is not bool or not isinstance(feedback['reason'], str):
                    raise ValueError('Native feedback must report explicit status')
                record.update({'native_feedback': feedback, 'admissible': feedback['accepted'], 'reason': feedback['reason']})
                if record['admissible']:
                    allowed.append(theory)
        evaluations.append(record)
    return {**base, 'status': 'complete', 'vocabulary': vocabulary, 'allowed_theories': allowed,
        'evaluations': evaluations, 'all_candidates_execution': all_outputs,
        'single_rule_outputs': single_rules, 'finite_theory_count': len(states),
        'relaxed_ground_output_subset_count': 1 << len(vocabulary),
        'accepted_theory_count': len(allowed), 'elapsed_seconds': time.monotonic() - started}
