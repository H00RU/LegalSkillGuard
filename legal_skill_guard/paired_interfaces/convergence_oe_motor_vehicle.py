"""Certify per-vehicle amounts from the statutes printed in OpenExempt inputs."""

import re

from legal_skill_guard.paired_interfaces import convergence_oe_federal_item_cap as federal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


FEDERAL = '11 U.S.C. § 522(d)(2)'
WISCONSIN = 'Wis. Stat. § 815.18(3)(g)'
CONSUMER_GOODS = 'Wis. Stat. § 815.18(3)(d)'
MARITAL = 'Wis. Stat. § 815.18(8)'
FEDERAL_TEXT = re.compile(r"The debtor's interest, not to exceed (\$[\d,]+) in value, in one motor vehicle\.")
WISCONSIN_TEXT = re.compile(
    r'Motor vehicles\. Motor vehicles not to exceed (\$[\d,]+) in aggregate value\. '
    r'Any unused amount of the aggregate value from par\. \(d\) may be added to this exemption '
    r'to increase the aggregate exempt value of motor vehicles under this paragraph\.'
)
CONSUMER_TEXT = re.compile(
    r'Consumer goods\. Household goods and furnishings, wearing apparel, keepsakes, jewelry and other '
    r'articles of personal adornment, appliances, books, musical instruments, firearms, sporting goods, '
    r'animals, or other tangible personal property held primarily for the personal, family or household '
    r'use of the debtor or a dependent of the debtor, not to exceed (\$[\d,]+) in aggregate value\.'
)
MARITAL_TEXT = (
    'Marital property rights. Each spouse is entitled to and may claim the exemptions under this section. '
    'If the property exempt under this section is limited to a specified maximum dollar amount, each spouse '
    'is entitled to one exemption. That exemption is limited to the specified maximum dollar amount, '
    "which may be combined with the other spouse's exemption in the same property or applied to different "
    'property included under the same exemption.'
)
VEHICLE = re.compile(
    r'\b(?:19|20)\d{2} (?:Chevrolet|Ford|Honda|Hyundai|Jeep|Lexus|Nissan|Rivian|Subaru|Toyota|Volkswagen) '
    r'[A-Za-z0-9][\w-]*\b', re.I,
)
PARTS = re.compile(r'\b(?:toy|die[- ]cast|model kit|engine|parts?|replacement|scale model|lease|financ\w*)\b', re.I)


def source_proof(view):
    if view['id'] != 'EV':
        return {}
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    prompt, _, statute = text.partition('\nStatutes:\n')
    if (scope is None or not {FEDERAL, WISCONSIN}.intersection(scope['citations'])
            or federal.PAIRWISE not in prompt):
        return {}
    rows = [block.partition('\n')[::2] for block in
            statute.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    allowed = set(scope['citations'])

    def amount(citation, pattern):
        supplied = [body for key, body in rows if key == citation]
        if citation in allowed and len(supplied) == 1 and (match := pattern.fullmatch(supplied[0])):
            return federal.cents(match[1])
        return None

    cap = amount(FEDERAL, FEDERAL_TEXT)
    vehicle = amount(WISCONSIN, WISCONSIN_TEXT)
    consumer = amount(CONSUMER_GOODS, CONSUMER_TEXT)
    try:
        filers, assets, _ = title_inventory(text)
    except ValueError:
        return {}
    pool = sum(federal.cents(r['amount_quote']) for r in assets.values())
    separate_spouses = (federal.JOINT_FACTS in prompt and
                         [body for key, body in rows if key == MARITAL] == [MARITAL_TEXT])
    proof = {}
    for row in assets.values():
        name = row['description']
        if (not VEHICLE.search(name) or PARTS.search(name) or federal.BUSINESS.search(row['source_quote'])
                or row['filing_interest_established'] is not True):
            continue
        value = federal.cents(row['amount_quote'])
        if value <= 0:
            continue
        known = {}
        if cap is not None and filers == 1:
            known[FEDERAL] = {'expected_cents': min(cap, value), 'printed_cap_cents': cap}
        if vehicle is not None and consumer is not None and (filers == 1 or separate_spouses):
            # All other visible assets together bound the potential draw on
            # the two state allowances, even if their classes are unresolved.
            upper = (vehicle + consumer) * filers
            lower = max(0, upper - (pool - value))
            if min(lower, value) == min(upper, value):
                known[WISCONSIN] = {'expected_cents': min(upper, value), 'lower_allowance_cents': lower,
                                    'upper_allowance_cents': upper}
        if known:
            proof[name] = known
    return proof


def apply(answer, proof):
    if not isinstance(answer, dict):
        return answer
    updated = dict(answer)
    for asset, citations in proof.items():
        claims = list(updated.get(asset, ()))
        for citation, value in citations.items():
            expected = {'citation': citation, 'claim_value': value['expected_cents'] / 100}
            if [row for row in claims if row['citation'] == citation] != [expected]:
                claims = [row for row in claims if row['citation'] != citation] + [expected]
        updated[asset] = claims
    return updated
