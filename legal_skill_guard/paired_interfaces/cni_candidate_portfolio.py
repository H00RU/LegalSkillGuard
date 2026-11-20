"""Select hypothesis readers from one budget-matched set of measured candidates."""

from legal_skill_guard.paired_interfaces import cni_signed_candidate_groups as signed


def group_evidence(raw, proofs, ranked):
    losses, recoveries, disagreements = {}, {}, set()
    for task, roles in ranked.items():
        if len({raw[role][task]['answer'] for role in roles}) > 1:
            disagreements.add(task)
        if task not in proofs:
            continue
        supported = {role for role in roles if signed.support(raw[role][task], proofs[task])}
        if supported:
            losses[task] = set(roles) - supported
            first = roles[0]
            if first in supported and any(role not in supported for role in roles[1:]):
                recoveries[task] = first
    return losses, recoveries, disagreements


def select(groups, ranked, *, physical_group_width):
    """Use the same ranked candidate pool and source gate in every screened policy."""
    if not groups:
        raise ValueError('At least one source-certified group is required')
    best = {task: roles[0] for task, roles in ranked.items()}
    priorities = {
        'candidate_driven': lambda row: (
            sum(best[task] in lost for task, lost in row['losses'].items()),
            len(row['recoveries']), row['position'],
        ),
        'chronological': lambda row: row['position'],
        'answer_disagreement': lambda row: (len(row['disagreements']), row['position']),
        'in_scope_disagreement': lambda row: (len(row['disagreements'] & set(row['proof_tasks'])), row['position']),
    }
    result = {}
    for policy, key in priorities.items():
        chosen = max(groups, key=key)
        allocation = {
            task: next(role for role in roles if role not in chosen['losses'].get(task, ()))
            for task, roles in ranked.items()
        }
        result[policy] = {
            'position': chosen['position'], 'physical_screen_budget': physical_group_width,
            'programs': allocation, 'replaced_native_choices': sorted(task for task in best
                                                                     if best[task] != allocation[task]),
        }
    result['native_fit_only'] = {
        'position': None, 'physical_screen_budget': 0, 'programs': best, 'replaced_native_choices': [],
    }
    return result
