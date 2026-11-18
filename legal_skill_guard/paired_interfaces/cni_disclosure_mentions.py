"""Exact participant mentions shared by both disclosure interfaces."""

from copy import deepcopy
import re

from legal_skill_guard.paired_interfaces.relational_program import template_version
from legal_skill_guard.skill_evolution.objects import digest

CAPITALIZED_NAME = r"[A-Z][A-Za-z0-9.-]*(?:[ \t]+[A-Z][A-Za-z0-9.-]*){0,5}"
MENTION_PATTERNS = (
    ('explicit_role', re.compile(r'\b(?:receiving|disclosing)[ \t]+part(?:y|ies)\b', re.I)),
    ('named_destination', re.compile(r'\b(?:to|among|by)[ \t]+(?:the[ \t]+)?(' + CAPITALIZED_NAME + r')\b')),
    ('possessive_group', re.compile(r'\b(' + CAPITALIZED_NAME + r")[’']s(?=\s+(?:employees|agents|advisers|advisors|representatives|staff|personnel)\b)")),
    ('group_affiliation', re.compile(r'\b(?:employees|agents|advisers|advisors|representatives|staff|personnel)\s+of\s+(?:the\s+)?(receiving party|disclosing party|' + CAPITALIZED_NAME + r')\b', re.I)),
    ('employee_or_representative', re.compile(r'\b(?:employees?|agents?|advisers?|advisors?|representatives?|personnel|staff)\b', re.I)),
)
MENTION_INSTRUCTIONS = (
    'The input also lists exact participant mentions and their character offsets inside each evidence window. '
    'These are surface occurrences, including multiple different names and roles. '
    'For each disclosure or sharing event, first distinguish who initially gave the information, who received '
    'that information, and whose listed employees could then receive it. In a chained provision, use the same '
    'named recipient when a later possessive group repeats that name. Do not transfer employees from the '
    'first actor to a later recipient. If a listed role or class does not settle the binding, keep it unknown.'
)


def mention_windows(text, ranges):
    """Index literal mentions only, including distractors and nonemployees."""
    windows = []
    for anchor, (start, end) in ranges.items():
        excerpt = text[start:end]
        mentions = []
        for kind, pattern in MENTION_PATTERNS:
            for match in pattern.finditer(excerpt):
                first, last = match.span(match.lastindex or 0)
                mentions.append({'kind': kind, 'start': start + first, 'end': start + last,
                                 'text': text[start + first:start + last]})
        if mentions:
            windows.append({'id': anchor, 'mentions': sorted(mentions, key=lambda row: (
                row['start'], row['end'], row['kind']))})
    return windows


def with_mentions(view):
    scoped = deepcopy(view)
    source = scoped['relational_public_source']
    mentions = mention_windows(source['source_text'], source['indexed_ranges'])
    if not mentions:
        raise ValueError('This source has no lexical participant matches to align')
    scoped['read_input']['participant_mentions'] = mentions
    for plan in scoped['plans']:
        previous = plan['reader_template_sha256']
        plan['system'] += '\n' + MENTION_INSTRUCTIONS
        plan['reader_template_sha256'] = template_version(
            plan['relational_program'], system=plan['system'], public_rules=previous,
            protocol='exact_participant_mention_inventory_v1',
        )
        plan['name'] += '_participant_mentions'
        plan['version'] = digest({key: value for key, value in plan.items() if key != 'version'})
    return scoped
