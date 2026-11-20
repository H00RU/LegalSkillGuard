"""Source anchors for constructive knowledge in a single operative definition."""

import re


# The triggering action and the inquiry object must be contiguous. Phrases
# such as "without further investigation" do not cancel an earlier inquiry.
INQUIRY = re.compile(
    r'\b(?:after|following|upon|assuming)\s+'
    r'(?:(?:having\s+(?:made|conducted|undertaken)|making|conducting|undertaking)\s+)?'
    r'(?:reasonable due|due|reasonable)\s+(?:inquiry|investigation)\b', re.I,
)
INQUIRY_DENIAL = re.compile(
    r'\b(?:not|without|never|no|except)\b(?:(?:\s+\w+){0,3})\s*$', re.I,
)
KNOWN_DISJUNCTION = re.compile(
    r'\b(?:means|shall mean)\s+(?:only\s+)?(?:(?:those|the|any)\s+)?'
    r'(?:facts|matters|information)\s+that\s+(?:are|were)\s+(?:actually\s+)?known\s+'
    r'or\s+should\s+(?:reasonably\s+)?have\s+been\s+known\b', re.I,
)
DEEMING = re.compile(
    r'\b(?P<actor>such\s+(?:individual|person)|each\s+such\s+(?:individual|person))\b'
    r'[^.!?;]{0,250}\bshall\s+be\s+deemed\s+to\s+have\s+knowledge\b'
    r'[^.!?;]{0,240}\bif\b[^.!?;]{0,240}\bsuch\s+(?:individual|person)\s+'
    r'should\s+(?:reasonably\s+)?have\s+known\b', re.I,
)


def positive_effect(definition):
    """Find a visible imputation or inquiry with its local qualifier intact."""
    for form, pattern in (('imputation_in_definition', KNOWN_DISJUNCTION), ('deeming_of_listed_people', DEEMING)):
        match = pattern.search(definition)
        if match and '<omitted>' not in match[0]:
            return {'form': form, 'span': [match.start(), match.end()]}
    for match in INQUIRY.finditer(definition):
        before = re.split(r'[,;:()]', definition[max(0, match.start() - 55):match.start()])[-1]
        if INQUIRY_DENIAL.search(before):
            continue
        return {'form': 'mandatory_inquiry', 'span': [match.start(), match.end()]}
    return None
