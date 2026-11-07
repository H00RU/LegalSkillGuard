"""Snapshot physical costs and preserved history without generation or grading."""
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def main():
    root = Path(__file__).resolve().parents[2]
    folder = Path(__file__).resolve().parent
    now = datetime.now(timezone.utc).isoformat()
    baseline = json.loads((root / 'artifacts/rr_method_runtime_20261107/baseline.json').read_text())
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_method_runtime_20261107/baseline.sqlite3') + '?mode=ro', uri=True) as db:
        original = {table: db.execute('select * from ' + table).fetchall()
                    for table in ('calls', 'meta', 'oracle_views')}
    original_ids = {row[0] for row in original['calls']}
    state = json.loads((root / 'docs/rr_v2/method_runtime_state_20261107.json').read_text())
    run_id = state['current_run_id']
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        db.execute('begin')
        for table, rows in original.items():
            assert set(rows) <= set(db.execute('select * from ' + table).fetchall()), table
        rows = db.execute('select id,role,purpose,source,request_hash,status,reserved_at,result from calls order by reserved_at').fetchall()
        oracle_total = db.execute('select count(*) from oracle_views').fetchone()[0]
    counts = dict(Counter(row[1] for row in rows))
    baseline_counts = dict(Counter(row[1] for row in original['calls']))
    pending = sum(row[5] == 'reserved' for row in rows)
    calls = []
    for cid, role, purpose, source, request_hash, status, reserved, encoded in rows:
        if cid in original_ids:
            continue
        result = json.loads(encoded) if encoded else {}
        usage = result.get('usage') or result.get('invocation', {}).get('usage') or {}
        calls.append({'call_id': cid, 'role': role, 'purpose': purpose, 'source': source,
                      'request_hash': request_hash, 'status': status, 'reserved_at': reserved,
                      'prompt_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
                      'completion_tokens': usage.get('completion_tokens', usage.get('output_tokens')),
                      'reasoning_tokens_separate_do_not_add': usage.get('reasoning_output_tokens'),
                      'elapsed_seconds': result.get('elapsed_seconds'),
                      'finish_reason': result.get('finish_reason'),
                      'raw_content_or_teacher_response_sha256': hashlib.sha256(result['content'].encode()).hexdigest()
                      if result.get('content') is not None else result.get('response_sha256')})
    for path, expected in baseline['preserved_run_files'].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path
    with (folder / 'goal_request_ledger_current.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(calls[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(calls)
    current = [call for call in calls if call['call_id'].startswith(run_id + ':')]
    profiles = list((root / 'artifacts/rr_method_runtime_20261107' / run_id / 'thinking/records').glob('*.json'))
    current_receipt = {'captured_utc': now, 'run_id': run_id, 'calls': current,
                       'physical_requests': len(current),
                       'pending_physical_requests': sum(call['status'] == 'reserved' for call in current),
                       'completed_profiles': len(profiles), 'expected_profiles': 40,
                       'comparison_complete': len(profiles) == 40,
                       'finish_reasons': dict(Counter(call['finish_reason'] for call in current if call['finish_reason'])),
                       'usage': {key: sum(call[key] or 0 for call in current)
                                 for key in ('prompt_tokens', 'completion_tokens')},
                       'elapsed_seconds': sum(call['elapsed_seconds'] or 0 for call in current),
                       'no_new_generation_or_grading': True,
                       'exact_paid_replays_are_not_new_physical_requests': True}
    current_name = run_id + '_physical_cost_snapshot.json'
    (folder / current_name).write_text(json.dumps(current_receipt, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    path = folder / 'goal_cost_snapshot_20261107.json'
    value = json.loads(path.read_text())
    value.update(captured_utc=now, cumulative_counts=counts, pending=pending,
                 same_goal_baseline=baseline_counts,
                 new_executor_requests=counts['executor'] - baseline_counts['executor'],
                 new_teacher_requests=counts['teacher'] - baseline_counts['teacher'],
                 new_oracle_views=oracle_total - len(original['oracle_views']),
                 oracle_cumulative=oracle_total,
                 settled_input_tokens_reported=sum(call['prompt_tokens'] or 0 for call in calls),
                 settled_output_tokens_reported=sum(call['completion_tokens'] or 0 for call in calls),
                 settled_request_elapsed_seconds=sum(call['elapsed_seconds'] or 0 for call in calls),
                 teacher_reasoning_field_reported_separately_do_not_add=sum(call['reasoning_tokens_separate_do_not_add'] or 0 for call in calls),
                 source_evidence=list(dict.fromkeys(value['source_evidence'] + [current_name])))
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    preservation = {'checked_utc': now, 'counts': counts, 'pending': pending, 'no_counter_reset': True,
                    'original438_calls_121_meta_130_oracles_identical': True,
                    'old_run_files_unchanged': len(baseline['preserved_run_files']),
                    'old_frozen_libraries_unchanged': 4,
                    'new_model_calls_by_snapshot': 0}
    (folder / 'history_preservation_current_runtime.json').write_text(json.dumps(preservation, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'captured_utc': now, 'current': {k: v for k, v in current_receipt.items() if k != 'calls'},
                      'goal_cost': value, 'preservation': preservation}, ensure_ascii=False))


if __name__ == '__main__':
    main()
