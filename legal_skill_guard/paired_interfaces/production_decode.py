"""Pure response -> production decode -> fixed native execution.

Shared by the actual InterfaceActor and offline source-reference probes.
This function makes no model request, loads no source review and grades nothing.
"""
import jsonschema

from legal_skill_guard.paired_interfaces import airline_interfaces, asset_port_decoder_v2
from legal_skill_guard.paired_interfaces import graph_interface, rich_graph_pairs
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.port_evidence import bind_port_evidence
from legal_skill_guard.paired_interfaces.evidence_projection import source_evidence
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.skill_evolution.native import restore_enum_transport


def decode_response(source, view, plan, response):
    errors, graph, ports, decoder, evidence, enum = [], None, None, None, {}, None
    if response['finish_reason'] != 'stop':
        errors.append('Non-stop generation remains a production refusal: ' + str(response['finish_reason']))
    try:
        raw, enum = restore_enum_transport(strict_json(response['content']), plan['schema'])
        jsonschema.validate(raw, plan['schema'])
        if source['dataset'] == 'OpenExempt' and 'fixed_skill_sha256' in plan:
            ports, decoder = asset_port_decoder_v2.decode(plan, raw, view['source_units'])
        else:
            if source['dataset'] == 'RuleArena_Airline':
                raw, receipt = bind_port_evidence(plan, raw, view['source_units'])
                graph, decoder = airline_interfaces.decode(plan, raw, view['source_units'])
                decoder = {'port_evidence': receipt, 'decoder': decoder}
            else:
                graph, decoder = graph_interface.decode_plan(plan, raw)
            graph, normalization = normalize_graph_evidence(graph, view['source_units'])
            decoder = {'decoder': decoder, 'source_evidence': normalization}
    except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
        errors.append(type(error).__name__ + ': ' + str(error))
    native = {}
    if not errors:
        if ports is not None:
            native = {task: asset_port_decoder_v2.consume(plan, ports, task) for task in view['native_tasks']}
        else:
            (world, _, _), identities = rich_graph_pairs.reference_graph(graph,
                {unit['id']: unit for unit in view['source_units']}, view['scope']['context'])
            native = rich_graph_pairs.consumer_signature(world, source['dataset'], view['native_public'])['native']
            if source['dataset'] == 'ContractNLI':
                evidence = {task: source_evidence(value, graph, identities, view['source_units'],
                    view['native_public'][task]) for task, value in native.items()}
    else:
        graph, ports = None, None
    for task in view['native_tasks']:
        native.setdefault(task, {'handled': False, 'answer': None, 'reason': 'Production decoder refusal'})
        native[task].update(evidence_sentence_ids=evidence.get(task, []), fallback_executed=False)
    return {'production_errors': errors, 'graph': graph, 'ports': ports, 'decoder_receipt': decoder,
            'enum_transport_receipt': enum, 'native': native}
