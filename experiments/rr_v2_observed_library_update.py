"""Use the paid partial TRAIN trajectory without acquiring or inventing R."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.observed_reader_learning import fit_observed_channels, observed_forecasts
from legal_skill_guard.rr.semantic_frames import frame_vector
from legal_skill_guard.rr.semantic_learning import H, OPS, context
from legal_skill_guard.rr.source_discrimination import (
    compile_discrimination, execute_paths, execute_selector, learn_evidence_paths,
    learn_selector, plan_questions,
)
from reports.method_redesign_20261109.evaluate_source_bound_program import training_examples

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/method_redesign_20261109'
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109'
PROBE = ROOT / 'artifacts/rr_method_redesign_20261109/M2_discriminating_cash_probe_20261109'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109/observed_library_update_v1_20261109'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_snapshot():
    path = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(path.resolve()) + '?mode=ro', uri=True) as db:
        db.execute('begin')
        rows = db.execute('select * from calls order by reserved_at,id').fetchall()
        meta = db.execute('select * from meta order by key').fetchall()
        oracle = db.execute('select * from oracle_views order by source,view_hash').fetchall()
    return {'calls': len(rows), 'counts_total': dict(Counter(r[1] for r in rows)),
        'pending': sum(r[6] == 'reserved' for r in rows),
        'logical_sha256': digest({'calls': rows, 'meta': meta, 'oracle': oracle})}


def operator_mass(model, c):
    mix = model['structured']['contexts'].get(''.join(map(str, c)), model['structured']['global'])
    return {name: sum(p for op, p in zip(OPS, mix) if op[0] == name)
            for name in ('self', 'other', 'negate_self')}


def main():
    before = ledger_snapshot()
    assert before['pending'] == 0
    frozen = read(OLD / 'frozen_learning.json'); acquisition = read(OLD / 'seal.json')
    probe_seal = read(PROBE / 'seal.json'); response = read(PROBE / 'executor.json')
    teacher = read(PROBE / 'teacher.json')
    assert response['validation']['status'] == teacher['validation']['status'] == 'decoded'
    case = probe_seal['case']; assert case['fold'] == 'induction'
    truth = teacher['physical_response']['value']['frame']
    assert teacher['physical_response']['value']['one_span_edit_preserves_other_local_roles']
    actual = frame_vector(response['validation']['decoded'])
    examples = training_examples()
    originals = frozen['training_rows']
    assert {e['mother'] for e in examples} == {r['mother'] for r in originals}
    assert case['source'] in {r['mother'] for r in originals}
    partial = {'case_id': case['case_id'], 'mother': case['source'],
               'h': frame_vector({'values': truth}), 'y': actual + [None, None],
               'context': context(case['facts'])}
    rows = [{**r} for r in originals] + [partial]
    counts = Counter(r['mother'] for r in rows)
    for r in rows:
        r['weight'] = 1. / counts[r['mother']]
    assert all(abs(sum(r['weight'] for r in rows if r['mother'] == m) - 1.) < 1e-12 for m in counts)
    models = fit_observed_channels(rows)
    # This attribution removes only the new observation, holding old-row weights.
    reweighted_old = fit_observed_channels(rows[:-1])
    updated_examples = examples + [{'case_id': case['case_id'], 'mother': case['source'],
                                   'facts': case['facts'], 'frame': truth}]
    original_role = learn_selector(examples)
    updated_role = learn_selector(updated_examples)
    paths = learn_evidence_paths(updated_examples, contrast=False)
    old_cash = execute_selector(original_role, case['facts'], case['focus'])
    new_cash = execute_selector(updated_role, case['facts'], case['focus'])
    source_prediction = execute_paths(paths, new_cash['candidates'])
    assert old_cash['prediction'] == [0, 2] and source_prediction == partial['h'] == [0, 0]
    assert any(all(candidate['values'][name] == truth[name] for name in ('payer', 'payee', 'work_activity', 'payment_medium'))
               for candidate in new_cash['candidates'])
    input_paths = [OLD / 'frozen_learning.json', OLD / 'seal.json', PROBE / 'seal.json',
                   PROBE / 'executor.json', PROBE / 'teacher.json']
    files = ['experiments/rr_v2_observed_library_update.py', 'legal_skill_guard/rr/observed_reader_learning.py',
             'legal_skill_guard/rr/semantic_learning.py', 'legal_skill_guard/rr/source_discrimination.py',
             'legal_skill_guard/rr/semantic_frames.py', 'tests/test_rr_observed_reader_learning.py',
             'reports/method_redesign_20261109/observed_update_protocol.md']
    hashes = {p: sha(ROOT / p) for p in files}
    seal = {'run_id': STAGE.name, 'files': hashes, 'config': acquisition['config'],
            'sources': acquisition['sources'], 'training_mothers': sorted(counts),
            'input_hashes': {str(p.relative_to(ROOT)): sha(p) for p in input_paths},
            'new_physical_requests': 0, 'TEST_authorized': False, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal)
    library = {'version': STAGE.name, 'inputs': seal['input_hashes'], 'training_rows': rows,
               'channels': models, 'source_role_selector': updated_role, 'source_role_paths': paths,
               'question_actions_not_extended_or_validated': True, 'native_legal_program_learned': False,
               'whole_binding_error_channel_learned': False, 'goal_complete': False}
    immutable_json(STAGE / 'library.json', library)
    loaded = read(STAGE / 'library.json')
    for h in H:
        assert observed_forecasts(loaded['channels'], h, partial['context']) == observed_forecasts(models, h, partial['context'])
    assert execute_paths(loaded['source_role_paths'], execute_selector(loaded['source_role_selector'], case['facts'], case['focus'])['candidates']) == source_prediction
    # No teacher grades are needed to audit the actual question opportunities.
    skill = compile_discrimination(examples)
    query_rows = []
    for c in acquisition['cases'] + [case]:
        candidates = execute_selector(skill['selector'], c['facts'], c['focus'])['candidates']
        plan = plan_questions(skill, candidates, c['focus'])
        query_rows.append({'case_id': c['case_id'], 'candidate_count': len(candidates),
                           'planned_actions': len(plan['actions']), 'planner_status': plan['status']})
    after = ledger_snapshot(); assert before == after
    receipt = {'captured_utc': datetime.now(timezone.utc).isoformat(),
        'new_model_calls': 0, 'ledger_before': before, 'ledger_after': after, 'new_mothers': 0,
        'source_weight_totals': {m: sum(r['weight'] for r in rows if r['mother'] == m) for m in counts},
        'actual_observed_slots': models['observed_slots'], 'unasked_slots': models['unobserved_slots'],
        'original_frozen_model_unchanged': sha(OLD / 'frozen_learning.json') == probe_seal['original_frozen_learning_sha256'],
        'library_sha256': sha(STAGE / 'library.json'), 'save_reload_all_h_exact': True,
        'new_cash_source_classification_before': old_cash['prediction'],
        'new_cash_source_classification_after': source_prediction,
        'TRAIN_replay_not_generalization': True,
        'D_work_operator_mass': {'original_frozen': operator_mass(frozen['models'], partial['context']),
             'old_rows_reweighted_only': operator_mass(reweighted_old, partial['context']),
             'with_actual_partial_cash_observation': operator_mass(models, partial['context'])},
        'query_action_opportunity_audit': query_rows,
        'learned_question_templates': len(skill['question_actions']),
        'original_question_answers_remain_unobserved': True,
        'new_performance_or_unique_contribution_claim': False, 'full_build_started': False,
        'two_contributions_established': False, 'goal_complete': False}
    immutable_json(STAGE / 'receipt.json', receipt)
    immutable_json(REPORT / 'observed_library_update_results.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
