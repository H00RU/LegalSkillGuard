"""Fixed TRAIN program integration of actual source fragments, with a strong control.

This isolates the shared acquisition repair. It does not rerun the already tested
semantic-field Lift or call a text selection an independent method result.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest, apply_revision_package
from legal_skill_guard.skill_evolution.patterns import learn
from legal_skill_guard.skill_evolution.revisions import VersionTable
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime, retrieve
from legal_skill_guard.skill_evolution.study import Study
from legal_skill_guard.skill_evolution.teacher import propose, compile_block
from experiments.legal_skill_evolution_fragment_preflight import FIELDS, QUESTION
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status

RUN = 'legal_skill_evolution_fragment_program_update_20261112'
ARMS = ('Full', 'Lift+GenericJoint')
LOCATOR = 'Complete supplied current source, including operative clauses, attached qualifications and definitions.'


def read(path):return json.loads(path.read_text())


def prepare(root):
    keys = read(root / 'artifacts/legal_skill_evolution_contract_updates_20261112/protocol.json')['previously_fixed_source_order']
    seed_path = root / 'artifacts/legal_skill_evolution_source_rule_check_20261112/FreeEvolution/B2.json'
    seed = Library.load(seed_path)
    if seed.hash != '4fbaea6ae0f9b0cf380af28740cdfd88785e5ae7f0edd5985b2600ef42198c0a':
        raise ValueError('Keep the actual previously learned shared seed')
    public = root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {s['key']: s for s in read(public)}
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    pilot = read(root / 'artifacts/legal_skill_evolution_fragment_preflight_20261112/completed.json')
    contract = {
        'question': 'Can learned legal computation consume located literal clauses instead of the failed synthesized recipient/permission fields, preserving every historical parent?',
        'learning_object': 'The actual existing exception-applicability producer and nondisclosure-consequence consumer, not artificial new helpers. Revise one or both only as the legal dependency requires.',
        'shared_literal_reader': {'question': QUESTION, 'source_locator': LOCATOR, 'fields': FIELDS},
        'reader_use': 'Use this exact measured two-field source-only reader for literal clause/definition acquisition when suitable. Reader fields can be bound to the array premises actually used by the program. The question, locator, field names/questions and representation identify the shared acquisition bundle; the host can reuse an exact prior physical response. Both arms have the identical interface and acquisition evidence. A changed semantic read is still permitted but is separately costed.',
        'actual_source_selections_not_semantic_gold': {k: {'values': v.get('values'), 'event': v.get('event')} for k, v in pilot['outcomes'].items()},
        'calculation': 'The program must compute disclosure permission/applicability and the native consequence from source text. Treat array entries as complete literal clauses/definitions, never as class atoms or booleans. Preserve the direction of prohibitions, exceptions, party roles, purpose and qualifications. The selected text contains irrelevant spans too; neither selection nor co-occurrence establishes a legal permission. Do not ask READ for the final legal label or complete permission decision.',
        'missingness': 'Unresolved text is not an absent rule, False, consent or permission. Do not silently use an old source constant where current legal text differs. Unsupported rules and meanings must remain unresolved.',
        'scope': 'Only the same disclosure tasks nda-5 and nda-7 when justified. Other original native views retain ordinary fallback and stay in the parent denominator. No source-ID/answer lookup, invented legal rule, or hand-written replacement by the experiment runner.',
        'comparison': 'One independent teacher proposal per arm from the identical actually learned Free B2 seed, same public source/feedback, common source-fragment interface and unchanged native/history admission. This is a shared-seed acquisition/update diagnostic, not independent seed acquisition or proof of Lift/CoRev.',
        'prior_negative_evidence': 'The prior original semantic-field Lift and nested-record alternatives are retained; do not regenerate their unchanged candidates. This diagnostic only tests the materially changed text-consuming program route. Do not force joint necessity, split a record into fake skills or claim interface breakage as legal co-revision.',
        'admission': 'Complete compatible old/new table, strict trigger-parent improvement and every historical parent nondecreasing. Report single-sufficient or strong-control absorption. Frozen fourth TRAIN parent is reused without another teacher or subsequent tuning.'}
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py'))
    paths += [Path(__file__).resolve(), root / 'experiments/legal_skill_evolution_fragment_preflight.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'arms': list(ARMS),
        'already_fixed_original_TRAIN_parents': keys, 'trigger': keys[2], 'history': keys[:2],
        'frozen_TRAIN_reuse': keys[3], 'shared_seed': str(seed_path.relative_to(root)), 'shared_seed_hash': seed.hash,
        'acquisition_contract': contract, 'workload': 'Exactly one independently generated free block per arm, at most three existing-skill edits; complete 2^k table on the same three TRAIN parents, then the fourth fixed TRAIN reuse. No unchanged failed Lift replay, follow-up proposal, new source, DEV/TEST or full matrix.',
        'interpretation': 'Common acquisition repair is not an independent contribution. Native gain, core execution, fallback, accepted edits, table necessity, actual learned patterns and control absorption are reported separately.',
        'offline_regressions_passed': 116, 'automatic_retries': 0,
        'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    folder = root / 'artifacts' / RUN
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, profile, seed, {k: records[k] for k in keys}


def evaluate(study, arm, seed, response, cohort):
    path = study.folder / arm / 'program_update.json'
    if path.exists():return read(path)
    value = {'arm': arm, 'old_library_hash': seed.hash, 'accepted': False,
             'scheduled_semantic_Lift_not_repeated': True}
    final = deepcopy(seed)
    try:
        blocks = response['value']['blocks']
        if len(blocks) > 1:raise ValueError('The fixed diagnostic allows one block per arm')
        if not blocks:
            value['no_proposal'] = True
        else:
            revisions = compile_block(blocks[0], seed, {k: study.records[k] for k in cohort}, arm)
            if any(r['operation'] == 'create' for r in revisions):
                raise ValueError('This diagnostic updates existing legal responsibilities; no new graph')
            full = apply_revision_package(seed, revisions, seed.hash)
            retrieval = {k: {v['id']: list(dict.fromkeys(retrieve(full, study.records[k], v) +
                retrieve(seed, study.records[k], v))) for v in study.records[k]['views']} for k in cohort}
            table = VersionTable(tuple(r['new_hash'] for r in revisions), (cohort[0],), tuple(cohort[1:]))
            tokens = {}
            for mask in range(1 << len(revisions)):
                library = apply_revision_package(seed, [r for i, r in enumerate(revisions) if mask & (1 << i)], seed.hash)
                tokens[mask] = 0
                for key in cohort:
                    status(study.folder, phase='literal_program_version_table', arm=arm, mask=mask, source=key)
                    result = study.parent(key, library, retrieval_sets=retrieval[key])
                    table.observe(mask, key, result['selection_grade'], result)
                    tokens[mask] += sum(e.get('usage', {}).get('total_tokens', 0)
                        for v in result['views'] for e in v['execution'].get('events', []) if e.get('kind') == 'READ_LOCAL')
            chosen = table.choose({m: n - tokens[0] for m, n in tokens.items()})
            if chosen is not None:
                final = apply_revision_package(seed, [r for i, r in enumerate(revisions) if chosen & (1 << i)], seed.hash)
                learned = learn(final, seed, revisions, table, chosen, generic=arm == 'Lift+GenericJoint',
                    source_records={k: study.records[k] for k in cohort})
                value.update(accepted=True, learned_pattern_ids=learned)
            value.update(revisions=revisions, table=table.export(), selected_mask=chosen, read_tokens=tokens)
    except Exception as error:
        from legal_skill_guard.rr.ledger import BudgetError
        from legal_skill_guard.skill_evolution.clients import GenerationHold
        if isinstance(error, (BudgetError, GenerationHold)):raise
        with study.ledger.transaction() as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():raise
        value['error'] = type(error).__name__ + ': ' + str(error)
    final.save(study.folder / arm / 'B3.json')
    value.update(new_library_hash=final.hash, skill_count=len(final.skills), pattern_count=len(final.revision_patterns))
    immutable_json(path, value)
    return value


def run(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    folder, protocol, profile, seed, records = prepare(root)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name, sha in protocol['code_sha256'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed: ' + name)
        ledger_path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before = physical_snapshot(ledger_path)
        if any(v.get('reserved', 0) for v in before.values()):raise ValueError('Reconcile pending calls first')
        if not (folder / 'ledger_before.json').exists():immutable_json(folder / 'ledger_before.json', before)
        keys = protocol['already_fixed_original_TRAIN_parents']
        study = object.__new__(Study)
        study.root, study.folder, study.stage, study.profile = root, folder, 'fragment_program_update', profile
        study.records = records
        grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        study.grading = {k: grading[k] for k in records}
        study.source_ids = {'train': keys, 'dev': [], 'test': []}
        study.batches, study.order, study.arms = [[k] for k in keys[:3]], keys[:3], ARMS
        study.ledger = EvolutionLedger(ledger_path, run_id=RUN, sources=study.source_ids,
            binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        prior_folders = sorted((root / 'artifacts').glob('legal_skill_evolution*_20261112'))
        study.executor.exact_replay_roots = [p for p in prior_folders if p != folder]
        study.executor.exact_replay_roots += [root / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            prior = read(root / rel)
            if digest(prior['executor']) != digest(profile['executor']):raise ValueError('Frozen executor changed')
            study.executor.exact_replay_roots.append(root / prior['artifacts'])
        # The preserved recovery run contains per-job call folders.
        study.executor.exact_replay_roots += list((root / 'artifacts/legal_skill_evolution_contract_read_recovery_20261112').glob('*_B*'))
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        cohort = [protocol['trigger']] + protocol['history']
        current = {k: study.parent(k, seed) for k in cohort}
        immutable_json(folder / 'before_results.json', current)
        for arm in ARMS:
            p = study.library_path(arm, 2)
            if not p.exists():deepcopy(seed).save(p)
        def one(arm):
            p = folder / arm / 'teacher_B3.json'
            if p.exists():return read(p)
            response = propose(FrozenTeacher(study.ledger, folder, profile['teacher']), arm=arm, batch=3,
                library=seed, source_records=[records[k] for k in cohort],
                feedback=study.feedback(cohort, current), learned_patterns=seed.revision_patterns,
                trigger=cohort[:1], history=cohort[1:], max_blocks=1, planned_lift=None,
                acquisition_contract=protocol['acquisition_contract'])
            immutable_json(p, response);return response
        status(folder, phase='two_fixed_literal_program_proposals')
        responses, errors = {}, []
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {a: pool.submit(one, a) for a in ARMS}
            for arm, job in jobs.items():
                try:responses[arm] = job.result()
                except Exception as error:errors.append(error)
        if errors:raise errors[0]
        updates = {a: evaluate(study, a, seed, responses[a], cohort) for a in ARMS}
        reuse = {a: study.parent(protocol['frozen_TRAIN_reuse'], Library.load(folder / a / 'B3.json')) for a in ARMS}
        result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'protocol_hash': digest(protocol), 'before': current, 'updates': updates, 'frozen_TRAIN_reuse': reuse,
            'ledger_before': read(folder / 'ledger_before.json'), 'ledger_after': physical_snapshot(ledger_path),
            'semantic_and_independent_mechanism_review_pending': True}
        immutable_json(folder / 'completed.json', result)
        status(folder, phase='terminal_review_pending', ledger=result['ledger_after'])
        return result


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('action', choices=['prepare', 'run']);a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if a.action == 'prepare':
        folder, protocol, _, _, _ = prepare(root)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'hash': digest(protocol), 'teacher_tasks': 2}))
    else:
        result = run(root);print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
