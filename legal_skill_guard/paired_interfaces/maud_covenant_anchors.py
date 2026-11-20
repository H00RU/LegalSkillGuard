"""Bind a pandemic exception readout to visible covenant anchors."""

import re


ORDINARY = re.compile(
    r'\b(?:conduct|carry on|operate|maintain)\b[^;<>]{0,130}?\b(?:in|only in)\s+'
    r'(?:the\s+)?ordinary course(?:\s+of\s+business)?\b', re.I,
)
NEGATIVE = re.compile(
    r'\b(?:(?:shall|will)\s+not(?=\s*:)|'
    r'(?:shall|will)\s+not\s*,?\s*(?:and|or|nor)\s+(?:(?:it|they)\s+)?'
    r'(?:(?:shall|will)\s+)?(?:(?:it|they)\s+)?(?:not\s+)?(?:permit|cause|allow)\b[^:;<>]{0,100}|'
    r'neither\s+[^.;:]{1,90}\bshall\s*,\s*and\s+neither\s+[^.;:]{1,90}\bshall\s+permit\b)', re.I,
)
SECTION = re.compile(
    r'(?<![\w.])(?:Section\s+)?\d+\.\d+\.?\s+[A-Z][A-Za-z][A-Za-z \-’\']{5,100}\.\s*'
)
NO_ADDITIONAL = 'no_additional_anchor'
EXCLUDED = 'excluded'


def inventory(excerpts):
    """Enumerate literal candidate effects in source order without reading references."""
    anchors = {}
    for excerpt, text in excerpts.items():
        headings = tuple(SECTION.finditer(text))
        matches = sorted(
            (hit.start(), family, hit)
            for family, pattern in (('ordinary', ORDINARY), ('negative', NEGATIVE))
            for hit in pattern.finditer(text)
        )
        for start, family, hit in matches:
            heading = next((ref[0].strip() for ref in reversed(headings) if ref.end() <= start), None)
            anchors[f'clause_{len(anchors) + 1}'] = {
                'excerpt': excerpt, 'range': [start, hit.end()], 'quote': hit[0],
                'candidate_family': family, 'preceding_section_heading': heading,
            }
    return anchors


def project(anchors, first, second):
    """Resolve both consumers from one set of bound effects, preserving partial scope."""
    if (first == NO_ADDITIONAL and second != NO_ADDITIONAL) or (first in anchors and first == second):
        return None, None
    families = {anchors[anchor]['candidate_family'] for anchor in (first, second) if anchor in anchors}
    missing = first is None or second is None
    return tuple(True if family in families else None if missing else False
                 for family in ('ordinary', 'negative'))


def check_equivalence(module, consumer):
    """Check the anchor projection against the existing finite local consumer."""
    anchors = {'a': {'candidate_family': 'ordinary'}, 'b': {'candidate_family': 'negative'}}
    translate = {'ordinary_course': 'a', 'negative_interim': 'b', 'other': NO_ADDITIONAL,
                 'no_additional_target_family': NO_ADDITIONAL, None: None}
    for s in module.states:
        targets = [translate[s[field]] for field in ('first_target', 'second_target')]
        present = list(dict.fromkeys(t for t in targets if t in anchors))
        remaining = None if None in targets else NO_ADDITIONAL
        present.extend([remaining] * (2 - len(present)))
        actual = project(anchors, *present)
        expected = consumer(s, {})
        if actual != (expected['governs_ordinary_course'], expected['governs_negative_interim']):
            raise ValueError('Binding a clause must preserve the original local scope and unknowns')
    return len(module.states)
