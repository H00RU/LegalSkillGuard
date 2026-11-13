from pathlib import Path
import json
from collections import Counter
from copy import deepcopy
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from experiments import legal_skill_evolution_positive_binding_acquisition as e

out=e.OUT;p=e.read(out/'protocol.json');pub={s['key']:s for s in e.read(e.PUBLIC)};grading=e.read(e.GRADING)

def metrics(result):
 rows=result['feedback']['views']
 return {'correct':sum(bool(v['score'] and v['score']['correct']) for v in rows),
  'core_executed':sum(v['core_executed'] for v in rows),'views':len(rows),
  'fallback_physical_requests':0,'uncovered':sum(not v['core_executed'] for v in rows)}

def analysis(lib,key,actual):
 output=actual['execution']['source_output'];feedback=e.checker(lib,pub[key],grading[key])(output)
 uses=[]
 for row in actual['feedback']['views']:
  value=row['execution']['value'];nodes=value.get('used_nodes',[])
  uses.append({'view':row['view'],'native_correct':bool(row['score'] and row['score']['correct']),
   'core_executed':row['core_executed'],'prediction':value.get('answer'),
   'used_root_ids':nodes,'used_terms':[output['statements'][n]['term'] for n in nodes]})
 return {**metrics(actual),'partial_source_check_passed':feedback['source_review_passed'],
  'partial_source_check_applicable':any(r['source']==key and r['forbidden_subterms'] for r in e.read(out/'partial_source_checks.json')),
  'explicit_source_violations':feedback['explicit_source_review_violations'],'views':uses,
  'source_root_constructors':dict(Counter(r['term'][0] for r in output['statements'])),
  'C_binding_roots':[r for r in output['statements'] if r['term'][0] in ('bound_disclosure_permission','bound_disposal_obligation')],
  'partial_check_not_a_complete_source_semantic_certificate':True,
  'C_binding_counter_is_not_a_count_of_Free_positive_norms':True}

summary=[];components=[]
for stage,keys in [('acquisition',p['acquisition_sources']),('reuse',p['reuse_sources'])]:
 for arm in e.ARMS:
  libpath=out/arm/'learned.json'
  if not libpath.exists():libpath=out/arm/'compiled.json'
  lib=e.read(libpath)
  for key in keys:
   name=e.name_for(key)
   if stage=='acquisition':
    path=out/arm/'fitted_execution'/name if arm=='ConstraintAcquire' else out/stage/arm/name
   else:path=out/'reuse_scores'/arm/name
   if not path.exists():continue
   actual=e.read(path);row={'stage':stage,'arm':arm,'source':key,**analysis(lib,key,actual)}
   if arm=='ConstraintAcquire':
    nofit=e.read(out/stage/arm/name)['NoFit'] if stage=='acquisition' else actual['NoFit']
    row['NoFit']={**metrics(nofit),'partial_source_check_passed':e.checker(lib,pub[key],grading[key])(nofit['execution']['source_output'])['source_review_passed']}
    output=actual['execution']['source_output'];without=deepcopy(output)
    without['statements']=[r for r in without['statements'] if r['term'][0] not in ('bound_disclosure_permission','bound_disposal_obligation')]
    dropped=e.checker(lib,pub[key],grading[key])(without)
    comps={'stage':stage,'source':key,'only_delete_actual_learned_positive_roots':metrics({'feedback':dropped}),
     'full':metrics(actual),'same_consumer_and_remaining_actual_roots':True,'new_physical_requests':0,
     'this_is_execution_component_evidence_not_independent_C_algorithm_credit':True}
    components.append(comps)
   summary.append(row)
aggregates={}
for stage in ('acquisition','reuse'):
 for arm in e.ARMS:
  rows=[r for r in summary if r['stage']==stage and r['arm']==arm]
  if not rows:continue
  total={k:sum(r[k] for r in rows) for k in ('correct','core_executed','uncovered','fallback_physical_requests')}
  total.update(views=sum(len(r['views']) for r in rows),mothers=len(rows),explicit_partial_checks_applicable_mothers=sum(r['partial_source_check_applicable'] for r in rows),
   explicit_partial_checks_passed_on_applicable_mothers=sum(r['partial_source_check_applicable'] and r['partial_source_check_passed'] for r in rows),
   C_specific_binding_root_count=sum(len(r['C_binding_roots']) for r in rows),mothers_with_C_binding_roots=sum(bool(r['C_binding_roots']) for r in rows))
  if arm=='ConstraintAcquire':total['NoFit']={k:sum(r['NoFit'][k] for r in rows) for k in ('correct','core_executed','uncovered')}
  aggregates[stage+':'+arm]=total
result={'same_goal':True,'goal_complete':False,'run_id':e.RUN,'aggregate':aggregates,'sources':summary,
 'U_dictionary_empty':True,'native_accuracy_is_not_source_semantic_acceptance':True,'all_old_scores_unchanged':True}
# This is a replaceable unbound live report, never a frozen scientific input.
folder=out/'live_analysis';folder.mkdir(exist_ok=True)
(folder/'source_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(folder/'component_deletion.json').write_text(json.dumps(components,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(aggregates,ensure_ascii=False))
