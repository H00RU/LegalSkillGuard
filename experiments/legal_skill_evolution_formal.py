"""The authorized fixed 128-parent external-skill study, through B8 DEV only.

TEST is a separate frozen continuation; this entry never opens sealed_test.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.study import Study, load_json
from legal_skill_guard.skill_evolution.clients import GenerationHold
from legal_skill_guard.skill_evolution.native import public_task, answer_wire_schema, DIRECT_SYSTEM
from legal_skill_guard.skill_evolution.runtime import render_messages

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/legal_skill_evolution_formal_v4_20261111.json'
ARMS = ('NoSkill', 'FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')
CURVE_ARMS = ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def schedule():
    actions = [('dev', arm, 0) for arm in ARMS]
    for batch in range(1, 9):
        actions += [('initial', arm, batch) for arm in ARMS]
        actions += [('update', arm, batch) for arm in ARMS]
        actions += [('dev', arm, batch) for arm in CURVE_ARMS]
        if batch == 8:actions += [('dev', arm, batch) for arm in ARMS if arm not in CURVE_ARMS]
    return actions


def prepare():
    goal = load_json(ROOT / 'configs/legal_skill_evolution_20261111.json')
    if goal['latest_user_overrides']['stage_one_only_stop'] is not False:
        raise ValueError('The current full-study authorization supersedes the old stage-one stop')
    review_path = ROOT / 'reports/legal_skill_evolution_run_20261111/formal_native_enum_review.json'
    review = load_json(review_path)
    if not review['old_client_terminal'] or review['inflight_before_promotion'] != 0:
        raise ValueError('Settle the existing client before promoting this common runtime check')
    if not review['offline_actual_TRAIN_final_answers_and_paths_preserved']:
        raise ValueError('A native type-check optimization needs actual offline evidence')
    previous = 'configs/legal_skill_evolution_formal_v3_20261111.json'
    prior = load_json(ROOT / previous)
    original = load_json(ROOT / prior['artifacts'] / 'execution_manifest.json')
    code = {p: sha(ROOT / p) for p in original['code']}
    for relative in ('legal_skill_guard/skill_evolution/answer_domain.py',
                     'tests/test_skill_evolution_answer_domain.py', 'legal_skill_guard/skill_evolution/teacher_transport.py',
                     'tests/test_skill_evolution_teacher_transport.py'):
        code[relative] = sha(ROOT / relative)
    data = {p: sha(ROOT / p) for p in original['data']}
    for path in (review_path, ROOT / 'reports/legal_skill_evolution_run_20261111/actual_TRAIN_enum_skip_regression.json'):
        data[str(path.relative_to(ROOT))] = sha(path)
    profile = {**prior, 'run_id': 'legal_skill_evolution_formal_v4_20261111',
        'artifacts': 'artifacts/legal_skill_evolution_20261111/formal_v4',
        'continuation_of': previous, 'same_training_pass': True,
        'preserved_completed_batch_prefix': review['preserved_completed_batch_prefix'],
        'teacher_input_transport': 'Lossless shared JSON values with exact round-trip evidence; no removed fields, source text or prior outcomes.',
        'forward_repair': 'Prove literal terminal answers disjoint from the existing native enum before unnecessary reads; unknown programs and dependency producers retain normal execution.'}
    profile['exact_replay_profiles'] = prior['exact_replay_profiles'] + [previous]
    profile['generation_binding'] = {'code_hash': digest(code), 'data_hash': digest(data),
        'executor_hash': digest(profile['executor']), 'teacher_hash': digest(profile['teacher'])}
    immutable_json(PROFILE, profile)
    folder = ROOT / profile['artifacts']
    immutable_json(folder / 'execution_manifest.json', {'code': code, 'data': data, 'profile_sha256': sha(PROFILE)})
    for relative in code:
        target = folder / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != sha(ROOT / relative):raise ValueError('Formal snapshot differs')
        shutil.copyfile(ROOT / relative, target)
    print(json.dumps({'prepared': str(PROFILE.relative_to(ROOT)), 'systems': len(ARMS),
        'training_sources': 128, 'batches': 8, 'pilot_skills_imported': False, 'new_model_calls': 0}), flush=True)


def verified_study():
    profile = load_json(PROFILE)
    manifest = load_json(ROOT / profile['artifacts'] / 'execution_manifest.json')
    if sha(PROFILE) != manifest['profile_sha256']:raise ValueError('Frozen formal profile changed')
    for p, expected in {**manifest['code'], **manifest['data']}.items():
        if sha(ROOT / p) != expected:raise ValueError('Frozen formal dependency changed: ' + p)
    return Study(ROOT, profile, stage='formal')


def preflight(study):
    card = study.executor.readiness()
    if not study.teacher.adapter.preflight()['ready']:raise ValueError('Frozen teacher is unavailable')
    tokenization = []
    for records in (study.records, study.dev_records):
        for source in records.values():
            for view in source['views']:
                messages = render_messages(DIRECT_SYSTEM, public_task(source, view), answer_wire_schema(source['dataset'], view))
                count = study.executor.tokenize(messages, thinking=False)['count']
                if count + study.profile['executor']['max_tokens'] > study.profile['executor']['context_tokens']:
                    raise ValueError('Complete formal input does not fit; no truncation')
                tokenization.append({'source': source['key'], 'view': view['id'], 'input_tokens': count})
    immutable_json(study.folder / 'preflight.json', {'card': card, 'tokenization': tokenization,
        'new_model_generation_requests': 0, 'thinking': False, 'TEST_opened': False})
    print(json.dumps({'preflight': 'passed', 'native_TRAIN_DEV_views': len(tokenization),
        'max_input_tokens': max(r['input_tokens'] for r in tokenization), 'new_model_calls': 0}), flush=True)


def evaluate_dev(study, arm, batch):
    library = Library.load(study.library_path(arm, batch))
    path = study.folder / 'dev' / arm / f'B{batch}.json'
    if path.exists():
        saved = load_json(path)
        if saved['library_hash'] != library.hash:raise ValueError('DEV checkpoint library changed')
        return saved
    results = []
    for key in study.source_ids['dev']:
        results.append(study.parent(key, library, purpose='skill_dev'))
    by_dataset = {}
    for row in results:by_dataset.setdefault(row['dataset'], []).append(row['native_grade'])
    means = {k: sum(values) / len(values) if all(v is not None for v in values) else None
             for k, values in by_dataset.items()}
    result = {'arm': arm, 'batch': batch, 'library_hash': library.hash, 'results': results,
        'native_parent_means_by_dataset': means,
        'equal_dataset_macro': sum(means.values()) / 5 if all(v is not None for v in means.values()) else None,
        'teacher_feedback': False, 'skill_updates': False, 'frozen_B8_not_best_DEV': True}
    immutable_json(path, result)
    print(json.dumps({'stage': 'formal_DEV', 'arm': arm, 'batch': batch,
        'equal_dataset_macro': result['equal_dataset_macro'], 'teacher_feedback': False}), flush=True)
    return result


def run(study):
    if not (study.folder / 'preflight.json').exists():raise ValueError('Run the read-only full input preflight first')
    study.initialize()
    for action, arm, batch in schedule():
        if (action == 'update' and arm == 'NoSkill' and batch >= study.profile.get('teacher_prefetch_from_batch', 9)):
            from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers
            prefetch_teachers(study, batch)
        if action == 'dev':evaluate_dev(study, arm, batch)
        elif action == 'initial':study.initial_batch(arm, batch)
        elif arm == 'NoSkill':
            # An empty reference library has no teacher or update proposal.
            library = Library.load(study.library_path(arm, batch - 1))
            if library.skills or library.revision_patterns:raise ValueError('NoSkill library is not empty')
            library.save(study.library_path(arm, batch))
        else:study.update(arm, batch)
    immutable_json(study.folder / 'training_DEV_completed.json', {
        'completed_utc': datetime.now(timezone.utc).isoformat(), 'training_sources': 128, 'batches': 8,
        'B8_library_hashes': {arm: Library.load(study.library_path(arm, 8)).hash for arm in ARMS},
        'goal_complete': False, 'TEST_started': False, 'next': 'B8 review, exposure-qualified freeze and fixed TEST continuation'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'preflight', 'run'])
    args = parser.parse_args()
    try:
        if args.action == 'prepare':prepare()
        else:
            study = verified_study()
            preflight(study) if args.action == 'preflight' else run(study)
    except GenerationHold as error:
        print(json.dumps({'state': 'held_at_request_boundary', 'goal_status': 'active', 'reason': str(error)}), flush=True)
        raise SystemExit(75)
