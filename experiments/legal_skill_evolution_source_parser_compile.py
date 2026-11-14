"""Compile the saved parser repair; preserve B6 originals and all raw failures."""
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_batch_update as updates
from experiments import legal_skill_evolution_source_parser_feedback as acquisition
from legal_skill_guard.rr.checkpoint import immutable_json


def run():
    train, folder = updates.train, acquisition.OUT
    files = [Path(__file__), Path(updates.__file__), Path(updates.checkpoints.__file__)]
    files += [train.ROOT / 'legal_skill_guard/skill_evolution' / n for n in
        ('lazy_native_selection.py', 'source_selection_certificate.py', 'source_disposal_review.py',
         'open_acquisition.py', 'source_composition.py', 'relational_learning.py', 'relational_rules.py')]
    immutable_json(folder / 'compilation_manifest.json', {'source_sha256': {
        str(p.relative_to(train.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'teacher_task_sha256': hashlib.sha256((folder / 'teacher_task.json').read_bytes()).hexdigest(),
        'new_model_calls': 0})
    rows, failures = {}, {}
    for arm in ('FreeUpdate', 'ConstraintAcquire'):
        try:
            rows[arm] = updates.compile_candidate(train.prepare(), 6, arm,
                task_path=folder / 'teacher_task.json', folder=folder / arm)
            print(json.dumps({'compiled': arm, 'correct': sum(r['correct'] for r in rows[arm]),
                'total': 4*len(rows[arm]), 'new_model_calls': 0}), flush=True)
        except Exception as error:
            failures[arm] = type(error).__name__ + ': ' + str(error)
            print(json.dumps({'failed_compile': arm, 'error': failures[arm]}), flush=True)
    if failures:
        immutable_json(folder / 'compilation_failures.json', failures)
        raise ValueError('Preserved actual compilation failures: ' + str(failures))
    pending = updates.checkpoints.remaining(updates.checkpoints.state(5)['pending_source_semantics'], rows)
    updates.checkpoints.record(6, {a: folder / a / 'library.json' for a in train.ARMS}, pending=pending)


if __name__ == '__main__':
    with (updates.train.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
