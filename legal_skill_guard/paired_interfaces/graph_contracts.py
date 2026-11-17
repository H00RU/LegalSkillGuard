"""Compile the already generated local encoding into the actual graph grammar.

This closes the generic-graph/finite-codec assembly gap. Codes, groups and
consumer semantics come from the frozen M1 asset, never observed answers.
"""
from copy import deepcopy

from legal_skill_guard.skill_evolution.objects import digest


def compile_weight_contract(original):
    plan = deepcopy(original)
    codec = plan.get('weight_codec')
    if codec is None:
        return plan
    codes = [group['code'] for group in codec['groups']]
    if len(codes) != len(set(codes)) or not codes:
        raise ValueError('The frozen encoding must have a nonempty distinct alphabet')
    relation = plan['schema']['properties']['relations']['items']
    stated, uncertain, other = (deepcopy(relation) for _ in range(3))
    stated['properties']['predicate'] = {'type': 'string', 'enum': ['weight']}
    stated['properties']['status'] = {'type': 'string', 'enum': ['stated']}
    stated['properties']['value'] = {'type': 'string', 'enum': codes}
    uncertain['properties']['predicate'] = {'type': 'string', 'enum': ['weight']}
    uncertain['properties']['status'] = {'type': 'string', 'enum': ['negated', 'not_stated', 'unknown', 'unread']}
    # The original unknown/null validator still applies. Negated exact values
    # are not merged into an entire residual class, since that would overstate
    # what is negated. None of these branches executes a known positive weight.
    other['properties']['predicate']['enum'] = [p for p in other['properties']['predicate']['enum'] if p != 'weight']
    plan['schema']['properties']['relations']['items'] = {'anyOf': [stated, uncertain, other]}
    plan['locked_candidate_version'] = plan.pop('version')
    plan['read_grammar_contract'] = {'derivation': 'frozen residual groups',
        'codes': codes, 'module_binding': codec['module_binding'],
        'native_labels_or_read_outcomes_used': False,
        'unknown_negated_unstated_unread_preserved': True}
    plan['version'] = digest(plan)
    return plan
