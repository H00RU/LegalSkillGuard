"""Read-only readiness review; no network, subprocess, model generation or oracle writes."""
from __future__ import annotations
import ast,copy,hashlib,importlib.util,json,socket,sqlite3,subprocess
from pathlib import Path
from collections import Counter
from dataclasses import replace
from unittest.mock import patch
from legal_skill_guard.rr.coverage import FiniteTheory,Residual,SourceLedger,complete,digest,plan_batch
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.public_horn import parse_public
from legal_skill_guard.rr.routing import ARMS,route_prediction
from legal_skill_guard.rr.readiness import current_binding
root=Path(__file__).resolve().parents[3];out=root/'reports/rr_v2_evidence/readiness_review';data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
status=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text())
core=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/core_acceptance.json').read_text())
ledger=root/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
db=sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True)
before={'db_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),'calls':digest(db.execute('select * from calls order by id').fetchall()),'meta':digest(db.execute('select * from meta order by key').fetchall()),'oracle':digest(db.execute('select * from oracle_views order by source,view_hash').fetchall())}
library=SkillLibrary.restore(root/'artifacts/rr_v2_preflight/semantic_common_path_v3/partial_library.frozen.json').export()
def deny(*args,**kw):raise RuntimeError('This review forbids network, subprocess and fresh inference')
formal_replays=[];source_rows=[]
with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(subprocess,'run',deny),patch.object(subprocess,'Popen',deny):
 for item in status:
  sid=item['source'];s=data.public(sid)
  if s['dataset']=='ProofWriter_OWA_depth5':continue
  record=json.loads((root/item['source_record']).read_text())
  raw=[c['raw_content'] for c in record['calls']]
  for arm in ARMS:
   dispatched=[]
   def generate(prompt,**kw):
    # No fresh prediction: reuse only existing raw responses to test control flow.
    # The missing third response is deliberately the last stored response again;
    # its answer is NOT reported as a real formal prediction or new task score.
    dispatched.append(kw)
    return {'content':raw[min(kw['step'],len(raw)-1)]}
   generate.is_offline_mock=True
   try:
    rr=route_prediction(s,arm=arm,library=copy.deepcopy(library),generate=generate,protocol={},partition='train',offline_mock=True)
    formal_replays.append({'source':sid,'arm':arm,'completed':True,'calls':rr['model_calls'],'purposes':rr['call_purposes'],'fallback':rr['result'].get('fallback_used',False),'certificate':rr['result']['certificate_status'],'frozen':rr['frozen_library_unchanged']})
   except Exception as exc:
    formal_replays.append({'source':sid,'arm':arm,'completed':False,'exception':type(exc).__name__,'message':str(exc)})
  learning=record['learning'];finish=[]
  for c in record['calls']:
   wire=db.execute('select result from calls where request_hash=?',(c['request_hash'],)).fetchone()
   wire=json.loads(wire[0]);finish.append({'finish_reason':wire.get('finish_reason'),'usage':wire.get('usage'),'content_chars':len(c['raw_content'])})
  category='model_error';tags=[]
  if s['dataset']=='ContractNLI':
   category='expected_native_fallback';tags=['no_formal_NLI_certificate','no_counterfactual_oracle']
   if record['analysis']['diagnostics']:
    category='expected_fallback_with_model_error_and_engineering_contract_gap'
    tags.extend(['additional_model_interface_format_error','wire_schema_accepts_parser_rejects_interface_shape'])
  elif s['dataset']=='SARA_v2_Binary' and item['index']==2:
   tags=['wrong_native_answer','tautological_IR','wrong_source_link','one_historical_oracle_failure_kept_charged']
  elif s['dataset']=='SARA_v2_Binary' and item['index']==7:tags=['native_fallback_correct_not_core','tautological_IR','wrong_source_link','field_only_no_connector']
  elif s['dataset']=='SARA_v2_Binary' and item['index']==12:tags=['wrong_native_and_IR_label','literal_grounding_pass_does_not_validate_rule_logic','no_collision_in_four_cached_views']
  elif s['dataset']=='SARA_v2_Binary':tags=['native_fallback_correct_not_core','IR_label_wrong','no_eligible_counterfactual_view']
  elif item['index'] in (1,15):tags=['output_token_limit_truncation','no_valid_last_native_output']
  else:tags=['wrong_native_and_IR_task_semantics','field_only_membership_no_executable_connector']
  source_rows.append({'index':item['index'],'source':sid,'dataset':s['dataset'],'category':category,'tags':tags,
   'model_error_observed':category=='model_error' or 'additional_model_interface_format_error' in tags,
   'native_correct':record['score']['task_correct'],'program_status':record['analysis']['program_status'],
   'certificate':record['analysis']['certificate_status'],'diagnostics':record['analysis']['diagnostics'],
   'learning_status':learning['status'],'oracle_views':len(learning['oracle_views']),'reference_failures':learning.get('reference_failures',0),
   'connector_synthesis_status':learning.get('connector_synthesis_status'),
   'graphs':(learning.get('learned_pattern') or {}).get('graphs',[]),'finish':finish})
 # Re-run original A micro fixtures; no new benchmark source or label.
 tledger=SourceLedger.from_text('General rule\nInternational exception\nGift deduction')
 tledger.clauses[0]=replace(tledger.clauses[0],state='compiled')
 tledger.clauses[1]=replace(tledger.clauses[1],context=('s0',));tledger.clauses[2]=replace(tledger.clauses[2],context=('s0',))
 theory=FiniteTheory(tledger,{}, {'exception':(False,True),'gift':(False,True)},
  {'op':'xor','args':[{'var':'exception'},{'var':'gift'}]},[Residual('s1',('exception',),'public_structure',False),Residual('s2',('gift',),'public_structure',False)])
 plan=plan_batch(theory,lambda ids:10+len(ids),13)
 assert plan.status=='separation_complete' and plan.selected==('s1','s2') and plan.cost==13
 opaque={'answer_type':'three_valued_owa','facts':['Bob is red.'],'rules':['If the opaque condition applies then Bob is blue.'],'query':'Bob is red.'}
 irrelevant=parse_public(opaque).assess(len,100)
 opaque['rules'].append('If someone is blue then they are red.')
 related=parse_public(opaque).assess(len,100)
 assert irrelevant['status']=='completion_stable' and related['status']!='completion_stable'
 # Successful separation-plan reachability in current producer is limited by
 # its contract: unresolved relevant scope returns conservative full-source;
 # otherwise all effect domains are singleton and no different-answer pair exists.
 main_cases=[]
 for r in core['records']:
  raw=json.loads((root/r['record_path']).read_text());a=raw['record']['analysis'];p=parse_public(data.public(r['source'])['public'])
  main_cases.append({'source':r['source'],'answer':a['answer'],'residual_count':len(p.residuals),'batch':a['public_grammar_assessment']['batch'],'A_main':r['A']['semantic_pass'],'B_main':r['B']['semantic_pass'],'B_collisions':len(r['B']['coarse_collisions']),'B_semantic_checks':len(r['B']['connector_semantic_checks'])})
after={'db_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),'calls':digest(db.execute('select * from calls order by id').fetchall()),'meta':digest(db.execute('select * from meta order by key').fetchall()),'oracle':digest(db.execute('select * from oracle_views order by source,view_hash').fetchall())}
assert before==after
counts=Counter((x['arm'],x['completed']) for x in formal_replays)
result={'binding':current_binding(root),'new_model_calls':0,'new_oracle_views':0,'network_and_subprocess_blocked':True,'ledger_unchanged':True,
 'before':before,'after':after,'fresh_core_evidence_reaudited':main_cases,
 'A_offline_existing_fixtures':{'xor_plan':{'status':plan.status,'selected':list(plan.selected),'context':list(plan.context),'cost':plan.cost},'opaque_irrelevant':irrelevant,'opaque_relevant':related},
 'A_implementation_findings':{'nontrivial_separation_plan_producer_not_connected':True,'engine_planning_cost_is_clause_count_not_token_count':True,
  'reason':'PublicHorn returns stable before planning, or conservative full source when any residual is query relevant; all other non-conflict domains are singleton no_effect. Non-PW analysis emits no finite residual observation theory.'},
 'source_rows':source_rows,'formal_controller_offline_replay':formal_replays,
 'formal_controller_replays_completed':sum(x['completed'] for x in formal_replays),'formal_controller_replays_total':len(formal_replays),
 'replay_limitation':'Synthetic generator returns only saved real raw strings; third fallback reuses last response. This tests controller safety only, never online model quality or real 3-call outcomes.',
 'budget':{'executor_used':124,'teacher_used':3,'executor_study_max':6000,'teacher_study_max':20,'remaining_full_train_max':216,'all_original_remaining_planned_calls_max':5688,'total_including_prior_if_all_planned_max':5812,'recovery_bucket_used':48,'recovery_bucket_remaining':184,'teacher_total_with_seven_remaining_batches_two_calls_each':17}}
(out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k in ['binding','new_model_calls','ledger_unchanged','formal_controller_replays_completed','formal_controller_replays_total','A_implementation_findings','budget']}))
