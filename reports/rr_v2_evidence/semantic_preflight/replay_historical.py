"""Current-code replay of original physical85–96; never adapt missing semantics."""
import json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.schema_validation import validate_response
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.preflight import score_source
root=Path(__file__).resolve().parents[3]
data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
db=sqlite3.connect(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
rows=db.execute("SELECT id,source,result FROM calls WHERE role='executor' ORDER BY reserved_at,id LIMIT 96").fetchall()
meta=dict(db.execute("SELECT key,value FROM meta WHERE key LIKE 'repair_outcome:%'"))
records=[]
for physical,(cid,sid,raw) in enumerate(rows,1):
    if physical<85:continue
    result=json.loads(raw);source=data.public(sid)
    validation=validate_response(source,data.grade(sid),result['content'])
    analysis=analyze(source,result['content'])
    row=dict(physical=physical,call_id=cid,source=sid,raw_unchanged=True,
        raw_sha256=__import__('hashlib').sha256(result['content'].encode()).hexdigest(),
        current_validation={k:v for k,v in validation.items() if k not in ['analysis','program_answer']},
        current_native_answer_score=score_source(source,analysis,data.grade(sid)),
        current_diagnostics=analysis['diagnostics'])
    prior=meta.get('repair_outcome:'+cid)
    if prior:
        before=json.loads(prior)
        row['historical_validation']={k:before.get(k) for k in ['pass','typed_schema_pass','model_IR_executed','reason','program_native_score']}
    records.append(row)
out=dict(scope='Current-code analysis only; original response and original outcomes retained',
    calls=len(records),new_model_requests=0,new_oracles=0,missing_semantics_synthesized=False,
    strict_passes=sum(r['current_validation']['pass'] for r in records),records=records)
(root/'reports/rr_v2_evidence/semantic_preflight/historical_replay.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'calls':out['calls'],'strict_passes':out['strict_passes'],'new_model_requests':0}))
