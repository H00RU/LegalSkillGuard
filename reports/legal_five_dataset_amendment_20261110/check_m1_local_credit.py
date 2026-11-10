"""Exact finite learning-rule audit. No model, API, train/test dataset, or gold selector."""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import json, math
OUT=Path(__file__).resolve().parent

def dist(pa,pc):
 return {(a,c):(pa if a else 1-pa)*(pc if c else 1-pc) for a,c in product((0,1),repeat=2)}
def signature(a,c): return a^c

def robust_preference(contexts,y=1):
 # Compare acquisition a=1 against a=0 in the SAME completion contexts.
 contrasts=[int(signature(0,c)!=y)-int(signature(1,c)!=y) for c in contexts]
 return {"contrasts":contrasts,"lower":min(contrasts),"upper":max(contrasts),"prefer_a1":min(contrasts)>0,"prefer_a0":max(contrasts)<0}

def audit(pa,pc):
 p=dist(pa,pc); ok={k:v for k,v in p.items() if signature(*k)==1};z=sum(ok.values())
 post={k:v/z for k,v in ok.items()};posterior_a=sum(v for (a,c),v in post.items() if a)
 grad=posterior_a-pa
 best=max(ok,key=lambda k:ok[k])
 # KL projection onto support y=1 is exactly prior conditioned on y=1.
 qkl=post.copy();assert qkl==post
 # A finite-difference derivative of log observed-label likelihood.
 alpha=math.log(float(pa/(1-pa))); eps=1e-6
 def loglik(alpha):
  ap=1/(1+math.exp(-alpha));cp=float(pc)
  return math.log(ap*(1-cp)+(1-ap)*cp)
 finite=(loglik(alpha+eps)-loglik(alpha-eps))/(2*eps)
 assert abs(finite-float(grad))<1e-8
 return {"prior_a1":float(pa),"prior_c1":float(pc),"joint": [{"a":a,"c":c,"p":float(v),"answer":signature(a,c)} for (a,c),v in p.items()],"observed_answer":1,"correct_answer_mass":float(z),"posterior_a1":float(posterior_a),"logit_ascent_directions":{"exact_MML":float(grad),"class_mass_MML":float(grad),"answer_support_KL_projection":float(sum(v for (a,c),v in qkl.items() if a)-pa),"hard_EM":float(best[0]-pa),"uniform_consistent_program_weighting":float(F(1,2)-pa),"MML_plus_prior_KL_at_initialization":float(grad),"single_context_c0_local_preference":float(1-pa),"single_context_c1_local_preference":float(-pa),"robust_common_contexts_0_1":0.0,"robust_after_native_context_evidence_c0":float(1-pa)},"finite_difference_MML":finite,"common_context_rule":robust_preference((0,1)),"after_independent_context_evidence":robust_preference((0,))}

main=audit(F(4,5),F(9,10))
grid=[]
for pa in (F(1,5),F(1,2),F(4,5)):
 for pc in (F(1,10),F(1,2),F(9,10)):
  r=audit(pa,pc);grid.append({k:r[k] for k in ("prior_a1","prior_c1","logit_ascent_directions")})
# Truly unobserved factor: exhaustive factorized MML already gives zero credit.
pa,pc=F(4,5),F(9,10);p=dist(pa,pc);ok={k:v for k,v in p.items() if k[1]==1};z=sum(ok.values())
unobserved_grad=sum(v/z for (a,c),v in ok.items() if a)-pa
assert unobserved_grad==0
# Finite dominance guarantee is only about queried contexts, never unseen ones.
assert robust_preference((0,))["prefer_a1"] and not robust_preference((0,1))["prefer_a1"]
result={"purpose":"algebraic nonredundancy, not learned accuracy or proof of novelty", "gradient_convention":"positive increases acquisition logit(a=1); log-likelihood ascent / negative-loss descent, margin=0 for pairwise preference", "toy_semantics":"binary compensation; not a claim that legal permission is negated prohibition", "main":main,"grid":grid,"independent_unobserved_factor_exact_MML_gradient":float(unobserved_grad),"scope_warning":"A singleton sampled context misses the opposing preference. At least two observed alternatives are needed here; any unenumerated context remains outside the guarantee.","external_calls":0,"training_runs":0}
mixed_contrasts=[1,1,-1]
assert sum(mixed_contrasts)/len(mixed_contrasts)>0 and min(mixed_contrasts)<0
result["mean_vs_robust"]={"local_contrasts":mixed_contrasts,"mean_prefers_a":True,"robust_prefers_a":False}
(OUT/"M1_FINITE_CHECK.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({"main":main["logit_ascent_directions"],"grid_cases":len(grid),"independent_factor_gradient":float(unobserved_grad)},indent=2))
