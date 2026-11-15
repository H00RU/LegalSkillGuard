"""Finish the pre-fixed selected-library and ordinary-reading controls.

A retained learned library remains the method's selected library. Its results
are not evidence that the rejected new proposal learned anything.
"""
from copy import deepcopy
import fcntl

from experiments import legal_skill_evolution_observation_link_runtime as runtime
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


def run():
    runtime.RUN='legal_skill_evolution_observation_link_refutation_20261115'
    runtime.OUT=runtime.ROOT/'artifacts'/runtime.RUN
    p=runtime.protocol();initial=runtime.generation.stage.read(runtime.OUT/'result.json')
    selected=initial['selected']['Method'];assert selected=='Method/Before'
    library=runtime.generation.stage.read(runtime.OUT/'libraries'/(selected+'.json'))
    public,kernels=runtime.generation.stage.acquired.runtime.previous.data()
    client=FrozenExecutor(EvolutionLedger(runtime.ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=runtime.RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p)),runtime.OUT,p['executor_profile'])
    rows=[]
    for phase,policy in [('reuse','native_residual'),('ordinary_reuse','direct_inputs_first')]:
        variant=deepcopy(p);variant['native_read_policy']=policy
        for sid in p['fixed_reuse_sources']:
            row=runtime.generation.stage.actor.execute_one(client,variant,selected,library,sid,kernels[sid],public[sid],phase,purpose='skill_actor')
            rows.append(runtime.graded(row,sid,selected,phase,public))
    immutable_json(runtime.OUT/'selected_method_reuse_controls.json',{'rows':rows,'same_frozen_sources_and_libraries':True,
        'new_teacher_update_not_adopted_not_learning_evidence':True,'goal_complete':False})


if __name__=='__main__':
    with(runtime.ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run()
