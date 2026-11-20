"""Recognize an express shared grant to employees and outside contractors."""

import re

from legal_skill_guard.paired_interfaces import cni_employee_permission as employees

EXTERNAL_MEMBER = re.compile(
    r'\b(?:contractors or employees\b|employees\b(?:\s*,\s*(?:officers|directors)\b){0,2}'
    r'\s*(?:,\s*|\s+(?:or|and)\s+)(?:independent consultants|contractors)\b)',
    re.I,
)
PENDING_CONSENT = re.compile(
    r'\b(?:only|subject to|except|after)\b[^.;]{0,75}\b(?:prior written (?:consent|approval)|consent of the discloser)\b',
    re.I,
)
AUDIENCE = re.compile(r'\b(?:only to|except(?: in confidence to such of)?)\s+', re.I)


def proof(spans):
    matches = []
    for path in employees.support(spans):
        text = ' '.join(spans[path['operative']].split())
        if heading := employees.NUMBERED.match(text):
            text = text[heading.end():]
        if path['form'] == 'express_recipient':
            grant = employees.PASSIVE_EMPLOYEES.match(text) or employees.MUTUAL_EXCEPTION.match(text)
        elif path['form'] == 'mutual_exception' and (item := employees.ALPHABETIC.match(text)):
            grant = employees.ANAPHORIC_EXCEPTION.match(text[item.end():])
        else:
            continue
        if grant and not PENDING_CONSENT.search(text):
            introduction = list(AUDIENCE.finditer(grant[0]))
            if not introduction:
                continue
            audience = introduction[-1].end()
            member = EXTERNAL_MEMBER.search(grant.string, audience)
            if member and member.start() < grant.end() and not re.search(r'[;.]', grant.string[audience:member.end()]):
                matches.append(sorted({path['governing'], path['operative']}))
    if len(matches) == 1:
        return {'answer': 'Entailment', 'evidence_sentence_ids': matches[0]}
    return None
