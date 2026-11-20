"""Apply the supplied Pennsylvania and federal rules to named asset categories."""

import re

from legal_skill_guard.paired_interfaces import convergence_oe_federal_item_cap as federal
from legal_skill_guard.paired_interfaces import convergence_oe_pa_item_forms as pennsylvania
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import (
    supplied_jurisdiction_scope,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.skill_evolution.objects import digest

GARMENT = re.compile(r'\b(?:hoodie|windbreaker|shirt|jacket|coat|cardigan|vest|robe)\b', re.I)
HOUSEHOLD = re.compile(r'\b(?:trash can|blender|ice maker|dishwasher|booster seat|router|gas range)\b', re.I)
COMPOSITE = re.compile(r'\b(?:set of|kit of|sewing machine|bundle|plus)\b', re.I)


def item_type(name):
    head, *features = re.split(r'\s+(?:with|made (?:from|of))\s+', name, maxsplit=1, flags=re.I)
    if COMPOSITE.search(name) or re.search(r'[,;/]|\band\b', head, re.I):
        return None
    if any(GARMENT.search(tail) or HOUSEHOLD.search(tail) for tail in features):
        return None
    types = [kind for kind, pattern in (('apparel', GARMENT), ('household', HOUSEHOLD))
             if any(hit.end() == len(head) for hit in pattern.finditer(head))]
    return types[0] if len(types) == 1 else None


def source_proof(view):
    text = view['public']['original_input']
    task = view['id']
    allowed = supplied_jurisdiction_scope(text)
    additions, excluded = {}, []
    scope = set(pennsylvania.RULES) | {federal.CITATION}
    if not allowed or not scope.intersection(allowed['citations']):
        return {'add': additions, 'exclude': excluded}
    prompt, _, law = text.partition('\nStatutes:\n')
    blocks = [block.partition('\n')[::2] for block in
              law.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')]
    provided = {name: [body for code, body in blocks if code == name]
                for name in scope.intersection(allowed['citations'])}
    pa_active = {name for name, expected in pennsylvania.RULES.items()
                 if len(provided.get(name, ())) == 1 and digest(provided[name][0]) == expected}
    federal_bodies = provided.get(federal.CITATION, [])
    item_limit = federal.LAW.fullmatch(federal_bodies[0]) if len(federal_bodies) == 1 else None
    independent_amount = task == 'EV' and federal.PAIRWISE in prompt
    personal_use = federal.PERSONAL in prompt
    try:
        filers, assets, _ = title_inventory(text)
    except ValueError:
        return {'add': additions, 'exclude': excluded}
    for row in assets.values():
        asset = row['description']
        kind = item_type(asset)
        if kind:
            irrelevant = {pennsylvania.SEWING}
            if kind == 'household':
                irrelevant.add(pennsylvania.APPAREL)
            excluded.extend((asset, citation) for citation in irrelevant & pa_active)
        if row['filing_interest_established'] is not True or federal.BUSINESS.search(row['source_quote']):
            continue
        amount = federal.cents(row['amount_quote'])
        lawful = {}
        if kind == 'apparel' and pennsylvania.APPAREL in pa_active and amount > 0:
            if task == 'EC' or (independent_amount and filers == 1):
                lawful[pennsylvania.APPAREL] = amount
        if (independent_amount and personal_use and item_limit and kind == 'household'
                and re.search(r'\btrash can\b', asset, re.I)
                and 0 < amount <= federal.cents(item_limit[1])):
            lawful[federal.CITATION] = amount
        if lawful:
            additions[asset] = lawful
    return {'add': additions, 'exclude': sorted(excluded)}


def apply(task, answer, proof):
    if not isinstance(answer, dict):
        return answer
    filtered = pennsylvania.filter_claims(task, answer, set(map(tuple, proof['exclude'])))
    result = dict(filtered)
    for asset, values in proof['add'].items():
        claims = list(filtered.get(asset, ()))
        present = set(claims) if task == 'EC' else {row['citation'] for row in claims}
        for citation in sorted(values.keys() - present):
            claims.append(citation if task == 'EC' else {
                'citation': citation, 'claim_value': values[citation] / 100,
            })
        result[asset] = claims
    return result
