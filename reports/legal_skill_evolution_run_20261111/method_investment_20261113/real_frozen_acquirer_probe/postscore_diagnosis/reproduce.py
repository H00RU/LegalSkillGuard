from experiments.legal_skill_evolution_frozen_acquirer_probe import setup,read,OUT,GRADING,arm_for
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.theory_supervision import native_loss,attach_scored_theories,diagnose_inputs
from legal_skill_guard.skill_evolution.open_acquisition import fit
p,_,public=setup();grading=read(GRADING);library=read(OUT/'ConstraintAcquire/library.json');obs=[];profiles=[];per=[]
for key in p['sources']:
 name=key.replace(':','_')+'.json';o=read(OUT/'unscored/C_eager'/name)['observation']
 profile=admissible_direct_compositions(library,o,contract_checker(library['spec'],public[key],grading[key]),timeout_seconds=90)
 assert profile['status']=='complete'
 losses=[native_loss(e['native_feedback']) for e in profile['evaluations']if e['partial_source_constraints_satisfied']and 'native_feedback'in e]
 minimum=min(x for x in losses if x is not None)
 per.append({'source':key,'actual_reachable_theories':profile['finite_theory_count'],'minimum_native_errors_with_current_language_and_actual_reads':minimum,'correctness_upper_bound':4-minimum})
 obs.append(o);profiles.append(profile)
 immutable_json(OUT/'postscore_diagnosis/profiles'/name,profile)
_,result=fit(library,[attach_scored_theories(o,a)for o,a in zip(obs,profiles)],prior_rule_ids=library['selected_rule_ids'],timeout_seconds=90)
diagnosis=diagnose_inputs(obs,profiles,'not_run');assert result['native_loss']==15 and sum(r['correctness_upper_bound']for r in per)==1
immutable_json(OUT/'postscore_diagnosis/oracle_fit.json',result)
immutable_json(OUT/'postscore_diagnosis/result.json',{'per_source':per,'global_native_errors_lower_bound':result['native_loss'],'independent_per_source_total_correctness_upper_bound':1,'total_native_views':16,'diagnosis':diagnosis,'postscore_diagnostic_not_a_new_trained_model':True,'scored_libraries_unchanged':True,'new_model_requests':0,'no_additional_G_fit_can_recover_missing_source_norms_in_this_frozen_space':True})
print('Actual fixed-read/source-output upper bound:1/16 even with independent per-source current-G choices; global minimum errors15.',flush=True)
