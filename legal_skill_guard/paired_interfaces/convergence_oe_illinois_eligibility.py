"""Exclude Illinois claims contradicted by the supplied statute and identified asset."""

import re

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import (
    supplied_jurisdiction_scope,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory

SECTION = '735 Ill. Comp. Stat. 5/12-1001'
VEHICLE, TRADE, HEALTH = (SECTION + f'({suffix})' for suffix in 'cde')
INTRO = (
    'Sec. 12-1001. Personal property exempt. The following personal property, owned by the debtor, '
    'is exempt from judgment, attachment, or distress for rent:'
)
LIMIT = (
    'The personal property exemptions set forth in this Section shall apply only to individuals '
    'and only to personal property that is used for personal rather than business purposes.'
)
CONDITIONS = {
    VEHICLE: "The debtor's interest, not to exceed $2,400 in value, in any one motor vehicle;",
    TRADE: ("The debtor's equity interest, not to exceed $1,500 in value, in any implements, "
            "professional books, or tools of the trade of the debtor;"),
    HEALTH: 'Professionally prescribed health aids for the debtor or a dependent of the debtor;',
}
PERSONAL_DEFAULT = 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'

# These heads identify ordinary personal objects, without inferring a type
# from features or the price. Coverage is limited to clearly identified goods.
PERSONAL_GOODS = re.compile(
    r'\b(?:earrings?|necklace|bracelet|gown|dress shirt|jacket|drying rack|webcam|'
    r'coffee table|dining table|accent chair|rice cooker|chandelier)\b', re.I,
)
UNKNOWN_TYPE = re.compile(r'\b(?:and|or|bundle|set of|including)\b', re.I)
VEHICLE_CONTEXT = re.compile(r'\b(?:motor|vehic\w*|truck|car|trailer|automotive)\b', re.I)
TRADE_CONTEXT = re.compile(r'\b(?:business|trade|profession\w*|occupation\w*|employ\w*|work)\b', re.I)
HEALTH_CONTEXT = re.compile(r'\b(?:prescri\w*|clinic\w*|medical|therap\w*|health|disabilit\w*)\b', re.I)


def exclusions(view):
    """Return asset–citation pairs that cannot stand as native claims."""
    if view['id'] not in ('EC', 'EV'):
        return set()
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if scope is None or SECTION not in scope['citations']:
        return set()
    prompt, _, statutes = text.partition('\nStatutes:\n')
    statutes = statutes.partition('\nSolved Reasoning Steps:\n')[0]
    blocks = [block.partition('\n')[::2] for block in statutes.strip().split('\n\n')]
    if [body for name, body in blocks if name == SECTION] != [INTRO, LIMIT]:
        return set()
    active = {name for name, body in CONDITIONS.items()
              if name in scope['citations'] and [s for k, s in blocks if k == name] == [body]}
    try:
        _, assets, _ = title_inventory(text)
    except ValueError:
        return set()

    excluded = {(row['description'], SECTION) for row in assets.values()}
    for row in assets.values():
        name = row['description']
        head = name.partition(' with ')[0].partition(' in ')[0]
        if not PERSONAL_GOODS.search(head) or UNKNOWN_TYPE.search(head):
            continue
        if VEHICLE in active and not VEHICLE_CONTEXT.search(name):
            excluded.add((name, VEHICLE))
        if TRADE in active and PERSONAL_DEFAULT in prompt and not TRADE_CONTEXT.search(row['source_quote']):
            excluded.add((name, TRADE))
        if HEALTH in active and not HEALTH_CONTEXT.search(row['source_quote']):
            excluded.add((name, HEALTH))
    return excluded
