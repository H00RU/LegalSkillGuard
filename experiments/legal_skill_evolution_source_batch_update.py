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
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json')}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    current_ids = [s for s in protocol['mixed_batches'][batch-1] if s in protocol['sources']]
    seen = list(dict.fromkeys(protocol['inherited_warmstart_sources'] + [
        s for b in protocol['mixed_batches'][:batch] for s in b if s in protocol['sources']]))
    libraries = {a: train.read(train.OUT / f'B{batch-1}' / a / 'library.json') for a in train.ARMS}
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
    task.update(batch=batch, current_sources=current_ids, tasks=tasks, current_libraries=libraries,
        actual_current_batch_results={a: train.read(train.OUT / f'B{batch}' / a / 'initial_summary.json') for a in train.ARMS},
        previous_repair_receipts={f'B{b}/{a}': train.read(train.OUT / f'B{b}' / a / 'update_result.json')
            for b in range(2, batch) for a in train.ARMS if (train.OUT / f'B{b}' / a / 'update_result.json').exists()},
        source_function_updates_allowed_to_fix_actual_errors_not_only_one_phrase=True,
        new_sources_or_synthetic_cases=0, inherited_exposure_not_a_blind_new_split=True,
        future_source_texts_or_labels_not_in_this_update=True)
    immutable_json(target, task)
    return task


def acquire(protocol, batch):
    task = make_task(protocol, batch)
    ledger = EvolutionLedger(train.ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=train.RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
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
            train.RUN + f':B{batch}:' + arm + ':update', source_ids=[t['source_id'] for t in task['tasks']],
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
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json')}
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
    if arm == 'ConstraintAcquire':
        prior_certificate = train.read(train.OUT / 'B2/ConstraintAcquire/selection_certificate.json')
        witness = next(r for r in rows if '8fb38aee' in r['source'])
        before = train.read(train.OUT / 'B2/ConstraintAcquire/candidate_results' / train.previous.old.name_for(witness['source']))
        unchanged_bias = all(library[k] == old[k] for k in ('language', 'renderers', 'selected_rule_ids'))
        loss = sum(4 - r['correct'] for r in rows)
        if unchanged_bias and loss == 1 and witness['observation']['context'] == before['observation']['context']:
            immutable_json(folder / 'selection_certificate.json', {
                'scope_sources': [r['source'] for r in rows], 'native_loss': 1, 'native_loss_lower_bound': 1,
                'selection_edits': 0, 'selection_edit_lower_bound': 0,
                'same_G_renderers_consumer_and_certified_residual_context': True,
                'reused_residual_certificate_sha256': digest(prior_certificate),
                'only_phi_changed_in_this_batch': True, 'not_a_new_G_update_or_semantic_certificate': True,
                'exact_objective_minimum_given_current_phi': True, 'new_model_calls': 0})
        else:
            from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
            from legal_skill_guard.skill_evolution.open_acquisition import fit
            from legal_skill_guard.skill_evolution.theory_supervision import attach_scored_theories
            observations = []
            for row in rows:
                sid = row['source']
                path = folder / 'projected_profiles' / train.previous.old.name_for(sid)
                if path.exists():
                    profile = train.read(path)
                else:
                    profile = admissible_projected_compositions(library, row['observation'],
                        train.previous.old.previous.prior.prior.checker(library, public[sid], grading[sid]), timeout_seconds=90)
                    immutable_json(path, profile)
                assert profile['status'] == 'complete', 'Incomplete search cannot become scored training constraints'
                observations.append(attach_scored_theories(row['observation'], profile))
            library, result = fit(library, observations, prior_rule_ids=old['selected_rule_ids'], timeout_seconds=90)
            immutable_json(folder / 'fit.json', result)
            assert result['status'] == 'sat', 'Keep incomplete fit and candidate; no fitted checkpoint is invented'
            rows = [initial.evaluate(library, t['source_id'], arm, batch,
                folder / 'fitted_results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
    immutable_json(folder / 'library.json', library)
    immutable_json(folder / 'update_result.json', {'arm': arm, 'batch': batch,
        'all_supplied_correct': sum(r['correct'] for r in rows), 'all_supplied_total': len(rows) * 4,
        'current_correct': sum(r['correct'] for r in rows if r['source'] in task['current_sources']),
        'current_total': len(task['current_sources']) * 4, 'unresolved': sum(r['unresolved'] for r in rows),
        'row_summary': [{k: r[k] for k in ('source', 'correct', 'unresolved')} for r in rows],
        'native_accuracy_not_source_semantic_certification': True, 'new_model_calls_during_compile': 0,
        'goal_complete': False})


def run(start, stop):
    protocol = train.prepare()
    for batch in range(start, stop + 1):
        initial.run(batch)
        if not (train.OUT / f'B{batch}/ConstraintAcquire/library.json').exists():
            acquire(protocol, batch)
            for arm in train.ARMS:
                compile_candidate(protocol, batch, arm)
        print(json.dumps({'source_batch_completed': batch}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, choices=range(4, 9), default=4)
    parser.add_argument('--stop', type=int, choices=range(4, 9), default=8)
    args = parser.parse_args()
    with (train.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.start, args.stop)
