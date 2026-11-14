"""Offline audit of closed TRAIN controls; never starts a model client.

The last joint response failed its required per-channel witness check. Its
factual payload is replayed separately to diagnose that failure, without
accepting the response, inventing a witness, or changing the original result.
"""
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import (
    apply_adapter, checked_witnesses, execute_alternatives,
)
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.objects import digest


ROOT = Path(__file__).resolve().parents[1]
RUNS = [
    'legal_skill_evolution_joint_grounding_control_20261114',
    'legal_skill_evolution_joint_grounding_focused_20261114',
    'legal_skill_evolution_residual_observation_20261114',
    'legal_skill_evolution_residual_port_control_20261114',
    'legal_skill_evolution_joint_scoped_observations_20261114',
]
REPORT = ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/residual_instantiation'


def read(path):
    return json.loads(path.read_text())


def joint_diagnostic():
    parent = ROOT / 'artifacts' / RUNS[2]
    closed = ROOT / 'artifacts' / RUNS[-1]
    packet = read(parent / 'packet.json')
    protocol = read(closed / 'protocol.json')
    public = packet['source']['views'][0]['public']
    response_path, = (closed / 'calls').glob('*/result.json')
    response = read(response_path)
    value = json.loads(response['content'])
    jsonschema.validate(value, protocol['schema'])
    failures = []
    for name, channel in value.items():
        if channel['status'] == 'unread':
            continue
        try:
            checked_witnesses(channel['witnesses'], public)
        except ValueError as exc:
            failures.append({'channel': name, 'status': channel['status'],
                             'error': str(exc)})
    # A diagnostic consumer replay, NOT a repaired/accepted model response.
    # No witness is added for the rejected absence channel. Its explicitly
    # supplied none_stated value is projected to the existing finite-set port.
    updated = deepcopy(packet['original_observation'])
    for name, channel in value.items():
        status = channel['status']
        if status == 'unread':
            continue
        if status == 'records':
            checked_witnesses(channel['witnesses'], public)
        updated['views'][0][name] = [] if status == 'none_stated' else deepcopy(channel['value'])
        updated['views'][0]['witnesses'].extend(deepcopy(channel['witnesses']))
    grounded = apply_adapter(packet['contract'], packet['kernel'], public,
                            updated, literal_context=literal_bindings({'public': public}))
    execution = execute_alternatives(packet['kernel'], grounded)
    return {
        'source': packet['source']['key'], 'physical_response_path': str(response_path.relative_to(ROOT)),
        'raw_response_sha256': digest(response),
        'strict_response_accepted': not failures, 'strict_check_failures': failures,
        'schema_valid': True,
        'channel_statuses': {k: v['status'] for k, v in value.items()},
        'payload_diagnostic_only': True, 'counts_as_core_success': False,
        'missing_quote_not_fabricated': True, 'correctness_checks_unchanged': True,
        'payload_view': updated, 'grounded_payload': grounded,
        'payload_execution': execution, 'kernel_program_sha256': digest(packet['kernel']['program']),
        'independent_contribution_gain_established': False,
        'new_model_requests_for_audit': 0, 'goal_complete': False,
    }


def cost_audit():
    before = read(ROOT / 'artifacts' / RUNS[0] / 'ledger_before_row_hashes.json')
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        rows = db.execute('select * from calls order by id').fetchall()
    by_id = {r[0]: r for r in rows}
    assert len(before) == 10614
    assert all(digest(by_id[key]) == val for key, val in before.items())
    new = [r for r in rows if r[0] not in before]
    assert len(new) == 5 and all(r[0].split(':')[0] in RUNS for r in new)
    assert not any(r[6] == 'reserved' for r in rows)
    calls = []
    for row in new:
        response = json.loads(row[8])
        calls.append({'id': row[0], 'role': row[1], 'source': row[4],
                      'status': row[6], 'usage': response['usage'],
                      'elapsed_seconds': response['elapsed_seconds'],
                      'finish_reason': response['finish_reason'],
                      'thinking_requested': response['thinking_requested'],
                      'request_hash': response['request_hash']})
    return {
        'ledger_before': len(before), 'ledger_after': len(rows),
        'all10614_previous_calls_unchanged': True, 'pending': 0,
        'new_executor_calls': sum(r[1] == 'executor' for r in new),
        'new_teacher_calls': sum(r[1] == 'teacher' for r in new),
        'total_executor_calls': sum(r[1] == 'executor' for r in rows),
        'total_teacher_calls': sum(r[1] == 'teacher' for r in rows),
        'executor_input_tokens': sum(c['usage']['prompt_tokens'] for c in calls),
        'executor_output_tokens': sum(c['usage']['completion_tokens'] for c in calls),
        'executor_service_seconds': sum(c['elapsed_seconds'] for c in calls),
        'new_independent_sources': 0, 'development_mothers_used': 1,
        'no_new_DEV_TEST_or_training': True,
        'executor_incremental_per_request_API_cash_usd': 0,
        'GPU_cost_usd': None, 'actual_resource_cash_invoice_available': False,
        'strict_host_witness_failure_after_completed_model_responses': 1,
        'calls': calls,
    }


def main():
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        diagnostic = joint_diagnostic()
        cost = cost_audit()
        immutable_json(REPORT / 'joint_scoped_diagnostic.json', diagnostic)
        immutable_json(REPORT / 'cost_and_preservation.json', cost)
        copies = []
        for run in RUNS:
            source = ROOT / 'artifacts' / run
            for path in sorted(source.rglob('*')):
                if not path.is_file() or path.name == 'ledger_before_row_hashes.json':
                    continue
                dest = REPORT / run / path.relative_to(source)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    assert dest.read_bytes() == path.read_bytes()
                else:
                    shutil.copyfile(path, dest)
                import hashlib
                copies.append({'original': str(path.relative_to(ROOT)),
                               'copy': str(dest.relative_to(ROOT)),
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        immutable_json(REPORT / 'artifact_copy_manifest.json', copies)
        print(json.dumps({'ledger': cost['ledger_after'], 'new_executor': cost['new_executor_calls'],
                          'strict_accepted': diagnostic['strict_response_accepted'],
                          'payload_only_execution': {k: diagnostic['payload_execution'][k] for k in ('handled', 'answer')},
                          'copied_files': len(copies)}), flush=True)


if __name__ == '__main__':
    main()
