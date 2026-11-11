"""Observed frozen-matrix/transfer costs, with shared responses charged once.

Uses the existing ledger attribution helpers. No model access or method changes;
unfinished TEST predictions are not opened by this report.
"""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_formal import ARMS, PROFILE as FORMAL_PROFILE
from reports.legal_skill_evolution_run_20261111.formal_cost_footprints import (
    ROOT, REPORT, usage, used_physical_ids)
from reports.legal_skill_evolution_run_20261111.skill_lineage import sha

FROZEN = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'


def load(path):
    return json.loads(path.read_text())


def main():
    completed = FROZEN / 'TEST_completed.json'
    if not completed.exists():
        print(json.dumps({'state': 'waiting_for_complete_frozen_matrix',
            'TEST_predictions_opened': False, 'new_model_calls': 0}))
        return
    done = load(completed)
    profile = load(ROOT / 'configs/legal_skill_evolution_frozen_v1_20261111.json')
    if done['freeze_artifact_sha256'] != profile['freeze']['artifact_sha256']:
        raise ValueError('Cost report must use the completed registered freeze')
    for relative, expected in done['result_file_sha256'].items():
        if sha(FROZEN / relative) != expected:
            raise ValueError('A completed native TEST result changed')
    cutoff = datetime.fromisoformat(done['completed_utc']).timestamp()
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        ledger = {i: {'id': i, 'role': role, 'status': status, 'reserved_at': at,
                      'result': json.loads(raw) if raw else {}}
                  for i, role, status, at, raw in db.execute('select id,role,status,reserved_at,result from calls')}
    prefix = profile['run_id'] + ':'
    frozen_ids = {i for i in ledger if i.startswith(prefix)}
    if any(ledger[i]['role'] == 'teacher' for i in frozen_ids):
        raise ValueError('Frozen evaluation unexpectedly accessed the teacher')
    matrix_dispatches = {i for i in frozen_ids if ledger[i]['reserved_at'] <= cutoff}

    def footprint(identities):
        identities = set(identities)
        return {**usage([ledger[i] for i in sorted(identities)]), 'response_ids': sorted(identities)}

    def consumed(paths, expected):
        paths = list(paths)
        if len(paths) != expected:
            raise ValueError('Cost evidence lacks a complete registered parent cohort')
        identities = set()
        for path in paths:
            identities.update(used_physical_ids(load(path), ledger))
        return identities

    by_arm = {arm: consumed((FROZEN / 'predictions' / arm).glob('*.json'), 160) for arm in ARMS}
    users = defaultdict(list)
    for arm, identities in by_arm.items():
        for identity in identities:
            users[identity].append(arm)
    formal = load(REPORT / 'formal_cost_footprints.json')
    formal_folder = ROOT / load(FORMAL_PROFILE)['artifacts']
    end_to_end = {}
    for arm in ARMS:
        points = formal['per_batch_observed_response_footprints'][arm]
        if max(p['batch'] for p in points) != 8:
            raise ValueError('Complete B8 acquisition costs are required')
        # DEV is excluded from the learning-plus-inference footprint. The
        # final formal point already deduplicates inherited/shared responses.
        training = {i for p in points for i in p['batch_distinct_response_ids']}
        dev = set()
        for point in (formal_folder / 'dev' / arm).glob('B*.json'):
            dev.update(used_physical_ids(load(point), ledger))
        training.difference_update(dev)
        end_to_end[arm] = footprint(training | by_arm[arm])
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'freeze_artifact_sha256': done['freeze_artifact_sha256'],
        'matrix_physical_dispatches_counted_once': footprint(matrix_dispatches),
        'per_arm_matrix_consumed_response_footprints': {a: footprint(ids) for a, ids in by_arm.items()},
        'per_arm_learning_plus_matrix_consumed_response_footprints_excluding_DEV': end_to_end,
        'shared_matrix_responses': [{'physical_id': i, 'used_by_arms': arms}
            for i, arms in sorted(users.items()) if len(arms) > 1],
        'matrix_dispatches_without_parent_evidence_attribution': sorted(matrix_dispatches - set(users)),
        'transfer_complete': False,
        'interpretation': formal['interpretation'],
        'learning_plus_inference_is_an_observed_response_footprint_not_independent_standalone_spending': True,
        'reported_generation_latencies_are_sums_not_wall_clock': True,
        'CLI_output_and_reasoning_token_fields_not_added_together': True,
        'GPU_and_teacher_actual_cash_invoices_unavailable': True,
        'cash_cost_or_cost_advantage_not_inferred_from_first_consumer_cache_order': True}
    transfer_done = FROZEN / 'transfer/completed.json'
    if transfer_done.exists():
        transfer = load(transfer_done)
        if transfer['freeze_artifact_sha256'] != done['freeze_artifact_sha256']:
            raise ValueError('Registered transfer belongs to another freeze')
        for relative, expected in transfer['result_sha256'].items():
            if sha(FROZEN / 'transfer' / relative) != expected:
                raise ValueError('A completed registered transfer result changed')
        target_only = consumed((FROZEN / 'predictions/Full_foreign_off').glob('*/*.json'), 160)
        result.update({'transfer_complete': True,
            'registered_transfer_foreign_on_consumed_response_footprint': footprint(by_arm['Full']),
            'registered_transfer_target_only_consumed_response_footprint': footprint(target_only),
            'additional_transfer_physical_dispatches_counted_once': footprint(frozen_ids - matrix_dispatches),
            'all_frozen_physical_dispatches_counted_once': footprint(frozen_ids)})
    (REPORT / 'frozen_cost_footprints.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'matrix_physical_requests': len(matrix_dispatches),
        'shared_matrix_responses': len(result['shared_matrix_responses']),
        'unattributed_matrix_dispatches': len(result['matrix_dispatches_without_parent_evidence_attribution']),
        'transfer_complete': result['transfer_complete'], 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
