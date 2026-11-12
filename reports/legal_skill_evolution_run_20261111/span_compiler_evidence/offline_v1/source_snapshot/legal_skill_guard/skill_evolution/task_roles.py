"""Literal role binding for the native employment-query form actually observed.

No family relation, statutory applicability, source ID or native label is
inferred. Other or ambiguous query forms retain an unknown role binding.
"""
import re


EMPLOYMENT = re.compile(r'\bapplies to (?P<employer>[A-Z][a-z]+) employing '
    r'(?P<employee>[A-Z][a-z]+) for (?:the year )?(?P<year>\d{4})\.$')


def explicit_task_roles(view):
    question = view.get('public', {}).get('question')
    if not isinstance(question, str):
        return None
    matches = list(EMPLOYMENT.finditer(question))
    if len(matches) != 1:
        return None
    match = matches[0]
    return {'arguments': {'employer': match['employer'], 'employee': match['employee'],
                          'year': int(match['year'])},
            'source_field': 'question', 'literal_text': match.group(),
            'character_range': [match.start(), match.end()],
            'inferred_legal_or_family_facts': False}
