"""One deadline-driven sequence; unchanged learner, explicit shared controls, frozen supplement."""
import copy
import fcntl
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin
from experiments.openexempt_online import Online, actor_payload, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.legal_namespace import (
    decode_asset_references, decode_classification, decode_reference,
    public_asset_catalog, public_catalog,
)
from legal_skill_guard.openexempt import ROOT, evaluate, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def identity(pid):
    p = Path('/proc') / str(pid) / 'stat'
    return p.read_text().rsplit(') ', 1)[1].split()[19] if p.exists() else None


def progress(chain, stage, **values):
    RunStore.atomic_json(chain / 'progress.json', {'at': now(), 'stage': stage,
        'actual_pid': os.getpid(), **values})


def empty_origins(build):
    source = ROOT / 'runs' / build['shared_empty_control_source_run']
    rows = {(r['case_id'], r['family']): r for r in read(ROOT / build['input_packet'])['rows']}
    holder, entries = SimpleNamespace(cfg=build, request_cache={}), []
    for batch in range(1, 9):
        for rec in read(source / f'batches/b{batch}_prequential_records.json')['empty']:
            row = rows[rec['case_id'], rec['family']]
            assert rec['bank_sha256'] == csha([]) and rec['delivered_skill_ids'] == []
            path = ROOT / rec['raw_call_path']
            inp = read(path.with_suffix('.input.json'))
            messages, schema, _ = actor_payload(row, [], direct_numeric=True, asset_references=True)
            assert inp['messages'] == messages and inp['schema'] == schema
            cache_origin(holder, path)  # Retains length-ended outputs too, never scores or parsed answers.
            response = read(path)['response']
            entries.append({'case_id': rec['case_id'], 'family': rec['family'],
                'raw_call_path': rec['raw_call_path'], 'raw_sha256': sha(path),
                'input_sha256': sha(path.with_suffix('.input.json')),
                'finish_reason': response['finish_reason'],
                'original_prompt_tokens': response['prompt_tokens'],
                'original_completion_tokens': response['completion_tokens']})
    assert len(entries) == len(holder.request_cache) == 256
    return holder.request_cache, entries


def prepare(config_path):
    cfg = read(config_path)
    chain = ROOT / 'artifacts/launches' / cfg['run_id']
    build = read(ROOT / cfg['build_config'])
    assert build['source_cases'] == 128 and build['planned_batches'] == 8
    assert not build['frozen_after_first_batch_control'] and not build.get('initial_library_publication')
    _, entries = empty_origins(build)
    index = chain / 'shared_empty_control_index.json'
    if index.exists():
        assert read(index)['entries'] == entries  # Immutable preparation data can be reused, never overwritten.
    else:
        RunStore.immutable_json(index, {
            'at': now(), 'entries': entries, 'all256_uniform_including_incomplete_outputs': True,
            'no_score_parsed_answer_skill_or_teacher_import': True,
            'original_reference_prompt_tokens': sum(v['original_prompt_tokens'] for v in entries),
            'original_reference_completion_tokens': sum(v['original_completion_tokens'] for v in entries)})
    files = {Path(__file__).resolve(), config_path, index,
             ROOT / cfg['build_config'], ROOT / cfg['test_config'],
             ROOT / cfg['prespecified_completed_reference_test_config'], ROOT / cfg['protocol'],
             ROOT / 'artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py',
             ROOT / 'experiments/openexempt_online.py'}
    for key in ('build_config', 'test_config', 'prespecified_completed_reference_test_config'):
        files.add(ROOT / read(ROOT / cfg[key])['protocol'])
    binding = RunStore.immutable_json(chain / 'execution_plan_binding_v2.json', {
        'at': now(), 'files': {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
        'source_probe_pid': cfg['source_probe_pid'], 'source_probe_start_ticks': cfg['source_probe_start_ticks'],
        'checkpoint_deadline_utc': cfg['checkpoint_deadline_utc'], 'no_new_generation_in_preparation': True})
    names = [str(p.relative_to(ROOT)) for p in files | {binding}]
    RunStore.immutable_json(chain / 'prepared_preservation_v2.json', preserve(cfg['run_id'], 'prepared-deadline-plan-v2', names))
    return {'shared_control_origins': 256, 'prepared_files': len(names)}


def check_plan(chain):
    binding = read(chain / 'execution_plan_binding_v2.json')
    assert all(sha(ROOT / path) == digest for path, digest in binding['files'].items())


def finish_probe_before_reordering(cfg, chain):
    root = ROOT / 'runs' / cfg['source_probe_run']
    pid, ticks = cfg['source_probe_pid'], cfg['source_probe_start_ticks']
    progress(chain, 'waiting_for_actual_completed_probe_no_GPU_job', source_probe_pid=pid)
    while True:
        actual = identity(pid)
        if actual is not None:
            assert actual == ticks, 'Never signal a reused PID'
        if (root / 'completion.json').exists():
            try:
                complete = read(root / 'completion.json')
            except json.JSONDecodeError:
                time.sleep(.05)
                continue
            assert complete['status'] == 'completed_actual_revision_outcome_teacher_prefix_probe'
            if actual is not None:
                os.kill(pid, signal.SIGTERM)  # Existing handler requests artifact-safe stop; model untouched.
            RunStore.immutable_json(chain / 'handoff_reordered_after_valid_completion.json', {
                'at': now(), 'scientific_completion_sha256': sha(root / 'completion.json'),
                'probe_pid': pid, 'matched_start_ticks': ticks,
                'only_completed_controller_signalled_not_model': actual is not None,
                'reason': 'User12h priority; explicit shared-empty/deferred-ownB1 successor, not a method-quality stop'})
            while identity(pid) == ticks:
                time.sleep(.1)
            receipt = read(root / 'terminal_preservation.json')
            assert len(receipt['paths']) == 2 and all(sha(p['path']) == p['sha256'] for p in receipt['paths'])
            assert not (ROOT / 'runs' / cfg['old_unstarted_formal_run']).exists(), 'Old successor raced; do not run two studies'
            return complete
        if actual is None:
            raise RuntimeError('Probe exited without valid completion; inspect preserved failure, never restart blindly')
        time.sleep(.05)


def build_complete_method(cfg, chain):
    path = ROOT / cfg['build_config']
    build = read(path)
    cache, entries = empty_origins(build)
    assert entries == read(chain / 'shared_empty_control_index.json')['entries']
    assert not (ROOT / 'runs' / build['run_id']).exists()
    extra = {Path(__file__).resolve(), chain / 'execution_plan_binding_v2.json', chain / 'shared_empty_control_index.json',
             chain / 'handoff_reordered_after_valid_completion.json'}
    probe = ROOT / 'runs' / cfg['source_probe_run']
    extra.update({probe / 'completion.json', probe / 'paired_records.json', probe / 'terminal_preservation.json'})
    for e in entries:
        p = ROOT / e['raw_call_path']
        extra.update((p, p.with_suffix('.input.json')))
    freeze(path, additional_sources=extra)
    learner = Online(path)
    assert not learner.bank and not learner.request_cache
    learner.request_cache = cache
    RunStore.immutable_json(learner.out / 'shared_empty_control_import.json', {
        'at': now(), 'bank_empty': True, 'native_cache_before_import': 0,
        'exact_empty_origins_after_import': 256, 'origin_index_sha256': sha(chain / 'shared_empty_control_index.json'),
        'no_old_learned_bank_teacher_skill_answer_score_or_target_import': True,
        'ownB1_measurement_deferred_not_learning': True})
    progress(chain, 'complete8_learning_shared_empty_deferred_ownB1', active_run_id=build['run_id'])
    learner.run()
    complete = read(learner.out / 'completion.json')
    if complete['status'] != 'completed_bounded_mechanism_study' or len(complete['batch_summary']) != 8:
        return False
    assert all((learner.out / f'publications/b{b}.json').is_file() for b in range(1, 9))
    assert complete['bank'] == read(learner.out / 'publications/b8.json')['bank']
    first = read(learner.out / 'publications/b1.json')
    link = RunStore.immutable_json(learner.out / 'frozen_after_B1_deferred_measurement_link.json', {
        'at': now(), 'bank': first['bank'], 'bank_sha256': first['bank_sha256'],
        'immutable_publication_fixed_at_B1': True, 'source_publication_at': first['at'],
        'source_publication_sha256': sha(learner.out / 'publications/b1.json'),
        'metadata_link_written_after_build_not_a_later_bank_selection': True,
        'measurement_pending': True, 'never_teacher_or_admission': True})
    RunStore.immutable_json(learner.out / 'deferred_B1_link_preservation.json', preserve(build['run_id'],
        'actual-B1-deferred-measurement-link', [str(link.relative_to(ROOT)),
        str((learner.out / 'publications/b1.json').relative_to(ROOT))]))
    return True


def verify_old_record(row, rec, generation, grading_directory):
    path = ROOT / rec['raw_call_path']
    raw, inp = read(path), read(path.with_suffix('.input.json'))
    wire = raw['calls'][0]['request']
    assert raw.get('transport_error') is None and len(raw['calls']) == 1
    assert wire['messages'] == inp['messages']
    assert wire['response_format']['json_schema']['schema'] == inp['schema']
    assert all(wire[k] == generation[k] for k in ('model', 'seed', 'temperature', 'top_p', 'top_k', 'max_tokens'))
    observed, response = raw['calls'][0]['response'], raw['response']
    assert wire.get('chat_template_kwargs', {}).get('enable_thinking', True) == (not generation['disable_thinking'])
    assert observed['id'] == response['raw_id']
    assert observed['usage']['prompt_tokens'] == response['prompt_tokens']
    assert observed['usage']['completion_tokens'] == response['completion_tokens']
    assert observed['choices'][0]['finish_reason'] == response['finish_reason']
    assert (observed['choices'][0]['message'].get('content') or '').strip() == response['content']
    if rec['parse_error'] is None:
        submitted = json.loads(raw['response']['content'])
        decoded = decode_asset_references(submitted, public_asset_catalog(row))
        catalog = public_catalog(row)
        answer = (decode_classification(decoded, catalog) if row['family'] == 'EC' else
            {k: [{'citation': decode_reference(c['citation_ref'], catalog), 'claim_value': c['claim_value']}
                 for c in values] for k, values in decoded.items()})
        assert rec['parsed'] == {'answer': answer}
    else:
        answer = None
    target = read(ROOT / grading_directory / f"{row['case_id']}.json")['targets'][row['family']]
    assert evaluate(row, answer, target) == rec['score']


def version_supplement(config_path, chain):
    cfg = read(config_path)
    source_cfg = ROOT / cfg['source_training_config']
    source = ROOT / 'runs' / read(source_cfg)['run_id']
    complete = read(source / 'completion.json')
    assert complete['status'] == 'completed_bounded_mechanism_study' and len(complete['batch_summary']) == 8
    assert complete['bank'] == read(ROOT / cfg['initial_library_publication'])['bank']
    receipt = read(source / 'terminal_preservation.json')
    assert len(receipt['paths']) == 2 and all(sha(p['path']) == p['sha256'] for p in receipt['paths'])
    rows = read(ROOT / cfg['input_packet'])['rows']
    by_key = {(r['case_id'], r['family']): r for r in rows}
    assert len(rows) == 256 and len({r['source_key'] for r in rows}) == 128
    train_keys = {r['source_key'] for r in read(ROOT / read(source_cfg)['input_packet'])['rows']}
    assert not train_keys & {r['source_key'] for r in rows}
    original = ROOT / 'runs' / cfg['original_comparison_run']
    old = read(original / 'scored_records.json')
    old_complete = read(original / 'completion.json')
    controls = {name: copy.deepcopy(old[name]) for name in cfg['historical_ablation_names']}
    for name, records in controls.items():
        assert len(records) == 256 and {(r['case_id'], r['family']) for r in records} == set(by_key)
        for rec in records:
            assert rec['source_key'] == by_key[rec['case_id'], rec['family']]['source_key']
            verify_old_record(by_key[rec['case_id'], rec['family']], rec, cfg['generation'], cfg['grading_directory'])
        assert metrics(records) == old_complete['metrics'][name]
    reference = RunStore.immutable_json(chain / (cfg['run_id'] + '_verified_historical_references.json'), {
        'at': now(), 'source_scored_records_sha256': sha(original / 'scored_records.json'),
        'source_completion_sha256': sha(original / 'completion.json'), 'records': controls,
        'all512_historical_wire_decode_scores_verified': True,
        'historical_versions_not_new_matched_feedback_ablations': True})
    freeze(config_path, additional_sources={Path(__file__).resolve(), source_cfg,
        source_cfg.with_suffix('.frozen.json'), source / 'completion.json', source / 'terminal_preservation.json',
        source / 'publications/b8.json', reference})
    study, status = None, 'failed'
    out = ROOT / 'runs' / cfg['run_id']
    try:
        study = Online(config_path)
        assert not study.request_cache and study.bank == complete['bank']
        progress(chain, 'observed_original_TEST_single_fixed_version', active_run_id=cfg['run_id'],
                 version_label=cfg['version_label'])
        predictions = study._dispatch.native(lambda r: study.answer(r, study.bank, 'frozen_version', 'method'), rows)
        RunStore.immutable_json(out / 'predictions_before_any_grading.json', predictions)
        study.grade(predictions)
        RunStore.immutable_json(out / 'scored_records.json', predictions)
        actual_metrics = metrics(predictions)
        rng = np.random.Generator(np.random.PCG64(2026102801))
        indices = rng.integers(0, 128, size=(20000, 128))
        alpha = .05 / 8
        contrasts = []
        for name, records in controls.items():
            old_by_key = {(r['case_id'], r['family']): r for r in records}
            for family in ('EC', 'EV'):
                selected = sorted((r for r in predictions if r['family'] == family), key=lambda r: r['case_id'])
                for metric in ('f1', 'full_output_f1'):
                    delta = np.asarray([r['score'][metric] - old_by_key[r['case_id'], family]['score'][metric] for r in selected])
                    interval = np.quantile(delta[indices].mean(axis=1), [alpha / 2, 1 - alpha / 2]).tolist()
                    contrasts.append({'historical_reference': name, 'family': family, 'metric': metric,
                        'mean_difference': float(delta.mean()), 'help': int((delta > 1e-12).sum()),
                        'hurt': int((delta < -1e-12).sum()), 'ties': int((abs(delta) <= 1e-12).sum()),
                        'bonferroni8_source_bootstrap_interval': interval})
        result = {'at': now(), 'status': 'completed_observed_original_TEST_version_supplement',
            'version_label': cfg['version_label'], 'source_training_run': source.name,
            'bank_sha256': csha(study.bank), 'metrics': actual_metrics,
            'historical_reference_metrics': {name: metrics(v) for name, v in controls.items()},
            'contrasts': contrasts, 'all8_endpoint_numeric_differences_positive': all(x['mean_difference'] > 1e-12 for x in contrasts),
            'all8_adjusted_interval_lower_bounds_positive': all(x['bonferroni8_source_bootstrap_interval'][0] > 0 for x in contrasts),
            'actual_native_calls': len(study.native), 'actual_teacher_calls': 0,
            'native_prompt_tokens': sum(v['response']['prompt_tokens'] for v in study.native),
            'native_completion_tokens': sum(v['response']['completion_tokens'] for v in study.native),
            'not_new_unseen_TEST_or_matched_feedback_component_causal_claim': True,
            'fresh_source_disjoint_evaluation_and_other_goal_work_still_required': True}
        assert not study.teachers
        RunStore.immutable_json(out / 'completion.json', result)
        status = result['status']
        return result
    except BaseException as exc:
        RunStore.immutable_json(out / 'failure.json', {'at': now(), 'error': repr(exc),
            'traceback': traceback.format_exc(), 'actual_native_calls': len(study.native) if study else 0})
        raise
    finally:
        if study is not None:
            study.progress('terminal', state=status)
        names = [str(p.relative_to(ROOT)) for p in out.rglob('*') if p.is_file()]
        RunStore.immutable_json(out / 'terminal_preservation.json', preserve(cfg['run_id'], 'actual-terminal', names))


def run(config_path):
    cfg = read(config_path)
    chain = ROOT / 'artifacts/launches' / cfg['run_id']
    try:
        check_plan(chain)
        complete = finish_probe_before_reordering(cfg, chain)
        check_plan(chain)
        with (ROOT / 'artifacts/openexempt_training.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ready = build_complete_method(cfg, chain) if complete['formal_adoption_accepted'] else False
            if not ready:
                progress(chain, 'prespecified_completed_third_version_not_new_fix_success',
                         reason='Revised TRAIN gate failed or complete8 not reached; no TEST-based version choice')
            test_path = ROOT / cfg['test_config' if ready else 'prespecified_completed_reference_test_config']
            result = version_supplement(test_path, chain)
            RunStore.immutable_json(chain / 'checkpoint_ready.json', {
                'at': now(), 'deadline_utc': cfg['checkpoint_deadline_utc'],
                'tested_version': result['version_label'], 'test_run': read(test_path)['run_id'],
                'all8_endpoint_numeric_differences_positive': result['all8_endpoint_numeric_differences_positive'],
                'goal_not_complete_primary_new_TEST_and_remaining_evidence_pending': True})
            progress(chain, 'checkpoint_complete_full_goal_still_active', test_run=read(test_path)['run_id'])
    except BaseException as exc:
        failure = RunStore.immutable_json(chain / 'pipeline_failure.json', {
            'at': now(), 'error': repr(exc), 'traceback': traceback.format_exc(),
            'no_blind_restart_or_model_change': True})
        preserve(cfg['run_id'], 'pipeline-failure-evidence', [str(failure.relative_to(ROOT))])
        raise


if __name__ == '__main__':
    os.chdir(ROOT)
    action, path = sys.argv[1], Path(sys.argv[2]).resolve()
    if action == 'prepare':
        print(json.dumps(prepare(path)), flush=True)
    elif action == 'run':
        run(path)
    else:
        raise ValueError('Use prepare or run')
