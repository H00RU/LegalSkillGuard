"""Check fixed DEV model programs against public source; never generate or grade."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.model_horn import parse_model_horn, assess_model_horn
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.source_program import compile_source, accept_observations, source_theory
from legal_skill_guard.rr.preflight import science_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    stage = ROOT / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(ROOT) == seal['files']
    expected = seal['sources']['dev']
    for arm in ARMS:
        assert {p.stem for p in (stage / 'dev/predictions' / arm).glob('*.json')} == {digest(s) for s in expected}
    scores = json.loads((stage / 'dev/scores.json').read_text())
    assert scores['DEV_complete']
    public = {s['key']: s for s in json.loads((ROOT / 'data/packets/rr_v2/public_dev.json').read_text())['sources']}
    library = SkillLibrary.restore(stage / 'build/B8.frozen.json').export()
    reviewed_path = Path(__file__).with_name('reference_v26_sparse_execution_and_M10_legal_source_review_after.json')
    reviewed = json.loads(reviewed_path.read_text())
    legal = {r['source']: r for r in reviewed['rows']}
    prior = ROOT / 'artifacts/rr_method_runtime_20261107' / reviewed['original_run_id']
    rows = []
    for arm, profile in ARMS.items():
        active = library if profile.interface == 'collision_refined' else {'patterns': []}
        for source_id in expected:
            path = stage / 'dev/predictions' / arm / (digest(source_id) + '.json')
            pred = json.loads(path.read_text())['prediction']
            result = pred['result']
            fallback = bool(result.get('fallback_used') or result.get('model_source_IR_still_unresolved'))
            row = {'arm': arm, 'source': source_id, 'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'program_status': result['program_status'], 'certificate_status': result['certificate_status'],
                'formal_A': result['A_main_path_executed'], 'formal_B': result['B_main_path_executed'],
                'fallback': fallback, 'DEV_match_after_all_predictions_fixed': scores['source_scores'][arm][source_id]['task_correct']}
            if fallback:
                row['classification'] = 'allowed_fallback_noncore'
            elif result['certificate_status'] != 'completion_stable':
                row['classification'] = 'no_stable_main_result'
            elif result['program_status'] == 'model_Horn_IR_compiled':
                program = parse_model_horn(public[source_id], pred['model_horn_code'])
                assert not program.export()['missing_units']
                assessment = assess_model_horn(program, active, interface=profile.interface)
                assert assessment['answer'] == result['answer'] and assessment['certificate_status'] == result['certificate_status']
                row.update(classification='whole_source_model_formulas_checked_and_executed',
                    exact_fact_rule_query_units_checked=True, current_answer=assessment['answer'],
                    model_code_sha256=hashlib.sha256(pred['model_horn_code'].encode()).hexdigest())
            elif result['program_status'] == 'source_IR_compiled' and source_id in legal:
                review = legal[source_id]
                old = json.loads((prior / 'dev/predictions/M10' / (digest(source_id) + '.json')).read_text())['prediction']
                if pred['program'] != old['program'] or pred['observation_rows'] != old['observation_rows']:
                    row['classification'] = 'changed_legal_program_requires_source_review'
                else:
                    assert public[source_id]['public']['facts'] == review['public_facts']
                    assert public[source_id]['public']['query'] == review['public_query']
                    compiled = compile_source(public[source_id], pred['program'], library=active)
                    observed = accept_observations(compiled, [r['name'] for r in pred['observation_rows']],
                        {'observations': pred['observation_rows']})
                    actual = assess_source(compiled, observed, compilation=profile.compilation)
                    assert actual['answer'] == result['answer'] and actual['status'] == result['certificate_status']
                    unresolved_name = review['unsupported_observation']
                    observed.pop(unresolved_name)
                    theory = source_theory(compiled, observed)
                    control = assess_source(compiled, observed, compilation=profile.compilation)
                    assert unresolved_name not in theory.facts and theory.domains[unresolved_name] == (False, True)
                    assert control['status'] == review['offline_unknown_domain_control']['status']
                    assert control['answer'] == review['offline_unknown_domain_control']['answer']
                    if control['execution'] is not None:
                        sparse_execution = compiled['query'].execute(theory.facts, return_environment=True)
                        assert unresolved_name not in sparse_execution['environment']
                    row.update(classification=review['classification'], unsupported_observation=unresolved_name,
                        full_observation_faithfulness_pass=False, public_source_review_reused_for_identical_program_and_observations=True,
                        query_stable_after_unsupported_observation_restored_unknown=control['status'] == 'completion_stable',
                        offline_unknown_control={'status': control['status'], 'answer': control['answer'],
                            'unknown_domain_count': len(theory.domains)}, review_sha256=hashlib.sha256(reviewed_path.read_bytes()).hexdigest(),
                        original_prediction_unchanged=True)
            else:
                row['classification'] = 'other_main_result_requires_public_source_review'
            rows.append(row)
    value = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'all240_original_DEV_predictions_fixed_before_score_read': True,
        'by_arm': {arm: dict(Counter(r['classification'] for r in rows if r['arm'] == arm)) for arm in ARMS},
        'rows': rows, 'source_semantics_not_inferred_from_native_label_or_formal_flags': True,
        'offline_controls_not_new_model_successes_or_research_sources': True,
        'original_predictions_observations_and_scores_not_modified': True,
        'private_DEV_or_TEST_labels_opened_by_this_audit': False, 'new_model_or_oracle_calls': 0,
        'full_goal_complete': False}
    out = Path(__file__).with_name('reference_' + args.run_id + '_DEV_source_semantics.json')
    out.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'run_id': args.run_id, 'by_arm': value['by_arm']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
