"""Audit the same-source automatic-API control, semantic failures and real repair reuse."""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import run,validate
from legal_skill_guard.rr.ordinary_rule_literal import lower

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUNS=['legal_auto_interface_cache_v1_20261110','legal_auto_interface_reader_v2_20261110','legal_auto_interface_fact_search_v1_20261110']
STAGE=BASE/'legal_auto_interface_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_auto_interface_results.json'
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_feedback_acquisition_20261110/ledger.after.sqlite3')


def read(p):return json.loads(p.read_text())


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def priority_reuse(programme,policies):
    # This is deliberately a strong ordinary repair-cache control, not a new
    # proposed algorithm. Both programmes encode the same151/152 source policies.
    p=BASE/'legal_independent_cache_review_v1_20261110/reviewed_cache.py';t=ast.parse(p.read_text()).body[0]
    literals={}
    for n in t.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['rules','priorities']:
            literals[n.targets[0].id]=ast.literal_eval(n.value)
    old={r['id']:r for r in literals['rules']};new=deepcopy(programme);applied=[]
    def overlap(a,b):return a in b or b in a
    for edge in literals['priorities']:
        h,l=old[edge['higher']],old[edge['lower']]
        if h['head']['positive'] or not l['head']['positive'] or h['head']['predicate']!=l['head']['predicate']:continue
        for nh in new['rules']:
            for nl in new['rules']:
                if nh['head']['positive'] or not nl['head']['positive'] or nh['head']['predicate']!=nl['head']['predicate']:continue
                if nh['head']['predicate']!=h['head']['predicate'] or not overlap(h['quote'],nh['quote']) or not overlap(l['quote'],nl['quote']):continue
                e={'higher':nh['id'],'lower':nl['id'],'quote':edge['quote']}
                if e not in new['priorities']:
                    new['priorities'].append(e);applied.append({'old_model_priority':edge,'new_priority':e,
                        'match':'same signed consequence predicate and overlapping exact governing source quotes; no variable/role aliases'})
    assert len(applied)==2
    assert new['rules']==programme['rules'] and new['predicates']==programme['predicates'] and new['unresolved']==programme['unresolved']
    validate(new,[p['rules'] for p in policies])
    return new,{'actual_old_model_review_code_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'instantiations':applied,
        'same_policy_cross_programme_repair_not_new_source_transfer':True,'ordinary_source_quote_and_signed_head_pattern_control':True,
        'not_an_independent_method_contribution':True,'all_new_rule_bodies_and_signatures_unchanged':True}


def main():
    before=snapshot(BEFORE);current=snapshot(DB);historic=deepcopy(current)
    calls=[r for r in current['calls'] if any(r[0].startswith(n+':') for n in RUNS)]
    historic['calls']=[r for r in historic['calls'] if r not in calls]
    historic['meta']=[r for r in historic['meta'] if r[0] not in ['method_runtime_policy:'+n for n in RUNS]]
    assert historic==before and len(calls)==3 and all(r[6]=='completed' for r in calls)
    assert not [r for r in current['calls'] if r[6]=='reserved']
    source=read(BASE/RUNS[0]/'source.json');seal=read(BASE/RUNS[0]/'seal.json')
    programme,receipt=lower(source['value']['code'],source['value']['interface'],seal['source_policies'])
    adapted=read(BASE/RUNS[0]/'literal_programme_provenance_adaptation.json')
    assert programme==adapted['program'] and receipt==adapted['adaptation']
    fresh=read(BASE/RUNS[2]/'execution_closed_before_grading.json');reader_seal=read(BASE/RUNS[2]/'seal.json')
    old_frames=read(BASE/RUNS[1]/'execution_closed_before_grading.json')
    cached=read(ROOT/'reports/method_redesign_20261109/legal_independent_cache_results.json')['native_results']
    cached_grades={r['ordinal']:r['cached_TRAIN_grade'] for r in cached}
    # Independent factual review compares actual new rows against source-defined
    # primitive statuses; it does not change a frame or fill a missing value.
    required={81:[('dependent',['Bob','Alice','2015'])],
        86:[('qualifying_child',['Bob','Alice','2015']),('qualifying_child',['Charlie','Bob','2015'])],
        72:[('deduction_under_151_allowable_to',['Bob','Alice','2015'])]}
    reviewed=[]
    for c in fresh['cases']:
        assert c['status']=='executed_pending_independent_semantic_review'
        actual={(f['atom']['predicate'],tuple(f['atom']['arguments'])) for f in c['raw_case']['facts'] if f['atom']['predicate']!='case_subject_year'}
        assert actual=={(p,tuple(a)) for p,a in required[c['ordinal']]}
        assert all(f['atom']['positive'] is True for f in c['raw_case']['facts'])
        assert not c['raw_case']['unresolved']
        case={**c['raw_case'],'query':c['old_unchanged_query'],'facts':c['raw_case']['facts']+c['deterministic_task_metadata']}
        out=run(programme,case);assert out==c['output']
        assert c['native_prediction']==cached_grades[c['ordinal']]
        row={'ordinal':c['ordinal'],'prediction':c['native_prediction'],'cached_TRAIN_grade':cached_grades[c['ordinal']],
            'independent_factual_review_passed':True,'new_model_facts_not_modified':True,'native_correct':True,
            'facts_from_real_repaired_reader':c['raw_case'],'task_metadata':c['deterministic_task_metadata'],
            'actual_source_programme_query_witnesses':out['query_witnesses'],'rule_witnesses':out['rule_witnesses'],
            'full_named_person_roster_complete':c['ordinal']!=81,
            'missing_Bob_roster_in81_does_not_enter_151c_proof':c['ordinal']==81,
            '86_narrow_query_lift_only_from_actual_positive_witness':c['ordinal']==86,'no_fallback_answer_used':True}
        reviewed.append(row)
    warm,repair=priority_reuse(programme,seal['source_policies'])
    source86=fresh['cases'][1];case={**source86['raw_case'],'facts':source86['raw_case']['facts']+source86['deterministic_task_metadata'],
        'query':{'predicate':'dependent','arguments':['Charlie','Bob','2015'],'positive':True}}
    cold_probe=run(programme,case);warm_probe=run(warm,case)
    assert cold_probe['answer'] is None and warm_probe['answer']=='Contradiction'
    repair['actual_source_contract_probe']={'query':case['query'],'cold_answer':None,'warm_answer':'Contradiction',
        'not_a_new_native_case_or_grade':True,'correctness_basis':'152(b)(1) gives an ineligible dependent no dependents, overriding the general152(a) derivation.'}
    immutable_json(STAGE/'warm_source_priority_reuse.json',{'repair':repair,'program':warm,'source_contract_probe':warm_probe})
    frozen={'cold_program':programme,'warm_program':warm,'source_response_sha256':hashlib.sha256((BASE/RUNS[0]/'source.json').read_bytes()).hexdigest(),
        'reader_response_sha256':hashlib.sha256((BASE/RUNS[2]/'execution_closed_before_grading.json').read_bytes()).hexdigest(),
        'runtime_cases':[{'case':{**c['raw_case'],'query':c['old_unchanged_query'],'facts':c['raw_case']['facts']+c['deterministic_task_metadata']},'prediction':c['native_prediction']} for c in fresh['cases']],
        'shared_author_task_metadata_not_model_learned':True,'shared_basic_fact_concept_scope_given':True,
        'ordinary_correct_cache_control_not_new_method':True}
    immutable_json(STAGE/'frozen_library_and_cases.json',frozen)
    restored=read(STAGE/'frozen_library_and_cases.json')
    for c in restored['runtime_cases']:
        assert run(restored['cold_program'],c['case'])['answer']==c['prediction']
        assert run(restored['warm_program'],c['case'])['answer']==c['prediction']
    for name in RUNS:
        stage=BASE/name;s=read(stage/'seal.json')
        for p,h in s['files'].items():
            dest=stage/'frozen'/p
            if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==h
            else:
                raw=(ROOT/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    wires=[json.loads(r[8]) for r in calls];teacher=next(w for r,w in zip(calls,wires) if r[1]=='teacher')
    execs=[w for r,w in zip(calls,wires) if r[1]=='executor'];assert all(w['thinking_requested'] is False and w['finish_reason']=='stop' and w['reasoning_content'] in [None,''] for w in execs)
    assert teacher['invocation']['attempt']==1 and not teacher['invocation']['tool_events_detected']
    original=read(BASE/'legal_relations_exceptions_native_v1_20261109/teacher_program.json')['physical_response']
    costs={'new_teacher_source':{'elapsed_seconds':teacher['elapsed_seconds'],**teacher['invocation']['usage']},
        'new_executor_readers':{'elapsed_seconds':sum(w['elapsed_seconds'] for w in execs),'input_tokens':sum(w['usage']['prompt_tokens'] for w in execs),'output_tokens':sum(w['usage']['completion_tokens'] for w in execs)},
        'historical_original_relation_source_step_only':{'elapsed_seconds':original['elapsed_seconds'],**original['invocation']['usage']}}
    delta=[]
    for r in calls:
        d=dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],r));d['result']=json.loads(d['result']);delta.append(d)
    immutable_json(STAGE/'request_ledger_delta.json',{'new_calls':delta,'new_oracle_views':0})
    captured=read(REPORT)['captured_utc'] if REPORT.exists() else datetime.now(timezone.utc).isoformat()
    result={'captured_utc':captured,'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},'pending':0,
        'new_charged_attempts':{'executor':2,'teacher':1},'new_physical_dispatches':{'executor':2,'teacher':1},'new_oracle_views':0,'new_native_grades':0,'new_original_sources':0,
        'all_pre_turn_rows_equal_backup':True,'pre_turn_counts':{k:len(v) for k,v in before.items()},'current_counts':{k:len(v) for k,v in current.items()},
        'current_ledger_logical_sha256':digest(current),'cold_API_and_source_programme_acquisition_real':True,'learned_predicates_including_neutral_roster':15,'learned_rules':14,
        'only_original151_152_source_scope_not_63_c5':True,'first_reader_real_semantic_errors_preserved':True,
        'question_echo_and_derived_status_injections_not_counted_success':True,'foundational_fact_concept_scope_shared_author_guidance_not_learned':True,
        'native_annual_calendar_and_distinct_identifier_metadata_shared_not_learned':True,'old_model_queries_reused_unchanged':True,
        'source_structure_adaptation_not_raw_code_success':receipt,'repaired_reader_valid_primitive_facts_all_three':True,
        'full_person_rosters_valid':2,'full_person_rosters_total':3,'source81_missing_roster_not_new_failure_gate':True,
        'native_correct':3,'native_n':3,'native_results':reviewed,'cold_and_warm_frozen_replay_equal':True,
        'warm_same_policy_priority_repair_reuse':repair,'cold_three_query_success_not_whole_programme_semantic_certificate':True,
        'not_a_new_blind_cohort_or_two_method_contributions':True,'two_method_contributions_established':False,
        'costs':costs,'complete_matched_causal_pipeline_cost_advantage_not_established':True,
        'source_step_costs_single_pair_and_different_interface_shapes_not_general_speed_claim':True,
        'executor_incremental_API_cash_usd':0,'teacher_actual_invoice_usd':None,'GPU_cost_usd':None,'total_project_cash_cost_usd':None,
        'goal_complete':False,'new_full_build_started':False,'main_training_started':False,'TEST_labels_read':False,'paper_started':False}
    immutable_json(REPORT,result)
    dst=Path('/media/sangfor/vdb/legal-skill-backups/legal_auto_interface_20261110/ledger.after.sqlite3');dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists():
        with sqlite3.connect(DB) as a,sqlite3.connect(dst) as b:a.backup(b)
    assert snapshot(dst)==current
    print(json.dumps({k:result[k] for k in ['counts_total','pending','new_charged_attempts','all_pre_turn_rows_equal_backup','native_correct','native_n','costs']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
