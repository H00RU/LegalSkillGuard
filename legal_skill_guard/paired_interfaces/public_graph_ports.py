"""Public graph-to-consumer port closure for equivalent relational spellings.

Keep every original node, relation, value, status and uncertainty. Derive only
the covenant subtype of an explicit obligation/prohibition action, and the
COVID subtype of an explicitly scoped exception condition. Neither hypothesis
labels nor reference graphs nor document keywords are consulted here.
"""
from copy import deepcopy
import json

from legal_skill_guard.paired_interfaces.consumer_graph_contract import consumer_graph as original_contract
from legal_skill_guard.skill_evolution.objects import digest


COVID = {'pandemic', 'epidemic', 'covid_19'}
COVENANTS = {'obligation': 'ordinary_course_covenant',
             'prohibition': 'negative_interim_covenant'}


def consumer_graph(graph):
    value, original_receipt = original_contract(graph)
    nodes = {n['id']: n for n in value['nodes']}
    edges = deepcopy(value['relations'])
    aliases, derived = {}, []
    for identity, node in list(nodes.items()):
        wanted = COVENANTS.get(node['concept']) if node['kind'] == 'effect' else None
        relations = [e for e in edges if e['status'] == 'stated' and e['arguments']
                     and e['arguments'][0] == identity]
        targets = [(e, nodes[target]) for e in relations for target in e['arguments'][1:]
                   if target in nodes]
        tags = set()
        if wanted and any(e['predicate'] == 'action' and target['concept'] == wanted
                          for e, target in targets):
            tags.add(wanted)
        if node['kind'] == 'exception' and node['concept'] not in COVID:
            tags.update(target['concept'] for e, target in targets
                        if e['predicate'] == 'condition' and target['concept'] in COVID)
        for tag in sorted(tags):
            new_id = 'public-port:' + digest([identity, tag])[:24]
            alias = {**node, 'id': new_id, 'concept': tag}
            if new_id in nodes:
                if nodes[new_id] != alias:
                    raise ValueError('Derived consumer port identity collides with a different input node')
            else:
                value['nodes'].append(alias)
                nodes[new_id] = alias
            aliases.setdefault(identity, []).append(new_id)
            derived.append({'original_node': identity, 'derived_node': new_id, 'concept': tag,
                            'basis': 'stated action subtype' if tag not in COVID else 'stated exception condition'})
    known = {json.dumps(e, sort_keys=True, ensure_ascii=False) for e in value['relations']}
    added = 0
    def append(edge):
        nonlocal added
        key = json.dumps(edge, sort_keys=True, ensure_ascii=False)
        if key not in known:
            known.add(key)
            value['relations'].append(edge)
            added += 1
    for edge in edges:
        args = edge['arguments']
        if not args:
            continue
        for alias in aliases.get(args[0], []):
            append({**edge, 'arguments': [alias, *args[1:]]})
        if edge['predicate'] == 'exception_for':
            for source in [args[0], *aliases.get(args[0], [])]:
                for target in args[1:]:
                    for alias in aliases.get(target, []):
                        append({**edge, 'arguments': [source, alias]})
    return value, {'original_public_contract': original_receipt, 'derived_consumer_ports': derived,
        'added_relations': added, 'all_original_nodes_and_relations_preserved': True,
        'unknown_negated_unread_values_and_scope_unchanged': True,
        'native_labels_reference_graphs_or_document_keyword_search_used': False,
        'not_a_learned_method_or_source_truth_certificate': True}
