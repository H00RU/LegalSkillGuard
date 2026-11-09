"""Necessary offline integrity regression for this real-data pilot; no calls."""
from datetime import datetime
import hashlib
import json
from experiments.rr_v2_semantic_learning import ROOT, STAGE, REPORT, check_frozen, read
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.semantic_frames import decode_frame


def main():
    f=check_frozen();seal=read(STAGE/'seal.json');closure=read(STAGE/'execution_closed_before_grading.json')
    forecast=read(STAGE/'blind_predictions.json');frozen_time=datetime.fromisoformat(forecast['captured_utc'])
    closed_time=datetime.fromisoformat(closure['captured_utc']); checks=[]
    for c in seal['cases']:
        if c['fold']=='induction':
            observations=[]
            for mode in ('direct','reader'):
                d=read(STAGE/'responses'/mode/(digest(c['case_id'])+'.json'))
                v=json.loads(d['physical_response']['content'])
                names=('work_is_agricultural','payment_is_agricultural_product') if mode=='direct' else ('agricultural_remuneration','payment_in_agricultural_products')
                observations.extend(2 if v[n] is None else int(v[n]) for n in names)
            assert observations==next(r for r in f['training_rows'] if r['case_id']==c['case_id'])['y']
            checks.append('actual_training_record_matches_fit:'+c['case_id'])
        else:
            for mode in ('direct','reader','retrieval'):
                d=read(STAGE/'responses'/mode/(digest(c['case_id'])+'.json'))
                assert frozen_time<datetime.fromisoformat(d['captured_utc'])<closed_time
                assert d['physical_response']['thinking_requested'] is False
                checks.append('blind_order_and_OFF:'+c['case_id']+':'+mode)
            t=read(STAGE/'teacher'/(digest(c['source'])+'.json'))
            assert closed_time<datetime.fromisoformat(t['physical_response']['invocation']['started_at'])
    c=next(c for c in seal['cases'] if c['case_id']=='TRAIN83:original')
    record=read(STAGE/'responses/direct'/(digest(c['case_id'])+'.json'))
    assert record['validation']['status']=='rejected'
    try:decode_frame(json.loads(record['physical_response']['content']),c['facts'])
    except ValueError as e:assert 'money' in str(e)
    else:raise AssertionError('Invented money pointer was accepted')
    assert closure['decisions'][c['case_id']]['source_span_acceptance']['direct'] is False
    checks.append('real_money_pointer_remains_rejected')
    rows=read(REPORT/'M1M2_real_TRAIN_results.json')['rows']
    assert all(r['joint_inference']['structured']['semantic_answer'] is None for r in rows)
    assert len(rows)==4 and len({r['mother'] for r in rows})==2
    checks.extend(['MAP_never_semantic_certificate','four_cases_are_two_mothers','excluded_grading_after_execution'])
    out={'passed':len(checks),'checks':checks,'new_model_calls':0,'frozen_learning_unchanged':True,
         'frozen_model_parameters_sha256':hashlib.sha256(json.dumps(f['models'],sort_keys=True).encode()).hexdigest()}
    (REPORT/'M1M2_evidence_integrity.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))


if __name__=='__main__':main()
