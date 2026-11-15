"""Matched neural recovery of the frozen service observation contract.

Only original TRAIN is used. Initial observations reuse compiled programs and
exact paid reads; missing cache evidence is explicit, never a model failure.
The ordinary reader can identify an already failed component. No teacher or
library update, new source, DEV/TEST, or unchanged request repetition.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_service_observer_validate as parent
from experiments import legal_skill_evolution_service_observer_TRAIN_audit as source_audit
from experiments import legal_skill_evolution_observation_TRAIN_replay as cache_index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_statutory_givens import constrain
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate,next_component,compare_reads
from legal_skill_guard.skill_evolution.observation_component_library import plan,component_value
from legal_skill_guard.skill_evolution.observation_scope_normalization import normalize
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import render_messages

ROOT=parent.ROOT
RUN='legal_skill_evolution_residual_reader_matched_20261115'
OUT=ROOT/'artifacts'/RUN
PREFIXES=('815f377b','982d5316','bb6b0bc1','3e22604a','ed3f34d3')


class NoNewPaidEvidence:
    artifacts=OUT/'offline_cache'
    ledger=SimpleNamespace(run_id=RUN)

    def tokenize(self,*args,**kwargs):raise RuntimeError('OfflineReadUnavailable: no exact paid response; no dispatch')
    def generate(self,*args,**kwargs):raise AssertionError('Offline preparation never generates')


def setup():
    path=OUT/'protocol.json';public,kernels=parent.acquired.data()
    if not path.exists():
        previous=parent.train.read(parent.OUT/'protocol.json')
        library_path=parent.OUT/'selected_libraries/CoverageRecombine.json'
        files=[Path(__file__),Path(parent.train.actor.__file__),Path(source_audit.__file__),
            library_path,parent.OUT/'protocol.json']
        files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
        files+=[ROOT/'tests'/name for name in ('test_skill_evolution_partial_native_proof.py',
            'test_skill_evolution_facts_only_component.py')]
        sources=[s for p in PREFIXES for s in public if s.split(':')[1].startswith(p)]
        assert len(sources)==5 and all(public[s]['split']=='train'for s in sources)
        protocol={k:previous[k]for k in ('sources','executor_profile','shared_native_event_encoding')}
        protocol.update(run_id=RUN,same_goal=True,fixed_sources=sources,library_path=str(library_path.relative_to(ROOT)),
            question='Under the same frozen acquired contract, does actual program residual feedback add to ordinary rereading?',
            initial='Actual compiled reads plus exactly reusable paid prefix; stop before the first new neural request.',
            exclusion_rules={'815f377b':'Native query first requires payment/termination timing, not the selected service contract.',
                '982d5316':'Source names no employer; frozen service converter requires known employer for a complete record.'},
            source_exclusions_are_not_model_failures=True,teacher_calls=0,thinking=False,
            no_new_sources_seeds_or_model_configuration=True,DEV_TEST_loaded=False,goal_complete=False,
            ledger_before=parent.acquired.lineage.ledger_snapshot(),
            source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files})
        immutable_json(path,protocol)
        for f in files:
            target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    protocol=parent.train.read(path)
    for name,sha in protocol['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    library=parent.train.read(ROOT/protocol['library_path'])
    cache,conflicts,origins={},{},{}
    names=cache_index.CACHE_NAMES+(parent.acquired.BASE.name,)
    for name in names:
        for f in (ROOT/'artifacts'/name/'component_reads').glob('*.json'):
            value=parent.train.read(f)
            if value['source']not in protocol['fixed_sources']:continue
            key=value['wire_input_sha256'];body={k:value[k]for k in ('source','component_id','value','error')}
            if key in cache and body!=cache[key][0]:conflicts.add(key)
            cache.setdefault(key,(body,value));origins.setdefault(key,[]).append(str(f.relative_to(ROOT)))
    for key,(_,value)in cache.items():
        if key in conflicts:continue
        for target in (OUT/'component_reads',NoNewPaidEvidence.artifacts/'component_reads'):
            immutable_json(target/(key+'.json'),value)
    immutable_json(OUT/'paid_cache_origins.json',{'origins':origins,'conflicts_not_replayed':sorted(conflicts)})
    return protocol,library,public,kernels


def initial_prefix(p,library,source,kernel):
    pub=source['views'][0]['public'];sid=source['key'];selection=plan(library,kernel)
    observation,failed,history,reads={},{},[],[]
    components={c['id']:c for c in library['components']};missing=None
    while True:
        observed,receipts=normalize(library,kernel,pub,observation)
        execution=evaluate(library,kernel,pub,observed,sid)
        history.append({'observed_components':sorted(observation),'execution':execution,
            'scope_normalization_receipts':receipts})
        if execution['handled']or any(w['source_review']['failures']for w in execution['binding_executions']):break
        cid=next_component(library,kernel,observation,failed,execution,selection,'native_residual')
        if cid is None:break
        try:
            value,receipt=parent.train.actor.read_component(NoNewPaidEvidence(),p,sid,components[cid],kernel,pub,purpose='skill_actor')
            observation.update(value);reads.append({'component_id':cid,**receipt})
        except ValueError as error:
            if 'OfflineReadUnavailable:' in str(error):missing={'component_id':cid,'reason':str(error)};break
            failed[cid]=str(error)
    return {'observation':observed,'execution':execution,'reads':reads,'history':history,
        'failed_paid_reads':failed,'first_missing_paid_read':missing,'new_model_calls':0,
        'missing_cache_is_not_a_failed_prediction':True}


def prepare():
    p,library,public,kernels=setup();rows=[]
    for sid in p['fixed_sources']:
        initial=initial_prefix(p,library,public[sid],kernels[sid])
        def no_dispatch(policy,action):raise ValueError('Offline action probe; no physical request')
        probe=compare_reads(library,kernels[sid],public[sid]['views'][0]['public'],sid,initial['observation'],no_dispatch)
        exclusion=next((r for pref,r in p['exclusion_rules'].items()if sid.split(':')[1].startswith(pref)),None)
        actions={name:r.get('action',{}).get('component_ids')for name,r in probe['policies'].items()}
        eligible=probe['eligible']and not exclusion and all(v==['service_events']for v in actions.values())and len(actions)==2
        rows.append({'source':sid,'initial':initial,'offline_action_probe':probe,
            'paired_read_eligible':eligible,'exclusion_reason':exclusion,
            'selection_uses_native_labels':False,'actions':actions})
    result={'rows':rows,'eligible_sources':[r['source']for r in rows if r['paired_read_eligible']],
        'new_model_calls':0,'teacher_calls':0,'DEV_TEST_loaded':False,'goal_complete':False}
    immutable_json(OUT/'offline_before.json',result)
    print(json.dumps({'eligible_sources':result['eligible_sources'],'actions':[
        {'source':r['source'].split(':')[1][:8],'before_handled':r['initial']['execution']['handled'],
            'choices':r['actions'],'excluded':r['exclusion_reason'],'missing_cache':r['initial']['first_missing_paid_read']}
        for r in rows]},ensure_ascii=False),flush=True)


def run():
    p,library,public,kernels=setup();before=parent.train.read(OUT/'offline_before.json')
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=[OUT]
    grading=parent.train.read(parent.train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    results=[]
    for initial in before['rows']:
        if not initial['paired_read_eligible']:continue
        sid=initial['source'];target=OUT/'pairs'/(digest(sid)+'.json')
        if target.exists():results.append(parent.train.read(target));continue
        kernel=kernels[sid];pub=public[sid]['views'][0]['public']
        def read(policy,action):
            assert action['component_ids']==['service_events']and action['facts_only']is True
            task={'current_case':{'facts':pub['facts']},
                'current_observation':{k:v for k,v in initial['initial']['observation'].items()if k in action['component_ids']},
                'existing_unresolved_messages':initial['initial']['execution']['unread_components']}
            schema=constrain(action['schema'],pub,kernel);messages=render_messages(action['prompt'],task,schema)
            count=client.tokenize(messages,thinking=False)['count']
            if count+p['executor_profile']['max_tokens']>p['executor_profile']['context_tokens']:raise ValueError('Frozen context exceeded')
            response=client.generate(RUN+':'+policy+':'+sid,source=sid,purpose='skill_actor',thinking=False,
                messages=messages,schema=decoding_schema(schema)[0])
            immutable_json(OUT/'raw_matched'/policy/(digest(sid)+'.json'),response)
            if response['finish_reason']!='stop':raise ValueError('generation_truncated: '+response['finish_reason'])
            return json.loads(response['content']),{k:response.get(k)for k in ('usage','finish_reason','elapsed_seconds','cache_hit','reused_physical_call_id')}
        value={'source':sid,**compare_reads(library,kernel,pub,sid,initial['initial']['observation'],read)}
        component=next(c for c in library['components']if c['id']=='service_events')
        for label,row in value['policies'].items():
            observation=row.get('observation_after',{}).get('service_events')
            if observation:
                parts=[component_value(library,component,kernel,pub,v)for v in observation['views']]
                checks=[source_audit.check(part,source_audit.reference(sid))for part in parts]
                row.update(service_conversions=parts,service_source_checks=checks,
                    service_component_usable=all(c['usable']for c in checks))
            scored=parent.train.scored({'source':sid,'execution':row['execution'],'reads':[],
                'grounded':{},'fallback':False},public,grading)
            row['native_score']=scored['native_score'];row['partial_source_review']=scored['partial_source_review']
            row['source_checked_core_success']=bool(row['execution']['handled']and row['native_score']['correct']and
                not row['partial_source_review']['failures']and row.get('service_component_usable'))
        immutable_json(target,value);results.append(value)
        print(json.dumps({'source':sid,'policies':{name:{'handled':r['execution']['handled'],
            'service_usable':r.get('service_component_usable'),'core_success':r['source_checked_core_success'],
            'error':r.get('error')}for name,r in value['policies'].items()}}),flush=True)
    immutable_json(OUT/'result.json',{'pairs':results,'same_frozen_contract_and_initial_observation':True,
        'no_library_update_no_teacher':True,'DEV_TEST_loaded':False,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','run'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'run':run}[args.phase]()
