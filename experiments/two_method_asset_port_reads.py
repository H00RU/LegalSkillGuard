"""Fixed local-model integration of OE ports on original reviewed pilot sources.

Exactly three existing development/calibration mothers,six views,three original
candidate families. No teacher call,native grading,held-out source or candidate
search. New physical reads are preserved for formal reuse; analysis versions
bind model,production decoder and alignment. Failed identical wires never retry.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, serialize_pair, sha
from legal_skill_guard.paired_interfaces.asset_graph_pairs import pair_from_read, record_from_read
from legal_skill_guard.paired_interfaces.asset_interfaces import consume
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PREFLIGHT = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'


def prepare(manifest_path):
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_relative_to(BASE.resolve()):
        raise ValueError('Use an explicit local immutable reference manifest')
    manifest = read(manifest_path)
    if manifest['structural_evaluation_mothers_opened'] or len(manifest['reviews']) != 6:
        raise ValueError('Only the three original D0/calibration mothers are authorized here')
    cards = {(row['source'], row['view']): row for row in manifest['reviews']}
    sources = read(BASE / 'prepared/source_lock.json')
    lock = read(BASE / 'pilot_lock.json')
    original_roles = {row['key']: row['role'] for row in lock['rows']}
    if any(original_roles.get(source) not in ('development', 'calibration') for source, _ in cards):
        raise ValueError('A structural or nonpilot source entered this integration')
    preflight = read(PREFLIGHT / 'protocol.json')
    if preflight['executor'] != lock['executor']:
        raise ValueError('The frozen executor profile changed')
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if (sha(public_path) != preflight['TRAIN_public_sha256']
            or sha(BASE / 'prepared/source_lock.json') != preflight['source_lock_sha256']
            or sha(BASE / 'pilot_lock.json') != preflight['pilot_lock_sha256']):
        raise ValueError('A frozen source or cohort changed before dispatch')
    public = {source['key']: source for source in read(public_path)}
    for (source, view), row in cards.items():
        path = ROOT / row['card_path']
        card = read(path)
        task, _ = inputs(public[source])
        units = next(item['source_units'] for item in task['views'] if item['view_id'] == view)
        if (public[source]['dataset'] != 'OpenExempt' or sha(path) != row['card_sha256']
                or card['source'] != source or card['view_id'] != view
                or card['role'] != original_roles[source] or card['source_units_sha256'] != digest(units)):
            raise ValueError('A source port card lost its exact source/view/role binding')
    for name, expected in preflight['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A preflight-bound source changed: ' + name)
    inventory = [row for row in read(PREFLIGHT / 'requests.json')
                 if (row['source'], row['opaque_view']) in cards]
    if len(inventory) != 18 or any(not row['dispatch_supported'] for row in inventory):
        raise ValueError('The six reviewed views/three candidate families changed')
    assets = read(PREFLIGHT / 'plan_assets.json')['OE_by_public_regime']
    versions = {plan['version']: plan for candidates in assets.values() for plan in candidates}
    paths = [Path(__file__).relative_to(ROOT), 'experiments/two_method_graph_corpus.py',
             'legal_skill_guard/paired_interfaces/asset_graph_pairs.py',
             'legal_skill_guard/paired_interfaces/asset_interfaces.py',
             'legal_skill_guard/paired_interfaces/program_residual.py',
             'legal_skill_guard/paired_interfaces/observed_abstention.py',
             'legal_skill_guard/paired_interfaces/structural_channel.py',
             'legal_skill_guard/paired_interfaces/native_graph_consumers.py',
             'legal_skill_guard/paired_interfaces/partial_consumer_worker.py',
             'legal_skill_guard/paired_interfaces/graph_pairs.py',
             'legal_skill_guard/paired_interfaces/graph_matching.py',
             'legal_skill_guard/paired_interfaces/control_tools.py',
             'legal_skill_guard/paired_interfaces/scope_learning.py',
             'legal_skill_guard/skill_evolution/clients.py', 'legal_skill_guard/skill_evolution/ledger.py',
             'legal_skill_guard/skill_evolution/native.py', 'legal_skill_guard/rr/client.py',
             'legal_skill_guard/rr/checkpoint.py', 'legal_skill_guard/rr/ledger.py',
             'tests/test_paired_asset_graph_pairs.py']
    bindings = {str(path): sha(ROOT / path) for path in paths}
    channel_versions = {version: digest({'actual_raw_read_version': version,
        'executor': preflight['executor'], 'production_and_alignment_source_sha256': bindings}) for version in versions}
    protocol = {'experiment': 'fixed_OE_program_port_integration_reads_v1',
        'source_sha256': bindings, 'executor': preflight['executor'],
        'reference_manifest_path': str(manifest_path.relative_to(ROOT)), 'reference_manifest_sha256': sha(manifest_path),
        'preflight_protocol_sha256': sha(PREFLIGHT / 'protocol.json'),
        'source_lock_sha256': sha(BASE / 'prepared/source_lock.json'),
        'requests_sha256': digest(inventory), 'source_mothers': 3, 'source_views': 6,
        'fixed_logical_reads': 18, 'candidate_families': ['columns', 'records', 'local_records'],
        'channel_versions': channel_versions, 'teacher_or_external_service_called': False,
        'native_grading_or_evaluation_source_opened': False,
        'original_candidate_families_and_pilot_mothers_unchanged': True,
        'new_F_port_version_does_not_overwrite_old_generic_pilot': True,
        'no_implicit_retry_or_extra_source_or_gain_based_selection': True,
        'rejected96_teacher_request_phase_not_started_by_this_entry': True}
    out = BASE / 'asset_port_reads_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(out / 'requests.json', inventory)
    for path in paths:
        destination = out / 'source_snapshot' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError('An immutable integration source snapshot changed')
        if not destination.exists():
            destination.write_bytes(raw)
    return out, protocol, inventory, cards, versions, sources


def failed_wires(roots):
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        failed = {row[0] for row in db.execute("select id from calls where status='failed'")}
    result = set()
    for root in roots:
        for path in (root / 'calls').glob('*/wire_request.json'):
            request = read(path.with_name('request.json'))
            if request['id'] in failed:
                result.add((request['source'], read(path)['body_sha256']))
    return result


def run(manifest_path):
    out, protocol, inventory, cards, plans, sources = prepare(manifest_path)
    driver = (out / 'driver.lock').open('a')
    fcntl.flock(driver, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise RuntimeError('An actual physical request is already in flight')
    for name, expected in protocol['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('An integration-bound source changed before dispatch')
    run_id = 'two_method_asset_port_reads_v1_20261117_' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources=sources['sources'],
        binding={'phase': 'fixed_original_OE_port_integration', 'protocol_sha256': sha(out / 'protocol.json')})
    executor = FrozenExecutor(ledger, out, protocol['executor'])
    roots = sorted(path for path in (BASE / 'asset_port_reads_v1').iterdir() if path.is_dir())
    executor.exact_replay_roots = roots
    denied = failed_wires(roots)
    readiness = executor.readiness()
    immutable_json(out / 'readiness' / (digest(readiness) + '.json'), readiness)
    public = {source['key']: source for source in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    records = []
    for row in inventory:
        identity = digest([row['source'], row['opaque_view'], row['version']])
        path = out / 'reads' / identity / 'decoded.json'
        if path.exists():
            records.append(read(path))
            continue
        plan = plans[row['version']]
        wire = json.dumps(executor.payload(messages=row['messages'], thinking=False, schema=row['schema']), ensure_ascii=False).encode()
        if (row['source'], hashlib.sha256(wire).hexdigest()) in denied:
            raise BudgetError('The identical previously failed physical wire cannot be redispatched')
        call_id = run_id + ':read:' + identity
        immutable_json(path.with_name('task.json'), row)
        print(json.dumps({'event': 'local_OE_read_dispatch', 'source': row['source'],
                          'view': row['opaque_view'], 'plan': row['plan'], 'call_id': call_id}), flush=True)
        # A wire/resource failure settles in the original ledger and stops this
        # driver, rather than creating synthetic perception observations.
        response = executor.generate(call_id, source=row['source'], purpose='skill_actor',
                                     messages=row['messages'], thinking=False, schema=row['schema'])
        source = public[row['source']]
        task, mapping = inputs(source)
        units = next(view['source_units'] for view in task['views'] if view['view_id'] == row['opaque_view'])
        raw, transport, errors = None, None, []
        if response['finish_reason'] != 'stop':
            errors.append('Original non-stop generation finish: ' + str(response['finish_reason']))
        try:
            raw = strict_json(response['content'])
            raw, transport = restore_enum_transport(raw, row['schema'])
            jsonschema.validate(raw, row['schema'])
            record_from_read(plan, raw, units)
        except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
            errors.append(type(error).__name__ + ': ' + str(error))
        card_row = cards[row['source'], row['opaque_view']]
        card_path = ROOT / card_row['card_path']
        if sha(card_path) != card_row['card_sha256']:
            raise ValueError('An audited source port card changed during the run')
        card = read(card_path)
        pair, alignment = pair_from_read(card, raw, plan, units, source=row['source'], role=card['role'],
            provenance=digest({'physical_read': response.get('reused_physical_call_id', call_id),
                               'source_card_sha256': sha(card_path)}),
            version=protocol['channel_versions'][row['version']], production_errors=errors)
        native = {name: consume(plan, raw, units, name) for name, opaque in mapping.items()
                  if opaque == row['opaque_view']} if not errors else {}
        record = {'source': row['source'], 'role': card['role'], 'view': row['opaque_view'],
            'plan': row['plan'], 'raw_read_version': row['version'], 'channel_version': pair.plan_version,
            'physical_call_id': response.get('reused_physical_call_id', call_id),
            'logical_call_id': call_id, 'reused_paid_response': bool(response.get('reused_physical_call_id')),
            'production_errors': errors, 'raw_port_read': raw, 'enum_transport_receipt': transport,
            'pair': serialize_pair(pair), 'alignment': alignment, 'native_outputs_before_grading': native,
            'token_usage': response['usage'], 'no_native_grading_or_labels_used': True,
            'same_original_mothers_not_new_independent_samples': True}
        immutable_json(path, record)
        records.append(record)
        print(json.dumps({'event': 'local_OE_read_settled', 'source': row['source'], 'view': row['opaque_view'],
            'plan': row['plan'], 'production_decode_accepted': not errors,
            'native_tasks_handled': sum(value['handled'] for value in native.values()), 'errors': errors}), flush=True)
    immutable_json(out / 'paired_reads.json', records)
    summary = {'status': 'fixed18_original_source_port_integration_settled', 'outputs': len(records),
        'production_decode_accepted': sum(not row['production_errors'] for row in records),
        'native_tasks_handled_without_grading': sum(value['handled'] for row in records
            for value in row['native_outputs_before_grading'].values()),
        'model_requests_reused_from_other_roots': sum(row['reused_paid_response'] for row in records),
        'source_mothers': 3, 'new_independent_mothers': 0, 'native_accuracy_not_evaluated': True,
        'no_teacher_request_or_new_candidate_search': True, 'complete_two_method_goal': False}
    immutable_json(out / 'terminal.json', summary)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **summary}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-manifest', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        out, protocol, inventory, *_ = prepare(args.reference_manifest)
        print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'logical_local_reads': len(inventory),
                          'source_mothers': 3, 'teacher_calls': 0, 'model_calls': 0}))
    else:
        run(args.reference_manifest)
