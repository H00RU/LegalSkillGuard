from copy import deepcopy
import json
from experiments import legal_skill_evolution_bound_edit_train as x
from legal_skill_guard.skill_evolution.source_patch_composition import compose_libraries
from legal_skill_guard.rr.checkpoint import immutable_json
public,before,proposed,training,other=x.setup();p=x.OUT;pool=x.e.read(p/'candidate_policies.json')['entries'];grade=x.e.read(x.e.previous.prior.prior.GRADING)
# Two ordinary overwrite policies use the same acquired programs and current
# exact quotes. No selection from native labels or the five validation scores.
allplain=[e['policy'] for e in pool if not e['policy']['guards']]
lastplain=[q for q in allplain if q['old_quote_position']==len(next(c for c in before['spec']['constructors'] if c['name']==q['old_constructor'])['arguments']) and q['new_quote_position']==len(next(c for c in proposed['spec']['constructors'] if c['name']==q['new_constructor'])['arguments'])]
immutable_json(p/'unbound_simple_controls/frozen_definitions.json',{'all_exact_quote_overwrite':allplain,'last_declared_quote_overwrite':lastplain,'no_new_model_requests':True,'same_source_programs_G_consumer':True,'not_independent_end_to_end_acquisition':True})
summary=[]
for name,policies in [('all_exact_quote_overwrite',allplain),('last_declared_quote_overwrite',lastplain)]:
 lib=compose_libraries(before,proposed,policies);immutable_json(p/'unbound_simple_controls'/name/'library.json',lib)
 for key in training+other:
  dst=p/'unbound_simple_controls'/name/'execution'/x.e.name_for(key)
  if dst.exists():continue
  pub,units,_=x.e.previous.prior.prior.source_material(x.e.previous.PARENT,public,key)
  o=x.observe(x.NoCalls(),x.RUN+':'+name+':'+key,key,lib,source_text=pub['source_text'],units=units,source_output=x.e.read(x.e.OUT/'upstream'/x.e.name_for(key))['source_output'])
  a=x.e.previous.prior.prior.evaluate_source(lib,o,public[key],None)
  immutable_json(dst,{'source':key,'observation':o,'actual':a,'new_model_requests':0})
 # Save all executions before any control scoring.
 rows=[]
 for key in training+other:
  r=x.e.read(p/'unbound_simple_controls'/name/'execution'/x.e.name_for(key));out=r['actual']['execution']['source_output']
  f=x.e.previous.prior.prior.checker(lib,public[key],grade[key])(out)
  rows.append({'source':key,'learning':key in training,'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in f['views']),
   'bad_reviewed_norms':sum(x.reviewed_status(key,n)[0]=='bad' for n in out['statements']),
   'old_capability_witnesses':sum(x.reviewed_status(key,n)[0]=='keep' for n in out['statements']),
   'full_source_semantics_certified':False,'feedback':f})
 summary.append({'name':name,'policies':len(policies),'rows':rows,'native_correct':sum(z['native_correct'] for z in rows),'bad_reviewed_norms':sum(z['bad_reviewed_norms'] for z in rows)})
immutable_json(p/'unbound_simple_controls/results.json',{'systems':summary,'new_model_requests':0,'goal_complete':False})
print(json.dumps([{k:v for k,v in s.items() if k!='rows'} for s in summary]),flush=True)
