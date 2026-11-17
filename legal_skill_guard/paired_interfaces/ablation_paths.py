"""Source-free operator ablations without growing the primary candidate pool.

Compression merges only equal complete residuals. Refinement starts coarse and
splits with an executable differing context. If both end at one representation,
that degeneracy is evidence about the ablation,not a manufactured advantage.
"""
from copy import deepcopy
import json

from legal_skill_guard.paired_interfaces.residual import (
    canonical, compile_pair, reader_prompt, reader_schema, value_partition)
from legal_skill_guard.paired_interfaces.program_residual import specialize


def _blocks_key(blocks, module):
    field = module.fields[0]
    return sorted(tuple(sorted(canonical(module.states[i][field]) for i in block)) for block in blocks)


def finite_operator_paths(module):
    if len(module.fields) != 1:
        raise ValueError('This ablation is one declared local scalar,not an answer encoding')
    signatures = [canonical(outcome) for outcome in module.outcomes]
    compressed = [[i] for i in range(len(module.states))]
    merges = []
    while True:
        pair = next(((i, j) for i in range(len(compressed)) for j in range(i + 1, len(compressed))
                     if signatures[compressed[i][0]] == signatures[compressed[j][0]]), None)
        if pair is None:
            break
        i, j = pair
        merges.append({'left': [module.states[k] for k in compressed[i]],
                       'right': [module.states[k] for k in compressed[j]],
                       'all_context_and_output_residuals_equal': True})
        compressed[i] = sorted(compressed[i] + compressed.pop(j))
    refined, splits = [list(range(len(module.states)))], []
    while True:
        collision = next(((b, i, j) for b, block in enumerate(refined) for i in block for j in block
                          if i < j and signatures[i] != signatures[j]), None)
        if collision is None:
            break
        block_index, left, right = collision
        context = next(c for c, (a, b) in enumerate(zip(module.outcomes[left], module.outcomes[right])) if a != b)
        groups = {}
        for index in refined[block_index]:
            groups.setdefault(canonical(module.outcomes[index][context]), []).append(index)
        splits.append({'left_local_state': module.states[left], 'right_local_state': module.states[right],
            'context': module.contexts[context], 'left_output': module.outcomes[left][context],
            'right_output': module.outcomes[right][context], 'new_blocks': len(groups)})
        refined[block_index:block_index + 1] = list(groups.values())
    if _blocks_key(compressed, module) != _blocks_key(refined, module):
        raise ValueError('Operator restrictions did not reach the same residual partition')
    field = module.fields[0]
    groups = value_partition(module, field)
    wanted = sorted(tuple(sorted(canonical(value) for value in group['members'])) for group in groups)
    if wanted != _blocks_key(compressed, module):
        raise ValueError('The canonical codec differs from the witnessed operator endpoints')
    features = [{'name': field + '__residual_code', 'operation': 'residual_bucket', 'field': field, 'groups': groups}]
    assets = {name: compile_pair(module, features, operation=name) for name in ('compression_only', 'refinement_only')}
    identical = (reader_schema(assets['compression_only']) == reader_schema(assets['refinement_only'])
                 and reader_prompt(assets['compression_only']) == reader_prompt(assets['refinement_only']))
    return {'module_binding': module.binding, 'compression_merges': merges, 'refinement_splits': splits,
        'assets': assets, 'complete_finite_output_vectors_preserved': True,
        'same_reader_wire_contract': identical, 'operator_path_distinguishable_from_final_accuracy': not identical,
        'native_labels_sources_or_weak_outputs_used': False,
        'compression_start_classes': len(module.states), 'refinement_start_classes': 1, 'end_classes': len(groups)}


def projection_operator_paths(skill, regime, executions):
    """OE fields;executions are fixed program calls,never native target labels."""
    residual = specialize(skill['procedure'], {'governing_regime': regime}, allowed_context_fields={'governing_regime'})
    full = set(skill['inputs']) - {'governing_regime', 'output_family'}
    required = set(residual['input_fields']) - {'output_family'}
    if not required <= full:
        raise ValueError('Public-context residual still depends on an unbound context field')
    protected = required & {'asset_descriptions', 'asset_values', 'number_of_debtors'}
    if not {'asset_descriptions', 'asset_values'} <= protected:
        raise ValueError('Keep exact inventory descriptions and amounts in every ablation')
    by_input = {canonical(row['inputs']): row['output'] for row in executions}
    witnesses = []
    for field in sorted(required - protected):
        found = None
        for row in executions:
            left = row['inputs']
            if left['governing_regime'] != regime:
                raise ValueError('Witness table belongs to another public law context')
            right = deepcopy(left)
            if not field.startswith('asset_is_') or any(type(v) is not bool for v in left[field]):
                raise ValueError('The refinement witness domain must explicitly describe this factual port')
            right[field] = [not value for value in left[field]]
            key = canonical(right)
            if key in by_input and canonical(row['output']) != canonical(by_input[key]):
                found = {'field': field, 'left_inputs': left, 'right_inputs': right,
                    'left_program_output': row['output'], 'right_program_output': by_input[key],
                    'only_this_port_changed': True}
                break
        if found is None:
            raise ValueError('No executed distinguishing witness for required refinement port: ' + field)
        witnesses.append(found)
    return {'public_regime': regime, 'frozen_legal_program_unchanged': True,
        'compression_start_ports': sorted(full), 'compression_remove_only': sorted(full - required),
        'refinement_start_protected_ports': sorted(protected), 'refinement_add_only': sorted(required - protected),
        'refinement_witnesses': witnesses, 'final_ports': sorted(required),
        'same_endpoint_as_primary_local_records': True, 'same_reader_wire_contract': True,
        'operator_path_distinguishable_from_final_accuracy': False,
        'exact_public_context_program_certificate': residual['certificate'],
        'both_EC_EV_and_all_remaining_numeric_array_contexts_preserved_by_static_program_proof': True,
        'finite_witnesses_do_not_certify_source_meaning_or_legal_truth': True,
        'native_labels_sources_or_weak_outputs_used': False}
