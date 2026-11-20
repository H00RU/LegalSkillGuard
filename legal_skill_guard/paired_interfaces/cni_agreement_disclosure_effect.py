"""Recognize source-bound bars on disclosing an NDA or participation in its talks."""

import re


AGREEMENT_AS_SUBJECT = re.compile(
    r'^(?:(?:\d+|[a-z])[.)]\s*)?this agreement'
    r'(?:\s+(?:itself|and\s+each additional agreement\b[^.;]{0,145}))?,?\s+'
    r'(?:shall|must|will) be kept confidential\b'
    r'[^.;]{0,160}\b(?:is|shall|must|will) not to be (?:reproduced|communicated|distributed|disclosed)\b',
    re.I,
)
PROMISE_BAR = re.compile(
    r'\b(?:agrees?|undertakes?)\b[^.;]{0,145}\bnot to\s+'
    r'(?:announce|publicize|disclose)(?:\s+or\s+(?:announce|publicize|disclose))?\b'
    r'[^.;]{0,95}\b(?:its|their|the party[’\']s)\s+participation\s+in\s+'
    r'(?:discussions|negotiations)\b[^.;]{0,145}\b(?:this agreement|hereunder)\b',
    re.I,
)
NEGATION = re.compile(
    r'\b(?:not (?:required|obligated)|does not prohibit|nothing (?:shall |will )?prevent)\b',
    re.I,
)
OTHER_CONTRACT = re.compile(r'\b(?:instead of this agreement|the other agreement|a separate agreement)\b', re.I)


def explicit_bar(spans):
    """Find an operative object and prohibition in the same source span."""
    for index, span in enumerate(spans):
        clause = ' '.join(span.split())
        if NEGATION.search(clause) or OTHER_CONTRACT.search(clause):
            continue
        if AGREEMENT_AS_SUBJECT.search(clause):
            return {'answer': 'Entailment', 'evidence_sentence_ids': [index], 'form': 'bar_on_agreement_itself'}
        if PROMISE_BAR.search(clause):
            return {'answer': 'Entailment', 'evidence_sentence_ids': [index], 'form': 'bar_on_participation_in_talks'}
    return None
