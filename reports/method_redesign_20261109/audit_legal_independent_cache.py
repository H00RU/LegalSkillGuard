"""Check the real independent acquisition, source-check correction and ledger.

No model dispatches or fresh grading labels are available in this audit.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT/'reports/method_redesign_20261109'
BASE = ROOT/'artifacts/rr_method_redesign_20261109'
FIRST = BASE/'legal_independent_cache_v1_20261110'
REVIEW = BASE/'legal_independent_cache_review_v1_20261110'
BEFORE = Path('/media/sangfor/vdb/legal-skill-backups/legal_percentage_reuse_20261110/ledger.after.sqlite3')
DB = ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def read(path): return json.loads(path.read_text())


def snapshot(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro', uri=True) as db:
        return {t: db.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}


def main():
    before = snapshot(BEFORE); current = snapshot(DB); historic = deepcopy(current)
    names = ['legal_independent_cache_v1_20261110', 'legal_independent_cache_review_v1_20261110']
    historic['calls'] = [r for r in historic['calls'] if not any(r[0].startswith(n+':') for n in names)]
    historic['meta'] = [r for r in historic['meta'] if r[0] not in ['method_runtime_policy:'+n for n in names]]
    assert historic == before and len(current['calls']) == len(before['calls'])+2
    first = read(FIRST/'source.json'); review = read(REVIEW/'review.json')
    executed = read(REVIEW/'execution_closed_before_grading.json')
    application = read(REVIEW/'review_application.json')
    assert application['no_manual_rule_or_answer_changes']
    assert hashlib.sha256((REVIEW/'reviewed_cache.py').read_bytes()).hexdigest() == executed['reviewed_code_sha256']
    checks = deepcopy(executed['software_source_checks'])
    failed = [r for r in checks['rows'] if not r['passed']]
    assert [r['name'] for r in failed] == ['role_reversal_not_inferred']
    row = failed[0]; assert row['actual'] == 'Contradiction' and row['execution']['query_refuted']
    witnesses = row['execution']['rule_witnesses']
    assert any(w['head'] == ['dependent',['P','Q','2015'],True] for w in witnesses)
    assert any(w['head'] == ['section_152_b_1_applies',['P','Q','2015'],True] for w in witnesses)
    assert any(w['head'] == ['section_151_c_applies',['Q','P','2015'],False] for w in witnesses)
    quote = 'such individual shall be treated as having no dependents for any taxable year of such individual beginning in such calendar year.'
    assert any(quote in p['rules'] for p in read(REVIEW/'seal.json')['policies'])
    row['allowed_answers'] = [None, 'Contradiction']; row['passed'] = True
    correction = {
        'original_frozen_execution_sha256': hashlib.sha256((REVIEW/'execution_closed_before_grading.json').read_bytes()).hexdigest(),
        'name': row['name'], 'original_allowed_answers': [None], 'correct_allowed_answers': [None,'Contradiction'],
        'actual_answer_and_code_unchanged': True, 'source_quote': quote,
        'reason': 'Qualifying_child(P,Q) makes Q a dependent of P;152(b)(1) then bars Q from claiming any dependent, including P. A correct explicit negative must be permitted; a conservative unknown remains permitted.',
        'source_supported_actual_proof_witnesses': [w for w in witnesses if w['head'] in [
            ['dependent',['P','Q','2015'],True], ['section_152_b_1_applies',['P','Q','2015'],True],
            ['section_151_c_applies',['Q','P','2015'],False]]],
        'classification': 'test_expected_outcome_error_not_model_error',
        'other_seven_expectations_and_all_actual_outputs_unchanged': True,
        'new_model_calls': 0, 'goal_complete': False}
    checks['all_passed'] = all(r['passed'] for r in checks['rows']); assert checks['all_passed']
    immutable_json(REVIEW/'source_check_interpretation_correction.json', correction)
    immutable_json(REVIEW/'source_checks_corrected.json', checks)
    grades = read(REPORT/'legal_native_pilot_grades.json')
    prior = {g['ordinal']: g for g in grades['cases']}; native = []
    for result in executed['native_results']:
        assert result['executed']
        old = prior[result['ordinal']]; prediction = result['output']['answer']
        native.append({'ordinal': result['ordinal'], 'source': old['source'], 'prediction': prediction,
            'cached_TRAIN_grade': old['original_TRAIN_grade'], 'correct': prediction == old['original_TRAIN_grade'],
            'candidate_prediction': old['pipeline'], 'same_as_candidate': prediction == old['pipeline'],
            'fallback_invocations': 0, 'core_answered': prediction is not None})
    assert all(r['same_as_candidate'] for r in native) and sum(r['correct'] for r in native) == 3
    wires = [first['physical_response'], review['physical_response']]
    assert all(w['invocation']['tool_events_detected'] is False for w in wires)
    assert all(w['invocation']['attempt'] == 1 for w in wires)
    original = read(BASE/'legal_library_runtime_v1_20261109/frozen_library.json')['program']
    source_prompt = read(FIRST/'seal.json')['teacher_messages']['user']
    for rule in original['rules']:
        assert rule['id'] not in source_prompt
    for person in ('Alice','Bob','Charlie','Dan'):
        assert person not in source_prompt
    preserved = {}
    for stage in (FIRST, REVIEW):
        seal = read(stage/'seal.json')
        for relative, want in seal['files'].items():
            path = stage/'frozen_source'/relative
            blob = (ROOT/relative).read_bytes() if not path.exists() else path.read_bytes()
            assert hashlib.sha256(blob).hexdigest() == want, relative
            if not path.exists(): path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(blob)
            preserved[str(path.relative_to(ROOT))] = want
    with sqlite3.connect('file:'+str(DB)+'?mode=ro', uri=True) as db:
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    assert counts == {'executor':1377,'teacher':62} and pending == 0
    out = {
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'counts_total': counts, 'pending': pending,
        'new_charged_attempts': {'executor':0,'teacher':2}, 'new_physical_dispatches': {'executor':0,'teacher':2},
        'new_oracle_views': 0, 'oracle_views_total': len(current['oracle_views']),
        'all_pre_turn_rows_equal_backup': True, 'all_pre_turn_rows_preserved_sha256': digest(historic),
        'current_full_ledger_logical_sha256': digest(current), 'bound_source_copies': preserved,
        'teacher_input_tokens': sum(w['invocation']['usage']['input_tokens'] for w in wires),
        'teacher_output_tokens': sum(w['invocation']['usage']['output_tokens'] for w in wires),
        'teacher_reasoning_tokens_subset_of_output': sum(w['invocation']['usage']['reasoning_output_tokens'] for w in wires),
        'teacher_request_elapsed_seconds': sum(w['elapsed_seconds'] for w in wires),
        'teacher_actual_cash_invoice_usd': None, 'GPU_cost_usd': None, 'total_project_cash_cost_usd': None,
        'executor_incremental_API_cash_usd': 0, 'source_rule_bodies_not_copied_from_candidate': True,
        'ordinary_cache_chose_public_solver': True, 'provided_shared_learned_API': True,
        'API_discovery_not_tested': True, 'source63_excerpt_extra_available_information': True,
        'matched_initial_source_prompt_or_causal_architecture_comparison': False,
        'first_response_type_and_source_issues_retained': True,
        'first_response_152_b_1_effect_missing': True,
        'review_rule_updates': len(application['updated_ids']), 'review_added_rules': len(application['added_ids']),
        'review_semantic_source_checks_original_passed': False, 'corrected_source_checks_passed': True,
        'source_check_expectation_correction': correction['classification'],
        'native_results': native, 'native_correct': 3, 'native_n': 4, 'core_answered': 3,
        'unresolved': [{'ordinal':87,'reason':'Unbounded claimant projection is not refuted by one explicit negative deduction witness.'}],
        'fallback_invocations': 0, 'same_native_outputs_as_candidate': True,
        'new_unique_rule_execution_advantage_established': False,
        'new_total_acquisition_cost_advantage_established': False,
        'baseline_is_conditional_independent_rule_acquisition_not_an_identical_program_clone': True,
        'old_four_local_targets_18_8_85_76_unchanged': True,
        'TEST_started': False, 'main_training_started': False, 'new_full_build_started': False,
        'goal_complete': False, 'two_contributions_established': False}
    immutable_json(REPORT/'legal_independent_cache_results.json', out)
    backup = Path('/media/sangfor/vdb/legal-skill-backups/legal_independent_cache_20261110'); backup.mkdir(parents=True,exist_ok=True)
    dest = backup/'ledger.after.sqlite3'
    if not dest.exists():
        with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as src:
            with sqlite3.connect(dest) as dst: src.backup(dst)
    assert snapshot(dest) == current
    print(json.dumps({k:out[k] for k in ('counts_total','pending','native_correct','native_n','core_answered',
          'corrected_source_checks_passed','teacher_input_tokens','teacher_output_tokens','teacher_request_elapsed_seconds',
          'all_pre_turn_rows_equal_backup')}, ensure_ascii=False))


if __name__ == '__main__': main()
