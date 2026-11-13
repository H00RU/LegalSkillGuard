"""Preserve this finite source-influence acquisition and real offline results."""
from collections import Counter
import hashlib,json,sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
FOLDER=ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113'


def export():
    old=json.loads((FOLDER/'execution/ledger_before.json').read_text())['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        columns=[r[1] for r in db.execute('pragma table_info(calls)')]
        rows=[list(r) for r in db.execute('select * from calls order by id')]
    previous={r[0]:r for r in old};now={r[0]:r for r in rows}
    assert all(now[k]==r for k,r in previous.items())
    added=[dict(zip(columns,r)) for r in rows if r[0] not in previous]
    assert len(added)==1 and added[0]['role']=='teacher' and added[0]['status']=='completed'
    assert not any(r[6]=='reserved' for r in rows)
    requests=[{**r,'result':json.loads(r['result'])} for r in added]
    cost={'new_physical_requests':{'executor':0,'teacher':1},
        'cumulative':{role:sum(r[1]==role for r in rows) for role in ['executor','teacher']},
        'pending':0,'total_rows':len(rows),'old_rows_unchanged':len(old),
        'ledger_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'requests':requests,'teacher_known_usage':requests[0]['result']['invocation']['usage'],
        'teacher_elapsed_seconds':requests[0]['result']['elapsed_seconds'],
        'executor_incremental_API_cash_usd':0,'teacher_invoice_usd':None,'GPU_allocation_usd':None,
        'preflight_namespace_error_physical_requests':0,'goal_complete':False}
    (OUT/'cost_and_preservation.json').write_text(json.dumps(cost,ensure_ascii=False,indent=2)+'\n')
    for src in FOLDER.rglob('*.json'):
        rel=src.relative_to(FOLDER)
        if 'teacher_adapter_cache' in rel.parts or rel.name.startswith('ledger_'):continue
        dst=OUT/'raw'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    for src in FOLDER.rglob('*.py'):
        rel=src.relative_to(FOLDER)
        if 'source_snapshot' not in rel.parts:continue
        dst=OUT/'frozen_source'/(str(rel)+'.txt');dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),rel
        else:dst.write_bytes(src.read_bytes())
    return cost

if __name__=='__main__':
    c=export();print(json.dumps({k:c[k] for k in ['new_physical_requests','cumulative','pending','old_rows_unchanged']}))
