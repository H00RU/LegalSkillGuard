"""Deterministic public graph closure at the fixed legal consumer boundary.

Source schema admits inquiry conditions attached by condition/object edges and
groups defined by member_of edges. These convey information already in the
read graph. Fixed consumers expect canonical standard and recipient ports.
No tag, actor, missing value, or completeness claim is supplied from labels.
"""
from copy import deepcopy

STANDARDS = {'explicit_actual_wording', 'no_inquiry_required', 'reasonable_inquiry_required',
             'due_inquiry_required', 'constructive_imputation'}


def consumer_graph(graph):
    result = deepcopy(graph)
    nodes = {n['id']: n for n in result['nodes']}
    additions, receipts = [], []
    known = {(e['predicate'], tuple(e['arguments']), e['status']) for e in result['relations']}

    def add(edge, predicate, arguments, basis):
        key = (predicate, tuple(arguments), edge['status'])
        if key not in known:
            known.add(key)
            additions.append({**edge, 'predicate': predicate, 'arguments': arguments})
            receipts.append({'predicate': predicate, 'arguments': arguments, 'basis': basis})

    members = {}
    for edge in graph['relations']:
        if edge['status'] == 'stated' and edge['predicate'] == 'member_of' and len(edge['arguments']) == 2:
            child, parent = edge['arguments']
            members.setdefault(parent, set()).add(child)
    for edge in graph['relations']:
        if edge['status'] != 'stated' or len(edge['arguments']) != 2:
            continue
        source, target = edge['arguments']
        if source not in nodes or target not in nodes:
            continue
        if (nodes[source]['concept'] == 'knowledge_definition'
                and edge['predicate'] in ('condition', 'object') and nodes[target]['concept'] in STANDARDS):
            add(edge, 'standard', [source, target], 'explicit definition-local inquiry/wording tag')
        if edge['predicate'] == 'recipient':
            stack, visited = list(members.get(target, ())), {target}
            while stack:
                member = stack.pop()
                if member in visited:
                    continue
                visited.add(member)
                add(edge, 'recipient', [source, member], 'explicit transitive member_of definition')
                stack.extend(members.get(member, ()))
    result['relations'].extend(additions)
    return result, {'derived_ports': receipts,
        'original_nodes_relations_statuses_and_scope_preserved': True,
        'native_answer_or_reference_values_used': False,
        'shared_public_consumer_contract_not_a_learned_method': True}
