"""Preserve the stopped B5 state before changing lossless input storage only."""
import hashlib
import json
import shutil
import sqlite3

from experiments import legal_skill_evolution_mixed_component_training as training
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.observation_teacher_transport import pack_task, unpack_task


def run():
    root, previous = training.OUT, training.PREVIOUS_OUT
    if (root / 'protocol.json').exists():
        raise ValueError('Already bound; use the existing entry rather than migrate again')
    with sqlite3.connect('file:' + str(training.ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        assert not db.execute('select 1 from calls where id like ?', (previous.name + ':B5:%:update',)).fetchone()
    copied = []
    for name in [f'B{i}' for i in range(1, 6)] + ['component_reads', 'raw_responses']:
        for path in sorted((previous / name).rglob('*')):
            if not path.is_file():
                continue
            target = root / path.relative_to(previous)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError('Migration would overwrite an existing artifact')
            shutil.copy2(path, target)
            copied.append({'path': str(path.relative_to(previous)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    task = training.read(previous / 'B5/teacher_task.json')
    sizes = {}
    for arm, library in task['current_libraries_both_available'].items():
        payload = {**task, 'seed_for_this_arm': library}
        packed = pack_task(payload)
        assert unpack_task(packed) == payload
        sizes[arm] = len(json.dumps(packed, ensure_ascii=False, separators=(',', ':')))
    immutable_json(root / 'resume_receipt.json', {
        'same_goal': True, 'previous_segment': str(previous.relative_to(training.ROOT)),
        'first_four_checkpoints_and_B5_initial_matched_reads_unchanged': True,
        'all_component_outputs_including_errors_preserved': True,
        'same_wire_read_profile_and_original_raw_values': True,
        'teacher_storage_roundtrip_exact': True, 'packed_B5_characters': sizes,
        'new_model_calls_for_migration': 0, 'copied_files': copied,
        'no_DEV_TEST_labels_read': True, 'goal_complete': False})
    print(json.dumps({'files_preserved': len(copied), 'B5_packed_characters': sizes,
        'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
