"""Bind the benchmark's federal item cap to explicit property and title."""

from decimal import Decimal
import re

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


CITATION = '11 U.S.C. § 522(d)(3)'
JOINT = '11 U.S.C. § 522(m)'
JOINT_TEXT = (
    'Subject to the limitation in subsection (b), this section shall apply separately with respect '
    'to each debtor in a joint case.'
)
PAIRWISE = 'Consider each asset-exemption pair independently, without factoring in aggregate values across multiple assets.'
PERSONAL = 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'
JOINT_FACTS = (
    'If the task involves a married couple, assume all assets mentioned are jointly owned, '
    'with each spouse holding an equal undivided interest, unless explicitly stated otherwise.'
)
LAW = re.compile(
    r"The debtor's interest, not to exceed \$([\d,]+) in value in any particular item or \$[\d,]+ in aggregate value, "
    r'in household furnishings, household goods, wearing apparel, appliances, books, animals, crops, or '
    r'musical instruments, that are held primarily for the personal, family, or household use of the debtor or a dependent of the debtor\.'
)
TYPE = re.compile(
    r'\b(?:wall-mounted floating shelf|bunk bed|wall clock|nightstands?|vanity stool|dishwasher|'
    r'washer-dryer|countertop blender|ice maker|space heater|smart thermostat|coat|cardigan|'
    r'windbreaker|jacket|dress shirt|camisole|hoodie|robe|slacks|bucket hat)\b', re.I,
)
BUSINESS = re.compile(r'\b(?:business|commercial|trade|resale|liens?|encumber\w*)\b', re.I)
MODES = ('one_item_cap', 'per_filer_cap')


def cents(token):
    return int(Decimal(str(token).replace('$', '').replace(',', '')) * 100)


def scope(view):
    text = view['public']['original_input']
    allowed = supplied_jurisdiction_scope(text)
    prompt, _, statutes = text.partition('\nStatutes:\n')
    if view['id'] != 'EV' or not allowed or CITATION not in allowed['citations']:
        return {}
    if PAIRWISE not in prompt or PERSONAL not in prompt:
        return {}
    sections = [block.partition('\n') for block in
                statutes.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    bodies = [body for heading, _, body in sections if heading == CITATION]
    if len(bodies) != 1 or not (law := LAW.fullmatch(bodies[0])):
        return {}
    try:
        count, assets, _ = title_inventory(text)
    except ValueError:
        return {}
    if count == 2 and (JOINT_FACTS not in prompt or [body for heading, _, body in sections if heading == JOINT]
                       != [JOINT_TEXT]):
        return {}
    return {r['description']: {'value': cents(r['amount_quote']), 'cap': cents(law[1]), 'filers': count}
            for r in assets.values() if r['filing_interest_established'] is True
            and TYPE.search(r['description'].partition(' with ')[0])
            and not BUSINESS.search(r['source_quote']) and cents(r['amount_quote']) > 0}


def expected(fact, mode):
    if mode not in MODES:
        raise ValueError('An item-cap policy must have a TRAIN-supported convention')
    multiplier = fact['filers'] if mode == 'per_filer_cap' else 1
    return min(fact['value'], fact['cap'] * multiplier)


def observed(answer, asset):
    if not isinstance(answer, dict):
        return ()
    return tuple(Decimal(str(row['claim_value'])) * 100
                 for row in answer.get(asset, []) if row['citation'] == CITATION)


def clip(answer, facts, mode):
    """Correct over-limit positive claims with one unambiguous amount."""
    changes = {}
    if not isinstance(answer, dict):
        return answer
    for asset, fact in facts.items():
        published = observed(answer, asset)
        target = expected(fact, mode)
        if published and len(set(published)) == 1 and published[0] > target:
            changes[asset] = [{**row, 'claim_value': target / 100} if row['citation'] == CITATION
                              else row for row in answer[asset]]
    return {**answer, **changes} if changes else answer
