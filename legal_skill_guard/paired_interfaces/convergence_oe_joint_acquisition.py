"""Rank classification and valuation update groups using signed repairs."""

from itertools import product

from legal_skill_guard.paired_interfaces import convergence_oe_bound_acquisition as bounds


TASKS = ('EC', 'EV')
ROUTES = {'incumbent': ('incumbent', 'incumbent'), 'EC_only': ('proposal', 'incumbent'),
          'EV_only': ('incumbent', 'proposal'), 'whole_proposal': ('proposal', 'proposal')}
POLICIES = (*bounds.POLICIES, 'native_fit_only')


def route(answers, name):
    return {task: answers[role][task] for task, role in zip(TASKS, ROUTES[name], strict=True)}


def relation_supported(ec, ev, ec_title, ev_title):
    """One statutory category, with each input's title and EV availability separate."""
    for category, available, a, b in product((False, True), repeat=4):
        if ec_title is not None and a is not ec_title or ev_title is not None and b is not ev_title:
            continue
        if ec is not None and ec is not (category and a):
            continue
        if not ev or category and b and available:
            return True
    return False


def direct_supported(ec, ev, ec_title, ev_title):
    return not ((ec is True and ec_title is False) or (ev and ev_title is False)
                or (ec is False and ev and ec_title is True))


def conflicts(answers, titles, exact):
    ec, ev = (answers[task] or {} for task in TASKS)
    wrong = set()
    for asset, (t_ec, t_ev) in titles.items():
        stated_ec = set(ec.get(asset, ()))
        positive_ev = {claim['citation'] for claim in ev.get(asset, ()) if claim['claim_value'] > 0}
        for law in stated_ec | positive_ev:
            presence = law in stated_ec
            ec_flag = presence if asset in ec or exact.get((asset, law)) is False else None
            flags = ec_flag, law in positive_ev, t_ec, t_ev
            shared = relation_supported(*flags)
            if shared != direct_supported(*flags):
                raise ValueError('The direct screen must receive exactly the same scoped evidence')
            if not shared:
                wrong.add((asset, law))
    return wrong


def port_claims(answer, task):
    if task == 'EC':
        return {(asset, law) for asset, laws in (answer or {}).items() for law in laws}
    return {(asset, claim['citation'], claim['claim_value']) for asset, claims in (answer or {}).items()
            for claim in claims}


def evidence(entering, proposal, titles, exact, values, item_cap, *, require_category=False, ev_excluded=()):
    previous = conflicts(entering, titles, exact)
    current = conflicts(proposal, titles, exact)
    old_ec, new_ec = (port_claims(x['EC'], 'EC') for x in (entering, proposal))
    old_ev, new_ev = (port_claims(x['EV'], 'EV') for x in (entering, proposal))
    retained_positive = {(asset, law) for asset, law, amount in old_ev & new_ev if amount > 0}
    consistency_gains = (previous - current) & (new_ec - old_ec) & retained_positive
    joined_repairs = {pair for pair in consistency_gains if exact.get(pair) is True
                      or not require_category and exact.get(pair) is None}
    ec_repairs = {pair for pair in new_ec - old_ec if exact.get(pair) is True and pair[0] in (entering['EC'] or {})}
    if entering['EC'] is not None and proposal['EC'] is not None:
        ec_repairs |= {pair for pair in old_ec - new_ec if exact.get(pair) is False and pair[0] in proposal['EC']}
    # A single EC correction can be backed by its paired EV read and a
    # literal category proof. Count it once.
    ec_repairs |= joined_repairs
    literal_errors = {pair for pair in new_ec - old_ec if exact.get(pair) is False}
    literal_errors |= {pair for pair in old_ec - new_ec if exact.get(pair) is True}
    ev_literal_errors = {(a, c) for a, c, value in new_ev - old_ev if value > 0 and (a, c) in ev_excluded}
    ev = bounds.evidence(entering['EV'], proposal['EV'], values, item_cap)
    return {
        'signed_repairs': len(ec_repairs) + ev['verified_repairs'],
        'joined_repairs': len(joined_repairs), 'cross_conflicts': len(current),
        'introduced_cross_conflicts': len(current - previous),
        'introduced_literal_errors': len(literal_errors) + len(ev_literal_errors),
        'unproved_consistency_gains': len(consistency_gains - joined_repairs),
        'unverified_disappearances': len(previous - current - joined_repairs) + ev['unverified_disappearances'],
        'incumbent_risk': len(previous) + ev['old_violations'],
        'proposal_violations': ev['proposal_violations'], 'new_violations': ev['new_violations'],
        'answer_disagreement': len(old_ec ^ new_ec) + ev['answer_disagreement'],
    }


def select(groups, native_gain, *, require_each_port=False):
    """Give each policy one measured source for the whole shared route pool."""
    def passes(row):
        return (row['signed_repairs'] > 0 and row['introduced_cross_conflicts'] == 0
                and row['introduced_literal_errors'] == 0 and row['new_violations'] == 0)

    def eligible(pos, name):
        if not passes(groups[pos][name]):
            return False
        if require_each_port and name == 'whole_proposal':
            return passes(groups[pos]['EC_only']) and passes(groups[pos]['EV_only'])
        return True

    def rank(policy, pos):
        whole = groups[pos]['whole_proposal']
        if policy == 'answer_disagreement':
            return whole['answer_disagreement'], pos
        if policy == 'incumbent_risk':
            return whole['incumbent_risk'], pos
        if policy == 'candidate_driven':
            return max((groups[pos][name]['signed_repairs'] for name in ROUTES
                        if native_gain[name] > 0 and eligible(pos, name)), default=0), pos
        return pos,

    choices = {}
    for policy in POLICIES:
        pos = max(groups, key=lambda pos: rank(policy, pos), default=None)
        picked = {name: eligible(pos, name) for name in groups.get(pos, {})}
        fits = ['incumbent', *(name for name in ROUTES if native_gain[name] > 0
                               and (picked.get(name, False) or policy == 'native_fit_only'))]
        winner = max(fits, key=lambda name: (native_gain[name], -ROUTES[name].count('proposal')))
        choices[policy] = {'route': winner, 'position': pos, 'screen_results': picked}
    return choices
