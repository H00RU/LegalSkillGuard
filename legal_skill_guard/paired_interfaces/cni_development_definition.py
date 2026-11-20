"""Keep defined categories of information outside the independent-work route."""

import re

from legal_skill_guard.paired_interfaces.cni_independent_development import WORK_CUE, proof as prior_proof


DEFINITION = re.compile(
    r"""^(?:\d+[.)]\s*)?(?:as used herein,\s*)?[“"']?confidential information[”"']?\s+"""
    r"(?:shall mean|means)\b", re.I,
)
DEFINED_DATA = re.compile(r'^\d+[.)]\s+[\w ]+\s+data:\s+data in any format\b', re.I)
PLAN = re.compile(r'\bdevelopment plans\b', re.I)
DATA_ORIGIN = re.compile(r'\bcollected,\s*developed,\s*maintained,\s*or managed\b', re.I)
OPERATIVE = re.compile(r'\b(?:may|can|permitted|allowed|entitled|authorized|shall not|right to)\b', re.I)


def definition_only(clause):
    """Accept a category description with one development cue inside its object."""
    match = PLAN.search(clause) if DEFINITION.match(clause) else (
        DATA_ORIGIN.search(clause) if DEFINED_DATA.match(clause) else None)
    cues = list(WORK_CUE.finditer(clause))
    return bool(match and not OPERATIVE.search(clause) and len(cues) == 1
                and match.start() <= cues[0].start() < cues[0].end() <= match.end())


def proof(spans, full_text):
    clauses = [' '.join(clause.split()) for clause in spans]
    if sum(len(WORK_CUE.findall(clause)) for clause in clauses) < len(
            WORK_CUE.findall(' '.join(full_text.split()))):
        return None
    ignored = [index for index, clause in enumerate(clauses) if definition_only(clause)]
    if not ignored:
        return None
    filtered = [clause if index not in ignored else '' for index, clause in enumerate(clauses)]
    result = prior_proof(filtered, ' '.join(filtered))
    if result is None or result['kind'] != 'no_work_route_cue':
        return None
    return {**result, 'kind': 'development_in_definition_only', 'definition_spans': ignored}
