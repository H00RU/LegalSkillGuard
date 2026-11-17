"""Compile the three existing layout families from frozen OpenExempt F ports.

The local-record family uses exact public-context residualization. Unknown
attributes retain explicit states; source declarations are never converted to
invented group membership or statutory exemption answers.
"""
import ast
from copy import deepcopy
import math
import re

import jsonschema

from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill, unsupported
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


STATES = ['stated', 'negated', 'not_stated', 'unknown', 'unread']


def frozen_skill():
    return module_assets('OpenExempt')['skill']


def regimes(skill):
    values = set()
    for node in ast.walk(ast.parse(skill['procedure'])):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        left = node.left
        if (isinstance(left, ast.Subscript) and isinstance(left.value, ast.Name) and left.value.id == 'inputs'
                and isinstance(left.slice, ast.Constant) and left.slice.value == 'governing_regime'
                and isinstance(node.comparators[0], ast.Constant) and isinstance(node.comparators[0].value, str)):
            values.add(node.comparators[0].value)
    if not values:
        raise ValueError('The frozen program declares no static public regime branches')
    return sorted(values)


def context_from_public(public):
    prefix, separator, _ = public.get('original_input', '').partition('\nFacts:\n')
    if not separator:
        raise ValueError('An explicit public facts boundary is required')
    solved = prefix.split('Solved Reasoning Steps:', 1)[-1] if 'Solved Reasoning Steps:' in prefix else ''
    matches = list(re.finditer(r'may claim property exemptions under ([A-Za-z][A-Za-z &-]{1,100}) statutes', solved))
    if len(matches) != 1:
        raise ValueError('The exact public solved regime is absent or ambiguous')
    assumption = 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'
    return {'governing_regime': matches[0].group(1), 'public_regime_quote': matches[0].group(0),
            'supported_by_frozen_legal_program': matches[0].group(1) in regimes(frozen_skill()),
            'public_task_assumptions': [assumption] if assumption in prefix else [],
            'source': 'explicit public solved context;not a predicted answer'}


def cell(schema):
    return record_schema({'value': schema, 'status': {'type': 'string', 'enum': STATES}})


def compile_plans(locked, regime):
    skill = frozen_skill()
    if regime not in regimes(skill):
        raise ValueError('The public context is outside the fixed program branches')
    residual = specialize(skill['procedure'], {'governing_regime': regime},
                          allowed_context_fields={'governing_regime'})
    fields = skill['inputs']
    arrays = sorted(name for name, port in fields.items() if port['type'] == 'array')
    if set(fields) - set(arrays) != {'governing_regime', 'number_of_debtors', 'output_family'}:
        raise ValueError('The declared frozen global input contract changed')
    booleans = {name for name in arrays if name.startswith('asset_is_')}
    if set(arrays) - booleans != {'asset_descriptions', 'asset_values'}:
        raise ValueError('The frozen asset-array contract needs an explicit new compiler')
    output = []
    for original in locked:
        plan = deepcopy(original)
        plan['locked_candidate_version'] = plan.pop('version')
        plan.pop('weight_codec', None)
        local = plan['name'] == 'local_records'
        requested = set(residual['input_fields'] if local else fields) - {'governing_regime', 'output_family'}
        selected_arrays = sorted(requested & set(arrays))
        aliases = {name: ('f' + str(i) if local else name) for i, name in enumerate(selected_arrays)}
        schemas = {name: cell({'type': ['boolean', 'null']} if name in booleans
                    else {'type': ['string', 'null']} if name == 'asset_descriptions'
                    else {'type': ['number', 'null'], 'minimum': 0}) for name in selected_arrays}
        scalar = {}
        if 'number_of_debtors' in requested:
            scalar['number_of_debtors'] = record_schema({**cell({'type': ['integer', 'null'], 'minimum': 1})['properties'],
                'unit_id': {'type': 'integer'}, 'quote': {'type': 'string'}})
        props = scalar
        if plan['name'] == 'columns':
            props.update(asset_unit_ids={'type': 'array', 'items': {'type': 'integer'}},
                         asset_quotes={'type': 'array', 'items': {'type': 'string'}})
            props.update({name: {'type': 'array', 'items': schemas[name]} for name in selected_arrays})
        else:
            row = {'unit_id': {'type': 'integer'}, 'quote': {'type': 'string'}}
            row.update({aliases[name]: schemas[name] for name in selected_arrays})
            props['assets'] = {'type': 'array', 'items': record_schema(row)}
        props.update(inventory_complete={'type': 'boolean'},
                     unresolved={'type': 'array', 'items': {'type': 'string'}})
        instructions = '''Read every current asset and only the declared factual ports from its source units.
Return no exemption citation, claim value, native EC/EV answer or legal reasoning.
Keep source order, exact asset descriptions, and each asset's own unit_id/quote.
Preserve explicit ownership/use uncertainty; possession is not legal ownership.
The public assumptions apply only as written and yield to explicit contrary facts.
For a known Boolean use its truth value; an explicitly negated attribute has value
false and status negated. Unknown, unread and not_stated values are always null;
none becomes false or zero. Missing values do not remove assets from inventory.
number_of_debtors counts explicitly identified current filing debtors, without
requiring or inventing a group node. Its evidence must be a contiguous source quote.
inventory_complete means every current asset was read, not all possible legal
facts. Use unresolved for ambiguities affecting that inventory or declared ports.
Copy dollar values and descriptions; the frozen consumer applies all laws.
The host supplies a public regime and output formatting; never infer them from
an expected answer. This reader does not receive native answers or EC/EV targets.
'''
        instructions += '\nDeclared public governing context: ' + regime + '.\nField dictionary:\n'
        for name in sorted(requested):
            instructions += aliases.get(name, name) + ' = ' + name + ': ' + fields[name]['question'] + '\n'
        if local:
            instructions += 'Unrequested attributes are outside this residual read interface; do not fabricate them.\n'
        plan.update(schema=record_schema(props), system=instructions,
            production_decoder='frozen_asset_program_ports_v1',
            public_context={'governing_regime': regime}, fixed_skill_sha256=digest(skill),
            fixed_program_sha256=digest(skill['procedure']), boolean_fields=sorted(booleans),
            array_fields=selected_arrays, field_aliases=aliases, requested_fields=sorted(requested),
            residual_program=residual if local else None,
            residual_required_fields=residual['input_fields'],
            certificate_port_reencoding={
                'from_declared_frozen_program_ports': True,
                'column_record_inverse_on_aligned_finite_arrays': True,
                'asset_order_and_unknown_states_preserved': True,
                'contextual_program_certificate': residual['certificate'] if local else None,
                'original_legal_function_and_premises_preserved': True,
                'no_source_prediction_or_native_label_used_for_compilation': True})
        plan['version'] = digest(plan)
        output.append(plan)
    return output


def decode_inputs(plan, value, units):
    if plan['fixed_skill_sha256'] != digest(frozen_skill()):
        raise ValueError('The frozen legal skill changed since port compilation')
    jsonschema.validate(value, plan['schema'])
    by_unit = {unit['id']: unit for unit in units}
    def anchor(unit, quote):
        if unit not in by_unit or not quote or by_unit[unit]['text'].count(quote) != 1:
            raise ValueError('An asset port requires one unique contiguous current-source anchor')
    def semantic(cell_value, field):
        data, status = cell_value['value'], cell_value['status']
        if status in ('unknown', 'unread', 'not_stated'):
            if data is not None:
                raise ValueError('An uncertain asset port carries a guessed value')
            return None
        if data is None:
            raise ValueError('An established asset port has no value')
        if status == 'negated' and (field not in plan['boolean_fields'] or data is not False):
            raise ValueError('Explicit negation requires a false Boolean port')
        return data
    if plan['name'] == 'columns':
        lengths = {len(value[field]) for field in ['asset_unit_ids', 'asset_quotes', *plan['array_fields']]}
        if len(lengths) != 1:
            raise ValueError('No truncation of misaligned asset arrays is permitted')
        rows = [{'unit_id': unit, 'quote': quote,
                 **{name: value[name][i] for name in plan['array_fields']}}
                for i, (unit, quote) in enumerate(zip(value['asset_unit_ids'], value['asset_quotes']))]
    else:
        rows = [{**row, **{name: row[alias] for name, alias in plan['field_aliases'].items()}}
                for row in value['assets']]
    inputs = {'governing_regime': plan['public_context']['governing_regime']}
    domains, anchors, seen = [], [], set()
    for name in plan['array_fields']:
        inputs[name] = []
    for i, row in enumerate(rows):
        anchor(row['unit_id'], row['quote'])
        identity = row['unit_id'], row['quote']
        if identity in seen:
            raise ValueError('Two assets have indistinguishable source anchors')
        seen.add(identity)
        anchors.append({'unit_id': row['unit_id'], 'quote': row['quote']})
        for name in plan['array_fields']:
            data = semantic(row[name], name)
            inputs[name].append(data)
            if data is None and name in plan['boolean_fields']:
                domains.append({'path': [name, i], 'values': [False, True]})
    if 'number_of_debtors' in plan['requested_fields']:
        data = value['number_of_debtors']
        anchor(data['unit_id'], data['quote'])
        inputs['number_of_debtors'] = semantic(data, 'number_of_debtors')
    if not value['inventory_complete'] or value['unresolved'] or not rows:
        return unsupported('The current asset port inventory is incomplete or unresolved',
                           raw_port_values_and_states_preserved=True)
    if (any(item is None or not isinstance(item, str) or not item for item in inputs['asset_descriptions'])
            or len(set(inputs['asset_descriptions'])) != len(rows)):
        return unsupported('An asset output description is missing or ambiguous')
    if any(type(item) not in (int, float) or not math.isfinite(item) or item < 0
           for item in inputs['asset_values']):
        return unsupported('An asset amount has no bounded exact factual input')
    if ('number_of_debtors' in plan['residual_required_fields']
            and (type(inputs.get('number_of_debtors')) is not int or inputs['number_of_debtors'] < 1)):
        return unsupported('A needed debtor count remains unknown; no singleton group is invented')
    return {'handled': True, 'inputs': inputs, 'domains': domains, 'asset_anchors': anchors,
            'field_statuses_remain_in_raw_read': True, 'native_grading_used': False}


def consume(plan, value, units, family):
    if family not in ('EC', 'EV'):
        return unsupported('Unknown native output family')
    projected = decode_inputs(plan, value, units)
    if not projected['handled']:
        return projected
    skill = deepcopy(frozen_skill())
    if plan['residual_program'] is not None:
        skill['procedure'] = plan['residual_program']['procedure']
    result = partial_skill(skill, {**projected['inputs'], 'output_family': family}, projected['domains'])
    return {**result, 'program_port_projection': projected,
            'paired_residual_consumer_executed': plan['residual_program'] is not None,
            'learned_native_main_path_executed': result['handled'], 'fallback_executed': False,
            'no_reference_graph_or_expected_answer_used': True}
