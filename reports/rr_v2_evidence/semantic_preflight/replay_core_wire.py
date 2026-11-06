"""Free replay of the four *fresh* core executions after checker correction."""
import base64,hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.preflight import ingest_source
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.source_learning import learn_source
from legal_skill_guard.rr.readiness import current_binding
root=Path(__file__).resolve().parents[3];stage=root/'artifacts/rr_v2_preflight/core_primary_v1';seal=json.loads((stage/'seal.json').read_text());data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
db=sqlite3.connect(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
records=[]
class CacheOnly:
 def _source(self,sid):assert sid in data.allowed
 def reserve_oracle(self,*args):raise RuntimeError('No new oracle views')
client=ExecutorClient(None,stage,seal['config']['executor'])
for index in seal['source_indices']:
 sid=data.order[index];raw=json.loads((stage/'sources'/f'{digest(sid)}.json').read_text());record=raw['record'];trace={};cursor=[0];checks=[]
 library=SkillLibrary.restore(root/'artifacts/rr_v2_preflight/semantic_common_path_v3/partial_library.frozen.json')
 def call(**kw):
  saved=record['calls'][cursor[0]];cursor[0]+=1
  row=db.execute('SELECT id,source,status,result FROM calls WHERE request_hash=?',(saved['request_hash'],)).fetchone()
  assert row[0].startswith('core_primary_v1:') and row[1]==sid and row[2]=='completed'
  wire=json.loads(row[3]);assert wire['content']==saved['raw_content'] and wire['raw_id']
  body=json.loads((Path(wire['artifact_directory'])/'wire_request.json').read_text());body_raw=base64.b64decode(body['body_b64'])
  assert hashlib.sha256(body_raw).hexdigest()==body['body_sha256']
  payload=client.payload(messages=kw['prompt'],thinking=kw['thinking'],schema=kw['schema'])
  checks.append(body_raw==json.dumps(payload,ensure_ascii=False).encode());return wire
 result=ingest_source(source=data.public(sid),grade=data.grade(sid),library=library,thinking=True,call=call,
  learner=lambda s,g,o:learn_source(s,g,o,trace=trace),ledger=CacheOnly(),artifacts=stage,
  oracle_artifacts=root/'artifacts/rr_v2_preflight/oracle_guard',binding=record['binding'],
  purpose='preflight_bug_retry',id_prefix='offline_never_dispatch',offline_mock=False)
 records.append(dict(source=sid,wire_bytes_equal=all(checks),main_analysis_equal=digest(result['analysis'])==digest(record['analysis']),
  main_learning_equal=digest(result['learning'])==digest(record['learning']),trace_equal=digest(trace)==digest(raw['trace'])))
result=dict(execution_binding=current_binding(root),fresh_primary_generation_binding=seal['binding'],
 sources=4,new_model_calls=0,new_oracle_views=0,all_equal=all(all(r[k] for k in ['wire_bytes_equal','main_analysis_equal','main_learning_equal','trace_equal']) for r in records),records=records)
(root/'reports/rr_v2_evidence/semantic_preflight/core_wire_compatibility.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='records'}))
