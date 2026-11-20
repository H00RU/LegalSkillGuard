"""Classify the source visibility of MAUD negative-covenant witnesses."""

import re

from legal_skill_guard.paired_interfaces.maud_parallel_excerpt import align_omissions
from legal_skill_guard.paired_interfaces.maud_section_reference import HEADER
from legal_skill_guard.paired_interfaces.maud_selective_import import exceptions, normalize

HEADING = re.compile(
    r'\b(?:(?i:section)\s+)?(?P<number>\d+\.\d+)\.?\s+'
    r'(?P<title>[A-Z][A-Za-z][A-Za-z ,’\-]{4,90})\.'
)
LOAN_PROVISO = re.compile(
    r'\(it being understood that modifications of such loans consistent with regulatory '
    r'[^;<>]{1,120}? guidelines[^;<>]{0,120}? shall not be a violation of this Section '
    r'(?P<section>\d+\.\d+)\((?P<subsection>[a-z])\)\)', re.I,
)
BRANCH_CLOSURE = re.compile(
    r'\bopen or close any,?\s+branch or automated banking facility,\s*except for such temporary closures'
    r'[^;<>]{1,400}?(?=;)', re.I,
)
ACCESS_LIMIT = re.compile(
    r'\bafford\b[^;<>]{1,220}?,\s*access,\s*subject to any reasonable restrictions[^;<>]{1,220}?'
    r'with respect to in-person access in light of [^;<>]{1,80}? concerns\b', re.I,
)
ROMAN = re.compile(r'[ivx]+')


def containing(pattern, text, left, right):
    return next((match for match in pattern.finditer(text) if match.start() <= left and right <= match.end()), None)


def local_scope(text, left, right):
    """Resolve a scoped local item or a distinct affirmative access duty."""
    heading = next(reversed(list(HEADING.finditer(text, 0, left))), None)
    if heading is None:
        return None
    if match := containing(LOAN_PROVISO, text, left, right):
        body = text[heading.end():match.start()]
        if (match['section'] == heading['number']
                and re.search(r'\(' + match['subsection'] + r'\)\s+(?:except|without limiting)\b', body, re.I)
                and re.search(r'\bplace on non-accrual any Company Loans\b[^;<>]{1,180}$', body, re.I)):
            return 'local_loan_modification', match.span()
    if (heading['title'].casefold() == 'negative covenants'
            and (match := containing(BRANCH_CLOSURE, text, left, right)) is not None):
        return 'local_branch_closure', match.span()
    if (heading['title'].casefold() == 'current information'
            and (match := containing(ACCESS_LIMIT, text, left, right)) is not None):
        return 'separate_access_duty', match.span()
    return None


def outside_native_excerpt(normalized, target, context, cue, numbered):
    """Bind a sibling-only cue relative to an exactly aligned target excerpt."""
    intervals = align_omissions(target, normalized)
    if intervals is None or cue in target or normalized.count(context) != 1 or context.count(cue) != 1:
        return 'cross_excerpt_unresolved'
    left = normalized.index(context)
    if left >= intervals[-1][1]:
        return 'beyond_task_excerpt'
    preamble = normalized[intervals[0][0]:intervals[-1][0]]
    if (header := HEADER.match(preamble)) is not None:
        clauses = exceptions(preamble[header.end():], ROMAN)
        cue_loc = left + context.index(cue)
        for name in set(numbered['pandemic_clauses']) - set(numbered['accepted_clauses']):
            phrase = clauses.get(name)
            if phrase and normalized.count(phrase) == 1:
                start = normalized.index(phrase)
                if start <= cue_loc and cue_loc + len(cue) <= start + len(phrase):
                    return 'preamble_clause_not_imported'
    return 'cross_excerpt_unresolved'


def inventory(public, selective_import):
    """Distinguish the original task excerpt from a condition seen in its sibling."""
    excerpts = public['original_excerpts']
    target = public['task_excerpts']['negative']
    normalized = {key: normalize(text).casefold() for key, text in excerpts.items()}
    numbered_exclusion = (selective_import is not None
                           and not selective_import['negative_import_includes_pandemic_condition'])
    result = {}
    for name, marker in public['focus_markers'].items():
        source = marker['excerpt']
        text = excerpts[source]
        left, right = marker['range']
        context = normalize(text[max(0, left - 72):right + 72]).casefold()
        cue = text[left:right]
        if cue != marker['cue']:
            raise ValueError('The focus marker must name its exact source occurrence')
        if source == target or context in normalized[target]:
            attachment = local_scope(text, left, right)
            kind, span = attachment if attachment is not None else ('in_task_excerpt', None)
        elif numbered_exclusion and selective_import['form'] == 'section_clause_list':
            kind, span = outside_native_excerpt(normalized[source], normalized[target],
                                                context, normalize(cue).casefold(), selective_import), None
        else:
            kind, span = 'cross_excerpt_unresolved', None
        result[name] = {'placement': kind, 'span': span, 'excerpt': source}
    return result


def require_visible_witness(answer, evidence):
    """Withhold an unsupported positive, preserving unresolved coverage."""
    witness = evidence.get(answer['focus'])
    if (answer['answer'] == 'Yes' and witness is not None and witness['placement'] in
            ('separate_access_duty', 'preamble_clause_not_imported', 'beyond_task_excerpt')):
        return {'answer': None, 'focus': None}
    return answer
