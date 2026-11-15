"""Plan factual observations over a finite set of coherent case bindings.

The legal program is unchanged. A plan minimizes worst-case declared observation
cost until the remaining bindings yield one handled program result. Its guarantee
is conditional on binding coverage and truthful observations; neither quotes nor
program agreement prove those assumptions. This is an execution component, not
an independent research-contribution claim.
"""
from functools import lru_cache
from math import isfinite

from .case_observation_contract import checked_witnesses, kernel_execution, validate_adapter
from .objects import digest
from .span_compiler import execute_json


def compile_observation_plan(kernel, bindings, observations):
    """Derive an exact decision tree from learned factual projections.

    Each observation declares a pure projection_program that maps one coherent
    argument assignment to the corresponding *factual* observation. A projection
    cannot contain native answers. Projections partition the binding set; they do
    not decide legal applicability or generate additional possible case facts.
    """
    if len({o['id'] for o in observations}) != len(observations):
        raise ValueError('Duplicate factual observation identity')
    results = []
    for row in bindings:
        try:
            result = kernel_execution(kernel, row['inputs'])
        except (KeyError, TypeError, ValueError) as exc:
            result = {'handled': False, 'answer': None, 'error': str(exc)}
        results.append(result)
    projections = {}
    for observation in observations:
        cost = observation['declared_cost']
        if type(cost) not in (int, float) or not isfinite(cost) or cost <= 0:
            raise ValueError('Observation cost must be positive and finite')
        validate_adapter(observation['projection_program'])
        values = []
        for row in bindings:
            projected = execute_json(observation['projection_program'], row['inputs'], {}, allow_helpers=True)
            if set(projected) != {'observation'}:
                raise ValueError('Factual projection must return only its observation')
            values.append(projected['observation'])
        projections[observation['id']] = values

    @lru_cache(None)
    def solve(indices):
        outputs = [results[i] for i in indices]
        if outputs and all(r['handled'] for r in outputs) and len({digest(r['answer']) for r in outputs}) == 1:
            return {'kind': 'answer', 'answer': outputs[0]['answer'], 'remaining_bindings': list(indices),
                'worst_case_declared_cost': 0}
        if not outputs or all(not r['handled'] for r in outputs):
            return {'kind': 'unresolved', 'answer': None, 'remaining_bindings': list(indices),
                'reason': 'The unchanged kernel does not cover the remaining assignments',
                'worst_case_declared_cost': 0}
        best = None
        for observation in observations:
            groups = {}
            values = projections[observation['id']]
            for i in indices:
                groups.setdefault(digest(values[i]), []).append(i)
            if len(groups) < 2:
                continue
            children = {key: solve(tuple(group)) for key, group in groups.items()}
            if any(child['worst_case_declared_cost'] is None for child in children.values()):
                continue
            cost = observation['declared_cost'] + max(c['worst_case_declared_cost'] for c in children.values())
            if best is None or (cost, observation['id']) < (best['worst_case_declared_cost'], best['observation_id']):
                best = {'kind': 'observe', 'observation_id': observation['id'],
                    'remaining_bindings': list(indices), 'worst_case_declared_cost': cost,
                    'branches': {key: {'observation': values[group[0]], 'next': children[key]}
                        for key, group in groups.items()}}
        return best or {'kind': 'unresolved', 'answer': None,
            'remaining_bindings': list(indices), 'reason': 'No supplied factual observation resolves all program outcomes',
            'worst_case_declared_cost': None}

    plan = solve(tuple(range(len(bindings))))
    return {'kernel_sha256': digest(kernel), 'bindings_sha256': digest(bindings),
        'observation_contract_sha256': digest(observations), 'tree': plan,
        'binding_program_results': results, 'planned_cost_is_not_actual_bill': True,
        'coverage_and_observation_truth_are_not_certified': True,
        'no_new_bindings_or_legal_rules_generated': True,
        'states_examined': solve.cache_info().currsize}


def consume_factual_observation(node, observation_id, value, witnesses, public):
    """An unseen or unsupported factual answer cannot select a favorable branch."""
    if node['kind'] != 'observe' or node['observation_id'] != observation_id:
        raise ValueError('Observation does not match the current factual read')
    checked_witnesses(witnesses, public)
    branch = node['branches'].get(digest(value))
    if branch is None or branch['observation'] != value:
        return {'kind': 'unresolved', 'answer': None,
            'remaining_bindings': node['remaining_bindings'],
            'reason': 'Actual factual observation lies outside the learned binding coverage',
            'requires_contract_update': True, 'actual_observation': value}
    return branch['next']
