"""Bind disclosure permission to employees of the receiving party."""

import re

from legal_skill_guard.paired_interfaces import cni_recipient_evidence as recipient

ACTOR = r'(?:the )?(?:recipient|receiving party)'
OBJECT = r'(?:the |such )?confidential information'
OWN_EMPLOYEES = rf"(?:{ACTOR}[’']s|its) employees?\b"
NUMBERED = re.compile(r'^(?P<clause>\d+(?:\.\d+)*)(?:\.)?(?=\s|$)\s*')
ALPHABETIC = re.compile(r'^\((?P<item>[a-z])\)\s+', re.I)
ACTIVE_LIST = re.compile(rf'\b{ACTOR} may(?: only)? disclose {OBJECT} to\s*:$', re.I)
LIST_EMPLOYEES = re.compile(rf'^(?:to\s+)?{OWN_EMPLOYEES}', re.I)
LIMITED_ACCESS = re.compile(r'\b(?:strict )?need to know\b', re.I)
LIST_PROHIBITION = re.compile(r'\b(?:shall|may|must|will) not\b|\bare prohibited from\b', re.I)
MUTUAL_LEAD = re.compile(
    rf"\beach party undertakes in relation to the other party[’']s {OBJECT}\s*:$", re.I,
)
ANAPHORIC_EXCEPTION = re.compile(
    rf'^not to disclose the same\b[^.;:]{{0,180}}\bexcept in confidence to such of {OWN_EMPLOYEES}',
    re.I,
)
MUTUAL_EXCEPTION = re.compile(
    rf'^neither party shall disclose {OBJECT} received from the other\b[^.;:]{{0,140}},\s*'
    rf'except {OWN_EMPLOYEES}', re.I,
)
PASSIVE_EMPLOYEES = re.compile(
    rf'^{OBJECT} may be disclosed only to (?:employees(?: or contractors)?|contractors or employees) '
    rf'of {ACTOR}\b', re.I,
)
CONSENT = re.compile(
    r'\b(?:prior (?:written )?(?:consent|approval)|subject to (?:the )?approval)\b', re.I,
)


def numbered_parent(texts, index, clause):
    """Only inherit from the same numbered list and its immediate governing clause."""
    parent, _, child = clause.rpartition('.')
    if not parent or not child:
        return None
    for before in range(index - 1, -1, -1):
        heading = NUMBERED.match(texts[before])
        if not heading:
            continue
        label = heading['clause']
        if label == parent:
            body = texts[before][heading.end():]
            return before if ACTIVE_LIST.search(body) and not CONSENT.search(body) else None
        if not label.startswith(parent + '.'):
            break
    return None


def mutual_parent(texts, index, item):
    """Resolve “the same” through an ordered series under the confidentiality lead."""
    siblings = []
    for before in range(index - 1, -1, -1):
        text = texts[before]
        if MUTUAL_LEAD.search(text):
            want = [chr(code) for code in range(ord('a'), ord(item))]
            return before if siblings[::-1] == want else None
        if NUMBERED.match(text):
            break
        if match := ALPHABETIC.match(text):
            letter = match['item'].lower()
            if letter not in 'ivx':
                siblings.append(letter)
    return None


def support(spans):
    """Return complete source witnesses for four express employee-permission forms."""
    texts = [' '.join(span.split()) for span in spans]
    existing = recipient.paths(texts)
    found = []
    for index, text in enumerate(texts):
        heading = NUMBERED.match(text)
        body = text[heading.end():] if heading else text
        if CONSENT.search(body.split(';', 1)[0]):
            continue
        if PASSIVE_EMPLOYEES.match(body) or MUTUAL_EXCEPTION.match(body):
            path = {'form': 'express_recipient', 'operative': index, 'governing': index}
        elif (heading and LIST_EMPLOYEES.match(body) and LIMITED_ACCESS.search(body)
              and not LIST_PROHIBITION.search(body)):
            parent = numbered_parent(texts, index, heading['clause'])
            path = {'form': 'numbered_permission', 'operative': index, 'governing': parent}
        elif ((alpha := ALPHABETIC.match(body)) and alpha['item'].lower() in 'abc'
              and ANAPHORIC_EXCEPTION.match(body[alpha.end():])):
            parent = mutual_parent(texts, index, alpha['item'].lower())
            path = {'form': 'mutual_exception', 'operative': index, 'governing': parent}
        else:
            continue
        if path['governing'] is not None and index not in existing:
            found.append(path)
    return found


def project(native, paths):
    """Provide the same complete, unambiguous source proof to each reader."""
    if len(paths) != 1:
        return native
    witness, = paths
    return {**native, 'answer': 'Entailment',
            'evidence_sentence_ids': sorted({witness['operative'], witness['governing']})}
