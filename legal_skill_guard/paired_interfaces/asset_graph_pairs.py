"""Versioned source-anchored OE port graphs for real structural channels.

The graph scope is F's exact residual read set for one public regime, retaining
both output families. Shared literal nodes define constants, never fill observed
asset-port facts. Asset identity matching uses source spans only. Every injective
alignment survives, and computation limits remain analysis unknowns.
"""
from collections import defaultdict
from copy import deepcopy
import json
import math
import re

from legal_skill_guard.paired_interfaces.asset_interfaces import decode_inputs, frozen_skill, regimes
from legal_skill_guard.paired_interfaces.graph_pairs import failure_graph
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill, unsupported
from legal_skill_guard.paired_interfaces.observed_abstention import abstention_graph, MARKER
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair
from legal_skill_guard.skill_evolution.objects import digest


SCHEMA = 'paired-frozen-asset-program-ports-v1'
ROOT_NODE = 'global_ports'
UNESTABLISHED = {'not_stated', 'unknown', 'unread'}


class AssetAlignmentLimit(ValueError):
    pass


def scope(regime):
    skill = frozen_skill()
    if regime not in regimes(skill):
        raise ValueError('Asset channel cannot invent a law domain')
    residual = specialize(skill['procedure'], {'governing_regime': regime},
                          allowed_context_fields={'governing_regime'})
    return {'schema': SCHEMA + ':' + digest(skill),
            'context': json.dumps({'governing_regime': regime}, sort_keys=True),
            'fields': sorted(set(residual['input_fields']) - {'output_family'}),
            'residual': residual}


def _value(value):
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('A literal port value must be finite')
        if value.is_integer():
            value = int(value)
    if type(value) not in (str, int, float, bool, type(None)):
        raise ValueError('Port literals are JSON scalars')
    return value


def _literal(value):
    value = _value(value)
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    identity = 'literal:' + digest(value)
    kind = ('literal_boolean_true' if value else 'literal_boolean_false') if type(value) is bool else (
        'literal_unknown' if value is None else 'literal_string' if isinstance(value, str) else 'literal_number')
    return identity, kind, Fact('literal_json:' + encoded, (identity,))


def _anchors(asset, units):
    unit = units.get(asset['unit_id'])
    if unit is None or not asset['quote']:
        return ()
    return tuple((asset['unit_id'], match.start(), match.end())
                 for match in re.finditer(re.escape(asset['quote']), unit['text']))


def record_from_read(plan, value, units):
    # This is the same production decoder, before using any reference. A native
    # domain refusal may retain a valid read; only a raised error rejects it.
    decode_inputs(plan, value, units)
    if plan['name'] == 'columns':
        assets = [{'unit_id': unit, 'quote': value['asset_quotes'][index],
                   'fields': {field: value[field][index] for field in plan['array_fields']}}
                  for index, unit in enumerate(value['asset_unit_ids'])]
    else:
        assets = [{'unit_id': row['unit_id'], 'quote': row['quote'],
                   'fields': {field: row[alias] for field, alias in plan['field_aliases'].items()}}
                  for row in value['assets']]
    return {'assets': assets, 'globals': {field: value[field] for field in ('number_of_debtors',) if field in value},
            'inventory_complete': value['inventory_complete'], 'unresolved': value['unresolved']}


def _encode(record, identities, domain, *, basis=None):
    if type(record['inventory_complete']) is not bool or not isinstance(record['unresolved'], list):
        raise ValueError('The local reference/read scope needs explicit Boolean and unresolved-list states')
    nodes = dict(basis.nodes) if basis is not None else {ROOT_NODE: 'global_facts'}
    # Pure literal definitions shared with a reference are a representation of
    # numbers/strings, not a factual claim about which asset has which value.
    facts = {fact for fact in basis.facts if fact.predicate.startswith('literal_json:')} if basis else set()
    facts.update({Fact('inventory_complete', (ROOT_NODE,), 'stated' if record['inventory_complete'] else 'negated'),
                  Fact('unresolved_scope', (ROOT_NODE,), 'stated' if record['unresolved'] else 'negated')})
    for constant in (None, False, True):
        identity, kind, definition = _literal(constant)
        nodes[identity] = kind
        facts.add(definition)
    def port(owner, field, cell):
        status, value = cell['status'], _value(cell['value'])
        if status in UNESTABLISHED and value is not None:
            raise ValueError('An uncertain reference/read port contains an asserted value')
        if status in ('stated', 'negated') and value is None:
            raise ValueError('An established reference/read port has no value')
        if status == 'negated' and (not field.startswith('asset_is_') or value is not False):
            raise ValueError('Explicit port negation requires a false Boolean value')
        literal, kind, definition = _literal(value)
        nodes[literal] = kind
        facts.add(definition)
        facts.add(Fact('port:' + field, (owner, literal), status))
    for index, asset in enumerate(record['assets']):
        identity = identities[index]
        nodes[identity] = 'asset'
        facts.add(Fact('present', (identity,)))
        for field, cell in asset['fields'].items():
            if field in domain['fields']:
                port(identity, field, cell)
    for field, cell in record['globals'].items():
        if field in domain['fields']:
            port(ROOT_NODE, field, cell)
    return Graph(tuple(sorted(nodes.items())), frozenset(facts), domain['schema'], domain['context'])


def reference_world(card, units, regime):
    if (card.get('source_semantic_truth_verified') is not True
            or card.get('native_answers_used') is not False
            or card.get('source_units_sha256') != digest(units)
            or card.get('fixed_skill_sha256') != digest(frozen_skill())
            or card.get('public_regime') != regime):
        raise ValueError('An asset reference needs its own source-only port review and exact binding')
    record = card['port_record']
    by_unit = {unit['id']: unit for unit in units}
    anchors = [_anchors(asset, by_unit) for asset in record['assets']]
    if any(len(value) != 1 for value in anchors) or len(set(anchors)) != len(anchors):
        raise ValueError('Reference assets need distinct unique source anchors')
    for cell in record['globals'].values():
        if len(_anchors(cell, by_unit)) != 1:
            raise ValueError('A reference scalar needs its own current-source evidence')
    order = sorted(range(len(anchors)), key=lambda i: anchors[i])
    identities = {index: 'asset:' + str(position) for position, index in enumerate(order)}
    domain = scope(regime)
    world = _encode(record, identities, domain)
    return world, {'asset_identities': identities, 'source_anchor_alignment_only': True,
        'unused_ports_projected_by_exact_residual': True,
        'residual_certificate': domain['residual']['certificate'],
        'source_reference_may_retain_unknown_native_inputs': True}


def _align(reference, observed, units, *, max_alignments, max_work):
    choices = {}
    for i, asset in enumerate(observed['assets']):
        choices[i] = [j for j, target in enumerate(reference['assets'])
                      if any(u == v and max(a, c) < min(b, d)
                             for u, a, b in _anchors(asset, units)
                             for v, c, d in _anchors(target, units))]
        if not choices[i]:
            choices[i] = ['unmatched_asset:' + str(i)]
    order, results, work = sorted(choices, key=lambda i: (len(choices[i]), i)), [], 0
    def visit(index, assignment, used):
        nonlocal work
        if index == len(order):
            results.append(dict(assignment))
            if len(results) > max_alignments:
                raise AssetAlignmentLimit('All source alignments exceed the fixed support limit')
            return
        current = order[index]
        for target in choices[current]:
            work += 1
            if work > max_work:
                raise AssetAlignmentLimit('Source alignment computation exhausted its fixed work bound')
            if target not in used:
                visit(index + 1, {**assignment, current: target}, used | {target})
    visit(0, {}, set())
    return results, choices


def pair_from_read(card, value, plan, units, *, source, role, provenance, version, production_errors=(),
                   max_alignments=256, max_work=100_000):
    observed = record_from_read(plan, value, units) if value is not None and not production_errors else None
    return pair_from_port_record(card, observed, plan, units, source=source, role=role,
        provenance=provenance, version=version, production_errors=production_errors,
        max_alignments=max_alignments, max_work=max_work)


def pair_from_port_record(card, observed, plan, units, *, source, role, provenance, version,
                          production_errors=(), max_alignments=256, max_work=100_000):
    """Accept a verified production record without imposing one decoder version.

    The caller binds that decoder in version. This accepts no target truth and
    retains every source alignment under the same graph rewrite semantics.
    """
    if not isinstance(version, str) or not re.fullmatch('[0-9a-f]{64}', version):
        raise ValueError('A complete model/decoder/alignment channel version is required')
    regime = plan['public_context']['governing_regime']
    reference, receipt = reference_world(card, units, regime)
    if observed is None or production_errors:
        if not production_errors:
            raise ValueError('An absent actual read requires explicit production error evidence')
        return Pair(source, reference, abstention_graph(reference), version, role, provenance), {
            **receipt, 'production_abstention': True, 'original_production_errors': list(production_errors)}
    try:
        alignments, choices = _align(card['port_record'], observed, {unit['id']: unit for unit in units},
                                    max_alignments=max_alignments, max_work=max_work)
    except AssetAlignmentLimit as error:
        return Pair(source, reference, failure_graph(reference, str(error)), version, role, provenance), {
            **receipt, 'analysis_alignment_unknown': str(error), 'production_abstention': False,
            'alignments_truncated_or_selected': False}
    if not alignments:
        reason = 'No injective source-anchor alignment;identity not inferred from port values'
        return Pair(source, reference, failure_graph(reference, reason), version, role, provenance), {
            **receipt, 'analysis_alignment_unknown': reason, 'production_abstention': False}
    identities = receipt['asset_identities']
    worlds = frozenset(_encode(observed, {i: identities.get(j, j) for i, j in match.items()}, scope(regime), basis=reference)
                       for match in alignments)
    return Pair(source, reference, worlds, version, role, provenance), {
        **receipt, 'compatible_source_anchor_choices': choices, 'alignments': len(alignments),
        'distinct_observed_worlds': len(worlds), 'production_abstention': False,
        'ambiguity_has_no_assigned_probability': True,
        'observed_port_values_filled_from_reference': False}


def consumer_signature(world, native_tasks=('EC', 'EV')):
    if world.schema != SCHEMA + ':' + digest(frozen_skill()):
        return unsupported('The asset port graph belongs to another frozen legal version')
    if MARKER in dict(world.nodes) or any(fact.predicate == 'read_failure' for fact in world.facts):
        return unsupported('Read rejection or analysis alignment unknown')
    try:
        regime = json.loads(world.context)['governing_regime']
        domain = scope(regime)
    except (KeyError, ValueError):
        return unsupported('Unsupported public asset graph context')
    if (Fact('inventory_complete', (ROOT_NODE,), 'stated') not in world.facts
            or Fact('inventory_complete', (ROOT_NODE,), 'negated') in world.facts
            or Fact('unresolved_scope', (ROOT_NODE,), 'negated') not in world.facts
            or Fact('unresolved_scope', (ROOT_NODE,), 'stated') in world.facts):
        return unsupported('The asset graph has an incomplete or conflicting local port scope')
    definitions = defaultdict(set)
    bindings = defaultdict(list)
    present = sorted(fact.arguments[0] for fact in world.facts
                     if fact.predicate == 'present' and fact.status == 'stated')
    if (not present or any(dict(world.nodes).get(identity) != 'asset' for identity in present)
            or any(fact.predicate == 'present' and fact.status != 'stated' and fact.arguments[0] in present
                   for fact in world.facts)):
        return unsupported('Asset graph inventory has no unique typed asset bindings')
    for fact in world.facts:
        if fact.predicate.startswith('literal_json:') and len(fact.arguments) == 1 and fact.status == 'stated':
            definitions[fact.arguments[0]].add(fact.predicate[len('literal_json:'):])
        elif fact.predicate.startswith('port:') and len(fact.arguments) == 2:
            bindings[fact.arguments[0], fact.predicate[5:]].append((fact.arguments[1], fact.status))
    def read_port(owner, field):
        rows = bindings[owner, field]
        if not rows:
            return None
        if len(rows) != 1 or len(definitions[rows[0][0]]) != 1:
            raise ValueError('Ambiguous asset port or literal definition')
        literal, status = rows[0]
        value = json.loads(next(iter(definitions[literal])))
        if status in UNESTABLISHED:
            if value is not None:
                raise ValueError('An unknown graph port acquired a guessed value')
            return None
        if value is None or status == 'negated' and (not field.startswith('asset_is_') or value is not False):
            raise ValueError('An established or negated port has inconsistent literal semantics')
        return value
    inputs, domains = {}, []
    try:
        for field in domain['fields']:
            if field == 'number_of_debtors':
                value = read_port(ROOT_NODE, field)
                if type(value) is not int or value < 1:
                    return unsupported('A necessary debtor count remains unknown')
                inputs[field] = value
                continue
            inputs[field] = [read_port(identity, field) for identity in present]
            if field.startswith('asset_is_'):
                for index, value in enumerate(inputs[field]):
                    if value is not None and type(value) is not bool:
                        raise ValueError('A category port is not a Boolean or unknown')
                    if value is None:
                        domains.append({'path': [field, index], 'values': [False, True]})
        if (any(type(value) is not str or not value for value in inputs['asset_descriptions'])
                or len(set(inputs['asset_descriptions'])) != len(present)
                or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                       for value in inputs['asset_values'])):
            return unsupported('The graph has unknown/ambiguous asset descriptions or amounts')
    except (ValueError, TypeError, KeyError) as error:
        return unsupported('Asset port graph cannot be consumed', error=str(error))
    skill = {**frozen_skill(), 'procedure': domain['residual']['procedure']}
    outputs = {}
    for task in native_tasks:
        if task not in ('EC', 'EV'):
            return unsupported('Unknown native output family')
        outputs[task] = partial_skill(skill, {**inputs, 'output_family': task}, domains)
    if not outputs or any(not result['handled'] for result in outputs.values()):
        return unsupported('Unknown asset inputs affect the original native outputs', native=outputs)
    return {'handled': True, 'signature': json.dumps({task: value['answer'] for task, value in outputs.items()},
                sort_keys=True, ensure_ascii=False), 'native': outputs,
            'source_or_native_gold_not_certified_by_program_execution': True}
