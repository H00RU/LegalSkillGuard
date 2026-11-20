"""Exclude inapplicable Pennsylvania apparel and sewing-machine claims."""

import re

from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.skill_evolution.objects import digest


APPAREL = '42 Pa. Cons. Stat. § 8124(a)(1)'
SEWING = '42 Pa. Cons. Stat. § 8124(a)(3)'
RULES = {
    APPAREL: 'b9156ea6a006ef28026cf73357a7ad2dcc141e81b91e5ba3f942b0c0ec066fe7',
    SEWING: '6042664c3dd428d35828b1f739327ceecd540fb41003d1ce333ff38a1208dd96',
}
NONAPPAREL = re.compile(
    r'^(?:a |an |the )?(?:bowl|dishwasher|wireless router|blender|child booster seat|ice maker)\b', re.I,
)
APPAREL_ONLY = re.compile(r'^(?:a |an |the )?(?:dress shirt|windbreaker)\b', re.I)
BUNDLE = re.compile(r'\b(?:sewing machine|dress shirt|windbreaker|apparel|bundle|set of)\b', re.I)


def excluded_item_citations(description):
    head, _, features = description.partition(' with ')
    if BUNDLE.search(features) or re.search(r'\b(?:and|plus)\b', head, re.I):
        return ()
    if NONAPPAREL.search(head):
        return APPAREL, SEWING
    if APPAREL_ONLY.search(head):
        return SEWING,
    return ()


def exclusions(view):
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if not scope or not set(RULES) & set(scope['citations']):
        return set()
    lines = text.partition('\nStatutes:\n')[2].partition('\nSolved Reasoning Steps:\n')[0].splitlines()
    exact = {name for name, body in zip(lines, lines[1:]) if name in RULES and digest(body) == RULES[name]}
    active = exact & set(scope['citations'])
    try:
        _, assets, _ = title_inventory(text)
    except ValueError:
        return set()
    return {(row['description'], law) for row in assets.values()
            for law in excluded_item_citations(row['description']) if law in active}


def filter_claims(task, answer, excluded):
    if not isinstance(answer, dict) or not excluded:
        return answer
    if task == 'EC':
        return {asset: [law for law in claims if (asset, law) not in excluded] for asset, claims in answer.items()}
    return {asset: [claim for claim in claims if (asset, claim['citation']) not in excluded]
            for asset, claims in answer.items()}
