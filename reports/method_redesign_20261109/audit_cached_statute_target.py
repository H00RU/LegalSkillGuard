"""Replay the actual wrong-target record through exact cached source ownership."""
from copy import deepcopy
import hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_cached_statute_target import bind_explicit_applies
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import complete,digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.source_program import compile_source,source_theory
from experiments.rr_v2_train3_cached_fact_reader import cached_source

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='cached_statute_target_control_v1_20261110';STAGE=BASE/RUN
REPORT=ROOT/'reports/method_redesign_20261109/cached_statute_target_results.json'
OLD_ROUTE='method_runtime_reference_v8_20261109:build:a7dd769431a9c2cd8024e878a73e456eef15cf9ce540bf5450cdc34e42f3f2b1:0'
OLD_FACT='semantic_disambiguation_acquisition_v1_20261109:direct:TRAIN83:original'


def read(p):return json.loads(p.read_text())


def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    if REPORT.exists():
        print(json.dumps({'existing_result':str(REPORT),'no_new_dispatch_or_grade':True}));return
    before=snapshot();assert not [r for r in before['calls'] if r[6]=='reserved']
    parent,training_source,code,old_compiled,adaptation=cached_source()
    source=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==parent['sources']['train'][82])
    callmap={r[0]:r for r in before['calls']}
    rawroute=json.loads(callmap[OLD_ROUTE][8]);route=json.loads(rawroute['content'])
    rawfact=json.loads(callmap[OLD_FACT][8]);fact=json.loads(rawfact['content'])
    assert route['rule_outputs']==['agricultural_employing_person_qualification']
    assert fact['payer']=='Alice' and fact['payee']=='Bob' and fact['work_is_agricultural'] is False
    assert fact['work_activity']=='domestic service' and fact['work_activity'] in source['public']['facts']
    bound,receipt=bind_explicit_applies(training_source,source,old_compiled['program'])
    assert receipt['selected_clause']=='agricultural_labor_exclusion' and receipt['selected_sources']==['s32']
    assert route['rule_outputs']!=[receipt['selected_clause']]
    assert bound['clauses']==old_compiled['program']['clauses'] and bound['observations']==old_compiled['program']['observations']
    compiled=compile_source(source,bound)
    o=compiled['observations']['b_agricultural_labor']
    assert o['entity']==fact['payee'] and o['predicate']=='agricultural labor'
    observed={'b_agricultural_labor':fact['work_is_agricultural']}
    completion=complete(source_theory(compiled,observed))
    assert completion.status=='completion_stable' and completion.answer=='Contradiction'
    # Actual old menu/name choice changes meaning; source ownership is not
    # replaceable by a descendant's membership in the same section context.
    wrong=deepcopy(bound)
    wrong['query']={'op':'if','args':[{'var':route['rule_outputs'][0]},'Entailment','Contradiction']}
    wrong_compiled=compile_source(source,wrong)
    software={'b_agricultural_labor':True,'b_agricultural_cash_test':False,
        'b_agricultural_worker_day_test':False,'b_admitted_agricultural_alien':False}
    def software_completion(comp,values):
        theory=source_theory(comp,{k:v for k,v in values.items() if k in comp['observations']})
        for k,v in values.items():
            if k not in comp['observations']:
                assert k in theory.domains
                theory.constraints.append({'op':'eq','args':[{'var':k},v]})
        return complete(theory)
    good_probe=software_completion(compiled,software);bad_probe=software_completion(wrong_compiled,software)
    assert good_probe.answer=='Entailment' and bad_probe.answer=='Contradiction'
    # Prevent accidental source-cache widening, ambiguous ownership or a
    # non-applicability question from silently becoming a generic route.
    changed=deepcopy(source);changed['public']['rules']+='\nchanged'
    ambiguous=deepcopy(old_compiled['program']);dup=deepcopy(next(c for c in ambiguous['clauses'] if c['sources']==['s32']));dup['name']='duplicate_owner';ambiguous['clauses'].append(dup)
    badquery=deepcopy(source);badquery['public']['query']='How much does Alice owe?'
    rejections=[]
    for label,src,prog in [('different_statute',changed,old_compiled['program']),('ambiguous_owner',source,ambiguous),('unsupported_question_shape',badquery,old_compiled['program'])]:
        try:bind_explicit_applies(training_source,src,prog)
        except ValueError as e:rejections.append({'case':label,'error':str(e)})
        else:raise AssertionError(label)
    # The original A question remains A, without an added plan requirement.
    same,original_receipt=bind_explicit_applies(training_source,training_source,old_compiled['program'])
    assert same['query']==old_compiled['program']['query']
    frozen={'original_TRAIN_ordinal':83,'source':source,'training_source':training_source,
        'actual_existing_teacher_cache_sha256':hashlib.sha256(code.encode()).hexdigest(),
        'actual_old_route_call':{'id':OLD_ROUTE,'content':rawroute['content'],'request_hash':callmap[OLD_ROUTE][5]},
        'actual_old_fact_call':{'id':OLD_FACT,'content':rawfact['content'],'request_hash':callmap[OLD_FACT][5]},
        'new_source_only_binding':receipt,'new_bound_programme':bound,
        'observed_model_value_reused_unchanged':observed,
        'explicit_role_mapping_not_a_new_learned_alias':{'model_payee':fact['payee'],'cached_observation_entity':o['entity'],
            'scope':'Original case has a single directed service/payment event; no multi-event extrapolation.'},
        'actual_prediction_before_grade':completion.answer,'status':completion.status,'projection':completion.projection,
        'no_fallback_or_label_input':True,'original_failed_route_not_accepted':True,
        'software_mismatch_not_native_case':{'conditions':software,'correct_root_answer':good_probe.answer,'wrong_child_answer':bad_probe.answer},
        'source_and_query_scope_rejections':rejections,'original_A_route_unchanged':original_receipt,
        'new_model_calls':0,'goal_complete':False}
    immutable_json(STAGE/'execution_before_original_cached_grade.json',frozen)
    protocol=ROOT/'reports/method_redesign_20261109/cached_statute_target_protocol.md'
    paths=['experiments/rr_v2_cached_statute_target.py','reports/method_redesign_20261109/audit_cached_statute_target.py',
        'legal_skill_guard/rr/source_structure.py','legal_skill_guard/rr/source_program.py','legal_skill_guard/rr/clause_scope.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    cfg=read(BASE/'contract_norm_binding_v1_20261110/seal.json')['config']
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding={'code_hash':digest(hashes),'config_hash':digest(cfg)},sources=parent['sources'],
        authorization_hash=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        question='Original TRAIN83: exact source-owned applies target in existing ordinary cache, reusing existing same-case work/role output, not a descendant qualification; one original native cached grade, no model dispatch or new hypothesis.')
    view_hash=digest({'kind':'original_native_cached_grade','source':source['key'],'public':source['public']})
    ledger.reserve_oracle(source['key'],view_hash)
    grade=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][source['key']]
    assert frozen['actual_prediction_before_grade']==grade['answer']
    grade_record={'source':source['key'],'view_hash':view_hash,'cached_original_TRAIN_grade':grade,
        'prediction_from_existing_model_fact_and_new_source_target_binding':frozen['actual_prediction_before_grade'],
        'correct':True,'new_model_calls':0,'new_original_TRAIN_cached_label_views':1,'new_native_pairs':0,'TEST_or_DEV_read':False}
    immutable_json(STAGE/'original_cached_TRAIN_grade.json',grade_record)
    restored=read(STAGE/'execution_before_original_cached_grade.json')
    replay=complete(source_theory(compile_source(restored['source'],restored['new_bound_programme']),restored['observed_model_value_reused_unchanged']))
    assert replay.answer==restored['actual_prediction_before_grade']
    after=snapshot();assert after['calls']==before['calls']
    assert [r for r in after['oracle_views'] if r not in before['oracle_views']]==[(source['key'],view_hash,next(r[2] for r in after['oracle_views'] if r[0]==source['key'] and r[1]==view_hash))]
    assert len(after['meta'])==len(before['meta'])+1
    report={'counts_total':{role:sum(r[1]==role for r in after['calls']) for role in ['executor','teacher']},
        'pending':0,'new_model_calls':0,'new_original_TRAIN_cached_label_views':1,'new_counterfactual_views':0,'new_native_pairs':0,
        'actual_original_TRAIN_ordinal':83,'original_route_wrong_target':route['rule_outputs'][0],
        'new_exact_source_target':receipt['selected_clause'],'actual_original_native_prediction':completion.answer,
        'cached_original_native_grade':grade['answer'],'native_correct':True,'fallback_used':False,
        'actual_source_programme_and_original_model_fact_reused':True,'same_source_new_question_reuse_not_new_source_generation':True,
        'old_model_route_not_reclassified_as_success':True,'software_counterexample_not_new_native_data':True,
        'independent_simple_correct_cache_route_sufficient':True,'new_binding_mechanism_is_engineering_not_two_contributions':True,
        'frozen_replay_equal':True,'old_calls_unchanged':True,'new_meta_policy_count':1,
        'ledger_logical_sha256':digest(after),'current_counts':{k:len(v) for k,v in after.items()},
        'evidence_path':str((STAGE/'execution_before_original_cached_grade.json').relative_to(ROOT)),
        'TEST_DEV_full_training_or_paper_started':False,'goal_complete':False}
    immutable_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','new_original_TRAIN_cached_label_views','new_exact_source_target','actual_original_native_prediction','native_correct','goal_complete']},ensure_ascii=False))


if __name__=='__main__':main()
