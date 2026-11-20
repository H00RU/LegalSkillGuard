"""Align public MAUD excerpts and preserve the attachment of omission gaps."""

import re


OMISSION = '<omitted>'
PANDEMIC = re.compile(r'\b(?:COVID(?:-?\s*19)?|pandemic|SARS(?:-CoV-2)?)\b', re.I)
EXCEPT = re.compile(r'\bexcept\b', re.I)
GOVERNOR = re.compile(r'\b(?:shall|will)\s+not\b|\b(?:neither|none of)\b[^;:]{1,180}?\bshall\b', re.I)
AFFIRMATIVE = re.compile(
    r'\b(?:shall|will)\s+(?:(?:and|shall|will|cause|the|its|subsidiaries|to)\b[, ]*)*'
    r'(?:conduct|carry on|use|operate|preserve)\b', re.I,
)
SENTENCE_END = re.compile(r'(?<!\d)\.(?=\s+[A-Z])')
RESTRICTED_IMPORT = re.compile(
    r'except to the extent any of clauses (?P<clauses>\([A-Z]\)[A-Z(), andor]+?) '
    r'of this paragraph apply thereto', re.I,
)
LABEL = re.compile(r'\(([A-Z])\)')


def align_omissions(excerpt, sibling):
    """Return the unique ordered occurrence of every preserved excerpt fragment."""
    pieces = [part.strip() for part in excerpt.split(OMISSION)]
    if len(pieces) < 2 or any(not p for p in pieces):
        return None
    first, cursor = [], 0
    for phrase in pieces:
        start = sibling.find(phrase, cursor)
        if start < 0:
            return None
        cursor = start + len(phrase)
        first.append((start, cursor))
    cursor = len(sibling)
    for phrase, (start, _) in zip(reversed(pieces), reversed(first), strict=True):
        if sibling.rfind(phrase, 0, cursor) != start:
            return None
        cursor = start
    text = sibling[first[0][0]:first[-1][1]]
    if OMISSION in text:
        return None
    return first


def outer(text):
    """Blank parentheticals without changing offsets in the normalized excerpt."""
    result, depth = [], 0
    for char in text:
        if char == '(':
            depth += 1
        result.append(char if depth == 0 else ' ')
        if char == ')':
            depth = max(0, depth - 1)
    return ''.join(result)


def numbered_clause_cues(preamble, restored_cues):
    """Associate parent-relative pandemic wording with its own outer letter."""
    levels, labels = 0, []
    for i, char in enumerate(preamble):
        if char == '(':
            if levels == 0 and (tag := LABEL.match(preamble, i)):
                labels.append((tag.start(), tag.end(), tag[1]))
            levels += 1
        elif char == ')':
            levels = max(0, levels - 1)
    return {name for (_, start, name), (end, _, _) in zip(
        labels, [*labels[1:], (len(preamble), 0, '')])
        if any(start <= a < b <= end for a, b in restored_cues)}


def attachment(excerpt, sibling):
    """Recover a missing condition only when the negative covenant imports it."""
    intervals = align_omissions(excerpt, sibling)
    if intervals is None:
        return None
    left, right = intervals[0][0], intervals[-1][1]
    restored = sibling[left:right]
    gaps = [(a[1] - left, b[0] - left) for a, b in zip(intervals, intervals[1:])]
    cues = [m for m in PANDEMIC.finditer(restored) if any(a <= m.start() and m.end() <= b for a, b in gaps)]
    if not cues:
        return None
    masked = outer(restored)
    target_start = intervals[-1][0] - left
    target = GOVERNOR.search(masked, target_start)
    if target is None:
        return None
    earlier = masked[:target.start()]
    scopes = list(EXCEPT.finditer(earlier))
    if not scopes:
        return None
    start = scopes[-1].start()
    roles = {'recovered_fragments': intervals, 'negative_governor': [target.start()+left, target.end()+left]}
    target_tail = restored[target.end():]
    if imported := RESTRICTED_IMPORT.search(target_tail):
        names = set(LABEL.findall(imported['clauses']))
        own_preamble = restored[start:target.start()]
        exception_end = AFFIRMATIVE.search(masked, start, target.start())
        if exception_end:
            own_preamble = restored[start:exception_end.start()]
        pandemic_letters = numbered_clause_cues(
            own_preamble, [(m.start() - start, m.end() - start) for m in cues])
        if pandemic_letters and not names & pandemic_letters:
            return {**roles, 'scope': 'excluded_by_explicit_clause_list',
                    'included': sorted(names), 'pandemic_letters': sorted(pandemic_letters)}
        # A listed import is meaningful only when the enclosing preamble and
        # its labels can be located. Other cases stay undecided.
        if pandemic_letters and names & pandemic_letters:
            return {**roles, 'scope': 'attached_by_explicit_clause_list'}
    tests = (AFFIRMATIVE, GOVERNOR, SENTENCE_END)
    if any(pattern.search(masked, start, target.start()) for pattern in tests):
        return {**roles, 'scope': 'separate_governing_clause'}
    if any(start <= m.start() and m.end() <= target.start() for m in cues):
        return {**roles, 'scope': 'attached_in_negative_preamble'}
    return {**roles, 'scope': 'outside_negative_preamble'}
