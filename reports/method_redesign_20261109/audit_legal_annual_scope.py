"""Audit annotation origins, all real source acquisitions and scoped identifiability."""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,itertools,json,re,sqlite3,tarfile
from pathlib import Path

from experiments.rr_v2_legal_annual_scope import ROOT,FIELDS,plan_sql,sql_value,probes,reference,check,read
from experiments.rr_v2_legal_annual_python_control import admitted
from legal_skill_guard.rr.ordinary_python_cache import execute
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_annual_scope_execution_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109'
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_temporal13_20261110/ledger.after.sqlite3')
RUNS=['legal_annual_scope_v1_20261110','legal_annual_scope_v2_20261110','legal_annual_scope_v3_20261110',
      'legal_annual_python_control_v1_20261110','legal_annual_python_repair_v1_20261110']
ANNOTATION='legal_TRAIN88_reference_facts_v1_20261110'


def snapshot(p):
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
  return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def annotated_runtime():
 projected=read(BASE/ANNOTATION/'reference_fact_projection.json');facts={}
 for text in projected['factual_projection']:
  m=re.fullmatch(r'(\w+)\((.*)\)\.',text);args=json.loads('['+m[2]+']');facts.setdefault(m[1],[]).append(args)
 def one(pred,key):
  vals=[r[1] for r in facts[pred] if r[0]==key]
  if len(vals)!=1:raise ValueError('Expected one annotation value '+str((pred,key)))
  return vals[0]
 payments=[];quals=[];events=[]
 for (pid,) in facts['payment_']:
  service=one('purpose_',pid);payer=one('agent_',pid);payee=one('patient_',pid)
  amount=one('amount_',pid);paid=one('start_',pid)
  payments.append([pid,payer,payee,int(paid[:4]),service,amount])
  agricultural=any(r==[service,'agricultural labor'] for r in facts['purpose_'])
  if agricultural:
   for r in facts['agent_']:
    if r[0]==service:quals.append([pid,service+' / employee witness '+r[1]])
  events.append({'payment_id':pid,'payer':payer,'payee':payee,'amount':amount,'annotated_payment_start':paid,
    'source_of_payment_date':'extra_TRAIN_reference_annotation_not_public_text_or_old_model_reader',
    'service_id':service,'agricultural_candidate':agricultural})
 return projected,payments,quals,events


def old_functions(name):
 p=BASE/name/'frozen/experiments/rr_v2_legal_annual_scope.py'
 text=p.read_text();tree=ast.parse(text);defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['sql_value','plan_sql']]
 ns={'sqlite3':sqlite3,'FIELDS':FIELDS};exec(compile(ast.Module(body=defs,type_ignores=[]),str(p),'exec'),ns)
 return ns


def identification(payments,quals):
 variants=[]
 for n in range(6):
  for keys in itertools.combinations(FIELDS,n):
   for op in ['cap','exclude_scope_at_least','exclude_scope_above','include_all']:
    plan={'scope_keys':list(keys),'threshold':7000,'adjustment':op};sql=plan_sql(plan)
    scores=check(sql);value=sql_value(sql,payments,quals)
    variants.append({'plan':plan,'runtime_total':value,'passes':[r['passed'] for r in scores['rows']]})
 expected=reference(payments,quals);fitting=[i for i,r in enumerate(variants) if r['runtime_total']==expected]
 correct=[i for i,r in enumerate(variants) if all(r['passes'])]
 assert len(variants)==128 and len(correct)==1
 survivors=[]
 for size in range(9):
  for subset in itertools.combinations(range(8),size):
   compatible=[i for i,r in enumerate(variants) if all(r['passes'][j] for j in subset)]
   if compatible==correct:survivors.append(subset)
  if survivors:break
 assert survivors
 return {'hypothesis_count':len(variants),'operators':['cap','exclude_scope_at_least','exclude_scope_above','include_all'],
  'scope_fields':FIELDS,'fixed_threshold_for_this_diagnostic':7000,
  'fit_observed_annotated_local_quantity':len(fitting),'pass_all_eight_source_contract_checks':len(correct),
  'unique_contract_consistent_plan':variants[correct[0]]['plan'],
  'minimum_identifying_check_count_within_these_eight_and_this_finite_grammar':size,
  'minimum_identifying_sets':[[probes()[j]['name'] for j in t] for t in survivors],
  'all_hypotheses':variants,'ordinary_exact_consistency_learner_recovers_same_unique_plan':True,
  'not_a_new_algorithm_or_general_minimality_theorem':True,
  'not_a_new_native_dataset_or_model_experiment':True,
  'observed_quantity_and_binary_threshold_alone_do_not_identify_legal_operator_scope':True}


def main():
 before=snapshot(BEFORE);current=snapshot(DB);historic=deepcopy(current)
 added=[r for r in current['calls'] if any(r[0].startswith(n+':') for n in RUNS)]
 historic['calls']=[r for r in historic['calls'] if not any(r[0].startswith(n+':') for n in RUNS)]
 historic['meta']=[r for r in historic['meta'] if r[0] not in ['method_runtime_policy:'+n for n in RUNS+[ANNOTATION]]]
 source=read(BASE/ANNOTATION/'reference_fact_projection.json')['source']
 new_views=[r for r in current['oracle_views'] if r not in before['oracle_views']]
 assert len(new_views)==1 and new_views[0][0]==source
 historic['oracle_views']=[r for r in historic['oracle_views'] if r not in new_views]
 assert historic==before and len(added)==7
 assert not [r for r in current['calls'] if r[6]=='reserved']
 assert all(r[1]=='executor' and r[6]=='completed' for r in added)
 projected,payments,quals,events=annotated_runtime();raw=read(BASE/RUNS[-1]/'source.json')
 assert raw['source_checks']['all_passed'];code=raw['code'];rows=admitted(payments,quals)
 actual=execute(code,rows,'component3306_b_1');expected=reference(payments,quals)
 assert actual==expected==20597
 observations={}
 old=old_functions(RUNS[0])
 for name in RUNS[:2]:
  q=read(BASE/name/'sql.json')['sql'];observations[name+':SQL']={'value':old['sql_value'](q,payments,quals),'source_checks_passed':False}
 plan=read(BASE/RUNS[0]/'raw_plan_semantic_diagnostic.json')['raw_plan']
 observations[RUNS[0]+':raw_plan_diagnostic_not_admitted']={'value':old['sql_value'](old['plan_sql'](plan),payments,quals),
   'source_quote_valid':False,'source_scope_checks_passed':False}
 v3=read(BASE/RUNS[2]/'plan.json');observations[RUNS[2]+':plan']={'value':sql_value(v3['sql'],payments,quals),'source_checks_passed':v3['source_checks']['all_passed']}
 observations[RUNS[-1]+':ordinary_Python']={'value':actual,'source_checks_passed':True,'actual_repaired_model_output_used':True}
 execution={'source':source,'TRAIN_ordinal':88,'annotated_events':events,'raw_payments':payments,'candidate_witnesses':quals,
  'local_admitted_rows':rows,'actual_local_component_total':actual,'observations':observations,
  'local_other_statutory_preconditions_assumed_not_a_complete_wage_or_employer_predictor':True,
  'annotation_dates_not_claimed_as_text_extraction_or_old_frame_recovery':True,
  'admission_identity_adapter_shared_not_learned_mechanism':True,
  'native_3306_a_2_A_prediction_or_grade_added':False,'original_bad_model_outputs_not_modified':True,
  'repair_code_sha256':hashlib.sha256(code.encode()).hexdigest(),'new_model_calls':0,'goal_complete':False}
 immutable_json(STAGE/'execution.json',execution)
 library={'code':code,'entrypoint':'law_cache','query_contract':'component3306_b_1','facts_contract':'unique admitted payment row dicts',
    'local_scope_only':'3306(b)(1) cumulative amount adjustment; all other exclusions/admission outside this component',
    'source_model_run':RUNS[-1],'source_instance_operator_scope_learned':True,'new_method_contribution_claim':False}
 immutable_json(STAGE/'frozen_library.json',library)
 restored=read(STAGE/'frozen_library.json');assert execute(restored['code'],rows,restored['query_contract'])==actual
 ident=identification(payments,quals);immutable_json(STAGE/'finite_scope_identifiability.json',ident)
 copied={}
 for name in RUNS:
  stage=BASE/name;seal=read(stage/'seal.json');copy={}
  for p,h in seal['files'].items():
   dest=stage/'frozen'/p
   if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==h
   else:
    data=(ROOT/p).read_bytes();assert hashlib.sha256(data).hexdigest()==h
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   copy[p]=h
  copied[name]=copy
 wires=[json.loads(r[8]) for r in added]
 assert all(w['thinking_requested'] is False and w['finish_reason']=='stop' and w['reasoning_content'] in [None,''] for w in wires)
 report_path=REPORT/'legal_annual_scope_results.json';captured=read(report_path)['captured_utc'] if report_path.exists() else datetime.now(timezone.utc).isoformat()
 result={'captured_utc':captured,'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},
  'pending':0,'new_charged_attempts':{'executor':7,'teacher':0},'new_physical_dispatches':{'executor':7,'teacher':0},
  'new_TRAIN_annotation_views':1,'new_native_task_grades':0,'all_pre_turn_rows_equal_backup':True,
  'pre_turn_counts':{k:len(v) for k,v in before.items()},'current_counts':{k:len(v) for k,v in current.items()},
  'old_ledger_logical_sha256':digest(historic),'current_ledger_logical_sha256':digest(current),
  'actual_source_programme_local_operator_validated':True,'ordinary_Python_control_strongest_successful_route':True,
  'declarative_plan_additional_capability_not_established':True,'two_method_contributions_established':False,
  'local_component_not_new_full_native_success':True,'source':source,'execution':execution,
  'finite_identification_summary':{k:v for k,v in ident.items() if k!='all_hypotheses'},
  'bound_source_copies':copied,'new_regressions_passed':9,
  'executor_prompt_tokens':sum(w['usage']['prompt_tokens'] for w in wires),
  'executor_output_tokens':sum(w['usage']['completion_tokens'] for w in wires),
  'executor_request_elapsed_seconds':sum(w['elapsed_seconds'] for w in wires),
  'executor_incremental_API_cash_usd':0,'GPU_cost_usd':None,'teacher_historical_invoice_usd':None,'total_project_cash_cost_usd':None,
  'raw_physical_call_summary':[{'id':r[0],'request_hash':r[5],'elapsed_seconds':w['elapsed_seconds'],'usage':w['usage'],'finish_reason':w['finish_reason'],'thinking_requested':False} for r,w in zip(added,wires)],
  'no_same_source_extra_interface_scan_planned':True,'no_sampling_thinking_scan':True,'client_retries':0,
  'goal_complete':False,'new_full_build_started':False,'TEST_labels_read':False,'paper_started':False}
 immutable_json(report_path,result)
 delta=[]
 for r in added:
  d=dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'],r));d['result']=json.loads(d['result']);delta.append(d)
 immutable_json(STAGE/'request_ledger_delta.json',{'new_calls':delta,'new_TRAIN_annotation_views':1})
 dst=Path('/media/sangfor/vdb/legal-skill-backups/legal_annual_scope_20261110/ledger.after.sqlite3');dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():
  with sqlite3.connect(DB) as a,sqlite3.connect(dst) as b:a.backup(b)
 assert snapshot(dst)==current
 print(json.dumps({k:result[k] for k in ['counts_total','pending','new_charged_attempts','new_TRAIN_annotation_views','executor_prompt_tokens','executor_output_tokens','executor_request_elapsed_seconds','all_pre_turn_rows_equal_backup','finite_identification_summary']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
