"""Real demanded-field execution plus a strong fixed direct-role control.

No hidden facts, new teacher, source or TEST. The current hospital TRAIN case
was fixed before this probe. Independent common institution observations are
identical, already paid, and are supplied to both conditions.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_observation_residual_projection as proof
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import schema,validate

ROOT=proof.ROOT
RUN='legal_skill_evolution_projected_observation_execute_20261115'
OUT=ROOT/'artifacts'/RUN
read=proof.previous.read
runtime=proof.previous.runtime
PARENT=ROOT/'artifacts/legal_skill_evolution_observation_contract_transfer_compact_saved_20261115'


def replace(library,contract):
    value=deepcopy(library);c=next(c for c in value['components']if c['id']=='service_events')
    c['relation_contract']=contract;s=schema(contract);s['required']=[]
    c['schema_json']=json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':s}}))
    return value


def run():
    public,kernels=runtime.previous.data();evidence=read(proof.OUT/'result.json');sid=evidence['source']
    base=read(ROOT/'artifacts/legal_skill_evolution_payment_contract_routing_20261115/candidate_libraries/Method/1.json')
    projected=replace(base,evidence['projected_contract'])
    group={'name':'service_core_worker','key':'source_key','fields':[
        {'name':'source_key','type':'string','copy':False,'nullable':False,'normalizer':None},
        {'name':'worker','type':'string','copy':True,'nullable':False,'normalizer':None}],
        'prompt':'Read current facts only. Enumerate the service occurrences and copy the literal person performing each service. A person receiving payment for services may be the performer; do not replace the performer with a workplace. Keep ambiguity unread. Return only this factual role and source witnesses.'}
    K={'var':'K'};W={'var':'W'}
    atom={'predicate':group['name'],'arguments':[K,W],'sign':'positive'}
    generic={'key_domain':'generic_direct_service_worker','enumerator':group['name'],'constants':[],
        'relations':[group],'covered_families':['service_'],'covered_properties':['agent_'],
        'rules':[{'id':'public_service_event','cost':1,'head':{'predicate':'service_','arguments':[K],'sign':'positive'},'body':[atom]},
                 {'id':'public_service_worker','cost':1,'head':{'predicate':'agent_','arguments':[K,W],'sign':'positive'},'body':[atom]}]}
    validate(generic,kernels[sid]);libraries={'ResidualProjection':projected,'FixedDirectRole':replace(base,generic)}
    parent=read(PARENT/'protocol.json')
    p={k:deepcopy(parent[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        include_observed_event_context=True,compile_literal_copy_and_shared_keys=True,
        original_TRAIN_sources=[sid],no_new_teacher=True,no_DEV_TEST=True,goal_complete=False,
        direct_control='Fixed public service/agent ontology, same minimal interface, no acquired service transduction',
        not_an_unseen_source_or_full_method_claim=True)
    immutable_json(OUT/'TRAIN_grading.json',{sid:read(PARENT/'TRAIN_grading.json')[sid]})
    files=[Path(__file__),Path(runtime.__file__),proof.OUT/'result.json']+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
    for name,lib in libraries.items():immutable_json(OUT/'libraries'/(name+'.json'),lib)
    for file in(PARENT/'component_reads').glob('*.json'):
        value=read(file)
        if value.get('source')==sid and not value.get('error'):immutable_json(OUT/'component_reads'/file.name,value)
    background={k:deepcopy(v)for k,v in evidence['actual_initial_observation'].items()if k!='service_events'}
    immutable_json(OUT/'common_paid_background.json',{'source':sid,'observation':background,
        'same_both_conditions':True,'no_new_factual_values':True})
    client=FrozenExecutor(EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p)),OUT,p['executor_profile'])
    rows=[runtime.run_case(client,p,name,lib,sid,public[sid]['views'][0]['public'],kernels[sid],
        initial_observation=background)for name,lib in libraries.items()]
    immutable_json(OUT/'result.json',{'rows':rows,'actual_model_reads':True,'new_teacher_requests':0,
        'only_existing_TRAIN':True,'strong_direct_role_control_included':True,
        'not_a_learning_advantage_or_goal_completion':True,'goal_complete':False})


if __name__=='__main__':
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run()
