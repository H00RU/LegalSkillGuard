"""Consume an actual local graph through preserved learned native programs.

Public generator geography is parsed as literal data, never executed. Native
reference arguments, grading functions and expected answers are not inputs.
Unsupported routes and ambiguous bag anchors remain unresolved.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json'
GEOGRAPHY = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/gen_questions.py'


def public_geography():
    definitions = {}
    for node in ast.parse(GEOGRAPHY.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('us_city_collection', 'international_city_collection'):
                    definitions[target.id] = ast.literal_eval(node.value)
    cities = {name: 'U.S.' for name in definitions['us_city_collection']}
    cities.update(definitions['international_city_collection'])
    return cities


def unresolved(reason):
    return {'handled': False, 'answer': None, 'reason': reason,
            'fallback_executed': False, 'native_grading_oracle_used_for_prediction': False}


def route_region(graph):
    cities = public_geography()
    quotes = [e['quote'] for e in graph['relations'] if e['predicate'] == 'route' and e['status'] == 'stated']
    if not quotes:
        return None
    matches = []
    for quote in quotes:
        found = sorted((m.start(), name) for name in cities
                       for m in re.finditer(r'(?<!\w)' + re.escape(name) + r'(?!\w)', quote))
        if len(found) == 2:
            matches.append(tuple(cities[name] for start, name in found))
    if not matches or len(set(matches)) != 1:
        return None
    origin, destination = matches[0]
    domestic = {'U.S.', 'Puerto Rico'}
    if origin in domestic and destination in domestic:
        return 'domestic_us'
    if origin in domestic and destination == 'South America' or destination in domestic and origin == 'South America':
        return 'south_america_other'
    east = {'India', 'China', 'Japan', 'South Korea', 'Hong Kong', 'Australia', 'New Zealand'}
    if origin in domestic and destination in east or destination in domestic and origin in east:
        return 'east_asia'
    # E.g. Peru is explicitly excluded by this preserved learned program's
    # South-America premise. Never send an unknown destination to its else arm.
    return None


def airline_inputs(graph, units):
    if not graph['scope_complete'] or graph['unresolved']:
        return unresolved('The bag/itinerary graph does not claim a complete resolved local scope')
    by_unit = {u['id']: u for u in units}
    bags = [n for n in graph['nodes'] if n['kind'] == 'bag']
    if not bags:
        return unresolved('No source-anchored bags')
    ordered, seen_anchors = [], set()
    for bag in bags:
        unit = by_unit.get(bag['unit_id'])
        if not unit or bag['quote'] not in unit['text']:
            return unresolved('Bag source evidence missing')
        occurrences = [m.start() for m in re.finditer(re.escape(bag['quote']), unit['text'])]
        if len(occurrences) != 1:
            return unresolved('Repeated bag quote does not determine occurrence identity')
        key = (unit['start'], occurrences[0])
        if key in seen_anchors:
            return unresolved('Two bags share an indistinguishable source anchor')
        seen_anchors.add(key)
        ordered.append((key, bag))
    ordered.sort(key=lambda item: item[0])
    arrays = {f'item_{p}s': [] for p in ('length', 'width', 'height', 'weight')}
    for key, bag in ordered:
        for predicate in ('length', 'width', 'height', 'weight'):
            edges = [e for e in graph['relations'] if e['predicate'] == predicate
                     and e['arguments'] and e['arguments'][0] == bag['id']]
            if (len(edges) != 1 or edges[0]['status'] != 'stated'
                    or type(edges[0]['value']) not in (float, int) or edges[0]['value'] < 0):
                return unresolved('A bag has a missing, ambiguous, or nonnumeric ' + predicate)
            value = edges[0]['value']
            if predicate == 'weight' and (int(value) != value or not 0 <= value <= 100):
                return unresolved('Weight is outside the certified integer 0..100 domain')
            arrays['item_' + predicate + 's'].append(value)
    prices = [e for e in graph['relations'] if e['predicate'] == 'ticket_price']
    if len(prices) != 1 or prices[0]['status'] != 'stated' or type(prices[0]['value']) is not int:
        return unresolved('Ticket price is missing or ambiguous')
    cabins = {'Main Cabin', 'Basic Economy', 'Main Plus', 'Premium Economy', 'Business', 'First'}
    values = {n['concept'] for n in graph['nodes'] if n['concept'] in cabins}
    values.update(e['value'] for e in graph['relations'] if e['predicate'] == 'cabin'
                  and e['status'] == 'stated' and isinstance(e['value'], str) and e['value'] in cabins)
    if len(values) != 1:
        return unresolved('Cabin is missing or ambiguous')
    region = route_region(graph)
    if region is None:
        return unresolved('Route is unestablished or outside the preserved learned module domain')
    return {'handled': True, 'inputs': {**arrays, 'ticket_price': prices[0]['value'],
            'cabin_class': next(iter(values)), 'route_fee_region': region},
            'bag_source_order': [b['id'] for key, b in ordered],
            'public_geography_sha256': hashlib.sha256(GEOGRAPHY.read_bytes()).hexdigest()}


def run_airline(graph, units, expected_library_sha256):
    if hashlib.sha256(LIBRARY.read_bytes()).hexdigest() != expected_library_sha256:
        raise ValueError('The fixed learned native consumer changed')
    extracted = airline_inputs(graph, units)
    if not extracted['handled']:
        return extracted
    library = json.loads(LIBRARY.read_text())
    skill = library['skills']['domestic_main_or_first_bag_total']
    if any(p['mode'] != 'constant' for p in skill['premises'].values()):
        return unresolved('Unresolved current legal premise')
    from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
    validate_procedure(skill['procedure'])
    payload = {'procedure': skill['procedure'], 'calls': [{'inputs': extracted['inputs']}],
               'premises': {k: v['value'] for k, v in skill['premises'].items()}}
    result = subprocess.run([sys.executable, '-m', 'legal_skill_guard.paired_interfaces.consumer_worker'],
        input=json.dumps(payload), capture_output=True, text=True, check=False, timeout=30, cwd=ROOT)
    if result.returncode:
        raise RuntimeError('Frozen pure consumer failed: ' + result.stderr[-1000:])
    answer = json.loads(result.stdout)
    return {'handled': True, 'answer': answer[0]['answer'], 'module': skill['id'],
        'inputs': extracted['inputs'], 'bag_source_order': extracted['bag_source_order'],
        'public_geography_sha256': extracted['public_geography_sha256'],
        'learned_native_main_path_executed': True, 'fallback_executed': False,
        'native_grading_oracle_used_for_prediction': False,
        'weight_representative_semantics': 'decoded equivalent input, not a claim of literal weight'}
