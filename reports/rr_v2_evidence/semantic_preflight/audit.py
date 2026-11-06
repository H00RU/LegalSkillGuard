"""Read-only audit of actual fixed-source records and the same persisted ledger."""
import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path
from collections import Counter

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.preflight import score_source
from legal_skill_guard.rr.engine import analyze

root=Path(__file__).resolve().parents[3]
out=root/'reports/rr_v2_evidence/semantic_preflight'
base=root/'artifacts/rr_v2_preflight'
seal=json.loads((base/'seal.semantic_path.json').read_text())
stage=base/seal['processing_continuation']['artifact_subdirectory']
data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
db=sqlite3.connect(base/'research_ledger.sqlite3');db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute('SELECT * FROM calls ORDER BY reserved_at,id')]
for r in rows:r['result']=json.loads(r['result']) if r['result'] else None
old=sqlite3.connect(base/'preserved_before_semantic_diagnosis/research_ledger.sqlite3')
prior=old.execute('SELECT * FROM calls ORDER BY id').fetchall()
current_original=[tuple(r) for r in db.execute('SELECT * FROM calls WHERE id IN ('+','.join('?' for _ in prior)+') ORDER BY id',[r[0] for r in prior])]
old_meta=dict(old.execute('SELECT key,value FROM meta'));new_meta=dict(db.execute('SELECT key,value FROM meta'))
old_oracle=old.execute('SELECT * FROM oracle_views ORDER BY source,view_hash').fetchall()
new_oracle=[tuple(r) for r in db.execute('SELECT * FROM oracle_views ORDER BY source,view_hash')]
if prior!=current_original or any(new_meta[k]!=v for k,v in old_meta.items()) or old_oracle!=new_oracle:
    raise ValueError('Historical charged rows, metadata or oracle records changed')
old.close()
source_status=[]
for i,sid in enumerate(data.order):
    original=json.loads((base/'oracle_guard/pilot_sources'/f'{digest(sid)}.json').read_text())
    path=stage/'pilot_sources'/f'{digest(sid)}.json'
    record=json.loads(path.read_text()) if path.exists() else None
    source=data.public(sid)
    row=dict(index=i,source=sid,dataset=source['dataset'],original_pilot_completed=True,
             original_score=original['score'],current_record_exists=bool(record),
             source_record=str(path.relative_to(root)) if record else None)
    if record:
        row.update(current_score=record['score'],program_status=record['analysis']['program_status'],
            certificate_status=record['analysis']['certificate_status'],calls_in_record=len(record['calls']),
            generation='free_replay_of_unchanged_generation' if record.get('replay_provenance') else 'current_common_two_pass_path',
            current_executable_IRs=sum(c['analysis']['program_status'] in {'executed_expression','candidate_pool_agreement_only'} for c in record['calls']),
            unresolved_reason=record['analysis']['diagnostics'],
            semantic_status='native_answer_matches_TRAIN' if record['score']['task_correct'] else 'native_answer_unresolved_or_incorrect')
    validation_path=stage/'semantic_checks'/f'{digest(sid)}.json'
    if validation_path.exists():
        validations=json.loads(validation_path.read_text())['validations']
        row['IR_checks']=[dict(typed_schema_pass=v['typed_schema_pass'],executed=v['model_IR_executed'],
            native_task_correct=v.get('program_native_score',{}).get('task_correct'),
            public_literal_grounding=v.get('source_grounding',{}).get('pass'),full_strict_repair_check=v['pass'],reason=v['reason']) for v in validations]
        row['strict_repair_check_passes']=sum(v['pass'] for v in validations)
    core_path=root/'artifacts/rr_v2_preflight/core_primary_v1/sources'/f'{digest(sid)}.json'
    if core_path.exists():
        core_validation=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/core_acceptance.json').read_text())
        match=next(c for c in core_validation['records'] if c['source']==sid)
        row['fresh_core_primary']={'A_semantic_pass':match['A']['semantic_pass'],'B_semantic_pass':match['B']['semantic_pass'],
            'record_path':match['record_path'],'fallback':False,'requests':match['fresh_physical_requests']}
    else:
        row['fresh_core_primary']={'A_semantic_pass':False,'B_semantic_pass':False,'fallback':True,
            'A_reason':'native_NLI_without_formal_certificate' if source['dataset']=='ContractNLI' else 'strict_IR_or_source_semantics_unresolved',
            'B_reason':original['learning'].get('connector_synthesis_status',original['learning']['status'])}
    source_status.append(row)
counts=Counter((r['role'],r['status']) for r in rows)
def usage(records):
    total=Counter();elapsed=0
    for r in records:
        v=r['result'] or {}; u=v.get('usage')
        if r['role']=='teacher':u=v.get('invocation',{}).get('usage') or u
        if isinstance(u,dict):
            for k,n in u.items():
                if type(n) in (int,float):total[k]+=n
        elapsed+=v.get('elapsed_seconds',0)
    return dict(tokens=dict(total),elapsed_seconds=elapsed)
new=[r for r in rows if r['id'] not in {x[0] for x in prior}]
from legal_skill_guard.rr.readiness import current_binding
actual=dict(execution_binding=current_binding(root),generation_binding=seal['binding'],historical_call_rows_preserved=len(prior),historical_meta_preserved=len(old_meta),oracle_records_preserved=len(old_oracle),binding=seal['binding'],counts={f'{k[0]}_{k[1]}':v for k,v in counts.items()},
            executor_used=sum(r['role']=='executor' for r in rows),teacher_used=sum(r['role']=='teacher' for r in rows),
            source_records=sum(s['current_record_exists'] for s in source_status),
            new_physical_requests=len(new),new_requests_usage=usage(new),all_requests_usage=usage(rows),
            executor_incremental_api_cash_usd=0,local_gpu_cost_unpriced=True,
            teacher_cash_invoice_available=False,teacher_failed_call_usage_known=False,
            no_main_training_or_formal_evaluation=True,original_study_caps={'executor':6000,'teacher':20},
            old_preflight_caps_superseded=True)
(out/'source_status.json').write_text(json.dumps(source_status,ensure_ascii=False,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n')
(out/'request_ledger.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
# Keep the complete ledger in JSON; a concise CSV is convenient for review.
s=io.StringIO();w=csv.DictWriter(s,fieldnames=['id','role','purpose','bucket','source','status','request_hash','reserved_at']);w.writeheader()
for r in rows:w.writerow({k:r[k] for k in w.fieldnames})
(out/'request_ledger.csv').write_text(s.getvalue())
print(json.dumps(actual,ensure_ascii=False))
