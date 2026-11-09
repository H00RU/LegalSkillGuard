"""One source edit that separates two preserved real TRAIN explanations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from experiments.rr_v2_semantic_disambiguation_pilot import messages
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import (
    FRAME_SCHEMA, decode_frame, exact_edit, frame_vector, obj,
)
from legal_skill_guard.rr.semantic_learning import H, Y, context, forecasts
from reports.method_redesign_20261109.audit_learning_attribution import (
    factor_fit, factored_forecast,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/method_redesign_20261109'
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109'
RUN = 'M2_discriminating_cash_probe_20261109'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
PROTOCOL = REPORT / 'M2_discriminating_probe_protocol.md'
REVIEW_SCHEMA = obj({
    'frame': FRAME_SCHEMA, 'one_span_edit_preserves_other_local_roles': {'type': 'boolean'},
    'edit_review': {'type': 'string'}, 'local_relation_review': {'type': 'string'},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}},
})


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_marginal(joint):
    values = np.zeros((3, 3))
    for y, p in zip(Y, joint):
        values[y[0], y[1]] += p
    assert np.isclose(values.sum(), 1.) and np.all(values > 0)
    return values.reshape(-1).tolist()


def prepare():
    base = read(OLD / 'seal.json')
    parent = next(c for c in base['cases'] if c['case_id'] == 'TRAIN71:controlled')
    facts, edit = exact_edit(parent['facts'], 'hay', 'cash')
    case = {**parent, 'case_id': 'TRAIN71:discriminating_cash', 'facts': facts,
            'variant': 'post_pilot_discriminating_cash', 'edit': edit}
    assert context(facts) == context(parent['facts']) == [1, 0]
    f = read(OLD / 'frozen_learning.json')
    # The old, already reported same-primitive control uses only these rows.
    assert {r['case_id'].split(':')[0] for r in f['training_rows']} == {'TRAIN71', 'TRAIN79'}
    weights = factor_fit(f['training_rows'])
    conditional = []
    for h in H:
        dist = forecasts(f['models'], h, context(facts))
        dist['factorized_same_grammar'] = factored_forecast(h, weights)
        conditional.append({'h': list(h), 'D_marginal': {
            name: direct_marginal(value) for name, value in dist.items()}})
    # A concrete offline separability check, not a constructed model success.
    assert H.index((0, 0)) == 0
    alternatives = {
        'D_work_reads_payment_class': {'h00_D_work': 0, 'h01_D_work': 1},
        'D_work_negates_work_class': {'h00_D_work': 1, 'h01_D_work': 1},
    }
    assert len({v['h00_D_work'] for v in alternatives.values()}) == 2
    files = [
        'experiments/rr_v2_channel_discriminating_probe.py',
        'experiments/rr_v2_semantic_disambiguation_pilot.py',
        'legal_skill_guard/rr/semantic_frames.py', 'legal_skill_guard/rr/semantic_learning.py',
        'reports/method_redesign_20261109/audit_learning_attribution.py',
        'legal_skill_guard/rr/method_client.py', 'legal_skill_guard/rr/client.py',
        'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/ledger.py',
        'legal_skill_guard/rr/checkpoint.py', 'legal_skill_guard/rr/coverage.py',
        'legal_skill_guard/inference/codex_cli_client.py',
        str(PROTOCOL.relative_to(ROOT)),
    ]
    hashes = {p: sha(ROOT / p) for p in files}
    seal = {'run_id': RUN, 'captured_utc': datetime.now(timezone.utc).isoformat(),
            'files': hashes, 'binding': {'code_hash': digest(hashes), 'config_hash': digest(base['config'])},
            'config': base['config'], 'sources': base['sources'], 'case': case, 'parent_case': parent,
            'protocol_sha256': sha(PROTOCOL), 'original_frozen_learning_sha256': sha(OLD / 'frozen_learning.json'),
            'forecasts': conditional, 'D_order': [list(h) for h in H],
            'competing_explanations': alternatives, 'old_frozen_models_refitted': False,
            'forecast_controls_only_use_original_induction': True, 'new_mothers': 0,
            'native_labels_used': False, 'TEST_started': False, 'goal_complete': False}
    path = STAGE / 'seal.json'
    if path.exists():
        old = read(path)
        # The clock is metadata; scientific contents cannot change on recovery.
        seal['captured_utc'] = old['captured_utc']
    immutable_json(path, seal)
    return seal


def clients(seal):
    for rel, expected in seal['files'].items():
        assert sha(ROOT / rel) == expected, rel
    assert sha(OLD / 'frozen_learning.json') == seal['original_frozen_learning_sha256']
    ledger = MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, binding=seal['binding'], sources=seal['sources'],
        authorization_hash=seal['protocol_sha256'],
        question='Does one existing-TRAIN medium-only edit distinguish the actual D.work role-read versus polarity explanations, and does a frozen structured channel outperform the same-primitive control on the acquired D marginal?')
    return MethodExecutor(ledger, STAGE, seal['config']['executor']), MethodTeacher(ledger, STAGE, seal['config']['teacher'])


def generate(seal):
    path = STAGE / 'executor.json'
    if path.exists():
        print(json.dumps({'existing': str(path)})); return
    e, _ = clients(seal)
    e.readiness()
    case = seal['case']
    wire = e.generate(RUN + ':direct:TRAIN71:cash', source=case['source'], purpose='method_train_synthesis',
        messages=messages(case, 'direct'), schema=FRAME_SCHEMA, thinking=False)
    try:
        decoded = decode_frame(json.loads(wire['content']), case['facts'])
        validation = {'status': 'decoded', 'decoded': decoded}
    except Exception as exc:
        validation = {'status': 'rejected', 'error_type': type(exc).__name__, 'error': str(exc)}
    immutable_json(path, {'physical_response': wire, 'validation': validation,
        'seal_sha256': sha(STAGE / 'seal.json'), 'captured_utc': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'validation': validation}, ensure_ascii=False), flush=True)


def review(seal):
    path = STAGE / 'teacher.json'
    if path.exists():
        print(json.dumps({'existing': str(path)})); return
    response = STAGE / 'executor.json'
    assert response.exists()
    immutable_json(STAGE / 'execution_closed_before_teacher.json', {
        'executor_sha256': sha(response), 'seal_sha256': sha(STAGE / 'seal.json'),
        'captured_utc': read(response)['captured_utc'], 'R_not_acquired_or_imputed': True})
    _, teacher = clients(seal)
    wire = teacher.summarize(RUN + ':review:TRAIN71:cash', source_ids=[seal['case']['source']],
        system_prompt='Independently review this one-span controlled TRAIN edit. Extract the new facts local payer/payee, paid activity, payment material and their separate agricultural classifications. Use exact short source substrings, JSON null when unknown. Check whether other local roles were preserved. Do not solve the native legal question. Do not assume a monetary amount establishes cash; here the actual words must support the material. No executor response or final legal label is supplied.',
        user_prompt=json.dumps({'parent_facts': seal['parent_case']['facts'],
            'new_facts': seal['case']['facts'], 'focus': seal['case']['focus'], 'exact_edit': seal['case']['edit']}, ensure_ascii=False),
        output_schema=REVIEW_SCHEMA)
    try:
        decoded = decode_frame(wire['value']['frame'], seal['case']['facts'])
        validation = {'status': 'decoded', 'decoded': decoded}
    except Exception as exc:
        validation = {'status': 'rejected', 'error': str(exc)}
    immutable_json(path, {'physical_response': wire, 'validation': validation,
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'evidence_level': 'Independent TRAIN teacher local judgment'})
    print(json.dumps(wire['value'], ensure_ascii=False), flush=True)


def evaluate(seal):
    output, teacher = read(STAGE / 'executor.json'), read(STAGE / 'teacher.json')
    closure = read(STAGE / 'execution_closed_before_teacher.json')
    assert closure['executor_sha256'] == sha(STAGE / 'executor.json')
    assert closure['seal_sha256'] == sha(STAGE / 'seal.json')
    assert teacher['validation']['status'] == 'decoded'
    assert teacher['physical_response']['value']['one_span_edit_preserves_other_local_roles']
    truth = frame_vector(teacher['validation']['decoded'])
    raw = json.loads(output['physical_response']['content'])
    observed = frame_vector({'values': raw})
    forecasts_for_h = next(r for r in seal['forecasts'] if r['h'] == truth)['D_marginal']
    scores = {}
    yi = H.index(tuple(observed))
    for name, p in forecasts_for_h.items():
        best = max(p)
        scores[name] = {'observed_probability': p[yi], 'D_pair_NLL': -math.log(p[yi]),
                        'top1_ties': [list(H[i]) for i, x in enumerate(p) if abs(x - best) < 1e-12],
                        'strict_top1_correct': int(abs(p[yi] - best) < 1e-12 and sum(abs(x - best) < 1e-12 for x in p) == 1)}
    compatibility = None
    if truth == [0, 0]:
        compatibility = {name: value['h00_D_work'] == observed[0]
            for name, value in seal['competing_explanations'].items()}
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'case': seal['case'],
        'teacher_h': truth, 'observed_D': observed, 'raw_schema_and_pointer_validation': output['validation'],
        'teacher_value': teacher['physical_response']['value'], 'D_scores': scores,
        'single_output_compatibility_only': compatibility,
        'universal_or_cognitive_operator_identified': False, 'new_model_training': False,
        'original_frozen_models_unchanged': sha(OLD / 'frozen_learning.json') == seal['original_frozen_learning_sha256'],
        'full_span_binding_forecast_claimed': False, 'native_task_success_claimed': False,
        'independent_contribution_established': False, 'goal_complete': False,
        'R_observations_bought_or_imputed': False, 'new_mothers': 0,
        'source_role_evidence': {k: raw[k] == teacher['physical_response']['value']['frame'][k]
            for k in ('payer', 'payee', 'work_activity', 'payment_medium')}}
    immutable_json(STAGE / 'result.json', result)
    immutable_json(REPORT / 'M2_discriminating_probe_results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('case', 'teacher_value', 'raw_schema_and_pointer_validation')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'generate', 'review', 'evaluate'])
    action = p.parse_args().action
    sealed = prepare()
    if action == 'prepare':
        print(json.dumps({'prepared': True, 'new_model_calls': 0, 'separation_checked': True,
            'conditional_forecasts': len(sealed['forecasts']), 'context': context(sealed['case']['facts'])}))
    else:
        globals()[action](sealed)
