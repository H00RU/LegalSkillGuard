"""Finite user-approved acceleration: matched two controls, frozen8, draft handoff.

Reuse the existing scheduling, preservation and frozen-comparison implementation.
No additional independent learning, timing repetition, answer repair or fallback.
"""
from __future__ import annotations

import copy
import fcntl
import importlib.util
from pathlib import Path
import sys
import traceback

ROOT = Path('/media/sangfor/vdb/legal-skill-evolve')
sys.path.insert(0, str(ROOT))
from experiments.openexempt_online import freeze, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning import runtime_sources
from legal_skill_guard.learning.experiment import now, read, sha

PREVIOUS = ROOT / 'artifacts/launches/openexempt_table_then_teacher_draft_20261024_run05.py'
spec = importlib.util.spec_from_file_location('preserved_staged_table_builder', PREVIOUS)
table = importlib.util.module_from_spec(spec)
spec.loader.exec_module(table)
phase = table.phase
DEFERRED = copy.deepcopy(table.STAGES[2:])
OUT = ROOT / 'artifacts/launches/openexempt_uniform_ablations_then_teacher_draft_20261025_run01'
RUN = 'legal_openexempt_uniform_ablations_then_teacher_draft_20261025_run01'
ENVIRONMENT = 'artifacts/live_8b_environment_phase_dispatch_20261025.json'
TIMING = ROOT / 'artifacts/launches/openexempt_uniform_ablation_acceleration_20261025_run01'
STOP = ROOT / ('artifacts/research/openexempt_legal_scope_20261020/'
    'WholeBank45_original492_user_authorized_stop_before_uniform_acceleration_verified_dual_20261025.json')
CONFIGS = [
    'configs/openexempt_whole_bank_public_assets128_phase4_20261025_run01.json',
    'configs/openexempt_task_local_public_assets128_phase4_20261025_run01.json']
INITIAL = 'configs/openexempt_initial8_frozen_TEST_20261025_run01.json'
FUTURE = str((OUT / 'six_future_learning_recipes_before_initial_TEST.json').relative_to(ROOT))
phase.OUT, phase.RUN = OUT, RUN
phase.ENVIRONMENT, phase.PROTOCOL = ENVIRONMENT, runtime_sources.CONTROL_PROTOCOL
table.OUT, table.RUN, table.INITIAL_CONFIG, table.FUTURE_PLAN = OUT, RUN, INITIAL, FUTURE


def save(name, value):
    RunStore.immutable_json(OUT / (name + '.json'), {'at': now(), **value})


def archive(label):
    names = {str(p.relative_to(ROOT)) for p in OUT.rglob('*') if p.is_file()}
    names.update(str(p.relative_to(ROOT)) for p in (
        Path(__file__), PREVIOUS, phase.OLD, table.owner.PHASE_FILE, STOP,
        ROOT / ENVIRONMENT, ROOT / runtime_sources.CONTROL_PROTOCOL,
        ROOT / table.PROTOCOL, phase.NEW_UNIT,
        TIMING / 'actual_timing_interpretation.json',
        TIMING / 'actual_eight_timing_complete_preservation.json'))
    for config in CONFIGS + [INITIAL]:
        path = ROOT / config
        names.update(str(p.relative_to(ROOT)) for p in (path, path.with_suffix('.frozen.json'))
                     if p.is_file())
    recipes = OUT / 'six_prospective_recipes_not_learning_authority.json'
    if recipes.is_file():
        for stage in read(recipes)['stages']:
            path = ROOT / stage['path']
            names.update(str(p.relative_to(ROOT)) for p in (path, path.with_suffix('.frozen.json')))
    receipt = preserve(RUN, label, sorted(names))
    if len({Path(p['path']).stat().st_dev for p in receipt['paths']}) != 2:
        raise RuntimeError('Require two distinct preservation devices')
    save(label + '_preservation', receipt)


phase.archive = table.archive = archive


def freeze_profile(path):
    extras = runtime_sources.validate_bundle(ROOT)
    extras.update((ROOT / runtime_sources.SNAPSHOTS).glob('*.py'))
    extras.update(ROOT.glob('third_party/ace/prompts/*.py'))
    extras.update({Path(__file__), PREVIOUS, ROOT / runtime_sources.CONTROL_PROTOCOL,
        ROOT / table.PROTOCOL, ROOT / 'experiments/openexempt_frozen_eval.py',
        ROOT / 'third_party/ace/LICENSE.txt', ROOT / 'third_party/ace/NOTICE.md',
        phase.NEW_UNIT})
    freeze(path, additional_sources=extras)


def extend(ledger, baseline, previous_ceiling, stage, predecessor=None):
    if predecessor is not None:
        phase.old.terminal(predecessor)
    with ledger.with_suffix(ledger.suffix + '.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = read(ledger)
        stable = lambda d: {k: v for k, v in d.items()
                            if k not in ('max_invocations', 'reservations')}
        if (before['max_invocations'] != previous_ceiling
                or stable(before) != stable(baseline)
                or before['reservations'][:len(baseline['reservations'])] != baseline['reservations']
                or stage['ceiling'] != previous_ceiling + 32):
            raise RuntimeError('Never reset quota, remove reservations or add undeclared learning')
        save(stage['run_id'] + '_before_extension', {'ledger': before, 'next': stage})
        archive(stage['run_id'] + '_before_extension')
        RunStore.atomic_json(ledger, {**before, 'max_invocations': stage['ceiling']})


def freeze_future_recipes():
    """Freeze six existing recipes; grant no execution or budget authority."""
    mapping = {s['run_id']: s['run_id'].replace('20261023_run02', 'phase4_20261025_run01')
               for s in DEFERRED}
    old_whole = 'legal_openexempt_whole_bank_public_assets128_20261023_run02'
    mapping[old_whole] = read(ROOT / CONFIGS[0])['run_id']
    stages = []
    ceiling = 4087
    for stage in DEFERRED:
        original = ROOT / stage['path']
        if (sha(original) != stage['config_sha256']
                or sha(original.with_suffix('.frozen.json')) != stage['frozen_sha256']
                or (ROOT / 'runs' / stage['run_id']).exists()):
            raise RuntimeError('Future recipes must remain genuinely unstarted and unchanged')
        value = phase.new_profile(read(original), stage, ENVIRONMENT, mapping)
        ceiling += stage['attempts']
        value['teacher']['total_invocation_budget'] = ceiling
        value['source_rebase_reason'] = ('Prospective recipe only after the user-approved uniform '
            'control execution amendment; identical scientific conditions, no learner or teacher execution.')
        for key in ('current_live_ledger_ceiling_not_changed',
                    'current_live_ledger_ceiling_at_preparation_not_changed'):
            if key in value:
                value[key] = 4087
        value['additional_learning_execution_authorization'] = 'deferred_until_user_review_after_teacher_draft'
        target = ROOT / stage['path'].replace('20261023_run02', 'phase4_20261025_run01')
        RunStore.immutable_json(target, value)
        freeze_profile(target)
        stages.append({**stage, 'path': str(target.relative_to(ROOT)), 'run_id': value['run_id'],
            'ceiling': ceiling, 'config_sha256': sha(target),
            'frozen_sha256': sha(target.with_suffix('.frozen.json'))})
    save('six_prospective_recipes_not_learning_authority', {'stages': stages,
        'teacher_calls': 0, 'ledger_extension': 0, 'independent_repeats_deferred': True})
    return stages


def main():
    timing = read(TIMING / 'actual_timing_interpretation.json')
    if (timing['observed_eight_call_wall_speedup'] < 1.5
            or timing['parallel_tokens_per_second'] / timing['serial_tokens_per_second'] < 1.5):
        raise RuntimeError('No sufficient measured gain; do not start an accelerated replacement pair')
    proof = read(STOP)
    if proof['native_calls'] != 492 or not proof['partial_B4_C1_not_published']:
        raise RuntimeError('Preserve the actual interrupted predecessor without a completed-control claim')
    for row in proof['terminal_archives_verified_each_member']:
        if sha(Path(row['path'])) != row['sha256']:
            raise RuntimeError('Original terminal backup changed')
    configs = [read(ROOT / name) for name in CONFIGS]
    table.STAGES = [{'path': path, 'run_id': cfg['run_id']}
                    for path, cfg in zip(CONFIGS, configs)]
    profiles = {(str(cfg['phase_dispatch']), cfg['inference_environment']) for cfg in configs}
    if (len(profiles) != 1 or {cfg['skill_commit_policy'] for cfg in configs}
            != {'whole_bank', 'task_local'} or not all(runtime_sources.uniform_control(c) for c in configs)
            or any((ROOT / 'runs' / cfg['run_id']).exists() for cfg in configs)):
        raise RuntimeError('Only two fresh matched explicitly amended controls are permitted')
    OUT.mkdir(exist_ok=False)
    save('queued', {'configs': CONFIGS, 'timing': timing, 'environment': read(ROOT / ENVIRONMENT),
        'all_independent_repeats_deferred': True, 'old_partial_control_retained_not_imported': True})
    for path in CONFIGS:
        freeze_profile(ROOT / path)
    archive('both_controls_frozen_before_any_new_learning')
    ledger = ROOT / configs[0]['teacher']['ledger']
    baseline = read(ledger)
    if baseline['max_invocations'] != 4023:
        raise RuntimeError('Retain the exact pre-handoff quota ceiling and all reservations')
    with (ROOT / 'artifacts/openexempt_training.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous, ceiling = None, 4023
        for path, cfg in zip(CONFIGS, configs):
            stage = {'path': path, 'run_id': cfg['run_id'], 'ceiling': ceiling + 32}
            if cfg['teacher']['total_invocation_budget'] != stage['ceiling']:
                raise RuntimeError('Bind each two-candidate control to its exact declared ceiling')
            extend(ledger, baseline, ceiling, stage, previous)
            print('Starting matched phase4 control: ' + cfg['run_id'], flush=True)
            phase.command([str(ROOT / '.venv/bin/python'), '-u', '-m',
                'experiments.openexempt_online', 'run', str(ROOT / path)])
            save(cfg['run_id'] + '_complete', phase.old.terminal(ROOT / path))
            archive(cfg['run_id'] + '_complete')
            previous, ceiling = ROOT / path, stage['ceiling']
        future = freeze_future_recipes()
        table.prepare_initial(future, learning_schedule=runtime_sources.CONTROL_SCHEDULE,
            learning_protocol=runtime_sources.CONTROL_PROTOCOL,
            evaluation_run_id='legal_openexempt_initial8_frozen_TEST_20261025_run01',
            additional_dependencies=(str(Path(__file__).relative_to(ROOT)),))
        archive('six_recipes_and_initial8_before_TEST')
        table.evaluate(INITIAL)
    save('necessary_experiments_complete_teacher_draft_handoff', {
        'two_uniform_controls_complete': True, 'frozen8_complete_and_dual_preserved': True,
        'all_independent_repeats_deferred_not_started': True,
        'no_second_timing_or_final16_or_extra_learning': True,
        'teacher_ledger_ceiling': 4087, 'actual_manuscript_results_integration_still_required': True})
    archive('necessary_experiments_complete_teacher_draft_handoff')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if OUT.is_dir() and not (OUT / 'handoff_failed.json').exists():
            save('handoff_failed', {'error': repr(exc), 'traceback': traceback.format_exc(),
                'no_retry_fallback_or_failed_stage_success': True})
            archive('failed_handoff_terminal')
        raise
