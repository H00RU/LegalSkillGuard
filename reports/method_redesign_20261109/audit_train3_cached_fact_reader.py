"""Audit original TRAIN3 ordinary reader, citation gap, replay, costs and ledger.

No native annotation replaces a generated value. Citation completeness is
reported separately, not silently added as a new native-task acceptance gate.
"""
import base64,hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_train3_cached_fact_reader import accept
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import complete,digest
from legal_skill_guard.rr.source_program import compile_source,source_theory

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='train3_cached_fact_reader_v1_20261110';STAGE=BASE/RUN
AUDIT=BASE/'train3_cached_fact_reader_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/train3_cached_fact_reader_results.json'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/train3_cached_fact_reader_20261110/ledger.before.sqlite3')


def read(p):return json.loads(p.read_text())


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=snapshot(BEFORE);db=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3';current=snapshot(db)
    added={t:[r for r in current[t] if r not in before[t]] for t in before}
    assert all([r for r in current[t] if r in before[t]]==before[t] for t in before)
    assert len(added['calls'])==1 and len(added['meta'])==2 and len(added['oracle_views'])==1
    call=added['calls'][0];assert call[0]==RUN+':facts' and call[1]=='executor' and call[6]=='completed'
    assert not [r for r in current['calls'] if r[6]=='reserved']
    assert {r[0] for r in added['meta']}=={'method_runtime_policy:'+RUN,'method_runtime_policy:cached_statute_target_control_v1_20261110'}
    target=read(ROOT/'reports/method_redesign_20261109/cached_statute_target_results.json')
    targetgrade=read(BASE/'cached_statute_target_control_v1_20261110/original_cached_TRAIN_grade.json')
    assert added['oracle_views'][0][:2]==(targetgrade['source'],targetgrade['view_hash'])
    seal=read(STAGE/'seal.json');raw=read(STAGE/'execution_before_cached_grading.json');w=raw['physical_response']
    assert {k:v for k,v in w.items() if k!='cache_hit'}==json.loads(call[8])
    assert w['cache_hit'] is False and w['thinking_requested'] is False
    assert w['reasoning_content'] is None and w['finish_reason']=='stop'
    path=Path(w['artifact_directory']);wire=read(path/'wire_request.json');payload=json.loads(base64.b64decode(wire['body_b64']))
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    assert {k:payload[k] for k in ['temperature','top_p','top_k','seed','max_tokens']}=={'temperature':.6,'top_p':.95,'top_k':20,'seed':45,'max_tokens':8192}
    assert payload['messages']==seal['messages'] and payload['response_format']['json_schema']['schema']==seal['schema']
    assert seal['source']['public']['query'] not in payload['messages'][1]['content']
    assert '2019-10-10' not in payload['messages'][1]['content']
    for p,sha in seal['files'].items():assert hashlib.sha256((STAGE/'frozen'/p).read_bytes()).hexdigest()==sha
    observed=accept(raw['raw_generated_values'],seal['source'])
    assert observed==raw['observed']=={'b_after_employment_termination':True,'b_termination_death':None,'b_retirement_for_disability':True}
    result=complete(source_theory(compile_source(seal['source'],seal['programme']),observed))
    assert result.status=='completion_stable' and result.answer==raw['answer']=='Entailment'
    grade=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][seal['source']['key']]
    assert result.answer==grade['answer']
    source69_etc={r[0]:r for r in current['calls']}
    route_id='method_runtime_reference_v8_20261109:build:a7dd769431a9c2cd8024e878a73e456eef15cf9ce540bf5450cdc34e42f3f2b1:0'
    fact_id='semantic_disambiguation_acquisition_v1_20261109:direct:TRAIN83:original'
    assert source69_etc[route_id][4]==source69_etc[fact_id][4]==targetgrade['source']
    oldroute=json.loads(source69_etc[route_id][8]);oldrequest=read(Path(oldroute['artifact_directory'])/'request.json')
    oldpayload=oldrequest['payload'];olduser=json.loads(oldpayload['messages'][-1]['content'])
    assert olduser['CURRENT_target']['unit_ids']==['s32']
    assert any(r['name']=='agricultural_labor_exclusion' and r['sources']==['s32'] for r in olduser['available_requested_rule_outputs'])
    immutable_json(BASE/'cached_statute_target_control_v1_20261110/actual_old_route_input.json',{
        'call_id':route_id,'original_request_hash':source69_etc[route_id][5],
        'actual_user_payload':olduser,'actual_model_route':json.loads(oldroute['content']),
        'correct_root_was_in_original_menu':True,'classification':'Model chose the wrong descendant; the old caller failed to enforce explicit target ownership.',
        'original_direct_fact_origin_matches_same_source':True})
    gap={
        'field':'b_after_employment_termination','model_value':True,
        'actual_quote':raw['raw_generated_values']['b_after_employment_termination']['quote'],
        'quote_exact_public_substring':True,
        'quote_mentions_retirement_but_not_payment_ordering':True,
        'native_reference_condition_consistent':True,
        'native_reference_is_not_used_to_fill_or_replace_model_value':True,
        'full_public_case_supplied_to_model':seal['source']['public']['facts'],
        'public_case_native_interpretation':'The causal termination/payment narrative is consistent with the original native intended condition. Exact payment day comes only from the separate native annotation.',
        'not_a_quote_only_semantic_certificate':True,
        'not_an_added_self_contained_quote_or_explicit_timestamp_acceptance_gate':True,
        'no_general_NL_entailment_or_all_predicate_fidelity_claim':True}
    review={
        'generated_values':raw['raw_generated_values'],'accepted_unchanged_model_values':observed,
        'actual_cached_execution':{'status':result.status,'answer':result.answer,'projection':result.projection},
        'original_TRAIN_cached_grade':grade,'native_task_correct':True,'fallback_used':False,
        'retirement_explicit_in_public_case':True,'unmentioned_death_left_unknown':True,
        'citation_scope_review':gap,'not_a_new_source_programme_or_either_contribution':True,
        'source_teacher_was_case_and_question_aware':True,
        'model_received_no_native_label_question_or_annotation_date':True,
        'partial_read_of_full_case_not_replaced_by_native_annotation':True,
        'original0of89_whole_source_executor_IR_not_changed':True}
    immutable_json(AUDIT/'native_review_and_replay.json',review)
    frozen={'source':seal['source'],'programme':seal['programme'],'actual_model_values':observed,
        'native_answer':result.answer,'source_programme_sha256':seal['old_paid_code_sha256'],
        'raw_model_frame_sha256':digest(raw['raw_generated_values']),'model_call_id':call[0],
        'ordinary_correct_policy_cache_not_new_method':True}
    immutable_json(AUDIT/'frozen_actual_reader_and_cache.json',frozen)
    reload=read(AUDIT/'frozen_actual_reader_and_cache.json')
    assert complete(source_theory(compile_source(reload['source'],reload['programme']),reload['actual_model_values'])).answer==reload['native_answer']
    costs={'new_executor_input_tokens':w['usage']['prompt_tokens'],'new_executor_output_tokens':w['usage']['completion_tokens'],
        'new_executor_elapsed_seconds':w['elapsed_seconds'],'new_executor_API_cash_usd':w['incremental_api_cash_usd'],
        'new_teacher_requests':0,'historical_teacher_cache_cost_not_removed':True,
        'GPU_cost_usd':None,'teacher_invoice_usd':None,'total_project_cash_usd':None,
        'client_retries':0,'provider_internal_teacher_retries_observable':False}
    delta={'new_model_calls':[{'id':call[0],'role':call[1],'purpose':call[2],'source':call[4],
            'request_hash':call[5],'status':call[6],'result':w}],
        'new_meta_policy_keys':[r[0] for r in added['meta']],
        'new_oracle_views':added['oracle_views'],'new_view_is_original_TRAIN83_not_a_counterfactual':True,
        'prior_rows_unchanged':True,'counts_before':{t:len(v) for t,v in before.items()},
        'counts_after':{t:len(v) for t,v in current.items()},'ledger_after_sha256':digest(current)}
    immutable_json(AUDIT/'request_and_view_ledger_delta.json',delta)
    report={'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':1,'teacher':0},'old_rows_preserved':True,
        'new_model_native_predictions_and_cached_grades':1,'source_ordinal':3,
        'actual_baseline_native_answer':'Entailment','native_correct':True,'fallback_n':0,'fallback_denominator':1,
        'baseline_native_task_consistent_with_citation_scope_gap':True,
        'generated_value_not_replaced_by_annotation_or_fallback':True,
        'quote_only_semantic_certificate':False,'citation_gap_fields':['b_after_employment_termination'],
        'original_full_source_executor_IR_denominator_unchanged':True,
        'source_rule_generated_by_previous_teacher_not_new_executor':True,
        'target83_actual_existing_model_fact_reuse_and_new_target_binding':target,
        'new_original_TRAIN83_cached_grade_views':1,'new_counterfactual_views':0,
        'new_sources_native_pairs_or_teacher_requests':0,
        'new_full_build_DEV_TEST_or_paper_started':False,'two_contributions_established':False,'goal_complete':False,
        'cold_frozen_replay_equal':True,'costs':costs,'current_counts':delta['counts_after'],
        'ledger_after_sha256':digest(current)}
    immutable_json(REPORT,report)
    backup=BEFORE.with_name('ledger.after.sqlite3')
    if not backup.exists():
        with sqlite3.connect(db) as a,sqlite3.connect(backup) as b:a.backup(b)
    assert snapshot(backup)==current and snapshot(db)==current
    print(json.dumps({k:report[k] for k in ['counts_total','new_charged_attempts','actual_baseline_native_answer','citation_gap_fields','new_original_TRAIN83_cached_grade_views','current_counts','goal_complete']},ensure_ascii=False))


if __name__=='__main__':main()
