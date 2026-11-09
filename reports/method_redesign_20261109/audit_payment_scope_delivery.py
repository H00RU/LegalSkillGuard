"""Read-only actual scope result, fair common control, source and cost evidence."""
from datetime import datetime,timezone
import hashlib
import json
from legal_skill_guard.rr.payment_scope import decode_payments,scope_sum
from legal_skill_guard.rr.source_discrimination import execute_paths
from experiments.rr_v2_payment_scope_pilot import ROOT,STAGE,prepare,read
from experiments.rr_v2_semantic_learning import check_frozen


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    check_frozen();s=prepare();p=read(STAGE/'processed_executor.json');t=read(STAGE/'teacher_processed.json')
    e=read(STAGE/'processed_execution.json');v=t['physical_response']['value']
    assert sha(STAGE/'executor.json')==p['original_executor_sha256']
    assert sha(ROOT/'reports/method_redesign_20261109/process_payment_scope.py')==p['processor_sha256']
    assert len(v['executor_event_reviews'])==len(p['decoded']['events'])==4
    assert {r['event_index'] for r in v['executor_event_reviews']}==set(range(4))
    assert all(r['all_role_relations_supported'] for r in v['executor_event_reviews'])
    assert v['independent_events']==p['normalized_value']['events']
    assert v['executor_event_completeness_supported'] is True
    decode_payments({'events':v['independent_events']},s['case']['facts'])
    ordinary=read(ROOT/'reports/method_redesign_20261109/M1_learned_dependency_results.json')['ordinary_same_information_paths']
    baseline=scope_sum(p['decoded'],payer='Alice',kind='wages',
        work_classify=lambda row:execute_paths(ordinary,[{'values':row}])[0],
        threshold=s['threshold_span'][1:].replace(',',''))
    for key in ('sum_lower','sum_upper','at_least_threshold','trace'):assert baseline[key]==e[key],key
    assert e['native_legal_answer'] is None and not e['source_review']['payment_year_explicit']
    assert [r['status'] for r in e['trace']]==['included','included','included','excluded']
    assert len(p['conversions'])==4 and all(c['path'][-1]=='payment_medium' for c in p['conversions'])
    assert read(STAGE/'executor.json')['validation']['status']=='rejected'
    case_id=s['source'];old=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109/build/sources'
    from legal_skill_guard.rr.coverage import digest
    prior=read(old/(digest(case_id)+'.json'))['calls'][1]
    refs=ROOT/'data/cache/rr_v2/SARA_reference/statutes/prolog/section3306.pl'
    out={'captured_utc':datetime.now(timezone.utc).isoformat(),'new_model_calls_this_step':{'executor':2,'teacher':1},
        'source':case_id,'case_id':'TRAIN88:original','new_sources':0,'new_native_labels_read':0,
        'prior_response':{'physical_origin':prior['physical_origin_call_id'],
                          'content':json.loads(prior['raw_content']),'executable_rule_generated':False},
        'actual_event_count':4,'independent_teacher_event_count':4,'independent_events_exactly_match':True,
        'all_role_relations_and_completeness_reviewed':True,'teacher_judgment_not_formal_semantic_proof':True,
        'strict_source_pointer_checks_passed_on_derived_IR':True,'raw_response_remains_unchanged_and_rejected':True,
        'conversions':p['conversions'],'source_scope_execution':e,'ordinary_same_information_control':baseline,
        'ordinary_and_learned_path_results_identical':True,
        'actual_learned_classification_uses':3,'uses_are_events_not_independent_sources':True,
        'training_mothers_for_classification':s['learned_paths']['training_rows'],
        'payment_year_not_filled_from_service_period':True,
        'read_only_reference_scope':{'file':str(refs.relative_to(ROOT)),'sha256':sha(refs),
            'observed_temporal_role':'s3306_a_2_is_wages checks start_(Remuneration,Time), distinct from service event dates',
            'not_used_as_a_complete_oracle_or_to_repair_facts':True},
        'native_answer_claimed':False,'model_full_rule_IR_claimed':False,
        'new_unique_M1_or_M2_effect_claimed':False,'goal_complete':False}
    path=ROOT/'reports/method_redesign_20261109/payment_scope_delivery_audit.json'
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'events':4,'total':e['sum_lower'],'reverse_excluded':True,'ordinary_same':True,
                      'native_legal_answer':None,'new_calls':out['new_model_calls_this_step'],'goal_complete':False}))


if __name__=='__main__':main()
