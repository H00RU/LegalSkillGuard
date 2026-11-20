"""Original confidentiality qualification through an express unmarked route."""

import re


DEFINITION = re.compile(
    r'\bconfidential information[”\'"]?\s*(?:,\s*whenever used in this agreement,\s*)?'
    r'(?:(?:shall|will|also)\s+)?(?:mean(?:s)?|include(?:s)?|may include)\b',
    re.I,
)
ORDINAL = re.compile(r'^\((?:[a-z]|[ivx]+)\)\s+', re.I)
UNMARKED_QUALIFIES = re.compile(
    r'\binformation\b[^.;]{0,120}\b(?:does not bear|not marked with|is not marked with)\b'
    r'[^.;]{0,110}\b(?:legends?|markings?)\b[^.;]{0,200}'
    r'\b(?:shall|will)\s+(?:nevertheless\s+)?be\s+(?:protected|treated)\s+'
    r'(?:hereunder\s+)?as\s+confidential information\b',
    re.I,
)
OPEN_RECOGNITION = re.compile(
    r'\bor\s+(?:(?:is\s+)?clearly intended to be disclosed in confidence|'
    r'otherwise disclosed in a manner consistent with its proprietary and confidential nature|'
    r'from all the relevant circumstances should reasonably be assumed by receiving party to be confidential|'
    r'(?:ought to be considered|should be deemed)\s+(?:by its nature to be\s+)?confidential'
    r'(?:\s+(?:from|by)\s+(?:its|their)\s+nature|\s+from (?:all )?the circumstances)?)\b',
    re.I,
)
SAME_CLAUSE_CONFIDENCE = re.compile(
    r'\b(?:treated as confidential|designated as confidential information|'
    r'marked (?:as )?[“\'"]?(?:confidential|proprietary))\b', re.I,
)
NATURE_DESCRIPTION = re.compile(
    r'\bconfidential information\b.*\bregardless of the form\b.*\bmay include\b'
    r'.*\b(?:would|should) reasonably be deemed to be confidential\b', re.I,
)
EXPLICIT_INDEPENDENCE = re.compile(
    r'\bshall apply to all confidential information\b.*'
    r'\bwhether or not it is designated as [“\'"]?confidential\b', re.I,
)


def alternative_route(spans):
    """Return the original span IDs establishing one qualifying open path."""
    clauses = [' '.join(s.split()) for s in spans]
    for i, current in enumerate(clauses):
        if any(rule.search(current) for rule in (UNMARKED_QUALIFIES, NATURE_DESCRIPTION, EXPLICIT_INDEPENDENCE)):
            return {'evidence_sentence_ids': [i], 'form': 'unmarked_information_qualifies'}
        open_route = OPEN_RECOGNITION.search(current)
        if not open_route or not SAME_CLAUSE_CONFIDENCE.search(current, 0, open_route.start()):
            continue
        if DEFINITION.search(current):
            return {'evidence_sentence_ids': [i], 'form': 'designation_or_context'}
        if ORDINAL.match(current):
            head = i - 1
            while head >= 0 and ORDINAL.match(clauses[head]):
                head -= 1
            if head >= 0 and DEFINITION.search(clauses[head]) and clauses[head].endswith((':', 'communications')):
                return {'evidence_sentence_ids': [head, i], 'form': 'contextual_definition_subclause'}
    return None
