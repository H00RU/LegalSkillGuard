"""Preserve B1--B7 and B8 initial reads across lossless reference storage repair."""
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
        raise ValueError('Already bound; use the existing training entry')
    assert training.read(previous / 'unbound_B8_transport_safe_stop.json')['reserved_count'] == 0
    with sqlite3.connect('file:' + str(training.ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        assert not db.execute('select 1 from calls where id like ?', (previous.name + ':B8:%:update',)).fetchone()
    copied = []
    for name in [f'B{i}' for i in range(1, 9)] + ['component_reads', 'raw_responses']:
        for path in sorted((previous / name).rglob('*')):
            if not path.is_file():
                continue
            target = root / path.relative_to(previous)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError('Migration would overwrite an artifact')
            shutil.copy2(path, target)
            copied.append({'original': str(path.relative_to(training.ROOT)),
                'relative': str(path.relative_to(previous)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    task = training.read(previous / 'B8/teacher_task.json')
    evidence = []
    dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    for arm, library in task['current_libraries_both_available'].items():
        payload = {**task, 'seed_for_this_arm': library}
        packed = pack_task(payload)
        assert dump(unpack_task(packed)) == dump(payload)
        evidence.append({'arm': arm, 'full_task_serialized_sha256': hashlib.sha256(dump(payload).encode()).hexdigest(),
            'packed_characters': len(dump(packed)), 'exact_value_type_and_key_order_roundtrip': True})
    immutable_json(root / 'resume_receipt.json', {
        'same_goal': True, 'previous_segment': str(previous.relative_to(training.ROOT)),
        'B1_through_B7_checkpoints_unchanged': True,
        'B8_initial_and_original_matched_reads_unchanged_not_repeated': True,
        'B8_teacher_previous_dispatches': 0, 'compact_reference_storage_evidence': evidence,
        'no_source_program_error_supervision_or_cost_metadata_omitted': True,
        'new_model_calls_for_migration': 0, 'copied_files': copied,
        'no_DEV_TEST_labels_read': True, 'goal_complete': False})
    print(json.dumps({'files_preserved': len(copied), 'B8_full_task_roundtrips': evidence,
        'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
