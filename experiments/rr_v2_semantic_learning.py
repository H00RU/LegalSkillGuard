"""Freeze learned programs and equal-information controls before excluded TRAIN."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.semantic_frames import frame_vector, reader_vector
from legal_skill_guard.rr.semantic_learning import (H, Y, context, compile_skill, run_skill,
    fit_channels, forecasts, operator_summary, decode_joint, semantic_loss)
from experiments.rr_v2_semantic_disambiguation_pilot import ROOT, STAGE, RUN

REPORT = ROOT/'reports/method_redesign_20261109'
LEARNING_FILES = ['legal_skill_guard/rr/semantic_learning.py', 'experiments/rr_v2_semantic_learning.py']


def read(path): return json.loads(path.read_text())


def response(case, mode):
    return read(STAGE/'responses'/mode/(digest(case['case_id'])+'.json'))


def observation(case):
    d, r = response(case, 'direct'), response(case, 'reader')
    assert d['validation']['status'] == r['validation']['status'] == 'decoded'
    return frame_vector(d['validation']['decoded']) + reader_vector(r['validation']['decoded'])


def annotations(seal, fold):
    result = {}
    for source in {c['source'] for c in seal['cases'] if c['fold'] == fold}:
        t = read(STAGE/'teacher'/(digest(source)+'.json'))
        assert all(v['status'] == 'decoded' for v in t['validation'])
        for row in t['value']['cases']:
            assert row['edit_valid_for_local_roles'], 'Keep invalid edit separate; do not silently train on it'
            result[row['case_id']] = row
    return result


def learning_rows(seal, fold):
    gold = annotations(seal, fold); rows = []
    for case in seal['cases']:
        if case['fold'] != fold: continue
        g = gold[case['case_id']]
        rows.append({'case_id': case['case_id'], 'mother': case['source'], 'h': frame_vector({'values': g['frame']}),
                     'y': observation(case), 'context': context(case['facts']), 'weight': .5,
                     'teacher_review': g['local_relation_review']})
    return rows


def freeze():
    seal = read(STAGE/'seal.json')
    assert not any((STAGE/'responses'/m/(digest(c['case_id'])+'.json')).exists()
                   for c in seal['cases'] if c['fold'] == 'excluded' for m in ('direct', 'reader', 'retrieval'))
    rows = learning_rows(seal, 'induction'); models = fit_channels(rows)
    skills = {'M1': compile_skill(rows), 'ordinary_same_information_tree': compile_skill(rows, contrast=False)}
    materials = []
    for case in seal['cases']:
        if case['fold'] != 'induction': continue
        row = next(r for r in rows if r['case_id'] == case['case_id'])
        materials.append({'facts': case['facts'], 'focus': case['focus'],
                          'direct_output': read(STAGE/'responses/direct'/(digest(case['case_id'])+'.json'))['validation']['decoded']['values'],
                          'local_reader_output': read(STAGE/'responses/reader'/(digest(case['case_id'])+'.json'))['validation']['decoded']['values'],
                          'verified_frame': annotations(seal, 'induction')[case['case_id']]['frame'],
                          'verified_relation_review': row['teacher_review']})
    questions = []
    for source in sorted({r['mother'] for r in rows}):
        questions.extend(read(STAGE/'teacher'/(digest(source)+'.json'))['value']['discrimination_questions'])
    files = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in LEARNING_FILES}
    frozen = {'run_id': RUN, 'captured_utc': datetime.now(timezone.utc).isoformat(), 'files': files,
              'acquisition_seal_sha256': hashlib.sha256((STAGE/'seal.json').read_bytes()).hexdigest(),
              'training_rows': rows, 'skills': skills, 'models': models, 'retrieval_materials': materials,
              'training_discrimination_questions': questions,
              'question_use': 'Training questions motivate the fixed D/R semantic slots; no unasked question is replayed as answered',
              'operator_summary': operator_summary(models, rows),
              'candidate_rule': 'Actual direct frame roles or explicit unknown; all nine class hypotheses. No gold insertion; role coverage graded separately.',
              'decoder_rule': 'Common maximum likelihood/MAP for statistics, unresolved without a trusted relation anchor',
              'M1_objective': 'Lexicographic supervised loss incl false exclusion, contrast failure, physical group cost, size; depth-limited deterministic search',
              'teacher_annotation_level': 'Source-inspected TRAIN local relation judgments, not full legal answers',
              'semantic_certificate_claimed': False, 'goal_complete': False}
    immutable_json(STAGE/'frozen_learning.json', frozen)
    predictions = {'captured_utc': datetime.now(timezone.utc).isoformat(),
                   'frozen_learning_sha256': hashlib.sha256((STAGE/'frozen_learning.json').read_bytes()).hexdigest(),
                   'Y_order': [list(y) for y in Y], 'H_order': [list(h) for h in H], 'cases': {}}
    for case in seal['cases']:
        if case['fold'] == 'excluded':
            predictions['cases'][case['case_id']] = {'context': context(case['facts']),
                'conditional_forecasts': [forecasts(models, h, context(case['facts'])) for h in H]}
    immutable_json(STAGE/'blind_predictions.json', predictions)
    receipt = {'captured_utc': predictions['captured_utc'], 'training_rows': rows, 'skills': skills,
               'operators': frozen['operator_summary'], 'excluded_actual_responses_seen': 0,
               'frozen_learning_sha256': predictions['frozen_learning_sha256'],
               'blind_predictions_sha256': hashlib.sha256((STAGE/'blind_predictions.json').read_bytes()).hexdigest()}
    immutable_json(REPORT/'M1M2_freeze_receipt.json', receipt)
    print(json.dumps({'frozen': True, 'train_mothers': 2, 'skills': skills, 'new_calls': 0}))


def check_frozen():
    f = read(STAGE/'frozen_learning.json')
    for p, sha in f['files'].items(): assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == sha, p
    assert read(STAGE/'blind_predictions.json')['frozen_learning_sha256'] == hashlib.sha256((STAGE/'frozen_learning.json').read_bytes()).hexdigest()
    return f


def close():
    check_frozen(); seal = read(STAGE/'seal.json'); hashes = {}
    for case in seal['cases']:
        if case['fold'] != 'excluded': continue
        for mode in ('direct', 'reader', 'retrieval'):
            p = STAGE/'responses'/mode/(digest(case['case_id'])+'.json')
            assert p.exists(); hashes[str(p.relative_to(STAGE))] = hashlib.sha256(p.read_bytes()).hexdigest()
    # Save actual source bindings and all arm decisions BEFORE grading requests.
    decisions = {}
    for c in seal['cases']:
        if c['fold'] != 'excluded': continue
        y = observation(c)
        p = read(STAGE/'blind_predictions.json')['cases'][c['case_id']]
        decisions[c['case_id']] = {'actual_y': y,
            'direct_source_role_candidates': response(c, 'direct')['validation']['decoded'],
            'M1': run_skill(read(STAGE/'frozen_learning.json')['skills']['M1'], y),
            'ordinary_tree': run_skill(read(STAGE/'frozen_learning.json')['skills']['ordinary_same_information_tree'], y),
            'correct_policy_cache': y[:2], 'direct_roles': y[:2],
            'retrieval': reader_vector(response(c, 'retrieval')['validation']['decoded']),
            'joint_inference': decode_joint(p['conditional_forecasts'], y),
            'none_of_the_above_retained': True}
    immutable_json(STAGE/'execution_closed_before_grading.json', {
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'files': hashes, 'decisions': decisions,
        'predictions_sha256': hashlib.sha256((STAGE/'blind_predictions.json').read_bytes()).hexdigest(),
        'all_arms_frozen_before_excluded_teacher': True})
    print(json.dumps({'closed': True, 'excluded_responses': len(hashes), 'new_calls': 0}))


def evaluate():
    f = check_frozen(); seal = read(STAGE/'seal.json'); closure = read(STAGE/'execution_closed_before_grading.json')
    for p, sha in closure['files'].items(): assert hashlib.sha256((STAGE/p).read_bytes()).hexdigest() == sha
    rows = learning_rows(seal, 'excluded'); gold = annotations(seal, 'excluded')
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'rows': [], 'arms': {}, 'forecast_scores': {},
              'training_mothers': 2, 'excluded_mothers': 2, 'excluded_cases': len(rows),
              'native_legal_tasks_evaluated': 0, 'goal_complete': False, 'TEST_read': False}
    blind = read(STAGE/'blind_predictions.json')
    for row in rows:
        cid = row['case_id']; case = next(c for c in seal['cases'] if c['case_id'] == cid)
        decision = closure['decisions'][cid]; y = row['y']; h = row['h']; teacher = gold[cid]['frame']
        direct = response(case, 'direct')['validation']['decoded']['values']
        role_coverage = {name: (direct[name] == teacher[name] or teacher[name] is None) for name in ('payer', 'payee', 'work_activity', 'payment_medium')}
        # Null branches are explicitly possible. Exact matching is conservative;
        # merely containing a gold phrase is not a role correctness certificate.
        arm = {'direct_roles': y[:2], 'correct_policy_cache': y[:2], 'local_reader': y[2:],
               'M1': decision['M1']['prediction'], 'ordinary_tree': decision['ordinary_tree']['prediction'],
               'same_material_retrieval': decision['retrieval']}
        arm.update({'MAP_'+name: v['MAP_h'] for name, v in decision['joint_inference'].items()})
        entry = {**row, 'variant': case['variant'], 'role_candidate_exact_coverage': role_coverage,
                 'all_roles_candidate_covered': all(role_coverage.values()), 'arms': arm,
                 'M1_execution': decision['M1'], 'joint_inference': decision['joint_inference'],
                 'teacher_frame': teacher, 'teacher_review': gold[cid]['local_relation_review'], 'forecast_scores': {}}
        for name, pred in arm.items():
            metric = {'pair_exact': int(pred == h), 'work_correct': int(pred[0] == h[0]),
                      'field_correct': sum(a == b for a, b in zip(pred, h)),
                      'wrong_confident_fields': sum(a != b and a != 2 for a, b in zip(pred, h)),
                      'unknown_fields': pred.count(2)}
            result['arms'].setdefault(name, []).append({'case_id': cid, **metric})
        dist = blind['cases'][cid]['conditional_forecasts'][H.index(tuple(h))]
        for name, probabilities in dist.items():
            yi = Y.index(tuple(y)); score = {'negative_log_likelihood': -math.log(probabilities[yi]),
                'joint_exact_top1': int(max(range(81), key=lambda i: probabilities[i]) == yi),
                'observed_probability': probabilities[yi], 'conditioned_on_grading_h_only_for_scoring': True}
            entry['forecast_scores'][name] = score
            result['forecast_scores'].setdefault(name, []).append({'case_id': cid, **score})
        result['rows'].append(entry)
    for section in ('arms', 'forecast_scores'):
        result[section] = {name: {'per_case': values, 'mean': {
            k: sum(v[k] for v in values)/len(values) for k in values[0] if isinstance(values[0][k], (int, float))}}
            for name, values in result[section].items()}
    result['identifiability'] = {'reliable_anchor_available': False, 'unresolved_cases': len(rows),
        'unresolved_ratio': 1., 'MAP_is_not_semantic_acceptance': True, 'none_of_the_above_retained': True}
    result['M1_absorbed_by_same_information_tree'] = f['skills']['M1']['tree'] == f['skills']['ordinary_same_information_tree']['tree']
    result['minimum_scope'] = 'One local work/medium relation family, four TRAIN mothers, controlled edits grouped; no full legal or cross-library claim'
    immutable_json(REPORT/'M1M2_real_TRAIN_results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'arms', 'forecast_scores')}, ensure_ascii=False))
    print(json.dumps({'arm_means': {k: v['mean'] for k, v in result['arms'].items()},
        'forecast_means': {k: v['mean'] for k, v in result['forecast_scores'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['freeze', 'close', 'evaluate'])
    globals()[p.parse_args().action]()
