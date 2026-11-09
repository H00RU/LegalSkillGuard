"""New shared deterministic path over preserved real TRAIN proposals, zero calls."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.legal_case_grounding import ground_case
from legal_skill_guard.rr.legal_predicate_skills import validate,run
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v3_20261109'
OUT=ROOT/'artifacts/rr_method_redesign_20261109/legal_grounded_replay_v1_20261109'

def read(p):return json.loads(p.read_text())

def main():
 s=read(STAGE/'seal.json');raw=read(STAGE/'facts.json')['value']['cases'];program=read(STAGE/'frozen_library.json')['program']
 validate(program,[p['rules'] for p in s['policies']]+[s['cases'][-1]['rules']])
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_grounded_replay.py','legal_skill_guard/rr/legal_case_grounding.py','legal_skill_guard/rr/legal_predicate_skills.py']}
 immutable_json(OUT/'seal.json',{'files':files,'raw_proposals_sha256':hashlib.sha256((STAGE/'facts.json').read_bytes()).hexdigest(),'source_library_sha256':hashlib.sha256((STAGE/'frozen_library.json').read_bytes()).hexdigest(),'new_model_calls':0,'not_a_new_blind_test':True,'original_native_labels_opened':False,'goal_complete':False})
 rows=[];grounded=[]
 for c in raw:
  source=next(o for o in s['cases'] if o['ordinal']==c['ordinal']);g,audit=ground_case(c,source,program);grounded.append(g)
  actual=run(program,g);flat=run(program,g,use_priorities=False)
  # Ordinary correct-policy cache receives identical original teacher material,
  # public question compilation, evidence gate and inference algorithm.
  ordinary=run(deepcopy(program),deepcopy(g));assert ordinary==actual
  rows.append({'ordinal':c['ordinal'],'grounding_audit':audit,'actual':actual,'without_priorities':flat,'ordinary_same_information_policy_cache':ordinary,'strong_control_equal':True})
 immutable_json(OUT/'shared_grounded_cases.json',{'cases':grounded})
 immutable_json(OUT/'frozen_library.json',{'program':program})
 restored=read(OUT/'frozen_library.json')['program']
 for g,row in zip(grounded,rows):assert run(restored,g)==row['actual']
 result={'captured_utc':datetime.now(timezone.utc).isoformat(),'cases':rows,'new_model_calls':0,'new_sources':0,'original_gold_opened':False,'source_semantics_are_reviewed_assumptions_not_formal_truth':True,'freeze_reload_exact':True,'goal_complete':False}
 immutable_json(OUT/'execution.json',result)
 print(json.dumps([{'ordinal':r['ordinal'],'answer':r['actual']['answer'],'query_witnesses':r['actual']['query_witnesses'],'without_priorities':r['without_priorities']['answer'],'rejected_rows':len(r['grounding_audit']['rejected_model_rows']),'strong_cache_equal':True} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()
