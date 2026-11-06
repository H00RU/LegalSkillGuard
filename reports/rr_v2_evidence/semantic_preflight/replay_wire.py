"""Compare common-path prompts/schema to preserved generation payloads, no calls."""
import base64,hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.preflight import ingest_source
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.client import ExecutorClient
root=Path(__file__).resolve().parents[3];base=root/'artifacts/rr_v2_preflight'
seal=json.loads((base/'seal.semantic_path.json').read_text());stage=base/seal['processing_continuation']['artifact_subdirectory'];data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
db=sqlite3.connect(base/'research_ledger.sqlite3');byhash={h:json.loads(result) for h,result in db.execute("SELECT request_hash,result FROM calls WHERE status='completed'")}
client=ExecutorClient(None,stage,seal['config']['executor']);library=SkillLibrary();checks=[];wire_bytes=[]
class NoCalls:
    def _source(self,sid):assert sid in data.allowed
def canonical_metadata(messages):
    from legal_skill_guard.rr.raw_recovery import _unique_object
    decoder=json.JSONDecoder(object_pairs_hook=_unique_object)
    result=[]
    markers=['\nCurrent learned role constraints: ',
             '\nTraining interface repair evidence (no reference program): ',
             '\nOne remaining joint repair/translation call. Previous public-output diagnostics:\n']
    for message in messages:
        content=message['content']
        for marker in markers:
            location=content.rfind(marker)
            if location<0:continue
            start=location+len(marker)
            value,end=decoder.raw_decode(content[start:])
            content=content[:start]+json.dumps(value,sort_keys=True,ensure_ascii=False)+content[start+end:]
        result.append({**message,'content':content})
    return result
for sid in data.order:
    source=data.public(sid);record=json.loads((stage/'pilot_sources'/f'{digest(sid)}.json').read_text());index=[0]
    def call(**kwargs):
        c=record['calls'][index[0]];wire=byhash[c['request_hash']]
        directory=Path(wire['artifact_directory']);directory=directory if directory.is_absolute() else root/directory
        old=json.loads((directory/'request.json').read_text())['payload']
        payload=client.payload(messages=kwargs['prompt'],thinking=kwargs['thinking'],schema=kwargs['schema'])
        body_path=directory/'wire_request.json'
        if body_path.exists():
            body=json.loads(body_path.read_text())
            raw=base64.b64decode(body['body_b64'])
            if hashlib.sha256(raw).hexdigest()!=body['body_sha256']:
                raise ValueError('Preserved wire body changed')
            if not record.get('replay_provenance'):
                wire_bytes.append(raw==json.dumps(payload,ensure_ascii=False).encode())
        changed=[k for k in old.keys()|payload.keys() if digest(old.get(k))!=digest(payload.get(k))]
        normalized_equal=digest({**old,'messages':canonical_metadata(old['messages'])})==digest({**payload,'messages':canonical_metadata(payload['messages'])})
        checks.append(dict(source=sid,step=index[0],origin='retained_legacy' if record.get('replay_provenance') else 'current_real',
            payload_exact_JSON_equal=not changed,payload_semantic_JSON_equal=normalized_equal,
            metadata_order_only=bool(changed) and normalized_equal,different_fields=changed))
        index[0]+=1
        return wire
    replay=ingest_source(source=source,grade=data.grade(sid),library=library,thinking=True,call=call,
        learner=lambda *args:record['learning'],ledger=NoCalls(),artifacts=stage,binding=seal['binding'],
        purpose='preflight_bug_retry',id_prefix='audit_never_dispatch',offline_mock=False)
    if digest(replay['analysis'])!=digest(record['analysis']):raise ValueError('Current analysis differs from replay')
    pattern=record['learning'].get('learned_pattern')
    if pattern:library.add(pattern,source=sid)
from legal_skill_guard.rr.readiness import current_binding
result=dict(execution_binding=current_binding(root),preflight_binding=seal['binding'],
    normalization='Only object key order inside the three named structured metadata fields; public text, values, schema and all other fields unchanged; duplicate keys rejected',
    all_payloads_equal=all(c['payload_semantic_JSON_equal'] for c in checks),
    all_analyses_equal=True,current_real_wire_bytes_equal=len(wire_bytes)==24 and all(wire_bytes),
    sources=20,new_model_calls=0,records=len(checks),current_real_all_equal=all(c['payload_semantic_JSON_equal'] for c in checks if c['origin']=='current_real'),records_detail=checks)
(root/'reports/rr_v2_evidence/semantic_preflight/wire_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records_detail'}))
for c in checks:
    if not c['payload_semantic_JSON_equal']:print(json.dumps(c))
