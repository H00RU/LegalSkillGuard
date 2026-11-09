"""One same-information direct control after common deterministic grounding."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.legal_predicate_skills import obj
ROOT=Path(__file__).resolve().parents[1]
RUN='legal_relations_shared_direct_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
BASE=ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v3_20261109'
COMMON=ROOT/'artifacts/rr_method_redesign_20261109/legal_grounded_replay_v1_20261109'

def read(p):return json.loads(p.read_text())

def main():
 base=read(BASE/'seal.json');system=('Solve these four original TRAIN statutory questions using the same complete shared inputs available to the symbolic method. '
 'You receive the original statutes/facts/query, actual source-learned rules and priorities, and common source-grounded factual relations and independently compiled query roles. '
 'Do not change the original question or invert claimant and subject. Distinguish Bob being a dependent of Alice from Bob having Charlie as his dependent. '
 'An explicit negative for one claimant does not prove all claimants negative. Return Entailment/Contradiction, or null when not resolved. '
 'Keep answer consistent with your justification. State actual people and year in witnesses. No tools, grading labels or source answers are available.')
 user={'original_cases':base['cases'],'shared_source_library':read(COMMON/'frozen_library.json'),
       'shared_grounded_cases':read(COMMON/'shared_grounded_cases.json'),
       'source_review':read(BASE/'priority_review.json')['value']}
 S={'type':'string'};schema=obj({'cases':{'type':'array','items':obj({'ordinal':{'type':'integer'},'answer':{'anyOf':[{'enum':['Entailment','Contradiction']},{'type':'null'}]},'reason':S,'witnesses':{'type':'array','items':S}}),'minItems':4,'maxItems':4}})
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_shared_direct.py','legal_skill_guard/rr/legal_case_grounding.py','legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/client.py','legal_skill_guard/rr/method_ledger.py']}
 binding={'code_hash':digest(files),'config_hash':digest(base['config'])};policy=ROOT/'reports/method_redesign_20261109/legal_interface_bounded_protocol.md'
 seal={'run_id':RUN,'files':files,'binding':binding,'config':base['config'],'sources':base['sources'],'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(user,ensure_ascii=False)}],'schema':schema,'authorization_hash':hashlib.sha256(policy.read_bytes()).hexdigest(),'grade_labels_opened':False,'goal_complete':False}
 immutable_json(STAGE/'seal.json',seal)
 if (STAGE/'direct.json').exists():print(json.dumps({'existing':True}));return
 ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=binding,sources=base['sources'],authorization_hash=seal['authorization_hash'],question='One complete same-information direct control on the same four already selected native TRAIN sources after common deterministic grounding, no new source or model setting.')
 e=MethodExecutor(ledger,STAGE,base['config']['executor']);e.readiness();w=e.generate(RUN+':direct',source=base['cases'][0]['source'],purpose='method_train_synthesis',messages=seal['messages'],schema=schema,thinking=False)
 try:v=json.loads(w['content']);validation={'status':'decoded_direct'}
 except Exception as exc:v=None;validation={'status':'rejected','error':str(exc)}
 immutable_json(STAGE/'direct.json',{'value':v,'validation':validation,'physical_response':w,'captured_utc':datetime.now(timezone.utc).isoformat()});print(json.dumps({'validation':validation,'value':v},ensure_ascii=False))
if __name__=='__main__':main()
