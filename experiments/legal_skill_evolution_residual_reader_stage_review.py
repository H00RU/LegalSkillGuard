"""Settle the existing matched TRAIN reads without creating a model client."""
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ROOT = Path(__file__).resolve().parents[1]
MATCHED = ROOT / 'artifacts/legal_skill_evolution_residual_reader_matched_20261115'
RECOVERY = ROOT / 'artifacts/legal_skill_evolution_residual_reader_recovery_20261115'
OUT = ROOT / 'artifacts/legal_skill_evolution_residual_reader_stage_review_20261115'


def read(path):
    return json.loads(path.read_text())


def run():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = list(map(dict, db.execute('SELECT * FROM calls ORDER BY rowid')))
    prefixes = []
    for folder in (MATCHED, RECOVERY):
        before = read(folder / 'protocol.json')['ledger_before']
        actual = digest([tuple(row.values()) for row in rows[:before['rows']]])
        assert actual == before['sha256']
        prefixes.append({'protocol': str((folder / 'protocol.json').relative_to(ROOT)), **before,
                         'all_original_fields_unchanged': True})

    charged = []
    for row in rows:
        if not row['id'].startswith((MATCHED.name + ':', RECOVERY.name + ':')):
            continue
        value = json.loads(row['result'])
        path = ROOT / value['artifact_directory'] / 'wire_request.json'
        saved = read(path)
        body = base64.b64decode(saved['body_b64'])
        assert hashlib.sha256(body).hexdigest() == saved['body_sha256']
        wire = json.loads(body)
        assert wire['chat_template_kwargs']['enable_thinking'] is False
        assert wire['max_tokens'] == 8192 and wire['temperature'] == .6 and wire['seed'] == 45
        assert value['finish_reason'] == 'stop' and row['status'] == 'completed'
        task = json.loads(wire['messages'][1]['content'])['task']
        facts_only = row['id'].startswith(MATCHED.name + ':')
        if facts_only:
            assert set(task['current_case']) == {'facts'}
            assert 'current_legal_query' not in task
        charged.append({k: row[k] for k in ('id', 'role', 'source', 'status')} | {
            'usage': value['usage'], 'elapsed_seconds': value['elapsed_seconds'],
            'finish_reason': value['finish_reason'], 'wire_sha256': saved['body_sha256'],
            'facts_only_service_read': facts_only, 'thinking_OFF_verified': True,
            'row_sha256': digest(tuple(row.values()))})
    assert len(charged) == 7 and all(r['role'] == 'executor' for r in charged)

    recovery = read(RECOVERY / 'result.json')
    outcomes = []
    for pair in recovery['pairs']:
        outcomes.append({'source': pair['source'], 'policies': {
            name: {'before_core_correct': value['before']['source_checked_core_success'],
                   'after_core_correct': value['recovered']['source_checked_core_correct'],
                   'handled': value['recovered']['execution']['handled'],
                   'native_score': value['recovered']['native_score'],
                   'partial_source_failures': value['recovered']['partial_source_review']['failures']}
            for name, value in pair['policies'].items()}})
    gains = {name: sum(p['policies'][name]['after_core_correct'] for p in outcomes)
             for name in ('residual_guided', 'ordinary_reread')}
    assert gains == {'residual_guided': 1, 'ordinary_reread': 1}
    parity = recovery['previous_compiled_observation_conversion_parity']
    complete = [r for r in parity if r['previous_complete']]
    assert all(r['exact_conversion_equal'] for r in complete)
    checks = read(RECOVERY / 'unbound_checks.json')
    assert checks['returncode'] == 0

    family = read(RECOVERY / 'common_family_result.json')
    view = family['shared_family_observation']['family_relationship_residence']['views'][0]
    result = {
        'no_new_model_client_or_requests': True, 'previous_ledger_prefixes': prefixes,
        'cumulative': {role: sum(r['role'] == role for r in rows) for role in ('executor', 'teacher')},
        'cumulative_status': {role: {status: sum(r['role'] == role and r['status'] == status for r in rows)
            for status in ('completed', 'failed', 'reserved')} for role in ('executor', 'teacher')},
        'new_physical_requests': {'executor': len(charged), 'teacher': 0}, 'calls': charged,
        'new_usage': {field: sum(c['usage'][field] for c in charged)
            for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'serial_model_request_seconds': sum(c['elapsed_seconds'] for c in charged),
        'actual_cash_invoice_and_GPU_allocation_unknown': True,
        'paired_core_correct': gains, 'pairs': outcomes,
        'compiled_conversion_parity': {'total': len(parity), 'previously_complete': len(complete),
            'previously_complete_exactly_unchanged': True,
            'changed_previously_incomplete': sum(not r['exact_conversion_equal'] for r in parity)},
        'shared_family': {'source': family['source'], 'raw_view': view,
            'core_correct': {k: v['source_checked_core_correct'] for k, v in family['policies'].items()},
            'converted_world_zero_source_failures_is_not_raw_semantic_success': True,
            'manual_source_review': {
                'source_relation': 'Alice pays her father Bob for work; Bob is father of Alice.',
                'raw_relation_error': 'related_person Bob is labeled daughter of reference_person Alice.',
                'unsupported_assertions': ['shared home', 'kinship interval copied from work dates'],
                'rejected_by_unchanged_converter': True,
                'no_unambiguous_semantics_preserving_repair_available': True}},
        'targeted_tests': {'returncode': checks['returncode'], 'stdout': checks['stdout']},
        'frozen_DEV_unchanged': True, 'no_TEST_or_new_sources': True,
        'shared_transport_repairs_are_not_method_contributions': True, 'goal_complete': False}
    immutable_json(OUT / 'cost_and_integrity.json', result)
    print(json.dumps({k: result[k] for k in ('cumulative', 'new_physical_requests', 'new_usage',
                                          'paired_core_correct', 'compiled_conversion_parity')}))


if __name__ == '__main__':
    run()
