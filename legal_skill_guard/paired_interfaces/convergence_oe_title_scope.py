"""Bind title to a named filer and a valuation group in the pinned public renderer."""

from functools import lru_cache
import hashlib
import json
import re

from legal_skill_guard.paired_interfaces.convergence_ev_inventory import (
    ASSET_TEMPLATES, ASSET_TEMPLATES_SHA256, _compile_template, public_inventory,
)


# The renderer distinguishes an assertion of title from possession, a claim,
# disclosure, or general estate listing. These indices bind to its byte hash.
UNRESOLVED = {
    'one_asset': {5, 9}, 'one_asset_single': {1, 3}, 'one_asset_couple': {1, 3},
    'two_assets': {1, 4}, 'two_assets_single': {4}, 'two_assets_couple': {4},
    'three_assets': {2}, 'three_assets_single': {2}, 'three_assets_couple': {2},
}
FILER = re.compile(r'^(?P<names>[^\n]+?) \(hereinafter the Debtor(?P<plural>s?)\) filed for bankruptcy\b')
HOLDER_MARKER = 'FILING_PARTY_CAPTURE'


@lru_cache(maxsize=1)
def rules():
    raw = ASSET_TEMPLATES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ASSET_TEMPLATES_SHA256:
        raise ValueError('The audited ownership decisions require the pinned public renderer')
    groups = json.loads(raw)
    if set(groups) != set(UNRESOLVED):
        raise ValueError('A renderer template group lacks an ownership decision')
    compiled = []
    for name, templates in groups.items():
        for index, template in enumerate(templates):
            if template.count('{party}') != 1 or HOLDER_MARKER in template:
                raise ValueError('A title template must have a single named party coordinate')
            pattern, size = _compile_template(template.replace('{party}', HOLDER_MARKER))
            pattern = re.compile(pattern.pattern.replace(HOLDER_MARKER, r'(?P<holder>[^\n]+?)'))
            compiled.append((f'{name}:{index}', pattern, size, index not in UNRESOLVED[name]))
    return tuple(compiled)


def filers(facts):
    match = FILER.match(facts.strip())
    if match is None:
        raise ValueError('The exact public filing introduction is required')
    full = match['names'].casefold()
    names = full.split(' and ')
    count = 2 if match['plural'] else 1
    if len(names) != count:
        raise ValueError('The named filing group and debtor count disagree')
    parts = [p.split() for p in names]
    designation = 'debtor' + match['plural']
    aliases = {full, designation, 'the ' + designation}
    if count == 1:
        aliases.update((parts[0][0], parts[0][-1]))
    else:
        aliases.add(' and '.join(p[0] for p in parts))
        last = parts[-1][-1]
        if len(parts[-1]) >= 2 and all(len(p) == 1 or p[-1] == last for p in parts):
            aliases.add('the ' + last + 's')
    return count, aliases


def title_inventory(original_input):
    """Return the unchanged asset inventory with each sentence's title status."""
    inventory = public_inventory(original_input)
    if inventory is None:
        raise ValueError('The literal asset inventory is unresolved')
    facts = original_input.split('\nFacts:\n', 1)[1].split('\nOutput contract:', 1)[0]
    count, aliases = filers(facts)
    by_quote = {}
    for row in inventory.values():
        by_quote.setdefault(row['source_quote'], []).append((row['description'], row['amount_quote']))
    decisions = {}
    for quote, assets in by_quote.items():
        matches = []
        for name, pattern, size, established in rules():
            match = pattern.fullmatch(quote) if size == len(assets) else None
            if match is None:
                continue
            pairs = [(match[f'asset_{i}'], match[f'value_{i}']) for i in range(1, size + 1)]
            if pairs == assets:
                matches.append((name, match['holder'].casefold(), True if established else None))
        decisions_here = {(holder, status) for _, holder, status in matches}
        if len(decisions_here) != 1:
            raise ValueError('The exact asset group has no unambiguous title template')
        (holder, status), = decisions_here
        if holder not in aliases:
            raise ValueError('The named holder is outside the resolved filing group')
        decisions[quote] = {'party': holder, 'status': status, 'templates': sorted(m[0] for m in matches)}
    return count, {slot: {**asset, 'filing_interest_established': decisions[asset['source_quote']]['status']}
                   for slot, asset in inventory.items()}, decisions
