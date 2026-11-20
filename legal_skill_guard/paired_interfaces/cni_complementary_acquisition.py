"""Choose two source groups while keeping supported alternatives available."""

from itertools import combinations


def choose(groups, ranked, *, group_width):
    """Compare total conflict coverage with replacement capacity at the same budget."""
    leaders = {task: readers[0] for task, readers in ranked.items()}
    pool = []
    for pair in combinations(sorted(groups, key=lambda row: row['position']), 2):
        losses = {(task, role) for row in pair for task, roles in row['veto_by_task'].items() for role in roles}
        remaining = {task: [role for role in roles if (task, role) not in losses]
                     for task, roles in ranked.items()}
        if any(not roles for roles in remaining.values()):
            continue
        replaced = sorted(task for task, roles in remaining.items() if roles[0] != leaders[task])
        repaired = set().union(*(row['leader_recoveries'] for row in pair))
        global_disagreement = set().union(*(row['answer_disagreements'] for row in pair))
        scoped_disagreement = set().union(*(set(row['answer_disagreements']) & set(row['proof_tasks']) for row in pair))
        pool.append({
            'groups': [row['position'] for row in pair],
            'programs': {task: roles[0] for task, roles in remaining.items()},
            'replaced': replaced,
            'remaining_replacements': {task: len(remaining[task]) for task in replaced},
            'undisturbed_recoveries': len(repaired.difference(replaced)),
            'global_disagreement': len(global_disagreement),
            'scoped_disagreement': len(scoped_disagreement),
            'conflicts': len(losses),
        })
    if not pool:
        raise ValueError('No two-screen allocation preserves at least one measured reader per hypothesis')

    keys = {
        'candidate_complement': lambda pair: (
            len(pair['replaced']), sum(pair['remaining_replacements'].values()), pair['undisturbed_recoveries'],
        ),
        'leader_count': lambda pair: (len(pair['replaced']), pair['undisturbed_recoveries']),
        'direct_conflict_coverage': lambda pair: (pair['conflicts'],),
        'answer_disagreement_coverage': lambda pair: (pair['global_disagreement'],),
        'scoped_answer_disagreement_coverage': lambda pair: (pair['scoped_disagreement'],),
        'chronological': lambda pair: (),
    }
    result = {}
    for name, score in keys.items():
        pair = max(pool, key=lambda row: (*score(row), row['groups'][::-1]))
        result[name] = {**pair, 'physical_screen_budget': 2 * group_width}
    result['native_fit_only'] = {'groups': [], 'programs': leaders, 'physical_screen_budget': 0}
    return result, len(pool)
