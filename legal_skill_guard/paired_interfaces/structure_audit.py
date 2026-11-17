"""Name-invariant, source-witnessed adjacent relationship combinations.

Absence from a partial annotation never certifies absence from its source.
These features audit bounded combinations, not arbitrary graph isomorphism.
"""
from collections import defaultdict
from itertools import combinations
import json


def combinations_by_key(graph, *, typed):
    """Keep relation argument positions, shared identity and repeated endpoints.

    Literals, quotes, display names and source-specific IDs are excluded from
    keys. Quotes and original IDs survive separately as inspection witnesses.
    Unknown/unread/not-stated relationships cannot witness a positive pattern.
    """
    nodes = {node['id']: node for node in graph['nodes']}
    if len(nodes) != len(graph['nodes']):
        raise ValueError('Duplicate node identities invalidate a structure audit')
    incident = defaultdict(list)
    for index, edge in enumerate(graph['relations']):
        if edge['status'] not in ('stated', 'negated'):
            continue
        args = edge['arguments']
        if not args or any(arg not in nodes for arg in args):
            raise ValueError('A witnessed relation needs existing referents')
        for anchor in set(args):
            incident[anchor].append((index, edge))
    patterns = {}
    for anchor, edges in incident.items():
        for (left_index, left), (right_index, right) in combinations(edges, 2):
            def encode(first, second):
                variables = {anchor: 0}
                records = []
                for edge in (first, second):
                    arguments = []
                    for identity in edge['arguments']:
                        if identity not in variables:
                            variables[identity] = len(variables)
                        node = nodes[identity]
                        arguments.append([variables[identity], node['kind'], node['concept']]
                                         if typed else variables[identity])
                    records.append([edge['predicate'], edge['status'], arguments])
                return json.dumps(records, sort_keys=True, separators=(',', ':'))
            key = min(encode(left, right), encode(right, left))
            if key not in patterns:
                patterns[key] = {'shared_node': anchor, 'relation_indices': [left_index, right_index],
                    'source_spans': [{k: edge[k] for k in ('unit_id', 'quote')} for edge in (left, right)],
                    'all_node_concepts_specified': all(nodes[arg]['concept'] != 'unspecified'
                        for edge in (left, right) for arg in edge['arguments'])}
    return patterns


def compare_target(target, training, *, typed):
    patterns = combinations_by_key(target, typed=typed)
    seen = set().union(*(combinations_by_key(graph, typed=typed) for graph in training))
    unseen = {key: value for key, value in patterns.items() if key not in seen}
    return {'target_distinct_combinations': len(patterns),
            'training_seen_combinations': len(patterns) - len(unseen),
            'annotation_unseen_combinations': unseen,
            'training_source_absence_verified': False,
            'novel_natural_structure_established': False}
