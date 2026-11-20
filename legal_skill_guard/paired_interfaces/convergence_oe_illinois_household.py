"""Check Illinois category exclusions for unambiguously described household objects."""

import re

from legal_skill_guard.paired_interfaces import convergence_oe_illinois_eligibility as illinois
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


APPAREL = illinois.SECTION + '(a)'
APPAREL_TEXT = 'The necessary wearing apparel, bible, school books, and family pictures of the debtor and the debtor\'s dependents;'
OBJECT = re.compile(
    r'\b(?:clothes dryer|table lamps?|can opener|streaming media player|acoustic guitar|rug)$', re.I,
)
MIXED = re.compile(r'\b(?:bundle|kit|with an? extra|plus)\b', re.I)


def exclusions(view):
    """Require original assets and the exact applicable clauses printed in the task."""
    if view['id'] not in ('EC', 'EV'):
        return set()
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if not scope or illinois.SECTION not in scope['citations']:
        return set()
    prompt, _, law = text.partition('\nStatutes:\n')
    blocks = [block.partition('\n')[::2] for block in
              law.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    if [body for code, body in blocks if code == illinois.SECTION] != [illinois.INTRO, illinois.LIMIT]:
        return set()
    expected = {APPAREL: APPAREL_TEXT, **illinois.CONDITIONS}
    active = {code for code, exact in expected.items() if code in scope['citations']
              and [body for name, body in blocks if name == code] == [exact]}
    try:
        _, inventory, _ = title_inventory(text)
    except ValueError:
        return set()
    result = set()
    for row in inventory.values():
        asset = row['description']
        name = asset.partition(' with ')[0].partition(' measuring ')[0]
        if (OBJECT.search(name) is None or illinois.UNKNOWN_TYPE.search(name) or MIXED.search(asset)
                or illinois.HEALTH_CONTEXT.search(row['source_quote'])):
            continue
        categories = {APPAREL, illinois.HEALTH}
        if (illinois.PERSONAL_DEFAULT in prompt
                and illinois.TRADE_CONTEXT.search(row['source_quote']) is None):
            categories.add(illinois.TRADE)
        result.update((asset, citation) for citation in active & categories)
    return result
