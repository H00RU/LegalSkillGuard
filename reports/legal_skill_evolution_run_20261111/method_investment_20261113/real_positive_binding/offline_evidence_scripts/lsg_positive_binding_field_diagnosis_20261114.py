from copy import deepcopy
from experiments import legal_skill_evolution_positive_binding_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.theory_supervision import attach_scored_theories,native_loss
from legal_skill_guard.skill_evolution.open_acquisition import fit

# These are explicit partial TRAIN source counterexamples from the saved review,
# not native-answer predicates and not synthesized replacement legal rules.
def false_fields(prefix,atom):
 p=atom['predicate'];a=atom['arguments']
 if p=='emit_bound_disclosure':
  if prefix=='4607' and a[4]=='need_to_know_only':return 'omitted confidentiality safeguard'
  if prefix=='6fce' and a[3]=='controlled_company_employees_and_professionals':return 'wrong recipient owner/class'
 if p=='emit_bound_disposal':
  if prefix in ('78ad','e82b') and a[1]=='return_or_authorized_destroy_on_request_all_materials':return 'unsupported written authorization or wrong action connection'
  if prefix=='6fce' and a[0] in ('disposal_binding_21','disposal_binding_24','disposal_binding_26'):return 'wrong action/trigger/retention profile at actual reviewed window'
 return None
p=e.read(e.OUT/'protocol.json');records=[];observations=[];snapshot=e.rows()
for key in p['acquisition_sources']:
 row=e.read(e.OUT/'acquisition/ConstraintAcquire'/e.name_for(key));profile=deepcopy(row['profile']);rejected=[];valid_losses=[]
 for ev in profile['evaluations']:
  errors=[false_fields(key[12:16],atom) for atom in ev['theory']];errors=[x for x in errors if x]
  if errors:
   ev.setdefault('native_feedback',{})['source_review_passed']=False
   rejected.append({'theory_index':ev['theory_index'],'violations':errors})
  elif ev.get('partial_source_constraints_satisfied') and 'native_feedback' in ev:
   loss=native_loss(ev['native_feedback'])
   if loss is not None:valid_losses.append(loss)
 assert valid_losses
 records.append({'source':key,'existing_theories':len(profile['evaluations']),
  'new_explicit_field_rejections':rejected,'independent_per_source_minimum_native_loss_after_review':min(valid_losses)})
 observations.append(attach_scored_theories(row['observation'],profile))
lib=e.read(e.OUT/'ConstraintAcquire/compiled.json')
_,result=fit(lib,observations,prior_rule_ids=lib['suggested_rule_ids'],timeout_seconds=90)
assert snapshot==e.rows()
immutable_json(e.OUT/'live_analysis/field_constraint_diagnosis.json',{'existing_paid_profiles_reused_without_reenumeration':True,
 'reviewed_TRAIN_source_fields_only':True,'no_reuse4_feedback_in_learning':True,'records':records,
 'per_source_optimistic_minimum_loss':sum(x['independent_per_source_minimum_native_loss_after_review'] for x in records),
 'common_G_fit_under_added_explicit_source_counterevidence':result,'installed_library_changed':False,'old_scores_unchanged':True,
 'new_physical_requests':0,'not_a_global_representation_impossibility_proof':True,'goal_complete':False})
print({'status':result['status'],'minimum_shared_loss':result.get('native_loss'),'per_source_optimistic_minimum_loss':sum(x['independent_per_source_minimum_native_loss_after_review'] for x in records),'new_model_calls':0})
