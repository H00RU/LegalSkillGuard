"""Recover already-paid, complete native first answers; never call a model.

This is a one-time current-run recovery, not a benchmark answer repair. The
discarded suffix is an auxiliary integer array absent from the Airline task.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3

import jsonschema
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.study import Study, load_json
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.native import public_task, answer_wire_schema, grade_view

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'configs/legal_skill_evolution_pilot_v4_20261111.json'
study = Study(ROOT, load_json(PROFILE))
study.initialize()
old = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v3'
library = Library()
receipt = []
with sqlite3.connect('file:' + str(study.ledger.path) + '?mode=ro', uri=True) as db:
    before = dict(db.execute('select role,count(*) from calls group by role'))
    for key in study.order[:3]:
        source = study.records[key]
        for view in source['views']:
            identity = digest({'source': key, 'view': view, 'library_hash': library.hash, 'retrieved': None})
            prior = load_json(old / 'view_results' / (identity + '.json'))
            if prior['execution'].get('answer') is not None:
                recovered = deepcopy(prior)
                physical = [e.get('physical_call_id', e['call_id']) for e in recovered['execution']['events']]
                recovery = 'preserved_complete_native_first_attempt'
            else:
                assert source['dataset'] == 'RuleArena_Airline'
                row = db.execute('select id,result from calls where source=? and id like ? and status=?',
                    (key, 'legal_skill_evolution_pilot_v3_20261111:%', 'completed')).fetchall()
                assert len(row) == 1
                call_id, raw = row[0]; result = json.loads(raw)
                assert result['finish_reason'] == 'length'
                request = load_json(Path(result['artifact_directory']) / 'request.json')
                payload = request['payload']
                sent = json.loads(payload['messages'][1]['content'])
                assert sent['task'] == public_task(source, view)
                schema = deepcopy(payload['response_format']['json_schema']['schema'])
                current = answer_wire_schema(source['dataset'], view)
                schema['properties']['evidence_sentence_ids'] = current['properties']['evidence_sentence_ids']
                assert digest(schema) == digest(current)
                match = re.fullmatch(r'\s*\{\s*"answer"\s*:\s*(0|[1-9][0-9]*)\s*,\s*'
                    r'"evidence_sentence_ids"\s*:\s*\[\s*[0-9,\s]*', result['content'])
                assert match, 'Native value incomplete or another semantic field present; no recovery permitted'
                answer = int(match.group(1))
                jsonschema.validate(answer, view['answer_schema'])
                recovered = {'view': view['id'], 'controlled': False,
                    'execution': {'answer': answer, 'evidence_sentence_ids': [], 'fallback': True,
                        'core_executed': False, 'retrieved': [], 'failed_candidates': [],
                        'full_response_complete': False, 'native_answer_field_complete': True,
                        'events': [{'call_id': call_id, 'physical_call_id': call_id,
                            'finish_reason': result['finish_reason'], 'usage': result['usage'],
                            'elapsed_seconds': result['elapsed_seconds'],
                            'auxiliary_tail_discarded': 'Only the non-native evidence integer array; native answer preserved'}]},
                    'score': grade_view(source['dataset'], view, study.grading[key][view['id']], answer)}
                physical = [call_id]
                recovery = 'complete_native_integer_before_truncated_unused_auxiliary_array'
            recovered['first_attempt_provenance'] = {'origin': str(old.relative_to(ROOT)),
                'physical_call_ids': physical, 'recovery': recovery,
                'native_source_and_task_unchanged': True, 'fresh_v4_model_output_claimed': False,
                'new_model_calls': 0, 'answers_or_test_labels_used_to_construct_recovery': False}
            immutable_json(study.folder / 'view_results' / (identity + '.json'), recovered)
            receipt.append({'source': key, 'view': view['id'], **recovered['first_attempt_provenance'],
                            'native_grade': recovered['score']['grade']})
    assert dict(db.execute('select role,count(*) from calls group by role')) == before
immutable_json(study.folder / 'original_first_attempt_prefix_recovery.json', {
    'views': receipt, 'physical_counts_before_and_after': before, 'new_model_calls': 0,
    'old_protocol_versions_retained': True, 'formal_study_will_start_from_empty_libraries': True})
print(json.dumps({'recovered_original_native_views': len(receipt), 'new_model_calls': 0,
                  'physical_counts': before, 'grades': [x['native_grade'] for x in receipt]}), flush=True)
