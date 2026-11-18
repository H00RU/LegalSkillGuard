"""Bind OpenExempt claim citations to the input's supplied jurisdiction premise."""

import re

from legal_skill_guard.rr.source_structure import CITATION


PREFIX_BY_JURISDICTION = {
    'Arizona': 'Ariz. Rev. Stat. ',
    'Federal': '11 U.S.C. ',
    'Illinois': '735 Ill. Comp. Stat. ',
    'Oregon': 'Or. Rev. Stat. ',
    'Pennsylvania': '42 Pa. Cons. Stat. ',
    'Wisconsin': 'Wis. Stat. ',
}
PREMISE = re.compile(r'^The Debtors? may claim property exemptions under ([A-Za-z ]+) statutes\.$', re.M)
PUBLIC_SCOPE_INSTRUCTIONS = (
    'Use the exemptions only from the jurisdictions explicitly supplied in the resolved public premise. '
    'The allowed citation enum is the intersection of those jurisdictions with the provided statute text. '
    'This enum restricts the search space. Determine applicability per asset and compute the claim amounts.'
)


def supplied_jurisdiction_scope(original_input):
    """Recover the unique solved jurisdiction premise and its literal citation vocabulary."""
    _, has_statutes, statutes = original_input.partition('\nStatutes:\n')
    statutes, has_solved, remainder = statutes.partition('\nSolved Reasoning Steps:\n')
    solved, has_facts, _ = remainder.partition('\nFacts:\n')
    if not (has_statutes and has_solved and has_facts):
        return None
    premises = list(PREMISE.finditer(solved))
    if len(premises) != 1:
        return None
    premise, = premises
    names = premise.group(1).split(' and ')
    if len(set(names)) != len(names) or any(name not in PREFIX_BY_JURISDICTION for name in names):
        return None
    prefixes = tuple(PREFIX_BY_JURISDICTION[name] for name in names)
    supplied = set(CITATION.findall(statutes))
    if not all(any(citation.startswith(prefix) for citation in supplied) for prefix in prefixes):
        return None
    return {'premise': premise.group(0),
            'citations': sorted(citation for citation in supplied if citation.startswith(prefixes))}


def bound_jurisdiction_citations(public):
    scope = public.get('supplied_jurisdiction_scope')
    if scope is None:
        return None
    if scope != supplied_jurisdiction_scope(public['original_input']):
        raise ValueError('The citation scope must come from the original public premise and statutes')
    return scope['citations']
