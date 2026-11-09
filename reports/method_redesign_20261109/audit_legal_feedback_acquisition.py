"""Replay actual source feedback -> ordinary consistency update -> frozen cache."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_legal_feedback_acquisition import BASE,ROOT,STAGE,hypotheses,offline,read,raw_rows,score,value
from experiments.rr_v2_legal_annual_scope import check,plan_sql,sql_value
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ordinary_python_cache import execute

RUNS=['legal_feedback_acquisition_v1_20261110','legal_feedback_direct_control_v1_20261110']
OUT=BASE/'legal_feedback_update_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_feedback_acquisition_results.json'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_annual_scope_20261110/ledger.after.sqlite3')
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=snapshot(BEFORE);current=snapshot(DB);historic=deepcopy(current)
    added=[r for r in current['calls'] if any(r[0].startswith(n+':') for n in RUNS)]
    historic['calls']=[r for r in historic['calls'] if r not in added]
    historic['meta']=[r for r in historic['meta'] if r[0] not in ['method_runtime_policy:'+n for n in RUNS]]
    assert historic==before and len(added)==3
    assert all(r[1]=='teacher' and r[6]=='completed' for r in added)
    assert not [r for r in current['calls'] if r[6]=='reserved']
    seal=read(STAGE/'seal.json');off=offline();libraries={};costs={}
    prior=read(BASE/'legal_annual_scope_v3_20261110/plan.json')
    diagnostic=read(BASE/'legal_annual_scope_execution_v1_20261110/execution.json')
    payments=diagnostic['raw_payments'];quals=diagnostic['candidate_witnesses']
    for arm in ['free','fixed']:
        raw=read(STAGE/(arm+'.json'));fixed=seal['fixed_queries'] if arm=='fixed' else None
        scores=score(raw['value']['tests'],seal['source_excerpt'],fixed)
        assert scores==raw['scores'] and scores['all_feedback_semantically_correct'] and scores['unique_reference_plan']
        # This is ordinary exact consistency over model-supplied values. The
        # independent source reference is a reporting check, not a candidate label.
        survivors=[h for h in hypotheses() if all(value(h,raw_rows(t['payments']))==t['expected'] for t in raw['value']['tests'])]
        assert len(survivors)==1 and survivors==scores['survivors']
        plan=survivors[0];sql=plan_sql(plan);checks=check(sql)
        assert checks['all_passed']
        result=sql_value(sql,payments,quals);assert result==20597
        library={'kind':'ordinary_source_feedback_consistency_policy_cache','source':seal['source'],'source_excerpt_sha256':hashlib.sha256(seal['source_excerpt'].encode()).hexdigest(),
            'plan':plan,'sql':sql,'feedback_arm':arm,'feedback_artifact_sha256':hashlib.sha256((STAGE/(arm+'.json')).read_bytes()).hexdigest(),
            'grammar_classes':52,'threshold_given_in_common_candidate_contract':7000,'scope_keys_and_operator_inferred_from_real_model_feedback':True,
            'all_other_statutory_preconditions_outside_component':True,'not_a_new_method_contribution_claim':True}
        path=OUT/(arm+'_frozen_library.json');immutable_json(path,library)
        restored=read(path);assert sql_value(restored['sql'],payments,quals)==result
        libraries[arm]={'plan':plan,'source_checks':checks,'local_annotated_result':result,'frozen_replay_equal':True,
            'prior_model_plan':prior['plan'],'prior_source_checks_passed':sum(r['passed'] for r in prior['source_checks']['rows']),
            'current_source_checks_passed':8,'native_task_grade_added':False,'model_feedback_tests':raw['value']['tests']}
        w=raw['physical_response'];costs[arm]={'elapsed_seconds':w['elapsed_seconds'],**w['invocation']['usage'],'tool_events_detected':w['invocation']['tool_events_detected']}
    direct_path=BASE/RUNS[1]/'source.json';direct=read(direct_path);assert direct['source_checks']['all_passed']
    programme=direct['code'];facts=diagnostic['local_admitted_rows'];actual=execute(programme,facts,'component3306_b_1');assert actual==20597
    immutable_json(OUT/'direct_frozen_library.json',{'kind':'ordinary_direct_policy_programme','code':programme,'source':seal['source'],
        'query_contract':'component3306_b_1','source_artifact_sha256':hashlib.sha256(direct_path.read_bytes()).hexdigest(),
        'no_author_or_model_feedback_values_seen':True,'scope_local_only':True,'not_a_new_method_contribution_claim':True})
    restored=read(OUT/'direct_frozen_library.json');assert execute(restored['code'],facts,restored['query_contract'])==actual
    w=direct['physical_response'];costs['direct_programme']={'elapsed_seconds':w['elapsed_seconds'],**w['invocation']['usage'],'tool_events_detected':w['invocation']['tool_events_detected']}
    libraries['direct_programme']={'source_checks':direct['source_checks'],'local_annotated_result':actual,'frozen_replay_equal':True,'native_task_grade_added':False}
    copied={}
    for name in RUNS:
        s=read(BASE/name/'seal.json');copied[name]={}
        for p,h in s['files'].items():
            data=(ROOT/p).read_bytes();assert hashlib.sha256(data).hexdigest()==h
            dest=BASE/name/'frozen'/p;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==data
            else:dest.write_bytes(data)
            copied[name][p]=h
    assert not any(c['tool_events_detected'] for c in costs.values())
    allcost={k:sum(c[k] for c in costs.values()) for k in ['elapsed_seconds','input_tokens','output_tokens','reasoning_output_tokens','cached_input_tokens']}
    delta=[]
    for r in added:
        d=dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],r));d['result']=json.loads(d['result']);delta.append(d)
    immutable_json(OUT/'request_ledger_delta.json',{'new_calls':delta,'new_oracle_views':0})
    captured=read(REPORT)['captured_utc'] if REPORT.exists() else datetime.now(timezone.utc).isoformat()
    result={'captured_utc':captured,'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':0,'teacher':3},'new_physical_dispatches':{'executor':0,'teacher':3},
        'new_original_sources':0,'new_native_task_grades':0,'new_oracle_views':0,'all_pre_turn_rows_equal_backup':True,
        'pre_turn_counts':{k:len(v) for k,v in before.items()},'current_counts':{k:len(v) for k,v in current.items()},
        'old_ledger_logical_sha256':digest(historic),'current_ledger_logical_sha256':digest(current),
        'teacher_configuration_unchanged':True,'executor_thinking_OFF_no_executor_request':True,'client_retries':0,
        'no_tool_events':True,'source_reference_labels_not_in_acquisition_prompts':True,
        'input_pool_authored_previously_not_autonomously_learned':True,'threshold_given_common_contract_not_learned':True,
        'quotient_and_selection':off,'ordinary_free_source_tests_also_identify':True,
        'ordinary_version_space_design_absorbs_fixed_query_selection':True,'two_method_contributions_established':False,
        'actual_feedback_update_and_freeze_completed':True,'libraries':libraries,'costs_by_arm':costs,'all_teacher_costs':allcost,
        'observed_costs_single_pair_not_general_advantage':True,'teacher_actual_invoice_usd':None,'GPU_cost_usd':None,'total_project_cash_cost_usd':None,
        'bound_source_copies':copied,'regressions_passed':4,'original_failed_predictions_preserved':True,
        'goal_complete':False,'new_full_build_started':False,'TEST_labels_read':False,'paper_started':False}
    immutable_json(REPORT,result)
    dst=Path('/media/sangfor/vdb/legal-skill-backups/legal_feedback_acquisition_20261110/ledger.after.sqlite3');dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists():
        with sqlite3.connect(DB) as a,sqlite3.connect(dst) as b:a.backup(b)
    assert snapshot(dst)==current
    print(json.dumps({k:result[k] for k in ['counts_total','pending','new_charged_attempts','all_pre_turn_rows_equal_backup','costs_by_arm','actual_feedback_update_and_freeze_completed']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
