"""One factual repair step derived from the actual legal-program residual."""
from .case_observation_contract import apply_adapter, execute_alternatives
from .kernel_residual import execution_residual
from .literal_facts import literal_bindings
from .observation_slice import compile_field_read, merge_field_read


def repair_step(contract, kernel, public, observation, read):
    context = literal_bindings({'public': public})
    grounded = apply_adapter(contract, kernel, public, observation, literal_context=context)
    before = execute_alternatives(kernel, grounded)
    result = {'before': before, 'grounded_before': grounded, 'read_requested': False,
        'legal_program_unchanged': True, 'opaque_unresolved_checks_preserved': True}
    if before['handled']:
        return {**result, 'execution': before, 'reason': 'Already handled'}
    if len(grounded['bindings']) != 1:
        return {**result, 'execution': before, 'reason': 'This step needs one coherent binding; alternatives remain unresolved'}
    residual = execution_residual(kernel, grounded['bindings'][0]['inputs'])
    result['residual'] = residual
    if residual['actual_execution'].get('handled'):
        return {**result, 'execution': before, 'reason': 'Kernel handled but the adapter retains coverage uncertainty; do not erase it'}
    ports = list(dict.fromkeys(p[0] for p in residual['return_cause_input_paths'] if p))
    if len(ports) != 1:
        return {**result, 'execution': before, 'reason': 'No unique current factual channel; a joint/alternative plan is needed'}
    try:
        action = compile_field_read(contract, kernel, public, observation, ports[0])
    except ValueError as exc:
        return {**result, 'execution': before, 'reason': 'Unsupported observation lens: ' + str(exc)}
    value, receipt = read(action)
    updated = merge_field_read(observation, action, value, public)
    after_grounded = apply_adapter(contract, kernel, public, updated, literal_context=context)
    after = execute_alternatives(kernel, after_grounded)
    return {**result, 'action': action, 'read_requested': True, 'read': value,
        'read_receipt': receipt, 'observation_after': updated,
        'grounded_after': after_grounded, 'execution': after}
