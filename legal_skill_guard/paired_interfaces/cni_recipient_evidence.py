"""Complete a cited recipient permission with its governing span and definition."""

import re

PROTECTED = re.compile(r'\b(?:confidential information|evaluation materials?|the information)\b', re.I)
DECLARATION = re.compile(r'["“]Representatives["”]\s+(?:shall\s+(?:mean|include)|means?|includes?)\b', re.I)
ALIAS = re.compile(r'\(\s*(?:collectively,?\s+)?["“]Representatives["”]\s*\)', re.I)
EMPLOYEES = re.compile(r'\bemployees?\b', re.I)
MENTION = re.compile(r"\b(?:(?:its|their|your|respective)\s+|recipient[’']s\s+)Representatives\b", re.I)
DIRECT = re.compile(
    r'\b(?:may (?:only )?(?:disclose|reveal|share)|may be disclosed|'
    r'undertakes to permit access|will be disclosed only)\b[^.;]{0,235}',
    re.I,
)
BAR_EXCEPT = re.compile(r'\b(?:will|shall) not disclose\b[^.;]{0,200}\bexcept\b[^.;]{0,95}', re.I)
INLINE = re.compile(r'\bto\s+(?:those of\s+)?(?:its|their|your)\s+[^.;]{0,125}\bemployees\b', re.I)
DEFERRED_PERMISSION = re.compile(
    r'\b(?:except with|subject to|only with|after obtaining)\b[^.;]{0,70}\b(?:consent|approval)\b', re.I,
)
SEPARATE_DUTY = re.compile(
    r'\b(?:and|or)\s+(?:(?:shall|will|must|may)\s+)?not\s+(?:disclose|reveal|share)\b', re.I,
)
CHILD = re.compile(r'^\((?P<item>[a-zivx]+)\)\s+', re.I)
DECIMAL = re.compile(r'^(?P<parent>\d+(?:\.\d+)+)\.(?P<child>\d+)\s+to\b')
BARE_AUDIENCE = re.compile(r'^\d+(?:\.\d+)+\s+to each party[’\']s respective Representatives\b', re.I)
EXCEPTION_LEAD = re.compile(r'^the restrictions\b[^;]{0,120}\bdo not apply to the disclosure of\b', re.I)
ACTOR_LEAD = re.compile(
    r'(?:\breceiving party shall\s*:\s*|\brecipient hereby undertakes\s*[:;]\s*|'
    r'^you and your Representatives)\s*$', re.I,
)
ROMAN = ('i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x')


def is_member_definition(text):
    if hit := DECLARATION.search(text):
        return EMPLOYEES.search(text[hit.end():].split(';', 1)[0]) is not None
    if hit := ALIAS.search(text):
        preceding = re.split(r'[.;]', text[:hit.start()])[-1]
        return EMPLOYEES.search(preceding) is not None
    return False


def governing_lead(lines, index, item):
    """Follow an unbroken enumeration beginning at the visible actor."""
    starts = set()
    for sequence in (tuple('abcdefghijklmnopqrstuvwxyz'), ROMAN):
        if item not in sequence:
            continue
        ordinal = sequence.index(item)
        start = index - ordinal - 1
        if start < 0 or not ACTOR_LEAD.search(lines[start]):
            continue
        prior = [CHILD.match(text) for text in lines[start + 1:index]]
        if all(hit and hit['item'].casefold() == want for hit, want in zip(prior, sequence[:ordinal], strict=True)):
            starts.add(start)
    return next(iter(starts)) if len(starts) == 1 else None


def paths(spans):
    """Build evidence paths independently of all model outputs."""
    lines = [' '.join(s.split()) for s in spans]
    definitions = {i for i, text in enumerate(lines) if is_member_definition(text)}
    result = {}
    for i, text in enumerate(lines):
        # A permissions fragment can inherit a numbered exception.
        if (number := DECIMAL.match(text)) and BARE_AUDIENCE.match(text):
            if (i < 2 or lines[i - 2].rstrip('.') != number['parent']
                    or not EXCEPTION_LEAD.search(lines[i - 1]) or not PROTECTED.search(lines[i - 1])):
                continue
            if len(definitions) == 1:
                result[i] = sorted({i - 1, i, *definitions})
            continue

        actor = None
        candidates = [SEPARATE_DUTY.split(match[0], maxsplit=1)[0]
                      for pattern in (DIRECT, BAR_EXCEPT) for match in pattern.finditer(text)]
        if (item := CHILD.match(text)):
            actor = governing_lead(lines, i, item['item'].casefold())
            if actor is None:
                continue
            if text[item.end():].casefold().startswith('only disclose '):
                candidates.append(SEPARATE_DUTY.split(text[item.end():].split(';', 1)[0], maxsplit=1)[0])
        operative = [
            value for value in candidates
            if (INLINE.search(value) or MENTION.search(value)) and not DEFERRED_PERMISSION.search(value)
        ]
        if len(operative) != 1 or not PROTECTED.search(text):
            continue
        clause, = operative
        if re.search(r'\b(?:may|will) be disclosed\b', clause, re.I) and actor is None and not INLINE.search(clause):
            continue
        if MENTION.search(clause) and len(definitions) == 1:
            dependencies = set(definitions)
        elif INLINE.search(clause):
            dependencies = set()
        else:
            continue
        if actor is not None:
            dependencies.add(actor)
        result[i] = sorted({i, *dependencies})
    return result


def complete(native, support):
    """Retain the original decision and add only one verified source chain."""
    if native['answer'] != 'Entailment':
        return native
    current = set(native['evidence_sentence_ids'])
    cited = {tuple(support[i]) for i in current if i in support}
    if len(cited) != 1:
        return native
    chain, = cited
    return {**native, 'evidence_sentence_ids': sorted(current | set(chain))}
