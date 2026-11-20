"""Bind independent work to its own exception without confusing prior knowledge."""

import re


EXCEPTION = re.compile(
    r"(?:\b(?:the receiving party[’']s )?obligations\b[^.;]{0,130}"
    r"\b(?:do|shall|will) not (?:apply|extend)\b[^.;]{0,100}\binformation\b|"
    r"\b(?:confidential information|the information)\b[^.;]{0,100}"
    r"\b(?:does not include|shall not include|shall exclude)\b)"
    r"[^.;]{0,55}$", re.I
)
ITEM = re.compile(r'^\((?:[a-z]+|\d+)\)\s+', re.I)
RECEIVER = r'(?:the )?(?:receiving party|recipient)'
INDEPENDENT_WORK = re.compile(
    rf'\b(?:independently\s+(?:developed|derived)\s+by\s+(?:or\s+for\s+)?{RECEIVER}\b|'
    rf'developed by {RECEIVER}\s+(?:completely\s+)?independently\b|'
    rf'developed by {RECEIVER}\s+without (?:reference to|(?:the )?use of|reliance on)\s+'
    r'(?:(?:any|the|such)\s+)?(?:confidential information|information disclosed)\b)', re.I
)
TIME_LIMIT = re.compile(
    r'\b(?:at or prior to|prior to|before)\s+(?:the time of\s+)?(?:its\s+)?(?:disclosure|receipt)\b', re.I
)
WORK_CUE = re.compile(
    r'\b(?:develop\w*|independen\w*|(?:creat\w*|generat\w*|deriv\w*|prepar\w*|produc\w*)'
    r'[^.;]{0,140}without (?:any |the )?(?:reference|use|using|reliance|relying))\b', re.I
)
TITLE = re.compile(r'^director\s*[-–]\s*corporate development and investor relations$', re.I)
SEVERABILITY = re.compile(r'\b(?:deemed to be|shall be held)\s+independent and severable\b', re.I)


def proof(spans, full_text):
    """Allow a linked affirmative witness or a conservative no-route condition."""
    clauses = [' '.join(s.split()) for s in spans]
    if sum(len(WORK_CUE.findall(t)) for t in clauses) < len(WORK_CUE.findall(' '.join(full_text.split()))):
        return None
    live, past_only, ambiguous = [], [], []
    header = None
    for i, clause in enumerate(clauses):
        item = ITEM.match(clause)
        if not item and clause:
            header = i if EXCEPTION.search(clause) else None
        if not WORK_CUE.search(clause):
            continue
        if TITLE.fullmatch(clause) or (SEVERABILITY.search(clause) and len(WORK_CUE.findall(clause)) == 1):
            continue
        if item and header is not None and INDEPENDENT_WORK.search(clause):
            path = [header, i]
            (past_only if TIME_LIMIT.search(clause) else live).append(path)
        else:
            ambiguous.append(i)
    if live:
        return {'kind': 'linked_independent_work', 'answer': 'Entailment',
                'evidence_sentence_ids': sorted({i for path in live for i in path})}
    if ambiguous:
        return None
    return {'kind': 'before_disclosure_only' if past_only else 'no_work_route_cue', 'answer': 'NotMentioned',
            'evidence_sentence_ids': [], 'past_only': past_only}
