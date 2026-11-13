from collections import Counter
from datetime import datetime,timezone
import json,hashlib,pathlib,sqlite3,shutil
from experiments.legal_skill_evolution_frozen_acquirer_probe import setup,OUT,ROOT,LEDGER,VARIANTS,read
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
p,_,public=setup();before=read(OUT/'ledger_before_row_hashes.json')
with sqlite3.connect('file:'+str(LEDGER)+'?mode=ro',uri=True)as db:rows=db.execute('select * from calls order by id').fetchall()
assert not any(r[6]=='reserved'for r in rows);now={r[0]:digest(r)for r in rows};assert all(now[k]==v for k,v in before.items())
new=[r for r in rows if r[0]not in before];assert len(new)==10 and all(r[1]=='executor'and r[6]=='completed'for r in new)
calls=[]
for r in new:
 d=json.loads(r[8]);request=read(pathlib.Path(d['artifact_directory'])/'request.json');assert d['thinking_requested']is False and d['finish_reason']=='stop'and request['payload']['max_tokens']==8192 and request['payload']['chat_template_kwargs']['enable_thinking']is False
 calls.append({'id':r[0],'source':r[4],'role':r[1],'status':r[6],'usage':d['usage'],'elapsed_seconds':d['elapsed_seconds'],'thinking':False,'max_tokens':8192,'finish_reason':d['finish_reason'],'result_sha256':digest(d)})
cost={'captured_utc':datetime.now(timezone.utc).isoformat(),'old_rows_unchanged':len(before),'new_executor_calls':10,'new_teacher_calls':0,'ledger_rows':len(rows),'reserved':0,'total_executor_calls':sum(r[1]=='executor'for r in rows),'total_teacher_calls':sum(r[1]=='teacher'for r in rows),'executor_prompt_tokens':sum(r['usage']['prompt_tokens']for r in calls),'executor_completion_tokens':sum(r['usage']['completion_tokens']for r in calls),'executor_service_seconds':sum(r['elapsed_seconds']for r in calls),'cash_invoice_and_GPU_allocation_unknown':True,'calls_sha256':digest(rows),'calls':calls}
unscored=list(OUT.glob('unscored/*/*.json'));scored=list(OUT.glob('scores/*/*.json'));assert len(unscored)==len(scored)==16 and max(f.stat().st_mtime_ns for f in unscored)<min(f.stat().st_mtime_ns for f in scored)
assert all(read(f)['feedback']['reason']=='unscored_execution'for f in unscored)
metrics={};outcomes=[]
for variant in VARIANTS:
 views=[]
 for key in p['sources']:
  name=key.replace(':','_')+'.json';fb=read(OUT/'scores'/variant/name)['feedback'];rows_for_source=[]
  for v in fb['views']:
   row={'source':key,'variant':variant,'view':v['view'],'answer':v['execution']['value']['answer'],'correct':(v.get('score')or{}).get('correct',False),'core':v['core_executed'],'fallback_executed':False};views.append(row);rows_for_source.append(row);outcomes.append(row)
 metrics[variant]={'correct':sum(r['correct']for r in views),'total':16,'core':sum(r['core']for r in views)}
assert all(m['correct']==1 for m in metrics.values());assert [metrics[v]['core']for v in VARIANTS]==[12,8,12,8]
C=read(OUT/'ConstraintAcquire/library.json');assert set(C['selected_rule_ids'])==set(C['suggested_rule_ids'])
immutable_json(OUT/'source_results.json',{'metrics':metrics,'rows':outcomes,'independent_mothers':4,'native_views_per_variant':16,'all16_unscored_saved_before_any_score':True,'fallback_requests':0,'C_fitted_and_suggested_rule_selection_sets_equal':True,'independent_C_or_U_advantage_established':False,'goal_complete':False})
immutable_json(OUT/'cost_and_preservation.json',cost)
immutable_json(OUT/'TERMINAL_PRESERVATION.json',{'run_boundary_terminal':True,'fixed_probe_complete':True,'all_bound_files_verified':True,'old_rows_unchanged':len(before),'ledger_rows':len(rows),'reserved':0,'new_executor_calls':10,'new_teacher_calls':0,'metrics':metrics,'original_native_scores_and_all_failures_retained':True,'goal_complete':False})
report=ROOT/'reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_frozen_acquirer_probe'
for f in OUT.rglob('*'):
 if f.is_file()and 'source_snapshot'not in f.parts:
  dst=report/f.relative_to(OUT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dst)
for src,name in [('/tmp/lsg_diagnose_frozen_acquirer_20261114.py','postscore_diagnosis/reproduce.py'),('/tmp/lsg_collect_frozen_acquirer_20261114.py','collect.py')]:
 dst=report/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
role=read(ROOT/'artifacts/legal_skill_evolution_MAUD_role_repair_20261114/cost_and_preservation.json')
checkpoint={**cost,'old_rows_unchanged':role['old_rows_unchanged'],'new_teacher_calls':1,'teacher_usage':role['teacher_usage'],'teacher_service_seconds':role['teacher_service_seconds'],'incremental_stages':['MAUD_role_repair','frozen_acquirer_probe'],'combined_new_physical_requests':11,'role_cost_evidence':'real_MAUD_role_repair/cost_and_preservation.json','probe_cost_evidence':'real_frozen_acquirer_probe/cost_and_preservation.json'}
checkpoint['calls']=[*role['calls'],*calls]
(ROOT/'reports/legal_skill_evolution_run_20261111/method_investment_20261113/current_checkpoint_cost.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'metrics':metrics,'cost':{k:v for k,v in cost.items()if k!='calls'}},ensure_ascii=False))
