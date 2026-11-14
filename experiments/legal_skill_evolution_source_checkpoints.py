"""Current source checkpoints reference immutable library versions.

A shared execution-interface repair can install a new version without changing
the paid proposal, original library or any historical execution record.
"""
from experiments import legal_skill_evolution_source_library_train as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def record(batch, paths, *, pending):
    libraries = {arm: {'path': str(path.relative_to(train.ROOT)),
        'library_sha256': digest(train.read(path))} for arm, path in paths.items()}
    assert set(libraries) == set(train.ARMS)
    immutable_json(train.OUT / f'B{batch}/checkpoint.json', {
        'batch': batch, 'libraries': libraries, 'pending_source_semantics': pending,
        'old_versions_and_calls_preserved': True})


def exists(batch):
    return (train.OUT / f'B{batch}/checkpoint.json').exists()


def state(batch):
    return train.read(train.OUT / f'B{batch}/checkpoint.json')


def load(batch, arm):
    item = state(batch)['libraries'][arm]
    library = train.read(train.ROOT / item['path'])
    assert digest(library) == item['library_sha256'], 'Checkpoint library bytes/meaning changed'
    return library


def remaining(pending, rows_by_arm):
    """Recognize the already-declared guarded-action normal form for this issue.

    Unrecognized representations stay pending for source review; they are not
    declared false, used as negative training facts, or called semantically valid.
    """
    result = []
    for issue in pending:
        rows = rows_by_arm.get(issue['arm'], [])
        row = next((r for r in rows if r['source'] == issue['source']), None)
        if row is None:
            result.append(issue)
            continue
        from legal_skill_guard.skill_evolution.source_disposal_review import branch_authorization_preserved
        if not branch_authorization_preserved(row['actual']['execution']['source_output'], issue['source_unit_ids']):
            result.append(issue)

    return result
