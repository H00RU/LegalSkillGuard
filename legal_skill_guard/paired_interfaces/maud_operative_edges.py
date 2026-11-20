"""Compose an operative condition with each covenanted effect before aggregating."""

from legal_skill_guard.paired_interfaces import maud_scope_relational as scope


FAMILIES = ('ordinary', 'negative')
EXCLUDED = {f'no_{family}_edge': family for family in FAMILIES}


def require_both(condition, attachment):
    if condition is False or attachment is False:
        return False
    if condition is None or attachment is None:
        return None
    return True


def project(candidates, first, second):
    """Resolve a marker's operative links to actual covenant IDs."""
    observed = {}
    for value in (first, second):
        if value is None:
            continue
        approved = value in candidates
        family = candidates[value]['candidate_family'] if approved else EXCLUDED.get(value)
        if family not in FAMILIES or family in observed:
            return None, None
        observed[family] = approved
    return tuple(observed.get(family) for family in FAMILIES)


def check_equivalence():
    """Check that the local conjunction preserves partial and excluded scopes."""
    module = scope.module()
    candidates = {name: {'candidate_family': name} for name in FAMILIES}
    for state in module.states:
        original = scope.local_consumer(state, {})
        expected = tuple(require_both(original[scope.PROJECTIONS[2]], original[coord])
                         for coord in scope.PROJECTIONS[:2])
        targets = [family if known else f'no_{family}_edge' if known is False else None
                   for family, known in zip(FAMILIES, expected, strict=True)]
        if project(candidates, *targets) != expected:
            raise ValueError('The operative edges must preserve every original local consumer state')
    return len(module.states)
