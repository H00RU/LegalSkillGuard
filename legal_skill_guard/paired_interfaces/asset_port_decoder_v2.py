"""Retain source-anchor ambiguity instead of forcing an asset correspondence.

Literal source quotes must occur.No field value,quote or scope bit is repaired.
Duplicate/overlapping quote supports survive for complete injective alignment
in M2;the native F consumes the actual read tuples independently of source IDs.
"""
from copy import deepcopy
import math
import re

import jsonschema

from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill, unsupported
from legal_skill_guard.skill_evolution.objects import digest


def decode(plan, value, units):
    if plan['fixed_skill_sha256'] != digest(frozen_skill()):
        raise ValueError('The frozen skill changed')
    jsonschema.validate(value, plan['schema'])
    by_unit = {unit['id']: unit for unit in units}
    supports = []
    def anchor(unit, quote):
        text = by_unit.get(unit, {}).get('text', '')
        occurrences = [match.span() for match in re.finditer(re.escape(quote), text)] if quote else []
        if not occurrences:
            raise ValueError('A port quote is not contiguous current-source evidence')
        return occurrences
    def cell(data, field):
        raw, status = data['value'], data['status']
        if status in ('unknown', 'unread', 'not_stated'):
            if raw is not None:
                raise ValueError('An unknown port cannot carry a guessed value')
        elif raw is None or status == 'negated' and (not field.startswith('asset_is_') or raw is not False):
            raise ValueError('An established/negated port has inconsistent value semantics')
        return deepcopy(data)
    if plan['name'] == 'columns':
        if len({len(value[field]) for field in ['asset_unit_ids', 'asset_quotes', *plan['array_fields']]}) != 1:
            raise ValueError('No truncation of misaligned asset arrays is permitted')
        rows = [{'unit_id': unit, 'quote': value['asset_quotes'][i],
                 'fields': {field: cell(value[field][i], field) for field in plan['array_fields']}}
                for i, unit in enumerate(value['asset_unit_ids'])]
    else:
        rows = [{'unit_id': row['unit_id'], 'quote': row['quote'],
                 'fields': {field: cell(row[alias], field) for field, alias in plan['field_aliases'].items()}}
                for row in value['assets']]
    for row in rows:
        supports.append({'unit_id': row['unit_id'], 'quote': row['quote'],
                         'all_source_spans': anchor(row['unit_id'], row['quote'])})
    globals_ = {}
    if 'number_of_debtors' in plan['requested_fields']:
        data = value['number_of_debtors']
        anchor(data['unit_id'], data['quote'])
        globals_['number_of_debtors'] = {**cell(data, 'number_of_debtors'),
                                       'unit_id': data['unit_id'], 'quote': data['quote']}
    return {'assets': rows, 'globals': globals_, 'inventory_complete': value['inventory_complete'],
            'unresolved': list(value['unresolved'])}, {
                'production_decoder': 'source_span_ambiguity_preserved_asset_ports_v2',
                'asset_anchor_supports': supports,
                'correspondences_chosen_from_reference_values': False,
                'raw_values_statuses_and_scope_bits_changed': False}


def consume(plan, record, family):
    if family not in ('EC', 'EV'):
        return unsupported('Unknown native output family')
    if not record['inventory_complete'] or record['unresolved'] or not record['assets']:
        return unsupported('The actual read declares an incomplete/unresolved asset port inventory')
    arrays, domains = {}, []
    for field in plan['array_fields']:
        arrays[field] = []
        for index, row in enumerate(record['assets']):
            data = row['fields'][field]
            value = data['value'] if data['status'] in ('stated', 'negated') else None
            arrays[field].append(value)
            if value is None and field.startswith('asset_is_'):
                domains.append({'path': [field, index], 'values': [False, True]})
    names, values = arrays['asset_descriptions'], arrays['asset_values']
    if (any(type(value) is not str or not value for value in names) or len(set(names)) != len(names)
            or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values)):
        return unsupported('An actual asset description/amount is absent or ambiguous')
    inputs = {**arrays, 'governing_regime': plan['public_context']['governing_regime'], 'output_family': family}
    if 'number_of_debtors' in record['globals']:
        cell = record['globals']['number_of_debtors']
        inputs['number_of_debtors'] = cell['value'] if cell['status'] in ('stated', 'negated') else None
    if ('number_of_debtors' in plan['residual_required_fields']
            and (type(inputs.get('number_of_debtors')) is not int or inputs['number_of_debtors'] < 1)):
        return unsupported('A required debtor count remains unknown')
    skill = deepcopy(frozen_skill())
    if plan['residual_program'] is not None:
        skill['procedure'] = plan['residual_program']['procedure']
    result = partial_skill(skill, inputs, domains)
    return {**result, 'paired_residual_consumer_executed': plan['residual_program'] is not None,
            'learned_native_main_path_executed': result['handled'], 'fallback_executed': False,
            'source_identity_uncertainty_does_not_fill_a_fact': True}
