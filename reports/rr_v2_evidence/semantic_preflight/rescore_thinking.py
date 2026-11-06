"""Apply repaired native scoring to the already selected paired records, no calls."""
import json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.preflight import score_source
root=Path(__file__).resolve().parents[3]
data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
base=root/'artifacts/rr_v2_preflight'
db=sqlite3.connect(base/'research_ledger.sqlite3')
wire_hashes={row[0] for row in db.execute('select request_hash from calls')}
records=[]
for sid in data.order:
    for thinking in (True,False):
        record=json.loads((base/'thinking_native_contract_fix'/f'{digest((sid,thinking))}.json').read_text())
        if record['wire_request_hash'] not in wire_hashes or record['source']!=sid or record['offline_mock']:
            raise ValueError('Existing thinking record lacks actual charged provenance')
        score=score_source(data.public(sid),record['analysis'],data.grade(sid))
        records.append(dict(source=sid,thinking=thinking,wire_request_hash=record['wire_request_hash'],
            old_task_correct=record['task_correct'],current_native_task_correct=score['task_correct']))
lookup={(r['source'],r['thinking']):r['current_native_task_correct'] for r in records}
harm=[sid for sid in data.order if lookup[sid,True] and not lookup[sid,False]]
if not harm:
    raise ValueError('Selection must be audited again if native scoring removed the existing ON advantage')
result=dict(new_model_calls=0,new_oracles=0,paired_sources=20,records=len(records),
    score_only_replay=True,selected_thinking=True,selection_unchanged=True,
    current_native_correct={str(t):sum(r['current_native_task_correct'] for r in records if r['thinking']==t) for t in (True,False)},
    on_correct_off_incorrect=harm,scoring_changes=sum(r['old_task_correct']!=r['current_native_task_correct'] for r in records),details=records)
(root/'reports/rr_v2_evidence/semantic_preflight/thinking_rescore.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='details'},ensure_ascii=False))
