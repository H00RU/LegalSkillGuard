"""Describe recorded A/B coverage and provenance without generation or grading."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    historical = json.loads((root / 'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B8.frozen.json').read_text())
    assert digest(historical['content']) == historical['sha256']
    historical_hashes = {item['pattern_hash'] for item in historical['content']['patterns']}
    library = SkillLibrary(stage='formal_train')
    rows, acquisitions, uses, separating, followups, exposures = [], [], [], [], [], []
    errors = Counter()
    for position, source in enumerate(seal['sources']['train']):
        path = stage / 'build/sources' / (digest(source) + '.json')
        if not path.exists():
            break
        record = json.loads(path.read_text())
        assert record['source'] == source and record['library_before_hash'] == digest(library.export())
        previous = {item['pattern_hash']: item for item in library.patterns}
        prediction, learning = record['prediction'], record['learning']
        outcome, calls = prediction['result'], prediction['calls']
        assert len(calls) <= 2 and len(learning['oracle_views']) <= 4
        if calls:
            request = json.loads((stage / 'build/journals' / digest(source) / 'request0.json').read_text())
            dispatch = json.loads(request['dispatch_json'])
            menu = json.loads(dispatch['messages'][1]['content'])['available_learned_patterns']
            assert {item['pattern_hash'] for item in menu} == set(previous)
            if menu:
                exposures.append(source)
        for call in calls:
            error = call['analysis'].get('error') or {}
            if isinstance(error, dict) and error.get('type'):
                errors[error['type']] += 1
        for action in prediction['translation_actions']:
            if action.get('kind') in {'factual_observation', 'joint_rule_translation_and_facts'}:
                followups.append({'source': source, 'kind': action['kind'],
                    'selected': action['selected'], 'selection_basis': action['selection_basis'],
                    'input_tokens': action['input_tokens'],
                    'completion_stable_after_response': bool(outcome['A_main_path_executed'])})
                if action['joint_separation_complete']:
                    separating.append(source)
        if outcome['program_status'] == 'source_IR_compiled':
            execution = outcome['assessment'].get('execution') or {}
            path_kind = 'model_source_IR'
        elif outcome['program_status'] == 'controlled_public_grammar':
            execution = outcome['execution']
            path_kind = ('controlled_Horn_after_failed_model_IR' if outcome.get('model_source_IR_still_unresolved')
                         else 'predefined_public_Horn_shortcut')
        else:
            execution, path_kind = {}, 'no_executable_prediction'
        for use in execution.get('pattern_uses', []):
            key = use['pattern_hash']
            assert key in previous
            support = list(previous[key]['evidence_sources'])
            assert use['supporting_training_sources'] == support
            assert set(support) <= set(seal['sources']['train'][:position])
            target_bank = record['dataset']
            support_banks = {item.split(':', 1)[0] for item in support}
            origin = ('foreign_only_stored_use' if target_bank not in support_banks else
                      'same_bank_stored_use' if support_banks == {target_bank} else
                      'shared_origin_stored_use')
            uses.append({'source': source, 'source_position': position, 'path_kind': path_kind,
                'core_primary_model_IR_path': path_kind == 'model_source_IR' and not outcome['fallback_used'],
                'pattern_hash': key, 'first_support_source': support[0],
                'supporting_sources_before_prediction': support,
                'provenance_class': origin, 'query_relevant': use.get('query_relevant', True),
                'execution_status': use['status'], 'TRAIN_match': record['score']['task_correct']})
        learned = learning.get('learned_pattern')
        if learned:
            key = library.add(learned, source=source)
            acquisitions.append({'source': source, 'source_position': position, 'pattern_hash': key,
                'first_acquisition': key not in previous,
                'same_hash_in_preserved_historical_library': key in historical_hashes,
                'same_structure_already_available': key in previous,
                'stored_pattern_was_used_in_prediction': any(use['pattern_hash'] == key for use in execution.get('pattern_uses', [])),
                'primitive_source': learning['primitive_source'], 'status': learning['status'],
                'fields': learned['fields'], 'graphs': learned['graphs'],
                'oracle_views_recorded': len(learning['oracle_views'])})
        rows.append({'source': source, 'source_position': position, 'dataset': record['dataset'],
            'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'program_status': outcome['program_status'], 'path_kind': path_kind,
            'conditional_A_certificate': outcome['A_main_path_executed'],
            'TRAIN_match_including_predefined_paths': record['score']['task_correct'],
            'native_fallback_used': outcome['fallback_used'],
            'controlled_Horn_fallback_used': bool(outcome.get('model_source_IR_still_unresolved')),
            'fallback_used': outcome['fallback_used'] or bool(outcome.get('model_source_IR_still_unresolved')),
            'learning_status': learning['status'],
            'learning_primitive_source': learning['primitive_source'],
            'model_program_candidate_present': prediction['program'] is not None,
            'model_connector_candidates_generated': learning['connector_candidates_generated']
                if learning['primitive_source'] == 'model_source_linked_inputs' else None,
            'model_connector_candidates_fully_checked': learning['connector_candidates_fully_checked']
                if learning['primitive_source'] == 'model_source_linked_inputs' else None,
            'source_program_diagnostic': learning.get('source_program_diagnostic'),
            'recorded_oracle_views': len(learning['oracle_views'])})
    for use in uses:
        assert set(use['supporting_sources_before_prediction']) <= set(seal['sources']['train'][:use['source_position']])
    for batch in range(1, len(rows) // 16 + 1):
        path = stage / 'build/batches' / f'B{batch}.json'
        if path.exists():
            snapshot = json.loads(path.read_text())
            assert snapshot['sources'] == seal['sources']['train'][:batch * 16]
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'prefix_sources_audited': len(rows), 'expected_sources': 128, 'rows': rows,
        'library_prefix_hashes_and_call_view_budgets_verified': True,
        'prediction_support_copied_before_later_library_merges': True,
        'all_final_support_snapshots_precede_prediction': True,
        'model_error_types': dict(errors),
        'effective_learning_inputs': {
            'by_dataset': {bank: {'sources': sum(row['dataset'] == bank for row in rows),
                'learning_status_counts': dict(Counter(row['learning_status'] for row in rows if row['dataset'] == bank)),
                'compiled_model_IR_sources': sum(row['dataset'] == bank and row['program_status'] == 'source_IR_compiled' for row in rows),
                'model_connector_candidate_sources': sum(row['dataset'] == bank and row['learning_primitive_source'] == 'model_source_linked_inputs' and row['model_connector_candidates_generated'] > 0 for row in rows),
                'predefined_Horn_input_sources': sum(row['dataset'] == bank and row['learning_primitive_source'] == 'predefined_public_Horn_grammar_not_new_rule_learning' for row in rows)}
                for bank in sorted({row['dataset'] for row in rows})},
            'primitive_source_label_alone_is_not_evidence_of_available_typed_inputs': True,
            'zero_generated_candidates_is_not_evidence_of_a_tested_connector_failure': True,
            'no_counterfactual_oracle_is_a_learning_data_boundary_separate_from_prediction_errors': True,
            'this_input_audit_adds_no_acceptance_requirement': True},
        'fallback': {'native_sources':sum(row['native_fallback_used'] for row in rows),
            'controlled_Horn_sources':sum(row['controlled_Horn_fallback_used'] for row in rows),
            'all_fallback_sources':sum(row['fallback_used'] for row in rows), 'denominator':len(rows),
            'raw_native_fallback_flag_is_not_total_fallback_coverage':True},
        'A': {'actual_followups': followups, 'separation_complete_request_sources': separating,
              'conditional_certificate_sources': [row['source'] for row in rows if row['conditional_A_certificate']],
              'source_faithfulness_is_not_proved_by_a_certificate_or_label_match': True},
        'B': {'patterns_so_far': library.export()['patterns'], 'acquisitions': acquisitions,
              'prompt_exposure_sources': exposures, 'actual_stored_graph_executions': uses,
              'query_relevant_use_classes': dict(Counter(use['provenance_class'] for use in uses if use['query_relevant'])),
              'core_primary_model_IR_executions':sum(use['core_primary_model_IR_path'] for use in uses),
              'fallback_executions_are_not_core_primary_success':True,
              'shared_origins_are_not_counted_as_foreign_only_transfer': True,
              'same_structure_rediscovery_is_not_counted_as_execution': True,
              'causal_transfer_or_score_gain_not_claimed_from_exposure_or_mixed_training': True},
        'new_model_calls': 0, 'new_oracle_views': 0, 'grading_packets_opened': False,
        'report_is_descriptive_not_an_added_acceptance_gate': True,
        'full_goal_complete': False}
    output = Path(__file__).with_name(args.run_id + '_mechanism_prefix_audit.json')
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'prefix_sources_audited': len(rows), 'patterns': len(library.patterns),
        'actual_stored_graph_executions': len(uses), 'actual_A_followups': len(followups), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
