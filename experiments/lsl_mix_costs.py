"""Read-only continuous ledger snapshot and separately measured training cost."""
from collections import Counter
from pathlib import Path
import json
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha


def main():
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    db = sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
    db.execute('begin')
    rows = db.execute('select id,role,purpose,source,status,reserved_at,result from calls order by reserved_at,id').fetchall()
    groups = {}
    compact = []
    for call_id, role, purpose, source, status, reserved_at, raw in rows:
        if not call_id.startswith('LSG-MIX256'):
            continue
        result = json.loads(raw) if raw else {}
        usage = result.get('usage') or {}
        prompt = usage.get('prompt_tokens', result.get('input_tokens'))
        completion = usage.get('completion_tokens', result.get('output_tokens'))
        namespace = call_id.split(':', 1)[0]
        group = groups.setdefault(namespace, {'physical_rows': 0, 'completed': 0, 'failed': 0, 'reserved': 0,
            'known_prompt_tokens': 0, 'known_completion_tokens': 0, 'rows_without_full_token_usage': 0,
            'sum_HTTP_seconds_not_GPU_wall': 0.})
        group['physical_rows'] += 1
        group[status] += 1
        group['known_prompt_tokens'] += prompt or 0
        group['known_completion_tokens'] += completion or 0
        group['rows_without_full_token_usage'] += prompt is None or completion is None
        group['sum_HTTP_seconds_not_GPU_wall'] += result.get('elapsed_seconds', 0.)
        compact.append({'id': call_id, 'role': role, 'purpose': purpose, 'source': source, 'status': status,
            'reserved_at': reserved_at, 'request_hash': result.get('request_hash'), 'thinking': result.get('thinking'),
            'transport_retries': result.get('transport_retries'), 'actual_HTTP_dispatches': result.get('actual_HTTP_dispatches'),
            'known_prompt_tokens': prompt, 'known_completion_tokens': completion,
            'finish': result.get('finish'), 'error': result.get('error'), 'elapsed_seconds': result.get('elapsed_seconds')})
    db.rollback()
    training = []
    receipts = [out / 'common_native_initialization/native_pass_complete.json',
                *sorted((out / 'acquisition').glob('*/epoch*/complete.json'))]
    for receipt in receipts:
        if not receipt.exists():
            continue
        done = load_json(receipt)
        training.append({'path': str(receipt.parent.relative_to(ROOT)), 'loop_seconds': done['seconds'],
            'receipt_sha256': sha(receipt), 'physical_model_generations_in_training_loop': 0})
    snapshot = {'time_unix': time.time(), 'continuous_ledger_counts': dict(Counter(row[1] for row in rows)),
        'pending': sum(row[4] == 'reserved' for row in rows), 'no_ledger_reset': True,
        'phase_new_remote_teacher_requests': sum(r['role'] == 'teacher' for r in compact),
        'phase_new_remote_API_cash_usd': 0, 'local_GPU_CPU_not_priced_as_zero': True,
        'GPU_cash_invoice_available': False, 'total_local_cash_cost_usd': None,
        'known_tokens_exclude_missing_transport_responses': True, 'groups': groups,
        'completed_GPU_training_loops': training,
        'completed_training_loop_wall_hours_excluding_loading_encoding_and_generation': sum(r['loop_seconds'] for r in training) / 3600,
        'training_hours_are_not_total_project_GPU_hours': True}
    snapshot['CPU_composition_loops'] = [{'path': str(p.parent.relative_to(ROOT)),
        'seconds': load_json(p)['seconds'], 'receipt_sha256': sha(p)}
        for p in sorted((out / 'composition').glob('*/epoch*/complete.json'))]
    probe = out / 'contract_evidence_probe/complete.json'
    snapshot['bounded_GPU_diagnostics'] = [{'path': str(probe.relative_to(ROOT)),
        'receipt_sha256': sha(probe), **load_json(probe)}] if probe.exists() else []
    write_json(out / 'mixed_request_cost_snapshot.json', snapshot)
    write_json(out / 'mixed_physical_request_ledger.json', compact)
    print(json.dumps({'counts': snapshot['continuous_ledger_counts'], 'pending': snapshot['pending'],
        'mixed_physical_requests': len(compact), 'teacher_new': snapshot['phase_new_remote_teacher_requests'],
        'completed_training_loop_wall_hours': snapshot['completed_training_loop_wall_hours_excluding_loading_encoding_and_generation']}))


if __name__ == '__main__':
    main()
