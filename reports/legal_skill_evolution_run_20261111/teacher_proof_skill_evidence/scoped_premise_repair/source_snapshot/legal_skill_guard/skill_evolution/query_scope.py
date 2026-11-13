"""Literal query arguments, separate from factual or legal propositions.

Only observed unambiguous native forms are recognized. These selectors never
extract the asserted amount, infer a relationship, or decide eligibility.
"""
import re

from .task_roles import explicit_task_roles

NAME = r'[A-Z][a-z]+'
YEAR = re.compile(r'\b(?:for|in)\s+(?:the\s+year\s+)?(?P<year>\d{4})\b', re.I)
DEPENDENT = re.compile(r'^(?P<taxpayer>'+NAME+r') can claim an exemption with '
    r'(?P<individual>'+NAME+r') the dependent for (?P<year>\d{4}) under ')
CHILD = re.compile(r'(?:^|,\s+)(?P<individual>'+NAME+r') is a qualifying child of '
    r'(?P<taxpayer>'+NAME+r') for (?:the year )?(?P<year>\d{4})\b')
SUBJECT = [
    re.compile(r'\b(?P<subject>'+NAME+r")[’']s\s"),
    re.compile(r'\b(?:for|to) (?P<subject>'+NAME+r') (?:for|in) (?:the year )?\d{4}\b'),
]


def literal_query_arguments(question):
    values, evidence = {}, []

    def add(name, value, start, end):
        values[name] = value
        evidence.append({'argument': name, 'value': value, 'field': 'question',
                         'start': start, 'end': end, 'text': question[start:end]})

    matches = list(YEAR.finditer(question))
    if matches and len({m['year'] for m in matches}) == 1:
        m = matches[0]
        add('year', int(m['year']), m.start('year'), m.end('year'))
    dependent = DEPENDENT.match(question) or CHILD.search(question)
    if dependent:
        for name in ('taxpayer', 'individual'):
            add(name, dependent[name], dependent.start(name), dependent.end(name))
    else:
        candidates = [m for pattern in SUBJECT for m in pattern.finditer(question)]
        if candidates and len({m['subject'] for m in candidates}) == 1:
            m = candidates[0]
            add('subject', m['subject'], m.start('subject'), m.end('subject'))
    existing = explicit_task_roles({'public': {'question': question}})
    if existing:
        for name, value in existing['arguments'].items():
            if name not in values:
                add(name, value, *existing['character_range'])
    return {'values': values, 'evidence': evidence,
            'case_or_legal_propositions_inferred': False}
