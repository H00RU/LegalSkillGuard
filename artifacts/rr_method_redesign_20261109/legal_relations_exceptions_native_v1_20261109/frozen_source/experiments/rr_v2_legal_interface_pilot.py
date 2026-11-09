"""Finite native legal interface pilot; preserve the original fixed pool/ledger."""
import argparse
from datetime import datetime, timezone
import hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.legal_predicate_skills import PROGRAM,CASES,obj,validate,validate_case,run,learned_guards,match_guard
ROOT=Path(__file__).resolve().parents[1]
RUN='legal_relations_exceptions_native_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
REPORT=ROOT/'reports/method_redesign_20261109'
SYSTEM=('Learn a reusable compact legal relation program from these TRAIN policies only. No case answers are available. '
 'Use predicates with explicit named argument roles, including distinct claimant/subject or parent/child and year where relevant. '
 'Every term is a string: ?x is a rule variable, other strings are literal constants (including years and amounts). '
 'A rule head follows from the conjunction of body atoms, with exact sign positive true/false; false is EXPLICIT negative evidence, never negation-as-failure. '
 'different pairs specify inequality for another taxpayer, never invent facts. Every head/distinct variable must occur in a body atom. '
 'Declare a neutral case_subject_year(person,year) relation, used only to enumerate the subjects/years actually named in case/query, so general amount rules are range-restricted. '
 'functional true means a terminal relation with last argument the output value and earlier arguments its key. '
 'Only nonfunctional relations may occur in rule bodies; reserve functional for final amounts. '
 'Priorities higher/lower are rule IDs supported by exact policy quotes, applying only when same keyed functional conclusions compete. '
 'Do not put a final legal conclusion in an undeclared external Boolean. Explicitly connect stated qualifying child/relative to dependent and deduction allowable to another person to its subject. '
 'Translate ONLY151(c),151(d)(1),(2),(5),152(a),152(b)(1) and their applicability predicates. '
 'For151(d)(2) derive both its applicability and its zero exemption effect;151(d)(5) may use an explicitly declared factual year-period relation as unresolved if arithmetic is not expressible. '
 'Do not implement a test or final answer. Other subrules not in this requested local module remain unresolved. '
 'guard_quote is the complete exact antecedent phrase, excluding its consequent; quote is an exact full governing sentence. '
 'All guard_quote/quote strings must be nonempty exact substrings of supplied policy. Source headings are not sufficient evidence for an invented legal condition. '
 'Use one consistent predicate vocabulary across these two policies. Return only the schema object.')
DIRECT_SCHEMA=obj({'cases':{'type':'array','items':obj({'ordinal':{'type':'integer'},'answer':{'anyOf':[{'enum':['Entailment','Contradiction']},{'type':'null'}]},'reason':{'type':'string'},'witnesses':{'type':'array','items':{'type':'string'}}})}})

def read(p):return json.loads(p.read_text())

def prepare():
 old=read(ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109/seal.json')
 public={s['key']:s['public'] for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
 cases=[{'ordinal':i,'source':old['sources']['train'][i-1],**public[old['sources']['train'][i-1]]} for i in [81,86,72,87]]
 policies=[{'section':n,'rules':next(c['rules'] for c in cases if c['ordinal']==i)} for n,i in [(151,81),(152,86)]]
 paths=['experiments/rr_v2_legal_interface_pilot.py','legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/client.py','legal_skill_guard/rr/method_ledger.py']
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
 protocol=REPORT/'legal_interface_pilot_protocol.md'
 s={'run_id':RUN,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},'files':files,
 'config':old['config'],'sources':old['sources'],'cases':cases,'policies':policies,'program_schema':PROGRAM,'case_schema':CASES,
 'system_prompt':SYSTEM,'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'TEST_authorized':False,
 'goal_complete':False,'prior_results_preserved':True,'source_semantics_review_required':True}
 immutable_json(STAGE/'seal.json',s);return s

def clients(s):
 l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],question='Do source learned legal role relations and source-given exception effects address native legal interface errors with same-information direct/cached-program controls? Finite four-source TRAIN diagnostic, not full training.')
 return MethodExecutor(l,STAGE,s['config']['executor']),MethodTeacher(l,STAGE,s['config']['teacher'])

def capture(s,action):
 path=STAGE/(action+'.json')
 if path.exists():print(json.dumps({'existing':str(path)}));return
 e,t=clients(s)
 if action in ('executor_program','teacher_program'):
  content=json.dumps({'policies':s['policies']},ensure_ascii=False);schema=PROGRAM;system=SYSTEM
 elif action=='facts':
  program=read(STAGE/'teacher_program.json')['value']
  system=('Extract only explicitly stated source-grounded legal/factual relations using the supplied predicate signatures. '
    'No rule inference or final answers. Every ground atom has exact factual sentence evidence. '
    'Resolve stated relation participants/direction/year, including nested son relations and explicit NOT entitled. '
    'case_subject_year is a neutral domain key for every named person/year relevant to the case/query; quote its supporting case or query span. '
    'Never replace missing evidence by false. Distinguish individual exemption from exemption allowed to someone for another person. '
    'Map the original native query to a ground declared atom; preserve claim polarity and any exact amount. '
    'Missing legal predicates/interpretations go to unresolved. No code, no reasoning conclusions, return only schema.')
  content=json.dumps({'predicate_signatures':program['predicates'],'source_program':program,
     'cases':[{k:c[k] for k in ('ordinal','facts','query')} for c in s['cases']]},ensure_ascii=False);schema=CASES
 elif action=='direct':
  program=read(STAGE/'teacher_program.json')['value']
  system=('Solve these original TRAIN legal tasks directly using all supplied policies, case facts and the same shared learned relation material. '
   'Return original native Entailment/Contradiction, or null if unresolved, with actual relational witnesses and short justification. '
   'Explicit negation is not universal closure. Do not use absent facts as false to complete an existential relation. No tools or hidden labels.')
  content=json.dumps({'cases':s['cases'],'shared_program':program},ensure_ascii=False);schema=DIRECT_SCHEMA
 else:raise ValueError(action)
 if action=='teacher_program':
  wire=t.summarize(RUN+':'+action,source_ids=[c['source'] for c in s['cases'][:3]],system_prompt=system,user_prompt=content,output_schema=schema);value=wire['value']
 else:
  e.readiness();wire=e.generate(RUN+':'+action,source=s['cases'][0]['source'],purpose='method_train_synthesis',messages=[{'role':'system','content':system},{'role':'user','content':content}],schema=schema,thinking=False);value=json.loads(wire['content'])
 try:
  if action.endswith('_program'):v=validate(value,[p['rules'] for p in s['policies']]);v={'status':'compiled','source_fidelity_proved':False}
  elif action=='facts':
   pred={p['name']:p for p in program['predicates']}
   assert sorted(c['ordinal'] for c in value['cases'])==sorted(c['ordinal'] for c in s['cases'])
   for case in value['cases']:
    original=next(c for c in s['cases'] if c['ordinal']==case['ordinal']);validate_case(case,original['facts']+' '+original['query'],pred)
   v={'status':'decoded','source_fidelity_proved':False}
  else:v={'status':'direct_predictions'}
 except Exception as exc:v={'status':'rejected','error':str(exc),'error_type':type(exc).__name__}
 immutable_json(path,{'value':value,'physical_response':wire,'validation':v,'captured_utc':datetime.now(timezone.utc).isoformat()})
 print(json.dumps({'action':action,'validation':v,'value':value},ensure_ascii=False))

def execute(s):
 program=read(STAGE/'teacher_program.json')['value'];cases=read(STAGE/'facts.json')['value']['cases']
 library=learned_guards(program,[p['rules'] for p in s['policies']]);immutable_json(STAGE/'frozen_library.json',{'program':program,'guards':library})
 results=[]
 for c in cases:
  results.append({'ordinal':c['ordinal'],'with_priorities':run(program,c),'without_priorities':run(program,c,use_priorities=False)})
 target=next(c for c in s['cases'] if c['ordinal']==87)
 out={'cases':results,'cross_policy63_guard_reuse':match_guard(library,target['rules'],63),'new_calls':0,'goal_complete':False,'native_gold_not_loaded':True}
 immutable_json(STAGE/'execution.json',out)
 print(json.dumps(out,ensure_ascii=False))

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','executor_program','teacher_program','facts','direct','execute']);args=p.parse_args();s=prepare()
 if args.action=='prepare':print(json.dumps({'prepared':True,'sources':[c['ordinal'] for c in s['cases']],'new_calls':0}))
 elif args.action=='execute':execute(s)
 else:capture(s,args.action)
if __name__=='__main__':main()
