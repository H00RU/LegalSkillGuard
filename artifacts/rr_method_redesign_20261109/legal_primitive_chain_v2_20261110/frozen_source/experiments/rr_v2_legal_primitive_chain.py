"""Two original local source interfaces and a noncircular TRAIN8 fact chain.

Source compilation never receives cases. Fact reading never receives the target
clause. This bounded preflight is shared with the ordinary cache control.
"""
import argparse
from copy import deepcopy
import ast
import z3
from datetime import datetime,timezone
import hashlib,itertools,json,re,sqlite3
from pathlib import Path

from experiments.rr_v2_source_role_modules import SCHEMA
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_case_grounding import compile_question
from legal_skill_guard.rr.legal_predicate_skills import PROGRAM,FACT,validate,validate_case,run
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_contracts import ContractError,compare_modules,expression,variables
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.source_obligations import compile_module,verify,bind_and_assess

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_primitive_chain_v2_20261110'
PREVIOUS=ROOT/'artifacts/rr_method_redesign_20261109/legal_primitive_chain_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
OLD=ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'
HEAD='section_63_c_6_A_applies'
PRIMITIVES={
 'married':{'roles':['subject','other_taxpayer','year'],'meaning':'An explicit case marital relation between two people in the case year. The shared literal adapter exposes both directions of this undirected relation.'},
 'separate_return':{'roles':['subject','year'],'meaning':'The named person is explicitly said to file a separate return in the case year.'},
 'itemized_deduction':{'roles':['subject','year'],'meaning':'A case-given itemized deduction status for this person/year, including an itemized deduction stated to be allowed. This is a premise, not the63(c)(6)(A) conclusion. Do not invent an unreported deduction or election.'}}
S={'type':'string'}


def read(p):return json.loads(p.read_text())


def schemas(sentences):
 p=deepcopy(PROGRAM)
 p['properties']['predicates'].update(minItems=4,maxItems=4)
 p['properties']['predicates']['items']['properties']['name']={'type':'string','enum':[*PRIMITIVES,HEAD]}
 p['properties']['predicates']['items']['properties']['functional']={'type':'boolean','enum':[False]}
 p['properties']['rules'].update(minItems=1,maxItems=4)
 p['properties']['rules']['items']['properties']['authority']={'type':'string','enum':['§63(c)(6)(A)']}
 p['properties']['priorities'].update(maxItems=0)
 f=deepcopy(SCHEMA)
 f['properties']['inputs'].update(minItems=1,maxItems=1)
 props=f['properties']['inputs']['items']['properties']
 props['name']={'type':'string','enum':['year']};props['type']={'type':'string','enum':['integer']}
 props['origin']={'type':'string','enum':['case']}
 f['properties']['domain']={'type':'string','enum':['True']}
 f['properties']['output_type']={'type':'string','enum':['boolean']}
 f['properties']['obligations'].update(minItems=1,maxItems=4)
 source=obj({'c6_program':p,'f68_module':f})
 fact=deepcopy(FACT)
 fact['properties']['atom']['properties']['predicate']={'type':'string','enum':list(PRIMITIVES)}
 fact['properties']['atom']['properties']['arguments'].update(minItems=2,maxItems=3)
 fact['properties']['quote']={'type':'string','enum':sentences}
 reader=obj({'facts':{'type':'array','items':fact,'maxItems':8},'unresolved':{'type':'array','items':S}})
 for schema in (source,reader):assert strict_output_schema_issues(schema)==[]
 return source,reader


def query_year(text):
 years=set(re.findall(r'\b(?:19|20)\d\d\b',text))
 if len(years)!=1:raise ContractError('One literal native query year required')
 return next(iter(years))


def reference_f68(source):
 m=re.search(r'taxable year beginning after (December 31, (\d{4})), and before (January 1, (\d{4}))',source)
 if not m:raise ContractError('Unsupported original temporal source pattern')
 return f'year > {int(m[2])} and year < {int(m[4])}'


def prepare():
 old=read(OLD/'seal.json');public={r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
 cases={str(i):public[old['sources']['train'][i-1]] for i in (8,76)}
 sentences=re.split(r'(?<=\.)\s+',cases['8']['public']['facts'].strip())
 assert all(q in cases['8']['public']['facts'] for q in sentences)
 source_schema,fact_schema=schemas(sentences)
 system=('Compile two small original TRAIN source interfaces. No case facts, native queries or labels are supplied. '
   'For c6_program, derive only the applicability condition63(c)(6)(A) using the supplied case-premise API. '
   'Do not take the target applicability as an input Boolean; derive it by joining the named taxpayer/spouse, year, separate return and either-spouse itemized status. '
   'Declare exactly the three given input predicates and '+HEAD+' with roles [subject,year], all nonfunctional. '
   'The primitive marital relation is exposed in both directions by the shared adapter. Use only positive source-condition Horn rules, variables named ?X, no facts or hardcoded people/years, no extra policy effects or priorities. '
   'Use exact nonempty substrings of the supplied63 source as guard_quote and quote. '
   'For f68_module, output whether the taxable-year-beginning condition that activates provision68(f) holds; true means that provision applies, not that overall section68 applies. '
   'Take exactly one raw integer input year, domain expression True; compute the source date comparisons yourself, not an input flag. '
   'Use pure integer/Boolean expressions, single comparisons joined by and/or/not, and conditional expressions; no imports, functions, chained comparisons or JSON code inside expressions. '
   'Keep source quotes verbatim. Supply nonvacuous source obligations using result. Unresolved dependencies stay explicit. Return only the schema.')
 material={'source63':cases['8']['public']['rules'],'source68':cases['76']['public']['rules'],
           'case_premise_API':PRIMITIVES,'target_output':{'name':HEAD,'roles':['subject','year']}}
 reader_system=('Read only literal case premises. Return relation facts using the supplied API, with named participants in their actual roles and the supplied narrative year. '
   'Do not answer a legal question, infer statutory applicability, add an unreported itemized deduction, or convert absent facts to false. '
   'For married use the two people as named; the common adapter handles relation symmetry. Separate-return statements about two named people may supply one fact for each. '
   'Use an exact supplied sentence as quote, preserving its characters. No target legal predicate is permitted. Return only the schema.')
 reader_material={'case_text':cases['8']['public']['facts'],'narrative_year':query_year(cases['8']['public']['query']),
                  'primitive_API':PRIMITIVES,'source_sentence_options':sentences}
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
  'experiments/rr_v2_legal_primitive_chain.py','legal_skill_guard/rr/legal_predicate_skills.py',
  'legal_skill_guard/rr/legal_case_grounding.py','legal_skill_guard/rr/source_obligations.py',
  'legal_skill_guard/rr/semantic_contracts.py','legal_skill_guard/rr/method_client.py',
  'legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
 protocol=ROOT/'reports/method_redesign_20261109/legal_primitive_chain_protocol.md'
 seal={'run_id':RUN,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
   'config':old['config'],'sources':old['sources'],'cases':cases,'source_schema':source_schema,'fact_schema':fact_schema,
   'teacher_messages':{'system':system,'user':json.dumps(material,ensure_ascii=False)},
   'fact_messages':[{'role':'system','content':reader_system},{'role':'user','content':json.dumps(reader_material,ensure_ascii=False)}],
   'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
   'source_compiler_receives_case_or_labels':False,'fact_reader_receives_target_clause_or_query':False,
   'reused_source_response_sha256':hashlib.sha256((PREVIOUS/'source.json').read_bytes()).hexdigest(),
   'source_model_redispatch_authorized_by_this_driver':False,'goal_complete':False}
 immutable_json(STAGE/'seal.json',seal);return seal


def ledger(s):
 return MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
   binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
   question='Complete the original TRAIN8 primitive-to63(c)(6)(A) chain without a target Boolean input, and the original76 local68(f) temporal interface. One shared source-only teacher batch; one literal reader on8; ordinary correct cache shares all inputs. No method-contribution claim by compilation alone.')


def c6_software_checks(program,source):
 info=validate(program,[source]);expected={k:v['roles'] for k,v in PRIMITIVES.items()}|{HEAD:['subject','year']}
 if {k:v['roles'] for k,v in info['predicates'].items()}!=expected:raise ContractError('Predicate signatures differ from the common premise interface')
 if any(p['functional'] for p in program['predicates']):raise ContractError('Local applicability predicates are nonfunctional')
 if any(r['head']['predicate']!=HEAD or r['head']['positive'] is not True for r in program['rules']):
  raise ContractError('Only the derived positive applicability head is in scope')
 def atom(p,args):return {'atom':{'predicate':p,'arguments':args,'positive':True},'quote':'software control'}
 checks=[]
 for m,separate,own,spouse in itertools.product((False,True),repeat=4):
  facts=[]
  if m:facts.extend([atom('married',['A','B','2017']),atom('married',['B','A','2017'])])
  if separate:facts.append(atom('separate_return',['A','2017']))
  if own:facts.append(atom('itemized_deduction',['A','2017']))
  if spouse:facts.append(atom('itemized_deduction',['B','2017']))
  case={'facts':facts,'query':{'predicate':HEAD,'arguments':['A','2017'],'positive':True},'unresolved':[]}
  got=run(program,case)['answer'];expected_value='Entailment' if m and separate and (own or spouse) else None
  if got!=expected_value:raise ContractError('Source conjunction/either-spouse truth-table mismatch '+str((m,separate,own,spouse,got)))
  checks.append({'married':m,'separate':separate,'own_itemized':own,'spouse_itemized':spouse,'answer':got})
 return {'positive_witness_boundary_checks':checks,'missing_positive_premise_not_defaulted_false':True,'software_controls_not_new_native_cases':True}


def normalize_obligations(value):
 out=deepcopy(value);syms=variables({r['name']:r['type'] for r in value['inputs']})
 result=z3.Bool('source_postcondition_result');env=syms|{'result':result}
 program=expression(value['expression'],syms);domain=expression(value['domain'],syms);rows=[]
 for old,new in zip(value['obligations'],out['obligations']):
  c=expression(old['condition'],env);a=expression(old['assertion'],env)
  reachable=z3.Solver();reachable.add(domain,result==program,c)
  if reachable.check()!=z3.sat:raise ContractError('Original output-dependent condition is vacuous or undecidable')
  new['condition']='True';new['assertion']='(not ('+old['condition']+')) or ('+old['assertion']+')'
  proof=z3.Solver();proof.add(z3.Implies(c,a)!=expression(new['assertion'],env))
  if proof.check()!=z3.unsat:raise ContractError('Postcondition normalization changed its logical meaning')
  rows.append({'name':old['name'],'original_condition_reachable_with_program':True,
               'implication_normalization_equivalent_for_all_inputs_and_results':True,
               'source_quote_unchanged':old['quote']==new['quote']})
 assert all(out[k]==value[k] for k in value if k!='obligations')
 return out,{'original_source_response':str(PREVIOUS/'source.json'),
             'program_signature_domain_and_source_quotes_unchanged':True,
             'only_postcondition_logical_orientation_changed':True,'checks':rows,
             'software_fixture_fix':'Supply the required unresolved=[] field; no source rule or model response changed.',
             'new_teacher_dispatches':0}


def generate(s,action):
 path=STAGE/(action+'.json')
 if path.exists():print(json.dumps({'existing':str(path)}));return
 l=ledger(s)
 if action=='source':
  prior=read(PREVIOUS/'source.json');w=prior['physical_response']
  value=deepcopy(prior['value']);value['f68_module'],adaptation=normalize_obligations(value['f68_module'])
  immutable_json(STAGE/'source_recovery.json',adaptation)
  validation={}
  try:validation['c6']={'status':'validated_source_program','checks':c6_software_checks(value['c6_program'],s['cases']['8']['public']['rules'])}
  except Exception as exc:validation['c6']={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
  try:
   f=compile_module(value['f68_module'],s['cases']['76']['public']['rules'])
   if f.signature!={'year':'integer'}:raise ContractError('A raw integer year, not a target flag, is required')
   checks=verify(f);comparison=compare_modules(value['f68_module']['expression'],reference_f68(s['cases']['76']['public']['rules']),f.signature,'True')
   if not checks['all_supplied_obligations_verified'] or not comparison['equivalent_over_supplied_domain']:raise ContractError('Local68(f) temporal source semantics failed')
   validation['f68']={'status':'validated_source_module','checks':checks,'independent_source_date_comparison':comparison}
  except Exception as exc:validation['f68']={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
 else:
  source=read(STAGE/'source.json');assert source['validation']['c6']['status']=='validated_source_program'
  e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
  w=e.generate(RUN+':facts8',source=s['cases']['8']['key'],purpose='method_primitive_observation',messages=s['fact_messages'],thinking=False,schema=s['fact_schema'])
  try:value=json.loads(w['content']);validation={'status':'raw_fact_frame_captured_semantic_check_pending'}
  except Exception as exc:value=None;validation={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
 immutable_json(path,{'physical_response':w,'value':value,'validation':validation,'source_response_reused_without_dispatch':action=='source'})
 print(json.dumps({'action':action,'value':value,'validation':validation},ensure_ascii=False,indent=2))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','source','facts']);a=p.parse_args().action;s=prepare()
 if a=='prepare':print(json.dumps({'prepared':True,'strict_schemas_valid':True,'new_model_calls':0}))
 else:generate(s,a)
