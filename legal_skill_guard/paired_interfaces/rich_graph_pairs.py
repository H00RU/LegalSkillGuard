"""Consumer-relevant literal fields for real M2 graphs, versioned separately.

Keep semantic relationships/statuses and literal names. Source-quote provenance
stays in the original response and alignment receipt. Only route quotes used by
the fixed geographic decoder and unambiguous source bag order enter the world.
No native label, reference role, or reference value fills an observed field.
"""
import json
import re

from legal_skill_guard.paired_interfaces import graph_pairs as old
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair

SCHEMA = 'paired-source-local-literal-semantic-graph-v2'


def semantic(value, identities, reference_nodes, context, units):
    base, metadata, receipt = old._semantic_graph(value, identities, reference_nodes, context)
    facts, bag_positions = set(base.facts), {}
    for node in value['nodes']:
        identity = identities[node['id']]
        facts.add(Fact('literal_name:' + json.dumps(node['name'], ensure_ascii=False), (identity,)))
        if node['kind'] == 'bag':
            unit = units.get(node['unit_id'])
            positions = [m.start() for m in re.finditer(re.escape(node['quote']), unit['text'])] if unit and node['quote'] else []
            if len(positions) == 1:
                bag_positions[identity] = (unit['start'], positions[0])
    ordered = sorted(bag_positions, key=lambda identity: bag_positions[identity])
    if len(set(bag_positions.values())) == len(bag_positions):
        for index, identity in enumerate(ordered):
            facts.add(Fact('bag_order:' + str(index), (identity,)))
    for edge in value['relations']:
        if edge['predicate'] == 'route':
            facts.add(Fact('route_quote:' + json.dumps(edge['quote'], ensure_ascii=False),
                           tuple(identities[a] for a in edge['arguments']), edge['status']))
    return Graph(base.nodes, frozenset(facts), SCHEMA, context), metadata, receipt


def reference_graph(value, units, context):
    order = sorted(value['nodes'], key=lambda node: (old.anchors(node, units), node['kind'], node['id']))
    identities = {node['id']: 'n' + str(index) for index, node in enumerate(order)}
    return semantic(value, identities, {}, context, units), identities


def pair_from_audited_reference(reference, observed, units, *, source, role, version,
                                provenance, context, semantic_reference_verified,
                                observation_errors=(), max_alignments=256):
    if semantic_reference_verified is not True:
        raise ValueError('Literal-rich graphs still require source-only reference audits')
    by_unit = {unit['id']: unit for unit in units}
    (ref, metadata, transport), identities = reference_graph(reference, by_unit, context)
    receipt = {'source': source, 'schema': SCHEMA, 'reference_literal_metadata': metadata,
               'source_alignment_uses_roles_values_or_labels': False,
               'reference_numeric_transport': transport}
    if observed is None or observation_errors:
        reason = '; '.join(observation_errors) or 'No complete observed graph'
        return Pair(source, ref, old.failure_graph(ref, reason), version, role, provenance), {
            **receipt, 'unknown_observation': reason}
    try:
        assignments, choices = old.mappings(reference, observed, by_unit, max_alignments=max_alignments)
    except old.AlignmentSupportLimit as error:
        return Pair(source, ref, old.failure_graph(ref, str(error)), version, role, provenance), {
            **receipt, 'unknown_observation': str(error)}
    if not assignments:
        reason = 'No injective source alignment'
        return Pair(source, ref, old.failure_graph(ref, reason), version, role, provenance), {
            **receipt, 'unknown_observation': reason}
    outcomes = set()
    for assignment in assignments:
        mapped = {old_id: identities.get(target, target) for old_id, target in assignment.items()}
        world, _, _ = semantic(observed, mapped, dict(ref.nodes), context, by_unit)
        outcomes.add(world)
    return Pair(source, ref, frozenset(outcomes), version, role, provenance), {
        **receipt, 'compatible_source_identity_choices': choices, 'alignment_count': len(assignments),
        'distinct_observed_worlds': len(outcomes), 'ambiguity_has_no_assigned_probability': True}


def rich_graph(world):
    if world.schema != SCHEMA:
        raise ValueError('Old and literal-rich semantic versions cannot be pooled')
    value = old.semantic_rich_graph(Graph(world.nodes, world.facts, old.SCHEMA, world.context))
    for node in value['nodes']:
        names = [json.loads(f.predicate[len('literal_name:'):]) for f in world.facts
                 if f.predicate.startswith('literal_name:') and f.arguments == (node['id'],)]
        if len(names) != 1:
            value['unresolved'].append('Missing or ambiguous literal node name')
        node['name'] = names[0] if len(names) == 1 else ''
        orders = [int(f.predicate[len('bag_order:'):]) for f in world.facts
                  if f.predicate.startswith('bag_order:') and f.arguments == (node['id'],)]
        if len(orders) == 1:
            node['source_order'] = orders[0]
    for edge in value['relations']:
        if edge['predicate'] != 'route':
            continue
        quotes = [json.loads(f.predicate[len('route_quote:'):]) for f in world.facts
            if f.predicate.startswith('route_quote:') and f.arguments == tuple(edge['arguments'])
            and f.status == edge['status']]
        if len(quotes) == 1:
            edge['quote'] = quotes[0]
        else:
            value['unresolved'].append('Missing or ambiguous route literal')
    return value


def consumer_signature(world, dataset, native_public):
    """native_public maps fixed public task IDs to their original public input."""
    value = rich_graph(world)
    from legal_skill_guard.paired_interfaces.native_graph_consumers import airline, openexempt, sara
    from legal_skill_guard.paired_interfaces.public_graph_ports import consumer_graph
    from legal_skill_guard.paired_interfaces.legal_consumers import contract
    from legal_skill_guard.paired_interfaces.partial_legal_consumer import maud
    outputs = {}
    for task, public in native_public.items():
        if dataset in ('ContractNLI', 'MAUD'):
            closed, _ = consumer_graph(value)
            result = (contract if dataset == 'ContractNLI' else maud)(closed, task)
        elif dataset == 'RuleArena_Airline':
            result = airline(value)
        elif dataset == 'OpenExempt':
            result = openexempt(value, public, task)
        elif dataset == 'SARA_v2_Binary':
            result = sara(value, public)
        else:
            raise ValueError('Unknown legal dataset')
        outputs[task] = result
    if not outputs or any(not result['handled'] for result in outputs.values()):
        return {'handled': False, 'reason': 'Reference or edited world outside a supported native ABI',
                'native': outputs}
    return {'handled': True, 'signature': json.dumps({task: result['answer'] for task, result in outputs.items()},
            sort_keys=True, ensure_ascii=False), 'native': outputs}
