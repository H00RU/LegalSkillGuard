"""Preserve actual check learning, strong controls and source-interface evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parent
FOLDER=ROOT/'artifacts/legal_skill_evolution_refutation_learning_20261113'
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def export():
    before=read(FOLDER/'ledger_before.json')['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        columns=[r[1] for r in db.execute('pragma table_info(calls)')]
        rows=[list(r) for r in db.execute('select * from calls order by id')]
    old={r[0]:r for r in before};now={r[0]:r for r in rows}
    assert all(now[k]==r for k,r in old.items())
    assert not any(r[6]=='reserved' for r in rows)
    added=[dict(zip(columns,r)) for r in rows if r[0] not in old]
    for r in added:r['result']=json.loads(r['result'])
    executor=[r for r in added if r['role']=='executor'];teacher=[r for r in added if r['role']=='teacher']
    assert all(r['result'].get('thinking_requested') is False for r in executor if r['status']=='completed')
    cost={'new_physical_requests':dict(Counter(r['role'] for r in added)),
        'cumulative':dict(Counter(r[1] for r in rows)),'pending':0,'total_rows':len(rows),
        'old_rows_unchanged':len(before),
        'ledger_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'requests':added,'executor_input_tokens':sum(r['result'].get('usage',{}).get('prompt_tokens',0) for r in executor),
        'executor_output_tokens':sum(r['result'].get('usage',{}).get('completion_tokens',0) for r in executor),
        'executor_elapsed_seconds':sum(r['result']['elapsed_seconds'] for r in executor),
        'teacher_input_tokens':sum(r['result']['invocation']['usage']['input_tokens'] for r in teacher),
        'teacher_output_tokens':sum(r['result']['invocation']['usage']['output_tokens'] for r in teacher),
        'teacher_reasoning_tokens_already_in_output':sum(r['result']['invocation']['usage']['reasoning_output_tokens'] for r in teacher),
        'teacher_elapsed_seconds':sum(r['result']['elapsed_seconds'] for r in teacher),
        'executor_incremental_API_cash_usd':0,'teacher_invoice_usd':None,'GPU_allocation_usd':None,
        'not_all_scope_or_source_values_semantically_certified':True,'goal_complete':False}
    write(DEST/'cost_and_preservation.json',cost)
    protocol=read(FOLDER/'fixed_validation/protocol.json');summaries=[]
    for arm in protocol['arms']:
        records=[read(FOLDER/'fixed_validation'/arm/(s.replace(':','_')+'.json')) for s in protocol['validation_sources']]
        views=[v for r in records for v in r['views']]
        events=[e for r in records for e in r['runtime']['events'] if 'result' in e]
        summaries.append({'arm':arm,'mother_sources':len(records),'native_views':len(views),
            'core_executed':sum(v['core_executed'] for v in views),
            'core_correct':sum(bool(v['score'] and v['score']['correct']) for v in views),
            'fallback':sum(v['fallback'] for v in views),'fallback_fraction':sum(v['fallback'] for v in views)/len(views),
            'exclusions':sum(len(v) for r in records for v in r['runtime']['exclusions'].values()),
            'logical_model_calls':len(events),'new_physical_model_calls':sum(not e['result'].get('cache_hit',False) for e in events),
            'logical_prompt_tokens':sum(e['result']['usage']['prompt_tokens'] for e in events),
            'logical_output_tokens':sum(e['result']['usage']['completion_tokens'] for e in events),
            'logical_service_seconds':sum(e['result']['elapsed_seconds'] for e in events),
            'actual_source_outputs_equal_NoChecks':all(r['runtime']['source_output']==read(FOLDER/'fixed_validation/NoChecks'/(r['source'].replace(':','_')+'.json'))['runtime']['source_output'] for r in records)})
    write(DEST/'comparison.json',{'arms':summaries,'shared_initial_acquisition_not_independent_initial_learning':True,
        'no_validation_based_method_repair':True,'fallback_not_executed':True,'goal_complete':False})
    for src in FOLDER.rglob('*.json'):
        rel=src.relative_to(FOLDER)
        if 'teacher_adapter_cache' in rel.parts or rel.name.startswith('ledger_'):continue
        dst=DEST/'raw'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    for src in FOLDER.rglob('*.py'):
        rel=src.relative_to(FOLDER)
        if not any(n in rel.parts for n in ['source_snapshot','representation_v1_archive','object_term_interface_archive']):continue
        dst=DEST/'frozen_source'/(str(rel)+'.txt');dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    return cost,summaries


if __name__=='__main__':
    c,s=export();print(json.dumps({'cost':{k:c[k] for k in ['new_physical_requests','cumulative','pending','old_rows_unchanged',
        'executor_input_tokens','executor_output_tokens','executor_elapsed_seconds','teacher_elapsed_seconds']},'comparison':s},ensure_ascii=False))
