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


def ordinary_action(contract, before, initial):
    """Give ordinary rereading the component named by its existing error message.

    This control needs no program dependency slice. If the message names no
    unique known component, it reads the full active contract. No label is used.
    """
    full = json.loads(contract['observation_schema_json'])
    components = list(full.get('properties', {}))
    selected = []
    for reason in before.get('unresolved', []):
        matches = [cid for cid in components if reason == cid or reason.startswith(cid + '_')
                   or reason.startswith(cid + ':') or (':' + cid) in reason or (' ' + cid) in reason]
        if matches:
            maximum = max(map(len, matches))
            selected.extend(cid for cid in matches if len(cid) == maximum and cid not in selected)
    scoped = bool(selected)
    schema = ({'type': 'object', 'properties': {cid: deepcopy(full['properties'][cid]) for cid in selected},
        'required': selected, 'additionalProperties': False} if scoped else full)
    return {'schema': schema, 'component_ids': selected if scoped else components,
        'scope_reason': 'existing_unresolved_message' if scoped else 'full_active_observation_contract',
        'prompt': contract['observation_prompt'] + '\nRe-read the complete current case and correct the unresolved factual observation for the requested existing components. Return the SAME component schemas. Do not infer the target claim as a case fact; keep genuinely unread channels explicit.',
        'current_observation': deepcopy(initial), 'current_execution': before,
        'same_observation_contract_sha256': digest(contract), 'program_slice_used': False}


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
                    from .conversion_residual import repair_step as conversion_step
                    outcome = conversion_step(contract, kernel, public, deepcopy(initial), checked_read)
                else:
                    outcome = repair_step(contract, kernel, public, deepcopy(initial), checked_read)
            else:
                action = ordinary_action(contract, before, initial)
                value, receipt = checked_read(action)
                jsonschema.validate(value, action['schema'])
                updated = deepcopy(initial)
                updated.update(deepcopy(value))
                jsonschema.validate(updated, json.loads(contract['observation_schema_json']))
                updated_grounded = apply_adapter(contract, kernel, public, updated,
                    literal_context=literal_bindings({'public': public}))
                outcome = {'execution': execute_alternatives(kernel, updated_grounded),
                    'read_requested': True, 'observation_after': updated, 'read_receipt': receipt, 'action': action}
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
