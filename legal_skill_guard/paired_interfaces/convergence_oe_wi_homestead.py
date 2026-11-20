"""Resolve the benchmark's supplied Wisconsin homestead scope and cap."""

import re

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


CITATION = 'Wis. Stat. § 815.20(1)'
SINGLE_CAP_CENTS = 7_500_000
OPENING = (
    'An exempt homestead selected by a resident owner and occupied by him or her shall be exempt from '
    'execution, from the lien of every judgment, and from liability for the debts of the owner to the '
    'amount of $75,000, except mortgages, laborers'
)
JOINT = (
    'The exemption extends to land owned by husband and wife jointly or in common or as marital property, '
    'and each spouse may claim a homestead exemption of not more than $75,000.'
)
PER_PAIR = 'Consider each asset-exemption pair independently, without factoring in aggregate values across multiple assets.'
JOINT_INTEREST = (
    'If the task involves a married couple, assume all assets mentioned are jointly owned, '
    'with each spouse holding an equal undivided interest, unless explicitly stated otherwise.'
)
OCCUPANCY = re.compile(r'\b(?:year-round residence|owner-occupied|principal residence|primary home)\b', re.I)
AMOUNT = re.compile(r'\$([0-9][0-9,]*)\.([0-9]{2})$')


def supported(view):
    """Limit scope to explicitly occupied, source-owned property in the native task."""
    text = view['public']['original_input']
    premise = supplied_jurisdiction_scope(text)
    if view['id'] not in ('EC', 'EV') or premise is None or CITATION not in premise['citations']:
        return {}
    instructions, _, supplied = text.partition('\nStatutes:\n')
    laws = [body for heading, _, body in (block.partition('\n') for block in
            supplied.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')) if heading == CITATION]
    if len(laws) != 1 or not laws[0].startswith(OPENING) or JOINT not in laws[0]:
        return {}
    if view['id'] == 'EV' and PER_PAIR not in instructions:
        return {}
    try:
        filers, assets, _ = title_inventory(text)
    except ValueError:
        return {}
    if view['id'] == 'EV' and filers == 2 and JOINT_INTEREST not in instructions:
        return {}
    bounds = {}
    for asset in assets.values():
        name = asset['description']
        money = AMOUNT.fullmatch(asset['amount_quote'])
        if asset['filing_interest_established'] is not True or not OCCUPANCY.search(name) or not money:
            continue
        cents = int(money[1].replace(',', '')) * 100 + int(money[2])
        if cents <= 0:
            continue
        # Equal stipulated shares give one statutory cap per named spouse.
        bound = min(cents, SINGLE_CAP_CENTS * filers)
        bounds[name] = {'title': True, 'filers': filers, 'stated_cents': cents,
                        'expected_cents': bound, 'source_quote': asset['source_quote']}
    return bounds
