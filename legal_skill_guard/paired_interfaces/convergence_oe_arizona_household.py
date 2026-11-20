"""Bind Arizona household claims to the supplied statute and named asset."""

import re

from legal_skill_guard.paired_interfaces.convergence_oe_federal_item_cap import cents
from legal_skill_guard.paired_interfaces.convergence_oe_illinois_eligibility import PERSONAL_DEFAULT
from legal_skill_guard.paired_interfaces.convergence_oe_pa_item_forms import filter_claims
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


HOUSEHOLD = 'Ariz. Rev. Stat. § 33-1123'
APPAREL, LIVESTOCK, RINGS, PETS = (f'Ariz. Rev. Stat. § 33-1125({i})' for i in (1, 3, 4, 11))
HOUSEHOLD_TEXT = (
    'Household furniture, furnishings and appliances. Household furniture and furnishings, household '
    'goods, including consumer electronic devices, and household appliances personally used by the debtor '
    'or a dependent of the debtor and not otherwise specifically prescribed in this chapter are exempt '
    'from process provided their aggregate fair market value does not exceed $15,000.'
)
LAWS = {
    HOUSEHOLD: HOUSEHOLD_TEXT,
    APPAREL: 'All wearing apparel of not more than a fair market value of five hundred dollars.',
    LIVESTOCK: 'Horses, milk cows and poultry of not more than an aggregate fair market value of one thousand dollars.',
    RINGS: 'All engagement and wedding rings of not more than an aggregate fair market value of two thousand dollars.',
    PETS: 'All domestic animals or household pets.',
}
CAP = 1_500_000
GOODS = re.compile(r'\b(?:air conditioning unit|air conditioner|ice maker|vacuum sealer|platform bed|'
                   r'card table|desktop fan|television|smart tv|pots and pans)\b', re.I)
EARRINGS = re.compile(r'\bearrings\b', re.I)
MIXED_ITEM = re.compile(r'\b(?:bundle|kit|plus|including|earrings|engagement rings?|wedding rings?|'
                        r'apparel|pet|horse|cow|poultry)\b', re.I)
NONPERSONAL = re.compile(r'\b(?:commercial|business|professional|trade|industrial|rental)\b', re.I)


def source_proof(view):
    if view['id'] not in ('EC', 'EV'):
        return {'eligible': {}, 'excluded': []}
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if not scope or HOUSEHOLD not in scope['citations']:
        return {'eligible': {}, 'excluded': []}
    prompt, _, law = text.partition('\nStatutes:\n')
    blocks = [block.partition('\n')[::2]
              for block in law.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    active = {name for name, exact in LAWS.items() if name in scope['citations']
              and [body for citation, body in blocks if citation == name] == [exact]}
    if HOUSEHOLD not in active:
        return {'eligible': {}, 'excluded': []}
    try:
        _, assets, _ = title_inventory(text)
    except ValueError:
        return {'eligible': {}, 'excluded': []}

    # The value of the whole visible estate is an upper bound on the amount
    # counted under the household rule, even if some categories are unresolved.
    below_cap = sum(cents(row['amount_quote']) for row in assets.values()) <= CAP
    eligible, excluded = {}, set()
    for row in assets.values():
        name = row['description']
        household_good = GOODS.search(name) and not MIXED_ITEM.search(name)
        plain_earrings = EARRINGS.search(name) and not re.search(r'\b(?:and|bundle|rings)\b', name, re.I)
        if household_good or plain_earrings:
            excluded.update((name, citation) for citation in active - {HOUSEHOLD})
        if (household_good and below_cap and PERSONAL_DEFAULT in prompt and row['filing_interest_established']
                and not NONPERSONAL.search(row['source_quote']) and (amount := cents(row['amount_quote'])) > 0):
            eligible[name] = amount
    return {'eligible': eligible, 'excluded': sorted(excluded)}


def apply(task, answer, proof):
    if not isinstance(answer, dict):
        return answer
    result = filter_claims(task, answer, set(map(tuple, proof['excluded'])))
    if not proof['eligible']:
        return result
    result = dict(result)
    for asset, amount in proof['eligible'].items():
        claims = result.get(asset, [])
        if task == 'EC':
            result[asset] = list(dict.fromkeys([*claims, HOUSEHOLD]))
        else:
            expected = {'citation': HOUSEHOLD, 'claim_value': amount / 100}
            if [claim for claim in claims if claim['citation'] == HOUSEHOLD] != [expected]:
                result[asset] = [claim for claim in claims if claim['citation'] != HOUSEHOLD] + [expected]
    return result
