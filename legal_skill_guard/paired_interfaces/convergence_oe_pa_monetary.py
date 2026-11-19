"""Execute the explicit Pennsylvania monetary clause in the pinned benchmark."""

from decimal import Decimal

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import (
    supplied_jurisdiction_scope,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.skill_evolution.objects import digest

CITATION = '42 Pa. Cons. Stat. § 8123'
# Same complete statute line in all eight already reviewed PA TRAIN views.
RULE_SHA256 = '3cc771f95f25502a4bae897ac275c330b364720b7004f6df8542fe79a5433866'
EV_SCOPE = 'Consider each asset-exemption pair independently, without factoring in aggregate values across multiple assets.'
JOINT_FACTS = ('If the task involves a married couple, assume all assets mentioned are jointly owned, '
               'with each spouse holding an equal undivided interest, unless explicitly stated otherwise.')


def claims(view):
    """Return positive claims with a source-bound interest and exact clause."""
    task = view['id']
    if task not in ('EC', 'EV'):
        return {}
    text = view['public']['original_input']
    premise = supplied_jurisdiction_scope(text)
    if not premise or CITATION not in premise['citations']:
        return {}
    instructions, _, statutes = text.partition('\nStatutes:\n')
    statute_lines = statutes.partition('\nSolved Reasoning Steps:\n')[0].splitlines()
    entries = [line for title, line in zip(statute_lines, statute_lines[1:]) if title == CITATION]
    if len(entries) != 1 or digest(entries[0]) != RULE_SHA256 or (task == 'EV' and EV_SCOPE not in instructions):
        return {}
    try:
        count, inventory, _ = title_inventory(text)
    except ValueError:
        return {}
    if count == 2 and JOINT_FACTS not in instructions:
        return {}
    rows = {}
    for asset in inventory.values():
        # Both spouses may claim separately. Require the task's joint assumption above.
        if count == 1 and asset['filing_interest_established'] is not True:
            continue
        value = Decimal(asset['amount_quote'][1:].replace(',', ''))
        if value > 0:
            rows[asset['description']] = float(min(value, count * 300))
    return rows


def apply(task, answer, additions):
    if not isinstance(answer, dict) or not additions:
        return answer
    result = dict(answer)
    for name, value in additions.items():
        original = result.get(name, [])
        if task == 'EC':
            if CITATION not in original:
                result[name] = [*original, CITATION]
        elif task == 'EV':
            claim = {'citation': CITATION, 'claim_value': value}
            if [item for item in original if item['citation'] == CITATION] != [claim]:
                result[name] = [item for item in original if item['citation'] != CITATION] + [claim]
    return result
