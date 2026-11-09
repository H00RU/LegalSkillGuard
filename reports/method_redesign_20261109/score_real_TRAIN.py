"""Read-only evidence scoring; preserve rejected spans, score raw labels separately.

Added after the first excluded D response invented a span. The learner, all its
parameters, prompts, raw responses and blind forecasts remain byte-identical.
No repaired or accepted frame is manufactured from a rejected observation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.semantic_frames import frame_vector, reader_vector
from legal_skill_guard.rr.semantic_learning import H, Y, run_skill, decode_joint
from experiments.rr_v2_semantic_learning import (ROOT, STAGE, REPORT, read, response, check_frozen, annotations)


def raw(case, mode):
    record = response(case, mode)
    value = json.loads(record['physical_response']['content'])
    labels = (frame_vector if mode == 'direct' else reader_vector)({'values': value})
    return {'labels': labels, 'raw_value': value, 'source_span_accepted': record['validation']['status'] == 'decoded',
            'validation': record['validation'], 'raw_record': record}


def close():
    f = check_frozen(); seal = read(STAGE/'seal.json'); hashes = {}; decisions = {}
    assert not any((STAGE/'teacher'/(digest(c['source'])+'.json')).exists()
                   for c in seal['cases'] if c['fold'] == 'excluded')
    for case in seal['cases']:
        if case['fold'] != 'excluded': continue
        records = {mode: raw(case, mode) for mode in ('direct','reader','retrieval')}
        for mode in records:
            p = STAGE/'responses'/mode/(digest(case['case_id'])+'.json')
            hashes[str(p.relative_to(STAGE))] = hashlib.sha256(p.read_bytes()).hexdigest()
        y = records['direct']['labels'] + records['reader']['labels']
        p = read(STAGE/'blind_predictions.json')['cases'][case['case_id']]
        decisions[case['case_id']] = {'actual_y': y,
            'source_span_acceptance': {mode: r['source_span_accepted'] for mode, r in records.items()},
            'direct_source_role_candidate_raw': records['direct']['raw_value'],
            'M1': run_skill(f['skills']['M1'], y),
            'ordinary_tree': run_skill(f['skills']['ordinary_same_information_tree'], y),
            'direct_roles': records['direct']['labels'], 'correct_policy_cache': records['direct']['labels'],
            'retrieval': records['retrieval']['labels'], 'reader': records['reader']['labels'],
            'joint_inference': decode_joint(p['conditional_forecasts'], y),
            'candidate_source_span_valid': records['direct']['source_span_accepted'],
            'none_of_the_above_retained': True, 'raw_labels_are_not_accepted_frames': True}
    immutable_json(STAGE/'execution_closed_before_grading.json', {
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'files': hashes, 'decisions': decisions,
        'predictions_sha256': hashlib.sha256((STAGE/'blind_predictions.json').read_bytes()).hexdigest(),
        'evidence_scoring_source_sha256': hashlib.sha256(open(__file__,'rb').read()).hexdigest(),
        'all_arms_frozen_before_excluded_teacher': True, 'rejected_spans_never_repaired': True,
        'scoring_change': 'Schema labels are reader observations even if source-span checks reject the frame; score label prediction and accepted-source success separately. Frozen learner unchanged.'})
    print(json.dumps({'execution_closed': True, 'actual_responses': len(hashes), 'rejected_spans': {
        cid: [m for m,v in d['source_span_acceptance'].items() if not v] for cid,d in decisions.items()}, 'new_calls': 0}))


def evaluate():
    f = check_frozen(); seal = read(STAGE/'seal.json'); closure = read(STAGE/'execution_closed_before_grading.json')
    for p, sha in closure['files'].items(): assert hashlib.sha256((STAGE/p).read_bytes()).hexdigest() == sha
    gold = annotations(seal, 'excluded'); blind = read(STAGE/'blind_predictions.json')
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'rows': [], 'arms': {}, 'forecast_scores': {},
              'training_mothers': 2, 'excluded_mothers': 2, 'excluded_cases': 4,
              'native_legal_tasks_evaluated': 0, 'goal_complete': False, 'TEST_read': False}
    for case in seal['cases']:
        if case['fold'] != 'excluded': continue
        cid = case['case_id']; decision = closure['decisions'][cid]; y = decision['actual_y']; g = gold[cid]
        h = frame_vector({'values': g['frame']}); d = decision['direct_source_role_candidate_raw']
        roles = {name: (d[name] == g['frame'][name] or g['frame'][name] is None)
                 for name in ('payer','payee','work_activity','payment_medium')}
        frame_covered = decision['candidate_source_span_valid'] and all(roles.values())
        predictions = {'direct_roles': y[:2], 'correct_policy_cache': y[:2], 'local_reader': y[2:],
            'M1': decision['M1']['prediction'], 'ordinary_tree': decision['ordinary_tree']['prediction'],
            'same_material_retrieval': decision['retrieval']}
        predictions.update({'MAP_'+name: v['MAP_h'] for name, v in decision['joint_inference'].items()})
        accepted = {'direct_roles': decision['source_span_acceptance']['direct'],
            'correct_policy_cache': decision['source_span_acceptance']['direct'],
            'local_reader': decision['source_span_acceptance']['reader'],
            'same_material_retrieval': decision['source_span_acceptance']['retrieval']}
        for name in ('M1', 'ordinary_tree'):
            accepted[name] = all(decision['source_span_acceptance'][m] for m in decision[name]['prompt_groups'])
        accepted.update({'MAP_'+name: frame_covered for name in decision['joint_inference']})
        entry = {'case_id': cid, 'mother': case['source'], 'variant': case['variant'], 'weight': .5, 'h': h, 'y': y,
            'role_candidate_exact_coverage': roles, 'candidate_source_span_valid': decision['candidate_source_span_valid'],
            'all_roles_candidate_covered': frame_covered, 'predictions': predictions, 'source_acceptance': accepted,
            'M1_execution': decision['M1'], 'joint_inference': decision['joint_inference'],
            'teacher_frame': g['frame'], 'teacher_review': g['local_relation_review'], 'forecast_scores': {}}
        for name, pred in predictions.items():
            metric = {'raw_pair_exact': int(pred == h), 'source_accepted_pair_exact': int(pred == h and accepted[name]),
                'work_correct': int(pred[0] == h[0]), 'field_correct': sum(a == b for a,b in zip(pred,h)),
                'wrong_confident_fields': sum(a != b and a != 2 for a,b in zip(pred,h)),
                'unknown_fields': pred.count(2), 'source_span_accepted': int(accepted[name])}
            result['arms'].setdefault(name, []).append({'case_id': cid, **metric})
        dist = blind['cases'][cid]['conditional_forecasts'][H.index(tuple(h))]
        for name, probs in dist.items():
            yi = Y.index(tuple(y)); score = {'negative_log_likelihood': -math.log(probs[yi]),
                'joint_exact_top1': int(max(range(81), key=lambda i: probs[i]) == yi), 'observed_probability': probs[yi]}
            entry['forecast_scores'][name] = score
            result['forecast_scores'].setdefault(name, []).append({'case_id': cid, **score})
        result['rows'].append(entry)
    for section in ('arms','forecast_scores'):
        result[section] = {name: {'per_case': vals, 'mean': {
            k: sum(v[k] for v in vals)/len(vals) for k in vals[0] if k != 'case_id'}} for name, vals in result[section].items()}
    result['identifiability'] = {'reliable_anchor_available': False, 'unresolved_cases': 4, 'unresolved_ratio': 1.,
                                'MAP_is_not_semantic_acceptance': True, 'none_of_the_above_retained': True}
    result['M1_absorbed_by_same_information_tree'] = f['skills']['M1']['tree'] == f['skills']['ordinary_same_information_tree']['tree']
    result['candidate_complete_roles_covered'] = sum(r['all_roles_candidate_covered'] for r in result['rows'])
    result['minimum_scope'] = 'Local work/medium only; four TRAIN mothers, variants grouped. No full legal or cross-library validation.'
    immutable_json(REPORT/'M1M2_real_TRAIN_results.json', result)
    print(json.dumps({'arm_means': {k:v['mean'] for k,v in result['arms'].items()},
        'forecast_means': {k:v['mean'] for k,v in result['forecast_scores'].items()},
        'roles_covered': result['candidate_complete_roles_covered'], 'M1_absorbed': result['M1_absorbed_by_same_information_tree'],
        'unresolved': result['identifiability']}, ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('action', choices=['close','evaluate']); globals()[p.parse_args().action]()
