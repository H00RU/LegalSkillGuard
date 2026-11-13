"""Export the finite residual-reader comparison without altering original data."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parent
FOLDER=ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113'
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def export():
    before=read(FOLDER/'ledger_before.json')['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        columns=[r[1] for r in db.execute('pragma table_info(calls)')]
        rows=[list(r) for r in db.execute('select * from calls order by id')]
    old={r[0]:r for r in before};now={r[0]:r for r in rows}
    assert all(now[k]==v for k,v in old.items())
    assert not any(r[6]=='reserved' for r in rows)
    added=[dict(zip(columns,r)) for r in rows if r[0] not in old]
    for r in added:r['result']=json.loads(r['result'])
    roles=Counter(r['role'] for r in added)
    executor=[r['result'] for r in added if r['role']=='executor']
    teacher=[r['result'] for r in added if r['role']=='teacher']
    assert len(executor)==53 and len(teacher)==2
    assert all(x['thinking_requested'] is False for x in executor)
    cost={'new_physical_requests':dict(roles),'cumulative':dict(Counter(r[1] for r in rows)),
        'pending':0,'total_rows':len(rows),'old_rows_unchanged':len(before),
        'ledger_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'requests':added,
        'executor_prompt_tokens':sum(x['usage']['prompt_tokens'] for x in executor),
        'executor_output_tokens':sum(x['usage']['completion_tokens'] for x in executor),
        'executor_elapsed_seconds':sum(x['elapsed_seconds'] for x in executor),
        'teacher_input_tokens':sum(x['invocation']['usage']['input_tokens'] for x in teacher),
        'teacher_output_tokens':sum(x['invocation']['usage']['output_tokens'] for x in teacher),
        'teacher_reasoning_tokens_already_in_output':sum(x['invocation']['usage']['reasoning_output_tokens'] for x in teacher),
        'teacher_elapsed_seconds':sum(x['elapsed_seconds'] for x in teacher),
        'executor_API_cash_usd':sum(x['incremental_api_cash_usd'] for x in executor),
        'teacher_invoice_usd':None,'GPU_allocation_usd':None,'goal_complete':False}
    write(DEST/'cost_and_preservation.json',cost)
    protocol=read(FOLDER/'fixed_validation/protocol.json');summary=[]
    for arm in protocol['arms']:
        records=[read(FOLDER/'fixed_validation'/arm/(s.replace(':','_')+'.json')) for s in protocol['validation_sources']]
        events=[e for r in records for e in r['runtime']['events'] if e['kind']=='neural']
        views=[v for r in records for v in r['views']]
        summary.append({'arm':arm,'mother_sources':len(records),'native_views':len(views),
            'core_executed':sum(v['core_executed'] for v in views),
            'core_native_correct':sum(bool(v['score'] and v['score']['correct']) for v in views),
            'fallback':sum(v['fallback'] for v in views),
            'fallback_fraction':sum(v['fallback'] for v in views)/len(views),
            'new_disposal_retention_target_correct':sum(bool(v['score'] and v['score']['correct']) for v in views if v['view'] in ['nda-16','nda-20']),
            'new_disposal_retention_target_total':sum(v['view'] in ['nda-16','nda-20'] for v in views),
            'logical_model_calls':len(events),'new_physical_model_calls':sum(not e['result'].get('cache_hit',False) for e in events),
            'logical_prompt_tokens':sum(e['result']['usage']['prompt_tokens'] for e in events),
            'logical_output_tokens':sum(e['result']['usage']['completion_tokens'] for e in events),
            'logical_service_seconds':sum(e['result']['elapsed_seconds'] for e in events),
            'residual_corrections':sum(r['runtime']['learned_corrections'] for r in records),
            'source_records':[{'source':r['source'],'core_correct':sum(bool(v['score'] and v['score']['correct']) for v in r['views']),
                'source_semantics_certified':False,'fallback':sum(v['fallback'] for v in r['views'])} for r in records]})
    equality=[]
    for source in protocol['validation_sources']:
        load=lambda arm:read(FOLDER/'fixed_validation'/arm/(source.replace(':','_')+'.json'))['runtime']['source_output']
        equality.append({'source':source,'Residual_equals_NoResidual':load('Residual')==load('NoResidual'),
            'Residual_equals_Seed':load('Residual')==load('Seed'),
            'Residual_equals_FreeReflection':load('Residual')==load('FreeReflection')})
    write(DEST/'comparison.json',{'arms':summary,'actual_source_output_equalities':equality,
        'same_initial_acquisition_independent_updates':True,'new_blind_TEST':False,
        'no_post_validation_repair':True,'first_contribution_established':False,'goal_complete':False})
    for src in FOLDER.rglob('*.json'):
        rel=src.relative_to(FOLDER)
        if 'teacher_adapter_cache' in rel.parts or rel.name.startswith('ledger_'):continue
        dst=DEST/'raw'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    for src in FOLDER.rglob('*.py'):
        rel=src.relative_to(FOLDER)
        if 'source_snapshot' not in rel.parts:continue
        dst=DEST/'frozen_source'/(str(rel)+'.txt');dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    return cost,summary,equality


if __name__=='__main__':
    c,s,e=export()
    print(json.dumps({'cost':{k:c[k] for k in ['new_physical_requests','cumulative','pending','old_rows_unchanged',
        'executor_prompt_tokens','executor_output_tokens','executor_elapsed_seconds','teacher_elapsed_seconds']},
        'summary':s,'equalities':e},ensure_ascii=False))
