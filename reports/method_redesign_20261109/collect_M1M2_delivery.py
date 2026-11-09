"""Read-only physical ledger, frozen-file and prior-stage preservation audit."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from experiments.rr_v2_semantic_learning import ROOT, REPORT, STAGE, check_frozen, read
from legal_skill_guard.rr.checkpoint import immutable_json


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    check_frozen()
    ledger=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before=Path('/media/sangfor/vdb/legal-skill-backups/method_redesign_20261109_start/ledger.sqlite3')
    with sqlite3.connect('file:'+str(ledger.resolve())+'?mode=ro',uri=True) as db:
        db.execute('begin'); rows=db.execute('select * from calls order by reserved_at,id').fetchall()
        meta=dict(db.execute('select * from meta'));oracle=db.execute('select * from oracle_views order by source,view_hash').fetchall()
    with sqlite3.connect('file:'+str(before)+'?mode=ro',uri=True) as db:
        prior=db.execute('select * from calls order by reserved_at,id').fetchall();oldmeta=dict(db.execute('select * from meta'))
        oldoracle=db.execute('select * from oracle_views order by source,view_hash').fetchall()
    current={r[0]:r for r in rows}; assert all(current[r[0]]==r for r in prior)
    assert all(meta[k]==v for k,v in oldmeta.items());assert oracle==oldoracle
    delta=[r for r in rows if r[0] not in {r[0] for r in prior}]
    counts={role:sum(r[1]==role for r in rows) for role in ('executor','teacher')}
    assert not any(r[6]=='reserved' for r in rows)
    base=read(REPORT/'baseline.json'); efficacy=ROOT/'artifacts/rr_method_efficacy_20261109'
    for rel,h in base['previous_efficacy_artifacts'].items():assert sha(efficacy/rel)==h,rel
    # Baseline exact snapshots of the previous stage are held in the existing
    # prior efficacy audit. Verify rather than mutate any old result.
    oldfiles=0
    audit=ROOT/'reports/method_efficacy_20261109/cost_and_preservation.json'
    if audit.exists():
        d=read(audit)
        preserved=d.get('original_artifacts',{})
        if isinstance(preserved,dict):
            for rel,h in preserved.items():
                assert sha(ROOT/'artifacts/rr_method_runtime_20261107'/rel)==h;oldfiles+=1
    seals=0;archived=[]
    for p in (ROOT/'artifacts/rr_method_redesign_20261109').rglob('seal.json'):
        s=read(p)
        for rel,h in s.get('files',{}).items():
            if sha(ROOT/rel)!=h:
                frozen=p.parent/'source_versions'/h/Path(rel).name
                assert frozen.exists() and sha(frozen)==h,rel
                archived.append({'seal':str(p.relative_to(ROOT)),'source':rel,'sha256':h,
                                 'exact_preserved_source':str(frozen.relative_to(ROOT))})
            else:seals+=1
    for name in ('cost_snapshot.json','preservation.json','request_ledger_delta.json'):
        p=REPORT/name;dest=REPORT/(p.stem+'.checkpoint01.json')
        if p.exists() and not dest.exists():shutil.copyfile(p,dest)
    calls=[]
    for r in delta:
        value=json.loads(r[8]) if r[8] else {};wire=value
        # Client terminal records themselves carry the physical response.
        usage=wire.get('usage',wire.get('invocation',{}).get('usage'))
        calls.append({'id':r[0],'role':r[1],'purpose':r[2],'source':r[4],'status':r[6],
            'reserved_at':r[7],'request_hash':r[5],'elapsed_seconds':wire.get('elapsed_seconds'),
            'usage_raw':usage,'thinking_requested':wire.get('thinking_requested'),
            'finish_reason':wire.get('finish_reason'), 'cash_invoice_usd':0 if r[1]=='executor' else None})
    pilot=[c for c in calls if c['id'].startswith('semantic_disambiguation_acquisition_v1_20261109:')]
    cost={'captured_utc':datetime.now(timezone.utc).isoformat(),'baseline_counts':base['baseline_counts'],
          'counts_total':counts,'pending':0,'new_charged_calls':len(delta),'ledger_reset':False,
          'executor_incremental_API_cash_usd':0,'teacher_invoice_usd':None,'GPU_allocation_usd':None,
          'cash_note':'Executor uses the existing local GPU service, no per-request API charge; teacher subscription/GPU allocation invoices unavailable. Unknown costs are not reported as zero.',
          'calls':calls,'pilot_counts':{role:sum(c['role']==role for c in pilot) for role in ('executor','teacher')},
          'pilot_executor_seconds':sum(c['elapsed_seconds'] or 0 for c in pilot if c['role']=='executor'),
          'pilot_teacher_seconds':sum(c['elapsed_seconds'] or 0 for c in pilot if c['role']=='teacher'),
          'current_goal_complete':False}
    for role in ('executor','teacher'):
        group=[c for c in pilot if c['role']==role];totals={}
        for c in group:
            for k,v in (c['usage_raw'] or {}).items():
                if isinstance(v,(int,float)):totals[k]=totals.get(k,0)+v
        cost['pilot_'+role+'_usage']=totals
    scope=[c for c in calls if c['id'].startswith('payment_scope_native_input_')]
    cost['payment_scope_counts']={role:sum(c['role']==role for c in scope) for role in ('executor','teacher')}
    cost['payment_scope_calls']=scope
    for role in ('executor','teacher'):
        group=[c for c in scope if c['role']==role];usage={}
        for c in group:
            for k,v in (c['usage_raw'] or {}).items():
                if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
        cost['payment_scope_'+role+'_usage']=usage
        cost['payment_scope_'+role+'_seconds']=sum(c['elapsed_seconds'] or 0 for c in group)
    probe=[c for c in calls if c['id'].startswith('M2_discriminating_cash_probe_20261109:')]
    cost['M2_discriminating_probe_counts']={role:sum(c['role']==role for c in probe) for role in ('executor','teacher')}
    cost['M2_discriminating_probe_calls']=probe
    for role in ('executor','teacher'):
        group=[c for c in probe if c['role']==role];usage={}
        for c in group:
            for k,v in (c['usage_raw'] or {}).items():
                if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
        cost['M2_discriminating_probe_'+role+'_usage']=usage
        cost['M2_discriminating_probe_'+role+'_seconds']=sum(c['elapsed_seconds'] or 0 for c in group)
    preservation={'captured_utc':cost['captured_utc'],'prior_call_rows_exactly_preserved':len(prior),
          'prior_meta_values_exactly_preserved':len(oldmeta),'oracle_rows_exactly_preserved':len(oracle),
          'previous_efficacy_files_unchanged':len(base['previous_efficacy_artifacts']),
          'old_stage_files_newly_rehashed':oldfiles,'old_stage_previous_verification_preserved':True,
          'current_generation_bound_files_unchanged':seals,'frozen_learning_and_blind_predictions_unchanged':True,
          'previous_generation_bound_files_exactly_preserved_in_source_versions':archived,
          'new_calls':len(delta),'new_goal_active':True,'TEST_started':False,'paper_started':False,
          'new_full_build_started':False,'main_targeted_by_changes':False}
    (REPORT/'cost_snapshot.json').write_text(json.dumps(cost,ensure_ascii=False,indent=2)+'\n')
    (REPORT/'preservation.json').write_text(json.dumps(preservation,ensure_ascii=False,indent=2)+'\n')
    (REPORT/'request_ledger_delta.json').write_text(json.dumps({'captured_utc':cost['captured_utc'],
        'columns':['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],
        'calls':delta,'counts_total':counts,'pending':0,'origin_ledger_reset':False,'private_meta_exported':False},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'counts':counts,'new_calls':len(delta),'pilot_counts':cost['pilot_counts'],
                     'pilot_executor_seconds':cost['pilot_executor_seconds'],'pilot_teacher_seconds':cost['pilot_teacher_seconds'],
                     'preservation':preservation},ensure_ascii=False))


if __name__=='__main__':main()
