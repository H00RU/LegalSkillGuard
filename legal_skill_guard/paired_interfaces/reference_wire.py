"""Source-reviewed inputs in the production wire ABI, without answer labels.

This inverse is a diagnostic fixture, never a model response or learned result.
Unknowns and closure are copied; a missing required port raises, rather than
being supplied by the native grader. Weight codes use the frozen alphabet.
"""
from copy import deepcopy

from legal_skill_guard.paired_interfaces.numeric_ports import port_number


def weight_cell(plan, data):
    result = deepcopy(data)
    if plan.get('weight_codec') and result['status'] == 'stated':
        groups = [g for g in plan['weight_codec']['groups'] if result['value'] in g['members']]
        if len(groups) != 1:
            raise ValueError('Reference weight outside the declared residual alphabet')
        result['value'] = groups[0]['code']
    return result


def graph_wire(plan, graph):
    result = deepcopy(graph)
    for edge in result['relations']:
        if edge['status'] == 'stated':
            edge['value'] = port_number(edge['predicate'], edge['value'])
        if edge['predicate'] == 'weight':
            edge.update(weight_cell(plan, {'value': edge['value'], 'status': edge['status']}))
    if plan['name'] == 'columns':
        for group in ('nodes', 'relations'):
            fields = plan['schema']['properties'][group]['properties']
            result[group] = {field: [row[field] for row in result[group]] for field in fields}
    return result


def asset_wire(plan, record):
    result = {key: deepcopy(record[key]) for key in ('inventory_complete', 'unresolved')}
    for field in plan['requested_fields']:
        if field in record['globals']:
            result[field] = deepcopy(record['globals'][field])
    if plan['name'] == 'columns':
        result['asset_unit_ids'] = [row['unit_id'] for row in record['assets']]
        result['asset_quotes'] = [row['quote'] for row in record['assets']]
        for field in plan['array_fields']:
            result[field] = [deepcopy(row['fields'][field]) for row in record['assets']]
    else:
        result['assets'] = [{key: deepcopy(row[key]) for key in ('unit_id', 'quote')} |
            {alias: deepcopy(row['fields'][field]) for field, alias in plan['field_aliases'].items()}
            for row in record['assets']]
    return result


def airline_wire(plan, graph, units):
    nodes = {node['id']: node for node in graph['nodes']}
    def edge(predicate, owner=None):
        matches = [e for e in graph['relations'] if e['predicate'] == predicate
                   and (owner is None or e['arguments'] == [owner])]
        if len(matches) != 1:
            raise ValueError('Reference port missing or ambiguous: ' + predicate)
        return matches[0]
    def cell(data):
        result = {key: deepcopy(data[key]) for key in ('value', 'status', 'unit_id', 'quote')}
        if result['status'] == 'stated':
            result['value'] = port_number(data['predicate'], result['value'])
        return result
    result = {'ticket_price': cell(edge('ticket_price')),
              'cabin_class': cell(edge('cabin')),
              'inventory_complete': graph['scope_complete'], 'unresolved': deepcopy(graph['unresolved'])}
    cabin_nodes = [nodes[a] for a in edge('cabin')['arguments'] if a in nodes
                   and nodes[a]['concept'] in ('Main Cabin', 'Basic Economy', 'Main Plus', 'Premium Economy', 'Business', 'First')]
    if result['cabin_class']['status'] == 'stated':
        if not cabin_nodes and result['cabin_class']['value'] in ('Main Cabin', 'Basic Economy', 'Main Plus', 'Premium Economy', 'Business', 'First'):
            pass  # The existing consumer also accepts the reviewed edge value.
        elif len(cabin_nodes) != 1:
            raise ValueError('No unique reviewed cabin concept')
        else:
            result['cabin_class']['value'] = cabin_nodes[0]['concept']
    route = edge('route')
    places = [nodes[a] for a in route['arguments'] if a in nodes and nodes[a]['kind'] == 'place']
    if route['status'] != 'stated' or len(places) != 2:
        raise ValueError('The reviewed route does not declare two ordered literal cities')
    for name, node in zip(('origin_city', 'destination_city'), places):
        result[name] = {'value': node['name'], 'status': 'stated', 'unit_id': node['unit_id'], 'quote': node['quote']}
    by_unit = {unit['id']: unit for unit in units}
    bags = sorted((n for n in graph['nodes'] if n['kind'] == 'bag'),
                  key=lambda n: (n['unit_id'], by_unit[n['unit_id']]['text'].index(n['quote'])))
    rows = []
    for bag in bags:
        row = {key: bag[key] for key in ('unit_id', 'quote')}
        for field, predicate in plan['port_binding'].items():
            e = edge(predicate, bag['id'])
            data = {key: deepcopy(e[key]) for key in ('value', 'status')}
            if data['status'] == 'stated':
                data['value'] = port_number(predicate, data['value'])
            row[field] = weight_cell(plan, data) if predicate == 'weight' else data
        rows.append(row)
    if plan['name'] == 'columns':
        result['bag_unit_ids'] = [row['unit_id'] for row in rows]
        result['bag_quotes'] = [row['quote'] for row in rows]
        for field in plan['port_binding']:
            result[field] = [row[field] for row in rows]
    else:
        result['bags'] = rows
    return result


def reference_wire(dataset, plan, card, units):
    if dataset == 'OpenExempt' and 'fixed_skill_sha256' in plan:
        return asset_wire(plan, card['port_record'])
    if dataset == 'RuleArena_Airline':
        return airline_wire(plan, card['graph'], units)
    return graph_wire(plan, card['graph'])
