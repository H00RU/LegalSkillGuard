"""Project a witness for each covenant anchor into the existing MAUD consumer."""

from itertools import product

EXCLUDED = 'no_operative_pandemic_exception'


def project(anchors, markers, witnesses):
    """Expose existential links while retaining unresolved anchors for each family."""
    by_family = {}
    for anchor, item in anchors.items():
        by_family.setdefault(item['candidate_family'], []).append(witnesses[anchor])
    return {
        marker: {
            family: _state(marker, slots) for family, slots in by_family.items()
        }
        for marker in markers
    }


def _state(marker, slots):
    if marker in slots:
        return True
    return None if None in slots else False


def check_equivalence(consume, families, trigger):
    """Preserve existing native answers, first witnesses and unknown coverage."""
    ordinary, negative = families
    anchors = {
        'o1': {'candidate_family': ordinary},
        'o2': {'candidate_family': ordinary},
        'n1': {'candidate_family': negative},
    }
    markers = ('first', 'second')
    count = 0
    for cells in product((True, False, None), repeat=len(anchors) * len(markers)):
        slots = {anchor: cells[start:start + len(markers)]
                 for start, anchor in zip(range(0, len(cells), len(markers)), anchors, strict=True)}
        witnesses = {
            anchor: next((marker for marker, flag in zip(markers, row, strict=True) if flag is True),
                         None if None in row else EXCLUDED)
            for anchor, row in slots.items()
        }
        original = {}
        for index, marker in enumerate(markers):
            ordinary_cells = (slots['o1'][index], slots['o2'][index])
            original[marker] = {
                families[ordinary]: True if True in ordinary_cells else None if None in ordinary_cells else False,
                families[negative]: slots['n1'][index],
                trigger: True,
            }
        projected = {
            marker: {**{families[f]: value for f, value in states.items()}, trigger: True}
            for marker, states in project(anchors, markers, witnesses).items()
        }
        for flags in product((True, False), repeat=len(families)):
            coverage = dict(zip(families, flags, strict=True))
            if consume(original, coverage) != consume(projected, coverage):
                raise ValueError('Anchor witnesses must preserve the consumer and the first positive witness')
            count += 1
    return count
