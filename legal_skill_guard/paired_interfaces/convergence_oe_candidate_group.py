"""Select an OpenExempt group that can refute a native-positive update."""

ENTERING = 'incumbent'
POLICIES = ('candidate_driven', 'chronological', 'answer_disagreement', 'incumbent_risk', 'native_fit_only')
VIOLATIONS = ('introduced_cross_conflicts', 'introduced_literal_errors', 'new_violations')


def refuted(evidence):
    return any(evidence[name] > 0 for name in VIOLATIONS)


def choose(groups, gain):
    """Use one complete source group and the same screen across selection policies."""
    roles = tuple(role for role in gain if role != ENTERING)
    eligible = [p for p in roles if gain[p] > 0]
    ordinary = max([ENTERING, *eligible], key=gain.__getitem__)
    if any(set(rows) != set(roles) for rows in groups.values()):
        raise ValueError('Every screened source must have complete matched candidate reads')

    def rank(position, policy):
        evidence = groups[position]
        if policy == 'candidate_driven':
            rejected = [p for p in eligible if refuted(evidence[p])]
            return (len(rejected), sum(gain[p] for p in rejected),
                    sum(evidence[p]['signed_repairs'] > 0 for p in eligible if p not in rejected), position)
        if policy == 'answer_disagreement':
            return sum(r['answer_disagreement'] for r in evidence.values()), position
        if policy == 'incumbent_risk':
            return max(r['incumbent_risk'] for r in evidence.values()), position
        return position,

    decisions = {}
    for policy in POLICIES:
        screened = policy != 'native_fit_only' and bool(groups)
        position = max(groups, key=lambda idx: rank(idx, policy)) if screened else None
        rows = groups.get(position, {})
        supported = [p for p in eligible if p in rows and not refuted(rows[p]) and rows[p]['signed_repairs'] > 0]
        decisions[policy] = {
            'position': position,
            'selected': max([ENTERING, *supported], key=gain.__getitem__) if policy != 'native_fit_only' else ordinary,
            'refuted_candidates': sorted(p for p in eligible if p in rows and refuted(rows[p])),
            'screened_reads': 2 * (len(roles) + 1) if screened else 0,
        }
    return decisions
