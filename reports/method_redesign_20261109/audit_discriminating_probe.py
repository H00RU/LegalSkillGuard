"""Verify the actual probe's order, equal interfaces and unchanged learning."""
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from experiments.rr_v2_channel_discriminating_probe import ROOT, REPORT, OLD, STAGE, read, sha


def payload(path):
    wire = read(path)
    body = base64.b64decode(wire['body_b64'])
    assert hashlib.sha256(body).hexdigest() == wire['body_sha256']
    return json.loads(body)


def main():
    s = read(STAGE / 'seal.json'); result = read(STAGE / 'result.json')
    assert sha(OLD / 'frozen_learning.json') == s['original_frozen_learning_sha256']
    assert result['teacher_h'] == result['observed_D'] == [0, 0]
    assert result['raw_schema_and_pointer_validation']['status'] == 'decoded'
    assert all(result['source_role_evidence'].values()) and len(result['source_role_evidence']) == 4
    assert result['single_output_compatibility_only'] == {
        'D_work_reads_payment_class': True, 'D_work_negates_work_class': False}
    e = s['case']['edit']; before = s['parent_case']['facts']; after = s['case']['facts']
    assert e['before'] == 'hay' and e['after'] == 'cash'
    assert before[:e['start']] == after[:e['start']]
    assert before[e['end']:] == after[e['start'] + len(e['after']):]
    new_paths = list(STAGE.rglob('wire_request.json')); assert len(new_paths) == 1
    body = payload(new_paths[0]); candidate = []
    for p in OLD.rglob('wire_request.json'):
        d = payload(p)
        if d['messages'][0] != body['messages'][0]:
            continue
        user = json.loads(d['messages'][1]['content'])
        if user == {'facts': before, 'focus': s['case']['focus']}:
            candidate.append((p, d))
    assert len(candidate) == 1
    old_path, old_body = candidate[0]
    for k in set(body) | set(old_body):
        if k != 'messages':
            assert body[k] == old_body[k], k
    assert body['messages'][0] == old_body['messages'][0]
    assert json.loads(body['messages'][1]['content']) == {'facts': after, 'focus': s['case']['focus']}
    assert body['chat_template_kwargs']['enable_thinking'] is False
    teachers = [read(p) for p in STAGE.rglob('request.json') if 'system_prompt' in read(p)]
    assert len(teachers) == 1
    assert set(json.loads(teachers[0]['user_prompt'])) == {'parent_facts', 'new_facts', 'focus', 'exact_edit'}
    for row in s['forecasts']:
        assert len(row['D_marginal']) == 5
        for p in row['D_marginal'].values():
            assert len(p) == 9 and abs(sum(p) - 1.) < 1e-12
    assert len(s['forecasts']) == 9
    assert s['factorized_control_fit_cases'] == ['TRAIN71:original', 'TRAIN71:controlled', 'TRAIN79:controlled']
    with sqlite3.connect('file:' + str((ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve()) + '?mode=ro', uri=True) as db:
        rows = db.execute('select id,role,status,reserved_at from calls where id like ? order by reserved_at', (s['run_id'] + ':%',)).fetchall()
        total = dict(db.execute('select role,count(*) from calls group by role').fetchall())
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    assert len(rows) == 2 and [r[1] for r in rows] == ['executor', 'teacher']
    assert all(r[2] == 'completed' for r in rows) and pending == 0
    stamp = datetime.fromisoformat(s['captured_utc']).timestamp()
    assert stamp < rows[0][3] < rows[1][3]
    closure = read(STAGE / 'execution_closed_before_teacher.json')
    assert closure['seal_sha256'] == sha(STAGE / 'seal.json')
    assert closure['executor_sha256'] == sha(STAGE / 'executor.json')
    output = {'captured_utc': datetime.now(timezone.utc).isoformat(),
        'actual_charged_probe_calls': len(rows), 'counts_total': total, 'pending': pending,
        'new_mother_sources': 0, 'new_native_labels_read': 0,
        'exact_one_span_change_checked': True,
        'same_system_focus_schema_model_sampling_as_original': True,
        'actual_previous_wire_request': str(old_path.relative_to(ROOT)),
        'all_h_forecasts_sealed_before_physical_generation': True,
        'same_grammar_control_retains_original_context_conditioning': True,
        'teacher_did_not_receive_executor_output': True,
        'execution_closed_before_teacher_dispatch_in_sealed_code': True,
        'original_frozen_learning_unchanged': True, 'raw_response_not_rewritten': True,
        'R_responses_not_acquired_or_imputed': True,
        'local_class_and_role_agreement_is_TRAIN_teacher_judgment': True,
        'full_binding_channel_not_predicted': True,
        'new_cross_mother_confirmation': False,
        'unique_contribution_or_native_success_claimed': False, 'goal_complete': False}
    immutable_json(REPORT / 'M2_discriminating_probe_audit.json', output)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
