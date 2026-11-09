"""Infer a patch from the real stored student/teacher pair, without calls."""
from pathlib import Path
import json
from legal_skill_guard.rr.contract_repair import infer_postcomposition

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109/redesign_rule_modules_v1_20261109'


def main():
    seal = json.loads((STAGE / 'seal.json').read_text())
    target = next(t for t in seal['targets'] if t['id'] == 'sara_percentage')
    student = json.loads((STAGE / 'executor_sara_percentage.json').read_text())
    teacher = json.loads((STAGE / 'teacher_sara_percentage.json').read_text())
    result = infer_postcomposition(student['module']['expression'], teacher['module']['expression'],
        target['signature'], 'income > threshold and threshold >= 0', target['rules'])
    assert result['status'] == 'verified_postcomposition_found'
    assert result['selected']['operator'] == 'min' and result['selected']['source_literal'] == 100
    result.update(source=target['source'], candidate_from_actual_paid_response=True,
        reference_from_actual_paid_response=True, native_labels_used=False,
        original_student_rejection_or_unresolved_fields_not_rewritten=True,
        patch_not_admitted_to_live_library=True, measured_method_efficacy=False,
        current_missing_component='Learn source-role/scope applicability and show real subsequent reuse against correct reference-program caching and ordinary targeted repair',
        goal_complete=False, new_model_or_oracle_calls=0)
    path = Path(__file__).with_name('repair_prototype_analysis.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'attempts'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
