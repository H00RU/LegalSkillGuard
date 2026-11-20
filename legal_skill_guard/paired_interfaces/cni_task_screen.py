"""Screen individual hypothesis updates with one matched source group."""


INCUMBENT, PROPOSAL = 'incumbent', 'proposal'
SCREENED = ('candidate_driven', 'chronological', 'answer_disagreement', 'in_scope_disagreement')


def select(groups, fit):
    """Apply the same scoped veto to every matched group choice."""
    if not groups:
        raise ValueError('A screened update requires at least one bound source group')
    eligible = {task for task, values in fit.items() if values[PROPOSAL] > values[INCUMBENT]}
    priorities = {
        'candidate_driven': lambda row: (len(eligible.intersection(row['lost'])),
                                        len(eligible.intersection(row['recovered'])), row['position']),
        'chronological': lambda row: row['position'],
        'answer_disagreement': lambda row: (len(row['disagreements']), row['position']),
        'in_scope_disagreement': lambda row: (len(eligible.intersection(row['disagreements'])), row['position']),
    }
    policies = {}
    for name in SCREENED:
        row = max(groups, key=priorities[name])
        blocked = eligible.intersection(row['lost'])
        policies[name] = {
            'position': row['position'], 'physical_screen_budget': 2, 'blocked': sorted(blocked),
            'programs': {task: PROPOSAL if task in eligible - blocked else INCUMBENT for task in fit},
        }
    policies['native_per_hypothesis'] = {
        'position': None, 'physical_screen_budget': 0, 'blocked': [],
        'programs': {task: PROPOSAL if task in eligible else INCUMBENT for task in fit},
    }
    return policies
