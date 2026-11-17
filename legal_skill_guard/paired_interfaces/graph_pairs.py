"""Source-anchor alignment for real reference/reader graph pairs.

Alignment never uses the expected role edge, native answer, or a concept tag.
Every compatible injective alignment is retained up to an explicit support
limit. Beyond that limit the observation is unknown, not a selected alignment.
"""
from __future__ import annotations

import json
import re

from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair
from legal_skill_guard.skill_evolution.objects import digest

SCHEMA = 'paired-source-local-semantic-graph-v1'
ENTITY_KINDS = {'person', 'organization', 'place', 'group', 'asset', 'bag'}


class AlignmentSupportLimit(ValueError):
    pass


def anchors(node, units):
    unit = units.get(node['unit_id'])
    if unit is None or not node['quote']:
        return ()
    return tuple((node['unit_id'], m.start(), m.end())
                 for m in re.finditer(re.escape(node['quote']), unit['text']))


def compatible(observed, reference, units):
    if observed['kind'] != reference['kind']:
        return False
    # Literal names can identify repeated mentions of a source entity. They
    # are not expected worker/employer values; all edge values are ignored.
    if observed['kind'] in ENTITY_KINDS - {'asset', 'bag'}:
        if observed['name'] == reference['name']:
            return True
        # A source can call the same person "Bob" and "her father Bob".
        # Retain overlapping literal mention supports, without using the
        # expected role edge, concept tag or an answer to choose an identity.
        def mentions(node):
            return [(unit, start + m.start(), start + m.end())
                    for unit, start, end in anchors(node, units)
                    for m in re.finditer(re.escape(node['name']), node['quote'])
                    if node['name']]
        return any(u == v and max(a, c) < min(b, d)
                   for u, a, b in mentions(observed)
                   for v, c, d in mentions(reference))
    return any(u == v and max(a, c) < min(b, d)
               for u, a, b in anchors(observed, units)
               for v, c, d in anchors(reference, units))


def mappings(reference, observed, units, *, max_alignments=256, max_work=100_000):
    choices = {}
    for node in observed['nodes']:
        candidates = [n['id'] for n in reference['nodes'] if compatible(node, n, units)]
        choices[node['id']] = candidates or ['unmatched:' + digest(node)[:24]]
    order = sorted(choices, key=lambda name: (len(choices[name]), name))
    results, work = [], 0

    def visit(i, binding, used):
        nonlocal work
        if i == len(order):
            results.append(dict(binding))
            if len(results) > max_alignments:
                raise AlignmentSupportLimit('Ambiguous source identity support exceeds the declared limit')
            return
        name = order[i]
        for candidate in choices[name]:
            work += 1
            if work > max_work:
                raise AlignmentSupportLimit('Source identity search limit exhausted')
            if candidate in used:
                continue
            visit(i + 1, {**binding, name: candidate}, used | {candidate})
    visit(0, {}, set())
    return results, choices


def _semantic_graph(value, identities, reference_nodes, context):
    normalized, receipt = normalize_numeric_ports(value)
    nodes = dict(reference_nodes)
    metadata = {}
    facts = {Fact('scope_complete', (str(bool(value['scope_complete'])),)),
             Fact('scope_unresolved', (str(bool(value['unresolved'])),))}
    for node in normalized['nodes']:
        identity = identities[node['id']]
        nodes[identity] = node['kind']
        metadata[identity] = {**node, 'id': identity}
        facts.add(Fact('present', (identity,)))
        facts.add(Fact('concept:' + node['concept'], (identity,)))
    for edge in normalized['relations']:
        key = json.dumps({'predicate': edge['predicate'], 'value': edge['value']},
                         sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        facts.add(Fact('relation:' + key, tuple(identities[a] for a in edge['arguments']), edge['status']))
    return Graph(tuple(sorted(nodes.items())), frozenset(facts), SCHEMA, context), metadata, receipt


def reference_graph(value, units, context):
    # The tie breaker is a supplied opaque identity, never a role or outcome.
    order = sorted(value['nodes'], key=lambda n: (anchors(n, units), n['kind'], n['id']))
    identities = {node['id']: 'n' + str(i) for i, node in enumerate(order)}
    return _semantic_graph(value, identities, {}, context), identities


def failure_graph(reference, reason):
    # A changed node domain keeps this outside every learned known edit image.
    # It therefore contributes unknown error mass instead of a clean identity.
    nodes = tuple(sorted([*reference.nodes, ('failed-read:' + digest(reason)[:20], 'unresolved_read')]))
    return Graph(nodes, frozenset({Fact('read_failure', (), 'unread')}), reference.schema, reference.context)


def pair_from_audited_reference(reference, observed, units, *, source, role, version,
                                provenance, context, semantic_reference_verified,
                                observation_errors=(), max_alignments=256):
    if semantic_reference_verified is not True:
        raise ValueError('Span validity or teacher provenance alone is not reference truth certification')
    by_unit = {u['id']: u for u in units}
    (ref, metadata, numeric_receipt), identities = reference_graph(reference, by_unit, context)
    receipt = {'source': source, 'alignment_uses_expected_roles_or_labels': False,
               'reference_numeric_transport': numeric_receipt, 'metadata': metadata}
    if observed is None or observation_errors:
        error = '; '.join(observation_errors) or 'No complete observed graph'
        out = failure_graph(ref, error)
        return Pair(source, ref, out, version, role, provenance), {**receipt, 'unknown_observation': error}
    try:
        assignments, choices = mappings(reference, observed, by_unit, max_alignments=max_alignments)
    except AlignmentSupportLimit as error:
        return Pair(source, ref, failure_graph(ref, str(error)), version, role, provenance), {
            **receipt, 'unknown_observation': str(error), 'alignments_truncated_or_selected': False}
    if not assignments:
        reason = 'No injective source-anchor alignment; identity not guessed'
        return Pair(source, ref, failure_graph(ref, reason), version, role, provenance), {
            **receipt, 'unknown_observation': reason}
    outcomes = set()
    for assignment in assignments:
        mapped = {old: identities.get(target, target) for old, target in assignment.items()}
        result, observed_metadata, transport = _semantic_graph(observed, mapped, dict(ref.nodes), context)
        outcomes.add(result)
    receipt.update({'compatible_source_identity_choices': choices, 'alignment_count': len(assignments),
                    'distinct_observed_graphs': len(outcomes), 'ambiguity_has_no_assigned_probability': True})
    return Pair(source, ref, frozenset(outcomes), version, role, provenance), receipt


def semantic_rich_graph(graph, metadata=None):
    """Reconstruct the pure legal consumer input, without adding missing nodes.

    CNI/MAUD consumers use concepts, relationships and uncertainty, not quotes.
    This is not an Airline quote/occurrence consumer adapter.
    """
    if graph.schema != SCHEMA:
        raise ValueError('Different graph serialization')
    if any(f.predicate == 'read_failure' for f in graph.facts):
        return {'nodes': [], 'relations': [], 'scope_complete': False, 'unresolved': ['read failure']}
    present = {f.arguments[0] for f in graph.facts if f.predicate == 'present' and f.status == 'stated'}
    concepts = {}
    for fact in graph.facts:
        if fact.predicate.startswith('concept:') and fact.status == 'stated':
            concepts.setdefault(fact.arguments[0], set()).add(fact.predicate[len('concept:'):])
    nodes, problems = [], []
    for identity, kind in graph.nodes:
        if identity not in present:
            continue
        tags = concepts.get(identity, set())
        if len(tags) != 1:
            problems.append('Ambiguous or absent semantic tag for an observed node')
        nodes.append({'id': identity, 'kind': kind, 'concept': next(iter(tags)) if len(tags) == 1 else 'unspecified'})
    relations = []
    for fact in sorted(graph.facts):
        if not fact.predicate.startswith('relation:'):
            continue
        if not set(fact.arguments) <= present:
            problems.append('Relation references a missing observed node')
            continue
        body = json.loads(fact.predicate[len('relation:'):])
        relations.append({**body, 'arguments': list(fact.arguments), 'status': fact.status})
    complete = Fact('scope_complete', ('True',)) in graph.facts
    if Fact('scope_unresolved', ('True',)) in graph.facts:
        problems.append('Unresolved source scope')
    return {'nodes': nodes, 'relations': relations, 'scope_complete': complete, 'unresolved': problems}


def consumer_signature(graph, dataset, tasks):
    from legal_skill_guard.paired_interfaces.public_graph_ports import consumer_graph
    from legal_skill_guard.paired_interfaces.legal_consumers import contract
    from legal_skill_guard.paired_interfaces.partial_legal_consumer import maud
    if dataset not in ('ContractNLI', 'MAUD'):
        return {'handled': False, 'reason': 'This pure graph consumer adapter is not implemented for this dataset'}
    value, contract_receipt = consumer_graph(semantic_rich_graph(graph))
    function = contract if dataset == 'ContractNLI' else maud
    results = [function(value, task) for task in tasks]
    if not results or any(not r['handled'] for r in results):
        return {'handled': False, 'reason': 'Reference or edited world outside fixed complete consumer domain'}
    return {'handled': True, 'signature': tuple(r['answer'] for r in results)}


def complete_loss_consumer(dataset, tasks, reference_worlds):
    # This gate prevents two unhandled results from comparing equal and being
    # silently counted as a successful zero-loss mechanism application.
    if any(not consumer_signature(g, dataset, tasks)['handled'] for g in reference_worlds):
        raise ValueError('Every loss reference must be inside the fixed consumer domain')
    def consume(graph):
        result = consumer_signature(graph, dataset, tasks)
        return ('defined', *result['signature']) if result['handled'] else ('unresolved',)
    return consume
