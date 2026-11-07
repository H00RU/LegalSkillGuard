"""Verify saved batch material and teacher records without generation or grading."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files


def read_frozen(path):
    payload = json.loads(path.read_text())
    assert digest(payload['content']) == payload['sha256'], f'Frozen content hash differs: {path.name}'
    return payload, {'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'content_sha256': payload['sha256']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    state = json.loads((stage / 'build/state.json').read_text())
    completed_batches = state['completed_batches']
    assert 0 <= completed_batches <= 8 and state['complete_sources'] >= completed_batches * 16
    library, record_hashes, batches, teacher_rows = SkillLibrary(stage='formal_train'), [], [], []
    frozen_files = {}
    for batch in range(1, completed_batches + 1):
        path = stage / 'build/batches' / f'B{batch}.json'
        sources = seal['sources']['train'][(batch - 1) * 16:batch * 16]
        snapshot = json.loads(path.read_text())
        teacher = json.loads((stage / 'build/teacher_batches' / f'B{batch}.json').read_text())
        for source in sources:
            record = json.loads((stage / 'build/sources' / (digest(source) + '.json')).read_text())
            assert record['library_before_hash'] == digest(library.export())
            assert len(record['prediction']['calls']) <= 2 and len(record['learning']['oracle_views']) <= 4
            if record['learning'].get('learned_pattern'):
                library.add(record['learning']['learned_pattern'], source=source)
            record_hashes.append(digest(record))
            material = json.loads((stage / 'build/arm_shared_material' / (digest(source) + '.json')).read_text())
            assert set(material) == set(ARMS)
            assert len({item['shared_material_hash'] for item in material.values()}) == 1
            for item in material.values():
                assert item['shared_material_hash'] == digest(item['shared_material'])
                assert item['shared_material']['source'] == source and item['extra_paid_preparation_calls'] == 0
                assert item['shared_material']['teacher_summary'] == teacher
        assert snapshot['sources'] == seal['sources']['train'][:batch * 16]
        assert snapshot['source_record_hashes'] == record_hashes and snapshot['library'] == library.export()
        assert teacher['source_ids'] == sources and teacher['library_hash'] == digest(library.export())
        assert set(teacher['accepted_pattern_hashes']) <= {item['pattern_hash'] for item in library.patterns}
        if batch in {1, 8}:
            name = f'B{batch}.frozen.json'
            frozen, frozen_files[name] = read_frozen(stage / 'build' / name)
            assert frozen['content'] == SkillLibrary(library.patterns, frozen=True, stage=f'formal_B{batch}').export()
            name = f'B{batch}.MB.frozen.json'
            frozen, frozen_files[name] = read_frozen(stage / 'build' / name)
            content = frozen['content']
            assert content['frozen'] is True and content['source_count'] == batch * 16
            assert content['extra_model_calls'] == 0 and content['source_answers_stored_as_patterns'] is False
            frozen_files[name].update(source_count=content['source_count'],
                typed_families=len(content['families']), horn_families=len(content['horn_families']))
        response = teacher.get('response')
        if response:
            assert response['source_ids'] == sources and response['model'] == seal['config']['teacher']['model']
            invocation = response['invocation']
            assert not invocation['tool_events_detected']
            origin=response.get('paid_response_origin')
            if origin:
                cid=origin['call_id'];old_run=cid.split(':build:teacher:',1)[0]
                directory=stage.parent/old_run/'build/calls'/digest(cid)
                old_request=json.loads((directory/'request.json').read_text())
                assert hashlib.sha256((directory/'request.json').read_bytes()).hexdigest()==origin['request_file_sha256']
                assert hashlib.sha256((directory/'result.json').read_bytes()).hexdigest()==origin['result_file_sha256']
                with sqlite3.connect('file:'+str(root/seal['ledger_path'])+'?mode=ro',uri=True) as db:
                    row=db.execute('select status,result from calls where id=?',(cid,)).fetchone()
                assert row[0]=='completed' and json.loads(row[1])=={k:v for k,v in response.items() if k!='paid_response_origin'}
                assert old_request['source_ids']==sources and old_request['config']==seal['config']['teacher']
                payload=json.loads(old_request['user_prompt'])
                current_records=[json.loads((stage/'build/sources'/(digest(source)+'.json')).read_text()) for source in sources]
                common=[{'source':r['source'],'dataset':r['dataset'],
                    'program_status':r['prediction']['result']['program_status'],
                    'certificate_status':r['prediction']['result']['certificate_status'],
                    'learning_status':r['learning']['status'],'refinement':r['learning'].get('refinement'),
                    'pattern':r['learning'].get('learned_pattern')} for r in current_records]
                assert payload=={'common_training_records':common,'library':library.export(),
                    'previous_transport_or_schema_errors':teacher['errors']}
            teacher_rows.append({'batch': batch, 'model': response['model'],
                'wrapper_attempt': invocation['attempt'], 'tool_events_detected': False,
                'usage': invocation['usage'], 'estimated_credits': invocation['estimated_credits'],
                'actual_cash_invoice_available': response['actual_cash_invoice_available'],
                'success_event_log_hash': invocation['event_log_sha256'],
                'full_success_event_log_in_record': 'event_log' in invocation,
                'paid_response_origin':origin,
                'usage_attribution':'original settled physical request; no new teacher invocation' if origin else 'current run physical invocation'})
        batches.append({'batch': batch, 'prefix_sources': batch * 16,
            'source_records_and_all6arms_common_material_verified': True,
            'no_future_pattern_sources': all(set(item['evidence_sources']) <= set(snapshot['sources']) for item in library.patterns),
            'teacher_status': teacher['status'], 'recorded_schema_transport_errors': len(teacher['errors'])})
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id, 'audit_version': 2,
        'committed_completed_batches': completed_batches, 'only_committed_batches_verified': True,
        'frozen_prefixes_required_by_protocol': [1, 8], 'frozen_files_verified': frozen_files,
        'completed_batches_verified': batches, 'teacher_records': teacher_rows,
        'teacher_wrapper_retries_configured': seal['config']['teacher']['retries'],
        'teacher_provider_HTTP_attempts_not_independently_countable_from_success_event_hash_alone': True,
        'cost_note': 'Known teacher CLI invocations, usage and wrapper attempts are retained. No extra lower-level retries or cash costs are inferred from absent data.',
        'sealed_science_unchanged': True, 'new_model_or_oracle_calls': 0,
        'grading_packets_opened': False, 'goal_complete': False}
    Path(__file__).with_name(args.run_id + '_batch_material_verification.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'batches_verified': len(batches), 'sources_verified': len(batches) * 16,
        'all6arms_share_same_material': True, 'teacher_successes': len(teacher_rows), 'new_model_or_oracle_calls': 0}))


if __name__ == '__main__':
    main()
