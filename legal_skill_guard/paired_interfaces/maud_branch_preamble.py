"""Verify an express pandemic condition confined to its own covenant preamble."""

import re

from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces import maud_section_reference as section

HEADER = re.compile(
    r'^(?:Section\s+)?(?P<root>\d+\.\d+)\.?\s+'
    r'(?P<heading>[^<.(]{6,120}?)\.\s+(?=\(|<omitted>)', re.I,
)
SIBLING = re.compile(r'^\(([a-z])\)\s*except\b', re.I)
PANDEMIC = re.compile(r'\b(?:COVID(?:[\s‐–-]*19)?|pandemic|coronavirus)\b', re.I)
CONDITION = re.compile(
    r'\b(?:respond to|in response to|(?:required to )?comply with)\s+COVID(?:[\s‐–-]*19)?\b|'
    r'\b(?:required by )?applicable Law\s*,?\s*\(including any COVID(?:[\s‐–-]*19)?\b',
    re.I,
)
IMPORT = re.compile(
    r'\b(?:without limiting|subject to|incorporat\w*|contained in|referred to|exceptions? in|foregoing)\b',
    re.I,
)
EXPLICIT_REFERENCE = re.compile(
    r'\b(?:section|subsection|clause|paragraph)\s+(?:\d+|\([a-zivx]+\)|[a-z]\b)', re.I,
)
GOVERNING_NEGATIVE = re.compile(r'\bshall not\s*,\s*and shall not permit\b', re.I)


def attachment(ordinary, negative):
    """Resolve two sibling preambles from their printed boundaries and references."""
    ordinary, negative = map(section.normalize, (ordinary, negative))
    a, b = HEADER.match(ordinary), HEADER.match(negative)
    if not a:
        return None
    ordinary_clause = ordinary[a.end():]
    ordinary_branch = SIBLING.match(ordinary_clause)
    negative_clause = negative
    if b:
        if (a['root'], a['heading'].casefold()) != (b['root'], b['heading'].casefold()):
            return None
        negative_clause = negative[b.end():].removeprefix('<omitted>').strip()
    negative_branch = SIBLING.match(negative_clause)
    if not ordinary_branch or not negative_branch or ordinary_branch[1] == negative_branch[1]:
        return None

    root = a['root']
    sibling_ref = re.compile(rf'\bSchedule\s+{re.escape(root)}\s*\({negative_branch[1]}\)', re.I)
    if not b and not sibling_ref.search(negative_clause):
        return None
    if '<omitted>' in negative_clause or PANDEMIC.search(negative_clause) or not negative_clause.endswith(':'):
        return None

    ordinary_duty = anchors.ORDINARY.search(ordinary_clause)
    negative_duty = GOVERNING_NEGATIVE.search(negative_clause)
    if ordinary_duty is None or negative_duty is None:
        return None
    preamble = ordinary_clause[:ordinary_duty.start()]
    if '<omitted>' in preamble or section.SECTION_HEADING.search(preamble) or not CONDITION.search(preamble):
        return None
    independent = sibling_ref.sub('the sibling schedule', negative_clause)
    if IMPORT.search(independent) or EXPLICIT_REFERENCE.search(independent):
        return None
    if re.search(rf'\b{re.escape(root)}\s*\({ordinary_branch[1]}\)', independent, re.I):
        return None

    return {
        'ordinary_section': f'{root}({ordinary_branch[1]})',
        'negative_section': f'{root}({negative_branch[1]})',
        'answer': {'ordinary': 'Yes', 'negative': 'No'},
    }
