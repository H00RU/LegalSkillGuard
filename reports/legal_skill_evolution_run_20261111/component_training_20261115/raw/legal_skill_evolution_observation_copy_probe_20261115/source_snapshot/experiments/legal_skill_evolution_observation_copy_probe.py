"""Real preflight of compiled existing copy/key obligations, then whole case.

The failed original TRAIN case and both frozen teacher contracts are fixed.
No new teacher, source, seed, target label or semantic repair is introduced.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value

ROOT=generation.ROOT
RUN='legal_skill_evolution_observation_copy_probe_20261115'
OUT=ROOT/'artifacts'/RUN
PARENT=ROOT/'artifacts/legal_skill_evolution_payment_contract_routing_20261115'
runtime=generation.runtime


def run():
    public,kernels=runtime.previous.data()
    sid=next(s for s in public if ':3e22604a'in s)
    old=generation.read(PARENT/'protocol.json')
    p={k:deepcopy(old[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        include_observed_event_context=True,compile_literal_copy_and_shared_keys=True,
        original_TRAIN_sources=[sid],new_teacher_requests=0,goal_complete=False,DEV_TEST=False)
    libraries={name:generation.read(PARENT/'candidate_libraries'/(name+'.json'))
               for name in ('Method/1','FreeTeacher/0')}
    immutable_json(OUT/'TRAIN_grading.json',{sid:generation.read(PARENT/'TRAIN_grading.json')[sid]})
    paths=[Path(__file__),Path(runtime.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += [PARENT/'candidate_libraries'/(name+'.json')for name in libraries]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in paths}
    immutable_json(OUT/'protocol.json',p)
    for file in paths:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
    for channel in ('component_reads','relation_reads'):
        for file in (PARENT/channel).glob('*.json'):
            value=generation.read(file)
            if value.get('source')==sid and not value.get('error'):
                immutable_json(OUT/channel/file.name,value)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile'])
    checks=[]
    for name,library in libraries.items():
        component=next(c for c in library['components']if c['id']=='service_events')
        value,receipt=runtime.group_read(client,p,sid,component,'service_core',public[sid]['views'][0]['public'],{})
        converted=component_value(library,component,kernels[sid],public[sid]['views'][0]['public'],value)
        check={'candidate':name,'observation':value,'receipt':receipt,'converted':converted,
               'not_whole_case_success':True}
        immutable_json(OUT/'first_reads'/(name+'.json'),check);checks.append(check)
    rows=[]
    for name,library in libraries.items():
        rows.append(runtime.run_case(client,p,name,library,sid,public[sid]['views'][0]['public'],kernels[sid]))
    immutable_json(OUT/'result.json',{'first_reads':checks,'whole_cases':rows,
        'only_existing_TRAIN_repair':True,'not_cross_case_generalization':True,
        'shared_compiler_not_a_learning_contribution':True,'goal_complete':False})


if __name__=='__main__':
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
