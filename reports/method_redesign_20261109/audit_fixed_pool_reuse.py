"""Read-only fixed-pool historical interface/annotation inventory; no refit."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from legal_skill_guard.rr.coverage import digest
from experiments.rr_v2_semantic_learning import ROOT,REPORT,STAGE,read


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    seal=read(STAGE/'seal.json');old=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109/build/sources'
    rows=[]
    for r in seal['source_pool']:
        p=old/(digest(r['source'])+'.json');d=read(p);calls=[]
        for c in d['calls']:
            try:wire=json.loads(c['raw_content'])
            except ValueError:wire={}
            observed=wire.get('factual_observations',[]) if isinstance(wire,dict) else []
            calls.append({'purpose':c['purpose'],'physical_origin_call_id':c['physical_origin_call_id'],
                'raw_content_sha256':hashlib.sha256(c['raw_content'].encode()).hexdigest(),
                'old_program_status':c['analysis'].get('program_status'),
                'old_interface_error_type':c['analysis'].get('error',{}).get('error_type'),
                'actual_factual_observation_entries':len(observed),
                'unknown_observation_declarations_are_not_actual_answers':True})
        rows.append({**r,'old_record':str(p.relative_to(ROOT)),'old_record_sha256':sha(p),'calls':calls,
                     'new_semantic_pilot_acquired':r['dataset']=='SARA_v2_Binary',
                     'used_to_refit_new_learner':False})
    r=next(x for x in rows if x['ordinal']==7);old7=read(ROOT/r['old_record'])
    q=json.loads(old7['calls'][1]['raw_content'])['factual_observations']
    tp=ROOT/'artifacts/rr_method_efficacy_20261109/efficacy_static_v2_schema_20261109/teacher_airline_train7.json'
    t=read(tp)['physical_response']['value']['factual_observations']; teacher={v['name']:v for v in t}
    grouped={}
    for v in q:grouped.setdefault(v['name'],[]).append(v)
    comparison=[{'name':name,'actual_executor_outputs':values,'teacher_judgment':teacher.get(name),
                 'values_agree':all(v['value']==teacher[name]['value'] for v in values) if name in teacher else None}
                for name,values in grouped.items()]
    refs=ROOT/'data/cache/rr_v2/RuleArena/airline'
    compute=(refs/'compute_answer.py').read_text();gen=(refs/'gen_questions.py').read_text()
    assert 'compute_check_cost(bag_list[1:]' in compute and '# Generate one carry-on item' in gen
    out={'captured_utc':datetime.now(timezone.utc).isoformat(),'new_model_calls':0,'fixed_pool_mothers':20,'sources':rows,
         'current_model_ledger_unchanged':{'executor':1362,'teacher':51},
         'new_M1_M2_training_data_from_this_audit':0,
         'legacy_Airline7':{'executor_physical_origin':old7['calls'][1]['physical_origin_call_id'],
              'teacher_record':str(tp.relative_to(ROOT)),'teacher_record_sha256':sha(tp),
              'actual_executor_entries':len(q),'unique_observations':len(grouped),'duplicate_entries':len(q)-len(grouped),
              'comparison':comparison,
              'teacher_disagreements':[x['name'] for x in comparison if x['values_agree'] is False],
              'disagreement_not_admitted_as_new_semantic_error':True,
              'reason':'Only storage fit differs (executor true vs teacher unknown); official benchmark generator/scorer presuppose the first carry-on. A physical-world unknown versus benchmark convention must not become an unannounced acceptance gate.'},
         'official_semantics':{'repository':'SkyRiver-2000/RuleArena','commit':'59f60f6b4eb93a9b6d187ec781349d4f15618903',
              'files':{p.name:sha(p) for p in (refs/'gen_questions.py',refs/'compute_answer.py')},
              'generator':'gen_questions.py generates the first bag with sample_carry_on at lines138-146',
              'scorer':'compute_answer.py line45 passes bag_list[1:] to checked-cost calculation',
              'no_generated_dataset_rows_or_TEST_labels_read':True,
              'runtime_policy_or_old_teacher_judgment_changed':False},
         'conclusion':'Reused inventory supplies usable actual local responses for three Airline sources, but no additional unambiguous multi-source TRAIN error/correction corpus is established. Do not turn old parser rejection or a teacher disagreement into new semantic success/failure labels.'}
    (REPORT/'M1M2_fixed_pool_reuse_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'new_calls':0,'sources':len(rows),'legacy_Airline7_unique':len(grouped),
                      'teacher_disagreements':out['legacy_Airline7']['teacher_disagreements'],
                      'safe_new_semantic_error_labels':0},ensure_ascii=False))


if __name__=='__main__':main()
