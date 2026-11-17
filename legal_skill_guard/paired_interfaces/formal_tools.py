"""Formal-stage common law tools, including the exact OE public-context D.

All arms get this same provider. It supplies a deterministic consumer, never
M1's reader schema, a source reference, a native answer or missing facts.
Original pilot tool providers and their frozen comparisons are unchanged.
"""
from copy import deepcopy
import math

import jsonschema

from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public, frozen_skill
from legal_skill_guard.paired_interfaces.control_tools import legal_tools as original_tools
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill, unsupported
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


def legal_tools(source, bundle):
    tools, assets = original_tools(source, bundle)
    if source['dataset'] != 'OpenExempt':
        return tools, assets
    skill, contexts, specifications, residuals = frozen_skill(), {}, {}, {}
    for view in source['views']:
        context = context_from_public(view['public'])
        contexts[view['id']] = context
        if context['supported_by_frozen_legal_program']:
            residual = specialize(skill['procedure'], {'governing_regime': context['governing_regime']},
                                  allowed_context_fields={'governing_regime'})
            residuals[view['id']] = residual
            props = {}
            for field in residual['input_fields']:
                if field == 'output_family':
                    continue
                if skill['inputs'][field]['type'] == 'array':
                    element = ({'type': ['boolean', 'null']} if field.startswith('asset_is_')
                               else {'type': ['string', 'null']} if field == 'asset_descriptions'
                               else {'type': ['number', 'null'], 'minimum': 0})
                    props[field] = {'type': 'array', 'items': element}
                elif field == 'number_of_debtors':
                    props[field] = {'type': ['integer', 'null'], 'minimum': 1}
                else:
                    raise ValueError('An unrecognized factual port needs explicit common-tool support')
            specifications[view['id']] = record_schema(props)
        else:
            specifications[view['id']] = record_schema({})
    schemas = [record_schema({'view_id': {'type': 'string', 'enum': [view]}, 'inputs': schema})
               for view, schema in specifications.items()]
    schema = {'oneOf': schemas}
    binding = digest({'fixed_skill': skill, 'source_public_contexts': contexts,
                      'residual_programs': residuals, 'input_schema': schema})

    def invoke(values):
        if digest(frozen_skill()) != digest(skill):
            raise ValueError('The common frozen OE legal function changed')
        jsonschema.validate(values, schema)
        view = values['view_id']
        if not contexts[view]['supported_by_frozen_legal_program']:
            return unsupported('Explicit public regime is outside the audited frozen legal program domain')
        if view not in ('EC', 'EV'):
            return unsupported('Unknown original native formatting family')
        inputs = deepcopy(values['inputs'])
        arrays = [value for key, value in inputs.items() if skill['inputs'][key]['type'] == 'array']
        if not arrays or len({len(value) for value in arrays}) != 1 or not arrays[0]:
            return unsupported('Residual asset arrays need an aligned nonempty inventory')
        if (any(type(value) is not str or not value for value in inputs['asset_descriptions'])
                or len(set(inputs['asset_descriptions'])) != len(inputs['asset_descriptions'])):
            return unsupported('Residual asset descriptions are absent or ambiguous')
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in inputs['asset_values']):
            return unsupported('Residual asset amounts remain unknown or invalid')
        if ('number_of_debtors' in inputs and type(inputs['number_of_debtors']) is not int):
            return unsupported('A needed debtor count remains unknown')
        domains = [{'path': [key, index], 'values': [False, True]}
                   for key, data in inputs.items() if key.startswith('asset_is_')
                   for index, value in enumerate(data) if value is None]
        residual_skill = {**skill, 'procedure': residuals[view]['procedure']}
        return {**partial_skill(residual_skill, {**inputs, 'output_family': view}, domains),
                'common_public_context_residual_consumer': True, 'fallback_executed': False,
                'invented_factual_inputs': False, 'tool_binding_sha256': binding}

    tools['public_context_residual_legal_module'] = {'binding_sha256': binding, 'input_schema': schema,
        'description': 'Execute exact public-context specialization of the same frozen OE F,with all EC/EV semantics retained. Supply only listed asset ports;null Boolean fields remain unknown and are partially executed. No unused debtor count or category is invented. The host binds public regime/native output family. Unsupported regimes stay unsupported. This tool is identical for all formal arms.',
        'invoke': invoke}
    return tools, {**assets, 'common_public_context_residual_programs': residuals,
                   'common_public_contexts': contexts, 'common_residual_tool_binding_sha256': binding}
