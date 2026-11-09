"""One concrete repair of the same four native TRAIN cases, no new sources."""
import argparse,hashlib,json,re
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.legal_predicate_skills import obj,validate,validate_case,run,learned_guards,match_guard
ROOT=Path(__file__).resolve().parents[1]
RUN='legal_relations_exceptions_native_v3_20261109'
OLD=ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
REPORT=ROOT/'reports/method_redesign_20261109'
S={'type':'string'}
INPUT_NAMES=['case_subject_year','qualifying_child','qualifying_relative','dependent','deduction_under_section_151_allowable']

def read(p):return json.loads(p.read_text())

def atom_schema(predicates,project=False):
 out=[]
 for p in predicates:
  arg={'anyOf':[S,{'type':'null'}]} if project else S
  n=len(p['roles']);out.append(obj({'predicate':{'enum':[p['name']]},'arguments':{'type':'array','prefixItems':[arg]*n,'items':False,'minItems':n,'maxItems':n},'positive':{'type':'boolean'}}))
 return {'anyOf':out}

def prepare():
 base=read(OLD/'seal.json');program=deepcopy(read(OLD/'teacher_program.json')['value']);source63=next(c for c in base['cases'] if c['ordinal']==87)['rules']
 templates=learned_guards(program,[p['rules'] for p in base['policies']]);matched=match_guard(templates,source63,63)
 assert any(t['learned_from_rule']=='r151_d_2_applicability' for t in matched)
 r=deepcopy(next(r for r in program['rules'] if r['id']=='r151_d_2_applicability'))
 r.update(id='transferred63c5',authority='26 U.S.C. §63(c)(5)',guard_quote=r['guard_quote'].replace('this section','section 151'))
 assert r['guard_quote'] in source63
 start=source63.index(r['guard_quote']);end=source63.index('    (6)',start)
 r['quote']=source63[start:end].strip();r['head']['predicate']='section_63_c_5_applies'
 p=deepcopy(next(p for p in program['predicates'] if p['name']=='section_151_d_2_applies'));p.update(name='section_63_c_5_applies',meaning='Applicability of the new source clause with the exact same normalized antecedent; role meanings retained from151(d)(2).')
 program['predicates'].append(p);program['rules'].append(r)
 validate(program,[p['rules'] for p in base['policies']]+[source63])
 factpred=[p for p in program['predicates'] if p['name'] in INPUT_NAMES]
 case_schemas=[]
 for case in base['cases']:
  sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z])',case['facts'])
  factual_variants=[]
  for fp in factpred:
   quote_enum=sentences+[case['query']] if fp['name']=='case_subject_year' else sentences
   factual_variants.append(obj({'atom':atom_schema([fp]),'quote':{'enum':list(dict.fromkeys(quote_enum))}}))
  case_schemas.append(obj({'ordinal':{'enum':[case['ordinal']]},'facts':{'type':'array','items':{'anyOf':factual_variants},'maxItems':8},'query':atom_schema(program['predicates'],True),'unresolved':{'type':'array','items':S}}))
 schema=obj({'cases':{'type':'array','prefixItems':case_schemas,'items':False,'minItems':4,'maxItems':4}})
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_interface_followup.py','legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/client.py','legal_skill_guard/rr/method_ledger.py']}
 protocol=REPORT/'legal_interface_bounded_protocol.md'
 out={**{k:base[k] for k in ('config','sources','cases','policies')},'run_id':RUN,'binding':{'code_hash':digest(files),'config_hash':digest(base['config'])},'files':files,'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
 'shared_program':program,'factual_predicates':factpred,'case_schema':schema,'transferred_guard_source_rule':'r151_d_2_applicability','original_teacher_program_sha256':hashlib.sha256((OLD/'teacher_program.json').read_bytes()).hexdigest(),'unmodified_V1_raw_responses_preserved':True,'TEST_authorized':False,'goal_complete':False}
 immutable_json(STAGE/'seal.json',out);return out

def clients(s):
 l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],question='Repair demonstrated native-query projection and invented-conclusion extraction failures in the same fixed legal pilot; verify source-role transfer and scoped exception effects with shared information, no new sources or configuration change.')
 return MethodExecutor(l,STAGE,s['config']['executor']),MethodTeacher(l,STAGE,s['config']['teacher'])

def generate(s,action):
 path=STAGE/(action+'.json')
 if path.exists():print(json.dumps({'existing':str(path)}));return
 e,t=clients(s)
 if action=='facts':
  system=('Extract ONLY the relations explicitly stated by the supplied case text using this fixed input predicate menu. '
   'Do not apply policy rules, supply amounts, derive applicability or guess unmentioned facts. Return each explicitly stated relationship once. In particular, a qualifying_child statement is not also an independently observed dependent or qualifying_relative statement. '
   'Each fact quote must be an exact substring of facts. case_subject_year only may also cite the original query to enumerate a neutral person/year key. '
   'A stated legal status (for example a person satisfies a specifically named child classification) is an input status; preserve its two participants and year. '
   'A statement that someone is entitled to an exemption/deduction for another under151 must retain both people; do not replace it by the general exemption amount. '
   'Explicit NOT entitlement is a negative literal of the same relation; absence of a statement is not false. '
   'Map each native query to a declared output predicate with the full declared arity. Use null for an unasked participant, e.g. a claimant not named in the question. '
   'Do not choose a person for an unasked role from your own legal reasoning. Preserve dollar spellings from output predicate material when the same number is meant. '
   'Do not infer final answers. Return only the schema object.')
  user={'input_predicates':s['factual_predicates'],'output_predicates':s['shared_program']['predicates'],
        'output_literals':sorted({a for r in s['shared_program']['rules'] for a in r['head']['arguments'] if not a.startswith('?')}),
        'cases':[{k:c[k] for k in ('ordinal','facts','query')} for c in s['cases']]};schema=s['case_schema']
 elif action=='priority_review':
  system=('Review only these source-learned rules against the original TRAIN statutes. No case labels or query answers are supplied. '
   'The previous interface allowed priorities only for terminal numeric amounts. The corrected executor also supports source-justified priorities between opposite signed relational conclusions for the same participants/year. '
   'State whether the exception that a dependent is treated as having no dependents must defeat an otherwise inferred positive dependent relation. '
   'Return only necessary additional higher/lower rule-ID edges with exact source quotes, and other semantic issues. Never invent an edge just to agree with an output. '
   'Do not replace source rules or complete unresolved sections. This is a source judgment, not a formal proof of natural-language fidelity.')
  user={'policies':s['policies'],'program':s['shared_program']}
  schema=obj({'additional_priorities':{'type':'array','items':obj({'higher':S,'lower':S,'quote':S})},'source_review':S,'other_issues':{'type':'array','items':S}})
 elif action=='direct':
  system=('Solve the original four TRAIN questions directly, using the same shared source material, extracted facts and learned priority review available to the symbolic method. '
   'Return original Entailment/Contradiction or null if unresolved. Report actual person/role/year witnesses as text, not just predicate names. '
   'Separate a dependent of someone from a person who has dependents. Your answer field must agree with your justification. Do not use hidden labels or tools.')
  user={'cases':s['cases'],'shared_program':s['shared_program'],'shared_facts':read(STAGE/'facts.json')['value'],'shared_priority_review':read(STAGE/'priority_review.json')['value']}
  schema=obj({'cases':{'type':'array','items':obj({'ordinal':{'type':'integer'},'answer':{'anyOf':[{'enum':['Entailment','Contradiction']},{'type':'null'}]},'reason':S,'witnesses':{'type':'array','items':S}})}})
 else:raise ValueError(action)
 if action=='priority_review':wire=t.summarize(RUN+':'+action,source_ids=[c['source'] for c in s['cases'][:3]],system_prompt=system,user_prompt=json.dumps(user,ensure_ascii=False),output_schema=schema);value=wire['value']
 else:
  e.readiness();wire=e.generate(RUN+':'+action,source=s['cases'][0]['source'],purpose='method_train_synthesis',messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(user,ensure_ascii=False)}],schema=schema,thinking=False);value=json.loads(wire['content'])
 validation={'status':'raw_review'}
 if action=='facts':
  try:
   assert sorted(c['ordinal'] for c in value['cases'])==sorted(c['ordinal'] for c in s['cases'])
   pred={p['name']:p for p in s['shared_program']['predicates']}
   for c in value['cases']:
    original=next(o for o in s['cases'] if o['ordinal']==c['ordinal']);validate_case(c,original['facts']+' '+original['query'],pred)
    for f in c['facts']:
     assert f['atom']['predicate'] in INPUT_NAMES
     text=original['facts']+' '+original['query'] if f['atom']['predicate']=='case_subject_year' else original['facts']
     assert f['quote'] in text
   validation={'status':'decoded','source_semantics_review':'pending'}
  except Exception as exc:validation={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
 immutable_json(path,{'value':value,'physical_response':wire,'validation':validation,'captured_utc':datetime.now(timezone.utc).isoformat()})
 print(json.dumps({'action':action,'validation':validation,'value':value},ensure_ascii=False))

def execute(s):
 facts=read(STAGE/'facts.json');assert facts['validation']['status']=='decoded'
 program=deepcopy(s['shared_program']);review=read(STAGE/'priority_review.json')['value'];program['priorities']+=review['additional_priorities']
 validate(program,[p['rules'] for p in s['policies']]+[s['cases'][-1]['rules']])
 immutable_json(STAGE/'frozen_library.json',{'program':program,'learned_guard_templates':learned_guards(program,[p['rules'] for p in s['policies']]+[s['cases'][-1]['rules']]),'source_review':review})
 rows=[]
 for c in facts['value']['cases']:
  rows.append({'ordinal':c['ordinal'],'role_and_priority':run(program,c),'without_priorities':run(program,c,use_priorities=False)})
 out={'cases':rows,'new_calls':0,'goal_complete':False,'original_native_labels_opened':False,'learned_program_from_real_TRAIN_teacher':True,'ordinary_same_information_correct_policy_cache':{'same_program':True,'same_inference_engine':True,'same_outputs':True,'not_an_independent_advantage_claim':True}}
 immutable_json(STAGE/'execution.json',out);print(json.dumps({ 'cases':[{'ordinal':r['ordinal'],'answer':r['role_and_priority']['answer'],'without_priorities':r['without_priorities']['answer'],'query_witnesses':r['role_and_priority'].get('query_witnesses')} for r in rows]},ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','facts','priority_review','direct','execute']);a=p.parse_args();s=prepare()
 if a.action=='prepare':print(json.dumps({'prepared':True,'new_sources':0,'reused_teacher_program':True,'guard_transfer':True}))
 elif a.action=='execute':execute(s)
 else:generate(s,a.action)
