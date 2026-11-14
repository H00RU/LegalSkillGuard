"""Resolve actual branch-scope review and compact audit metadata, preserving versions.

The original checkpoint and complete G proof stay intact. No learned program,
rule, observation, source output, native score or physical ledger row changes.
"""
from copy import deepcopy
import fcntl
import json

from experiments import legal_skill_evolution_source_batch_update as updates
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    train, checkpoints = updates.train, updates.checkpoints
    folder = train.OUT / 'B6/post_semantic_review'
    old = checkpoints.state(6)
    # Already promoted: verify the immutable review instead of repeating it.
    if all('/post_semantic_review/' in v['path'] for v in old['libraries'].values()):
        assert not old['pending_source_semantics']
        return
    rows, paths, metadata = {}, {}, []
    original = train.OUT / 'B6/source_parser_correction'
    task = train.read(original / 'teacher_task.json')
    for arm in train.ARMS:
        library = checkpoints.load(6, arm)
        before = deepcopy(library)
        if 'fit' in library and 'fully_checked_selection' in library['fit']:
            value = library['fit']['fully_checked_selection']
            library['fit']['fully_checked_selection'] = {k: value[k] for k in
                ('selected_rule_ids', 'native_loss', 'native_loss_by_context', 'selection_edits', 'complexity')}
        assert {k:v for k,v in before.items() if k!='fit'} == {k:v for k,v in library.items() if k!='fit'}
        path = folder / arm / 'library.json'
        immutable_json(path, library)
        paths[arm] = path
        completed = original / arm / ('fitted_results' if arm == 'ConstraintAcquire' else 'candidate_results')
        rows[arm] = [train.read(completed / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
        metadata.append({'arm': arm, 'before_library_sha256': digest(before), 'after_library_sha256': digest(library),
            'all_fields_except_fit_metadata_identical': True,
            'before_serialized_bytes': len(json.dumps(before)), 'after_serialized_bytes': len(json.dumps(library))})
    pending = checkpoints.remaining(old['pending_source_semantics'], rows)
    assert not pending, 'Do not clear an unrecognized or incorrectly attached authorization'
    issue = old['pending_source_semantics'][0]
    row = next(r for r in rows[issue['arm']] if r['source'] == issue['source'])
    norms = [s for s in row['actual']['execution']['source_output']['statements']
        if s['term'][0]=='disposal_obligation' and set(s['support_ids']) & set(issue['source_unit_ids'])]
    definition = next(c for c in checkpoints.load(6, issue['arm'])['spec']['constructors']
        if c['name']=='acquired_joint_exception_scope_v3')
    immutable_json(folder / 'branch_authorization_review.json', {'issue': issue, 'actual_source_norms': norms,
        'existing_constructor_definition': definition,
        'finding': 'The declared joint exception type separately retains the two connected action scopes. Actual return is no_acquired_exception; destruction is written_authorization with the unchanged original source quote. The earlier recognizer only supported authorized_action_alternative, so its remaining flag was validation coverage, not a surviving source omission.',
        'no_generated_output_or_law_changed_by_review': True, 'native_label_not_used_to_clear_issue': True})
    immutable_json(folder / 'previous_checkpoint.json', old)
    new = {'batch':6, 'libraries': {a: {'path': str(p.relative_to(train.ROOT)),
        'library_sha256':digest(train.read(p))} for a,p in paths.items()},
        'pending_source_semantics': pending, 'old_versions_and_calls_preserved': True}
    immutable_json(folder / 'reviewed_checkpoint.json', new)
    immutable_json(folder / 'receipt.json', {'previous_checkpoint_sha256':digest(old),
        'reviewed_checkpoint_sha256':digest(new), 'metadata':metadata,
        'only_current_checkpoint_pointer_promoted':True,'old_checkpoint_bytes_and_libraries_preserved':True,
        'all_original_responses_scores_and_calls_unchanged':True,'new_model_calls':0,'goal_complete':False})
    target = train.OUT / 'B6/checkpoint.json'
    temporary = target.with_name('.reviewed_checkpoint.tmp')
    temporary.write_bytes((folder/'reviewed_checkpoint.json').read_bytes())
    temporary.replace(target)
    print(json.dumps({'B6_source_checkpoint_reviewed': True, 'pending': len(pending), 'metadata': metadata}), flush=True)


if __name__ == '__main__':
    with (updates.train.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
