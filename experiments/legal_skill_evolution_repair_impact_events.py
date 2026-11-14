"""Build actual source-backed impact supervision and exercise its contract path.

This imports preserved executions only. No original experiment is rerun, no new
source/label is introduced, and two mothers sharing one update are not counted
as two independent program revisions. Learned impact prediction remains pending.
"""
from copy import deepcopy
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.repair_impact_contracts import generation_requirements, select_revisions, observed_couplings

OUT = e.ROOT / 'artifacts/legal_skill_evolution_repair_impact_20261114'
MAUD = e.ROOT / 'artifacts/legal_skill_evolution_MAUD_role_repair_20261114'


def maud_event():
    original = e.read(MAUD / 'actual_repair_event.json'); reviews = original['actual_source_reviews']
    contract = {'repairs': [], 'conclusions': [], 'source': 'actual_MAUD_role_repair',
        'impact_profile_status': 'observed_supervision_not_yet_predictive'}
    for review in reviews:
        contract['repairs'].append({'id': review['id'], 'dependency': 'inquiry_target_role',
            'evidence_ref': 'actual_repair_event.json#' + review['id'], 'source': review['source'],
            'judgment': review['judgment']})
        contract['conclusions'].append({'id': review['source'] + ':' + review['view'],
            'source': review['source'], 'view': review['view'], 'value': 'Constructive knowledge',
            'validity': 'supported', 'evidence_ref': 'unchanged_after_reasonable_inquiry_requirement',
            'source_quote': review['evidence_quote']})
    components = {'Original': [], 'ConsumerOnly': ['decision_program'],
        'RendererOnly': ['constructors', 'renderers'],
        'Repaired': ['constructors', 'renderers', 'decision_program'],
        'NoFitWithSamePublicRepair': ['constructors', 'renderers', 'decision_program']}
    candidates = []
    for name, changed in components.items():
        files = list((MAUD / 'component_execution' / name).glob('*.json'))
        actual = [e.read(f) for f in files]
        effects = {'repairs': {}, 'conclusions': {}}
        references = []
        for review in reviews:
            row = next(r for r in actual if r['source'] == review['source'] and r['view'] == review['view'])
            effects['repairs'][review['id']] = row['partial_source_check']['source_review_passed']
            view, = row['feedback']['views']
            effects['conclusions'][review['source'] + ':' + review['view']] = view['execution']['value']['answer']
            path = next(f for f in files if e.read(f)['source'] == review['source'] and e.read(f)['view'] == review['view'])
            references.append({'path': str(path.relative_to(e.ROOT)), 'sha256': digest(e.read(path))})
        candidates.append({'id': name, 'changed_components': changed, 'edit_cost': len(changed),
            'actual_effects': effects, 'execution_refs': references})
    result = {'event_id': 'actual_MAUD_inquiry_target_repair', 'parent_program_revision': original['physical_teacher_call'],
        'independent_program_updates': 1, 'mother_sources': sorted({r['source'] for r in reviews}),
        'source_reviews': reviews, 'contract': contract,
        'generation_input': generation_requirements(contract), 'actual_candidates': candidates,
        'selection': select_revisions(contract, candidates),
        'observed_coupling_supervision': observed_couplings(contract, candidates),
        'known_simple_control_absorption': True, 'not_a_new_U_contribution_score': True}
    return result


def nda_harm_event():
    root = e.ROOT / 'artifacts/legal_skill_evolution_source_scope_repair_20261114'
    actual = e.read(root / 'source_results.json')['rows']; previous = e.read(e.OUT / 'source_results.json')['rows']
    prev = {r['source']: r for r in previous}; harms = []
    for source in actual:
        key = source['source']
        old_views = prev[key]['ConstraintAcquire']['per_view']
        new_views = source['ConstraintAcquire']['views']
        for a, b in zip(old_views, new_views):
            if a['score'] and a['score']['correct'] and not (b['score'] and b['score']['correct']):
                harms.append({'source': key, 'view': a['view'],
                    'before_answer': a['answer'], 'after_answer': b['execution']['value']['answer'],
                    'actual_before_used_roots': a['actual_used_roots'],
                    'old_native_correct_is_not_automatically_a_supported_legal_invariant': True,
                    'source_validity_review_needed_before_protection': True})
    assert len(harms) == 4
    return {'event_id': 'actual_NDA_scope_repair_and_cross_source_harm',
        'independent_program_updates': 1, 'actual_cross_source_regressions': harms,
        'source_corrections_ref': str((root / 'unbound_C_actual_mechanism_and_partial_review.json').relative_to(e.ROOT)),
        'old_correct_answer_not_automatically_frozen': True,
        'whole_patch_and_additive_overwrite_controls_retained': True}


def e82b_event():
    name = 'ContractNLI_e82b951aca3540fe6be6bfa63cae714cb7c7d55f38631402a3b6521eb6fc9bc6.json'
    before_path = e.ROOT / 'artifacts/legal_skill_evolution_field_binding_function_reuse_20261114/acquisition/ConstraintAcquire' / name
    after_path = e.ROOT / 'artifacts/legal_skill_evolution_scoped_atoms_20261114/execution/ConstraintAcquire/fitted_execution' / name
    before = e.read(before_path); after = e.read(after_path)
    answers = [a for a in before['observation']['visible_inputs']['answers']
        if any(s in a['id'] for s in ('trigger', 'material', 'connection'))]
    norms = [r for r in after['execution']['source_output']['statements'] if r['term'][0] == 'disposal_obligation']
    units = [u for u in before['observation']['visible_inputs']['units'] if u['id'] in (42, 45)]
    assert len(norms) == 1 and len(units) == 2
    return {'event_id': 'actual_e82b_action_specific_source_repair', 'independent_program_updates': 1,
        'mother_source': before['source'], 'source_evidence': units,
        'actual_before_readings': answers, 'actual_after_norms': norms,
        'source_supported_required_changes': ['destroy_trigger_from_project_end_to_request',
            'destroy_material_from_information_copies_derivatives_to_receiving_and_downstream_copies'],
        'source_supported_stable_relations': ['return_trigger_is_request',
            'return_material_includes_confidential_information_and_copies', 'return_AND_destroy_connection'],
        'source_role_labels_are_acquisition_supervision_not_a_new_experiment': True,
        'before_ref': str(before_path.relative_to(e.ROOT)), 'after_ref': str(after_path.relative_to(e.ROOT)),
        'not_counted_as_fresh_or_independent_validation': True}


def run():
    events = [maud_event(), nda_harm_event(), e82b_event()]
    for event in events:
        immutable_json(OUT / (event['event_id'] + '.json'), event)
    immutable_json(OUT / 'current_supervision_status_v2.json', {'events': [e['event_id'] for e in events],
        'independent_parent_program_updates': 3, 'new_model_requests': 0,
        'generation_requirements_materialized': True,
        'real_editor_has_consumed_impact_generation_requirements': False,
        'selection_executed_on_preserved_real_candidate_variants': True,
        'learned_legal_dependency_impact_predictor_complete': False,
        'unreviewed_native_regressions_not_promoted_to_keep_labels': True,
        'goal_complete': False})
    print(json.dumps({'actual_parent_updates': len(events),
        'MAUD_selected': events[0]['selection']['selected'],
        'MAUD_observed_bundles': events[0]['observed_coupling_supervision']['observed_minimal_admissible_bundles'],
        'NDA_cross_source_harms': len(events[1]['actual_cross_source_regressions']),
        'new_model_requests': 0, 'impact_predictor_complete': False}), flush=True)


if __name__ == '__main__':
    run()
