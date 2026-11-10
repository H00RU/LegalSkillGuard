"""Audit actual Qwen call binding, cached native grades and frozen replay."""
import base64,hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_contract_norm_binding import compile_binding
from experiments.rr_v2_legal_independent_cache import execute_code
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
SOURCE=BASE/'contract_norm_binding_v1_20261110';STAGE=BASE/'contract_norm_binding_audit_v1_20261110'
BACKUP=Path('/media/sangfor/vdb/legal-skill-backups/contract_norm_binding_20261110')
REPORT=ROOT/'reports/method_redesign_20261109/contract_norm_binding_with_selector_results.json'


def read(path):return json.loads(path.read_text())


def ledger(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    dbpath=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before=ledger(BACKUP/'ledger.before.sqlite3');after=ledger(dbpath)
    assert all(r in after['calls'] for r in before['calls']) and all(r in after['meta'] for r in before['meta'])
    assert before['oracle_views']==after['oracle_views'] and not any(r[6]=='reserved' for r in after['calls'])
    delta=[r for r in after['calls'] if r not in before['calls']]
    assert len(delta)==1 and delta[0][0]=='contract_norm_binding_v1_20261110:binding' and delta[0][1]=='executor' and delta[0][6]=='completed'
    seal=read(SOURCE/'seal.json');raw=read(SOURCE/'execution_before_cached_grading.json');wire=raw['physical_response']
    assert wire['finish_reason']=='stop' and wire['thinking_requested'] is False and wire['reasoning_content'] is None and not wire['cache_hit']
    for path,sha in seal['files'].items():assert hashlib.sha256((SOURCE/'frozen'/path).read_bytes()).hexdigest()==sha
    parent_path=BASE/'contract_norm_cache_v1_20261110/source.json'
    assert hashlib.sha256(parent_path.read_bytes()).hexdigest()==seal['parent_source_sha256']
    callpaths=list((SOURCE/'calls').glob('*/wire_request.json'));assert len(callpaths)==1
    sent=read(callpaths[0]);body=base64.b64decode(sent['body_b64']);payload=json.loads(body)
    assert hashlib.sha256(body).hexdigest()==sent['body_sha256']
    assert payload['chat_template_kwargs']=={'enable_thinking':False}
    assert {k:payload[k] for k in ['temperature','top_p','top_k','seed','max_tokens']}=={'temperature':0.6,'top_p':0.95,'top_k':20,'seed':45,'max_tokens':8192}
    assert payload['messages']==seal['messages'] and payload['response_format']['json_schema']['schema']==seal['schema']
    bundle={'source_code':seal['source_code'],'interface':seal['interface'],'policies':seal['policy_calls'],
        'source_contracts':seal['source_contracts'],'material':seal['material'],'model_bindings':raw['value'],
        'parent_source_sha256':seal['parent_source_sha256'],
        'binding_response_sha256':hashlib.sha256((SOURCE/'execution_before_cached_grading.json').read_bytes()).hexdigest()}
    immutable_json(STAGE/'frozen_source_and_binding.json',bundle);restored=read(STAGE/'frozen_source_and_binding.json')
    interface={p['name']:p for p in restored['interface']};replays=[]
    grades_path=ROOT/'data/packets/rr_v2/grading_only/train.json';cached=read(grades_path)['sources']
    rows=[]
    for policy,material,original in zip(restored['policies'],restored['material'],raw['cases']):
        selected=restored['model_bindings']['bindings'][policy['policy_id']]
        query=compile_binding(selected,policy,interface)
        assert query==original['compiled_query'] and original['status']=='executed_pending_native_semantic_review'
        output=execute_code(restored['source_code'],[],query,[s['contract'] for s in restored['source_contracts']])
        assert output==original['execution'];replays.append({'ordinal':original['ordinal'],'query':query,'execution':output})
        source_id=seal['source_ids'][len(rows)];label=cached[source_id]['answer']
        # This is a native norm-statement reading, not a theorem that every
        # concrete object/context satisfies the source applicability predicate.
        route_matches_native_norm_view=query['predicate']==policy['normative_query']['predicate'] and query['positive'] is True
        rows.append({'ordinal':original['ordinal'],'source':source_id,'original_native_question':original['original_native_question'],
            'selected_entrypoint':query['predicate'],'selected_polarity':query['positive'],
            'native_norm_view_and_polarity_review':route_matches_native_norm_view,
            'answer':output['answer'],'original_cached_TRAIN_label':label,'native_correct':output['answer']==label,
            'main_cache_call_executed':True,'fallback_used':False,'cold_replay_equal':True,
            'source_arguments_copied_not_induced_by_executor':True,
            'scope_review':'Original native NLI interpretation; stored source actor/object/conduct remain unchanged. Especially for115, this does not assert universal equivalence of the source samples/prototypes/products domain to all objects in the original hypothesis.'})
    assert len(rows)==2 and all(r['native_correct'] and r['native_norm_view_and_polarity_review'] for r in rows)
    # Both questions are the same frozen native hypothesis, and the source
    # acquisition was already instructed to expose its norm-statement route.
    # An ordinary task-configured selector is therefore a necessary control.
    # It still executes the paid source cache; it does not return a label.
    assert len({m['original_native_question'] for m in restored['material']})==1
    deterministic=[]
    for policy,material in zip(restored['policies'],restored['material']):
        query=compile_binding({'entrypoint':policy['normative_query']['predicate'],'positive':True},policy,interface)
        output=execute_code(restored['source_code'],[],query,[s['contract'] for s in restored['source_contracts']])
        original=next(r for r in rows if r['ordinal']==material['original_TRAIN_ordinal'])
        deterministic.append({'ordinal':original['ordinal'],'query':query,'execution':output,
            'equal_actual_model_bound_output':output['answer']==original['answer'],
            'cached_native_label_match':output['answer']==original['original_cached_TRAIN_label']})
    assert all(r['equal_actual_model_bound_output'] and r['cached_native_label_match'] for r in deterministic)
    immutable_json(STAGE/'posthoc_task_bound_selector_control.json',{'rows':deterministic,
        'additional_model_calls':0,'source_program_acquisition_cost_not_removed':True,
        'selector_uses_given_task_and_source_routing_metadata_not_model_binding':True,
        'posthoc_same_known_TRAIN_cases_not_new_blind_effect':True,
        'does_not_cover_other_hypotheses_or_uncompiled_contracts':True,
        'no_default_native_answer_or_fallback_returned':True})
    immutable_json(STAGE/'native_grades_and_replay.json',{'cases':rows,'replays':replays,
        'known_original_TRAIN_not_fresh_blind_evaluation':True,
        'only_cached_TRAIN_labels_reused':True,'grade_file_sha256':hashlib.sha256(grades_path.read_bytes()).hexdigest(),
        'new_counterfactual_oracle_views':0,'new_method_contributions':0,'goal_complete':False})
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    order=seal['sources']['train'];mapped={r['source']:r for r in rows};statuses=[]
    for ordinal,key in enumerate(order,1):
        if public[key]['dataset']!='ContractNLI':continue
        row=mapped.get(key)
        statuses.append({'ordinal':ordinal,'source':key,'attempted_in_this_baseline':row is not None,
            'status':'native_binding_executed_and_matched' if row else 'not_attempted_outside_two_policy_cache',
            'answer':row['answer'] if row else None,'fallback_used':False if row else None,
            'unattempted_not_reclassified_as_model_error_or_success':row is None})
    assert len(statuses)==24
    immutable_json(STAGE/'original24_source_status.json',{'rows':statuses,'attempted':2,'native_correct':2,
        'unattempted':22,'fallback_n':0,'fallback_denominator':2,'not_whole_goal_method_coverage':True})
    meta_delta=[r for r in after['meta'] if r not in before['meta']]
    assert len(meta_delta)==1 and {k:len(v) for k,v in after.items()}=={'calls':1466,'meta':226,'oracle_views':136}
    source_cost=read(ROOT/'reports/method_redesign_20261109/contract_norm_cache_results.json')['costs']
    result={'counts_total':{role:sum(r[1]==role for r in after['calls']) for role in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':1,'teacher':0},'new_native_task_grades':2,
        'additional_posthoc_selector_native_grade_comparisons':2,
        'only_known_cached_TRAIN_labels_reused':True,'new_counterfactual_oracle_views':0,'new_sources':0,'new_native_pairs':0,
        'ordinary_source_cache_native_query_binding_n':2,'native_correct':2,'semantic_norm_route_review_passed':2,
        'fallback_n':0,'fallback_denominator':2,'original24_attempted':2,'original24_unattempted':22,
        'actual_executor_outputs_only_entrypoint_and_polarity':True,'arguments_from_acquired_cache':True,
        'posthoc_task_bound_selector_control_correct':2,'posthoc_task_bound_selector_control_n':2,
        'posthoc_selector_additional_model_calls':0,'same_control_still_uses_paid_source_cache':True,
        'call_binding_effect_beyond_task_configured_selector_not_established':True,
        'source_program_generated_by_previous_teacher':True,'executor_full_source_synthesis_not_tested':True,
        'automatic_event_reader_or_exception_subcondition_composition_not_tested':True,
        'query_view_definitions_supplied_not_learned':True,'two_known_positive_TRAIN_queries_not_generalization':True,
        'native_label_correctness_not_full_logical_domain_equivalence':True,
        'old_0of89_source_IR_history_not_changed_or_combined':True,'two_contributions_established':False,
        'old_rows_preserved':True,'ledger_counts':{k:len(v) for k,v in after.items()},
        'costs':{'input_tokens':wire['usage']['prompt_tokens'],'output_tokens':wire['usage']['completion_tokens'],
            'elapsed_seconds':wire['elapsed_seconds'],'executor_incremental_API_cash_usd':0,'GPU_allocation_usd':None,
            'retries':0,'thinking':False,'reasoning_content':None,'finish_reason':wire['finish_reason'],
            'source_acquisition_teacher_calls_previous_turn':1,'source_acquisition_seconds_previous_turn':source_cost['elapsed_seconds'],
            'source_plus_binding_seconds':source_cost['elapsed_seconds']+wire['elapsed_seconds'],
            'teacher_actual_invoice_usd':None,'total_project_cash_cost_usd':None,
            'no_cross_model_or_scope_causal_latency_advantage_claim':True},
        'TEST_or_DEV_labels_opened':False,'main_training_started':False,'goal_complete':False}
    immutable_json(REPORT,result)
    immutable_json(STAGE/'charged_delta.json',{'new_call_rows':delta,'new_policy_meta_keys':[r[0] for r in meta_delta],
        'all_old_call_and_meta_rows_preserved':True,'oracle_rows_unchanged':True})
    target=BACKUP/'ledger.after.sqlite3'
    if not target.exists():
        with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as db,sqlite3.connect(target) as dest:db.backup(dest)
    assert ledger(target)==after
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
