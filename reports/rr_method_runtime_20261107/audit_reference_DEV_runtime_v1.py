"""Audit completed original six-arm DEV without generating or opening labels."""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    stage=ROOT/'artifacts/rr_method_runtime_20261107'/args.run_id
    seal=json.loads((stage/'seal.json').read_text())
    assert science_files(ROOT)==seal['files']
    completion=json.loads((stage/'build/completion.json').read_text())
    assert completion['build_complete'] and completion['sources']==128 and completion['batches']==8
    for name,sha in completion['frozen_files'].items():
        assert hashlib.sha256((stage/'build'/name).read_bytes()).hexdigest()==sha
    expected=seal['sources']['dev']
    assert len(expected)==40 and not set(expected)&set(seal['sources']['train'])
    # No score file is opened until every original arm/source prediction exists.
    for arm in ARMS:
        assert {p.stem for p in (stage/'dev/predictions'/arm).glob('*.json')}=={digest(s) for s in expected}
    scores=json.loads((stage/'dev/scores.json').read_text())
    assert scores['DEV_complete'] and scores['sources_per_arm']==40 and scores['outputs_per_arm']==48
    library=SkillLibrary.restore(stage/'build/B8.frozen.json').export()
    patterns={p['pattern_hash']:p for p in library['patterns']}
    with sqlite3.connect('file:'+str((ROOT/seal['ledger_path']).resolve())+'?mode=ro',uri=True) as db:
        physical=db.execute('select id,role,purpose,source,request_hash,status,result from calls').fetchall()
    by_hash={}
    for row in physical:
        if row[1]=='executor' and row[5]=='completed':
            by_hash.setdefault((row[3],row[4]),[]).append(row)
    rows=[];uses=[];arm_totals={};origins=set()
    for arm in ARMS:
        current=[]
        for source in expected:
            record=json.loads((stage/'dev/predictions'/arm/(digest(source)+'.json')).read_text())
            prediction=record['prediction'];result=prediction['result']
            assert 0<=len(prediction['calls'])<=prediction['model_calls']<=3
            assert len(prediction['call_purposes'])==prediction['model_calls']
            fallback=bool(result.get('fallback_used') or result.get('model_source_IR_still_unresolved'))
            primary=not fallback and result['program_status'] in {'source_IR_compiled','model_Horn_IR_compiled'}
            execution=result.get('execution') or (result.get('assessment') or {}).get('execution') or {}
            for use in execution.get('pattern_uses',[]):
                key=use['pattern_hash'];assert key in patterns
                support=use['supporting_training_sources']
                assert support==patterns[key]['evidence_sources']
                assert set(support)<=set(seal['sources']['train']) and source not in support
                bank=source.split(':',1)[0];banks={s.split(':',1)[0] for s in support}
                kind='foreign_only_stored_use' if bank not in banks else 'same_bank_stored_use' if banks=={bank} else 'shared_origin_stored_use'
                uses.append({'arm':arm,'source':source,'pattern_hash':key,'supporting_training_sources':support,
                    'provenance_class':kind,'primary_model_IR_path':primary,'query_relevant':use.get('query_relevant',True),
                    'execution_status':use['status'],'causal_necessity_or_benefit_not_inferred':True})
            exposures=set()
            for path in (stage/'dev/journals'/arm/digest(source)).glob('request*.json'):
                request=json.loads(path.read_text())
                if 'dispatch_json' not in request:continue
                dispatch=json.loads(request['dispatch_json']);payload=json.loads(dispatch['messages'][1]['content'])
                menu=payload.get('available_learned_patterns',payload.get('runtime_contract',{}).get('available_learned_patterns',[]))
                exposures.update(p['pattern_hash'] for p in menu)
            assert exposures<=set(patterns)
            if ARMS[arm].interface!='collision_refined':assert not exposures
            calls=[]
            for call in prediction['calls']:
                matched=[p for p in by_hash.get((source,call['request_hash']),[])
                    if json.loads(p[6]).get('content')==call['raw_content']]
                assert len(matched)==1
                origin=matched[0];cid=origin[0];response=json.loads(origin[6])
                assert origin[2]=='method_dev' and cid.startswith(args.run_id+':dev:')
                if call.get('physical_origin_call_id'):assert call['physical_origin_call_id']==cid
                assert response['thinking_requested'] is False and not response.get('reasoning_content')
                directory=Path(response['artifact_directory'])
                wire=json.loads(base64.b64decode(json.loads((directory/'wire_request.json').read_text())['body_b64']))
                assert wire['chat_template_kwargs']['enable_thinking'] is False
                assert wire['max_tokens']==seal['config']['executor']['max_tokens']
                origins.add(cid)
                calls.append({'physical_origin_call_id':cid,'reused':bool(call.get('physical_origin_call_id')),
                    'finish_reason':response['finish_reason'],'usage':response['usage']})
            row={'arm':arm,'source':source,'dataset':source.split(':',1)[0],
                'record_sha256':hashlib.sha256((stage/'dev/predictions'/arm/(digest(source)+'.json')).read_bytes()).hexdigest(),
                'program_status':result['program_status'],'certificate_status':result['certificate_status'],
                'A_actual':result['A_main_path_executed'],'B_actual':result['B_main_path_executed'],
                'primary_model_IR_path':primary,'fallback':fallback,
                'native_fallback':result.get('fallback_used',False),
                'controlled_Horn_fallback':bool(result.get('model_source_IR_still_unresolved')),
                'DEV_match':scores['source_scores'][arm][source]['task_correct'],
                'logical_calls':prediction['model_calls'],'calls':calls,
                'pattern_prompt_exposure':sorted(exposures),
                'actual_stored_graph_executions':len(execution.get('pattern_uses',[])),
                'final_error':result.get('error'),
                'source_faithfulness_not_implied_by_type_or_label_match':True}
            rows.append(row);current.append(row)
        arm_totals[arm]={'sources':len(current),
            **{k:sum(bool(r[k]) for r in current) for k in ('A_actual','B_actual','primary_model_IR_path','fallback','DEV_match')},
            'logical_calls':sum(r['logical_calls'] for r in current),
            'exact_paid_raw_replays':sum(c['reused'] for r in current for c in r['calls']),
            'final_program_status':dict(Counter(r['program_status'] for r in current)),
            'by_dataset':{bank:{'sources':len(group),
                **{k:sum(bool(r[k]) for r in group) for k in ('A_actual','B_actual','primary_model_IR_path','fallback','DEV_match')}}
                for bank in sorted({r['dataset'] for r in current})
                if (group:=[r for r in current if r['dataset']==bank])}}
    table={(r['arm'],r['source']):r for r in rows};pairs={}
    for control in ('M10','M01','MA','MB','M00'):
        pairs[control]={'both_correct':0,'M11_only_correct':0,'control_only_correct':0,'both_incorrect':0}
        for source in expected:
            a=table['M11',source]['DEV_match'];b=table[control,source]['DEV_match']
            key='both_correct' if a and b else 'M11_only_correct' if a else 'control_only_correct' if b else 'both_incorrect'
            pairs[control][key]+=1
    dev_physical=[r for r in physical if r[0].startswith(args.run_id+':dev:')]
    value={'captured_utc':datetime.now(timezone.utc).isoformat(),'run_id':args.run_id,
        'complete_original_six_arm_DEV':True,'sources_per_arm':40,'outputs_per_arm':48,
        'original_saved_scores':scores['scores'],'arm_totals':arm_totals,'paired_source_correctness':pairs,
        'rows':rows,'stored_graph_uses':uses,
        'actual_stored_use_provenance':dict(Counter(u['provenance_class'] for u in uses if u['primary_model_IR_path'])),
        'physical_requests_by_role_status':dict(Counter(r[1]+':'+r[5] for r in dev_physical)),
        'unique_completed_physical_origins_in_saved_predictions':len(origins),
        'logical_calls_total':sum(r['logical_calls'] for r in rows),
        'exact_paid_raw_replays_total':sum(c['reused'] for r in rows for c in r['calls']),
        'thinking_OFF_and_per_prediction_three_call_budget_verified':True,
        'raw_replay_same_DEV_run_source_and_original_files_verified':True,
        'frozen_library_files_unchanged':True,'original_DEV_private_labels_opened_by_this_audit':False,
        'TEST_opened':False,'new_model_or_oracle_calls':0,
        'actual_stored_use_or_label_gain_does_not_prove_causal_transfer':True,
        'report_is_descriptive_not_an_added_acceptance_gate':True,'full_goal_complete':False}
    out=Path(__file__).with_name('reference_'+args.run_id+'_DEV_runtime_audit.json')
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('run_id','complete_original_six_arm_DEV','logical_calls_total','exact_paid_raw_replays_total','actual_stored_use_provenance')},ensure_ascii=False))


if __name__=='__main__':main()
