"""Test actual paid TRAIN3 teacher caches without dispatch or label repair.

Native annotation-derived premises below are explicitly a reference-only arm,
never a model reader, free semantic adaptation, or same-input accuracy trial.
Partial Boolean completions exercise the actual stored AST, not new cases.
"""
from itertools import product
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import complete, digest
from legal_skill_guard.rr.pal_frontend import lower_pal
from legal_skill_guard.rr.source_program import compile_source, source_theory

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'train3_cached_condition_control_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/train3_cached_condition_results.json'
SHORT='reference_pal_teacher_sara3_v2_20261108:compile'
FULL='reference_pal_teacher_sara3_full_v3_20261108:compile'
AFTER='b_after_employment_termination'
DEATH='b_termination_death'
RETIRE='b_retirement_for_disability'


def read(p):return json.loads(p.read_text())


def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def labels(values):
    values=set(values)
    return next(iter(values)) if len(values)==1 else None


def reference(observed):
    completions=[]
    for after,death,retire in product((False,True),repeat=3):
        row=dict(zip((AFTER,DEATH,RETIRE),(after,death,retire)))
        if any(v is not None and row[k]!=v for k,v in observed.items()):continue
        completions.append('Entailment' if after and (death or retire) else 'Contradiction')
    return labels(completions)


def main():
    before=snapshot();assert not [r for r in before['calls'] if r[6]=='reserved']
    old=read(BASE/'native_subclause3_audit_v1_20261110/evidence.json')
    source=old['original_source_packet'];assert source['key'] in read(BASE/'redesign_source_roles_v1_20261109/seal.json')['sources']['train']
    saved={r[0]:json.loads(r[8]) for r in before['calls'] if r[0] in (SHORT,FULL)}
    items={}
    for cid in (SHORT,FULL):
        raw=saved[cid];code=raw['value']['code'];programme,adaptation=lower_pal(source,code)
        compiled=compile_source(source,programme)
        items[cid]={'code':code,'code_sha256':hashlib.sha256(code.encode()).hexdigest(),
            'paid_request_sha256':raw['request_sha256'],'paid_response_sha256':raw['response_sha256'],
            'programme':programme,'format_adaptation':adaptation,
            'query_dependencies':sorted(compiled['query'].completion_dependencies()),
            'source_coverage_count':len(compiled['covered']),
            'declared_observations':list(compiled['observations'].values()),
            'teacher_received_case_and_question':True,'new_physical_generation':False,
            'compiled':compiled}
    c=items[FULL]['compiled'];assert set(c['query'].completion_dependencies())=={AFTER,DEATH,RETIRE}
    rows=[]
    for values in product((None,False,True),repeat=3):
        bindings=dict(zip((AFTER,DEATH,RETIRE),values))
        th=source_theory(c,bindings);done=complete(th);expected=reference(bindings)
        assert done.answer==expected
        assert not any(r.unknown_scope for r in th.residuals)
        assert done.status==('translation_unresolved' if expected is None else 'completion_stable'),done.status
        if expected is None:assert done.reason=='different-answer completions'
        rows.append({'supplied_software_conditions':bindings,'actual_answer':done.answer,'expected':expected,
            'actual_status':done.status,'projection':done.projection,
            'native_case_or_additional_hypothesis':False})
    # Same original native proof as the prior audit, with explicit role/time
    # annotation provenance. It is not furnished to a new model or production
    # prediction path, and absence of death is never made false.
    ref_inputs={AFTER:True,RETIRE:True}
    th=source_theory(c,ref_inputs);done=complete(th)
    assert done.status=='completion_stable' and done.answer==old['already_cached_original_TRAIN_grade']['answer']
    deletion={}
    for name in ref_inputs:
        reduced={k:v for k,v in ref_inputs.items() if k!=name}
        result=complete(source_theory(c,reduced));assert result.answer is None
        deletion[name]={'answer':result.answer,'status':result.status}
    ref_run={'given_reference_conditions':ref_inputs,'actual_answer':done.answer,'status':done.status,
        'cached_original_native_label_match':True,'not_a_new_model_prediction_or_same_information_trial':True,
        'observations_are_native_annotation_derived_not_a_model_frame':True,
        'after_payment_support':{'employment_end':'2019-10-10','payment_start':'2019-10-10',
            'origin':'Original TRAIN3 annotation; exact payment day not stated in public prose.'},
        'retirement_support':{'retirement_event':'retired','agent':'Bob','reason':'disability',
            'origin':'Already inspected original TRAIN3 annotation and corresponding public retired/disability sentence.'},
        'no_false_default_for_death':DEATH not in ref_inputs,
        'other_observations_and_plan_conditions_remain_unknown':True,
        'minimal_reference_support_deletions':deletion,'projection':done.projection}
    short=items[SHORT]['compiled']
    short_result=complete(source_theory(short,{'b_employer_payment':True,'b_disability_retirement_termination':True}))
    assert short_result.status=='translation_unresolved' and short_result.answer is None
    short_control={'status':short_result.status,'answer':short_result.answer,'reason':short_result.reason,
        'whole_source_contract_keeps_untranslated_units_TOP':True,
        'not_a_new_Goal_requirement_for_every_module_to_compile_all_source':True,
        'not_accepted_by_ignoring_unknown_source_obligations':True}
    for item in items.values():item.pop('compiled')
    frozen={'source':source,'actual_paid_teacher_caches':items,'full_cache_software_partial_cases':rows,
        'reference_only_original_TRAIN3_execution':ref_run,'target_only_cache_conservative_whole_source_status':short_control,
        'originating_native_audit_evidence_sha256':hashlib.sha256((BASE/'native_subclause3_audit_v1_20261110/evidence.json').read_bytes()).hexdigest(),
        'same_source_correct_cache_available_by_exact_statute_and_target':True,
        'not_cross_source_or_held_out_error_repair_generalization':True,
        'no_old_failed_Qwen_code_fixed_or_old_score_changed':True}
    immutable_json(STAGE/'frozen_control.json',frozen)
    assert snapshot()==before
    report={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'pending':0,'new_model_calls':0,'new_oracle_views':0,'new_native_pairs':0,
        'new_model_native_predictions_or_grades':0,'ledger_rows_unchanged':True,'ledger_logical_sha256':digest(before),
        'actual_existing_full_teacher_cache_compiles':True,'software_partial_condition_cases':len(rows),
        'reference_only_original_TRAIN3_support_size':len(ref_inputs),
        'existing_cache_computes_original_A_when_native_premises_supplied':True,
        'shared_symbolic_query_projection_already_sufficient':True,
        'model_reader_for_that_cache_not_established':True,
        'cached_B_or_other_source_conditions_not_filled':True,
        'target_only_cache_not_misrepresented_as_whole_source_certificate':True,
        'source_rule_generation_error_not_an_identified_new_repair_algorithm':True,
        'independent_advantage_over_correct_policy_cache_not_established':True,
        'scope_of_error_repair_retrieval':'Exact same-source correct cache exists. No other original A query supplies an independent native reuse test; self retrieval is not generalization.',
        'do_not_generate_more_same_case_repair_trials_without_a_distinct_mechanism':True,
        'teacher_programme_does_not_itself_acquire_event_facts_from_public_case':True,
        'TEST_DEV_full_training_or_paper_started':False,'two_contributions_established':False,'goal_complete':False,
        'evidence_path':str((STAGE/'frozen_control.json').relative_to(ROOT))}
    immutable_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','software_partial_condition_cases','reference_only_original_TRAIN3_support_size','model_reader_for_that_cache_not_established','goal_complete']},ensure_ascii=False))


if __name__=='__main__':main()
