"""One safe migration of the actual stopped B3 run; never dispatch a model.

Keep B1/B2 checkpoints and B3's paid proposal/initial comparisons. Reuse only
provider-completed component outputs that pass the SAME original schema and
whose source, prompt and frozen model profile are unchanged. A stricter exact
status grammar is not reported as a new physical generation of those outputs.
"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_mixed_component_training as training
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_teacher_transport import pack_task, unpack_task
from legal_skill_guard.skill_evolution.teacher_transport import unpack_programs


def run():
    root, previous = training.OUT, training.PREVIOUS_OUT
    if (root / 'protocol.json').exists():
        raise ValueError('Already bound; resume the existing training entry instead of remigrating')
    db = sqlite3.connect('file:' + str(training.ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    protocol = training.read(previous / 'protocol.json')
    receipts = []
    for batch in (1, 2):
        value = training.read(previous / f'B{batch}/checkpoint.json')
        immutable_json(root / f'B{batch}/checkpoint.json', value)
    # Initial observations and the already executed matched-read comparison
    # are not repeated merely because guidance implementation changed.
    source = previous / 'B3'
    for name in ('initial', 'matched_reads', 'matched_raw'):
        for path in (source / name).rglob('*.json'):
            immutable_json(root / 'B3' / path.relative_to(source), training.read(path))
    for name in ('initial_scored_results.json', 'teacher_task.json'):
        immutable_json(root / 'B3' / name, training.read(source / name))
    arm = 'CoverageRecombine'
    proposal = training.read(source / arm / 'teacher.json')
    paid_id = protocol['run_id'] + ':B3:' + arm + ':update'
    paid = db.execute('select status,result from calls where id=?', (paid_id,)).fetchone()
    assert paid and paid['status'] == 'completed'
    paid_result = json.loads(paid['result'])
    assert paid_result['response_sha256'] == proposal['response_sha256']
    request = training.read(previous / 'calls' / digest(paid_id) / 'request.json')
    task = training.read(source / 'teacher_task.json')
    expected = {**task, 'seed_for_this_arm': task['current_libraries_both_available'][arm]}
    assert unpack_programs(json.loads(request['user_prompt'])) == expected
    packed = pack_task(expected)
    assert unpack_task(packed) == expected
    immutable_json(root / 'B3' / arm / 'teacher.json', proposal)
    immutable_json(root / 'B3' / arm / 'paid_proposal_reuse.json', {
        'physical_call_id': paid_id, 'response_sha256': proposal['response_sha256'],
        'complete_underlying_teacher_task_unchanged': True, 'new_physical_requests': 0,
        'only_input_storage_encoding_changes_for_remaining_arm': True})
    sources = [previous, training.PRIOR_OUT,
        training.ROOT / 'artifacts/legal_skill_evolution_observation_component_execution_conditional_20261115']
    seen = set()
    for folder in sources:
        for path in (folder / 'component_reads').glob('*.json'):
            record = training.read(path)
            if record.get('error') or record.get('value') is None:
                continue
            raw_path = folder / 'raw_responses' / path.name
            if not raw_path.exists():
                continue
            raw = training.read(raw_path)
            physical_request = training.read(Path(raw['artifact_directory']) / 'request.json')
            identity = physical_request['id']
            settled = db.execute('select status,result,source,purpose from calls where id=?', (identity,)).fetchone()
            assert settled and settled['status'] == 'completed' and settled['purpose'] == 'skill_actor'
            assert settled['source'] == record['source'] == physical_request['source']
            result = json.loads(settled['result'])
            assert result['request_hash'] == physical_request['request_hash'] == raw['request_hash']
            payload = physical_request['payload']
            schema = json.loads(payload['messages'][-1]['content'])['output_schema']
            assert json.loads(raw['content']) == record['value']
            jsonschema.validate(record['value'], schema)
            wire, checks = decoding_schema(schema)
            new_payload = request_payload(protocol['executor_profile'], messages=payload['messages'], thinking=False, schema=wire)
            before = {k: v for k, v in payload.items() if k != 'response_format'}
            after = {k: v for k, v in new_payload.items() if k != 'response_format'}
            assert before == after, 'Source/prompt/profile changed; cannot migrate this observation'
            jsonschema.validate(record['value'], wire)
            key = digest({'source': record['source'], 'messages': payload['messages'], 'wire_schema': wire})
            if key in seen:
                continue
            seen.add(key)
            value = deepcopy(record)
            value.update(wire_input_sha256=key, original_wire_input_sha256=record['wire_input_sha256'],
                logical_request_only_wire_not_dispatched=True, deferred_decoder_checks=checks)
            value['receipt'].update(cache_hit=True, reused_physical_call_id=identity,
                reuse_kind='validated_same_source_prompt_schema_with_equivalent_stricter_status_guidance',
                new_physical_requests=0, prior_raw_response_path=str(raw_path.relative_to(training.ROOT)))
            immutable_json(root / 'component_reads' / (key + '.json'), value)
            receipts.append({'logical_read_key': key, 'physical_call_id': identity,
                'original_record': str(path.relative_to(training.ROOT)), 'value_sha256': digest(record['value']),
                'wire_schema_changed': payload['response_format']['json_schema']['schema'] != wire,
                'no_output_adaptation_or_score_selection': True})
    db.close()
    immutable_json(root / 'resume_receipt.json', {
        'same_goal': True, 'checkpoints_preserved': [1, 2], 'B3_initial_and_matched_reads_preserved': True,
        'successful_B3_teacher_reused': paid_id, 'invalid_outputs_not_adapted': True,
        'validated_output_replays': receipts, 'new_model_calls_for_migration': 0,
        'new_teacher_serialization_roundtrips_same_full_task': True,
        'teacher_payload_characters': len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))),
        'no_DEV_TEST_labels_read': True, 'goal_complete': False})
    print(json.dumps({'validated_reads_reused': len(receipts), 'teacher_proposals_reused': 1,
        'new_model_calls': 0, 'B1_B2_preserved': True}), flush=True)


if __name__ == '__main__':
    run()
