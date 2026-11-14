"""Matched follow-up reads under one frozen learned observation contract.

Eligibility uses only the common initial execution, never a native label or
which policy later succeeds. Both branches retain their raw observations and
run the same binding adapter and legal kernel. Unsupported residuals are logged
rather than relabelled as successful targeted reads.
"""
from copy import deepcopy
import json

import jsonschema

from .case_observation_contract import apply_adapter, execute_alternatives
from .kernel_residual_reader import repair_step
from .literal_facts import literal_bindings
from .objects import digest


def compare_reads(contract, kernel, public, observation, read):
    """Run one matched opportunity; ``read(policy, action)`` returns value, receipt.

    This is a comparison runtime, not a claim of novelty or an empirical result.
    It accepts no grading information and does not edit the learned contract.
    """
    initial = deepcopy(observation)
    before_contract = digest(contract)
    grounded = apply_adapter(contract, kernel, public, initial,
        literal_context=literal_bindings({'public': public}))
    before = execute_alternatives(kernel, grounded)
    result = {'contract_sha256': before_contract, 'kernel_sha256': digest(kernel),
        'initial_observation_sha256': digest(initial), 'common_before': before,
        'eligible': not before['handled'] and contract['requires_neural_read'],
        'eligibility_uses_native_answers': False, 'policies': {}}
    if not result['eligible']:
        result['reason'] = 'Initial execution handled or contract declares no neural read'
        return result
    for policy in ('residual_guided', 'ordinary_reread'):
        calls = []

        def checked_read(action):
            if calls:
                raise ValueError('One physical read opportunity per matched step')
            calls.append({'action': deepcopy(action)})
            value, receipt = read(policy, action)
            calls[-1].update(value=deepcopy(value), receipt=deepcopy(receipt))
            return value, receipt

        try:
            if policy == 'residual_guided':
                if kernel.get('backend') == 'sara_statute_program':
                    # The Python dependency slicer cannot trace the immutable
                    # author Prolog program. Do not pretend otherwise or swap P.
                    outcome = {'execution': before, 'read_requested': False,
                        'reason': 'Native Prolog residual-to-observation lens not integrated'}
                else:
                    outcome = repair_step(contract, kernel, public, deepcopy(initial), checked_read)
            else:
                schema = json.loads(contract['observation_schema_json'])
                action = {'schema': schema,
                    'prompt': contract['observation_prompt'] + '\nRe-read the complete current case and correct the unresolved factual observation. Return the full SAME observation schema. Do not infer the target claim as a case fact; keep genuinely unread channels explicit.',
                    'current_observation': deepcopy(initial), 'current_execution': before,
                    'same_observation_contract_sha256': before_contract}
                value, receipt = checked_read(action)
                jsonschema.validate(value, schema)
                updated_grounded = apply_adapter(contract, kernel, public, value,
                    literal_context=literal_bindings({'public': public}))
                outcome = {'execution': execute_alternatives(kernel, updated_grounded),
                    'read_requested': True, 'observation_after': value, 'read_receipt': receipt}
            result['policies'][policy] = {**outcome, 'calls': calls,
                'same_initial_observation_sha256': digest(initial), 'fallback': False}
        except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
            result['policies'][policy] = {'execution': {'handled': False, 'answer': None},
                'error': type(error).__name__ + ': ' + str(error), 'calls': calls,
                'same_initial_observation_sha256': digest(initial), 'fallback': False}
    assert digest(contract) == before_contract and digest(observation) == digest(initial)
    result['contract_and_initial_observation_unchanged'] = True
    result['comparison_success_is_not_an_innovation_certificate'] = True
    return result
