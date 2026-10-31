"""One exact finite handoff: unchanged45 stages, then six matched future builds.

No TEST, score-selected experiment, failed-stage retry or alternative solver.
The old finite plan supplies its original stage and terminal/source contracts.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

ROOT = Path('/media/sangfor/vdb/legal-skill-evolve')
sys.path.insert(0, str(ROOT))
from experiments.openexempt_online import actor_payload, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha

OLD = ROOT / 'artifacts/launches/openexempt_text45_to_remaining8_20261023.py'
OLD_SHA = 'b3c1f8650dbe2a3061ce0f7ee9c19dd1c287448831bd33dd908078e2783ebc07'
spec = importlib.util.spec_from_file_location('original_exact_remaining8_plan', OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
OUT = ROOT / 'artifacts/launches/openexempt_text45_legacy_ablations_then_phase_repeats_20261024_run02'
RETIREMENT = OUT.parent / 'remaining8_original_waiter_retired_for_finite_phase_handoff_20261023.json'
PROTOCOL = 'docs/research/OPENEXEMPT_PHASE_DISPATCH_HANDOFF_20261023.md'
ENVIRONMENT = 'artifacts/live_8b_environment_phase_dispatch_20261023.json'
OLD_ENV = 'artifacts/live_8b_environment_EOS_aligned_20261020.json'
UNIT = 'legal-qwen3-8b-phase-dispatch.service'
NEW_UNIT = ROOT / 'ops' / UNIT
GIT = '/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/bin/git'
GIT_ENV = {**os.environ, 'GIT_EXEC_PATH': '/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/lib/git-core'}
COMMITS = ('0a73ed2496979d22ecb034329fbc14261956a9dc', '8337a1d6ca20f4a3df7b6670dc7f1c02a8545104')
RUN = 'legal_openexempt_finite_phase_handoff_20261024_run02'


def command(args, **kwargs):
    result = subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True, **kwargs)
    if result.returncode:
        if OUT.is_dir():
            RunStore.immutable_json(OUT / 'subprocess_failures' / (str(time.time_ns()) + '.json'), {
                'at': now(), 'argv': args, 'returncode': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr,
                'no_retry_or_discarded_failure': True})
        result.check_returncode()
    return result


def save(name, value):
    RunStore.immutable_json(OUT / (name + '.json'), {'at': now(), **value})


def archive(archive_label):
    names = [str(p.relative_to(ROOT)) for p in OUT.rglob('*') if p.is_file() and p.name != 'progress.json']
    names += [str(Path(__file__).relative_to(ROOT)), PROTOCOL, str(NEW_UNIT.relative_to(ROOT)),
              'ops/legal-qwen3-8b.service', OLD_ENV, str(OLD.relative_to(ROOT)),
              str(old.FIRST.relative_to(ROOT)), str(old.FIRST.with_suffix('.frozen.json').relative_to(ROOT))]
    for stage in old.STAGES:
        path = ROOT / stage['path']
        names += [str(path.relative_to(ROOT)), str(path.with_suffix('.frozen.json').relative_to(ROOT))]
        if stage in old.STAGES[2:]:
            future = ROOT / stage['path'].replace('20261023_run02', '20261023_run03')
            names += [str(p.relative_to(ROOT)) for p in (future, future.with_suffix('.frozen.json')) if p.is_file()]
    versions = ROOT / 'artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023'
    names += [str(p.relative_to(ROOT)) for p in versions.glob('*.py')]
    receipt = preserve(RUN, archive_label, names)
    if len({Path(v['path']).stat().st_dev for v in receipt['paths']}) != 2:
        raise RuntimeError('Two independent preservation devices required')
    save(archive_label + '_preservation', receipt)


def check_own_sources(queued):
    for name, digest in queued['controller_sources'].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError('Frozen finite handoff source changed: ' + name)


def plan():
    if sha(OLD) != OLD_SHA or old.ticks(old.TEXT_PID) != old.TEXT_START or old.ticks(old.MODEL_PID) != old.MODEL_START:
        raise RuntimeError('Prepare against the exact live original Text and model')
    packages = {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}
    for stage in old.STAGES:
        old.unchanged(stage, OLD_SHA, packages)
    ledger = ROOT / read(old.FIRST)['teacher']['ledger']
    if read(ledger)['max_invocations'] != 3991:
        raise RuntimeError('Text45 must retain the actual3991 ceiling')
    return {'controller_sources': {str(p.relative_to(ROOT)): sha(p) for p in (
                Path(__file__), OLD, ROOT / PROTOCOL, NEW_UNIT)},
            'original_model': [old.MODEL_PID, old.MODEL_START],
            'Text45': [old.TEXT_PID, old.TEXT_START], 'stages': old.STAGES,
            'packages': packages, 'source_promotion': list(COMMITS),
            'current_ceiling_unchanged': 3991, 'final_ceiling_unchanged': 8507}


def extend(ledger, baseline, previous_ceiling, stage, predecessor, queued):
    check_own_sources(queued)
    prior = old.terminal(predecessor)
    with ledger.with_suffix(ledger.suffix + '.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = read(ledger)
        stable = lambda value: {k: v for k, v in value.items() if k not in ('max_invocations', 'reservations')}
        reserved = before.get('historical_count_lower_bound', 0) + len(before['reservations'])
        if (before['max_invocations'] != previous_ceiling or stable(before) != stable(baseline)
                or before['reservations'][:len(baseline['reservations'])] != baseline['reservations']
                or stage['ceiling'] != previous_ceiling + stage['attempts']
                or reserved + stage['attempts'] > stage['ceiling']):
            raise RuntimeError('No quota reset or changed declared stage ceiling')
        save(stage['run_id'] + '_before_extension', {'predecessor': prior, 'ledger': before, 'next': stage})
        archive(stage['run_id'] + '_before_extension')
        RunStore.atomic_json(ledger, {**before, 'max_invocations': stage['ceiling']})


def new_profile(source, stage, environment, run_map):
    result = copy.deepcopy(source)
    result.update(run_id=run_map[source['run_id']], inference_environment=environment,
        phase_dispatch={'policy': 'ordered_independent_phases_v1', 'native_workers': 4,
                        'teacher_workers': 2, 'required_max_num_seqs': 4},
        execution_order_addendum=PROTOCOL,
        prospective_source_rebase_from_unstarted_profile=stage['path'],
        source_rebase_reason='Prospective matched145/245 independent-phase scheduling after all unchanged45 stages; same scientific protocol, per-answer budget, data, teacher, caps and cumulative quota.',
        previous_frozen_profile_retained_not_overwritten=True)
    if 'required_completed_predecessors' in result:
        result['required_completed_predecessors'] = [run_map.get(v, v) for v in result['required_completed_predecessors']]
    if 'current_live_ledger_ceiling_not_changed' in result:
        result['current_live_ledger_ceiling_not_changed'] = 4055
    if 'future_ceiling_basis' in result:
        result['future_ceiling_basis'] = 'Exact serial stage extensions4055 through8507, retaining all prior reservations; declared dispatch inside each learner only.'
    if 'prospective_only_not_started_not_frozen_not_queued' in result:
        result['prospective_only_not_started_not_frozen_not_queued'] = False
    operational = {'run_id', 'inference_environment', 'phase_dispatch', 'execution_order_addendum',
        'prospective_source_rebase_from_unstarted_profile', 'source_rebase_reason',
        'previous_frozen_profile_retained_not_overwritten', 'required_completed_predecessors',
        'current_live_ledger_ceiling_not_changed', 'future_ceiling_basis',
        'prospective_only_not_started_not_frozen_not_queued'}
    if ({k: v for k, v in source.items() if k not in operational}
            != {k: v for k, v in result.items() if k not in operational}):
        raise RuntimeError('Operational rebase changed a scientific condition')
    return result


def verify_recovery():
    reference = read(ROOT / 'artifacts/research/openexempt_legal_scope_20261020/original_8b_and_existing_rootdisk_recovery_all13_official_manifest_SHA_verified_NO_transition_20261023.json')
    checks = []
    for device in reference['devices']:
        directory = Path(device['directory'])
        if directory.stat().st_dev != device['device']:
            raise RuntimeError('Recovery device changed')
        for item in device['verified']:
            path = directory / item['file']
            if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
                raise RuntimeError('Original deployment/recovery asset changed: ' + str(path))
        checks.append({'directory': str(directory), 'device': device['device'], 'verified_files': 13})
    dependencies = read(ROOT / OLD_ENV)['inference_dependency_source_sha256']
    for name, digest in dependencies.items():
        if sha(name) != digest:
            raise RuntimeError('Original inference dependency changed: ' + name)
    recovery = []
    for base in (Path('/media/sangfor/vdb/legal-skill-backups'), Path('/home/yndx/hhy/legal-skill-rootdisk-backups')):
        path = base / (RUN + '-original_runtime_dependency_sources.tar.gz')
        members = {str(Path(name).relative_to('/media/sangfor/vdb/legal-skill-runtime')): digest
                   for name, digest in dependencies.items()}
        with tarfile.open(path, 'x:gz') as archive:
            for name in dependencies:
                archive.add(name, arcname=str(Path(name).relative_to('/media/sangfor/vdb/legal-skill-runtime')), recursive=False)
        with tarfile.open(path, 'r:gz') as archive:
            found = {member.name: hashlib.sha256(archive.extractfile(member).read()).hexdigest() for member in archive}
        if found != members:
            raise RuntimeError('Recovery runtime source archive differs from actual dependency bytes')
        recovery.append({'path': str(path), 'sha256': sha(path), 'device': path.stat().st_dev, 'members': found})
    save('original_runtime_dependency_sources_preserved', {'archives': recovery})
    save('original_deployment_recovery_reverified', {'devices': checks, 'no_download_or_model_call': True})


def capture_service(queued):
    check_own_sources(queued)
    expected = read(ROOT / OLD_ENV)
    if old.ticks(old.MODEL_PID) != old.MODEL_START:
        raise RuntimeError('Original model ended before the approved boundary')
    command(['systemctl', '--user', 'stop', 'legal-qwen3-8b.service'])
    if (old.ticks(old.MODEL_PID) == old.MODEL_START
            or command(['systemctl', '--user', 'show', 'legal-qwen3-8b.service', '-p', 'ActiveState', '--value']).stdout.strip() != 'inactive'):
        raise RuntimeError('Never start a second instance alongside the original model')
    command(['systemctl', '--user', 'link', str(NEW_UNIT)])
    command(['systemctl', '--user', 'daemon-reload'])
    command(['systemctl', '--user', 'start', UNIT])
    generation = read(old.FIRST)['generation']
    deadline = time.monotonic() + 900
    while True:
        pid = int(command(['systemctl', '--user', 'show', UNIT, '-p', 'MainPID', '--value']).stdout.strip())
        status = command(['systemctl', '--user', 'show', UNIT, '-p', 'ActiveState', '--value']).stdout.strip()
        if status not in ('active', 'activating') or not pid:
            raise RuntimeError('The declared single replacement service failed; no automatic fallback')
        readiness = WireClient(generation).readiness()
        if readiness['ready']:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError('Declared replacement did not become ready within900s')
        print('Waiting for the one declared replacement service readiness', flush=True)
        time.sleep(15)
    proc = Path('/proc') / str(pid)
    argv = [v.decode() for v in (proc / 'cmdline').read_bytes().split(b'\0') if v]
    changed = list(expected['actual_argv'])
    changed[changed.index('--max-num-seqs') + 1] = '4'
    if argv != changed:
        raise RuntimeError('Serving argv changed beyond the declared sequence limit')
    capture = {'at': now(), 'pid': pid, 'process_start_ticks': old.ticks(pid), 'actual_argv': argv,
        'service_unit': UNIT, 'model_root': expected['model_root'],
        'model_official_revision': expected['model_official_revision'],
        'same_previously_verified_model_path_revision_no_download_no_weight_update': True,
        'inference_dependency_source_sha256': expected['inference_dependency_source_sha256'],
        'generation_EOS_and_grammar_EOS_aligned': expected['generation_EOS_and_grammar_EOS_aligned'],
        'dependency_patch': expected['dependency_patch'], 'readiness': readiness,
        'actual_GPU_snapshot': command(['nvidia-smi', '--query-gpu=name,uuid,memory.used,memory.total', '--format=csv,noheader']).stdout.strip(),
        'original_environment_sha256': sha(ROOT / OLD_ENV),
        'only_serving_change': '--max-num-seqs1to4', 'no_second_simultaneous_instance': True}
    RunStore.immutable_json(ROOT / ENVIRONMENT, capture)
    save('actual_new_environment', capture)
    return capture


def timing_only(capture):
    cfg = read(old.FIRST)
    cfg['inference_environment'] = ENVIRONMENT
    rows = [r for r in read(ROOT / cfg['input_packet'])['rows'] if r['case_id'] in (181, 182)]
    if len(rows) != 4 or {(r['case_id'], r['family']) for r in rows} != {(i, f) for i in (181, 182) for f in ('EC', 'EV')}:
        raise RuntimeError('Only the four prespecified public TRAIN tasks are permitted')
    def check():
        if old.ticks(capture['pid']) != capture['process_start_ticks']:
            raise RuntimeError('New service handle changed; no timing retry')
    lock, native = threading.Lock(), []
    def progress(*args, **kwargs):
        with lock:
            RunStore.atomic_json(OUT / 'progress.json', {'at': now(), 'state': 'eight_unscored_transport_timings', **kwargs})
    owner = SimpleNamespace(cfg=cfg, check=check, progress=progress, native=native)
    report = []
    for workers in (1, 4):
        started = time.monotonic()
        def infer(row):
            messages, schema, *_ = actor_payload(row, [], direct_numeric=True, asset_references=True)
            name = f'timing{workers}_{row["case_id"]}_{row["family"]}'
            RunStore.immutable_json(OUT / 'timing' / (name + '.input.json'), {'messages': messages, 'schema': schema, 'generation': cfg['generation']})
            return Comparison.call(owner, OUT / 'timing' / (name + '.raw.json'), messages, schema,
                cfg['generation']['max_tokens'], {'stage': 'unscored_timing', 'arm': name,
                    'document_id': row['case_id'], 'family': row['family'], 'call_role': 'openexempt'})
        if workers == 1:
            answers = [infer(row) for row in rows]
        else:
            with ThreadPoolExecutor(max_workers=4) as pool:
                answers = list(pool.map(infer, rows))
        report.append({'workers': workers, 'actual_calls': 4, 'wall_seconds': time.monotonic() - started,
            'prompt_tokens': sum(a['prompt_tokens'] for a in answers),
            'completion_tokens': sum(a['completion_tokens'] for a in answers),
            'finish_reasons': [a['finish_reason'] for a in answers]})
    save('eight_fixed_unscored_timings', {'timings': report, 'actual_native_calls': len(native),
        'no_targets_grading_answer_selection_or_learner_import': True})


def transition(queued):
    for config in (old.FIRST, *(ROOT / s['path'] for s in old.STAGES[:2])):
        old.terminal(config)
    verify_recovery()
    if {d.metadata['Name']: d.version for d in importlib.metadata.distributions()} != queued['packages']:
        raise RuntimeError('The canonical Python package environment changed')
    if command([GIT, 'status', '--porcelain', '--untracked-files=no'], env=GIT_ENV).stdout:
        raise RuntimeError('Preserve unrelated tracked work; do not promote over a dirty tree')
    save('before_source_transition', {'original_source_HEAD': command([GIT, 'rev-parse', 'HEAD'], env=GIT_ENV).stdout.strip(),
                                     'approved_commits': list(COMMITS)})
    archive('before_source_transition')
    for commit in COMMITS:
        command([GIT, '-c', 'user.name=Codex', '-c', 'user.email=codex@localhost', 'cherry-pick', commit], env=GIT_ENV)
    command([str(ROOT / '.venv/bin/python'), '-c',
        "from pathlib import Path; from legal_skill_guard.learning import runtime_sources as s; "
        "root=Path.cwd();s.validate_bundle(root);"
        "[s.verify_revision(root,n,h) for n,vs in s.HISTORICAL.items() for h in vs]"])
    capture = capture_service(queued)
    timing_only(capture)
    run_map = {s['run_id']: s['run_id'].replace('20261023_run02', '20261023_run03') for s in old.STAGES[2:]}
    stages = []
    for stage in old.STAGES[2:]:
        path = ROOT / stage['path']
        if (sha(path) != stage['config_sha256']
                or sha(path.with_suffix('.frozen.json')) != stage['frozen_sha256']
                or (ROOT / 'runs' / stage['run_id']).exists()):
            raise RuntimeError('The declared prospective source profile is not untouched')
        source = new_profile(read(path), stage, ENVIRONMENT, run_map)
        target = ROOT / stage['path'].replace('20261023_run02', '20261023_run03')
        RunStore.immutable_json(target, source)
        code = ("from pathlib import Path;from experiments.openexempt_online import freeze;"
                "from legal_skill_guard.learning import runtime_sources as s;"
                "root=Path.cwd();cfg=Path(" + repr(str(target)) + ");"
                "extras=[root/n for n in s.CURRENT];"
                "extras += list((root/s.SNAPSHOTS).glob('*.py'));"
                "extras += list(root.glob('third_party/ace/prompts/*.py'));"
                "extras += [root/'third_party/ace/LICENSE.txt',root/'third_party/ace/NOTICE.md',"
                "root/'experiments/openexempt_frozen_eval.py',root/s.PROTOCOL,root/" + repr(PROTOCOL) + ","
                "root/" + repr(str(Path(__file__).relative_to(ROOT))) + ",root/'ops/" + UNIT + "'];"
                "freeze(cfg,additional_sources=extras)")
        command([str(ROOT / '.venv/bin/python'), '-c', code])
        stages.append({**stage, 'path': str(target.relative_to(ROOT)), 'run_id': source['run_id'],
            'config_sha256': sha(target), 'frozen_sha256': sha(target.with_suffix('.frozen.json'))})
    save('six_actual_new_frozen_profiles', {'stages': stages, 'actual_model': capture,
        'original_profiles_retained': True, 'no_quota_extension_during_freeze': True})
    archive('new_execution_and_profiles')
    return stages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('inspect', 'run'))
    args = parser.parse_args()
    queued = plan()
    if args.action == 'inspect':
        print(json.dumps({'plan_valid': True, 'stages': len(queued['stages']), 'no_state_change_or_model_calls': True}))
        return
    if old.ticks(2183806) == '474380328' or not RETIREMENT.is_file():
        raise RuntimeError('Retire only the verified waiting original controller before starting this one')
    OUT.mkdir(exist_ok=False)
    queued['retirement_receipt_sha256'] = sha(RETIREMENT)
    save('queued', queued)
    ledger = ROOT / read(old.FIRST)['teacher']['ledger']
    baseline = read(ledger)
    save('ledger_at_queue_unchanged', baseline)
    archive('queued')
    print('Waiting for exact Text45; no model/source/profile/ceiling changes', flush=True)
    while old.ticks(old.TEXT_PID) == old.TEXT_START:
        check_own_sources(queued)
        if old.ticks(old.MODEL_PID) != old.MODEL_START:
            raise RuntimeError('Original serving process ended; do not retry learning')
        time.sleep(45)
    predecessor, ceiling = old.FIRST, 3991
    for stage in old.STAGES[:2]:
        with (ROOT / 'artifacts/openexempt_training.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            old.unchanged(stage, OLD_SHA, queued['packages'])
            extend(ledger, baseline, ceiling, stage, predecessor, queued)
        print('Starting unchanged45 ablation', stage['run_id'], flush=True)
        command([str(ROOT / '.venv/bin/python'), '-u', '-m', stage['module'], 'run', str(ROOT / stage['path'])])
        save(stage['run_id'] + '_completed', old.terminal(ROOT / stage['path']))
        predecessor, ceiling = ROOT / stage['path'], stage['ceiling']
    with (ROOT / 'artifacts/openexempt_training.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stages = transition(queued)
    for stage in stages:
        with (ROOT / 'artifacts/openexempt_training.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = ROOT / stage['path']
            if (sha(path) != stage['config_sha256'] or sha(path.with_suffix('.frozen.json')) != stage['frozen_sha256']
                    or (ROOT / 'runs' / stage['run_id']).exists()
                    or any(sha(ROOT / n) != h for n, h in read(path.with_suffix('.frozen.json'))['files'].items())):
                raise RuntimeError('Require the exact newly frozen unstarted learner')
            extend(ledger, baseline, ceiling, stage, predecessor, queued)
        print('Starting matched prospective repeat', stage['run_id'], flush=True)
        command([str(ROOT / '.venv/bin/python'), '-u', '-m', stage['module'], 'run', str(path)])
        save(stage['run_id'] + '_completed', old.terminal(path))
        predecessor, ceiling = path, stage['ceiling']
    save('all_eight_stages_complete_NOT_TEST', {'runs': [s['run_id'] for s in old.STAGES[:2]] + [s['run_id'] for s in stages],
        'final_TEST_still_requires_complete16_real_banks_and_frozen_analysis': True})
    archive('all_eight_stages_complete_NOT_TEST')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / 'handoff_failed.json').exists():
            save('handoff_failed', {'error': repr(error), 'traceback': traceback.format_exc(),
                'no_retry_no_fallback_no_failed_stage_as_complete': True})
            archive('failed_handoff_terminal')
        raise
