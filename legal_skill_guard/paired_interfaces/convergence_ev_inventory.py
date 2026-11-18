"""Recover public EV asset identities from the pinned OpenExempt renderer."""

from functools import lru_cache
import hashlib
import json
import re
from string import Formatter

from legal_skill_guard.openexempt import ROOT, UPSTREAM
from legal_skill_guard.skill_evolution.native import record_schema


ASSET_TEMPLATES = UPSTREAM / 'data/templates/asset_templates.json'
ASSET_TEMPLATES_SHA256 = '2051014bbb2a2f59600992cd1caa4604405b859c2867d4ce32cffb6a2e8efbb5'
INVENTORY_FILES = {str(ASSET_TEMPLATES.relative_to(ROOT)),
                   'legal_skill_guard/paired_interfaces/convergence_ev_inventory.py'}
MONEY = r'\$(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}'
INVENTORY_INSTRUCTIONS = (
    'The EV answer has one required slot for each asset in the public inventory. Apply the complete native task '
    'to every listed asset under the supplied facts and rules. Return null for an asset omitted from the claim plan, '
    'an empty list for an explicitly empty claims list, or the native citation/value claims list.'
)


def _literal(pattern):
    parts = re.split(r'\b([Aa]n?)\b', pattern)
    return ''.join(re.escape(part) if i % 2 == 0 else (part[0] + 'n?') for i, part in enumerate(parts))


def _compile_template(template):
    parts, sizes = [], {'asset': 0, 'value': 0}
    for literal, field, _, _ in Formatter().parse(template):
        parts.append(_literal(literal))
        if field is None:
            continue
        if field == 'party':
            parts.append(r'[^\n]+?')
            continue
        sizes[field] += 1
        group = f'{field}_{sizes[field]}'
        parts.append(f'(?P<{group}>' + (MONEY if field == 'value' else r'[^\n]+?') + ')')
    if not sizes['asset'] or sizes['asset'] != sizes['value']:
        raise ValueError('The pinned renderer must bind each asset description to its own amount')
    return re.compile(''.join(parts)), sizes['asset']


@lru_cache(maxsize=1)
def _templates():
    raw = ASSET_TEMPLATES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ASSET_TEMPLATES_SHA256:
        raise ValueError('The public OpenExempt asset renderer changed')
    return tuple(_compile_template(template) for group in json.loads(raw).values() for template in group)


def public_inventory(original_input):
    """Return source-bound assets when every monetary unit has one exact parse."""
    _, has_facts, remainder = original_input.partition('\nFacts:\n')
    facts, has_contract, _ = remainder.partition('\nOutput contract:')
    if not has_facts or not has_contract:
        return None
    assets = []
    for quote in re.split(r'(?<=\.)\s+', facts.strip()):
        if '$' not in quote:
            continue
        amounts = re.findall(MONEY, quote)
        if quote.count('$') != len(amounts):
            return None
        candidates = set()
        for pattern, size in _templates():
            match = pattern.fullmatch(quote) if size == len(amounts) else None
            if match:
                candidates.add(tuple((match[f'asset_{i}'], match[f'value_{i}']) for i in range(1, size + 1)))
        if len(candidates) != 1:
            return None
        parsed, = candidates
        assets.extend({'description': description, 'amount_quote': amount, 'source_quote': quote}
                      for description, amount in parsed)
    if not assets or len({row['description'] for row in assets}) != len(assets):
        return None
    return {f'asset_{i}': row for i, row in enumerate(assets, 1)}


def inventory_answer_schema(native_array_schema, inventory):
    claims = native_array_schema['items']['properties']['claims']
    return record_schema(dict.fromkeys(inventory, {**claims, 'type': ['array', 'null']}))


def restore_inventory_answer(answer, inventory):
    if set(answer) != set(inventory):
        raise ValueError('The EV response must provide a claims list for every bound asset')
    return {row['description']: answer[key] for key, row in inventory.items() if answer[key] is not None}


def with_ev_inventory(source):
    if source['dataset'] != 'OpenExempt':
        return source
    views = []
    for view in source['views']:
        if view['id'] == 'EV':
            inventory = public_inventory(view['public']['original_input'])
            if inventory:
                view = {**view, 'public': {**view['public'], 'asset_inventory': inventory,
                                           'asset_inventory_instructions': INVENTORY_INSTRUCTIONS}}
        views.append(view)
    return {**source, 'views': views}


def bound_ev_inventory(public):
    inventory = public.get('asset_inventory')
    if inventory is not None and inventory != public_inventory(public['original_input']):
        raise ValueError('The EV wire inventory must be recoverable from its original public source')
    return inventory


class EVInventoryActor:
    """Give the same source-derived EV slots to each arm at the revised stages."""

    def __init__(self, actor):
        self.actor = actor

    def __call__(self, source, library, purpose):
        return self.actor(with_ev_inventory(source), library, purpose)

    def verify_saved(self, source, library, purpose, result):
        self.actor.verify_saved(with_ev_inventory(source), library, purpose, result)
