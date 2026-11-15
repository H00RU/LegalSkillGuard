"""Positive literal facts for the surface forms seen in actual TRAIN failures.

These records do not invert relationships, classify legal eligibility, use
names as labels, or infer negative facts from an absent mention. Full source
text remains with the task. Unsupported syntax supplies no relation argument.
"""
import re

from .task_roles import explicit_task_roles


NAME = r'[A-Z][a-z]+'
KINSHIP = r'father|mother|son|daughter|spouse|wife|husband'
START = r'(?:^|(?<=[.!?])\s+)'
FAMILY_FORMS = [
    re.compile(START + rf'(?P<owner>{NAME}) has (?:a |an )(?P<relation>{KINSHIP}),? (?P<relative>{NAME})\b'),
    re.compile(START + rf'(?P<owner>{NAME}) has paid \$[\d,]+(?:\.\d+)? to '
               rf'(?:her|his|their) (?P<relation>{KINSHIP}) (?P<relative>{NAME})\b'),
]


def literal_bindings(view):
    public = view.get('public', {})
    values, evidence = {}, []
    question = public.get('question')
    if isinstance(question, str):
        values['current_question'] = question
        evidence.append({'argument': 'current_question', 'field': 'question',
                         'start': 0, 'end': len(question), 'text': question})
    roles = explicit_task_roles(view)
    if roles:
        values.update(roles['arguments'])
        evidence.append({'arguments': sorted(roles['arguments']), 'field': 'question',
            'start': roles['character_range'][0], 'end': roles['character_range'][1],
            'text': roles['literal_text']})
    facts = public.get('facts')
    mentions = []
    if isinstance(facts, str):
        for pattern in FAMILY_FORMS:
            for match in pattern.finditer(facts):
                # has_relative(owner, literal relationship word, relative).
                # "Alice ... her father Bob" is [Alice, father, Bob].
                triple = [match['owner'], match['relation'], match['relative']]
                mentions.append((match.start('owner'), triple))
                evidence.append({'argument': 'case_family_relations', 'value': triple,
                    'field': 'facts', 'start': match.start('owner'), 'end': match.end('relative'),
                    'text': facts[match.start('owner'):match.end('relative')]})
    if mentions:
        values['case_family_relations'] = [t for _, t in sorted(mentions)]
    return {'values': values, 'evidence': evidence,
            'family_relation_semantics': 'has_relative(owner, literal_kinship_word, relative); positive observed mentions only; absence is not a negative fact',
            'legal_conclusions_derived': False}
