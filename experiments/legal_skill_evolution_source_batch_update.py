"""Normal incremental C/control acquisition after a real mixed-batch residual.

The common consumer and actual source scope are preserved. A certificate for
an unchanged G is reused only when its concrete residual context is identical
and its loss/edit lower bounds are attained on all supplied sources. Otherwise
use the existing exact projected-output learner; partial search is not a fit.
"""
import argparse
from copy import deepcopy
import fcntl
import json

from experiments import legal_skill_evolution_source_batch_initial as initial
from experiments import legal_skill_evolution_source_library_train as train
from experiments import legal_skill_evolution_source_checkpoints as checkpoints
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, INSTRUCTION, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT


def make_task(protocol, batch):
    target = train.OUT / f'B{batch}/teacher_task.json'
    if target.exists():
        return train.read(target)
    prior = train.read(train.OUT / 'B2/teacher_task.json')
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    current_ids = [s for s in protocol['mixed_batches'][batch-1] if s in protocol['sources']]
    seen = list(dict.fromkeys(protocol['inherited_warmstart_sources'] + [
        s for b in protocol['mixed_batches'][:batch] for s in b if s in protocol['sources']]))
    libraries = {a: checkpoints.load(batch-1, a) for a in train.ARMS}
    tasks = []
    for sid in seen:
        units = train.read(train.parent.OUT / 'source_pass/ConstraintAcquire' /
            train.previous.old.name_for(sid))['observation']['visible_inputs']['units']
        actual = {}
        for arm, library in libraries.items():
            row = initial.evaluate(library, sid, arm, batch, train.OUT / f'B{batch}' / arm /
                'pre_update_seen' / train.previous.old.name_for(sid))
            if 'actual' not in row:
                actual[arm] = {'error': row.get('error'), 'correct': row['correct'], 'unresolved': row['unresolved']}
            else:
                value = row['actual']
                actual[arm] = {'statements': value['execution']['source_output']['statements'],
                    'unresolved': value['execution']['source_output']['unresolved'],
                    'native_feedback': value['feedback'], 'correct': row['correct'], 'unresolved_views': row['unresolved']}
        tasks.append({'source_id': sid, 'current_batch': sid in current_ids,
            'full_source_text': public[sid]['views'][0]['public']['source_text'], 'source_units': units,
            'incoming_source_output': train.read(train.parent.OUT / 'source_pass/upstream' /
                train.previous.old.name_for(sid))['source_output'],
            'native_TRAIN_supervision': grading[sid], 'actual_current': actual})
    task = {key: deepcopy(prior[key]) for key in ('common_frozen_consumer',
        'common_observed_signatures', 'source_function_patch_code', 'encoder_code', 'observer_code',
        'prior_partial_source_reviews_and_failed_replacements')}
    assert libraries['ConstraintAcquire']['spec']['decision_program'] == libraries['FreeUpdate']['spec']['decision_program']
    task['common_frozen_consumer'] = libraries['ConstraintAcquire']['spec']['decision_program']
    review_path = train.OUT / 'B5/shared_source_disposal_reviews.json'
    if review_path.exists():
        task['shared_reviewed_source_scope_checks'] = train.read(review_path)
        task['source_scope_check_code'] = (train.ROOT / 'legal_skill_guard/skill_evolution/source_disposal_review.py').read_text()
    task.update(batch=batch, current_sources=current_ids, tasks=tasks, current_libraries=libraries,
        pending_source_semantics=checkpoints.state(batch-1)['pending_source_semantics'],
        actual_current_batch_results={a: train.read(train.OUT / f'B{batch}' / a / 'initial_summary.json') for a in train.ARMS},
        previous_repair_receipts={f'B{b}/{a}': train.read(train.OUT / f'B{b}' / a / 'update_result.json')
            for b in range(2, batch) for a in train.ARMS if (train.OUT / f'B{b}' / a / 'update_result.json').exists()},
        source_function_updates_allowed_to_fix_actual_errors_not_only_one_phrase=True,
        new_sources_or_synthetic_cases=0, inherited_exposure_not_a_blind_new_split=True,
        future_source_texts_or_labels_not_in_this_update=True)
    immutable_json(target, task)
    return task


def acquire(protocol, batch, ledger):
    task = make_task(protocol, batch)
    # Remove the closed B2-specific diagnosis; retain the original architecture,
    # strong-control freedoms, source semantic constraints and public repairs.
    system = train.SYSTEM
    start = system.index('In the current second-batch residual,')
    end = system.index('Keep old valid source abilities', start)
    system = system[:start] + 'Diagnose the actual current-batch residuals in the task, using the full source and the current complete libraries.\n\n' + system[end:]
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
    for arm in train.ARMS:
        path = train.OUT / f'B{batch}' / arm / 'teacher.json'
        if path.exists():
            continue
        prompt = system + '\n' + (train.previous.old.C_PART + '\n' + train.previous.old.previous.prior.prior.C_SPEC
            if arm == 'ConstraintAcquire' else train.previous.old.FREE_PART)
        prompt += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
        prompt += '\nAllowed attributes: ' + ','.join(sorted(train.previous.old.METHODS))
        prompt += '\nAllowed calls: ' + ','.join(sorted(train.previous.old.CALLS))
        size = len(render_structured_codex_prompt(prompt, user))
        assert size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(path.with_name('preflight.json'), {'task_sha256': digest(task),
            'characters': size, 'same_information_both_arms': True, 'schema_issues': []})
        result = FrozenTeacher(ledger, train.OUT, protocol['teacher_profile']).propose(
            ledger.run_id + f':B{batch}:' + arm + ':update', source_ids=[t['source_id'] for t in task['tasks']],
            system_prompt=prompt, user_prompt=user, output_schema=train.previous.schema_for(arm))
        immutable_json(path, result)
        print(json.dumps({'source_teacher_saved': arm, 'batch': batch}), flush=True)


def compile_candidate(protocol, batch, arm):
    task = train.read(train.OUT / f'B{batch}/teacher_task.json')
    folder = train.OUT / f'B{batch}' / arm
    if (folder / 'library.json').exists():
        return
    old = task['current_libraries'][arm]
    raw = deepcopy(train.read(folder / 'teacher.json')['value'])
    program, preservation = apply_function_edits(old['source_program'], raw.pop('source_function_edits'))
    raw['source_program'] = program
    assert raw['decision_functions'] == []
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    library, receipt, proposal = train.previous.old.compile_raw(old, raw, arm, public)
    library['spec']['decision_program'] = task['common_frozen_consumer']
    if arm == 'ConstraintAcquire':
        library['selected_rule_ids'] = library['suggested_rule_ids']
    immutable_json(folder / 'compiled_candidate.json', library)
    immutable_json(folder / 'function_patch_preservation.json', preservation)
    immutable_json(folder / 'compilation_receipt.json', receipt)
    rows = [initial.evaluate(library, t['source_id'], arm, batch,
        folder / 'candidate_results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
    if any('observation' not in row for row in rows):
        raise ValueError('Actual candidate execution failed; preserve raw output before a specific repair')
    from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
    reviews = task.get('shared_reviewed_source_scope_checks', [])
    def checker_for(sid):
        original = train.previous.old.previous.prior.prior.checker(library, public[sid], grading[sid])
        return with_disposal_review(original, sid, reviews, library['spec']['decision_program'])
    if arm == 'ConstraintAcquire':
        from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
        from legal_skill_guard.skill_evolution.open_acquisition import fit
        from legal_skill_guard.skill_evolution.theory_supervision import attach_scored_theories
        from legal_skill_guard.skill_evolution.source_selection_certificate import certify_unchanged_selection
        def profile_for(sid, observation):
            path = folder / 'source_checked_profiles' / train.previous.old.name_for(sid)
            if path.exists():
                return train.read(path)
            profile = admissible_projected_compositions(library, observation, checker_for(sid), timeout_seconds=90)
            immutable_json(path, profile)
            return profile
        certificate = certify_unchanged_selection(library, old['selected_rule_ids'], rows, checker_for, profile_for)
        immutable_json(folder / 'current_selection_diagnosis.json', certificate)
        if certificate['certified']:
            immutable_json(folder / 'selection_certificate.json', certificate)
        else:
            observations = []
            for row in rows:
                profile = profile_for(row['source'], row['observation'])
                assert profile['status'] == 'complete', 'Incomplete search cannot become scored training constraints'
                observations.append(attach_scored_theories(row['observation'], profile))
            library, result = fit(library, observations, prior_rule_ids=old['selected_rule_ids'], timeout_seconds=90)
            immutable_json(folder / 'fit.json', result)
            assert result['status'] == 'sat', 'Keep incomplete fit and candidate; no fitted checkpoint is invented'
            rows = [initial.evaluate(library, t['source_id'], arm, batch,
                folder / 'fitted_results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
    source_checks = []
    for row in rows:
        feedback = checker_for(row['source'])(row['actual']['execution']['source_output'])
        source_checks.append({'source': row['source'], 'source_review_passed': feedback.get('source_review_passed', True),
            'reviewed_disposal_scope_violations': feedback.get('reviewed_disposal_scope_violations', [])})
    immutable_json(folder / 'shared_source_review_results.json', {'rows': source_checks,
        'same_checks_both_arms': True, 'unreviewed_fields_not_negatives': True})
    assert all(r['source_review_passed'] for r in source_checks), 'Candidate fails actual shared source review; keep raw proposal and failures'
    immutable_json(folder / 'library.json', library)
    immutable_json(folder / 'update_result.json', {'arm': arm, 'batch': batch,
        'all_supplied_correct': sum(r['correct'] for r in rows), 'all_supplied_total': len(rows) * 4,
        'current_correct': sum(r['correct'] for r in rows if r['source'] in task['current_sources']),
        'current_total': len(task['current_sources']) * 4, 'unresolved': sum(r['unresolved'] for r in rows),
        'row_summary': [{k: r[k] for k in ('source', 'correct', 'unresolved')} for r in rows],
        'native_accuracy_not_source_semantic_certification': True, 'new_model_calls_during_compile': 0,
        'goal_complete': False})
    return rows


def finalize(batch, rows_by_arm):
    pending = checkpoints.remaining(checkpoints.state(batch-1)['pending_source_semantics'], rows_by_arm)
    checkpoints.record(batch, {a: train.OUT / f'B{batch}' / a / 'library.json' for a in train.ARMS}, pending=pending)


def run(start, stop, ledger):
    protocol = train.prepare()
    for batch in range(start, stop + 1):
        initial.run(batch)
        if not checkpoints.exists(batch):
            acquire(protocol, batch, ledger)
            rows_by_arm = {}
            for arm in train.ARMS:
                rows_by_arm[arm] = compile_candidate(protocol, batch, arm) or []
            finalize(batch, rows_by_arm)
        print(json.dumps({'source_batch_completed': batch}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, choices=range(4, 9), default=4)
    parser.add_argument('--stop', type=int, choices=range(4, 9), default=8)
    args = parser.parse_args()
    with (train.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        from experiments.legal_skill_evolution_mixed_training_continue import setup
        run(args.start, args.stop, setup()[1])
