"""Compile the frozen Airline program's ports into the three locked H families.

The earlier generic ontology did not implement the original skill's seven
input ports. This production adapter derives their inventory from that skill,
transposes the four item arrays, and installs the precomputed weight alphabet.
No source, response, native answer or score participates in plan generation.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.native_adapters import LIBRARY
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

STATES = list(gi.STATUSES)
CABINS = ['Main Cabin', 'Basic Economy', 'Main Plus', 'Premium Economy', 'Business', 'First']


def cell(value):
    return record_schema({'value': deepcopy(value), 'status': {'type': 'string', 'enum': STATES}})


def anchored(value):
    result = cell(value)
    result['properties'].update(unit_id={'type': 'integer'}, quote={'type': 'string'})
    result['required'] = list(result['properties'])
    return result


def weight_cell(codec):
    positive = cell({'type': 'string', 'enum': [g['code'] for g in codec['groups']]})
    positive['properties']['status']['enum'] = ['stated']
    uncertain = cell({'type': ['number', 'null']})
    uncertain['properties']['status']['enum'] = [s for s in STATES if s != 'stated']
    return {'anyOf': [positive, uncertain]}


def compile_plans(locked):
    library = json.loads(LIBRARY.read_text())
    skill = library['skills']['domestic_main_or_first_bag_total']
    fields = skill['inputs']
    arrays = [name for name, port in fields.items() if port['type'] == 'array']
    expected = {'item_lengths': 'length', 'item_widths': 'width',
                'item_heights': 'height', 'item_weights': 'weight'}
    if set(arrays) != set(expected) or set(fields) - set(arrays) != {
            'ticket_price', 'cabin_class', 'route_fee_region'}:
        raise ValueError('The declared preserved consumer input signature changed')
    library_hash = hashlib.sha256(LIBRARY.read_bytes()).hexdigest()
    scalar = {'ticket_price': anchored({'type': ['integer', 'null'], 'minimum': 0}),
        'cabin_class': anchored({'type': ['string', 'null'], 'enum': CABINS + [None]}),
        'origin_city': anchored({'type': ['string', 'null']}),
        'destination_city': anchored({'type': ['string', 'null']})}
    instructions = '''Read the current passenger's bag inventory into the exact requested ports.
Copy the ticket price, cabin class, departure city and destination city from the facts.
For every listed item, retain its own source unit and full item quote. The first,
second and third listed dimensions populate length, width and height, respectively.
All item arrays/records follow source order. Keep every bag, including small bags;
the fixed consumer determines carry-on and checked-bag status later.
Copy the measurements, never compute a fee or answer. A missing or unread value
stays null with the corresponding status. No absent measurement becomes zero.
Keep stated, negated, not_stated, unknown and unread distinct. Mark inventory_complete
only if every listed item and all global ports were read. Include source evidence
for each global port. Do not infer a measurement from another bag.'''
    declarations = {name: {'type': port['type'], 'question': port['question']}
                    for name, port in fields.items()}
    output = []
    for original in locked:
        plan = deepcopy(original)
        plan['locked_candidate_version'] = plan.pop('version')
        plan['fixed_program_input_contract'] = declarations
        plan['fixed_library_sha256'] = library_hash
        plan['port_binding'] = expected
        props = deepcopy(scalar)
        if plan['name'] == 'columns':
            props['bag_unit_ids'] = {'type': 'array', 'items': {'type': 'integer'}}
            props['bag_quotes'] = {'type': 'array', 'items': {'type': 'string'}}
            for field in arrays:
                props[field] = {'type': 'array', 'items': cell({'type': ['number', 'null']})}
            layout = 'parallel arrays with exactly aligned item counts'
        else:
            row = {'unit_id': {'type': 'integer'}, 'quote': {'type': 'string'}}
            for field, attribute in expected.items():
                row[field] = (weight_cell(plan['weight_codec']) if field == 'item_weights'
                              and plan.get('weight_codec') else cell({'type': ['number', 'null']}))
            props['bags'] = {'type': 'array', 'items': record_schema(row)}
            layout = 'one complete anchored record per item'
        props.update(inventory_complete={'type': 'boolean'},
                     unresolved={'type': 'array', 'items': {'type': 'string'}})
        plan['schema'] = record_schema(props)
        plan['system'] = instructions + '\nUse ' + layout + '.'
        if plan.get('weight_codec'):
            plan['system'] += '\nFor each stated integer weight 0..100, return the following generated code, not the literal number:\n'
            for group in plan['weight_codec']['groups']:
                plan['system'] += group['code'] + ' for ' + str(sorted(group['members'])) + '\n'
            plan['system'] += 'Out-of-domain weights remain unknown; never round into a code.'
        plan['production_decoder'] = 'frozen_consumer_port_inventory_v1'
        plan['certificate_port_reencoding'] = {
            'from_declared_frozen_program_ports': True,
            'column_record_inverse_on_aligned_finite_arrays': True,
            'bag_order_and_unknown_statuses_preserved': True,
            'weight_partition_certificate': plan.get('weight_codec', {}).get('certificate'),
            'legal_program_not_changed': True,
            'no_feedback_or_native_labels_used_to_generate_schema': True}
        plan['version'] = digest(plan)
        output.append(plan)
    return output


def decode(plan, value, units):
    by_unit = {u['id']: u for u in units}
    nodes, relations, constructions = [], [], []
    def check(unit_id, quote):
        if unit_id not in by_unit or not quote or quote not in by_unit[unit_id]['text']:
            raise ValueError('Program port lacks contiguous current-source evidence')
    def add_node(identity, kind, concept, unit_id, quote):
        check(unit_id, quote)
        nodes.append({'id': identity, 'kind': kind, 'concept': concept,
                      'name': quote, 'quote': quote, 'unit_id': unit_id})
    def add_edge(predicate, arguments, data, unit_id, quote):
        if data['status'] == 'stated' and data['value'] is None and predicate not in ('route',):
            raise ValueError('A stated scalar port cannot carry an absent value')
        if data['status'] in ('unknown', 'unread', 'not_stated') and data['value'] is not None:
            raise ValueError('Unknown port cannot carry a guessed value')
        check(unit_id, quote)
        relations.append({'predicate': predicate, 'arguments': arguments,
            'value': data['value'], 'status': data['status'], 'unit_id': unit_id, 'quote': quote})
    globals_value = value['ticket_price']
    add_edge('ticket_price', [], globals_value, globals_value['unit_id'], globals_value['quote'])
    cabin = value['cabin_class']
    if cabin['status'] == 'stated' and cabin['value'] in CABINS:
        add_node('cabin', 'information', cabin['value'], cabin['unit_id'], cabin['quote'])
        add_edge('cabin', ['cabin'], cabin, cabin['unit_id'], cabin['quote'])
    else:
        add_edge('cabin', [], cabin, cabin['unit_id'], cabin['quote'])
    origin, destination = value['origin_city'], value['destination_city']
    for identity, port in [('origin', origin), ('destination', destination)]:
        if port['status'] == 'stated' and isinstance(port['value'], str):
            check(port['unit_id'], port['quote'])
            if port['value'] not in port['quote']:
                raise ValueError('City port must copy its literal current-source name')
            add_node(identity, 'place', 'unspecified', port['unit_id'], port['value'])
    if (origin['status'] == destination['status'] == 'stated'
            and origin['unit_id'] == destination['unit_id']):
        # The field roles come from the reader, not a second source extractor.
        # This source quote supplies the unchanged existing route port evidence.
        quote = by_unit[origin['unit_id']]['text']
        add_edge('route', ['origin', 'destination'], {'status': 'stated', 'value': None}, origin['unit_id'], quote)
    else:
        add_edge('route', [], {'status': 'unknown', 'value': None}, origin['unit_id'], origin['quote'])
    if plan['name'] == 'columns':
        fields = ['bag_unit_ids', 'bag_quotes', *plan['port_binding']]
        counts = {len(value[field]) for field in fields}
        if len(counts) != 1:
            raise ValueError('Frozen program arrays are unaligned; no truncation')
        bags = [{'unit_id': value['bag_unit_ids'][i], 'quote': value['bag_quotes'][i],
                 **{field: value[field][i] for field in plan['port_binding']}}
                for i in range(len(value['bag_quotes']))]
    else:
        bags = value['bags']
    for i, bag in enumerate(bags):
        identity = 'bag:' + str(i)
        add_node(identity, 'bag', 'unspecified', bag['unit_id'], bag['quote'])
        for field, predicate in plan['port_binding'].items():
            data = deepcopy(bag[field])
            if predicate == 'weight' and plan.get('weight_codec') and data['status'] == 'stated':
                groups = [g for g in plan['weight_codec']['groups'] if data['value'] == g['code']]
                if len(groups) != 1:
                    raise ValueError('Weight is not in the fixed program-generated alphabet')
                representative = min(groups[0]['members'])
                constructions.append({'bag': identity, 'encoded': data['value'],
                                      'consumer_representative': representative,
                                      'not_a_literal_source_weight_claim': True})
                data['value'] = representative
            add_edge(predicate, [identity], data, bag['unit_id'], bag['quote'])
    result = {'nodes': nodes, 'relations': relations,
              'scope_complete': value['inventory_complete'], 'unresolved': list(value['unresolved'])}
    return result, {'decoder': plan['production_decoder'], 'consumer_constructions': constructions,
                    'port_signature': plan['fixed_program_input_contract'],
                    'fixed_library_sha256': plan['fixed_library_sha256']}
