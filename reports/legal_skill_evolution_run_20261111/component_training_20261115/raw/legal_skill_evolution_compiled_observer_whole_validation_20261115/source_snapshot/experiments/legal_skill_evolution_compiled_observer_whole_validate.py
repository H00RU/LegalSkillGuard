"""Finish the fixed TRAIN integration with necessary real, non-repeated reads.

The actual new observer programs are frozen before execution. Existing exact
reads are shared; model and data settings are unchanged. This is not a new
complete training/DEV run. Ordinary teaching receives the same public runtime.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_compiled_observer_learning as acquired
from experiments import legal_skill_evolution_observation_TRAIN_replay as cache_index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value


ROOT=acquired.ROOT
RUN='legal_skill_evolution_compiled_observer_whole_validation_20261115'
OUT=ROOT/'artifacts'/RUN
SELECTED=ROOT/'artifacts/legal_skill_evolution_compiled_observer_validation_component_abi_20261115'


def setup():
    read=acquired.train.read;parent=read(acquired.OUT/'protocol.json')
    keys=parent['acquisition_sources']+parent['fixed_reuse_sources']
    selected=read(SELECTED/'selected_before_reuse.json')['selected']
    checkpoint=read(acquired.train.OUT/'B8/checkpoint.json')
    for arm,choice in selected.items():
        assert choice['source_errors']==0 and choice['usable_acquisition_cases']==2
        library=deepcopy(read(ROOT/checkpoint['libraries'][arm]['path']))
        for component in library['components']:
            if component['id']==acquired.COMPONENT:
                component['observation_program']=choice['component']['observation_program']
        immutable_json(OUT/'libraries'/(arm+'.json'),library)
    protocol_path=OUT/'protocol.json'
    if not protocol_path.exists():
        paths=[Path(__file__),ROOT/'experiments/legal_skill_evolution_observation_component_execute.py',
            SELECTED/'selected_before_reuse.json',SELECTED/'result.json',acquired.OUT/'protocol.json']
        paths+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
        paths+=sorted((OUT/'libraries').glob('*.json'))
        protocol={'run_id':RUN,'same_goal':True,'sources':parent['sources'],'fixed_sources':keys,
            'executor_profile':parent['executor_profile'],'shared_public_pure_calculation':True,
            'shared_native_event_encoding':FACTUAL_ENCODING,
            'same_schema_neural_ablation_predeclared':True,'ablation_has_all_other_observations_fixed':True,
            'teacher_calls':0,'thinking':False,'DEV_TEST_loaded':False,'no_implicit_retries':True,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},
            'ledger_before':acquired.lineage.ledger_snapshot(),'goal_complete':False}
        immutable_json(protocol_path,protocol)
        for p in paths:
            target=OUT/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    protocol=read(protocol_path)
    for name,sha in protocol['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    # Copy actual paid records only, never the offline missing-read markers.
    cache,conflicts,origins={},{},{}
    for run in cache_index.CACHE_NAMES:
        for path in sorted((ROOT/'artifacts'/run/'component_reads').glob('*.json')):
            row=read(path)
            if row['source']not in keys:continue
            key=row['wire_input_sha256'];payload={k:row[k]for k in ('source','component_id','value','error')}
            if key in cache and payload!=cache[key][0]:conflicts.add(key)
            cache.setdefault(key,(payload,row));origins.setdefault(key,[]).append(str(path.relative_to(ROOT)))
    for key,(_,row)in cache.items():
        if key not in conflicts:immutable_json(OUT/'component_reads'/(key+'.json'),row)
    immutable_json(OUT/'paid_read_origins.json',{'origins':origins,'conflicting_keys_not_used':sorted(conflicts)})
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['sources'],'dev':[],'test':[]},binding=digest(protocol))
    client=FrozenExecutor(ledger,OUT,protocol['executor_profile'])
    client.exact_replay_roots=[OUT]+[ROOT/'artifacts'/r for r in cache_index.CACHE_NAMES]
    return protocol,client


def run():
    protocol,client=setup();read=acquired.train.read
    bank=acquired.train.actor.acquisition.previous.parent.OUT
    public={s['key']:s for s in read(bank/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:acquired.train.actor.acquisition.current_case_interface(r['kernel'])
        for r in read(bank/'SARA_native_kernel_bank.json')}
    grading=read(acquired.train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    rows=[]
    for arm in acquired.train.ARMS:
        library=read(OUT/'libraries'/(arm+'.json'))
        for sid in protocol['fixed_sources']:
            row=acquired.train.actor.execute_one(client,protocol,arm,library,sid,kernels[sid],public[sid],
                'whole_fixed_TRAIN',purpose='skill_actor')
            rows.append(acquired.train.scored(row,public,grading))
    immutable_json(OUT/'whole_results.json',{'rows':rows,'DEV_TEST_loaded':False,'goal_complete':False})
    # Isolate reading mode on the method's SAME acquired schema/converter.
    library=read(OUT/'libraries'/(acquired.train.ARMS[0]+'.json'))
    component=next(c for c in library['components']if c['id']==acquired.COMPONENT)
    neural={k:v for k,v in component.items()if k!='observation_program'}
    ablations=[]
    for sid in protocol['fixed_sources']:
        target=OUT/'same_contract_neural_ablation'/(digest(sid)+'.json')
        if target.exists():ablations.append(read(target));continue
        pub=public[sid]['views'][0]['public'];entry={'source':sid}
        try:
            observation,receipt=acquired.train.actor.read_component(client,protocol,sid,neural,kernels[sid],pub,purpose='skill_actor')
            converted=[component_value(library,neural,kernels[sid],pub,v)for v in observation[acquired.COMPONENT]['views']]
            entry.update(observation=observation,receipt=receipt,converted=converted,
                source_checks=[acquired.source_checks(sid,v)for v in converted])
            original=next(r for r in rows if r['candidate']==acquired.train.ARMS[0]and r['source']==sid)
            if original.get('observation')and set(original['observation'])==set(original['plan']['component_ids']):
                changed=deepcopy(original['observation']);changed.update(observation)
                grounded=acquired.train.actor.convert(library,original['plan']['component_ids'],kernels[sid],pub,changed)
                execution=acquired.train.actor.execute_alternatives(kernels[sid],grounded)
                entry.update(same_other_observations=True,whole_execution=execution,whole_grounded=grounded)
        except Exception as error:entry['error']=type(error).__name__+': '+str(error)
        immutable_json(target,entry);ablations.append(entry)
    immutable_json(OUT/'result.json',{'whole_rows':rows,'same_contract_neural_ablation':ablations,
        'teacher_calls':0,'no_new_sources_seeds_or_configurations':True,'DEV_TEST_loaded':False,
        'not_an_independent_contribution_certificate':True,'goal_complete':False})
    print(json.dumps({'whole_core_correct':{a:sum(r['execution']['handled']and r['native_score']['correct']for r in rows if r['candidate']==a)for a in acquired.train.ARMS},
        'whole_core_handled':{a:sum(r['execution']['handled']for r in rows if r['candidate']==a)for a in acquired.train.ARMS},
        'neural_ablation_source_usable':[all(v['usable']for v in r.get('source_checks',[]))if r.get('source_checks')else False for r in ablations]}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
