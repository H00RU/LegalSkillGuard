"""Source-local graph interface shared by reference annotation and paid reads.

Node identities are transported through supplied source units and literal
anchors. Native answers and benchmark label strings are not interface fields.
"""
from __future__ import annotations

from copy import deepcopy
import re

from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

KINDS = ('person', 'organization', 'group', 'asset', 'bag', 'event', 'effect',
         'exception', 'condition', 'definition', 'place', 'information', 'time')
CONCEPTS = (
    'unspecified', 'receiving_party', 'disclosing_party', 'either_party', 'own_employees',
    'affiliate_employees', 'legal_advisors', 'financial_advisors', 'consultants', 'agents',
    'contractors', 'other_third_parties', 'permission', 'prohibition', 'obligation',
    'disclosure', 'return', 'destruction', 'retention', 'confidential_information',
    'all_confidential_information_and_copies', 'some_confidential_information',
    'termination', 'request', 'termination_or_request', 'termination_and_request',
    'written_consent', 'need_to_know', 'unconditional', 'ordinary_course_covenant',
    'negative_interim_covenant', 'knowledge_definition', 'explicit_actual_wording',
    'no_inquiry_required', 'reasonable_inquiry_required', 'due_inquiry_required',
    'constructive_imputation', 'pandemic', 'epidemic', 'covid_19', 'public_health_emergency',
    'other_disruption', 'service', 'employment', 'payment', 'cash', 'noncash',
    'agricultural_labor', 'domestic_service', 'enrollment', 'student', 'university',
    'hospital', 'medical_patient', 'marriage', 'residence', 'kinship', 'income',
    'wearing_apparel', 'household_good', 'personal_tangible_property', 'other_asset',
    'checked_bag', 'carry_on_bag', 'personal_item', 'domestic_us', 'south_america_other',
    'east_asia', 'other_route', 'Main Cabin', 'Basic Economy', 'Main Plus',
    'Premium Economy', 'Business', 'First',
)
PREDICATES = (
    'actor', 'recipient', 'member_of', 'owner', 'action', 'information', 'trigger',
    'exception_for', 'condition', 'standard', 'worker', 'employer', 'payer', 'payee',
    'service_link', 'date_start', 'date_end', 'date_at', 'amount', 'weight',
    'length', 'width', 'height', 'quantity', 'category', 'domicile', 'petition_date',
    'route', 'cabin', 'ticket_price', 'subject', 'object', 'native_factual_given',
)
STATUSES = ('stated', 'negated', 'not_stated', 'unknown', 'unread')


def schema():
    node = record_schema({'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': list(KINDS)},
        'concept': {'type': 'string', 'enum': list(CONCEPTS)}, 'name': {'type': 'string'},
        'unit_id': {'type': 'integer'}, 'quote': {'type': 'string'}})
    relation = record_schema({'predicate': {'type': 'string', 'enum': list(PREDICATES)},
        'arguments': {'type': 'array', 'items': {'type': 'string'}},
        'value': {'type': ['string', 'number', 'boolean', 'null']},
        'status': {'type': 'string', 'enum': list(STATUSES)},
        'unit_id': {'type': 'integer'}, 'quote': {'type': 'string'}})
    return record_schema({'nodes': {'type': 'array', 'items': node},
        'relations': {'type': 'array', 'items': relation},
        'scope_complete': {'type': 'boolean'}, 'unresolved': {'type': 'array', 'items': {'type': 'string'}}})


def source_units(source, view):
    public = view['public']
    field = 'facts' if source['dataset'] in ('SARA_v2_Binary', 'RuleArena_Airline') else 'source_text'
    if source['dataset'] == 'OpenExempt':
        # Native EC and EV remain separate; reference annotation and factual
        # reading see only the current view's Facts, never construction gold.
        text = public['original_input']
        if '\nFacts:\n' not in text:
            raise ValueError('Native OpenExempt facts boundary is missing')
        text = text.split('\nFacts:\n', 1)[1].split('\n\nOutput contract:', 1)[0]
        field = 'facts'
    else:
        text = public[field]
    if field == 'source_text' and 'sentence_spans' in public:
        cuts = public['sentence_spans']
    else:
        starts = [0] + [m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])|\n\s*\n', text)]
        cuts = list(zip(starts, starts[1:] + [len(text)]))
    units = [{'id': i, 'field': field, 'start': a, 'end': b, 'text': text[a:b]}
             for i, (a, b) in enumerate(cuts) if text[a:b].strip()]
    # Retain nonempty gaps left by the supplied native sentence spans.
    covered, cursor = [], 0
    for unit in units:
        if unit['start'] > cursor and text[cursor:unit['start']].strip():
            covered.append({'field': field, 'start': cursor, 'end': unit['start'], 'text': text[cursor:unit['start']]})
        covered.append(unit)
        cursor = unit['end']
    if cursor < len(text) and text[cursor:].strip():
        covered.append({'field': field, 'start': cursor, 'end': len(text), 'text': text[cursor:]})
    return [{**unit, 'id': i} for i, unit in enumerate(covered)]


SYSTEM = '''Read the supplied source units into the requested typed local graph.
The graph describes source entities, events, operative effects and their actual relationships.
Every node needs a short literal name and a contiguous quote from its supplied unit.
Every relation needs a contiguous source quote. Preserve actor/recipient, worker/employer,
separate events, and which obligation an exception modifies. Use the declared concepts
as semantic tags, with the literal name retaining the source wording. An institution
or workplace is not automatically an employer. A service period is not a payment date.
Keep unknown, not_stated, negated and unread distinct. A missing date remains unknown
or not_stated; neither the question nor a statutory possibility creates a case fact.
For contracts, permission/prohibition/obligation nodes link by action to the action node,
by actor to the acting party, by recipient to the recipient class, and by information
to the protected material. Conditions and exception attachments are separate edges.
For MAUD, identify the actual covenant or definition and attach each exception/inquiry
condition to its own scope. Mere mention of a pandemic does not establish an exception.
For bags and assets, tie measurements, amounts, owner and category to their named item.
Return no native task answer, fee total, exemption allocation or hypothesis label.
Mark scope_complete only for the source-local ontology actually covered. List anything
that this ontology or your reading leaves unresolved. Return the requested JSON.'''


def validate(value, units):
    import jsonschema
    jsonschema.validate(value, schema())
    by_unit = {u['id']: u for u in units}
    names = [n['id'] for n in value['nodes']]
    if len(set(names)) != len(names):
        raise ValueError('Graph node IDs must be unique')
    ids = set(names)
    for node in value['nodes']:
        unit = by_unit.get(node['unit_id'])
        if not unit or not node['quote'] or node['quote'] not in unit['text']:
            raise ValueError('A graph node lacks contiguous current-source evidence')
        if not node['name'] or node['name'] not in node['quote']:
            raise ValueError('Graph node names are literal source anchors')
    for edge in value['relations']:
        unit = by_unit.get(edge['unit_id'])
        if not unit or not edge['quote'] or edge['quote'] not in unit['text']:
            raise ValueError('A graph relation lacks contiguous current-source evidence')
        if not set(edge['arguments']) <= ids:
            raise ValueError('Relation references an unobserved node')
        if edge['status'] in ('not_stated', 'unknown', 'unread') and edge['value'] is not None:
            raise ValueError('Unknown or unstated values cannot carry guessed factual values')
    return {'schema_and_source_spans_valid': True, 'source_semantic_truth_verified': False,
            'nodes': len(value['nodes']), 'relations': len(value['relations'])}


def columns_schema():
    base = schema()
    result = {}
    for group in ('nodes', 'relations'):
        item = base['properties'][group]['items']
        result[group] = record_schema({name: {'type': 'array', 'items': spec}
                                      for name, spec in item['properties'].items()})
    result.update({name: base['properties'][name] for name in ('scope_complete', 'unresolved')})
    return record_schema(result)


def decode_columns(value):
    result = {k: deepcopy(value[k]) for k in ('scope_complete', 'unresolved')}
    for group in ('nodes', 'relations'):
        columns = value[group]
        sizes = {len(values) for values in columns.values()}
        if len(sizes) != 1:
            raise ValueError('Unaligned graph columns are unresolved, never zip-truncated')
        result[group] = [dict(zip(columns, row)) for row in zip(*columns.values())]
    return result


def plans(weight_interface=None):
    base = {'name': 'columns', 'schema': columns_schema(), 'system': SYSTEM + '\nUse parallel columns in source occurrence order.',
            'operation': 'baseline_columns'}
    anchored = {'name': 'records', 'schema': schema(), 'system': SYSTEM + '\nKeep every linked tuple on its own source-anchored record.',
                'operation': 'binding_reification', 'paired_decoder': 'exact keyed record/column inverse'}
    local = {'name': 'local_records', 'schema': schema(), 'system': SYSTEM + '\nWalk each source unit in order. Resolve each local actor, object and exception attachment before moving to another unit.',
             'operation': 'same_semantic_partition_local_reencoding'}
    if weight_interface is not None:
        feature = next(f for f in weight_interface['features'] if f['operation'] == 'residual_bucket')
        groups = feature['groups']
        instructions = ['For a stated weight in integer pounds 0..100, encode the weight relation value with these source-local codes:']
        instructions.extend(g['code'] + ' for integers ' + str(min(g['members'])) + '..' + str(max(g['members'])) for g in groups)
        instructions.append('Weights outside that declared domain remain unknown. Preserve the literal source quote; do not calculate a fee.')
        local['system'] += '\n' + '\n'.join(instructions)
        local['operation'] = 'residual_value_partition_and_binding_reification'
        local['weight_codec'] = {'groups': groups, 'module_binding': weight_interface['module_binding'],
                                 'certificate': weight_interface['certificate'],
                                 'fixed_consumer_sha256': weight_interface['fixed_consumer_sha256']}
    for plan in (base, anchored, local):
        plan['version'] = digest(plan)
    return [base, anchored, local]


def decode_plan(plan, value):
    graph = decode_columns(value) if plan['name'] == 'columns' else deepcopy(value)
    constructions = []
    codec = plan.get('weight_codec')
    if codec:
        for edge in graph['relations']:
            if edge['predicate'] != 'weight' or edge['status'] != 'stated':
                continue
            groups = [g for g in codec['groups'] if g['code'] == edge['value']]
            if len(groups) != 1:
                raise ValueError('The residual weight reader must return one declared encoding')
            representative = min(groups[0]['members'])
            constructions.append({'source_arguments': edge['arguments'], 'encoded': edge['value'],
                                   'consumer_representative': representative,
                                   'not_a_claim_of_literal_source_weight': True})
            edge['value'] = representative
    return graph, {'paired_decoder': plan.get('paired_decoder', plan['operation']),
                    'consumer_constructions': constructions}
