"""Collapse repeated witnesses before decoding a two-slot covenant read."""


def fold_pair(row, candidates, first, second):
    """Preserve the cited family while leaving the other family unresolved."""
    if row[first] == row[second] and row[first] in candidates:
        return {**row, second: None}
    return row
