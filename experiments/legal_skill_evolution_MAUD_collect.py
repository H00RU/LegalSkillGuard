"""Collect the completed fixed MAUD study without new inference or rescoring."""
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from experiments.legal_skill_evolution_MAUD_rule_acquisition import (
    ROOT, FOLDER, TEACHER_PARENT, PUBLIC, GRADING, LEDGER, read, name_for, setup)
from experiments.legal_skill_evolution_MAUD_boundary_control import HERE, verify

REPORT = ROOT / 'reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD'


def collect():
    protocol, _, public = setup()
    verify()
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        rows = db.execute('select * from calls order by id').fetchall()
    assert not any(r[6] == 'reserved' for r in rows)
    checks = []
    for folder in (TEACHER_PARENT, FOLDER):
        before = read(folder / 'ledger_before_row_hashes.json')
        present = {r[0]: digest(r) for r in rows}
        assert all(present.get(k) == v for k, v in before.items())
        checks.append({'run': folder.name, 'old_rows_unchanged': len(before)})
    assert checks[0]['old_rows_unchanged'] == 10099
    assert checks[1]['old_rows_unchanged'] == 10101
    selected = [r for r in rows if r[0].startswith((FOLDER.name + ':', TEACHER_PARENT.name + ':'))]
    assert Counter(r[1] for r in selected) == {'executor': 54, 'teacher': 3}
    calls = []
    for r in selected:
        result = json.loads(r[8])
        record = dict(zip(('id', 'role', 'purpose', 'bucket', 'source', 'request_hash', 'status', 'reserved_at'), r[:8]))
        record['usage'] = result.get('usage', result.get('invocation', {}).get('usage'))
        record['elapsed_seconds'] = result.get('elapsed_seconds')
        record['raw_result_sha256'] = digest(result)
        if r[1] == 'executor':
            request = read(Path(result['artifact_directory']) / 'request.json')
            payload = request['payload']
            assert payload['chat_template_kwargs']['enable_thinking'] is False
            assert payload['max_tokens'] == 8192
            assert result['thinking_requested'] is False and result['finish_reason'] == 'stop'
            record.update({'thinking': False, 'max_tokens': 8192, 'finish_reason': 'stop'})
        elif r[6] == 'failed':
            record.update({'usage_unknown': True, 'failure': '600-second teacher timeout; no recoverable semantic response'})
        calls.append(record)
    def total(role, field):
        return sum((r['usage'] or {}).get(field, 0) or 0 for r in calls if r['role'] == role)
    cost = {
        'captured_utc': read(FOLDER / 'cost_and_preservation.json')['captured_utc']
            if (FOLDER / 'cost_and_preservation.json').exists() else datetime.now(timezone.utc).isoformat(),
        'old_rows_unchanged': 10099, 'continuation_old_rows_unchanged': 10101,
        'new_executor_calls': 54, 'new_teacher_calls': 3, 'teacher_failed_calls': 1,
        'ledger_rows': len(rows), 'reserved': 0,
        'total_executor_calls': sum(r[1] == 'executor' for r in rows),
        'total_teacher_calls': sum(r[1] == 'teacher' for r in rows),
        'executor_prompt_tokens': total('executor', 'prompt_tokens'),
        'executor_completion_tokens': total('executor', 'completion_tokens'),
        'teacher_known_input_tokens': total('teacher', 'input_tokens'),
        'teacher_known_cached_input_tokens': total('teacher', 'cached_input_tokens'),
        'teacher_known_output_tokens': total('teacher', 'output_tokens'),
        'teacher_known_reasoning_output_tokens': total('teacher', 'reasoning_output_tokens'),
        'teacher_failed_usage_unknown': True,
        'executor_service_seconds': sum(r['elapsed_seconds'] or 0 for r in calls if r['role'] == 'executor'),
        'teacher_service_seconds_including_timeout': sum(r['elapsed_seconds'] or 0 for r in calls if r['role'] == 'teacher'),
        'cash_invoice_and_GPU_allocation_unknown': True,
        'calls_sha256': digest(rows), 'prefix_preservation': checks, 'calls': calls}
    grading = read(GRADING)
    results = []
    for stage in ('acquisition', 'reuse'):
        for key in protocol['acquisition_sources'] if stage == 'acquisition' else protocol['reuse_sources']:
            source = public[key]
            for view in source['views']:
                name = name_for(key, view)
                if stage == 'acquisition':
                    actual = {
                        'C': read(FOLDER / 'ConstraintAcquire/fitted_execution' / name),
                        'NoFit': read(FOLDER / 'acquisition/ConstraintAcquire' / name)['NoFit'],
                        'Free': read(FOLDER / 'acquisition/FreeUpdate' / name),
                        'FreeRepaired': read(HERE / 'acquisition/FreeRepaired' / name)}
                else:
                    actual = {'C': read(FOLDER / 'reuse_scores/ConstraintAcquire' / name),
                              'NoFit': read(HERE / 'scores/NoFit' / name),
                              'Free': read(FOLDER / 'reuse_scores/FreeUpdate' / name),
                              'FreeRepaired': read(HERE / 'scores/FreeUpdate' / name)}
                row = {'stage': stage, 'source': key, 'parent_id': source['parent_id'], 'view': view['id'],
                       'annotation': grading[key][view['id']], 'arms': {}}
                for arm, item in actual.items():
                    feedback = item['feedback']['views'][0]
                    value = feedback['execution']['value']
                    row['arms'][arm] = {'answer': value['answer'], 'core': feedback['core_executed'],
                        'correct': (feedback.get('score') or {}).get('correct', False),
                        'full_source_semantics_certified': False}
                if stage == 'reuse':
                    item = read(FOLDER / 'reuse_scores/SimpleControl' / name)
                    row['arms']['Simple'] = {'answer': item['actual']['answer'],
                        'correct': item['score']['correct'], 'core_method_credit': False}
                else:
                    row['arms']['Simple'] = {'correct': True, 'core_method_credit': False}
                results.append(row)
    metrics = {}
    for stage in ('acquisition', 'reuse'):
        subset = [r for r in results if r['stage'] == stage]
        for arm in ('C', 'NoFit', 'Free', 'FreeRepaired', 'Simple'):
            metrics[stage + ':' + arm] = {'correct': sum(r['arms'][arm]['correct'] for r in subset),
                'total': len(subset), 'core': sum(r['arms'][arm].get('core', False) for r in subset)
                    if arm != 'Simple' else None}
    assert [metrics['acquisition:' + a]['correct'] for a in ('C', 'NoFit', 'Free', 'FreeRepaired', 'Simple')] == [12, 12, 11, 12, 12]
    assert [metrics['reuse:' + a]['correct'] for a in ('C', 'NoFit', 'Free', 'FreeRepaired', 'Simple')] == [4, 5, 4, 5, 5]
    unscored = [*FOLDER.glob('reuse/*/*.json'), *HERE.glob('reuse/*/*.json')]
    scored = [*FOLDER.glob('reuse_scores/*/*.json'), *HERE.glob('scores/*/*.json')]
    assert len(unscored) == 24 and len(scored) == 30
    assert max(p.stat().st_mtime_ns for p in unscored) < min(p.stat().st_mtime_ns for p in scored)
    assert (HERE / 'freeze.json').stat().st_mtime_ns < min(p.stat().st_mtime_ns for p in unscored)
    for p in unscored:
        assert read(p)['feedback']['reason'] == 'unscored_execution'
    evidence = {'metrics': metrics, 'rows': results, 'fallback_physical_requests': 0,
        'independent_acquisition_mothers': 4, 'independent_reuse_mothers': 2,
        'old_full_TRAIN_exposure_retained_not_new_blind_test': True,
        'all_24_unscored_executions_saved_before_any_of_30_scores': True,
        'repair_frozen_before_first_future_material_execution': True,
        'score_cannot_certify_full_legal_norm': True, 'goal_complete': False}
    terminal = {'run_boundary_terminal': True, 'fixed_study_complete': True,
        'all_current_bindings_verified': True, 'supplementary_control_binding_verified': True,
        'ledger_rows': len(rows), 'old_ledger_rows_unchanged': 10099,
        'continuation_old_ledger_rows_unchanged': 10101, 'reserved_requests': 0,
        'metrics': metrics, 'goal_complete': False,
        'reason': 'Fixed4/2 TRAIN MAUD study complete; independent C gain and actual U learning remain unsupported.'}
    immutable_json(FOLDER / 'cost_and_preservation.json', cost)
    immutable_json(FOLDER / 'source_results.json', evidence)
    immutable_json(FOLDER / 'TERMINAL_PRESERVATION.json', terminal)
    REPORT.mkdir(parents=True, exist_ok=True)
    copies = [*FOLDER.glob('*.json'), *FOLDER.glob('initial/*.json'),
              *FOLDER.glob('reuse_initial/*.json'), *FOLDER.glob('shared/*.json'),
              *FOLDER.glob('ConstraintAcquire/*.json'),
              *FOLDER.glob('FreeUpdate/*.json'), *FOLDER.glob('ConstraintAcquire/fitted_execution/*.json'),
              *FOLDER.glob('acquisition/*/*.json'), *FOLDER.glob('reuse/*/*.json'),
              *FOLDER.glob('reuse_scores/*/*.json'), *FOLDER.glob('source_boundary_control/**/*.json')]
    # Persist all original inputs, paid outputs, failures and wire requests.
    for base, namespace in ((TEACHER_PARENT, 'original'), (FOLDER, 'continuation')):
        paths = [*base.glob('calls/*/*.json')]
        if namespace == 'original':
            paths += [*base.glob('ConstraintAcquire/*.json'), *base.glob('FreeUpdate/*.json'),
                      base / 'protocol.json', base / 'TERMINAL_PRESERVATION.json',
                      base / 'software_regression.log']
            paths += list(base.glob('teacher_adapter_cache/_failures/**/*.json'))
        for path in paths:
            target = REPORT / 'raw' / namespace / path.relative_to(base)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    for path in copies:
        target = REPORT / path.relative_to(FOLDER)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    print(json.dumps({'metrics': metrics, 'ledger_rows': len(rows),
                      'new_calls': {'executor': 54, 'teacher': 3}, 'goal_complete': False}))


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        collect()
