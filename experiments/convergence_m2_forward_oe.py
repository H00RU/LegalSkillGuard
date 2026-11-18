"""Carry measured TRAIN-only title failures into matched future OE updates."""

from experiments.convergence_pilot_b0 import ROOT, read, sha
from legal_skill_guard.skill_evolution.objects import digest


FILES = {
    'experiments/convergence_m2_forward_oe.py', 'experiments/convergence_oe_conditioned_value_probe.py',
    'experiments/convergence_oe_title_partition_probe.py', 'experiments/convergence_oe_title_value_probe.py',
    'legal_skill_guard/paired_interfaces/convergence_oe_title_value.py',
}


def prepare_conditioning(visible, executor):
    # The archived probes also import the fit driver for their B4 source audit.
    from experiments.convergence_oe_conditioned_value_probe import POINTER, SCHEMA, SYSTEM, _condition, _source_inputs
    from experiments.convergence_oe_title_partition_probe import crossed_groups, joint_group
    from experiments.convergence_oe_title_value_probe import _materials

    root = ROOT / read(POINTER)['artifact_root']
    saved = read(root / 'binding.json')
    terminal = read(root / 'terminal.json')
    archive = read(root / 'source_snapshot_receipt.json')
    if (root.name != digest(saved) or saved['executor'] != executor or archive['archived_terminal_binding'] != root.name
            or archive['files'] != saved['source_sha256'] or terminal['TEST_opened']
            or terminal['status'] != 'completed_M2_natural_conditioned_value_probe' or terminal['executor_calls'] != 8
            or not saved['literal_facts_supplied_equally']):
        raise ValueError('Use the verified TRAIN-only diagnostic from the fixed pilot')
    _, _, source, original, _, _, _, _ = _materials()
    if source != saved['root'] or source not in {row['key'] for row in visible}:
        raise ValueError('The original pilot group must remain in the visible TRAIN prefix')
    joint = joint_group(crossed_groups(original))
    theory, shared, independent = _condition(joint)
    cases = joint['cases']
    inputs = _source_inputs(cases)
    if (digest(inputs) != saved['source_query_inputs_sha256'] or digest([SYSTEM, SCHEMA]) != saved['local_contract_sha256']
            or digest(shared['signatures']) != saved['shared_signatures_sha256']
            or digest(independent['signatures']) != saved['independent_signatures_sha256']):
        raise ValueError('The forward projection must retain the exact prior calibrated wire and interpretation scope')
    expected = [query['independently_verified_source_facts']['stated_value_dollars'] for query in inputs]
    for name in ('candidate', 'incumbent'):
        rows = terminal['measured'][name]['reads']
        if [row['value'] for row in rows] != expected or any(row['failure'] is not None for row in rows):
            raise ValueError('Teacher feedback must describe the actual measured full-amount failure')
    feedback = {'observed_issue': 'Both prior programs used the entire asset value even for opposing components of the same title filter.',
                'source_rule': 'Keep the same ownership interpretation under amount-only changes. The full value goes to one component, and the other receives zero. Preserve uncertainty when title cannot be determined.',
                'native_labels_or_source_text_supplied': False}
    record = {'root': str(root.relative_to(ROOT)), 'terminal_sha256': sha(root / 'terminal.json'),
              'query_sha256': saved['source_query_inputs_sha256'], 'shared_signatures_sha256': saved['shared_signatures_sha256']}
    return {'binding': record, 'theory': theory, 'cases': cases, 'inputs': inputs, 'teacher_feedback': feedback}


def selection_decision(candidate, incumbent, literal_status):
    """Require a coherent incumbent witness before using shared-only rejection."""
    controls = {'native_only': bool(candidate['native_positive'])}
    literal_ok = literal_status == 'eligible_train_update' and controls['native_only']
    paired = (literal_ok and candidate['all_queries_observed'] and incumbent['all_queries_observed']
              and candidate['independent_compatible'] and incumbent['shared_compatible'])
    selective = paired and not candidate['shared_compatible']
    controls.update(literal_only=literal_ok)
    for selector, field in (('independent_completions', 'independent_compatible'),
                            ('shared_explanation', 'shared_compatible'), ('single_interpretation', 'single_compatible')):
        controls[selector] = literal_ok and candidate[field] if candidate['all_queries_observed'] else None
    return {'eligible_paired_contrast': paired, 'isolated_shared_rejection_applied': selective,
            'candidate_selected_by': controls}


def measure_update(reader, out, context, candidate, incumbent, native, visible, literal):
    from experiments.convergence_oe_conditioned_value_probe import _measure, _validate

    measured, summaries = {}, {}
    neutral = [{**row, 'patch_utility': row['baseline_utility']} for row in native]
    for role, program, pairs in (('incumbent', incumbent, neutral), ('candidate', candidate, native)):
        reads = _measure(reader, out, context['cases'], context['inputs'], program)
        validation, summary = _validate(context['theory'], context['cases'], reads, program, pairs, visible)
        summaries[role] = {**summary, 'all_queries_observed': all(r['value'] is not None for r in reads)}
        measured[role] = {'reads': reads, 'validation': validation}
    selection = selection_decision(summaries['candidate'], summaries['incumbent'], literal['status'])
    return {**selection, 'conditioned_projection': {'comparison': summaries, 'evidence': measured,
                                                     'binding': context['binding']}}
