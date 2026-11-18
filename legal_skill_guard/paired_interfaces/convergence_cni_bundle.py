"""ContractNLI read with one synthesized task and the complete native cohort."""

import json
import re

import jsonschema

from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces.cni_disclosure_mentions import with_mentions
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


EVENT_TERMS = re.compile(
    r'\b(?:may|shall|must|will|can)(?:\s+not)?\s+(?:be\s+)?'
    r'(?:disclos\w*|shar\w*|divulg\w*|restrict\s+access|inform\w*|notif\w*)\b', re.I,
)


def event_coordinates(text, ranges, windows):
    """Expose event wording and repeated names without assigning legal roles."""
    observed = []
    for window in windows:
        first, last = ranges[window['id']]
        phrases = [{'text': match[0], 'start': first + match.start(), 'end': first + match.end()}
                   for match in EVENT_TERMS.finditer(text[first:last])]
        destinations = [row for row in window['mentions'] if row['kind'] == 'named_destination']
        possessives = [row for row in window['mentions'] if row['kind'] == 'possessive_group']
        repeated = [{'name': destination['text'], 'destination_offset': destination['start'],
                     'possessive_offset': group['start']}
                    for destination in destinations for group in possessives
                    if destination['end'] < group['start'] and destination['text'] == group['text']]
        if phrases or repeated:
            observed.append({'id': window['id'], 'event_wording': phrases, 'repeated_name_offsets': repeated})
    return observed


def build_bundle(source):
    if (source['dataset'] != 'ContractNLI' or len(source['views']) != 17
            or sum(view['id'] == disclosure.TASK for view in source['views']) != 1):
        raise ValueError('A complete ContractNLI bundle requires all seventeen original hypotheses')
    selected, local_view = disclosure.build(source)
    local_view = with_mentions(local_view)
    bundle = source_bundle({**source, 'evidence_presentation': 'explicit_zero_based_spans'})
    native = {name: schema for name, schema in wire_schema(source['dataset'], bundle)['properties'].items()
              if name != disclosure.TASK}
    local_input = {key: value for key, value in local_view['read_input'].items() if key != 'source_text'}
    public_source = local_view['relational_public_source']
    local_input['event_coordinates'] = event_coordinates(public_source['source_text'],
        public_source['indexed_ranges'], local_input['participant_mentions'])
    # The original document and its complete zero-based evidence inventory are shared.
    public = {'full_public_input': bundle['public'], 'employee_disclosure_subtask': local_input}
    plans = []
    for local in local_view['plans']:
        schema = record_schema({'native_answers': record_schema(native), 'disclosure': local['schema']})
        system = (
            'Answer the sixteen specified native hypotheses using the original exact document and evidence IDs. '
            'When the label is NotMentioned use an empty evidence list. For the remaining hypothesis only, '
            'return its anchored local reading in disclosure. Use the same original document for all tasks. '
            'The event coordinates list literal phrases and repeated name offsets. Bind a permission, its actor '
            'and the employee group to the same event. A definition or instruction to inform someone must not be '
            'treated as a permission to share information. The list may omit other legitimate event wording.\n'
            + local['system'] + '\nReturn JSON in this schema: '
            + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))
        )
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': json.dumps(public, ensure_ascii=False, sort_keys=True)}]
        protocol = {'schema': schema, 'messages': messages, 'local_plan': local}
        plans.append({**protocol, 'version': digest(protocol)})
    return {'source_sha256': digest(source), 'selected_source': selected, 'local_view': local_view,
            'native_bundle': {**bundle, 'bundle_native_views': [view for view in bundle['bundle_native_views']
                                                               if view['id'] != disclosure.TASK]}, 'plans': plans}


def decode_bundle(source, bundle, plan, response):
    if (bundle['source_sha256'] != digest(source) or plan not in bundle['plans']
            or plan['version'] != digest({k: v for k, v in plan.items() if k != 'version'})):
        raise ValueError('The measured hybrid response lost its exact source and plan binding')
    if response['finish_reason'] != 'stop':
        raise ValueError('An incomplete physical response cannot be recovered as native answers')
    decoded, transport_receipt = restore_enum_transport(json.loads(response['content']), plan['schema'])
    jsonschema.validate(decoded, plan['schema'])
    native_wire = decoded['native_answers']
    answers, evidence = decode_native(source['dataset'], bundle['native_bundle'], native_wire)
    direct = {task: {'answer': answer, 'handled': True, 'evidence_sentence_ids': evidence[task],
                     'fallback_executed': False} for task, answer in answers.items()}
    local = decode_response(bundle['selected_source'], bundle['local_view'], plan['local_plan'], {
        'content': json.dumps(decoded['disclosure']), 'finish_reason': response['finish_reason'],
    })
    result = {**direct, **local['native']}
    if set(result) != {view['id'] for view in source['views']} or set(direct) & set(local['native']):
        raise ValueError('Surgical interface replacement must preserve all seventeen original hypotheses')
    return {'native': result, 'local_decoder_receipt': local['decoder_receipt'],
            'local_production_errors': local['production_errors'], 'enum_transport_restorations': transport_receipt,
            'fallback_executed': False}
