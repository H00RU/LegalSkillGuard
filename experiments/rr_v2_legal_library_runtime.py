"""Execute and restore actual acquired skills; no model or grading access."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3,time
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.legal_library_runtime import execute_library
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=A/'legal_library_runtime_v1_20261109'


def read(p):return json.loads(p.read_text())


def snapshot():
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
  tables={t:db.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}
  assert db.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
 return hashlib.sha256(json.dumps(tables,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
 before=snapshot();library=read(A/'legal_grounded_replay_v1_20261109/frozen_library.json')
 cases=read(A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']
 paths=['legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/legal_library_runtime.py','experiments/rr_v2_legal_library_runtime.py','tests/test_rr_legal_library_runtime.py']
 immutable_json(STAGE/'seal.json',{'files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'original_library_sha256':hashlib.sha256((A/'legal_grounded_replay_v1_20261109/frozen_library.json').read_bytes()).hexdigest(),'new_model_calls':0,'original_native_labels_not_opened':True,'goal_complete':False})
 immutable_json(STAGE/'frozen_library.json',library);restored=read(STAGE/'frozen_library.json');assert restored==library
 start=time.monotonic();rows=[]
 old=read(A/'legal_grounded_replay_v1_20261109/execution.json')['cases']
 for case in cases:
  result=execute_library(restored,case);control=execute_library(deepcopy(restored),deepcopy(case));assert result==control
  previous=next(o['actual']['answer'] for o in old if o['ordinal']==case['ordinal']);assert result['answer']==previous
  rows.append({'ordinal':case['ordinal'],'runtime':result,'ordinary_same_information_runtime_equal':True,'native_prediction_unchanged':True})
 elapsed=time.monotonic()-start;after=snapshot();assert before==after
 out={'captured_utc':datetime.now(timezone.utc).isoformat(),'cases':rows,'new_model_calls':0,'new_oracle_views':0,'new_sources':0,'native_predictions_modified':False,'native87_is_a_core_success':False,'frozen_library_exact_restoration':True,'ledger_logical_sha256_before':before,'ledger_logical_sha256_after':after,'elapsed_seconds':elapsed,'independent_method_advantage_established':False,'goal_complete':False}
 immutable_json(STAGE/'execution.json',out)
 print(json.dumps([{'ordinal':r['ordinal'],'answer':r['runtime']['answer'],'mechanism':r['runtime']['mechanism'],'source_call_count':len(r['runtime']['source_calls']),'conditions':[c['condition']['condition_value'] for c in r['runtime']['source_calls']]} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()
