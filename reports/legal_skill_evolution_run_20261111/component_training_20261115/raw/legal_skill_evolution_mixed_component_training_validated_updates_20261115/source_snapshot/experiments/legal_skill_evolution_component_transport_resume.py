"""Resume paid B7 proposals after verified request-boundary preservation.

No acquisition is repeated. B1--B6, original B7 initial observations and the
already performed matched reads remain historical. Only B7 candidate validation
is repeated after concrete format/diagnostic repairs, then B8 continues normally.
"""
import hashlib
import json
import shutil
import sqlite3

from experiments import legal_skill_evolution_mixed_component_training as training
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_teacher_transport import unpack_task


def run():
    root, previous = training.OUT, training.PREVIOUS_OUT
    if (root / 'protocol.json').exists():
        raise ValueError('Already bound; use the existing training entry')
    assert training.read(previous / 'unbound_safe_stop_verified.json')['reserved_count'] == 0
    with sqlite3.connect('file:' + str(training.ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        task = training.read(previous / 'B7/teacher_task.json')
        paid = []
        for arm in training.ARMS:
            identity = previous.name + ':B7:' + arm + ':update'
            row = db.execute('select status,result from calls where id=?', (identity,)).fetchone()
            assert row and row[0] == 'completed'
            response = training.read(previous / 'B7' / arm / 'teacher.json')
            assert json.loads(row[1])['response_sha256'] == response['response_sha256']
            request = training.read(previous / 'calls' / digest(identity) / 'request.json')
            expected = {**task, 'seed_for_this_arm': task['current_libraries_both_available'][arm]}
            assert unpack_task(json.loads(request['user_prompt'])) == expected
            paid.append({'arm': arm, 'physical_call_id': identity,
                'response_sha256': response['response_sha256'], 'original_complete_task_unchanged': True})
    copied = []

    def preserve(path, relative):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError('Migration would overwrite an artifact')
        shutil.copy2(path, target)
        copied.append({'original': str(path.relative_to(training.ROOT)), 'relative': str(relative),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    for name in [f'B{i}' for i in range(1, 7)] + ['component_reads', 'raw_responses']:
        for path in sorted((previous / name).rglob('*')):
            if path.is_file():
                preserve(path, path.relative_to(previous))
    for name in ('initial', 'matched_reads', 'matched_raw'):
        for path in sorted((previous / 'B7' / name).rglob('*')):
            if path.is_file():
                preserve(path, path.relative_to(previous))
    for name in ('teacher_task.json', 'initial_scored_results.json', 'inherited_routes.json'):
        path = previous / 'B7' / name
        preserve(path, path.relative_to(previous))
    for arm in training.ARMS:
        path = previous / 'B7' / arm / 'teacher.json'
        preserve(path, path.relative_to(previous))
        for path in (previous / 'B7/post' / (arm + '/retained')).glob('*.json'):
            preserve(path, path.relative_to(previous))
    for path in (previous / 'B7/invalid_proposals').rglob('*.json'):
        preserve(path, 'B7/pre_repair_invalid_proposals' / path.relative_to(previous / 'B7/invalid_proposals'))
    immutable_json(root / 'resume_receipt.json', {
        'same_goal': True, 'previous_segment': str(previous.relative_to(training.ROOT)),
        'first_six_checkpoints_unchanged': True,
        'original_B7_initial_and_matched_reads_unchanged_not_repeated': True,
        'original_B7_checkpoint_preserved_in_previous_segment': True,
        'B7_paid_teacher_proposals_reused': paid,
        'B7_candidate_validation_repeated_after_concrete_code_changes': True,
        'no_NEW_B7_teacher_or_unchanged_model_retry': True,
        'new_model_calls_for_migration': 0, 'copied_files': copied,
        'no_DEV_TEST_labels_read': True, 'goal_complete': False})
    print(json.dumps({'files_preserved': len(copied), 'paid_teacher_proposals_reused': len(paid),
        'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
