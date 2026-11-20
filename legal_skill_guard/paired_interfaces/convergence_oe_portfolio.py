"""Select verifiable combinations of independently executed OpenExempt ports."""

from itertools import combinations, product

from legal_skill_guard.paired_interfaces import convergence_oe_candidate_group as candidates

ENTERING = candidates.ENTERING
PORTS = ('EC', 'EV')
BASE = (ENTERING, ENTERING)


def routes(readers):
    return tuple(product(readers, repeat=len(PORTS)))


def compose(answers, route):
    return {task: answers[program][task] for task, program in zip(PORTS, route, strict=True)}


def changed_ports(route):
    return tuple((i, program) for i, program in enumerate(route) if program != ENTERING)


def admissible(groups, selected, route):
    """Require a witnessed repair per changed port and check the actual composition."""
    if any(candidates.refuted(groups[pos][route]) for pos in selected):
        return False
    for i, reader in changed_ports(route):
        single = tuple(reader if j == i else ENTERING for j in range(len(PORTS)))
        if not any(groups[pos][single]['signed_repairs'] > 0 for pos in selected):
            return False
    return True


def select(groups, gains, readers, budget=2):
    """Give every acquisition policy the same source group pool and budget."""
    wanted = tuple(route for route, gain in gains.items() if route != BASE
                   and gain > 0 and all(gains[tuple(reader if j == i else ENTERING for j in range(len(PORTS)))] > 0
                                        for i, reader in changed_ports(route)))
    positions = sorted(groups)
    expected = set(routes(readers))
    if set(gains) != expected or any(set(group) != expected for group in groups.values()):
        raise ValueError('All policies must compare the same fully measured route pool')
    count = min(budget, len(positions))
    if count < 0:
        raise ValueError('A source budget cannot be negative')

    def utility(route):
        return gains[route], -len(changed_ports(route))

    def provable(selection):
        return [path for path in wanted if admissible(groups, selection, path)]

    def candidate_rank(selection):
        possible = provable(selection)
        excluded = [path for path in wanted if any(candidates.refuted(groups[pos][path]) for pos in selection)]
        return (max((gains[path] for path in possible), default=0.0),
                len(excluded), sum(gains[path] for path in excluded), selection)

    def control_rank(pos, name):
        rows = groups[pos]
        if name == 'answer_disagreement':
            # Count original whole-reader disagreement once, independent of how many
            # Cartesian assignments reuse any one of its readouts.
            return sum(rows[p, p]['answer_disagreement'] for p in readers if p != ENTERING), pos
        if name == 'incumbent_risk':
            return rows[BASE]['incumbent_risk'], pos
        return pos,

    decisions = {}
    for name in candidates.POLICIES:
        if name == 'native_fit_only':
            selected, possible = (), wanted
        elif name == 'candidate_driven' and count:
            selected = max(combinations(positions, count), key=candidate_rank)
            possible = provable(selected)
        else:
            selected = tuple(sorted(sorted(positions, key=lambda pos: control_rank(pos, name))[-count:])) if count else ()
            possible = provable(selected)
        decisions[name] = {
            'positions': list(selected), 'route': max([BASE, *possible], key=utility),
            'screened_read_uses': len(selected) * len(readers) * len(PORTS),
        }
    return decisions
