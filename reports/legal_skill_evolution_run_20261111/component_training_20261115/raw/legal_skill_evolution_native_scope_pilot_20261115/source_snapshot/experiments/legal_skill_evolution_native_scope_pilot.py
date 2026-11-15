"""Validate the actual missing TRAIN input after offline scoped-proof checks.

One existing source, unchanged independently learned libraries and model profile;
ordinary direct-input routing receives the identical public execution repair.
No training update, new teacher, DEV, TEST or answer-guided fact repair.
"""
import argparse
import fcntl
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_observation_TRAIN_replay as cache_index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate,next_component
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import plan

ROOT=train.ROOT
RUN='legal_skill_evolution_native_scope_pilot_20261115'
OUT=ROOT/'artifacts'/RUN
PREVIOUS=ROOT/'artifacts/legal_skill_evolution_compiled_observer_whole_validation_20261115'


def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('select * from calls order by id')]
    return {'rows':len(rows),'row_hashes':{r['id']:digest(tuple(r.values()))for r in rows},
        'roles':{role:sum(r['role']==role for r in rows)for role in ('executor','teacher')},
        'reserved':sum(r['status']=='reserved'for r in rows)}


def setup():
    read=train.read;parent=read(PREVIOUS/'protocol.json')
    sid=next(s for s in parent['fixed_sources']if ':250fc5' in s)
    bank=train.actor.acquisition.previous.parent.OUT
    public=next(s for s in read(bank/'SARA_corrected_TRAIN_views.json')if s['key']==sid)
    kernel=next(train.actor.acquisition.current_case_interface(r['kernel'])for r in read(bank/'SARA_native_kernel_bank.json')if r['source']==sid)
    assert public['split']=='train' and sid in parent['sources']
    for arm in train.ARMS:immutable_json(OUT/'libraries'/(arm+'.json'),read(PREVIOUS/'libraries'/(arm+'.json')))
    path=OUT/'protocol.json'
    if not path.exists():
        paths=[Path(__file__),Path(train.actor.__file__)]
        paths+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
        paths+=sorted((ROOT/'tests').glob('test_skill_evolution_partial_native_proof.py'))
        paths+=sorted((OUT/'libraries').glob('*.json'))
        paths+=[bank/'SARA_corrected_TRAIN_views.json',bank/'SARA_native_kernel_bank.json',PREVIOUS/'protocol.json']
        protocol={'run_id':RUN,'same_goal':True,'sources':parent['sources'],'fixed_source':sid,
            'executor_profile':parent['executor_profile'],'thinking':False,'teacher_calls':0,
            'native_proof_routing':True,'shared_native_event_encoding':FACTUAL_ENCODING,
            'shared_public_pure_calculation':True,'DEV_TEST_loaded':False,'goal_complete':False,
            'comparison':'same acquired libraries and public runtime; native residual versus direct query input routing',
            'not_an_independent_method_or_generalization_certificate':True,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}}
        immutable_json(path,protocol)
        immutable_json(OUT/'ledger_before.json',snapshot())
        for p in paths:
            dst=OUT/'source_snapshot'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes())
    protocol=read(path)
    for name,sha in protocol['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    cache,conflicts,origins={},{},{}
    names=cache_index.CACHE_NAMES+(PREVIOUS.name,)
    for name in names:
        for p in sorted((ROOT/'artifacts'/name/'component_reads').glob('*.json')):
            row=read(p)
            if row['source']!=sid:continue
            key=row['wire_input_sha256'];body={k:row[k]for k in ('source','component_id','value','error')}
            if key in cache and body!=cache[key][0]:conflicts.add(key)
            cache.setdefault(key,(body,row));origins.setdefault(key,[]).append(str(p.relative_to(ROOT)))
    for key,(_,row)in cache.items():
        if key not in conflicts:immutable_json(OUT/'component_reads'/(key+'.json'),row)
    immutable_json(OUT/'paid_read_origins.json',{'origins':origins,'conflicts_not_reused':sorted(conflicts)})
    return protocol,public,kernel


def offline(protocol,source,kernel):
    client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=RUN))
    result=[];sid=source['key'];pub=source['views'][0]['public']
    for arm in train.ARMS:
        lib=train.read(OUT/'libraries'/(arm+'.json'))
        component=next(c for c in lib['components']if c.get('observation_program'))
        observed,receipt=train.actor.read_component(client,protocol,sid,component,kernel,pub,purpose='skill_actor')
        before=evaluate(lib,kernel,pub,observed,sid)
        selected={p:next_component(lib,kernel,observed,[],before,plan(lib,kernel),p)
            for p in ('native_residual','direct_inputs_first')}
        assert not before['handled'] and all(c=='service_events'for c in selected.values()),selected
        result.append({'arm':arm,'actual_compiled_observation':observed,'receipt':receipt,
            'native_before_service_read':before,'next_provider':selected})
    immutable_json(OUT/'offline_before.json',{'new_model_calls':0,'rows':result,
        'actual_unread_not_false':True,'both_controls_select_same_missing_service_provider':True})


def run(real):
    protocol,source,kernel=setup();offline(protocol,source,kernel)
    if not real:
        print(json.dumps({'offline_passed':True,'next_provider_both_arms':'service_events','new_calls':0}),flush=True);return
    assert snapshot()['reserved']==0
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['sources'],'dev':[],'test':[]},binding=digest(protocol))
    client=FrozenExecutor(ledger,OUT,protocol['executor_profile'])
    client.exact_replay_roots=[OUT,PREVIOUS]+[ROOT/'artifacts'/n for n in cache_index.CACHE_NAMES]
    grading=train.read(train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    rows=[]
    for arm in train.ARMS:
        library=train.read(OUT/'libraries'/(arm+'.json'))
        for policy in ('native_residual','direct_inputs_first'):
            row=train.actor.execute_one(client,{**protocol,'native_read_policy':policy},arm,library,
                source['key'],kernel,source,policy,purpose='skill_actor')
            rows.append(train.scored(row,{source['key']:source},grading))
    after=snapshot();before=train.read(OUT/'ledger_before.json')
    assert all(after['row_hashes'][i]==h for i,h in before['row_hashes'].items())
    immutable_json(OUT/'result.json',{'rows':rows,'ledger_after':after,
        'new_physical_requests':{r:after['roles'][r]-before['roles'][r]for r in after['roles']},
        'prior_ledger_unchanged':True,'DEV_TEST_loaded':False,'goal_complete':False,
        'shared_engineering_repair_not_independent_contribution':True})
    print(json.dumps({'summary':[{'arm':r['candidate'],'policy':r['phase'],
        'handled':r['execution']['handled'],'native_correct':r['native_score']['correct'],
        'source_errors':r['partial_source_review']['failures'],'reads':r.get('component_read_order')}
        for r in rows],'counts':after['roles']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(args.real)
