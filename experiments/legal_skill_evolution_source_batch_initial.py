"""Execute the current source library before a subsequent original TRAIN batch.

Actual source extraction, composition and native consumers are executed; a
static pass with a different library hash cannot stand in for these results.
No model transport is available. Zero current-batch error commits an unchanged
library, recording no new learning credit or claim of complete source truth.
"""
import argparse
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_library_train as train
from experiments.legal_skill_evolution_source_local_preview import NoModel
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def evaluate(library, sid, arm, batch, target):
    if target.exists():
        row = train.read(target)
        assert row['library_sha256'] == digest(library)
        return row
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json')}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    upstream = train.read(train.parent.OUT / 'source_pass/upstream' / train.previous.old.name_for(sid))['source_output']
    old_row = train.read(train.parent.OUT / 'source_pass/ConstraintAcquire' / train.previous.old.name_for(sid))
    units = old_row['observation']['visible_inputs']['units']
    row = {'source': sid, 'arm': arm, 'batch': batch, 'library_sha256': digest(library),
        'new_model_calls': 0, 'fallback': False}
    try:
        observation = train.previous.old.observe(NoModel(), f'{train.RUN}:B{batch}:initial:{arm}:{sid}',
            sid, library, source_text=public[sid]['views'][0]['public']['source_text'],
            units=units, source_output=upstream)
        assert observation['new_model_requests'] == 0
        primary = train.previous.old.previous.prior.prior.evaluate_source(library, observation, public[sid], None)
        immutable_json(target.with_name(target.stem + '_primary.json'), {
            'source': sid, 'observation': observation, 'actual_unscored': primary,
            'library_sha256': digest(library), 'new_model_calls': 0})
        actual = train.previous.old.previous.prior.prior.evaluate_source(library, observation, public[sid], grading[sid])
        row.update(observation=observation, actual=actual,
            correct=sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
            unresolved=sum(not v['core_executed'] for v in actual['feedback']['views']))
    except (ValueError, KeyError, TypeError) as error:
        row.update(error=type(error).__name__ + ': ' + str(error), correct=0, unresolved=len(public[sid]['views']))
    immutable_json(target, row)
    return row


def run(batch):
    protocol = train.prepare()
    keys = [k for k in protocol['mixed_batches'][batch-1] if k in protocol['sources']]
    summaries = []
    for arm in train.ARMS:
        library = train.read(train.OUT / f'B{batch-1}' / arm / 'library.json')
        rows = [evaluate(library, sid, arm, batch,
            train.OUT / f'B{batch}' / arm / 'initial' / train.previous.old.name_for(sid)) for sid in keys]
        summary = {'arm': arm, 'batch': batch, 'current_correct': sum(r['correct'] for r in rows),
            'current_total': 4 * len(rows), 'unresolved': sum(r['unresolved'] for r in rows),
            'library_sha256': digest(library), 'new_model_calls': 0,
            'rows': [{k: r[k] for k in ('source', 'correct', 'unresolved')} for r in rows]}
        immutable_json(train.OUT / f'B{batch}' / arm / 'initial_summary.json', summary)
        summaries.append(summary)
    # A normal zero-residual batch need not call the teacher. Do not skip one
    # arm's update solely because the other arm happened to fit these cases.
    if all(s['current_correct'] == s['current_total'] and not s['unresolved'] for s in summaries):
        for arm in train.ARMS:
            library = train.read(train.OUT / f'B{batch-1}' / arm / 'library.json')
            immutable_json(train.OUT / f'B{batch}' / arm / 'library.json', library)
        immutable_json(train.OUT / f'B{batch}/update_receipt.json', {
            'operation': 'unchanged_library_no_observed_current_batch_native_residual',
            'new_teacher_calls': 0, 'actual_new_batch_execution_not_static_pass_relabeling': True,
            'source_truth_not_certified_by_native_accuracy': True,
            'new_phi_or_G_learning_credit': False, 'goal_complete': False})
    print(json.dumps({'batch': batch, 'initial': summaries,
        'library_checkpoint_saved': (train.OUT / f'B{batch}/ConstraintAcquire/library.json').exists()}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--batch', type=int, choices=range(3, 9), required=True)
    run(p.parse_args().batch)
