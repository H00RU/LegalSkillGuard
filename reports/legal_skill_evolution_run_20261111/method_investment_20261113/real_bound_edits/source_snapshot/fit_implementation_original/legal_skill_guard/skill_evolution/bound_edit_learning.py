"""Select source/program-bound effects against actual cut/retain witnesses.

The finite policy pool, source meanings and witnessed proof requirements are
acquired inputs. This exact cover learner supplies no legal relation or label.
"""
from copy import deepcopy
import json

from .objects import digest


def learn_effects(entries, effects, forbidden_proofs, protected_roots):
    """Minimum policy dictionary cutting every bad proof, preserving witnesses.

    effects[i][source] names actual pre-update root indices retired by policy i.
    Proofs are actual positive-program witnesses; each must lose a premise.
    The final chosen dictionary must still be reexecuted and source checked.
    """
    if len(entries) != len(effects) or not forbidden_proofs:
        raise ValueError('A finite actual effect pool and erroneous proof witnesses are required')
    for proof in forbidden_proofs:
        if not proof['root_indices']:
            raise ValueError('An unsupported conclusion is not a witnessed editable proof')
    eligible = []
    for index, (entry, application) in enumerate(zip(entries, effects)):
        if any(set(application.get(source, [])) & set(roots) for source, roots in protected_roots.items()):
            continue
        coverage = 0
        for position, proof in enumerate(forbidden_proofs):
            if set(application.get(proof['source'], [])) & set(proof['root_indices']):
                coverage |= 1 << position
        if coverage:
            eligible.append((index, coverage))
    # Exact dynamic programming on witnessed failed proofs, not repeated LLM
    # proposal generation or partial source claims treated as negative labels.
    def objective(indices):
        size = sum(len(json.dumps(entries[i]['policy'], sort_keys=True, separators=(',', ':')).encode()) for i in indices)
        retired = {(source, root) for i in indices for source, roots in effects[i].items() for root in roots}
        return len(indices), len(retired), size, tuple(entries[i]['id'] for i in indices)
    states = {0: ()}
    for index, coverage in eligible:
        for state, selected in list(states.items()):
            target = state | coverage; candidate = (*selected, index)
            if target not in states or objective(candidate) < objective(states[target]):
                states[target] = candidate
    required = (1 << len(forbidden_proofs)) - 1
    if required not in states:
        return {'status': 'not_expressible', 'candidate_count': len(entries),
            'eligible_count': len(eligible), 'uncovered_proof_witnesses': len(forbidden_proofs),
            'new_model_requests': 0}
    chosen = states[required]
    value = {'status': 'selected_requires_execution', 'entries': [deepcopy(entries[i]) for i in chosen],
        'candidate_count': len(entries), 'eligible_count': len(eligible),
        'objective': list(objective(chosen)[:3]),
        'forbidden_proofs': deepcopy(forbidden_proofs), 'protected_roots': deepcopy(protected_roots),
        'new_model_requests': 0, 'source_or_transfer_semantics_certified': False}
    value['id'] = digest(value)
    return value
