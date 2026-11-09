"""Source-only independent acquisitions and shared source review, same ledger."""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.legal_support_ranges import (BLOCKS,INPUTS,NODES,PAL_SCHEMA,PROFILE_SCHEMA,QUOTES,S,evaluate_pal,validate_profile)
from legal_skill_guard.rr.semantic_frames import obj
ROOT=Path(__file__).resolve().parents[1]
RUN='legal_support_acquisition_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
REPORT=ROOT/'reports/method_redesign_20261109'
COMMON=('Derive a SOUND OVERAPPROXIMATION of the possible claimant argument of a positive section151 deduction for a fixed focus person and calendar year. '
 'Only simplified supplied TRAIN law governs. No case facts, final queries or labels are supplied. '
 'This is a may-support range, not a set of people already entitled. You may ignore age, income and disqualifying conditions only when doing so enlarges the candidate set. '
 'Never treat a read of another taxpayer in an amount/exception condition as creating a positive deduction claimant. '
 'Keep explicit source-provided interface assertions as possible support. An unparsed support family or unknown source effect is TOP, not empty. '
 'Input sets are already projected onto this focus/year, preserving participants and time. family is a conservative connected set through factual kinship/marriage anchors; it may contain extra relatives. '
 'household contains peers obtained from co-residence/household anchors. spouses contains all factual/explicitly implied spouse peers. Any unresolved relevant peer has TOP. '
 'The data-side completeness assumption is relative to the accepted extensional SARA case facts, not to all possible real-world people. Unrelated actors/payers alone do not establish a required kinship or spouse relationship. '
 'Use only pure expressions: named input sets, union(a,b,...), intersect(a,b,...), a|b, a&b, singleton(focus), empty(), top(). No strings/fact constants, imports, functions, loops, or Python execution. '
 'Known_* sets are explicit positive interface assertions, not inferred absent facts. All source quotes must occur verbatim in the respective supplied source. '
 'No generated case, answer, target-specific people or test knowledge. Quotes establish provenance, not proof of soundness.')
DESCRIPTIONS={
 'known_deduction151':'claimants explicitly stated to have a151 deduction for focus/year',
 'known_exemptions151':'claimants explicitly stated to have a151 exemption for focus/year',
 'known_dependent152':'claimants for whom focus is explicitly stated to be a152 dependent',
 'known_children152':'claimants for whom focus is explicitly a152(c)(1) qualifying child',
 'known_relatives152':'claimants for whom focus is explicitly a152(d)(1) qualifying relative',
 'relationship_c2':'claimants for whom focus explicitly satisfies the152(c)(2) relationship status',
 'relationship_d2':'claimants for whom focus explicitly satisfies the152(d)(2) relationship status',
 'spouses':'spouse peers of focus, including implied unbound peers as TOP',
 'family':'conservative kinship/marriage connected peers of focus, including an unresolved relevant family as TOP',
 'household':'co-residence/household peers of focus, unresolved relevant peer as TOP',
 'all_actors':'all actors from the accepted case, including unrelated anonymous actors as TOP; not known to be legal claimants'}
REVIEW_SCHEMA=obj({'profile_sound_support_bound':{'type':'boolean'},'profile_issues':{'type':'array','items':S,'maxItems':12},'pal_sound_support_bound':{'type':'boolean'},'pal_issues':{'type':'array','items':S,'maxItems':12},'comparison':{'enum':['equivalent','profile_tighter','pal_tighter','incomparable','not_established']},'source_quotes':{'type':'array','items':S,'maxItems':8},'reason':S})


def read(p):return json.loads(p.read_text())


def prepare():
 base=read(ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v1_20261109/seal.json')
 blocks={}
 for policy in base['policies']:
  text=policy['rules'];matches=list(re.finditer(r'(?m)^\(([a-d])\) ',text))
  assert len(matches)==4
  for i,m in enumerate(matches):blocks[str(policy['section'])+m[1]]=text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
 assert set(blocks)==set(BLOCKS)
 prior=read(ROOT/'artifacts/rr_method_redesign_20261109/legal_library_runtime_v1_20261109/frozen_library.json')['program']
 material={'source_blocks':blocks,'input_set_meanings':DESCRIPTIONS,'frozen_previous_TRAIN_program':prior,
  'output_node_meanings':{'deduction151':'deduction claimants for focus/year','exemptions151':'exemption claimants for focus/year','dependent152':'claimants whose dependent focus could be','children152':'claimants whose qualifying child focus could be','relatives152':'claimants whose qualifying relative focus could be'}}
 profile_system=COMMON+(' Return one effect/target/support summary for EACH supplied source block. effects supports/forwards create or forward possible positive claimant support; removes_only cannot introduce support; amount_only changes quantities rather than adding claimants; unknown remains open. '
 'output is one named intermediate relation, or none/unknown. Each relation automatically contains its corresponding known_* seed in addition to any source-derived support. '
 'Compositional support expressions may reference input sets and named output relations; no cyclic unsupported references. Do not silently omit a source block. Return only the profile schema.')
 pal_system=COMMON+(' Return one compact executable set expression giving the complete root deduction151 support overapproximation. '
 'Use only input sets and focus, not undefined intermediate output relations. Account for the explicit positive interface inputs and all positive constructors in the supplied source. '
 'You may use the supplied frozen TRAIN material without inheriting its unresolved implementation gaps. Keep the expression compact and as precise as the source permits. '
 'List unresolved source semantics rather than defaulting them away. Return only the PAL schema.')
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_support_acquisition.py','legal_skill_guard/rr/legal_support_ranges.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']}
 protocol=REPORT/'legal_support_acquisition_protocol.md'
 s={'run_id':RUN,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(base['config'])},'config':base['config'],'sources':base['sources'],
 'source_ids':[base['cases'][0]['source'],base['cases'][1]['source']], 'material':material,'profile_system':profile_system,'pal_system':pal_system,
 'profile_schema':PROFILE_SCHEMA,'pal_schema':PAL_SCHEMA,'review_schema':REVIEW_SCHEMA,'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
 'case_facts_or_queries_provided_to_acquisition':False,'DEV_or_TEST_labels_opened':False,'goal_complete':False}
 immutable_json(STAGE/'seal.json',s);return s


def clients(s):
 l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],question='Does a source-covered compositional claimant-support summary acquire safe bounds more reliably or cheaply than an independently generated compact source-conditioned expression? Same existing TRAIN151/152 source; no case answers or full build.')
 return MethodExecutor(l,STAGE,s['config']['executor']),MethodTeacher(l,STAGE,s['config']['teacher'])


def generate(s,action):
 path=STAGE/(action+'.json')
 if path.exists():print(json.dumps({'existing':str(path)}));return
 e,t=clients(s)
 if action=='review':
  profile=read(STAGE/'profile.json');pal=read(STAGE/'pal.json')
  system=('Independently review each proposed SOURCE SUPPORT UPPER BOUND against the supplied simplified TRAIN law. No case facts/answers or benchmark labels are provided. '
   'Sound means any possible positive151 claimant for fixed focus/year, under the declared accepted SARA extensional inputs, is included; it need not be entitled. '
   'Check explicit151 exemption/deduction statuses, self and spouse,152(c)/(d) necessary relationship/household anchors and typed input completeness, and whether amounts/deleting exceptions can introduce new claimants. '
   'Check both strategies equally, including any ignored known_* interface input or non-source domain closure. Quote source for findings. '
   'Do not repair or output a replacement program. Your review is a source semantics judgment, not a formal proof of NL fidelity. Return only the review schema.')
  w=t.summarize(RUN+':review',source_ids=s['source_ids'],system_prompt=system,user_prompt=json.dumps({'common_material':s['material'],'compositional_profile':profile,'independent_flat_expression':pal},ensure_ascii=False),output_schema=REVIEW_SCHEMA);value=w['value']
 else:
  system=s[action+'_system'];schema=s[action+'_schema'];e.readiness()
  w=e.generate(RUN+':'+action,source=s['source_ids'][0],purpose='method_train_synthesis',messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(s['material'],ensure_ascii=False)}],schema=schema,thinking=False)
  try:value=json.loads(w['content'])
  except Exception as exc:
   immutable_json(path,{'physical_response':w,'value':None,'validation':{'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}});print(json.dumps({'action':action,'status':'invalid_json'}));return
 try:
  if action=='profile':validate_profile(value,s['material']['source_blocks'])
  elif action=='pal':
   evaluate_pal(value,{k:[] for k in INPUTS},'focus')
   if any(not q or not any(q in b for b in s['material']['source_blocks'].values()) for q in value['quotes']):raise ValueError('PAL source quote absent')
  validation={'status':'structurally_valid' if action!='review' else 'source_review_captured','NL_source_soundness_proved':False}
 except Exception as exc:validation={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
 immutable_json(path,{'captured_utc':datetime.now(timezone.utc).isoformat(),'physical_response':w,'value':value,'validation':validation})
 print(json.dumps({'action':action,'validation':validation,'value':value},ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','profile','pal','review']);a=p.parse_args();s=prepare()
 if a.action=='prepare':print(json.dumps({'prepared':True,'source_blocks':len(s['material']['source_blocks']),'case_data_in_prompt':False,'new_calls':0}))
 else:generate(s,a.action)
