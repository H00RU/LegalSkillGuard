"""Evaluate a proposed skill update on settled TRAIN reads.

The actual executor and ledger verifier are supplied by the study actor.
The selector consumes the same reads for its shared, independent and
single-witness controls and keeps the native TRAIN comparison separate.
"""
from copy import deepcopy

from legal_skill_guard.paired_interfaces.shared_semantics import (
    ExplanationState, allowed_relation, consistent_assignment, has_assertion, is_unobserved, matches_assertions,
)


def unsupported_literal_assertions(outputs, allowed_signatures, fields):
    """Literal source assertions require entailment across all admissible readings."""
    allowed_signatures = tuple(allowed_signatures)
    if not allowed_signatures or any(len(signature) != len(outputs) for signature in allowed_signatures):
        raise ValueError('Literal assertion checks require nonempty matched reference signatures')
    fields = set(fields)
    unsupported = []
    for index, output in enumerate(outputs):
        if is_unobserved(output):
            continue
        if type(output) is not dict or not fields <= output.keys():
            raise ValueError('Literal assertion fields must be present in the declared local projection')
        for field in sorted(fields):
            observed = output[field]
            if is_unobserved(observed):
                continue
            if not all(matches_assertions(observed, signature[index][field])
                       for signature in allowed_signatures):
                unsupported.append({'case_index': index, 'field': field})
    return unsupported


def validate_patch(theory, patch_sha256, group_reads, native_comparisons, *,
                   visible_train, verify_projection, verify_native_pair):
    """Return a reproducible selection receipt for one measured patch."""
    visible = set(visible_train)
    state = ExplanationState(theory, patch_sha256)
    controls = []
    relations = []
    seen_groups = set()
    for group in group_reads:
        cases = group['cases']
        outputs = group['outputs']
        group_key = tuple(sorted(case.source_id for case in cases))
        if (group_key in seen_groups or not group_key or len(set(group_key)) != len(group_key)
                or any(case.root_id not in visible for case in cases)):
            raise ValueError('Groups must identify distinct variants from the visible TRAIN prefix')
        seen_groups.add(group_key)
        real_ids = group['physical_call_ids']
        if len(set(real_ids)) != len(real_ids):
            raise ValueError('One physical response cannot certify distinct group members')
        verified = state.observe(
            cases, outputs, physical_call_ids=real_ids, evidence_kind='actual_model',
            physical_verifier=lambda identity, case, output:
                verify_projection(patch_sha256, identity, case, output),
        )
        independent = allowed_relation(theory, cases, mode='independent_completions')
        relation = allowed_relation(theory, cases)
        relations.append(relation)
        literal_fields = group.get('literal_assertion_fields', ())
        controls.append({
            'source_ids': [case.source_id for case in cases],
            'independent_per_case_compatible': any(
                matches_assertions(outputs, expected)
                for expected in independent['signatures'].values()),
            'shared_locally_compatible': verified['locally_allowed'],
            'shared_prefix_compatible': verified['cumulative_shared_explanation_exists'],
            'asserted_outputs_present': has_assertion(outputs),
        })
        if literal_fields:
            controls[-1]['unsupported_literal_assertions'] = unsupported_literal_assertions(
                outputs, relation['signatures'].values(), literal_fields)

    if relations:
        factors = [[assignment for support in relation['supports'].values() for assignment in support]
                   for relation in relations]
        singleton = consistent_assignment(factors)
        if singleton is None:
            raise ValueError('Reference groups have no jointly feasible audited interpretation')
        for group, relation, control in zip(group_reads, relations, controls):
            signature_key = next(
                key for key, support in relation['supports'].items()
                if any(all(singleton[k] == v for k, v in assignment.items())
                       for assignment in support))
            control['single_witness_compatible'] = matches_assertions(
                group['outputs'], relation['signatures'][signature_key])

    native_gain = 0.0
    native_sources = set()
    for pair in native_comparisons:
        source = pair['source']
        if source in native_sources or source not in visible:
            raise ValueError('Native utility requires unique, visible TRAIN mothers')
        baseline, candidate = pair['baseline_utility'], pair['patch_utility']
        if (any(type(value) not in (int, float) or not 0 <= value <= 1
                for value in (baseline, candidate))
                or verify_native_pair(patch_sha256, pair) is not True):
            raise ValueError('Native comparison is missing a verified paired execution')
        native_sources.add(source)
        native_gain += candidate - baseline

    observations = state.observations
    refuted = any(row['status'] == 'refuted' for row in observations)
    asserted = any(row['asserted_output_present'] for row in observations)
    if refuted:
        status = 'rejected_by_shared_explanation'
    elif any(control.get('unsupported_literal_assertions') for control in controls):
        status = 'rejected_unsupported_literal_assertion'
    elif not asserted or not native_sources:
        status = 'insufficient_positive_supervision'
    elif native_gain <= 0:
        status = 'retain_incumbent_on_native_train'
    else:
        status = 'eligible_train_update'
    return {
        'patch_sha256': patch_sha256,
        'status': status,
        'explanation_state': state.snapshot(),
        'matched_controls': controls,
        'paired_native_sources': sorted(native_sources),
        'native_utility_sum_delta': native_gain,
        'native_comparisons': deepcopy(native_comparisons),
    }
