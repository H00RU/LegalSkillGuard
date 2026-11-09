"""Offline composition comparison on already recorded TRAIN; no model client."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import numpy as np

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.composed_reader_channels import function_closure, primitive_functions, fit_channels, forecasts
from legal_skill_guard.rr.semantic_learning import H, Y
from experiments.rr_v2_semantic_learning import ROOT, STAGE as OLD, REPORT, read, check_frozen
from reports.method_redesign_20261109.audit_reader_backoff_control import empirical_backoff

STAGE = ROOT / 'artifacts/rr_method_redesign_20261109/composed_reader_offline_v1_20261109'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_snapshot():
    connection = sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
    tables = {name: connection.execute('SELECT * FROM ' + name + ' ORDER BY 1').fetchall()
              for name in ('calls', 'meta', 'oracle_views')}
    counts = dict(connection.execute('SELECT role, COUNT(*) FROM calls GROUP BY role'))
    pending = connection.execute("SELECT COUNT(*) FROM calls WHERE status='pending'").fetchone()[0]
    connection.close()
    return {'counts_total': counts, 'pending': pending,
            'logical_sha256': hashlib.sha256(json.dumps(tables, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def fixed_trajectory_support(rows, grammar):
    result = []
    for mother in sorted({r['mother'] for r in rows}):
        actual = [r for r in rows if r['mother'] == mother]
        slots = []
        for slot in range(4):
            slots.append([f['expression'] for f in grammar if all(
                f['table'][H.index((r['h'][slot % 2], r['h'][1 - slot % 2]))] == r['y'][slot]
                for r in actual)])
        result.append({'mother': mother, 'cases': [r['case_id'] for r in actual],
                       'fixed_class_operator_count': math.prod(len(s) for s in slots), 'slot_version_spaces': slots})
    return result


def main():
    frozen = check_frozen()
    files = ['legal_skill_guard/rr/composed_reader_channels.py', 'experiments/rr_v2_composed_reader_audit.py',
             'tests/test_rr_composed_reader_channels.py', 'reports/method_redesign_20261109/composed_channel_protocol.md']
    original_files = [OLD / 'frozen_learning.json', OLD / 'blind_predictions.json',
                      REPORT / 'M1M2_real_TRAIN_results.json', REPORT / 'reader_backoff_control_results.json']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in original_files}
    seal = {'files': {p: sha(ROOT / p) for p in files}, 'original_frozen_files': hashes,
            'training_case_ids': [r['case_id'] for r in frozen['training_rows']],
            'analysis': 'Offline repair diagnostic on previously observed TRAIN exclusions; not new blind validation',
            'new_model_calls': 0, 'new_sources_or_labels': 0, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal)
    destination = REPORT / 'composed_channel_results.json'
    if destination.exists():
        result = read(destination)
        assert result['seal_sha256'] == sha(STAGE / 'seal.json')
        for relative, value in result['saved_artifacts'].items():
            assert sha(STAGE / relative) == value
        print(json.dumps({'existing_verified_result': True, 'summary': result['scores']}, ensure_ascii=False)); return
    before = ledger_snapshot()
    started = time.perf_counter()
    model = fit_channels(frozen['training_rows'])
    fit_seconds = time.perf_counter() - started
    immutable_json(STAGE / 'fitted_model.json', model)
    recovered = read(STAGE / 'fitted_model.json')
    blind = read(OLD / 'blind_predictions.json')
    prediction = {}
    started = time.perf_counter()
    for cid, case in blind['cases'].items():
        all_h = []
        for h, old in zip(H, case['conditional_forecasts']):
            new = forecasts(model, h, case['context'])
            assert new == forecasts(recovered, h, case['context'])
            memory, _ = empirical_backoff(frozen['training_rows'], h, case['context'], old['independent'], .05)
            values = {'composed_joint': new['joint'], 'factorized_same_closure': new['factorized_same_closure'],
                      'untrained_same_closure': new['untrained_same_closure'],
                      'original_joint': old['structured'], 'grammar_free_memory_backoff': memory}
            for p in values.values():
                assert len(p) == 81 and all(v > 0 for v in p) and abs(sum(p) - 1.) < 1e-12
            all_h.append(values)
        prediction[cid] = {'context': case['context'], 'conditional_forecasts': all_h}
    forecast_and_reload_seconds = time.perf_counter() - started
    immutable_json(STAGE / 'all_h_predictions.json', prediction)
    original = read(REPORT / 'M1M2_real_TRAIN_results.json')
    per_case = []
    for r in original['rows']:
        cid = r['case_id']; yi = Y.index(tuple(r['y'])); hi = H.index(tuple(r['h']))
        models = {}
        for name in prediction[cid]['conditional_forecasts'][0]:
            distribution = prediction[cid]['conditional_forecasts'][hi][name]
            mode = max(distribution)
            mode_ties = [list(Y[i]) for i, p in enumerate(distribution) if abs(p - mode) <= 1e-12]
            likelihood = [f[name][yi] for f in prediction[cid]['conditional_forecasts']]
            best = max(likelihood)
            h_ties = [list(h) for h, p in zip(H, likelihood) if abs(p - best) <= 1e-12]
            models[name] = {'joint_NLL': -math.log(distribution[yi]), 'unique_joint_mode_correct': mode_ties == [r['y']],
                'joint_mode_ties': mode_ties, 'unique_inverse_MAP_correct': h_ties == [r['h']], 'inverse_MAP_ties': h_ties,
                'MAP_plus_complete_source_frame_correct': h_ties == [r['h']] and r['all_roles_candidate_covered']}
        per_case.append({'case_id': cid, 'mother': r['mother'], 'weight': r['weight'], 'observed_y': r['y'],
                         'teacher_h_for_conditional_scoring_only': r['h'], 'models': models})
    weight = sum(r['weight'] for r in per_case)
    scores = {name: {'mean_joint_NLL': sum(r['weight'] * r['models'][name]['joint_NLL'] for r in per_case) / weight,
        'unique_joint_mode_correct': sum(r['models'][name]['unique_joint_mode_correct'] for r in per_case),
        'unique_inverse_MAP_correct': sum(r['models'][name]['unique_inverse_MAP_correct'] for r in per_case),
        'MAP_plus_complete_source_frame_correct': sum(r['models'][name]['MAP_plus_complete_source_frame_correct'] for r in per_case)}
        for name in per_case[0]['models']}
    after = ledger_snapshot(); assert before == after
    assert all(sha(ROOT / path) == h for path, h in hashes.items())
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'seal_sha256': sha(STAGE / 'seal.json'),
        'analysis': seal['analysis'], 'new_model_calls': 0, 'new_sources_or_labels': 0,
        'grammar': model['grammar'], 'original_functions': 7, 'closure_functions': len(model['grammar']),
        'joint_operator_count': len(model['grammar']) ** 4, 'settings': model['settings'],
        'training_cases': seal['training_case_ids'], 'training_mothers': 2, 'scored_cases': 4,
        'original_excluded_TRAIN_mothers': 2, 'scores': scores, 'per_case': per_case,
        'trajectory_support': {'primitive_grammar': fixed_trajectory_support(frozen['training_rows'] + original['rows'], primitive_functions()),
                               'composed_grammar': fixed_trajectory_support(frozen['training_rows'] + original['rows'], model['grammar'])},
        'fit_seconds': fit_seconds, 'forecast_and_exact_reload_check_seconds': forecast_and_reload_seconds,
        'saved_artifacts': {p: sha(STAGE / p) for p in ['fitted_model.json', 'all_h_predictions.json']},
        'old_frozen_files_preserved': hashes, 'ledger_before': before, 'ledger_after': after,
        'semantic_acceptance_or_original_observations_modified': False, 'new_hyperparameters_scanned': False,
        'shared_ordinary_source_program_previous_local_correct': 4, 'shared_source_program_inference_calls': 0,
        'actual_native_legal_answers_evaluated': False, 'new_blind_efficacy_evidence': False,
        'independent_method_contribution_established': False, 'real_model_calls_triggered_by_this_audit': False,
        'goal_complete': False}
    immutable_json(destination, result)
    print(json.dumps({'scores': scores, 'functions': len(model['grammar']), 'fit_seconds': fit_seconds,
                      'ledger_unchanged': before == after, 'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
