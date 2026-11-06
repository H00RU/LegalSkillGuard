"""Actual saved-call restore under denied network; never spend a reservation."""
import json
import socket
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def snapshot():
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        return {t: db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall() for t in ['calls', 'meta', 'oracle_views']}


def main():
    sys.path.insert(0, str(ROOT))
    from legal_skill_guard.rr.client import ExecutorClient
    from legal_skill_guard.rr.coverage import digest
    from legal_skill_guard.rr.cumulative_repair import STAGE, inputs, load
    from legal_skill_guard.rr.ledger import BudgetLedger
    from legal_skill_guard.rr.preflight import atomic_json
    from legal_skill_guard.rr.schema_validation import validate_response

    before = snapshot()
    if any(r[6] == 'reserved' for r in before['calls']):
        raise RuntimeError('Wait for the existing physical request; never restart it')
    cfg, data = inputs(ROOT)
    current_revision = json.loads((ROOT / 'docs/rr_v2/runtime_state.json').read_text())['last_repair_revision']
    seal, _, _ = load(ROOT, current_revision)
    restored, revalidated, failed_preserved = [], [], []
    def deny(*args, **kwargs):
        raise RuntimeError('Network and dispatch forbidden during saved-output restore')
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
            patch.object(ExecutorClient, '_wire', deny), patch.object(ExecutorClient, 'tokenize', deny):
        for row in before['calls']:
            call_id, role, purpose, _, source, request_hash, status, _, result_json = row
            if not call_id.startswith('cumulative:'):
                continue
            if status != 'completed':
                assert status == 'failed'
                failed_preserved.append(call_id)
                continue  # retain the charged failure, never redispatch it
            revision = call_id.split(':')[1]
            stage = ROOT / STAGE / revision
            frozen = json.loads((stage / 'seal.json').read_text())
            ledger = BudgetLedger(ROOT / cfg['ledger_path'], sources=data.manifest['allowlist'],
                code_hash=frozen['binding']['code_hash'], config_hash=frozen['binding']['config_hash'])
            request = json.loads((stage / 'calls' / digest(call_id) / 'request.json').read_text())
            payload = request['payload']
            result = ExecutorClient(ledger, stage, frozen['config']['executor']).generate(call_id,
                source=source, purpose=purpose, messages=payload['messages'], thinking=True,
                schema=payload['response_format']['json_schema']['schema'])
            assert result['cache_hit'] and result['content'] == json.loads(result_json)['content']
            assert result['request_hash'] == request_hash
            restored.append(call_id)
            if revision == current_revision:
                replay = validate_response(data.public(source), data.grade(source), result['content'])
                saved = json.loads((stage / 'validations' / (digest(call_id) + '.json')).read_text())
                saved.pop('wire_request_hash')
                # Compare persisted JSON values; dataclass context tuples serialize as arrays.
                assert json.loads(json.dumps(replay, allow_nan=False)) == saved
                revalidated.append(call_id)
    assert snapshot() == before
    evidence = {'network_blocked': True, 'physical_requests_added': 0, 'teacher_requests_added': 0,
                'oracle_rows_added': 0, 'ledger_rows_and_meta_exactly_unchanged': True,
                'restored_call_ids': restored, 'current_revision_revalidated': revalidated,
                'failed_call_ids_preserved_without_redispatch': failed_preserved,
                'current_binding': seal['binding'], 'all_passed': True}
    atomic_json(Path(__file__).parent / 'actual_restore_verified.json', evidence)
    print(json.dumps({'restored': len(restored), 'current_revision_revalidated': len(revalidated), 'new_calls': 0}))


if __name__ == '__main__':
    main()
