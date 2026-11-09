"""Offline source review and differential analysis of the fixed pilot."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
from legal_skill_guard.rr.semantic_contracts import compare_modules, evaluate

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109/redesign_rule_modules_v1_20261109'


def main():
    seal = json.loads((STAGE / 'seal.json').read_text())
    for rel, expected in seal['files'].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel
    rows = []
    for target in seal['targets']:
        student = json.loads((STAGE / ('executor_' + target['id'] + '.json')).read_text())
        teacher = json.loads((STAGE / ('teacher_' + target['id'] + '.json')).read_text())
        signature = target['signature']
        domain = 'length > 0 and width > 0 and height > 0' if target['id'] == 'airline_size' else 'income > threshold and threshold >= 0'
        difference = compare_modules(student['module']['expression'], teacher['module']['expression'], signature, domain)
        row = dict(target=target['id'], source=target['source'], comparison=difference,
            student_admission_status_unchanged=student['validation']['status'],
            teacher_admission_status_unchanged=teacher['validation']['status'],
            source_truth_not_proved_by_program_agreement=True, new_method_core_effect=False)
        if target['id'] == 'airline_size':
            assert difference['equivalent_over_supplied_domain']
            assert 'adding the total outside dimensions of each bag, length + width + height' in target['rules']
            row['independent_rule_review'] = 'Both expressions implement the explicit three-dimension sum. The supplied inch units are consistent with the policy, but source quotes alone are not a fidelity proof.'
        else:
            assert 'In no event shall the applicable percentage exceed 100 percent.' in target['rules']
            assert difference['status'] == 'sat'
            binding = dict(income=276932, threshold=250000, married_separate=False)
            row['public_TRAIN18_binding_for_diagnostic_only'] = binding
            row['student_actual_case_value'] = evaluate(student['module']['expression'], signature, binding)
            row['teacher_actual_case_value'] = evaluate(teacher['module']['expression'], signature, binding)
            assert row['student_actual_case_value'] == row['teacher_actual_case_value'] == 22
            row['counterexample_exceeds_source_cap'] = difference['left_value'] > 100 and difference['right_value'] == 100
            assert row['counterexample_exceeds_source_cap']
            # The first SMT witness may use threshold0. For source semantics,
            # also keep the actual TRAIN18 threshold and unmarried status;
            # vary only income. This is a diagnostic, not an oracle-labelled
            # extra source or a native benchmark score.
            source_difference = compare_modules(student['module']['expression'], teacher['module']['expression'],
                signature, 'income > threshold and threshold == 250000 and not married_separate')
            assert source_difference['status'] == 'sat'
            assert source_difference['left_value'] > 100 and source_difference['right_value'] == 100
            row['source_compatible_counterexample_with_original_threshold_and_status'] = source_difference
            row['independent_rule_review'] = 'The teacher has upward rounding, married-separate1250 versus2500 denominator, and100 cap. The student has correct positive-domain rounding and denominator switch but omits the cap and openly lists it unresolved. Its citation is not a verbatim policy span; original rejection remains in force.'
            row['counterexample_is_solver_diagnostic_not_new_source_or_oracle_view'] = True
        rows.append(row)
    with sqlite3.connect('file:' + str((ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve()) + '?mode=ro', uri=True) as db:
        calls = [dict(zip([r[1] for r in db.execute('pragma table_info(calls)')], r)) for r in db.execute("select * from calls where id like 'redesign_rule_modules_v1_20261109:%' order by reserved_at")]
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    result = dict(captured_utc=datetime.now(timezone.utc).isoformat(), question='Does the compact representation carry genuine source semantics, and can one-case correctness hide a reusable-rule defect?',
        rows=rows, four_actual_generations=len(calls), total_ledger=counts, pending=pending,
        source_fidelity_review_scope='Only the requested size/percentage definitions, not complete original tasks or all statutory clauses',
        role_signatures_supplied_not_learned=True, sources_or_seeds_added=False,
        calls_or_oracle_views_added_by_analysis=0, evidence_level='real_generation_capacity_control_plus_offline_counterexample; not method efficacy',
        goal_complete=False)
    (REPORT / 'module_pilot_analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (REPORT / 'request_ledger_delta.json').write_text(json.dumps(dict(calls=calls, counts_total=counts, pending=pending, original_ledger_reset=False), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
