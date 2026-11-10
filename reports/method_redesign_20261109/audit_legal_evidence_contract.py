"""Audit source guidance versus ordinary self-review, keeping truth and provenance apart."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import run
from experiments.rr_v2_legal_evidence_contract_v2 import source_units,normalize
from experiments.rr_v2_legal_auto_interface_fact_search import metadata

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BACK=Path('/media/sangfor/vdb/legal-skill-backups/legal_evidence_contract_20261110')
STAGE=BASE/'legal_evidence_contract_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_evidence_contract_results.json'
RUNS=['legal_evidence_contract_source_v1_20261110','legal_evidence_contract_ordinary_v1_20261110',
      'legal_evidence_contract_teacher_v2_20261110','legal_evidence_contract_review_v2_20261110','legal_evidence_contract_guided_v2_20261110']


def read(p):return json.loads(p.read_text())


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def review_reader(result,programme):
    expected={81:{('dependent',('Bob','Alice','2015')),('qualifying_child',('Bob','Alice','2015'))},
        86:{('qualifying_child',('Bob','Alice','2015')),('qualifying_child',('Charlie','Bob','2015'))},
        72:{('deduction_under_151_allowable_to',('Bob','Alice','2015'))}}
    grades={r['ordinal']:r['cached_TRAIN_grade'] for r in read(ROOT/'reports/method_redesign_20261109/legal_auto_interface_results.json')['native_results']}
    cases=[]
    for c in result['cases']:
        ordinal=c['ordinal'];primitive=[];materialized=[];structural=[];false_rows=[]
        for f in c['raw_case']['facts']:
            a=f['atom'];k=(a['predicate'],tuple(a['arguments']))
            if a['predicate']=='case_subject_year':primitive.append(f)
            elif a['positive'] and k in expected[ordinal]:primitive.append(f)
            elif a['predicate'] in ['different','taxable_year_begins_in_calendar_year','taxable_year_begins_in_2018_through_2025']:
                # Actual outputs here are about native2015, not a new general
                # date parser or a false-fact default. They are kept separate.
                structural.append(f)
            else:
                materialized.append(f)
                if ordinal==86 and a['positive'] and a['predicate'] in ['dependent','section_151c_applies','deduction_under_151_allowable_to'] and a['arguments']==['Charlie','Bob','2015']:
                    false_rows.append(f)
        case={**c['raw_case'],'facts':primitive,'query':c['query_reused_unchanged']}
        case['facts']=primitive+metadata(case)
        replay=run(programme,case);answer=replay['answer']
        if ordinal==86 and answer!='Entailment':answer=None
        cases.append({'ordinal':ordinal,'recorded_status':c['status'],'recorded_native_prediction':c.get('native_prediction'),
            'cached_TRAIN_grade':grades[ordinal],'recorded_native_label_matches':c.get('native_prediction')==grades[ordinal],
            'materialized_consequences_not_all_semantically_false':materialized,'actually_false_for_this_case':false_rows,
            'task_structural_or_period_classification_separate_from_legal_consequences':structural,
            'direct_premise_channel_clean':not materialized,'raw_model_frame_not_modified':True,
            'reviewed_primitive_subset':primitive,'reviewed_subset_case':case,'reviewed_subset_execution':replay,
            'reviewed_subset_native_prediction':answer,'reviewed_subset_native_correct':answer==grades[ordinal],
            'subset_selection_is_posthoc_independent_semantic_review_not_an_automatic_reader_or_format_adapter':True,
            'wrong_or_derived_values_not_filled_or_silently_changed':True})
    return {'native_correct':sum(r['recorded_native_label_matches'] for r in cases),'n':len(cases),
        'clean_direct_premise_channels':sum(r['direct_premise_channel_clean'] for r in cases),
        'semantically_false_assertion_count':sum(len(r['actually_false_for_this_case']) for r in cases),
        'reviewed_primitive_subset_native_correct':sum(r['reviewed_subset_native_correct'] for r in cases),
        'not_a_new_zero_inferred_fact_goal_acceptance_gate':True,'cases':cases}


def main():
    before=snapshot(BACK/'ledger.before.sqlite3');current=snapshot(DB);old=deepcopy(current)
    calls=[r for r in current['calls'] if any(r[0].startswith(n+':') for n in RUNS)]
    old['calls']=[r for r in old['calls'] if r not in calls]
    old['meta']=[r for r in old['meta'] if r[0] not in ['method_runtime_policy:'+n for n in RUNS]]
    assert old==before and len(calls)==5 and all(r[6]=='completed' for r in calls)
    assert not any(r[6]=='reserved' for r in current['calls'])
    source=read(BASE/RUNS[0]/'result.json');firstseal=read(BASE/RUNS[0]/'seal.json')
    entries=source['value']['entries'];api=firstseal['api'];badquotes=[];contradictions=[]
    for e in entries:
        if any(not q or not any(q in p['rules'] for p in firstseal['source_policies']) for q in e['source_quotes']):badquotes.append(e['predicate'])
        if any(len(normalize(q).split())>=6 and normalize(q) in normalize(e['direct_evidence']) for q in e['insufficient_evidence']):contradictions.append(e['predicate'])
    source_failure={'complete_stop_not_truncation':source['physical_response']['finish_reason']=='stop',
        'missing_API_entries':sorted({p['name'] for p in api}-{e['predicate'] for e in entries}),
        'entries_with_nonliteral_or_empty_source_quotes':badquotes,
        'entries_marking_the_same_long_assertion_sufficient_and_insufficient':contradictions,
        'amount_guidance_has_no_asserted_amount':not any(x in next(e for e in entries if e['predicate']=='exemption_amount')['direct_evidence'].lower() for x in ['amount a','amount of','$','zero']),
        'not_semantically_repaired_by_filling_coverage_or_whitespace':True,'not_used_for_guided_generation':True}
    assert len(badquotes)==14 and len(contradictions)==10
    teacher=read(BASE/RUNS[2]/'result.json');tseal=read(BASE/RUNS[2]/'seal.json');treview=read(BASE/RUNS[2]/'source_review.json')
    assert teacher['status']=='source_guidance_captured_pending_semantic_review' and treview['no_contract_entry_changed_by_reviewer']
    assert tseal['units']==source_units(tseal['source_policies'])
    for u in tseal['units']:
        policy=next(p for p in tseal['source_policies'] if p['section']==u['section'])
        assert policy['rules'][u['start_character']:u['end_character']]==u['text']
    p=read(BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json')['warm_program']
    readers={name:review_reader(read(BASE/runid/'result.json'),p) for name,runid in zip(['ordinary','ordinary_review','guided'],[RUNS[1],RUNS[3],RUNS[4]])}
    # Keep proof-bypass and actual exception inconsistency separate from label
    # correctness. They are diagnostic interventions, not extra native cases.
    first=read(BASE/RUNS[1]/'result.json');probes=[]
    for c in first['cases'][:2]:
        case={**c['raw_case'],'query':c['query_reused_unchanged'],'facts':c['raw_case']['facts']+c['metadata']};q=deepcopy(p)
        if c['ordinal']==81:
            q['rules']=[r for r in q['rules'] if r['head']['predicate']!='section_151c_applies'];ids={r['id'] for r in q['rules']};q['priorities']=[e for e in q['priorities'] if e['higher'] in ids and e['lower'] in ids]
        else:case['query']={'predicate':'dependent','arguments':['Charlie','Bob','2015'],'positive':True}
        execution=run(q,case);probes.append({'ordinal':c['ordinal'],'answer':execution['answer'],'execution':execution,'not_a_new_native_case_or_grade':True})
    assert [r['answer'] for r in probes]==['Entailment',None]
    costs={};delta=[]
    for r in calls:
        w=json.loads(r[8]);short=next(n for n in RUNS if r[0].startswith(n+':'))
        if r[1]=='executor':
            assert w['thinking_requested'] is False and w['finish_reason']=='stop' and w['reasoning_content'] in [None,'']
            usage={'input_tokens':w['usage']['prompt_tokens'],'output_tokens':w['usage']['completion_tokens']}
        else:
            assert w['invocation']['attempt']==1 and not w['invocation']['tool_events_detected'];usage=w['invocation']['usage']
        costs[short]={'role':r[1],'elapsed_seconds':w['elapsed_seconds'],**usage}
        d=dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],r));d['result']=w;delta.append(d)
    for runid in RUNS:
        s=read(BASE/runid/'seal.json')
        for path,h in s['files'].items():assert hashlib.sha256((BASE/runid/'frozen'/path).read_bytes()).hexdigest()==h
    frozen={'program':p,'readers':readers,'all_raw_frames_preserved':True,'independent_review_not_a_production_filter':True}
    immutable_json(STAGE/'frozen_reader_comparison.json',frozen);restored=read(STAGE/'frozen_reader_comparison.json')
    for results in restored['readers'].values():
        for c in results['cases']:assert run(restored['program'],c['reviewed_subset_case'])==c['reviewed_subset_execution']
    immutable_json(STAGE/'request_ledger_delta.json',{'new_calls':delta,'new_oracle_views':0})
    captured=read(REPORT)['captured_utc'] if REPORT.exists() else datetime.now(timezone.utc).isoformat()
    result={'captured_utc':captured,'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':4,'teacher':1},'new_physical_dispatches':{'executor':4,'teacher':1},
        'all_pre_turn_rows_equal_backup':True,'pre_turn_counts':{k:len(v) for k,v in before.items()},'current_counts':{k:len(v) for k,v in current.items()},
        'current_ledger_logical_sha256':digest(current),'new_original_sources':0,'new_native_grades':0,'new_oracle_views':0,
        'source_v1_failure':source_failure,'teacher_source_contract_count':len(teacher['value']['contracts']),
        'teacher_contract_case_free_and_no_authored_legal_status_mapping':True,'teacher_guidance_source_review':treview,
        'readers':readers,'ordinary_first_read_counterprobes':probes,'costs':costs,
        'source_acquisition_not_free_or_counted_as_native_success':True,
        'teacher_vs_executor_resources_not_matched_for_general_advantage_claim':True,
        'posthoc_reviewed_subset_not_autonomous_raw_frame_recovery':True,'frozen_subset_replay_equal':True,
        'two_method_contributions_established':False,'goal_complete':False,'main_training_started':False,'new_full_build_started':False,
        'TEST_labels_read':False,'paper_started':False,'executor_incremental_API_cash_usd':0,
        'teacher_actual_invoice_usd':None,'GPU_cost_usd':None,'total_project_cash_cost_usd':None}
    immutable_json(REPORT,result)
    after=BACK/'ledger.after.sqlite3'
    if not after.exists():
        with sqlite3.connect(DB) as a,sqlite3.connect(after) as b:a.backup(b)
    assert snapshot(after)==current
    print(json.dumps({'counts_total':result['counts_total'],'new_charged_attempts':result['new_charged_attempts'],
        'readers':{k:{a:v[a] for a in ['native_correct','n','clean_direct_premise_channels','semantically_false_assertion_count','reviewed_primitive_subset_native_correct']} for k,v in readers.items()},'costs':costs},ensure_ascii=False))


if __name__=='__main__':main()
