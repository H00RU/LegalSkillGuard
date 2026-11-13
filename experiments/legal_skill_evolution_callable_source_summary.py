"""Summarize the fixed trial and physical costs after all requests settle."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_source_trial import ARMS, OUT, ROOT
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def read(path):
    return json.loads(path.read_text())


def run():
    p=read(OUT/'protocol.json');stats={};records=[]
    for arm in ARMS:
        cases=[read(OUT/'execution'/arm/key.replace(':','_')/'result.json') for key in p['source_ids']]
        records.extend(cases)
        stats[arm]={'cases':len(cases),'core_executed':sum(r['core_executed'] for r in cases),
            'native_core_correct':sum(bool(r['native_score'] and r['native_score']['correct']) for r in cases),
            'fallback_required':sum(r['fallback_required'] for r in cases),
            'fallback_executed':sum(r['fallback_executed'] for r in cases),
            'native_semantics_review_not_automatically_certified_by_score':True}
    before=read(OUT/'ledger_before.json')['rows'];before_map={r[0]:r for r in before}
    db=sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)
    rows=[list(r) for r in db.execute('select * from calls order by id')]
    current={r[0]:r for r in rows}
    assert all(current[k]==row for k,row in before_map.items())
    assert not any(r[6]=='reserved' for r in rows)
    new=[r for r in rows if r[0] not in before_map]
    assert all(r[0].startswith(p['run_id']+':') for r in new)
    calls=[]
    for row in new:
        result=json.loads(row[8]);usage=result.get('usage',result.get('invocation',{}).get('usage',{}))
        calls.append({'id':row[0],'role':row[1],'source':row[4],'status':row[6],
            'request_hash':row[5],'usage':usage,'service_seconds':result.get('elapsed_seconds'),
            'finish_reason':result.get('finish_reason'),'physical_request_charged':True})
    summary={'same_goal':True,'goal_complete':False,'TRAIN_only_not_new_blind_TEST':True,
        'mother_case_count':len(p['source_ids']),'shared_main_law_count':1,'arms':stats,
        'raw_native_difference':stats['ProofSkills']['native_core_correct']-stats['IndependentCache']['native_core_correct'],
        'final_two_contribution_attribution':False,'two_contributions_established':False,
        'cost':{'new_physical_requests':dict(Counter(r[1] for r in new)),
            'cumulative':dict(Counter(r[1] for r in rows)),'rows':len(rows),'pending':0,
            'old_rows_unchanged':len(before),'ledger_sha256':digest(rows),'calls':calls,
            'teacher_cash_invoice_available':False,'executor_incremental_API_cash':0,
            'GPU_allocation_cash_unknown':True},
        'results':[{'source':r['source'],'arm':r['arm'],'answer':r['result']['answer'],
            'value':r['result']['value'],'core':r['core_executed'],'score':r['native_score'],
            'fallback_required':r['fallback_required'],'read_error':r['read_error']} for r in records],
        'semantic_review_separate_from_raw_native_scores':True,
        'no_expansion_or_repair_on_this_fixed_check_set':True}
    immutable_json(OUT/'stage_result.json',summary)
    print(json.dumps({k:summary[k] for k in ('arms','raw_native_difference')},ensure_ascii=False))
    print(json.dumps({k:v for k,v in summary['cost'].items() if k!='calls'},ensure_ascii=False))


if __name__=='__main__':run()
