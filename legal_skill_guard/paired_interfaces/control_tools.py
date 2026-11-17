"""Shared frozen legal tools available to independently learned programs.

Only the preserved law/program assets and caller-supplied factual inputs enter
these tools. Original case facts, grading records and construction metadata are
never loaded. Tool availability is not a certification of extracted facts or
of the historical learned module's completeness.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import jsonschema

from legal_skill_guard.paired_interfaces.public_graph_ports import consumer_graph
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.legal_consumers import contract
from legal_skill_guard.paired_interfaces.partial_legal_consumer import maud
from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def unsupported(reason):
    return {'handled': False, 'answer': None, 'reason': reason,
            'native_grading_oracle_used': False, 'new_model_requests': 0}


def skill_inputs(skill):
    return record_schema({k: {'type': p['type']} for k, p in skill['inputs'].items()})


def execute_skill(skill, values):
    from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
    jsonschema.validate(values, skill_inputs(skill))
    validate_procedure(skill['procedure'])
    if any(p['mode'] != 'constant' for p in skill['premises'].values()):
        return unsupported('This preserved program has unresolved legal premises')
    arrays = [v for k, v in values.items() if skill['inputs'][k]['type'] == 'array']
    if arrays and len({len(v) for v in arrays}) != 1:
        return unsupported('Input arrays are not aligned; no zip truncation')
    if skill['id'] == 'domestic_main_or_first_bag_total':
        if values['route_fee_region'] not in ('domestic_us', 'south_america_other', 'east_asia'):
            return unsupported('Route lies outside the preserved learned program domain')
        if any(type(w) is not int or not 0 <= w <= 100 for w in values['item_weights']):
            return unsupported('Weights lie outside the fixed integer domain')
    elif skill['id'] == 'personal_asset_exemption_plan_by_solved_regime':
        if values['governing_regime'] not in ('Illinois', 'Federal and Wisconsin',
                'Federal and Pennsylvania', 'Arizona', 'Federal and Arizona'):
            return unsupported('Regime lies outside the preserved learned program domain')
        for name, items in values.items():
            if name.startswith('asset_is_') and any(type(v) is not bool for v in items):
                return unsupported('An unknown category is not a false Boolean')
    payload = {'procedure': skill['procedure'], 'calls': [{'inputs': values}],
               'premises': {k: p['value'] for k, p in skill['premises'].items()}}
    result = subprocess.run([sys.executable, '-m', 'legal_skill_guard.paired_interfaces.consumer_worker'],
        input=json.dumps(payload), capture_output=True, text=True, cwd=ROOT, timeout=30)
    if result.returncode:
        raise ValueError('The shared frozen legal program failed: ' + result.stderr[-1000:])
    answer = json.loads(result.stdout)[0]['answer']
    return {'handled': True, 'answer': answer, 'frozen_program_sha256': digest(skill['procedure']),
            'factual_truth_certified': False, 'native_grading_oracle_used': False, 'new_model_requests': 0}


def module_assets(dataset):
    module = read(BASE / 'pilot_lock.json')['modules'][dataset]
    path = ROOT / module['asset']
    if sha(path) != module['sha256']:
        raise ValueError('The shared frozen legal asset changed')
    common = {'dataset': dataset, 'module_binding': module,
              'historical_module_full_legal_completeness_not_certified': True,
              'same_assets_available_to_main_method': True}
    if dataset in ('RuleArena_Airline', 'OpenExempt', 'SARA_v2_Binary'):
        names = ('native_graph_consumers.py', 'partial_consumer_worker.py', 'rich_graph_pairs.py')
        common['shared_native_graph_adapters'] = {name: {
            'python_source': (ROOT / 'legal_skill_guard/paired_interfaces' / name).read_text(),
            'sha256': sha(ROOT / 'legal_skill_guard/paired_interfaces' / name)} for name in names}
    if dataset in ('RuleArena_Airline', 'OpenExempt'):
        skill = read(path)['skills'][module['skill']]
        return {**common, 'skill': skill}
    if dataset in ('ContractNLI', 'MAUD'):
        adapter = ROOT / 'legal_skill_guard/paired_interfaces/public_graph_ports.py'
        extension = {}
        if dataset == 'MAUD':
            from legal_skill_guard.paired_interfaces.partial_legal_consumer import base_binding, PROTOCOL
            partial = ROOT / 'legal_skill_guard/paired_interfaces/partial_legal_consumer.py'
            extension = {'completion_invariant_execution': {'protocol': PROTOCOL,
                'frozen_base_sha256': base_binding(), 'source': partial.read_text(), 'sha256': sha(partial),
                'defined_base_outputs_unchanged': True, 'shared_by_all_arms': True,
                'graph_unknown_fields_or_scope_not_repaired': True}}
        return {**common, **extension, 'python_source': path.read_text(), 'graph_schema': gi.schema(),
                'shared_public_consumer_port_closure': {'source': adapter.read_text(), 'sha256': sha(adapter)}}
    if dataset == 'SARA_v2_Binary':
        from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface
        prototype = current_case_interface(read(path)[0]['kernel'])
        statutes = {}
        for name, expected in prototype['statute_sha256'].items():
            statute = ROOT / prototype['statute_directory'] / name
            if sha(statute) != expected:
                raise ValueError('An author statute asset changed')
            statutes[name] = statute.read_text()
        # The old case-specific query is not a tool input or a source fact.
        prototype = {k: v for k, v in prototype.items()
                     if k not in ('native_query', 'name', 'query_clause')}
        return {**common, 'statute_kernel_template': prototype, 'statute_sources': statutes}
    raise ValueError('No shared frozen legal module for dataset')


def legal_tools(source, bundle):
    dataset = source['dataset']
    assets = module_assets(dataset)
    views = {v['id']: v for v in bundle['bundle_native_views']}
    if dataset in ('RuleArena_Airline', 'OpenExempt'):
        skill = assets['skill']
        def invoke(values):
            if digest(module_assets(dataset)['skill']) != digest(skill):
                raise ValueError('The legal tool binding changed after construction')
            return execute_skill(skill, values)
        schema = skill_inputs(skill)
        description = 'Execute the unchanged shared learned program on typed factual ports. Read failure and out-of-domain inputs remain unhandled.'
    elif dataset in ('ContractNLI', 'MAUD'):
        tasks = ['nda-5', 'nda-7', 'nda-16', 'nda-20'] if dataset == 'ContractNLI' else list(views)
        schema = record_schema({'graph': gi.schema(), 'task': {'type': 'string', 'enum': tasks}})
        def invoke(values):
            module_assets(dataset)  # Check the same frozen function source.
            graph, numeric = normalize_numeric_ports(values['graph'])
            graph, closure = consumer_graph(graph)
            return {**(contract if dataset == 'ContractNLI' else maud)(graph, values['task']),
                    'public_numeric_transport': numeric, 'public_graph_closure': closure,
                    'native_grading_oracle_used': False, 'new_model_requests': 0}
        description = 'Apply the same fixed source-graph consumer and public closures as the main method; unknown scope is not defaulted.'
    else:
        from legal_skill_guard.skill_evolution.partial_native_proof import execute
        from legal_skill_guard.skill_evolution.sara_statute_kernel import input_schema
        template = assets['statute_kernel_template']
        scalar = {'anyOf': [{'type': 'string'}, {'type': 'number'},
                            record_schema({'variable': {'type': 'string', 'enum': ['_']}})]}
        schema = record_schema({'view_id': {'type': 'string', 'enum': list(views)},
            'query': {'type': 'array', 'minItems': 1, 'items': record_schema({
                'predicate': {'type': 'string'}, 'arguments': {'type': 'array', 'items': scalar}})},
            'binding': input_schema(template), 'complete_families': {'type': 'array', 'items': {'type': 'string'}}})
        def invoke(values):
            module_assets(dataset)
            kernel = {**deepcopy(template), 'native_query': values['query'],
                      'name': values['query'][0]['predicate'], 'query_clause': values['query'][0]['predicate']}
            result = execute(kernel, values['binding'], values['complete_families'],
                             views[values['view_id']]['public'])
            return {**result, 'native_grading_oracle_used': False, 'new_model_requests': 0}
        description = 'Execute unchanged author statutes on data-only supplied query/facts with guarded factual closure. A target answer cannot be asserted as a fact.'
    tools = {'frozen_legal_module': {'binding_sha256': digest(assets), 'description': description,
                                   'input_schema': schema, 'invoke': invoke}}
    if dataset in ('RuleArena_Airline', 'OpenExempt', 'SARA_v2_Binary'):
        def graph_invoke(values):
            if digest(module_assets(dataset)) != digest(assets):
                raise ValueError('A common native graph adapter binding changed')
            from experiments.two_method_annotate import inputs
            from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
            from legal_skill_guard.paired_interfaces.rich_graph_pairs import semantic, consumer_signature
            task, mapping = inputs(source)
            native_id = values['native_view_id']
            opaque = mapping[native_id]
            units = next(view['source_units'] for view in task['views'] if view['view_id'] == opaque)
            graph, receipt = normalize_graph_evidence(values['graph'], units)
            identities = {node['id']: node['id'] for node in graph['nodes']}
            world, _, _ = semantic(graph, identities, {}, dataset, {u['id']: u for u in units})
            result = consumer_signature(world, dataset, {native_id: views[native_id]['public']})
            native = result.get('native', {}).get(native_id, unsupported(result.get('reason', 'Unsupported graph')))
            return {**native, 'common_literal_evidence_transport': receipt,
                    'source_graph_tool_binding_sha256': digest(assets),
                    'no_case_label_or_other_view_fact_used': True}
        tools['source_graph_native_module'] = {'binding_sha256': digest(assets),
            'input_schema': record_schema({'graph': gi.schema(),
                'native_view_id': {'type': 'string', 'enum': list(views)}}),
            'description': 'Consume a source-anchored graph through the same literal-rich native adapter as the main method. Source units are used for literal pointer/order binding only. SARA query comes only from the public question; OE uses the explicit public solved regime. Unknowns remain unresolved.',
            'invoke': graph_invoke}
    if dataset == 'OpenExempt':
        def partial_invoke(values):
            if digest(module_assets(dataset)) != digest(assets):
                raise ValueError('A common finite partial-consumer binding changed')
            from legal_skill_guard.paired_interfaces.native_graph_consumers import BOOLEAN_PORTS, partial_skill
            jsonschema.validate(values, skill_inputs(skill))
            arrays = [v for name, v in values.items() if skill['inputs'][name]['type'] == 'array']
            if len({len(v) for v in arrays}) != 1:
                return unsupported('Partial input arrays are not aligned')
            if any(v is not None and type(v) is not bool for name in BOOLEAN_PORTS for v in values[name]):
                return unsupported('Partial classification ports are Boolean or explicitly unknown')
            domains = [{'path': [name, index], 'values': [False, True]}
                for name in BOOLEAN_PORTS for index, value in enumerate(values[name]) if value is None]
            return partial_skill(skill, values, domains)
        tools['finite_partial_legal_module'] = {'binding_sha256': digest(assets),
            'input_schema': skill_inputs(skill),
            'description': 'Execute the same frozen OE program with null unknown classification array entries. Enumerate both Boolean values only when actually demanded; return an answer only if all allowed completions agree. No unknown is asserted false.',
            'invoke': partial_invoke}
    return tools, assets
