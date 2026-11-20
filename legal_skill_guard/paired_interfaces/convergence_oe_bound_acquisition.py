"""Rank measured candidate groups by repairs to source-proved amount bounds."""

from collections import defaultdict
from decimal import Decimal

from legal_skill_guard.paired_interfaces import convergence_oe_federal_item_cap as federal
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import filers


POLICIES = ('chronological', 'answer_disagreement', 'incumbent_risk', 'candidate_driven')


def public_bounds(view):
    text = view['public']['original_input']
    jurisdiction = supplied_jurisdiction_scope(text)
    inventory = public_inventory(text)
    if view['id'] != 'EV' or not jurisdiction or not inventory:
        return {}, None
    listed = defaultdict(set)
    for row in inventory.values():
        listed[row['description']].add(federal.cents(row['amount_quote']))
    values = {asset: next(iter(amounts)) for asset, amounts in listed.items() if len(amounts) == 1}
    prompt, _, remainder = text.partition('\nStatutes:\n')
    facts = text.partition('\nFacts:\n')[2].partition('\nOutput contract:')[0]
    if federal.PAIRWISE not in prompt:
        return {}, None
    try:
        count, _ = filers(facts)
    except ValueError:
        return values, None
    supplied = [block.partition('\n')[::2] for block in
                remainder.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    law = [body for name, body in supplied if name == federal.CITATION]
    if federal.CITATION not in jurisdiction['citations'] or len(law) != 1:
        return values, None
    text_cap = federal.LAW.fullmatch(law[0])
    if text_cap is None:
        return values, None
    # The larger per-filer interpretation is a conservative ceiling where
    # the joint parameter is unresolved. Do not fit it from later batches.
    return values, federal.cents(text_cap[1]) * count


def ceiling(asset, citation, values, item_cap):
    amount = values[asset]
    if item_cap is not None and citation == federal.CITATION:
        amount = min(amount, item_cap)
    return amount


def observations(answer, values):
    output = defaultdict(set)
    for asset, claims in (answer or {}).items():
        if asset in values:
            for claim in claims:
                output[asset, claim['citation']].add(Decimal(str(claim['claim_value'])) * 100)
    return output


def evidence(incumbent, proposal, values, item_cap):
    first, second = (observations(arm, values) for arm in (incumbent, proposal))

    def violations(rows):
        return {slot for slot, amounts in rows.items()
                if any(amount > ceiling(*slot, values, item_cap) for amount in amounts)}

    old, new = violations(first), violations(second)
    common = first.keys() & second.keys()
    repaired = {slot for slot in (old - new) & common if len(first[slot]) == len(second[slot]) == 1
                and next(iter(second[slot])) > 0}
    suppressed = (old - new) - repaired
    return {'verified_repairs': len(repaired), 'unverified_disappearances': len(suppressed),
            'old_violations': len(old), 'proposal_violations': len(new),
            'new_violations': len(new - old),
            'answer_disagreement': sum(first.get(k) != second.get(k) for k in first.keys() | second.keys())}


def select(groups, native_gain):
    if not groups:
        return {policy: {'position': None, 'decision': 'incumbent'} for policy in POLICIES}
    ranks = {
        'chronological': lambda i: i,
        'answer_disagreement': lambda i: (groups[i]['answer_disagreement'], i),
        'incumbent_risk': lambda i: (groups[i]['old_violations'], i),
        'candidate_driven': lambda i: (groups[i]['verified_repairs'], -groups[i]['proposal_violations'], i),
    }
    result = {}
    for name, rank in ranks.items():
        i = max(groups, key=rank)
        group = groups[i]
        eligible = native_gain > 0 and group['verified_repairs'] > 0 and group['proposal_violations'] == 0
        result[name] = {'position': i, 'decision': 'proposal' if eligible else 'incumbent'}
    return result


def remove_violations(answer, values, item_cap):
    """Source-only direct control. Removing an impossible claim adds no claim."""
    if not isinstance(answer, dict):
        return answer
    return {asset: [row for row in claims if asset not in values or
                    Decimal(str(row['claim_value'])) * 100 <= ceiling(asset, row['citation'], values, item_cap)]
            for asset, claims in answer.items()}
