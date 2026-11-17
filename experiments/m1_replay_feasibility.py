"""Reproduce the finite M1 comparison from published responses; no generation."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.skill_evolution.native import grade_view

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'reports/two_method_followthrough_20261116/M1_finite_evidence_20261117'


def serialized(value):
    # Source-span tuples are JSON arrays on disk. Compare the persisted ABI.
    return json.loads(json.dumps(value, ensure_ascii=False))


def replay():
    manifest=json.loads((PACKET/'manifest.json').read_text())
    for n,h in manifest['files_sha256'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
    data=json.loads(gzip.decompress((PACKET/'finite_replay.json.gz').read_bytes()))
    cases=data['cases'];original=0
    for c in cases:
        assert c['role'] in ('development','calibration')
        assert serialized(decode_response(c['source'],c['view'],c['plan'],c['original_response']))==c['current_actual']
        response={'finish_reason':'stop','content':json.dumps(reference_wire('OpenExempt',c['plan'],c['source_card'],c['view']['source_units']))}
        assert serialized(decode_response(c['source'],c['view'],c['plan'],response))==c['reference_probe']
        original+=1
    for row in data['prompt_predictions']:
        c=next(c for c in cases if c['source']['key']==row['source'] and c['view_id']==row['view'] and c['plan']['name']=='records')
        assert serialized(decode_response(c['source'],c['view'],c['plan'],data['raw_calls'][row['physical_call_id']]['result.json']))==row['decoded']
    for partition,rows in data['native_scores'].items():
        for row in rows:
            c=next(c for c in cases if c['source']['key']==row['source'] and c['view_id']==row['view'])
            metrics=grade_view('OpenExempt',c['native_views'][row['task']],data['D_C_annotations'][row['source']][row['task']],row['answer']) if row['handled'] else {'grade':0.0,'unresolved_or_failed':True}
            assert metrics==row['metrics']
    dev=data['native_scores']['development']
    mean=lambda name:sum(r['grade'] for r in dev if r['candidate']==name)/2
    selection={'fixed':'records','M1':'local_records' if mean('local_records')>mean('records') else 'records',
               'ordinary_prompt':'prompt_records' if mean('prompt_records')>mean('records') else 'records'}
    assert selection==data['terminal']['selection']
    for arm,name in selection.items():
        rows=[r for r in data['native_scores']['calibration_diagnostic'] if r['candidate']==name]
        assert len(rows)==4
        assert sum(r['grade'] for r in rows)/4==data['terminal']['arms'][arm]['native_task_mean']
        assert sum(r['metrics'].get('correct',False) for r in rows)==0
    decision=data['attribution_decision']; skill=frozen_skill()
    for row in decision['same_actual_input_full_F_vs_generated_F_prime_checks']:
        inputs=row['full_result']['contrasting_or_representative_completions'][0]['completion_witness']
        c=next(c for c in cases if c['source']['key']==row['source'] and c['view_id']==row['view'] and c['plan']['name']=='local_records')
        full=partial_skill(skill,inputs,[])
        reduced=partial_skill(dict(skill,procedure=c['plan']['residual_program']['procedure']),inputs,[])
        assert full['handled'] and reduced['handled'] and full['answer']==reduced['answer']==row['full_result']['answer']
    for row in decision['reference_completion_replays']:
        c=next(c for c in cases if c['source']['key']==row['source'] and c['view_id']==row['view'] and c['plan']['name']=='local_records')
        value=partial_skill(dict(skill,procedure=c['plan']['residual_program']['procedure']),row['completion_inputs'],[])
        assert value['handled'] and value['answer']==row['answer']
    return {'original_real_response_replays':original,'reference_probes':original,
        'new_prompt_responses_replayed':len(data['prompt_predictions']),
        'native_score_checks':sum(len(r) for r in data['native_scores'].values()),
        'same_input_full_vs_residual_checks':3,'reference_completion_checks':5,
        'selection':selection,'M1_calibration_native_F1':1/3,'exact_correct_each_arm':0,
        'decision':decision['decision'],'new_model_calls':0}


if __name__=='__main__':print(json.dumps(replay(),ensure_ascii=False,sort_keys=True))
