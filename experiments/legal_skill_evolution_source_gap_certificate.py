"""Exact unchanged-G optimum from source-wise bounds, not a partial search pass.

With no unknown worlds, sum of per-source minima lower-bounds any shared G.
If the supplied prior attains every minimum, loss is globally optimal; zero
selection edits are then uniquely optimal before complexity. Zero-loss sources
need no exhaustive enumeration. Positive minima require a completed exact profile.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.theory_supervision import native_loss
from legal_skill_guard.skill_evolution.relational_rules import canonical,context_identity,language_identity


def certify(bounds):
    if not bounds or any(not row['hard_constraints_satisfied'] or row['unknown_worlds'] for row in bounds):
        raise ValueError('Actual source hard checks and fully observed contexts required')
    for row in bounds:
        if row['actual_loss']!=row['lower_bound']:
            raise ValueError('Prior is not proven optimal; run the actual learner')
        if row['lower_bound']<0 or row['actual_loss']<0:
            raise ValueError('Native mistakes cannot be negative')
        if row['lower_bound'] and row['lower_bound_basis']!='completed_exact_reachable_profile':
            raise ValueError('A positive lower bound requires exhaustive evidence')
    return {'status':'certified_optimal_unchanged','global_native_loss_lower_bound':sum(r['lower_bound'] for r in bounds),
        'actual_prior_native_loss':sum(r['actual_loss'] for r in bounds),'selection_edits':0,
        'objective_order':['native_loss','selection_edits_from_actual_prior','complexity'],
        'unique_zero_edit_selection':True,'no_improvement_from_G_fit':True,'sources':bounds,
        'solver_selection_run_claimed':False,'not_a_goal_or_source_semantics_certificate':True}


def run():
    p,_,public=e.setup();grading=e.read(e.previous.prior.prior.GRADING);arm='ConstraintAcquire'
    lib=e.read(e.OUT/arm/'compiled.json');prior=lib['suggested_rule_ids'];assert len(prior)==len(set(prior))
    assert set(prior)<={r['id'] for r in lib['language']['rules']}
    bounds=[];folder=e.OUT/'certified_revision'
    for key in p['acquisition_sources']:
        row=e.read(e.OUT/'unbound_pure_preview'/arm/e.name_for(key));o=row['observation'];actual=row['actual']
        assert not o['context']['unknown_groups']
        feedback=e.previous.prior.prior.checker(lib,public[key],grading[key])(actual['execution']['source_output'])
        loss=native_loss(feedback);assert loss is not None
        outputs=actual['execution']['composition']['certain_outputs']
        keys={canonical({k:v for k,v in a.items() if k!='context_index'}) for a in outputs}
        hard={canonical(a) for a in o['context']['required']}<=keys and not {canonical(a) for a in o['context']['forbidden']}&keys
        assert feedback['source_review_passed'] and hard
        if loss==0:
            lower=0;basis='nonnegative_native_loss_and_actual_zero_loss_prior'
        else:
            profile=e.read(e.OUT/arm/'profiles'/e.name_for(key))
            assert profile['status']=='complete'
            assert profile['context_sha256']==context_identity(o['context']) and profile['language_sha256']==language_identity(lib['language'])
            values=[native_loss(x['native_feedback']) for x in profile['evaluations']
                if x['partial_source_constraints_satisfied'] and 'native_feedback' in x]
            lower=min(v for v in values if v is not None);basis='completed_exact_reachable_profile'
        bounds.append({'source':key,'actual_loss':loss,'lower_bound':lower,'lower_bound_basis':basis,
            'hard_constraints_satisfied':True,'unknown_worlds':False})
        immutable_json(folder/'execution'/e.name_for(key),actual)
    proof=certify(bounds);proof.update({'same_goal':True,'goal_complete':False,'prior_rule_ids':prior,
        'prior_rule_cost':sum(r['cost'] for r in lib['language']['rules'] if r['id'] in prior),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'new_model_requests':0,
        'original6fce_timeout_retained_not_promoted_to_complete':True})
    learned=deepcopy(lib);learned['selected_rule_ids']=list(prior)
    immutable_json(folder/'certificate.json',proof);immutable_json(folder/'library.json',learned)
    print(e.json.dumps({'status':proof['status'],'native_loss':proof['actual_prior_native_loss'],'native_correct':32-proof['actual_prior_native_loss'],
        'selection_edits':0,'new_model_requests':0}),flush=True)


if __name__=='__main__':run()
