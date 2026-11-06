"""Recompute B on the same20 sources with cache-only oracle access, no models."""
import hashlib,json,socket,subprocess
from pathlib import Path
from unittest.mock import patch
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.source_learning import DurableOracle,learn_source
root=Path(__file__).resolve().parents[3];base=root/'artifacts/rr_v2_preflight'
data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
old_seal=json.loads((base/'seal.oracle_guard.json').read_text())
files=['legal_skill_guard/rr/'+n+'.py' for n in ['source_learning','learning','oracles','interfaces','public_horn','coverage']]
compat={n:old_seal['protected_files'].get(n)==hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files}
class CacheOnly:
    def _source(self,sid):
        if sid not in data.allowed:raise ValueError('Not an original TRAIN source')
    def reserve_oracle(self,*args):raise RuntimeError('This audit forbids all new oracle views')
def deny(*args,**kwargs):raise RuntimeError('B replay forbids network and reference subprocess execution')
records=[]
with patch.object(socket.socket,'connect',deny),patch.object(subprocess,'run',deny),patch.object(subprocess,'Popen',deny):
    for sid in data.order:
        source=data.public(sid);grade=data.grade(sid)
        old=json.loads((base/'oracle_guard/pilot_sources'/f'{digest(sid)}.json').read_text())['learning']
        new=learn_source(source,grade,DurableOracle(CacheOnly(),base/'oracle_guard',source,grade))
        equal=digest(new)==digest(old)
        differences=[k for k in old.keys()|new.keys() if digest(old.get(k))!=digest(new.get(k))]
        records.append(dict(source=sid,exact_semantic_JSON_equal=equal,different_fields=differences,
            old_hash=digest(old),new_hash=digest(new),old_status=old['status'],new_status=new['status']))
from legal_skill_guard.rr.readiness import current_binding
result=dict(execution_binding=current_binding(root),sources=20,new_model_calls=0,new_oracle_views=0,network_and_subprocess_blocked=True,
    dependency_hashes_unchanged=compat,all_exact=all(r['exact_semantic_JSON_equal'] for r in records),records=records)
(root/'reports/rr_v2_evidence/semantic_preflight/learning_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
for r in records:
    if not r['exact_semantic_JSON_equal']:print(json.dumps(r))
