"""Link a MAUD carve-out to both covenants through its source section."""

import re


HEADER = re.compile(
    r'^section\s*(?P<number>\d+\.\d+)\.?\s*(?P<heading>[a-z][^<.(]{7,145})\.\s*', re.I
)
SECTION_HEADING = re.compile(r'\b(?i:section)\s+\d+\.\d+\.?\s+[A-Z][A-Za-z ]{8,}\.')
COVID_ACTION = re.compile(r'\bthe taking of any COVID(?:-19)? Action\b', re.I)
EXCEPT = re.compile(r'\bexcept\b', re.I)
ORDINARY = re.compile(r'\bconduct\b[^.;]{0,140}\bordinary course\b', re.I)
NEGATIVE = re.compile(r'\bthe company shall not\b', re.I)
BRANCH = re.compile(r'^\(([a-z])\)\s+', re.I)
NEGATIVE_BRANCH = re.compile(r'\(([b-z])\)\s+without limiting\b', re.I)
OVERRIDE = re.compile(
    r'\bnotwithstanding anything to the contrary contained in section\s+'
    r'(?P<start>\d+\.\d+(?:\([a-z]\))?), nothing in section\s+'
    r'(?P<body>\d+\.\d+(?:\([a-z]\))?) shall prevent the company\b'
    r'(?P<exception>[^;]{1,450}?\bin response to COVID(?:-19)?\b[^;]{0,190}?)'
    r'\band no such [^;]{0,150}?\bshall be deemed to violate or breach section\s+'
    r'(?P<end>\d+\.\d+(?:\([a-z]\))?)\.', re.I
)
RESTRICTED_IMPORT = re.compile(r'\bexcept to the extent any of clauses\b', re.I)


def normalize(text):
    """Remove directional marks and the terminal corpus page notation."""
    text = text.translate(dict.fromkeys(map(ord, '\u200e\u200f\u200b\u00ad'), None))
    text = re.sub(r'\s*\(pages?\s+\d+(?:\s*[-–]\s*\d+)?\)\s*$', '', text, flags=re.I)
    return ' '.join(text.split())


def branch(text, header, formula):
    segment = text[header.end():].strip()
    if segment.startswith('<omitted>'):
        segment = segment[len('<omitted>'):].lstrip()
    item = BRANCH.match(segment)
    if item is None:
        return None
    body = segment[item.end():]
    # A named destination must visibly contain its duty before another
    # lettered clause or an omission.
    match = formula.search(body, 0, min(len(body), 1800))
    if match is None or '<omitted>' in body[:match.start()]:
        return None
    if re.search(r'\([a-z]\)\s+(?:except|the company agrees|the company shall)\b',
                 body[:match.start()], re.I):
        return None
    return item[1].casefold()


def section_override(ordinary, negative, root, positions):
    matches = [list(OVERRIDE.finditer(text)) for text in (ordinary, negative)]
    if any(len(hits) != 1 for hits in matches):
        return None
    a, b = (hits[0] for hits in matches)
    if a[0].casefold() != b[0].casefold():
        return None
    if len({a['start'], a['body'], a['end']}) != 1:
        return None
    target = a['body']
    attached = tuple(role for role, leaf in positions.items() if target in (root, f'{root}({leaf})'))
    if not attached:
        return None
    return {'form': 'whole_section_override' if target == root else 'subsection_override',
            'section': root, 'reference': target, 'targets': attached,
            'ordinary_anchor': [a.start(), a.end()], 'negative_anchor': [b.start(), b.end()]}


def shared_preamble(ordinary, negative, root):
    """Bind a visible exception before the two verified member duties."""
    first = re.search(r'\(a\)\s+the company shall\b', ordinary, re.I)
    prefix, gap, continuation = negative.partition('<omitted>')
    if first is None or not gap:
        return None
    prefix = prefix.strip()
    if re.sub(r'\s+', '', ordinary[:first.start()]).casefold() != re.sub(r'\s+', '', prefix).casefold():
        return None
    cue = COVID_ACTION.search(prefix)
    if cue is None or not EXCEPT.search(prefix, 0, cue.start()):
        return None
    continuation = continuation.strip()
    if NEGATIVE_BRANCH.match(continuation) is None or RESTRICTED_IMPORT.search(continuation):
        return None
    if ordinary.count(continuation) != 1 or not NEGATIVE.search(continuation):
        return None
    location = ordinary.index(continuation)
    if location <= first.end() or SECTION_HEADING.search(ordinary, first.end(), location):
        return None
    if not ORDINARY.search(ordinary, first.end(), min(first.end() + 1250, location)):
        return None
    return {'form': 'shared_visible_preamble', 'section': root, 'reference': root,
            'targets': ('ordinary', 'negative'), 'ordinary_anchor': [0, first.start()],
            'negative_anchor': [0, len(prefix)]}


def attachment(ordinary, negative):
    """Return grounded positive scope, leaving other placements unresolved."""
    ordinary, negative = map(normalize, (ordinary, negative))
    a, b = map(HEADER.match, (ordinary, negative))
    if not a or not b or a['number'] != b['number'] or a['heading'].casefold() != b['heading'].casefold():
        return None
    root = a['number']
    linked = shared_preamble(ordinary, negative, root)
    if linked is not None:
        return linked
    positions = {'ordinary': branch(ordinary, a, ORDINARY), 'negative': branch(negative, b, NEGATIVE)}
    if None in positions.values() or len(set(positions.values())) != 2:
        return None
    return section_override(ordinary, negative, root, positions)
