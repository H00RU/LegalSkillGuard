"""Check a necessary condition for punctuation-only recovery of saved responses.

Uses the existing strict prefix reader and the actual sent schema. No failed
model response is completed, compiled, scored, or changed by this report.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.raw_recovery import _unique_object


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    root = folder.parents[1]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    state = json.loads((stage / 'build/state.json').read_text())
    matrix = json.loads((folder / (args.run_id + '_complete_prefix_failure_matrix.json')).read_text())
    count = matrix['committed_sources']
    assert count <= state['complete_sources'] and len(matrix['rows']) == count
    module_path = folder / 'audit_truncation_prefixes.py'
    spec = importlib.util.spec_from_file_location('saved_prefix_reader', module_path)
    prefix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prefix)
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object)
    connection = sqlite3.connect('file:' + str((root / seal['ledger_path']).resolve()) + '?mode=ro', uri=True)
    rows, controls, required = [], [], None
    try:
        for position, source in enumerate(seal['sources']['train'][:count]):
            path = stage / 'build/sources' / (digest(source) + '.json')
            record = json.loads(path.read_text())
            expected = matrix['rows'][position]
            assert record['source'] == expected['source'] == source
            assert digest(record) == state['source_hashes'][position] == expected['committed_record_digest']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['record_sha256']
            assert len(record['prediction']['calls']) == len(expected['paid_calls'])
            for call, paid in zip(record['prediction']['calls'], expected['paid_calls']):
                status, encoded = connection.execute('select status,result from calls where id=?', (paid['call_id'],)).fetchone()
                physical = json.loads(encoded)
                assert status == 'completed' and physical['content'] == call['raw_content']
                assert physical['usage'] == call['usage'] and physical['thinking_requested'] is False
                request = json.loads((stage / 'build/journals' / digest(source) / ('request' + str(call['step']) + '.json')).read_text())
                dispatch = json.loads(request['dispatch_json'])
                fields = set(dispatch['schema']['required'])
                if required is None:
                    required = fields
                assert fields == required
                content = call['raw_content']
                _, complete, unfinished = prefix.complete_values(content)
                missing = sorted(required - set(complete))
                rows.append({'source_position': position + 1, 'source': source,
                    'call_id': paid['call_id'], 'finish_reason': physical['finish_reason'],
                    'raw_content_sha256': hashlib.sha256(content.encode()).hexdigest(),
                    'complete_root_fields': complete, 'first_incomplete_value_field': unfinished,
                    'missing_complete_required_root_values': missing,
                    'punctuation_only_recovery_necessary_condition_met': not missing})
                if physical['finish_reason'] == 'stop':
                    original = decoder.decode(content)
                    assert set(original) == required and content.rstrip().endswith('}')
                    shortened = content.rstrip()[:-1]
                    assert set(prefix.complete_values(shortened)[1]) == required
                    try:
                        decoder.decode(shortened)
                    except json.JSONDecodeError:
                        pass
                    else:
                        raise AssertionError('Outer-brace control remained complete JSON')
                    assert decoder.decode(shortened + '}') == original
                    no_query = {k: v for k, v in original.items() if k != 'query'}
                    assert 'query' not in prefix.complete_values(json.dumps(no_query)[:-1])[1]
                    controls.append({'original_response_sha256': rows[-1]['raw_content_sha256'],
                        'complete_values_detected_after_removing_only_outer_brace': True,
                        'restoring_that_brace_preserves_original_decoded_values': True,
                        'missing_query_is_not_recovered': True,
                        'syntactic_control_only_not_a_semantic_pass': True})
    finally:
        connection.close()
    truncated = [row for row in rows if row['finish_reason'] == 'length']
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'audited_committed_sources': count, 'settled_responses_verified': len(rows),
        'scope': 'previously verified committed prefix; raw content and usage rechecked against read-only ledger',
        'required_root_fields_from_actual_sent_schemas': sorted(required),
        'prefix_reader_path': str(module_path.relative_to(root)),
        'prefix_reader_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest(),
        'finish_reasons': dict(Counter(row['finish_reason'] for row in rows)),
        'length_first_incomplete_fields': dict(Counter(row['first_incomplete_value_field'] for row in truncated)),
        'length_responses_missing_complete_query': sum('query' in row['missing_complete_required_root_values'] for row in truncated),
        'length_responses_with_all_required_root_values_complete': sum(row['punctuation_only_recovery_necessary_condition_met'] for row in truncated),
        'complete_field_presence_is_necessary_not_sufficient_for_recovery': True,
        'real_complete_response_syntactic_controls': controls, 'rows': rows,
        'actual_model_responses_closed_compiled_or_scored_by_audit': False,
        'missing_rules_queries_values_or_source_links_inferred': False,
        'original_responses_and_ledger_modified': False,
        'new_model_or_oracle_or_grading_calls': 0, 'grading_packets_opened': False,
        'this_report_adds_no_method_acceptance_requirement': True,
        'core_success_or_readiness_claimed': False, 'full_goal_complete': False}
    output = folder / (args.run_id + '_first' + str(count) + '_required_root_values_audit.json')
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    assert science_files(root) == seal['files']
    print(json.dumps({key: result[key] for key in ('audited_committed_sources', 'settled_responses_verified',
        'finish_reasons', 'length_first_incomplete_fields', 'length_responses_missing_complete_query',
        'length_responses_with_all_required_root_values_complete', 'new_model_or_oracle_or_grading_calls')}))


if __name__ == '__main__':
    main()
