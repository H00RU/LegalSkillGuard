"""Select equal-budget contract screens using independently proved assertions."""


def support(answer, proof):
    return (answer['answer'] == proof['answer']
            and set(proof['evidence_sentence_ids']) <= set(answer['evidence_sentence_ids']))


def compatibility(before, after, proofs):
    """Recognize only newly introduced source contradictions or lost witnesses."""
    old = {task for task, proof in proofs.items() if support(before[task], proof)}
    new = {task for task, proof in proofs.items() if support(after[task], proof)}
    return {'lost': sorted(old - new), 'recovered': sorted(new - old)}


def select(groups, fit_gain):
    """Every screened policy chooses one complete two-read group."""
    if not groups:
        raise ValueError('Candidate screening requires at least one certified source group')
    latest = max(groups, key=lambda row: row['position'])
    disagreed = max(groups, key=lambda row: (row['disagreement'], row['position']))
    directed = max(groups, key=lambda row: (len(row['lost']), len(row['recovered']), row['position']))
    result = {}
    for name, group in (('candidate_driven', directed), ('chronological', latest),
                        ('answer_disagreement', disagreed)):
        blocked = bool(group['lost'])
        result[name] = {'position': group['position'], 'physical_screen_budget': 2, 'veto': blocked,
                        'decision': 'proposal' if fit_gain > 0 and not blocked else 'incumbent'}
    result['native_fit_only'] = {'position': None, 'physical_screen_budget': 0, 'veto': False,
                                 'decision': 'proposal' if fit_gain > 0 else 'incumbent'}
    return result
