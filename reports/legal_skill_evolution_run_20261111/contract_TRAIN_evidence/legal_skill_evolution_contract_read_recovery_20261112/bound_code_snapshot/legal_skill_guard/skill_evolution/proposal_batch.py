"""Prepare unchanged per-arm feedback, then overlap independent teachers only."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
import time

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from .objects import Library, digest
from .clients import FrozenTeacher
from .teacher import propose
from . import patterns
from .lift_proposals import schedule_lift


def load(path):return json.loads(path.read_text())


def prepare_context(study, arm, batch):
    initial = study.initial_batch(arm, batch)
    old = Library.load(study.library_path(arm, batch - 1))
    current = {r['source']: r for r in initial['results']}
    trigger = sorted(current, key=lambda k: (current[k]['selection_grade'] is None,
        current[k]['selection_grade'] if current[k]['selection_grade'] is not None else 0,
        study.order.index(k)))[:3]
    past = [key for keys in study.batches[:batch - 1] for key in keys]
    history = past[:5]
    cohort = trigger + history
    path = study.folder / arm / f'update_context_B{batch}.json'
    if path.exists():
        saved = load(path)
        if saved['old_library_hash'] != old.hash or saved['cohort'] != cohort:
            raise ValueError('Saved teacher/replay context differs from the fixed batch')
        current = saved['current']
    else:
        for key in history:current[key] = study.parent(key, old)
        immutable_json(path, {'old_library_hash': old.hash, 'cohort': cohort, 'current': current})
    generated = patterns.candidates(old, [current[k] for k in trigger], generic=arm == 'Lift+GenericJoint') if (
        arm in ('Full', 'CoRevOnly', 'AllPorts+CoRev', 'Lift+GenericJoint')) else []
    planned_lift = schedule_lift(old, [current[k] for k in trigger], arm)
    queue = generated[:1]
    if planned_lift:
        queue.append({'planned_lift': planned_lift})
    return {'arm': arm, 'batch': batch, 'old': old, 'current': current,
        'trigger': trigger, 'history': history, 'cohort': cohort, 'queue': queue,
        'planned_lift': planned_lift,
        'teacher_path': study.folder / arm / f'teacher_B{batch}.json'}


def propose_context(study, context, teacher=None):
    path = context['teacher_path']
    if path.exists():return load(path)
    cohort, old = context['cohort'], context['old']
    return propose(teacher or study.teacher, arm=context['arm'], batch=context['batch'], library=old,
        source_records=[study.records[k] for k in cohort], feedback=study.feedback(cohort, context['current']),
        learned_patterns=old.revision_patterns, trigger=context['trigger'], history=context['history'],
        max_blocks=3 - len(context['queue']), planned_lift=context['planned_lift'],
        acquisition_contract=study.profile.get('acquisition_contract'))


def prefetch_teachers(study, batch):
    """No executor runs during the bounded parallel teacher interval.

    On an error, drain the at-most-two running calls and leave unsent arms
    untouched. Failed/reserved identities cannot silently dispatch again.
    """
    workers = study.profile['teacher_proposal_workers']
    if workers != 2 or study.ledger.teacher_concurrency != workers:
        raise BudgetError('This continuation authorizes two teacher workers and one executor')
    arms = [arm for arm in study.arms if arm != 'NoSkill']
    expected = study.batches[batch - 1]
    old_hashes = {}
    for arm in study.arms:
        path = study.folder / arm / f'initial_B{batch}.json'
        if not path.exists():raise ValueError('Finish every arm first attempt before teacher dispatch')
        library = Library.load(study.library_path(arm, batch - 1))
        binding = {'batch': batch, 'arm': arm, 'source_ids': expected, 'library_hash': library.hash}
        if load(path)['binding'] != binding:
            raise ValueError('First-attempt batch binding changed before teacher prefetch')
        old_hashes[arm] = library.hash
    complete_path = study.folder / f'teacher_prefetch_B{batch}_completed.json'
    if complete_path.exists():
        saved = load(complete_path)
        if saved['old_library_hashes'] != old_hashes:
            raise ValueError('Completed teacher batch has different batch-start libraries')
        for arm, expected_hash in saved['teacher_response_hashes'].items():
            if digest(load(study.folder / arm / f'teacher_B{batch}.json')) != expected_hash:
                raise ValueError('A completed teacher response changed')
        if set(saved['teacher_response_hashes']) != set(arms):raise ValueError('Incomplete teacher batch receipt')
        return saved
    with study.ledger.transaction() as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise BudgetError('Reconcile actual in-flight requests before starting a teacher batch')
        before = db.execute("select count(*) from calls where role='teacher'").fetchone()[0]
    contexts = {arm: prepare_context(study, arm, batch) for arm in arms}
    jobs = [arm for arm in arms if not contexts[arm]['teacher_path'].exists()]
    started_path = study.folder / f'teacher_prefetch_B{batch}_started.json'
    if not started_path.exists():
        immutable_json(started_path, {'started_unix': time.time(), 'workers': workers,
            'batch': batch, 'old_library_hashes': old_hashes, 'teacher_jobs': jobs,
            'source_cohorts': {arm: contexts[arm]['cohort'] for arm in arms}, 'teacher_count_before': before})
    started = load(started_path)
    if started['old_library_hashes'] != old_hashes or started['workers'] != workers:
        raise ValueError('Interrupted teacher batch has changed inputs or worker policy')

    def one(arm):
        teacher = FrozenTeacher(study.ledger, study.folder, study.profile['teacher'])
        response = propose_context(study, contexts[arm], teacher)
        immutable_json(contexts[arm]['teacher_path'], response)
        return response

    errors, pending, cursor = {}, {}, 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='skill_teacher') as pool:
        while pending or (cursor < len(jobs) and not errors):
            while not errors and cursor < len(jobs) and len(pending) < workers:
                arm = jobs[cursor];cursor += 1
                pending[pool.submit(one, arm)] = arm
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                arm = pending.pop(future)
                try:future.result()
                except Exception as error:errors[arm] = error
    with study.ledger.transaction() as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise BudgetError('Teacher workers ended with an actual reserved request; reconcile before continuing')
        after = db.execute("select count(*) from calls where role='teacher'").fetchone()[0]
    if errors:
        immutable_json(study.folder / f'teacher_prefetch_B{batch}_failed.json', {
            'errors': {a: type(e).__name__ + ': ' + str(e) for a, e in errors.items()},
            'unsent_arms': jobs[cursor:], 'new_physical_teacher_requests': after - before,
            'all_started_workers_drained': True, 'automatic_retries': 0})
        raise next(iter(errors.values()))
    result = {'batch': batch, 'completed_utc': datetime.now(timezone.utc).isoformat(), 'workers': workers,
        'wall_seconds_since_initial_start': time.time() - started['started_unix'],
        'old_library_hashes': old_hashes,
        'teacher_response_hashes': {a: digest(load(contexts[a]['teacher_path'])) for a in arms},
        'new_physical_teacher_requests_this_attempt': after - before,
        'executor_concurrency': 1, 'source_order_and_teacher_payloads_unchanged': True,
        'candidate_validation_still_serial': True, 'automatic_retries': 0}
    immutable_json(complete_path, result)
    return result
