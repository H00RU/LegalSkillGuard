"""Bind the printed COVID qualification in each of two separate company preambles."""

import re

from legal_skill_guard.paired_interfaces import maud_branch_preamble as branch
from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces.maud_section_reference import normalize


QUALIFICATION = re.compile(r'\bby applicable Law \(including any COVID-19 Measures?\)', re.I)
COMPANY = re.compile(r'\b(?:the )?Company shall\b', re.I)
NEGATIVE_ENTRY = re.compile(r'\(b\)\s+Except\b', re.I)


def proof(ordinary, negative):
    """Require the company's own two visible preambles under the same section."""
    ordinary, negative = (normalize(text) for text in (ordinary, negative))
    left, right = (branch.HEADER.match(text) for text in (ordinary, negative))
    if (left is None or right is None or left['root'] != right['root']
            or left['heading'].casefold() != right['heading'].casefold()
            or 'parent' in left['heading'].casefold() or 'company' not in left['heading'].casefold()):
        return None
    lead = ordinary[left.end():]
    if not lead.casefold().startswith('(a) except '):
        return None
    duty = anchors.ORDINARY.search(lead)
    if duty is None or not COMPANY.search(lead, 0, duty.start()):
        return None
    end_of_governor = left.end() + duty.end()
    if not negative.startswith(ordinary[:end_of_governor]):
        return None
    affirmative = lead[:duty.start()]
    if ('<omitted>' in affirmative or NEGATIVE_ENTRY.search(affirmative)
            or QUALIFICATION.search(affirmative) is None):
        return None
    second = NEGATIVE_ENTRY.search(negative, end_of_governor)
    if second is None or anchors.SECTION.search(negative, end_of_governor, second.start()):
        return None
    limiter = anchors.NEGATIVE.search(negative, second.end(), min(len(negative), second.end() + 800))
    if limiter is None or not COMPANY.search(negative, second.end(), limiter.end()):
        return None
    prohibitive = negative[second.end():limiter.start()]
    if ('<omitted>' in prohibitive or anchors.SECTION.search(prohibitive)
            or QUALIFICATION.search(prohibitive) is None):
        return None
    return {'section': left['root'], 'answer': {'ordinary': 'Yes', 'negative': 'Yes'},
            'ordinary_preamble': [left.end(), left.end() + duty.start()],
            'negative_preamble': [second.start(), limiter.end()]}
