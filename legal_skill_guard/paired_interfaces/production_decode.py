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
from legal_skill_guard.skill_evolution.objects import digest


def decode_response(source, view, plan, response):
    errors, graph, ports, decoder, evidence, enum = [], None, None, None, {}, None
    relational_native = None
    if response['finish_reason'] != 'stop':
        errors.append('Non-stop generation remains a production refusal: ' + str(response['finish_reason']))
    try:
        raw, enum = restore_enum_transport(strict_json(response['content']), plan['schema'])
        jsonschema.validate(raw, plan['schema'])
        if plan.get('reader_kind') == 'consumer_relational_program':
            if errors:raise ValueError('Incomplete generation cannot execute a synthesized consumer program')
            from legal_skill_guard.paired_interfaces import relational_program
            if digest(source)!=plan['source_public_sha256']:
                raise ValueError('A generated consumer program lost its source binding')
            if 'indexed_evidence_binding' in plan:
                from legal_skill_guard.paired_interfaces import indexed_relational_read
                decoder = indexed_relational_read.decode(
                    plan['relational_program'], plan['indexed_evidence_binding'], raw, view['relational_public_source'])
                if plan.get('native_evidence_codec') == 'cni_clause_ranges_v1' and raw != indexed_relational_read.UNREAD:
                    from legal_skill_guard.paired_interfaces import cni_disclosure_relational
                    native_view, = source['views']
                    if source['dataset'] != 'ContractNLI' or native_view['id'] != cni_disclosure_relational.TASK:
                        raise ValueError('The native clause evidence codec belongs to a different task')
                    if decoder['outputs'].get(native_view['id']) is not None:
                        anchor = raw.partition('|')[0]
                        evidence[native_view['id']] = cni_disclosure_relational.native_evidence(
                            native_view['public'], anchor, plan['indexed_evidence_binding']['spans'][anchor])
            else:
                decoder=relational_program.decode(plan['relational_program'],raw,view['relational_public_source'])
            relational_native={task:{'handled':decoder['outputs'].get(task) is not None,
                'answer':decoder['outputs'].get(task),'reason':None if decoder['outputs'].get(task) is not None else 'unknown local consumer output',
                'paired_relational_consumer_executed':True,'fallback_executed':False} for task in view['native_tasks']}
        elif plan.get('reader_kind') == 'consumer_relational':
            if errors:
                raise ValueError('Incomplete generation cannot execute a synthesized decoder')
            from legal_skill_guard.paired_interfaces.residual import validate_read, decode
            asset=plan['relational_asset']
            if (digest(asset)!=plan['relational_asset_sha256']
                    or asset['fixed_consumer_sha256']!=view['consumer_sha256']
                    or digest(source)!=plan['source_public_sha256']):
                raise ValueError('A generated pair lost its source/consumer/library binding')
            receipt=validate_read(asset,raw,view['relational_public_source'])
            anchor=raw.get('source_anchor') if asset['layout']=='flat' else (raw.get('observation') or {}).get('source_anchor')
            if receipt['supported'] and anchor!=view['source_anchor']:
                raise ValueError('The read belongs to another source-local binding')
            decoded=(decode(asset,receipt['values'],view['consumer_context'],module_binding=plan['module_binding'])
                     if receipt['supported'] else {'valid':False,'unresolved':'unread local source'})
            values=decoded.get('outputs') if decoded['valid'] else None
            relational_native={}
            for task in view['native_tasks']:
                key=plan['native_projection'][task]
                value=values.get(key) if isinstance(values,dict) else None
                relational_native[task]={'handled':value is not None,'answer':value,
                    'reason':None if value is not None else decoded.get('unresolved','unknown consumer output'),
                    'paired_relational_consumer_executed':decoded['valid'],'fallback_executed':False}
            decoder={'source_read_validation':receipt,'consumer_result':decoded,
                     'method_one_relational_pair_executed':True,
                     'source_semantics_verified_by_inference_oracle':False}
        elif source['dataset'] == 'OpenExempt' and 'fixed_skill_sha256' in plan:
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
        if relational_native is not None:
            native=relational_native
        elif ports is not None:
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
