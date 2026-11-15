"""Validate unchanged paid joint edits with their actual shared-helper scope.

The first validation incorrectly checked converters without the shared helpers.
Its frozen failure remains in the acquisition run; this recovery makes no new
teacher call and changes neither generated code nor source truth checks.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_service_observer_update as acquired
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.observation_component_library import component_value,validate
from legal_skill_guard.skill_evolution.objects import digest

ROOT=acquired.ROOT
RUN='legal_skill_evolution_service_observer_shared_helpers_fix_20261115'
OUT=ROOT/'artifacts'/RUN
train=acquired.train


def setup():
    path=OUT/'protocol.json'
    if not path.exists():
        previous=train.read(acquired.OUT/'protocol.json')
        files=[Path(__file__),Path(acquired.__file__),Path(train.actor.__file__),
            acquired.OUT/'protocol.json',acquired.OUT/'teacher_task.json',acquired.OUT/'result.json']
        files +=[acquired.OUT/a/'teacher.json'for a in train.ARMS]
        files +=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
        files +=[ROOT/'tests'/name for name in ('test_skill_evolution_facts_only_component.py',
            'test_skill_evolution_partial_native_proof.py')]
        p={k:v for k,v in previous.items()if k not in ('run_id','source_sha256','ledger_before')}
        p.update(run_id=RUN,source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files},
            repair='Validate shared_helpers plus original conversion_program as actually executed.',
            teacher_outputs_unchanged=True,new_teacher_calls=0,prior_failed_validation=str(acquired.OUT.relative_to(ROOT)))
        immutable_json(path,p)
        for f in files:
            dst=OUT/'source_snapshot'/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(f.read_bytes())
    p=train.read(path)
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def validate_updates():
    p=setup();public,kernels=acquired.data();client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=RUN))
    all_candidates=[];selected={}
    for arm in train.ARMS:
        base=train.read(acquired.BASE/'libraries'/(arm+'.json'))
        old=next(c for c in base['components']if c['id']==acquired.COMPONENT);candidates=[]
        for i,proposal in enumerate(train.read(acquired.OUT/arm/'teacher.json')['value']['candidates']):
            entry={'arm':arm,'candidate':i,'cases':[]}
            component={**deepcopy(old),**{k:v for k,v in proposal.items()if k!='rationale'},'facts_only':True}
            library=deepcopy(base);library['components']=[component if c['id']==acquired.COMPONENT else c for c in library['components']]
            try:
                validate_adapter(component['observation_program'],excluded_source_ids=p['sources'])
                validate_adapter(base['shared_helpers']+'\n\n'+component['conversion_program'],excluded_source_ids=p['sources'])
                for field in ('observation_program','conversion_program'):
                    for n in ast.walk(ast.parse(component[field])):
                        if isinstance(n,ast.Constant):
                            assert n.value not in ('Alice','Bob','Charlie','Dan','Johns Hopkins University'),'Training entity constant'
                            if type(n.value)is int:assert n.value not in (2015,2017,2018,2019),'Training year constant'
                validate(library,kernels[p['acquisition_sources'][0]])
                for sid in p['acquisition_sources']:
                    pub=public[sid]['views'][0]['public']
                    observation,receipt=train.actor.read_component(client,p,sid,component,kernels[sid],pub,purpose='skill_actor')
                    parts=[component_value(library,component,kernels[sid],pub,v)for v in observation[acquired.COMPONENT]['views']]
                    checks=[acquired.source_checks(sid,v)for v in parts]
                    entry['cases'].append({'source':sid,'observation':observation,'receipt':receipt,'converted':parts,'checks':checks})
                errors=sum(len(c['errors'])for r in entry['cases']for c in r['checks'])
                usable=sum(all(c['usable']for c in r['checks'])for r in entry['cases'])
                entry.update(source_errors=errors,usable_cases=usable)
                candidates.append((errors,-usable,len(component['observation_program'])+len(component['conversion_program']),i,library))
            except Exception as error:entry['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'candidate_results'/arm/(str(i)+'.json'),entry);all_candidates.append(entry)
        if candidates:
            c=min(candidates,key=lambda x:x[:-1])
            if c[0]==0 and -c[1]==len(p['acquisition_sources']):
                path=OUT/'selected_libraries'/(arm+'.json');immutable_json(path,c[-1])
                selected[arm]={'candidate':c[3],'path':str(path.relative_to(ROOT)),'sha256':digest(c[-1])}
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only_selection':True})
    reuse=[];whole=[];grading=train.read(train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    for arm,choice in selected.items():
        library=train.read(ROOT/choice['path']);component=next(c for c in library['components']if c['id']==acquired.COMPONENT)
        for sid in p['fixed_reuse_sources']:
            pub=public[sid]['views'][0]['public'];observation,receipt=train.actor.read_component(client,p,sid,component,kernels[sid],pub,purpose='skill_actor')
            parts=[component_value(library,component,kernels[sid],pub,v)for v in observation[acquired.COMPONENT]['views']]
            reuse.append({'arm':arm,'source':sid,'observation':observation,'receipt':receipt,'converted':parts,
                'checks':[acquired.source_checks(sid,v)for v in parts]})
        sid=next(s for s in p['acquisition_sources']if ':250fc5' in s)
        row=train.actor.execute_one(client,p,arm,library,sid,kernels[sid],public[sid],'whole_university',purpose='skill_actor')
        whole.append(train.scored(row,public,grading))
    immutable_json(OUT/'result.json',{'candidates':all_candidates,'selected':selected,'fixed_reuse':reuse,
        'whole_university':whole,'new_teacher_calls':0,'new_executor_calls':0,'DEV_TEST_loaded':False,
        'no_generated_code_or_observation_changed':True,'goal_complete':False})
    print(json.dumps({'selected':selected,'candidate_errors':[c.get('error')for c in all_candidates],
        'reuse_usable':[all(c['usable']for c in r['checks'])for r in reuse],
        'whole':[{'arm':r['candidate'],'handled':r['execution']['handled'],'native_correct':r['native_score']['correct'],
            'source_failures':r['partial_source_review']['failures'],'error':r.get('error')}for r in whole]}),flush=True)


def neural():
    p=setup();public,kernels=acquired.data();selected=train.read(OUT/'selected_before_reuse.json')['selected']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=[OUT]
    rows=[]
    for arm,choice in selected.items():
        library=train.read(ROOT/choice['path']);component=next(c for c in library['components']if c['id']==acquired.COMPONENT)
        component={k:v for k,v in component.items()if k!='observation_program'}
        for sid in [next(s for s in p['acquisition_sources']if ':250fc5' in s)]+p['fixed_reuse_sources']:
            row={'arm':arm,'source':sid,'same_schema_converter_facts_only_input':True}
            try:
                pub=public[sid]['views'][0]['public'];observation,receipt=train.actor.read_component(client,p,sid,component,kernels[sid],pub,purpose='skill_actor')
                parts=[component_value(library,component,kernels[sid],pub,v)for v in observation[acquired.COMPONENT]['views']]
                row.update(observation=observation,receipt=receipt,converted=parts,checks=[acquired.source_checks(sid,v)for v in parts])
            except Exception as error:row['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'neural_same_contract'/arm/(digest(sid)+'.json'),row);rows.append(row)
    immutable_json(OUT/'neural_ablation.json',{'rows':rows,'DEV_TEST_loaded':False,'goal_complete':False})
    print(json.dumps({'neural_usable':[all(c['usable']for c in r.get('checks',[]))if r.get('checks')else False for r in rows]}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('validate','neural'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'validate':validate_updates,'neural':neural}[args.phase]()
