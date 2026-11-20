"""Bind OpenExempt EV keys to a unique original asset without changing claims."""

import re

from legal_skill_guard.paired_interfaces.convergence_ec_inventory import asset_key
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory


ODOMETER = re.compile(r'[0-9]{1,3}(?:,[0-9]{3})* (?:mi|miles)', re.I)


def aliases(inventory):
    """Keep ambiguity in the lookup so that even a case-folded tie abstains."""
    by_name = {}
    for asset in inventory.values():
        name = asset['description']
        by_name.setdefault(name.casefold(), set()).add(name)
        # The anchored renderer records mileage in the same exact name.
        # Remove the entire last mileage phrase, never a general name prefix.
        for separator in (', ', ' ('):
            for match in re.finditer(separator if separator == ', ' else r' \(', name):
                stem, tail = name[:match.start()], name[match.end():]
                if separator == ' (' and not tail.endswith(')'):
                    continue
                suffix = tail.removesuffix(')') if separator == ' (' else tail
                if ODOMETER.fullmatch(suffix):
                    by_name.setdefault(stem.casefold(), set()).add(name)
    return by_name


def bind_valuation(view, answer):
    """Return the original valuation with only uniquely supported source keys."""
    if view['id'] != 'EV' or not isinstance(answer, dict):
        return answer
    inventory = public_inventory(view['public']['original_input'])
    if not inventory:
        return answer
    original = {asset['description'] for asset in inventory.values()}
    by_name = aliases(inventory)
    bound = {}
    for name, claims in answer.items():
        target = name
        if name not in original:
            candidates = by_name.get(name.casefold(), set())
            if len(candidates) == 1:
                target, = candidates
            elif not candidates:
                target = asset_key(name, inventory)
        bound.setdefault(target, []).extend(claims)
    return bound
