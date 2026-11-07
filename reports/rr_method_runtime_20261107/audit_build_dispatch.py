"""Compare actual HTTP bodies with saved dispatch and original public inputs."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_program import compiler_prompt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    manifest = json.loads((root / seal['source_manifest']).read_text())
    packet_path = root / 'data/packets/rr_v2/public_train.json'
    assert hashlib.sha256(packet_path.read_bytes()).hexdigest() == manifest['packet_sha256']['public_train']
    packet = json.loads(packet_path.read_text())
    assert packet['split'] == 'train' and not packet['contains_gold_or_reference_program']
    public = {source['key']: source for source in packet['sources']}
    config = seal['config']['executor']
    rows, source_count = [], 0
    for source in seal['sources']['train']:
        source_path = stage / 'build/sources' / (digest(source) + '.json')
        if not source_path.exists():
            break
        record = json.loads(source_path.read_text()); source_count += 1
        _, expected = compiler_prompt(public[source])
        units = json.loads(expected)['units']
        for call in record['prediction']['calls']:
            step = call['step']
            saved = json.loads((stage / 'build/journals' / digest(source) / f'request{step}.json').read_text())
            dispatch = json.loads(saved['dispatch_json'])
            call_id = args.run_id + ':build:' + digest(source) + ':' + str(step)
            folder = stage / 'build/calls' / digest(call_id)
            wire = json.loads((folder / 'wire_request.json').read_text())
            body = base64.b64decode(wire['body_b64'])
            assert hashlib.sha256(body).hexdigest() == wire['body_sha256']
            expected_wire = request_payload(config, messages=dispatch['messages'], thinking=False, schema=dispatch['schema'])
            assert body == json.dumps(expected_wire, ensure_ascii=False).encode()
            tokenization = json.loads((folder / 'request.json').read_text())['tokenization']
            assert tokenization['count'] <= config['context_tokens'] - config['max_tokens']
            compiler_request = set(dispatch['schema']['properties']) == {'code'}
            if compiler_request:
                payload = json.loads(dispatch['messages'][1]['content'])
                assert payload['source'] == source and payload['units'] == units
            usage = call.get('usage')
            match = usage['prompt_tokens'] == tokenization['count'] if usage else None
            if usage:
                assert match
            rows.append({'source': source, 'step': step, 'call_id': call_id,
                'wire_sha256': wire['body_sha256'], 'exact_saved_dispatch_and_sampling': True,
                'thinking_off': True, 'full_original_units_verified': compiler_request,
                'serving_count': tokenization['count'], 'response_prompt_count_matches': match,
                'response_count_unavailable': usage is None})
    receipt = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'prefix_sources_audited': source_count, 'calls': rows,
        'all_available_response_prompt_counts_match_serving_measurement': True,
        'source_or_schema_or_sampler_changes_detected': False,
        'grading_packets_opened': False, 'new_model_or_oracle_calls': 0,
        'interpretation': 'Transport, public-input completeness and context-budget evidence only; not accepted IR, learned-rule faithfulness or core A/B success.'}
    Path(__file__).with_name(args.run_id + '_dispatch_audit.json').write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'prefix_sources_audited': source_count, 'requests_verified': len(rows),
        'response_counts_unavailable': sum(row['response_count_unavailable'] for row in rows), 'new_model_or_oracle_calls': 0}))


if __name__ == '__main__':
    main()
