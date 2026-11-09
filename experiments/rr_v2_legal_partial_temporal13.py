"""Execute the real source programme using only checked parts of real frames.

This fixes an all-fields gate in the ordinary prototype. It does not turn the
shared symbolic kernel/evidence filtering into a claimed new contribution.
"""
import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from experiments.rr_v2_legal_temporal13 import ROOT, SIGNATURE, DOMAIN, REFERENCE, assess, literal_frame, union_days, read
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.partial_scalar_evidence import certify

BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_partial_temporal13_v1_20261110'
ORIGINAL=BASE/'legal_temporal13_v1_20261110'
READERS=['legal_temporal13_v1_20261110','legal_temporal13_v2_20261110','legal_temporal13_unguided_v1_20261110']
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def project(frame,facts,year):
    # Reference surface parser is an independent checker only. Every asserted
    # event/date/participant below comes from the unchanged REAL model frame.
    reference=literal_frame(facts); checked={}; quarantine=[]
    checked['tax_year_days']={'value':(date(year+1,1,1)-date(year,1,1)).days,
                             'evidence':{'origin':'native_query_calendar_year','year':year}}
    residence=frame['co_residence_intervals']
    if residence == reference['co_residence_intervals']:
        checked['same_abode_days']={'value':union_days([(r['start'],r['end']) for r in residence],year),
            'evidence':{'origin':'actual_model_frame_verified_against_own_source_sentences','raw_model_events':residence,
                        'native_complete_event_record_normalization':True}}
    else:quarantine.append({'field':'co_residence_intervals','raw_claim':residence,'reason':'Source/date/participant/record inventory mismatch; no residence bound admitted'})
    rel=frame['relationships_152_c_2']
    if rel == reference['relationships_152_c_2'] and any(r['start_year']<=year<=r['end_year'] for r in rel):
        checked['relationship_152_c_2']={'value':True,'evidence':{'origin':'actual_model_relation_matches_its_own_source_clause','raw_model_events':rel}}
    elif rel:quarantine.append({'field':'relationships_152_c_2','raw_claim':rel,'reason':'Role/year/source mismatch; complete relationship condition stays unknown'})
    if frame['reported_birth_dates']:
        quarantine.append({'field':'reported_birth_dates','raw_claim':frame['reported_birth_dates'],
            'reason':'No dated birth event is in the original case. Age/younger remain unknown; no claim repaired or deleted in the raw frame.'})
    if frame['reported_joint_returns']:
        quarantine.append({'field':'reported_joint_returns','raw_claim':frame['reported_joint_returns'],
            'reason':'No joint-return event is in the original case. Marriage is not a return; condition stays unknown.'})
    return checked,quarantine


def execute():
    if (STAGE/'execution_closed_before_grading.json').exists():print('Existing immutable partial execution');return
    s=read(ORIGINAL/'seal.json');source=read(ORIGINAL/'source.json');assert source['status']=='source_verified'
    case=s['case'];year=int(re.search(r'year (\d{4})\.',case['public']['query'])[1])
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_partial_temporal13.py','legal_skill_guard/rr/partial_scalar_evidence.py',
        'experiments/rr_v2_legal_temporal13.py','legal_skill_guard/rr/semantic_contracts.py','tests/test_rr_partial_scalar_evidence.py')}
    immutable_json(STAGE/'seal.json',{'files':files,'source':case['key'],'original_TRAIN_ordinal':13,
        'source_programme_file_sha256':hashlib.sha256((ORIGINAL/'source.json').read_bytes()).hexdigest(),
        'uses_actual_existing_model_programme_and_frame_values':True,'new_model_calls':0,'goal_complete':False})
    library={'expression':source['compiled']['expression'],'signature':SIGNATURE,'domain':DOMAIN}
    immutable_json(STAGE/'frozen_library.json',library);restored=read(STAGE/'frozen_library.json')
    rows=[]
    for name in READERS:
        record=read(BASE/name/'facts.json');frame=record['value'];checked,quarantine=project(frame,case['public']['facts'],year)
        proof=certify(restored['expression'],restored['signature'],restored['domain'],checked,quarantined=quarantine)
        assert proof['answer']=='Contradiction' and set(proof['proof_support'])=={'same_abode_days','tax_year_days'}
        assert all(values==[False,True] for values in proof['withhold_each_support_value'].values())
        # Unrestricted narrative does not establish an upper bound on ALL abode
        # days; record this reading explicitly, rather than an unconditional proof.
        open_reading=certify(restored['expression'],SIGNATURE,DOMAIN,
                             {k:v for k,v in checked.items() if k!='same_abode_days'},quarantined=quarantine)
        assert open_reading['answer'] is None
        independent=assess(restored['expression'],{k:checked[k]['value'] if k in checked else None for k in SIGNATURE})
        assert independent['answer']==proof['answer']
        rows.append({'reader_run':name,'actual_raw_frame_sha256':hashlib.sha256((BASE/name/'facts.json').read_bytes()).hexdigest(),
            'whole_frame_still_rejected':True,'partial_proof':proof,'unrestricted_narrative_view':open_reading,
            'actual_unchanged_model_residence_values_used':True,'no_values_taken_from_bad_or_missing_fields':True,
            'no_deterministic_replacement_frame_or_fallback_answer_used':True,'raw_frame_not_repaired':True,
            'ordinary_partial_binding_cache_same_answer':independent['answer'],
            'new_learned_mechanism_claim':False})
    result={'source':case['key'],'original_TRAIN_ordinal':13,'prediction':'Contradiction','rows':rows,
        'independent_native_sources':1,'reader_attempts_same_source_not_three_native_examples':True,
        'source_generation_actual_Qwen_IR':True,'source_role_API_provided_not_learned':True,
        'needed_evidence_only_residence_days_and_query_calendar':True,
        'source_case_normalization_assumption':'Original native complete residence-event record; unrestricted narrative remains unknown.',
        'shared_correctness_component_not_novel_contribution':True,
        'strict_frame_gate_was_overbroad_for_a_query_with_a_verified_countercondition':True,
        'invalid_observations_excluded_not_made_true_or_false':True,
        'source_rule_semantics_checks_unchanged':True,'prediction_closed_before_grade':True,
        'new_model_calls':0,'goal_complete':False}
    immutable_json(STAGE/'execution_closed_before_grading.json',result)
    for p,h in files.items():
        data=(ROOT/p).read_bytes();assert hashlib.sha256(data).hexdigest()==h
        target=STAGE/'frozen'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print(json.dumps({'source':case['key'],'native_sources':1,'reader_frames':len(rows),'prediction':result['prediction'],
        'proof_support':list(rows[0]['partial_proof']['proof_support']),'fallback_answers':0,'new_models':0,'new_method_contribution':False},ensure_ascii=False,indent=2))


def grade():
    if (STAGE/'TRAIN_grade.json').exists():print('Existing immutable TRAIN grade');return
    seal=read(STAGE/'seal.json');result=read(STAGE/'execution_closed_before_grading.json')
    for p,h in seal['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:
        assert c.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
        policy=json.loads(c.execute("select value from meta where key='method_runtime_policy:legal_temporal13_v3_20261110'").fetchone()[0])
    ledger=MethodLedger(DB,run_id=policy['run_id'],binding=policy['execution_binding'],sources=policy['sources'],authorization_hash=policy['authorization_hash'],question=policy['question'])
    view={'kind':'SARA_v2_Binary','edit':None};vh=digest(view)
    with ledger.transaction() as c:prior=bool(c.execute('select 1 from oracle_views where source=? and view_hash=?',(seal['source'],vh)).fetchone())
    if not prior:ledger.reserve_oracle(seal['source'],vh)
    gold=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][seal['source']]['answer']
    direct=read(BASE/'legal_temporal13_v3_20261110/direct.json')['value']
    out={'source':seal['source'],'original_TRAIN_ordinal':13,'gold':gold,'prediction':result['prediction'],
         'correct':result['prediction']==gold,'direct_prediction':direct['answer'],'direct_correct':direct['answer']==gold,
         'both_predictions_frozen_before_grade':True,'view_hash':vh,'compatible_prior_view_reused':prior,
         'new_oracle_views':int(not prior),'new_model_calls':0,'TEST_labels_read':False,'goal_complete':False}
    immutable_json(STAGE/'TRAIN_grade.json',out)
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['execute','grade']);a=p.parse_args().action
    execute() if a=='execute' else grade()
