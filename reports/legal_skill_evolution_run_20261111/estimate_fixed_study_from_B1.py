"""Observed B1 cost and explicitly conditional sizing, without extra runs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .formal_cost_footprints import usage

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
LEARNING_ARMS = ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')


def main():
    folder = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v1'
    paths = [folder / a / 'update_B1.json' for a in LEARNING_ARMS]
    if not all(p.exists() for p in paths):
        print(json.dumps({'B1_update_phase_complete': False, 'new_model_calls': 0}));return
    receipts = [json.loads(p.read_text()) for p in paths]
    teacher_hashes = {r['teacher_request_sha256'] for r in receipts}
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        raw = db.execute("select id,role,purpose,reserved_at,status,result from calls where id like 'legal_skill_evolution_formal_%'").fetchall()
    rows = [{'id': i, 'role': role, 'purpose': purpose, 'reserved_at': at, 'status': status,
             'result': json.loads(body) if body else {}} for i, role, purpose, at, status, body in raw]
    start = min(r['reserved_at'] for r in rows if r['purpose'] == 'skill_actor')
    later_dev = [r['reserved_at'] for r in rows if r['purpose'] == 'skill_dev' and r['reserved_at'] > start]
    if not later_dev:raise ValueError('Wait for the actual post-update DEV boundary before estimating B1')
    stop = min(later_dev)
    teachers = [r for r in rows if r['role'] == 'teacher' and r['result'].get('request_sha256') in teacher_hashes]
    actors = [r for r in rows if r['purpose'] == 'skill_actor' and start <= r['reserved_at'] < stop]
    if len(teachers) != 6 or any(r['status'] != 'completed' for r in teachers + actors):
        raise ValueError('A completed first batch and its charged outcomes are required')
    wall = stop - start
    mean_teacher = sum(r['result']['elapsed_seconds'] for r in teachers) / len(teachers)
    logical = {r['arm']: r['logical_candidate_parent_executions'] for r in receipts}
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'observed_B1': {'parent_sources': 16, 'learning_arms': 6, 'start_reserved_at': start,
            'first_post_update_DEV_dispatch_at': stop, 'learning_phase_wall_seconds': wall,
            'actual_physical_cost': usage(teachers + actors), 'logical_candidate_parent_executions_by_arm': logical,
            'mean_teacher_latency_seconds': mean_teacher,
            'DEV_and_TEST_execution_cost_not_in_this_phase': True},
        'conditional_sizing_not_a_completion_promise': {
            '8_batches_at_identical_B1_workload_learning_hours': wall * 8 / 3600,
            '48_teacher_calls_at_observed_B1_mean_hours': mean_teacher * 48 / 3600,
            'future_replay_parents_per_block': 8, 'B1_replay_parents_per_block': 3,
            'per_arm_batch_logical_ceiling': 192, 'actual_B1_logical_by_arm': logical,
            'point_to_update_after_B2': 'B1 has three-parent trigger-only replay; later batches have history and more retained candidates, so B1 alone cannot forecast complete replay/DEV/TEST cost.',
            'model_retry_seed_source_or_configuration_scan_added': False},
        'actual_project_cash_invoice_usd': None,
        'token_latency_and_physical_accounting_are_authoritative_not_assumed_cash_prices': True}
    (REPORT / 'fixed_study_cost_estimate_B1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'B1_learning_phase_minutes': wall / 60, 'B1_physical_executor': len(actors),
        'B1_teacher': len(teachers), 'B1_logical_by_arm': logical,
        'conditional_8_batch_learning_hours': wall * 8 / 3600,
        'includes_DEV_TEST_forecast': False}))


if __name__ == '__main__':main()
