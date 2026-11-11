"""Single entry for the frozen-model external-skill study; no parameter training."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest, Library
from legal_skill_guard.skill_evolution.clients import GenerationHold
from legal_skill_guard.skill_evolution.native import public_task, answer_wire_schema, DIRECT_SYSTEM
from legal_skill_guard.skill_evolution.study import Study, load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.runtime import render_messages

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/legal_skill_evolution_pilot_v7_20261111.json'


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    if sys.version_info < (3, 11):
        raise RuntimeError('Use the already-pinned Python 3.11 inference environment')
    original = load_json(ROOT / 'configs/rr_v2_preflight.json')
    executor = original['executor']
    teacher = original['teacher']
    teacher['executable'] = '/home/yndx/.local/share/codex-npm/bin/codex'
    expected_teacher = 'e14fc83739c13c1074b12bd1acce4010c893c7f6fbfc1593b4a31d74cabb57af'
    if file_hash(teacher['executable']) != expected_teacher:
        raise RuntimeError('Authorized frozen teacher executable has changed')
    scientific = list((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')) + [
        ROOT / 'experiments/legal_skill_evolution.py', ROOT / 'legal_skill_guard/rr/client.py',
        ROOT / 'legal_skill_guard/rr/ledger.py', ROOT / 'legal_skill_guard/rr/scoring.py',
        ROOT / 'legal_skill_guard/openexempt.py', ROOT / 'legal_skill_guard/inference/codex_cli_client.py',
        ROOT / 'tests/test_legal_skill_evolution.py', ROOT / 'tests/test_skill_evolution_runtime.py']
    code = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(scientific)}
    data_paths = ['artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
                  'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json']
    data = {p: file_hash(ROOT / p) for p in data_paths}
    for name in ('candidate_source_manifest.json', 'pilot_source_manifest.json', 'CONTROLLED_LAYER_EVIDENCE.json'):
        path = 'reports/legal_skill_evolution_plan_20261111/' + name
        data[path] = file_hash(ROOT / path)
    for path in (ROOT / 'data/cache/openexempt/servantez-OpenExempt-ec6fa25').rglob('*.py'):
        data[path.relative_to(ROOT).as_posix()] = file_hash(path)
    profile = {'protocol': 'LSG-LegalSkill-20261111', 'run_id': 'legal_skill_evolution_pilot_v7_20261111',
        'artifacts': 'artifacts/legal_skill_evolution_20261111/pilot_v7', 'executor': executor,
        'teacher': teacher, 'teacher_binary_sha256': expected_teacher,
        'generation_binding': {'code_hash': digest(code), 'data_hash': digest(data),
            'executor_hash': digest(executor), 'teacher_hash': digest(teacher)},
        'selection_grade': 'all_predeclared_native_and_controlled_TRAIN_views_mean_within_parent',
        'primary_native_scores': 'native_only_kept_separate', 'pilot_arms': PILOT_ARMS,
        'new_sources_or_seeds': False, 'model_parameter_updates': False,
        'exact_replay_profiles': ['configs/legal_skill_evolution_pilot_v4_20261111.json'],
        'prior_logical_replay_executions': {'Full:1': 60},
        'first_attempt_prefix_recovery': 'Only original complete native answer fields; protocol versions and raw costs retained; no labels used in recovery'}
    immutable_json(PROFILE, profile)
    folder = ROOT / profile['artifacts']
    immutable_json(folder / 'execution_manifest.json', {'code': code, 'data': data,
        'profile_sha256': file_hash(PROFILE), 'base_model_verification':
        load_json(ROOT / 'artifacts/legal_skill_evolution_20261111/base_model_verified.json')})
    for relative in code:
        target = folder / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != (ROOT / relative).read_bytes():
            raise ValueError('Existing frozen source snapshot differs')
        shutil.copyfile(ROOT / relative, target)
    print(json.dumps({'prepared_profile': str(PROFILE), 'code_files_bound': len(code), 'new_model_calls': 0}), flush=True)


def verify_manifest(profile):
    manifest = load_json(ROOT / profile['artifacts'] / 'execution_manifest.json')
    if file_hash(PROFILE) != manifest['profile_sha256']:
        raise ValueError('Frozen generation profile changed')
    for relative, expected in manifest['code'].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError('Scientific source changed after binding: ' + relative)
    for relative, expected in manifest['data'].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError('Frozen native data/grader dependency changed: ' + relative)


def preflight(study):
    card = study.executor.readiness()
    teacher = study.teacher.adapter.preflight()
    if not teacher['ready']:
        raise RuntimeError('Existing frozen teacher authentication is not ready')
    tokenization = []
    for key in study.order:
        source = study.records[key]
        for view in source['views']:
            messages = render_messages(DIRECT_SYSTEM, public_task(source, view),
                                       answer_wire_schema(source['dataset'], view))
            count = study.executor.tokenize(messages, thinking=False)
            if count['count'] + study.profile['executor']['max_tokens'] > study.profile['executor']['context_tokens']:
                raise ValueError('Complete pilot input exceeds the frozen context, no truncation')
            tokenization.append({'source': key, 'view': view['id'], 'input_tokens': count['count'],
                'template_suffix_tokens': count['tokens'][-24:], 'answer_schema_hash': digest(answer_wire_schema(source['dataset'], view))})
    result = {'model_card': card, 'teacher_preflight': teacher, 'pilot_views': len(tokenization),
        'tokenization': tokenization, 'new_model_generation_requests': 0, 'thinking': False,
        'captured_utc': datetime.now(timezone.utc).isoformat()}
    path = study.folder / 'preflight.json'
    if not path.exists():immutable_json(path, result)
    print(json.dumps({'preflight': 'passed', 'views': len(tokenization),
        'largest_input_tokens': max(r['input_tokens'] for r in tokenization), 'new_model_calls': 0}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'preflight', 'source', 'initial', 'update', 'pilot'])
    parser.add_argument('--source-index', type=int, choices=range(1, 21), default=1)
    parser.add_argument('--batch', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--arm', choices=PILOT_ARMS, default='Full')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare();return
    profile = load_json(PROFILE)
    verify_manifest(profile)
    study = Study(ROOT, profile)
    if args.action == 'preflight':
        preflight(study);return
    if not (study.folder / 'preflight.json').exists():
        raise ValueError('Offline/native input and live read-only preflight must finish before generation')
    study.initialize()
    if args.action == 'source':
        result = study.parent(study.order[args.source_index - 1], Library.load(study.library_path(args.arm, 0)))
        print(json.dumps(result, ensure_ascii=False), flush=True)
    elif args.action == 'initial':study.initial_batch(args.arm, args.batch)
    elif args.action == 'update':study.update(args.arm, args.batch)
    else:study.run()


if __name__ == '__main__':
    try:
        main()
    except GenerationHold as error:
        print(json.dumps({'state': 'held_at_request_boundary', 'reason': str(error)}), flush=True)
        sys.exit(75)
