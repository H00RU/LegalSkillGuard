"""Bind MAUD pandemic conditions through explicitly imported preamble clauses."""

import re

from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces import maud_parallel_excerpt as parallel
from legal_skill_guard.paired_interfaces import maud_section_reference as section

TAG = re.compile(r'\(([a-z]{1,5})\)', re.I)
RANGE_IMPORT = re.compile(
    r'^without limiting the foregoing, subject to the exceptions described in clauses '
    r'\((?P<first>[a-z])\) through \((?P<last>[a-z])\) of the foregoing sentence,\s*', re.I,
)
SECTION_IMPORT = re.compile(
    r'^\((?P<target>[a-z])\) subject to the exceptions contained in any of the clauses '
    r'(?P<list>\([ivx]+\)(?:(?:,\s*|\s+(?:and|or)\s+)\([ivx]+\))+)\s+'
    r'of Section (?P<root>\d+\.\d+)\((?P<origin>[a-z])\)', re.I,
)
PANDEMIC_CONDITION = re.compile(
    r'\b(?:pursuant to (?:any )?|(?:respond|in response) to )'
    r'(?:any )?COVID(?:\s*[-–‐]?\s*19)?\s+Measures\b', re.I,
)
NEGATIVE_DUTY = re.compile(r'\b(?:the )?Company(?:\s*:\s*\([ivx]+\))?\s+shall not\b', re.I)
PAGE_DIVIDER = re.compile(r'\b\d{1,3}\s+_{5,}\s*')
NUMERIC_GLOSS = re.compile(r'(?<=[A-Za-z])(?=\([0-9]+\))')


def normalize(text):
    visible = section.normalize(text)
    return ' '.join(NUMERIC_GLOSS.sub(' ', PAGE_DIVIDER.sub(' ', visible)).split())


def exceptions(text, pattern):
    """Extract only outer members of the exception list preceding the duty."""
    duty = anchors.ORDINARY.search(text)
    if duty is None:
        return {}
    prefix = text[:duty.start()]
    start = re.search(r'\bexcept\s+(?=\([a-z])', prefix, re.I)
    if start is None or '<omitted>' in prefix[start.start():]:
        return {}
    prefix = prefix[start.end():]
    depth, spans = 0, []
    for i, char in enumerate(prefix):
        if char == '(':
            if depth == 0 and (tag := TAG.match(prefix, i)) and pattern.fullmatch(tag[1].casefold()):
                spans.append((tag[1].casefold(), i, tag.end()))
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
    if len({tag for tag, _, _ in spans}) != len(spans):
        return {}
    return {name: prefix[left:right] for (name, _, left), (_, right, _) in zip(
        spans, [*spans[1:], ('', len(prefix), 0)], strict=True,
    )}


def compile_import(ordinary, negative):
    """Prove preamble scope, leaving local item exceptions outside this proof."""
    ordinary, negative = map(normalize, (ordinary, negative))
    prefix, gap, tail = negative.rpartition(parallel.OMISSION)
    if not gap:
        return None
    tail = tail.strip()
    is_range = RANGE_IMPORT.match(tail)
    if is_range:
        prefix = prefix.strip()
        if parallel.OMISSION in prefix or ordinary.count(prefix) != 1 or not NEGATIVE_DUTY.search(tail, is_range.end()):
            return None
        start = ordinary.index(prefix)
        visible = ordinary[start:]
        ordinary_items = exceptions(visible, re.compile(r'[a-z]'))
        first, last = ord(is_range['first'].lower()), ord(is_range['last'].lower())
        if first > last:
            return None
        names = [chr(i) for i in range(first, last + 1)]
        form = 'preceding_sentence_range'
    elif (numbered := SECTION_IMPORT.match(tail)) is not None:
        intervals = parallel.align_omissions(negative, ordinary)
        if intervals is None or not NEGATIVE_DUTY.search(tail, numbered.end()):
            return None
        visible = ordinary[intervals[0][0]:intervals[-1][0]]
        header = section.HEADER.match(visible)
        if (header is None or header['number'] != numbered['root']
                or not visible[header.end():].startswith(f'({numbered["origin"].lower()})')
                or numbered['origin'].lower() == numbered['target'].lower()):
            return None
        ordinary_items = exceptions(visible[header.end():], re.compile(r'[ivx]+'))
        names = [name.casefold() for name in TAG.findall(numbered['list'])]
        form = 'section_clause_list'
    else:
        return None
    if not names or len(set(names)) != len(names) or not set(names) <= ordinary_items.keys():
        return None
    pandemic = sorted(name for name, quote in ordinary_items.items() if PANDEMIC_CONDITION.search(quote))
    if not pandemic:
        return None
    return {'form': form, 'accepted_clauses': names, 'pandemic_clauses': pandemic,
            'negative_import_includes_pandemic_condition': bool(set(names) & set(pandemic))}
