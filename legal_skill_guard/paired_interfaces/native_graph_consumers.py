"""Project literal-rich graphs into the existing frozen legal programs.

Only supplied graph assertions enter factual ports. Native public context
provides the question, explicit task assumptions, solved regime and wire family.
No benchmark grading, original case Prolog, or stored native query is loaded.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys

import jsonschema

from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[2]
BOOLEAN_PORTS = ('asset_is_personal_nonbusiness_property', 'asset_is_federal_household_category',
    'asset_is_personal_tangible_property', 'asset_is_wearing_apparel',
    'asset_is_arizona_wearing_apparel', 'asset_is_arizona_household_good_or_appliance')
CONCEPT_FAMILIES = {'service': 'service_', 'employment': 'service_', 'domestic_service': 'service_',
    'agricultural_labor': 'service_', 'payment': 'payment_', 'marriage': 'marriage_',
    'residence': 'residence_', 'enrollment': 'enrollment_', 'hospital': 'hospital_',
    'university': 'educational_institution_', 'medical_patient': 'medical_patient_',
    'income': 'income_'}


def native_family(node):
    if node['concept'] in ('hospital', 'university'):
        return CONCEPT_FAMILIES[node['concept']] if node['kind'] in ('organization', 'place') else None
    return CONCEPT_FAMILIES.get(node['concept']) if node['kind'] == 'event' else None


def unsupported(reason, **extra):
    return {'handled': False, 'answer': None, 'reason': reason,
            'native_grading_oracle_used': False, 'new_model_requests': 0, **extra}


def money(value):
    if type(value) in (int, float):
        return value
    if isinstance(value, str) and re.fullmatch(r'\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?', value):
        from decimal import Decimal
        result = Decimal(value.replace('$', '').replace(',', ''))
        return int(result) if result == result.to_integral() else float(result)
    return None


def value_of(edge, nodes):
    if edge['value'] is not None:
        return edge['value']
    if len(edge['arguments']) == 2:
        target = nodes[edge['arguments'][1]]
        if target['kind'] in ('time', 'information'):
            return target['name']
    return None


def partial_skill(skill, inputs, domains, *, max_worlds=4096):
    from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
    validate_procedure(skill['procedure'])
    if any(row['mode'] != 'constant' for row in skill['premises'].values()):
        return unsupported('The preserved program has unresolved premises')
    if type(max_worlds) is not int or not 1 <= max_worlds <= 20000:
        raise ValueError('Declare the bounded finite partial execution work')
    payload = {'procedure': skill['procedure'], 'inputs': inputs, 'domains': domains,
        'max_worlds': max_worlds, 'premises': {k: v['value'] for k, v in skill['premises'].items()}}
    raw = subprocess.run([sys.executable, '-B', '-m',
        'legal_skill_guard.paired_interfaces.partial_consumer_worker'], input=json.dumps(payload),
        text=True, capture_output=True, cwd=ROOT, timeout=30)
    if raw.returncode:
        return unsupported('Finite partial program execution failed', error=raw.stderr[-1600:])
    result = strict_json(raw.stdout)
    return {**result, 'frozen_program_sha256': digest(skill['procedure']),
            'original_partial_inputs_sha256': digest(inputs), 'native_grading_oracle_used': False,
            'new_model_requests': 0, 'model_or_source_semantics_certified': False}


def oe_inputs(graph, public, output_family):
    if output_family not in ('EC', 'EV'):
        return unsupported('Unknown native output family')
    graph, _ = normalize_numeric_ports(graph)
    nodes = {node['id']: node for node in graph['nodes']}
    assets = [node for node in graph['nodes'] if node['kind'] == 'asset']
    if not assets or not graph['scope_complete']:
        return unsupported('The supplied graph lacks a complete asset inventory')
    text = public.get('original_input', '')
    prefix, delimiter, _ = text.partition('\nFacts:\n')
    if not delimiter:
        return unsupported('No explicit public facts/solved-regime boundary')
    solved = prefix.split('Solved Reasoning Steps:', 1)[-1] if 'Solved Reasoning Steps:' in prefix else ''
    match = re.findall(r'may claim property exemptions under (Illinois|Federal and Wisconsin|Federal and Pennsylvania|Arizona|Federal and Arizona) statutes', solved)
    if len(match) != 1:
        return unsupported('The exact public solved regime is missing or ambiguous')
    people = {node['id'] for node in graph['nodes'] if node['kind'] == 'person'}
    members = {edge['arguments'][0] for edge in graph['relations']
        if edge['predicate'] == 'member_of' and edge['status'] == 'stated'
        and len(edge['arguments']) == 2 and edge['arguments'][0] in people
        and nodes[edge['arguments'][1]]['kind'] == 'group'
        and re.search(r'\bdebtors?\b', nodes[edge['arguments'][1]]['name'], re.I)}
    if not members:
        return unsupported('Debtor count is not represented in the graph')
    descriptions = [node['name'] for node in assets]
    if len(set(descriptions)) != len(descriptions):
        return unsupported('Two assets have indistinguishable literal output descriptions')
    result = {'asset_descriptions': descriptions, 'asset_values': [], 'governing_regime': match[0],
        'number_of_debtors': len(members), 'output_family': output_family,
        **{key: [] for key in BOOLEAN_PORTS}}
    domains = []
    explicit_personal_default = ('Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.' in prefix)
    for index, node in enumerate(assets):
        relevant = [edge for edge in graph['relations'] if edge['arguments'] and edge['arguments'][0] == node['id']]
        amounts = [money(value_of(edge, nodes)) for edge in relevant
                   if edge['predicate'] == 'amount' and edge['status'] == 'stated']
        if len(amounts) != 1 or amounts[0] is None or amounts[0] < 0:
            return unsupported('An asset amount is absent, ambiguous or not a currency number')
        result['asset_values'].append(amounts[0])
        flags = {key: set() for key in BOOLEAN_PORTS}
        for edge in relevant:
            if edge['predicate'] != 'category' or edge['value'] not in flags:
                continue
            if edge['status'] in ('stated', 'negated'):
                flags[edge['value']].add(edge['status'] == 'stated')
        contrary_use = any(edge['predicate'] == 'category' and edge['status'] == 'stated'
                           and edge['value'] in ('business_use', 'business_property', 'nonpersonal_use')
                           for edge in relevant)
        personal_use = explicit_personal_default and not graph['unresolved'] and not contrary_use
        if personal_use and node['concept'] in ('household_good', 'wearing_apparel'):
            flags['asset_is_federal_household_category'].add(True)
            flags['asset_is_personal_tangible_property'].add(True)
        if personal_use and node['concept'] == 'household_good':
            flags['asset_is_arizona_household_good_or_appliance'].add(True)
        if personal_use and node['concept'] == 'wearing_apparel':
            flags['asset_is_wearing_apparel'].add(True)
            flags['asset_is_arizona_wearing_apparel'].add(True)
        if personal_use and node['concept'] == 'personal_tangible_property':
            flags['asset_is_personal_tangible_property'].add(True)
        # This task default is applied only with an explicit closed graph and
        # no unread contrary description, never to override an unknown claim.
        if personal_use:
            flags['asset_is_personal_nonbusiness_property'].add(True)
        for key, values in flags.items():
            if len(values) > 1:
                return unsupported('Conflicting asserted asset categories', port=key)
            value = next(iter(values)) if values else None
            result[key].append(value)
            if value is None:
                domains.append({'path': [key, index], 'values': [False, True]})
    return {'handled': True, 'inputs': result, 'domains': domains,
            'literal_output_descriptions_are_reader_values': True,
            'no_other_view_or_grading_used': True}


def openexempt(graph, public, output_family):
    inputs = oe_inputs(graph, public, output_family)
    if not inputs['handled']:
        return inputs
    result = partial_skill(module_assets('OpenExempt')['skill'], inputs['inputs'], inputs['domains'])
    return {**result, 'graph_port_projection': inputs,
            'learned_native_main_path_executed': result['handled'], 'fallback_executed': False}


def sara_binding(graph):
    """Project assertions; a payment never becomes income/employment/cash."""
    graph, _ = normalize_numeric_ports(graph)
    nodes = {node['id']: node for node in graph['nodes']}
    facts, negatives, properties, problems = [], [], set(), []
    def add(predicate, args):
        row = {'predicate': predicate, 'arguments': args}
        if row not in facts:
            facts.append(row)
    for node in graph['nodes']:
        if native_family(node):
            add(native_family(node), [node['id']])
        elif node['concept'] in CONCEPT_FAMILIES:
            problems.append('A native event/type has no compatible typed referent')
        if node['concept'] in ('domestic_service', 'agricultural_labor'):
            add('type_', [node['id'], node['concept'].replace('_', ' ')])
            properties.add((node['id'], 'type_'))
    from legal_skill_guard.skill_evolution.sara_statute_kernel import GIVENS, literal_date
    for edge in graph['relations']:
        args, predicate, status = edge['arguments'], edge['predicate'], edge['status']
        if predicate == 'native_factual_given':
            if status not in ('stated', 'negated'):
                continue
            try:
                row = strict_json(edge['value'])
                if set(row) != {'predicate', 'arguments'}:
                    raise ValueError('A literal native factual record needs explicit typed arguments')
                # Referent positions survive graph variable renaming. Literal
                # numbers/strings remain read values, not source lookups.
                row['arguments'] = [args[v['node_argument']] if isinstance(v, dict)
                    and set(v) == {'node_argument'} and type(v['node_argument']) is int
                    and 0 <= v['node_argument'] < len(args) else v for v in row['arguments']]
                if status == 'negated':
                    if row['predicate'] not in GIVENS:
                        raise ValueError('Negated primitive facts are not closed-world absence')
                    negatives.append(row)
                else:
                    add(row['predicate'], row['arguments'])
            except (ValueError, TypeError) as error:
                problems.append(str(error))
            continue
        if not args or status != 'stated':
            continue
        source = nodes[args[0]]
        family = native_family(source)
        port = None
        if predicate in ('worker', 'payer', 'actor', 'subject'):
            port = 'agent_'
        elif predicate == 'payee':
            port = 'patient_'
        elif predicate in ('recipient', 'employer') and family == 'service_':
            port = 'patient_'
        elif predicate == 'object' and family in ('marriage_', 'enrollment_'):
            port = 'patient_'
        elif predicate == 'service_link' and family == 'payment_':
            port = 'purpose_'
        elif predicate in ('date_start', 'date_end'):
            value = literal_date(value_of(edge, nodes))
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                problems.append('An incomplete date is not a complete native day')
                continue
            port = 'start_' if predicate == 'date_start' else 'end_'
            add(port, [args[0], value]); properties.add((args[0], port))
            continue
        elif predicate == 'amount':
            value = money(value_of(edge, nodes))
            carriers = [args[0]] if family is not None else [other['arguments'][0]
                for other in graph['relations'] if other['predicate'] == 'object'
                and other['status'] == 'stated' and len(other['arguments']) == 2
                and other['arguments'][1] == args[0]
                and native_family(nodes[other['arguments'][0]]) in ('payment_', 'income_')]
            if value is not None and len(carriers) == 1:
                add('amount_', [carriers[0], value]); properties.add((carriers[0], 'amount_'))
            continue
        if port and len(args) == 2 and family is not None:
            add(port, [args[0], args[1]]); properties.add((args[0], port))
    # No whole-case closure is ever inferred from the generic graph ontology.
    # Only its explicitly closed mapped families can support finite absence.
    closed = graph['scope_complete'] and not graph['unresolved'] and not problems
    closed = closed and not any(e['status'] in ('unknown', 'unread') for e in graph['relations'])
    scans = sorted(set(CONCEPT_FAMILIES.values())) if closed else []
    referents = {row['arguments'][0] for row in facts if len(row['arguments']) == 1}
    properties = {(event, port) for event, port in properties if event in referents}
    uncertain_ports = {'worker': 'agent_', 'payer': 'agent_', 'actor': 'agent_', 'subject': 'agent_',
        'payee': 'patient_', 'recipient': 'patient_', 'employer': 'patient_', 'object': 'patient_',
        'date_start': 'start_', 'date_end': 'end_', 'amount': 'amount_', 'service_link': 'purpose_'}
    for edge in graph['relations']:
        if edge['arguments'] and edge['status'] in ('unknown', 'unread', 'negated'):
            properties.discard((edge['arguments'][0], uncertain_ports.get(edge['predicate'])))
    return {'binding': {'facts': facts, 'negative_givens': negatives, 'extraction_status': 'unread'},
        'scope_contract': {'family_scans': scans,
            'event_properties': [{'event': event, 'predicate': port} for event, port in sorted(properties)]},
        'projection_problems': problems, 'missing_roles_dates_and_givens_not_filled': True}


def sara_query(question, graph):
    """Public question ABI, with graph identities rather than original case IDs.

    This compiles a bounded literal question grammar. Unsupported or ambiguous
    queries remain unsupported; no stored benchmark query/fact is consulted.
    """
    from legal_skill_guard.rr.legal_case_grounding import citation
    authority = citation(question)
    root = 's' + authority.replace('(', '_').replace(')', '') if authority else ''
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', question))
    if len(years) != 1:
        return unsupported('Public query needs one explicit calendar year')
    year, variable = int(next(iter(years))), {'variable': '_'}
    def stated_in_year(identity):
        nodes = {n['id']: n for n in graph['nodes']}
        values = [value_of(edge, nodes) for edge in graph['relations']
            if edge['arguments'] and edge['arguments'][0] == identity and edge['status'] == 'stated'
            and edge['predicate'] in ('date_at', 'date_start')]
        return any(str(year) in re.findall(r'\b\d{4}\b', str(value)) for value in values)
    people = []
    for node in graph['nodes']:
        if node['kind'] != 'person':
            continue
        words = re.findall(r'\b[A-Z][a-z]+\b', node['name'])
        hits = [m.start() for word in words for m in re.finditer(r'\b' + re.escape(word) + r'\b', question)]
        if hits:
            people.append((min(hits), node['id']))
    people.sort()
    if len({position for position, identity in people}) != len(people):
        return unsupported('Public person identity is ambiguous in the read graph')
    person = people[0][1] if people else None
    money_claims = re.findall(r'\$([\d,]+)', question)
    amount = int(money_claims[0].replace(',', '')) if len(money_claims) == 1 else None
    args = None
    if root in ('s3306_a_1', 's63_f_2_A') and person:
        args = [person, year]
    elif root == 's3306_a_2_A' and person:
        args = [person, year, variable, variable]
    elif root == 's68_f':
        args = [year]
    elif root in ('s63_c_6_A', 's152_b_1') and person:
        args = [person, *([variable, variable] if root == 's63_c_6_A' else [variable]), year]
    elif root in ('s7703_a_2', 's2_a_1_A') and person:
        args = [person, variable, variable, variable, year]
    elif root == 's63_c_3' and person and amount is not None:
        args = [person, amount, year]
    elif root == 's63_c_7_ii' and amount is not None:
        args = [year, amount]
    elif root == 's151_d_2' and person and amount is not None:
        args = [person, variable, amount, year]
    elif root == 's151_d_3_B' and person:
        claim = re.search(r'equal to (\d+)\.?$', question)
        if claim:
            args = [int(claim[1]), person, variable, year, variable]
    elif root in ('s152_c_1', 's151_c') and len(people) == 2:
        args = [people[0][1], people[1][1], *([variable] if root == 's151_c' else []), year]
    elif root in ('s63_d', 's63_c_5') and person:
        args = [person, variable, variable, year, *([variable] if root == 's63_c_5' else [])]
    elif root.startswith('s3306_'):
        binding = sara_binding(graph)['binding']['facts']
        def values(predicate, identity):
            return [row['arguments'][1] for row in binding
                if row['predicate'] == predicate and row['arguments'][0] == identity]
        services = [node['id'] for node in graph['nodes'] if native_family(node) == 'service_']
        payments = [node['id'] for node in graph['nodes'] if native_family(node) == 'payment_']
        if len(people) >= 2 and 'employing' in question:
            services = [event for event in services if people[1][1] in values('agent_', event)]
        elif person:
            services = [event for event in services if person in values('agent_', event)]
        event = services[0] if len(services) == 1 else None
        starts = values('start_', event) if event else []
        query_days = [day for day in starts if str(day).startswith(str(year) + '-')]
        day = query_days[0] if len(query_days) == 1 else None
        if root in ('s3306_c_1', 's3306_c_2') and event:
            args = [event, *([variable] if root == 's3306_c_2' else []), year]
        elif root == 's3306_c_5' and len(people) == 2 and event and day:
            args = [event, people[0][1], people[1][1], day]
        elif root == 's3306_c_21' and person and event and day:
            args = [event, person, variable, day]
        elif root in ('s3306_c_10_A_i', 's3306_c_10_A') and person and event and day:
            recipients = values('patient_', event)
            if len(recipients) == 1:
                args = [person, recipients[0], day] if root.endswith('_i') else [event, recipients[0], person, day]
        elif root == 's3306_b_10_A':
            payments = [event for event in payments if stated_in_year(event)]
            if person:
                payments = [event for event in payments if person in values('agent_', event)]
            if amount is not None:
                payments = [event for event in payments if amount in values('amount_', event)]
            if len(payments) == 1:
                args = [payments[0], variable, variable, variable, variable, variable]
        elif root == 's3306_b' and len(payments) == 1:
            payment = payments[0]
            links = values('purpose_', payment)
            if len(links) == 1 and stated_in_year(payment):
                args = [variable, payment, links[0], variable, variable, variable, variable, variable]
    elif root.startswith('s1_') and amount is not None and person:
        binding = sara_binding(graph)['binding']['facts']
        income_events = [row['arguments'][0] for row in binding if row['predicate'] == 'income_']
        incomes = [row['arguments'][1] for row in binding if row['predicate'] == 'amount_'
            and row['arguments'][0] in income_events
            and stated_in_year(row['arguments'][0])
            and {'predicate': 'agent_', 'arguments': [row['arguments'][0], person]} in binding]
        if len(incomes) == 1:
            args = [incomes[0], amount]
    if args is None:
        return unsupported('Public native query is outside the current literal ABI grammar', query_root=root)
    queries = [{'predicate': root, 'arguments': args}]
    if root == 's3306_c_10_A_i':
        queries.insert(0, {'predicate': 's3306_c_10_A', 'arguments': [event, args[1], person, args[2]]})
    return {'handled': True, 'query': queries,
            'public_question_only_and_read_entity_ids': True,
            'original_case_query_or_expected_polarity_loaded': False}


def sara(graph, public, *, query=None):
    assets = module_assets('SARA_v2_Binary')
    projection = sara_binding(graph)
    compiled = sara_query(public['question'], graph) if query is None else {'handled': True, 'query': query}
    if not compiled['handled']:
        return {**compiled, 'graph_port_projection': projection}
    template = deepcopy(assets['statute_kernel_template'])
    template.update(native_query=compiled['query'], name='+'.join(q['predicate'] for q in compiled['query']))
    targets = {q['predicate'] for q in compiled['query']}
    if any(row['predicate'] in targets for row in projection['binding']['facts'] + projection['binding']['negative_givens']):
        return unsupported('A target query cannot be asserted as an extracted factual given')
    from legal_skill_guard.skill_evolution.partial_native_proof import execute
    try:
        result = execute(template, projection['binding'], [], public,
                         scope_contract=projection['scope_contract'])
    except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
        return unsupported('Graph facts/query are outside the guarded native ABI',
                           error=type(error).__name__ + ': ' + str(error), graph_port_projection=projection)
    return {**result, 'graph_port_projection': projection, 'public_query_compilation': compiled,
        'native_grading_oracle_used': False, 'original_case_query_or_facts_loaded': False,
        'new_model_requests': 0, 'fallback_executed': False,
        'learned_native_main_path_executed': result['handled']}


def airline(graph):
    """Consume numeric ports in source bag order; never infer unread values."""
    if not graph['scope_complete'] or graph['unresolved']:
        return unsupported('The bag inventory/attributes remain unresolved')
    graph, _ = normalize_numeric_ports(graph)
    bags = [node for node in graph['nodes'] if node['kind'] == 'bag']
    positions = [node.get('source_order') for node in bags]
    if (not bags or any(type(p) is not int for p in positions)
            or len(set(positions)) != len(positions)):
        return unsupported('Source bag order is missing or ambiguous')
    bags.sort(key=lambda node: node['source_order'])
    values = {name: [] for name in ('item_lengths', 'item_widths', 'item_heights', 'item_weights')}
    for node in bags:
        for predicate, field in (('length', 'item_lengths'), ('width', 'item_widths'),
                                 ('height', 'item_heights'), ('weight', 'item_weights')):
            edges = [edge for edge in graph['relations'] if edge['predicate'] == predicate
                     and edge['arguments'] and edge['arguments'][0] == node['id']]
            if (len(edges) != 1 or edges[0]['status'] != 'stated'
                    or type(edges[0]['value']) not in (int, float) or edges[0]['value'] < 0):
                return unsupported('Missing or ambiguous bag measurement: ' + predicate)
            values[field].append(edges[0]['value'])
    prices = [edge for edge in graph['relations'] if edge['predicate'] == 'ticket_price']
    if len(prices) != 1 or prices[0]['status'] != 'stated' or type(prices[0]['value']) is not int:
        return unsupported('Missing or ambiguous ticket price')
    cabins = {'Main Cabin', 'Basic Economy', 'Main Plus', 'Premium Economy', 'Business', 'First'}
    cabin_values = {node['concept'] for node in graph['nodes'] if node['concept'] in cabins}
    cabin_values.update(edge['value'] for edge in graph['relations'] if edge['predicate'] == 'cabin'
                        and edge['status'] == 'stated' and edge['value'] in cabins)
    routes = [edge for edge in graph['relations'] if edge['predicate'] == 'route']
    if not routes or any(edge['status'] != 'stated' for edge in routes) or len(cabin_values) != 1:
        return unsupported('Missing or ambiguous route/cabin')
    regions = {edge['value'] for edge in routes if edge['value'] is not None}
    if not regions:
        from legal_skill_guard.paired_interfaces.native_adapters import route_region
        region = route_region(graph)  # Only the reader's literal route quote is parsed.
    elif len(regions) == 1:
        region = next(iter(regions))  # An asserted region is never corrected from a quote.
    else:
        return unsupported('Conflicting asserted route regions')
    if region not in ('domestic_us', 'south_america_other', 'east_asia'):
        return unsupported('Route is outside the preserved learned program domain')
    values.update(ticket_price=prices[0]['value'], cabin_class=next(iter(cabin_values)), route_fee_region=region)
    from legal_skill_guard.paired_interfaces.control_tools import execute_skill
    result = execute_skill(module_assets('RuleArena_Airline')['skill'], values)
    return {**result, 'graph_port_projection': values, 'fallback_executed': False,
            'learned_native_main_path_executed': result['handled']}
