"""Compute the Illinois general-property amount under the benchmark input."""

from decimal import Decimal
import re

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


CITATION = '735 Ill. Comp. Stat. 5/12-1001(b)'
RULE = re.compile(r"The debtor's equity interest, not to exceed \$([\d,]+) in value, in any other property;")
PAIRWISE = 'Consider each asset-exemption pair independently, without factoring in aggregate values across multiple assets.'
ENCUMBRANCE = re.compile(r'\b(?:mortgage|encumber\w*|liens?|pledged|equity share|security interest)\b', re.I)


def source_amounts(view):
    if view['id'] != 'EV':
        return {}
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if not scope or CITATION not in scope['citations']:
        return {}
    prompt, _, laws = text.partition('\nStatutes:\n')
    if PAIRWISE not in prompt:
        return {}
    blocks = laws.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')
    sections = [block.partition('\n') for block in blocks]
    statutes = [body for heading, _, body in sections if heading == CITATION]
    if len(statutes) != 1 or not (rule := RULE.fullmatch(statutes[0])):
        return {}
    try:
        filers, assets, _ = title_inventory(text)
    except ValueError:
        return {}
    facts = text.partition('\nFacts:\n')[2].partition('\nOutput contract:')[0]
    if filers != 1 or ENCUMBRANCE.search(facts):
        return {}
    cap = int(rule[1].replace(',', ''))
    amounts = {}
    for row in assets.values():
        if row['filing_interest_established'] is not True:
            continue
        value = Decimal(row['amount_quote'].replace('$', '').replace(',', ''))
        if value > 0:
            amounts[row['description']] = min(value, cap)
    return amounts


def apply(answer, amounts):
    if not isinstance(answer, dict) or not amounts:
        return answer
    revised = dict(answer)
    for asset, value in amounts.items():
        rows = answer.get(asset, [])
        previous = [row for row in rows if row['citation'] == CITATION]
        if len(previous) == 1 and Decimal(str(previous[0]['claim_value'])) == value:
            continue
        revised[asset] = [row for row in rows if row['citation'] != CITATION]
        revised[asset].append({'citation': CITATION, 'claim_value': float(value)})
    return revised
