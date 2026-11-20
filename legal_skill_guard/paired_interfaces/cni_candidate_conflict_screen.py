"""Allocate readers from one equal-budget, source-checked ContractNLI group."""

from legal_skill_guard.paired_interfaces.cni_candidate_portfolio import group_evidence


def source_signals(raw, proofs, ranked):
    losses, repairs, disagreements = group_evidence(raw, proofs, ranked)
    class_conflicts, evidence_disagreements = {}, set()
    for task, roles in ranked.items():
        signatures = {(raw[role][task]['answer'], tuple(sorted(raw[role][task]['evidence_sentence_ids'])))
                      for role in roles}
        if len(signatures) > 1:
            evidence_disagreements.add(task)
        if task not in proofs:
            continue
        expected = proofs[task]['answer']
        asserted = {role: raw[role][task]['answer'] for role in roles}
        if expected in asserted.values():
            conflicts = {role for role, answer in asserted.items() if answer not in (None, expected)}
            if conflicts:
                class_conflicts[task] = conflicts
                losses.setdefault(task, set()).update(conflicts)
    return {
        'veto_by_task': {task: sorted(roles) for task, roles in losses.items() if roles},
        'class_conflicts': {task: sorted(roles) for task, roles in class_conflicts.items()},
        'leader_recoveries': sorted(repairs),
        'answer_disagreements': sorted(disagreements),
        'evidence_disagreements': sorted(evidence_disagreements),
        'proof_tasks': sorted(proofs),
    }


def choose(groups, ranked, *, physical_group_width):
    """Screen one group under a common veto, with several acquisition controls."""
    if not groups:
        raise ValueError('At least one measured source group is needed')
    leaders = {task: readers[0] for task, readers in ranked.items()}

    def leader_conflicts(group):
        return sum(leaders[task] in rejected for task, rejected in group['veto_by_task'].items())

    keys = {
        'candidate_driven': lambda group: (leader_conflicts(group), len(group['leader_recoveries']), group['position']),
        'chronological': lambda group: group['position'],
        'answer_disagreement': lambda group: (len(group['answer_disagreements']), group['position']),
        'in_scope_answer_disagreement': lambda group: (
            len(set(group['answer_disagreements']).intersection(group['proof_tasks'])), group['position'],
        ),
        'in_scope_evidence_disagreement': lambda group: (
            len(set(group['evidence_disagreements']).intersection(group['proof_tasks'])), group['position'],
        ),
        'source_class_conflict_count': lambda group: (
            sum(map(len, group['class_conflicts'].values())), group['position'],
        ),
    }
    choices = {}
    for policy, rank in keys.items():
        chosen = max(groups, key=rank)
        veto = chosen['veto_by_task']
        programs = {task: next(role for role in readers if role not in veto.get(task, ()))
                    for task, readers in ranked.items()}
        choices[policy] = {'position': chosen['position'], 'physical_screen_budget': physical_group_width,
                           'programs': programs,
                           'replaced_native_choices': sorted(task for task in leaders if programs[task] != leaders[task])}
    choices['native_fit_only'] = {'position': None, 'physical_screen_budget': 0, 'programs': leaders,
                                  'replaced_native_choices': []}
    return choices
