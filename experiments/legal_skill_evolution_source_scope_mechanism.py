"""Actual scope-join interventions and partial source review, zero model calls.

Review only the previously stated concrete defects. This is neither complete
English semantic certification nor a new zero-error acceptance gate.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_gap_acquisition as e
from experiments import legal_skill_evolution_source_scope_repair as repair
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def walk(term):
    if isinstance(term, list):
        yield term
        for child in term[1:]:
            yield from walk(child)


def run():
    protocol, _ = repair.setup()
    _, _, public = e.setup()
    grading = e.read(e.previous.prior.prior.GRADING)
    library = e.read(repair.OUT / 'ConstraintAcquire/compiled.json')
    rows = []
    for key in protocol['acquisition_sources']:
        baseline = e.read(e.OUT / 'unbound_provenance_replay/execution' / e.name_for(key))
        actual = e.read(repair.OUT / 'ConstraintAcquire/execution' / e.name_for(key))
        current = actual['actual']['execution']['source_output']['statements']
        previous = baseline['execution']['source_output']['statements']
        interventions = []
        for name, removed in [
            ('remove_qualified_permission_join', {'compose_permission_qualified_v4'}),
            ('remove_disposal_scope_joins', {'compose_atomic_return_v4', 'compose_atomic_destroy_v4',
                'compose_alternative_v4', 'compose_conjunction_v4', 'compose_cause_alternative_v4'})]:
            lib = deepcopy(library)
            lib['selected_rule_ids'] = [r for r in lib['suggested_rule_ids'] if r not in removed]
            result = e.previous.prior.prior.evaluate_source(lib, actual['observation'], public[key], grading[key])
            interventions.append({'name': name, 'removed': sorted(removed), 'actual': result})
        if key.startswith('ContractNLI:6fce'):
            invalid = [s for s in previous if s['support_ids'] == [15]
                and s['term'][0] == 'disposal_obligation'
                and any(t[0] == 'action_alternative' for t in walk(s['term']))
                and any(t[0] == 'request_by' for t in walk(s['term']))]
            assert len(invalid) == 1
            invalid_terms = {digest(s['term']) for s in invalid}
            assert not invalid_terms & {digest(s['term']) for s in current}
            agreement = [s for s in current if s['term'][0] == 'disposal_obligation'
                and {20, 21} <= set(s['support_ids'])
                and any(t[:2] == ['source_local_trigger', 'agreement_end'] for t in walk(s['term']))]
            assert agreement
            qualifications = [s for s in current if s['term'][0] == 'permission'
                and any(t[0] in {'employees_of', 'consultants_of', 'agents_of'} for t in walk(s['term']))]
            assert len(qualifications) == 3
            assert all({10, 12} <= set(s['support_ids']) and any(t[0] == 'acquired_disclosure_condition_v4'
                and t[3] == 'written_required' for t in walk(s['term'])) for s in qualifications)
            cause = [s for s in current if any(t[0] == 'cause_disposal_v4' for t in walk(s['term']))]
            assert cause and all(s['support_ids'] == [61] for s in cause)
            review = {'incorrect_incoming_request_destroy_norm_removed': True,
                'agreement_end_return_acquired_with_parent_child_support': True,
                'three_participant_permissions_have_actual_written_qualification': True,
                'cause_affiliate_duty_and_reference_retained': True,
                'reference_expansion_still_unresolved': True}
        else:
            branch40 = [s for s in current if s['term'][0] == 'disposal_obligation' and s['support_ids'] == [39, 40]
                and any(t[0] == 'source_local_trigger' and t[1] == 'relationship_nonformation_deadline'
                    and 'three (3) months' in t[2] for t in walk(s['term']))]
            branch41 = [s for s in current if s['term'][0] == 'disposal_obligation' and s['support_ids'] == [39, 41]
                and any(t[0] == 'source_local_trigger' and t[1] == 'request'
                    and 'promptly' in t[2] for t in walk(s['term']))]
            assert branch40 and branch41
            review = {'separate_nonformation_and_prompt_request_branches_with_joint_support': True,
                'three_months_and_both_signatures_preserved_as_raw_trigger_qualification': True,
                'raw_qualification_is_not_an_executed_numeric_deadline_calculation': True}
        rows.append({'source': key, 'actual_partial_source_review': review,
            'full_source_semantics_certified': False, 'interventions': interventions})
    immutable_json(repair.OUT / 'unbound_C_actual_mechanism_and_partial_review.json',
        {'rows': rows, 'new_model_requests': 0, 'not_an_independent_C_or_U_effect_certificate': True})
    print(json.dumps({'actual_sources': len(rows), 'partial_source_checks_passed': True,
        'new_model_requests': 0}), flush=True)


if __name__ == '__main__':
    run()
