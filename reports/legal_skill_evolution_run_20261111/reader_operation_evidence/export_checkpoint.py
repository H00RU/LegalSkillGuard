"""Export this finite reader-operation checkpoint, preserving raw responses."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FIRST = ROOT/'artifacts/legal_skill_evolution_semantic_operations_20261113'
CURRENT = ROOT/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113'


def export():
    before = json.loads((FIRST/'ledger_before.json').read_text())['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        columns = [r[1] for r in db.execute('pragma table_info(calls)')]
        rows = [list(r) for r in db.execute('select * from calls order by id')]
    old = {r[0]: r for r in before}; now = {r[0]: r for r in rows}
    assert all(now[k] == r for k,r in old.items())
    added = [dict(zip(columns,r)) for r in rows if r[0] not in old]
    assert not any(r['status']=='reserved' for r in added)
    counts = Counter((r[columns.index('role')],r[columns.index('status')]) for r in rows)
    requests = []
    for r in added:
        result = json.loads(r['result']) if r['result'] else None
        requests.append({**r,'result':result})
    cost = {'new_physical_requests':{role:sum(r['role']==role for r in added) for role in ('executor','teacher')},
        'cumulative':{role:sum(n for (rr,s),n in counts.items() if rr==role) for role in ('executor','teacher')},
        'requests':requests,'pending':0,'old_rows_unchanged':len(before),'total_rows':len(rows),
        'ledger_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'teacher_usage':[{k:r['result'].get(k) for k in ('model','elapsed_seconds','invocation')}
                        for r in requests if r['role']=='teacher'],
        'executor_usage':[r['result'].get('usage') for r in requests if r['role']=='executor'],
        'local_executor_incremental_API_cash_usd':0,'teacher_actual_cash_usd':None,
        'GPU_cash_allocation_usd':None,'cash_invoice_unknown_not_zero':True,
        'reasoning_tokens_included_in_output_not_added_twice':True,'goal_complete':False}
    (OUT/'cost_and_preservation.json').write_text(json.dumps(cost,ensure_ascii=False,indent=2)+'\n')
    for label,folder in [('first',FIRST),('constructive',CURRENT)]:
        for src in folder.rglob('*.json'):
            relative = src.relative_to(folder)
            if relative.parts[0] in ('source_snapshot','teacher_adapter_cache') or relative.name.startswith('ledger_'):
                continue
            dst = OUT/'raw'/label/relative;dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists(): assert dst.read_bytes()==src.read_bytes(),relative
            else: dst.write_bytes(src.read_bytes())
        script = folder/'source_snapshot/experiments/legal_skill_evolution_semantic_operations.py'
        dst = OUT/'raw'/label/'frozen_runner.py.txt';dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(script.read_bytes())
    return cost


if __name__=='__main__':
    result = export()
    print(json.dumps({k:result[k] for k in ['new_physical_requests','cumulative','pending','old_rows_unchanged']}))
