"""Describe actual compiler output prefixes; never reconstruct or alter an IR."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.raw_recovery import _unique_object


GROUPS = {'bindings', 'observations', 'rule_residuals', 'nodes', 'scopes', 'clauses'}


def complete_values(content):
    """Read complete values only, using the production prefix diagnostic rules."""
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object)
    records, fields, complete_fields, pos = [], [], [], 0

    def ws(at):
        while at < len(content) and content[at] in ' \t\r\n':
            at += 1
        return at

    pos = ws(pos)
    if content[pos:pos + 1] != '{':
        return records, complete_fields, None
    pos += 1
    while True:
        try:
            key, end = decoder.raw_decode(content, ws(pos))
        except (ValueError, TypeError):
            return records, complete_fields, None
        if not isinstance(key, str) or key in fields:
            return records, complete_fields, None
        pos = ws(end)
        if content[pos:pos + 1] != ':':
            return records, complete_fields, None
        pos = ws(pos + 1)
        fields.append(key)
        try:
            value, end = decoder.raw_decode(content, pos)
        except (ValueError, TypeError):
            if key in GROUPS and key != 'scopes' and content[pos:pos + 1] == '[':
                at = pos + 1
                while True:
                    try:
                        row, end = decoder.raw_decode(content, ws(at))
                    except (ValueError, TypeError):
                        break
                    records.append((key, row))
                    at = ws(end)
                    if content[at:at + 1] != ',':
                        break
                    at += 1
            return records, complete_fields, key
        complete_fields.append(key)
        if key == 'scopes' and isinstance(value, dict):
            records.extend((key, row) for row in value.values() if row is not None)
        elif key in GROUPS and isinstance(value, list):
            records.extend((key, row) for row in value)
        pos = ws(end)
        if content[pos:pos + 1] != ',':
            return records, complete_fields, None
        pos += 1


def repetitions(values):
    counts = Counter(digest(value) for value in values)
    return {'complete_values': len(values), 'unique_exact_JSON_values': len(counts),
            'duplicate_excess': sum(n - 1 for n in counts.values()),
            'largest_exact_value_multiplicity': max(counts.values(), default=0),
            'repeated_value_hashes': {key: n for key, n in counts.items() if n > 1}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    conn = sqlite3.connect('file:' + str(Path(seal['ledger_path']).resolve()) + '?mode=ro', uri=True)
    rows, source_count = [], 0
    for source in seal['sources']['train']:
        path = stage / 'build/sources' / (digest(source) + '.json')
        if not path.exists():
            break
        record = json.loads(path.read_text())
        assert record['source'] == source
        source_count += 1
        for call in record['prediction']['calls']:
            assert call['cache_hit'] is False and call['physical_origin_call_id'] is None
            call_id = f"{args.run_id}:build:{digest(source)}:{call['step']}"
            status, value = conn.execute('SELECT status,result FROM calls WHERE id=?', (call_id,)).fetchone()
            result = json.loads(value)
            assert status == 'completed' and result['content'] == call['raw_content']
            content = call['raw_content']
            records, complete_fields, truncated_field = complete_values(content)
            error = call['analysis'].get('error') or {}
            prefix = error.get('complete_prefix_diagnosis') or {}
            if 'complete_declaration_count' in prefix:
                assert len(records) == prefix['complete_declaration_count']
            nodes = [row['body'] for group, row in records if group == 'nodes'
                     and isinstance(row, dict) and row.get('kind') == 'expression' and 'body' in row]
            bindings = [row['value'] for group, row in records if group == 'bindings'
                        and isinstance(row, dict) and 'value' in row]
            names = Counter(row['name'] for _, row in records
                            if isinstance(row, dict) and isinstance(row.get('name'), str))
            rows.append({'source': source, 'dataset': record['dataset'], 'call_id': call_id,
                         'source_record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'response_sha256': hashlib.sha256(content.encode()).hexdigest(),
                         'finish_reason': result['finish_reason'], 'usage': result['usage'],
                         'complete_root_fields': complete_fields, 'first_incomplete_value_field': truncated_field,
                         'complete_declarations_by_group': dict(Counter(group for group, _ in records)),
                         'duplicate_declaration_name_excess': sum(n - 1 for n in names.values()),
                         'expression_node_bodies': repetitions(nodes), 'binding_values': repetitions(bindings),
                         'recorded_compiler_error_type': error.get('type'),
                         'accepted_model_IR': call['analysis'].get('program_status') == 'source_IR_compiled'})
    conn.close()
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
              'committed_sources': source_count, 'settled_responses': len(rows),
              'finish_reasons': dict(Counter(row['finish_reason'] for row in rows)),
              'length_first_incomplete_fields': dict(Counter(row['first_incomplete_value_field']
                  for row in rows if row['finish_reason'] == 'length')),
              'responses_with_exact_repeated_node_bodies': sum(row['expression_node_bodies']['duplicate_excess'] > 0 for row in rows),
              'rows': rows, 'prefix_only': True, 'candidate_reconstructed_or_modified': False,
              'repetition_does_not_imply_semantic_equivalence_or_redundancy': True,
              'this_is_not_a_request_to_increase_output_limit_or_change_the_protocol': True,
              'new_model_or_oracle_calls': 0, 'grading_packets_opened': False,
              'full_goal_complete': False}
    output = Path(__file__).with_name(args.run_id + f'_first{source_count}_truncation_prefix_audit.json')
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ['committed_sources', 'settled_responses',
        'length_first_incomplete_fields', 'responses_with_exact_repeated_node_bodies', 'new_model_or_oracle_calls']}))


if __name__ == '__main__':
    main()
