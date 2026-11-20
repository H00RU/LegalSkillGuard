"""Detect a pandemic proviso that explicitly governs its own covenant only."""

import re

from legal_skill_guard.paired_interfaces import maud_section_reference as section


CUE = re.compile(r'\b(?:COVID(?:\s*[-‐–]?\s*19)?|pandemic|coronavirus|SARS[- ]CoV[- ]2)\b', re.I)
SELF_PROVISO = re.compile(
    r'\bthis Section (?P<root>\d+\.\d+)\((?P<letter>[a-z])\) shall not prohibit\b'
    r'(?P<permission>[^<>;]{1,250}?\bfrom taking\b[^<>;]{1,180}?\bin response to\b[^<>;]{1,225})',
    re.I,
)
SIBLING_DUTY = re.compile(r'\b(?:shall|will)\s+not\s*(?:,|:|and\b|nor\b)', re.I)


def attachment(ordinary_excerpt, negative_excerpt):
    """Bind a visible self-reference without extending it into a sibling preamble."""
    ordinary, negative = map(section.normalize, (ordinary_excerpt, negative_excerpt))
    a, b = map(section.HEADER.match, (ordinary, negative))
    if not a or not b or (a['number'], a['heading'].casefold()) != (b['number'], b['heading'].casefold()):
        return None
    first = section.branch(ordinary, a, section.ORDINARY)
    sibling = section.branch(negative, b, SIBLING_DUTY)
    if first is None or sibling is None or first == sibling:
        return None
    hits = list(SELF_PROVISO.finditer(ordinary, a.end()))
    if len(hits) != 1:
        return None
    (hit,) = hits
    if hit['root'] != a['number'] or hit['letter'].casefold() != first:
        return None
    duty = section.ORDINARY.search(ordinary, a.end(), hit.start())
    if duty is None or '<omitted>' in ordinary[a.end():hit.start()]:
        return None
    if section.SECTION_HEADING.search(ordinary, a.end(), hit.start()):
        return None
    if re.search(rf'\({re.escape(sibling)}\)\s+except\b', ordinary[duty.end():hit.start()], re.I):
        return None
    cues = list(CUE.finditer(ordinary))
    if not cues or any(not hit.start('permission') <= m.start() < hit.end('permission') for m in cues):
        return None
    preamble = negative[b.end():].removeprefix('<omitted>').strip()
    if not preamble.endswith(':') or '<omitted>' in preamble or CUE.search(negative):
        return None
    if re.search(rf'\b{re.escape(a["number"])}\s*\({re.escape(first)}\)', preamble, re.I):
        return None
    return {'ordinary_section': f'{a["number"]}({first})', 'negative_section': f'{a["number"]}({sibling})',
            'ordinary_proviso_range': [hit.start(), hit.end()], 'negative_preamble_shown': True}
