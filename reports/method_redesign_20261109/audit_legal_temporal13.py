"""Audit real temporal programme/grounding failures, partial execution and costs."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
REPORT=ROOT/'reports/method_redesign_20261109'
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_fact_boundary_20261110/ledger.after.sqlite3')
NAMES=['legal_temporal13_v1_20261110','legal_temporal13_v2_20261110','legal_temporal13_v3_20261110','legal_temporal13_unguided_v1_20261110']
PARTIAL=BASE/'legal_partial_temporal13_v1_20261110'


def read(p):return json.loads(p.read_text())


def snapshot(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as d:
        return {t:d.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=snapshot(BEFORE);current=snapshot(DB);old=deepcopy(current)
    old['calls']=[r for r in old['calls'] if not any(r[0].startswith(n+':') for n in NAMES)]
    old['meta']=[r for r in old['meta'] if r[0] not in ['method_runtime_policy:'+n for n in NAMES]]
    grade=read(PARTIAL/'TRAIN_grade.json')
    if grade['new_oracle_views']:
        old['oracle_views']=[r for r in old['oracle_views'] if (r[0],r[1])!=(grade['source'],grade['view_hash'])]
    assert old==before
    added=[r for r in current['calls'] if any(r[0].startswith(n+':') for n in NAMES)]
    assert len(added)==5 and all(r[1]=='executor' and r[6]=='completed' for r in added)
    assert not [r for r in current['calls'] if r[6]=='reserved']
    source=read(BASE/NAMES[0]/'source.json');assert source['status']=='source_verified'
    failed=[read(BASE/n/'facts.json') for n in [NAMES[0],NAMES[1],NAMES[3]]]
    assert failed[0]['value']==failed[1]['value']
    assert failed[2]['value']['relationships_152_c_2'][0]['individual']=='Bob'
    assert failed[2]['value']['reported_birth_dates']==failed[0]['value']['reported_birth_dates']
    guided=read(BASE/NAMES[1]/'seal.json');unguided=read(BASE/NAMES[3]/'seal.json')
    assert guided['reader_messages']==unguided['messages'] and guided['config']==unguided['config']
    raw=read(BASE/NAMES[2]/'execution_closed_before_grading.json');execution=read(PARTIAL/'execution_closed_before_grading.json')
    assert raw['reader_fallback_used'] and raw['this_native_result_NOT_counted_as_core_method_validation']
    assert grade['correct'] and grade['direct_correct'] and len(execution['rows'])==3
    for row in execution['rows']:
        proof=row['partial_proof'];assert proof['answer']=='Contradiction'
        assert set(proof['proof_support'])=={'same_abode_days','tax_year_days'}
        assert proof['support_verified_over_all_other_input_values']
        assert all(v==[False,True] for v in proof['withhold_each_support_value'].values())
        assert row['unrestricted_narrative_view']['answer'] is None
        assert row['no_deterministic_replacement_frame_or_fallback_answer_used']
        assert 'age_at_year_end' not in proof['checked_bindings'] and 'younger_than_taxpayer' not in proof['checked_bindings']
    # Official source programme contains a partial relative-age default, NOT an
    # unconditional exemption from the separate absolute age<25 requirement.
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as a:
        name='sara_v2/statutes/prolog/section152.pl';raw152=a.extractfile(name).read();txt=raw152.decode()
    clause=txt.split('s152_c_3(Dependent,Taxp,Taxy) :-',1)[1].split('%(d) Qualifying relative',1)[0]
    assert 'is_descendent_of(Dependent,Taxp,_,_)' in clause and 'start_(Individual_is_born,Individual_dob)' in clause
    source_alignment={'original_TRAIN_ordinal':13,'four_conditions':['152(c)(2) relationship','more than half of year same principal abode','younger than taxpayer and age<25','no disallowed joint return'],
        'relationship_interval_years':[2015,2020],'reported_residence_interval':['2015-09-01','2019-02-03'],
        'verified_native_calendar_intersection_days':34,'calendar_year_days':365,
        'birth_dates_or_joint_return_NOT_reported':True,'marriage_not_joint_return':True,
        'reference_source_file':name,'reference_source_sha256':hashlib.sha256(raw152).hexdigest(),
        'reference_descendant_relative_age_default_exists':True,'default_does_NOT_make_whole_age_clause_automatically_true':True,
        'reference_defaults_NOT_imported_into_learned_source_program':True,
        'native_record_completeness_assumption_explicit':True,'unrestricted_narrative_view_unknown':True}
    wires=[json.loads(r[8]) for r in added]
    assert all(w['thinking_requested'] is False and w['finish_reason']=='stop' and w['reasoning_content'] in [None,''] for w in wires)
    copies={}
    for name in NAMES:
        stage=BASE/name;seal=read(stage/'seal.json');copied={}
        for p,h in seal['files'].items():
            saved=stage/'frozen'/p
            if saved.exists():assert hashlib.sha256(saved.read_bytes()).hexdigest()==h
            else:
                data=(ROOT/p).read_bytes();assert hashlib.sha256(data).hexdigest()==h
                saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(data)
            copied[p]=h
        copies[name]=copied
    partial_seal=read(PARTIAL/'seal.json')
    for p,h in partial_seal['files'].items():assert hashlib.sha256((PARTIAL/'frozen'/p).read_bytes()).hexdigest()==h
    rows=[]
    for row,w in zip(added,wires):
        rows.append({'id':row[0],'role':row[1],'status':row[6],'request_hash':row[5],
            'prompt_tokens':w['usage']['prompt_tokens'],'completion_tokens':w['usage']['completion_tokens'],
            'elapsed_seconds':w['elapsed_seconds'],'finish_reason':w['finish_reason'],'thinking_requested':False})
    existing_report=REPORT/'legal_temporal13_results.json'
    captured=read(existing_report)['captured_utc'] if existing_report.exists() else datetime.now(timezone.utc).isoformat()
    result={'captured_utc':captured,
        'counts_total':{r:sum(x[1]==r for x in current['calls']) for r in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':5,'teacher':0},'new_physical_dispatches':{'executor':5,'teacher':0},
        'new_TRAIN_oracle_views':grade['new_oracle_views'],'all_pre_turn_rows_equal_backup':True,
        'pre_turn_counts':{k:len(v) for k,v in before.items()},'current_counts':{k:len(v) for k,v in current.items()},
        'current_ledger_logical_sha256':digest(current),'all_pre_turn_rows_preserved_sha256':digest(old),
        'new_call_rows':rows,'source_only_actual_executor_programs_verified':1,
        'full_model_frames_valid':0,'model_frame_attempts_same_source':3,'frame_errors':[2,2,1],
        'matched_guided_to_unguided_messages_and_model_config_equal':True,
        'guided_removed_fixed_role_reversal_but_not_fabricated_birth':True,
        'source_alignment':source_alignment,'grade':grade,
        'native_source_count':1,'native_ordinary_source_programme_correct':1,'direct_same_information_correct':1,
        'partial_actual_model_evidence_execution_views':3,'not_three_independent_native_examples':True,
        'actual_field_values_not_repaired':True,'partial_proof_fallback_answers':0,
        'separate_deterministic_reader_fallback_results':1,'fallback_result_not_core_method_success':True,
        'shared_partial_binding_cache_matches':True,'partial_admission_is_correctness_gate_fix_not_new_contribution':True,
        'two_contributions_established':False,'goal_complete':False,'new_full_build_started':False,
        'TEST_labels_read':False,'paper_started':False,'bound_source_copies':copies,
        'executor_prompt_tokens':sum(w['usage']['prompt_tokens'] for w in wires),
        'executor_completion_tokens':sum(w['usage']['completion_tokens'] for w in wires),
        'executor_request_elapsed_seconds':sum(w['elapsed_seconds'] for w in wires),
        'executor_incremental_API_cash_usd':0,'GPU_cost_usd':None,'teacher_actual_cash_invoice_usd':None,
        'total_project_cash_cost_usd':None,'sampling_or_thinking_scan':False,'client_retries':0,
        'regressions':{'scalar_proof_tests':6,'calendar_and_unknown_input_assertions':8,'actual_bad_frame_and_literal_check_assertions':5}}
    immutable_json(REPORT/'legal_temporal13_results.json',result)
    immutable_json(PARTIAL/'source_condition_alignment.json',source_alignment)
    delta=[]
    for row in added:
        d=dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],row));d['result']=json.loads(d['result']);delta.append(d)
    immutable_json(PARTIAL/'request_ledger_delta.json',{'new_calls':delta,'new_oracle_views':grade['new_oracle_views']})
    path=Path('/media/sangfor/vdb/legal-skill-backups/legal_temporal13_20261110/ledger.after.sqlite3');path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with sqlite3.connect(DB) as a,sqlite3.connect(path) as b:a.backup(b)
    assert snapshot(path)==current
    print(json.dumps({k:result[k] for k in ['counts_total','pending','new_charged_attempts','new_TRAIN_oracle_views','executor_prompt_tokens','executor_completion_tokens','executor_request_elapsed_seconds','all_pre_turn_rows_equal_backup','source_only_actual_executor_programs_verified','full_model_frames_valid','native_source_count','native_ordinary_source_programme_correct','direct_same_information_correct']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
