"""Deterministic native consumption and TRAIN scoring of preserved paid reads.

This is postprocessing of the same physical requests, not another independent
trial. Unknowns, malformed outputs and unsupported module domains remain in
the denominator. Native labels enter only after the prediction is constructed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.legal_consumers import contract, maud
from legal_skill_guard.paired_interfaces.native_adapters import run_airline
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--read-phase', choices=['pilot_reads_v1', 'pilot_reads_v2'], default='pilot_reads_v2')
    args = parser.parse_args()
    out = BASE / ('pilot_native_postprocessing_' + args.read_phase.removeprefix('pilot_reads_'))
    lock = read(BASE / 'pilot_lock.json')
    train_root = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    train = {s['key']: s for s in read(train_root / 'public.json')}
    modules = ['legal_skill_guard/paired_interfaces/native_adapters.py',
               'legal_skill_guard/paired_interfaces/legal_consumers.py',
               'experiments/two_method_score_pilot_reads.py']
    protocol = {'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'), 'read_phase': args.read_phase,
        'source_sha256': {p: sha(ROOT / p) for p in modules},
        'prediction_uses_native_grading_or_reference_arguments': False,
        'all_inputs_are_actual_locked_pilot_read_outputs': True,
        'new_model_calls': 0, 'independent_repeat_claimed': False}
    immutable_json(out / 'protocol.json', protocol)
    predictions = []
    for path in sorted((BASE / args.read_phase / 'reads').glob('*/decoded.json')):
        row = read(path)
        source = train[row['source']]
        graph = row['decoded_graph']
        outputs = {}
        for view in source['views']:
            if row['native_view_to_opaque_source_view'][view['id']] != row['opaque_source_view']:
                continue
            if row['errors'] or graph is None:
                result = {'handled': False, 'answer': None, 'reason': 'invalid or truncated physical reading'}
            elif source['dataset'] == 'ContractNLI':
                result = contract(graph, view['id'])
            elif source['dataset'] == 'MAUD':
                result = maud(graph, view['id'])
            elif source['dataset'] == 'RuleArena_Airline':
                result = run_airline(graph, gi.source_units(source, view),
                                     lock['modules']['RuleArena_Airline']['sha256'])
            else:
                result = {'handled': False, 'answer': None, 'reason': 'native graph adapter not implemented'}
            outputs[view['id']] = result
        prediction = {'source': row['source'], 'dataset': source['dataset'], 'plan': row['plan'],
            'plan_version': row['plan_version'], 'physical_call_id': row['physical_call_id'],
            'read_artifact_sha256': sha(path), 'read_errors': row['errors'], 'outputs': outputs,
            'same_physical_read_postprocessed': True, 'new_model_calls': 0}
        immutable_json(out / 'predictions' / path.parent.name / 'prediction.json', prediction)
        predictions.append(prediction)
    # Only original TRAIN labels, mechanically applied after predictions exist.
    grading = read(train_root / 'grading.json')
    rows = []
    for prediction in predictions:
        for view_id, result in prediction['outputs'].items():
            label = grading[prediction['source']][view_id]['answer']
            if prediction['dataset'] not in ('ContractNLI', 'MAUD', 'RuleArena_Airline', 'SARA_v2_Binary'):
                score, native_metric = None, 'requires original structured native grader'
            else:
                score = int(bool(result['handled']) and result['answer'] == label)
                native_metric = 'exact_match'
            rows.append({'source': prediction['source'], 'dataset': prediction['dataset'],
                'view': view_id, 'plan': prediction['plan'], 'plan_version': prediction['plan_version'],
                'physical_call_id': prediction['physical_call_id'], 'handled': result['handled'],
                'prediction': result['answer'], 'reference': label, 'score': score,
                'native_metric': native_metric, 'fallback_executed': False})
    by_parent = defaultdict(list)
    for row in rows:
        if row['score'] is not None:
            by_parent[row['dataset'], row['plan'], row['source']].append(row['score'])
    by_dataset = defaultdict(list)
    for (dataset, plan, source), scores in by_parent.items():
        by_dataset[dataset, plan].append(sum(scores) / len(scores))
    summary = [{'dataset': d, 'plan': p, 'mothers_observed': len(values),
                'mother_macro': sum(values) / len(values)}
               for (d, p), values in sorted(by_dataset.items())]
    artifact = {'rows': rows, 'observed_partial_cohort_summary': summary,
        'pilot_complete': False, 'method_effect_or_generalization_claimed': False,
        'same_paid_read_postprocessing_not_an_independent_trial': True, 'new_model_calls': 0}
    key = digest(artifact)
    immutable_json(out / 'snapshots' / (key + '.json'), artifact)
    print(json.dumps({'observed_read_outputs': len(predictions), 'handled_native_views': sum(r['handled'] for r in rows),
                      'summary': summary, 'snapshot': key, 'pilot_complete': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
