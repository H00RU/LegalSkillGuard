"""Execute acquired repair-impact constraints during generation and selection.

The contract's legal dependencies, validity judgments and learned range come
from actual source-backed experience. This module supplies neither a law nor an
impact predictor. Unknown validity is not an invariant and old answers can lose
protection only with explicit counterevidence and a new required recheck.
"""
from copy import deepcopy

from .objects import digest


def generation_requirements(contract):
    """Give an editor semantic targets, protected conclusions and coupled checks.

    This is not a frozen-file/AST allowlist: an implementation can be replaced
    if its actual semantic effects satisfy the current contract.
    """
    return {'repair_dependencies': deepcopy(contract['repairs']),
        'preserve_supported_conclusions': [deepcopy(c) for c in contract['conclusions']
            if c['validity'] == 'supported' and not c.get('counterevidence')],
        'recheck_invalidated_conclusions': [deepcopy(c) for c in contract['conclusions']
            if c.get('counterevidence')],
        'unreviewed_is_not_unchanged_or_false': True,
        'contract_sha256': digest(contract)}


def verify_effects(contract, actual):
    """Check actual reexecuted observations, not an editor's claimed footprint."""
    failures = []; unknown = []
    for repair in contract['repairs']:
        result = actual.get('repairs', {}).get(repair['id'])
        if result is None:
            unknown.append({'id': repair['id'], 'reason': 'required_source_repair_not_checked'})
        elif result is not True:
            failures.append({'id': repair['id'], 'reason': 'source_counterevidence_not_resolved'})
    for conclusion in contract['conclusions']:
        identity = conclusion['id']
        if conclusion.get('counterevidence'):
            if not conclusion['counterevidence'].get('evidence_ref'):
                raise ValueError('Invalidating an old conclusion needs actual counterevidence')
            recheck = actual.get('rechecks', {}).get(identity)
            if recheck is None:
                unknown.append({'id': identity, 'reason': 'invalidated_conclusion_requires_recheck'})
            elif recheck is not True:
                failures.append({'id': identity, 'reason': 'new_source_recheck_failed'})
            continue
        if conclusion['validity'] != 'supported':
            continue
        result = actual.get('conclusions', {}).get(identity)
        if result is None:
            unknown.append({'id': identity, 'reason': 'supported_conclusion_not_reexecuted'})
        elif result != conclusion['value']:
            failures.append({'id': identity, 'reason': 'supported_conclusion_changed',
                'expected': conclusion['value'], 'actual': result})
    return {'status': 'rejected' if failures else 'needs_recheck' if unknown else 'admissible',
        'failures': failures, 'unknown': unknown, 'contract_sha256': digest(contract),
        'not_a_full_source_semantics_certificate': True}


def select_revisions(contract, candidates):
    """Constraint-first selection with ordinary edit size only as a tie-break."""
    checked = []; accepted = []
    for candidate in candidates:
        result = verify_effects(contract, candidate['actual_effects'])
        checked.append({'id': candidate['id'], **result})
        if result['status'] == 'admissible':
            accepted.append(candidate)
    selected = min(accepted, key=lambda c: (c['edit_cost'], c['id'])) if accepted else None
    return {'selected': None if selected is None else selected['id'], 'checked': checked,
        'no_success_from_missing_checks': True, 'new_model_requests': 0}


def observed_couplings(contract, candidates):
    """Infer required component bundles within actually executed alternatives.

    This is supervision for a later impact predictor. It is not a generalization
    claim: a component never varied in real data has unknown necessity.
    """
    passing = [c for c in candidates if verify_effects(contract, c['actual_effects'])['status'] == 'admissible']
    sets = {tuple(sorted(c['changed_components'])) for c in passing}
    minima = sorted(s for s in sets if not any(set(t) < set(s) for t in sets))
    return {'observed_minimal_admissible_bundles': [list(s) for s in minima],
        'actual_variants': len(candidates), 'unobserved_edits_have_unknown_necessity': True,
        'not_a_learned_cross_source_impact_profile': True}
