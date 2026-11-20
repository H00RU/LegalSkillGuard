"""Bind classification keys to unique assets named in the original public input."""

from legal_skill_guard.paired_interfaces.convergence_ec_inventory import VALUATION
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory


def matches(key, item):
    name = item['description'].casefold()
    folded = key.casefold()
    if folded == name:
        return True
    article, matched, suffix = folded.partition(name)
    if not matched or article not in ('', 'a ', 'an ', 'the '):
        return False
    value = VALUATION.fullmatch(suffix)
    source = item['source_quote'].casefold()
    return bool(value and value[1] == item['amount_quote']
                and folded in source and source.count(name) == 1)


def bind(view, answer):
    """Preserve exact keys and abstain when an alias matches multiple asset slots."""
    if view['id'] != 'EC' or not isinstance(answer, dict):
        return answer
    inventory = public_inventory(view['public']['original_input'])
    if not inventory:
        return answer
    names = {row['description'] for row in inventory.values()}
    result = {}
    for key, citations in answer.items():
        if key not in names:
            targets = [row['description'] for row in inventory.values() if matches(key, row)]
            if len(targets) == 1:
                key, = targets
        result[key] = list(dict.fromkeys([*result[key], *citations])) if key in result else citations
    return result
