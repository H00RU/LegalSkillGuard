"""Refresh committed TRAIN failure evidence from immutable records and a read-only ledger."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files


def physical_evidence(connection, call, call_id):
    row = connection.execute('SELECT status,result FROM calls WHERE id=?', (call_id,)).fetchone()
    assert row is not None, 'Missing physical ledger record: ' + call_id
    status, result_json = row
    assert status == 'completed', 'Committed response has not settled: ' + call_id
    result = json.loads(result_json)
    assert result['content'] == call['raw_content'], 'Response differs from physical ledger: ' + call_id
    assert result['usage'] == call['usage'], 'Usage differs from physical ledger: ' + call_id
    assert result['thinking_requested'] is False, 'Executor thinking is not OFF: ' + call_id
    return {'call_id': call_id, 'status': status, 'finish_reason': result['finish_reason'],
            'usage': result['usage'], 'elapsed_seconds': result['elapsed_seconds'],
            'raw_content_sha256': hashlib.sha256(result['content'].encode()).hexdigest(),
            'thinking_requested': False, 'recorded_analysis': call['analysis'],
            'raw_content_and_usage_match_physical_ledger': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    state = json.loads((stage / 'build/state.json').read_text())
    count = state['complete_sources']
    assert len(state['source_hashes']) == count
    connection = sqlite3.connect('file:' + str((root / seal['ledger_path']).resolve()) + '?mode=ro', uri=True)
    rows, finishes, errors = [], Counter(), Counter()
    with connection:
        for position, source in enumerate(seal['sources']['train'][:count]):
            path = stage / 'build/sources' / (digest(source) + '.json')
            record = json.loads(path.read_text())
            assert record['source'] == source and digest(record) == state['source_hashes'][position]
            prediction = record['prediction']
            outcome = prediction['result']
            paid_calls, source_errors = [], Counter()
            for call in prediction['calls']:
                origin = call['physical_origin_call_id'] if call['cache_hit'] else (
                    args.run_id + ':build:' + digest(source) + ':' + str(call['step']))
                assert origin
                paid = physical_evidence(connection, call, origin)
                paid['logical_step'] = call['step']
                paid['exact_paid_replay'] = call['cache_hit']
                paid_calls.append(paid)
                finishes[paid['finish_reason']] += 1
                error = call['analysis'].get('error') or {}
                if error.get('type'):
                    source_errors[error['type']] += 1
                    errors[error['type']] += 1
            accepted = outcome['program_status'] == 'source_IR_compiled'
            horn_recovery = bool(outcome.get('model_source_IR_still_unresolved'))
            fallback = outcome['fallback_used'] or horn_recovery
            if accepted:
                failure_class = 'accepted_model_IR_requires_corresponding_semantic_review'
            elif paid_calls and all(call['finish_reason'] == 'length' for call in paid_calls):
                failure_class = 'incomplete_model_output_before_IR_execution'
            elif source_errors and set(source_errors) <= {'JSONDecodeError', 'Unsupported'}:
                failure_class = 'rejected_model_output_before_IR_execution'
            else:
                failure_class = 'see_recorded_analysis'
            rows.append({'source': source, 'dataset': record['dataset'], 'source_position': position,
                'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'committed_record_digest': state['source_hashes'][position],
                'model_IR_accepted': accepted, 'A_conditional_certificate': outcome['A_main_path_executed'],
                'raw_B_execution_flag': outcome['B_main_path_executed'],
                'B_primary_model_IR_execution': accepted and outcome['B_main_path_executed'] and not fallback,
                'fallback_used': fallback, 'native_fallback_used': outcome['fallback_used'],
                'controlled_Horn_after_failed_model_IR': horn_recovery,
                'TRAIN_match': record['score']['task_correct'], 'program_status': outcome['program_status'],
                'learning_status': record['learning']['status'], 'model_error_types': dict(source_errors),
                'last_error': outcome.get('error'), 'paid_calls': paid_calls,
                'prediction_failure_classification': failure_class,
                'B_oracle_availability': ('unavailable_under_original_protocol'
                    if record['learning']['status'] == 'no_counterfactual_oracle'
                    else 'original_authorized_training_oracle'),
                'uncharged_source_or_views_added': False})
    connection.close()
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'scientific_code_hash': seal['code_hash'], 'committed_sources': count,
        'planned_sources': len(seal['sources']['train']), 'completed_output_finish_reasons': dict(finishes),
        'model_error_types': dict(errors), 'rows': rows,
        'state_committed_prefix_and_record_digests_verified': True,
        'all_response_content_and_usage_match_read_only_physical_ledger': True,
        'raw_B_execution_does_not_imply_core_success': True,
        'reported_TRAIN_scores_read_from_existing_records_not_regraded': True,
        'new_model_calls_by_audit': 0, 'new_oracle_views': 0, 'grading_packets_opened': False,
        'all_unfinished_sources_remain_unassessed': True,
        'core_success_or_readiness_claimed': False, 'full_goal_complete': False}
    output = Path(__file__).with_name(args.run_id + '_complete_prefix_failure_matrix.json')
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('committed_sources', 'completed_output_finish_reasons',
        'model_error_types', 'new_model_calls_by_audit')}))


if __name__ == '__main__':
    main()
