"""Measure revised probes separately, preserving their actual request costs."""
import argparse
from itertools import combinations
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_refutation_atomic import FOLDER,generic
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_learning import instantiate,messages
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode

DEST=FOLDER/'independent_measurement'


def select(tests,cases,rows,costs):
    names=[t['name'] for t in tests];expected={(c['id'],n) for c in cases for n in names}
    by={(r['case'],r['test']):r for r in rows}
    if len(by)!=len(rows) or set(by)!=expected or set(costs)!=set(names):raise ValueError('Incomplete measured bank')
    scores=[]
    for k in range(len(names)+1):
        for group in combinations(names,k):
            rejected={c['id'] for c in cases if any(by[c['id'],n]['exclude_candidate'] for n in group)}
            false=sum(c['status']=='supported' and c['id'] in rejected for c in cases)
            missed=sum(c['status']=='rejected' and c['id'] not in rejected for c in cases)
            objective=(false,missed,sum(costs[n]['physical_requests'] for n in group),
                       sum(costs[n]['total_tokens'] for n in group),tuple(sorted(group)))
            scores.append((objective,list(group),sorted(rejected)))
    objective,group,rejected=min(scores)
    return {'selected_tests':group,'rejected_training_cases':rejected,'objective':list(objective),
        'objective_order':['false_refutation','uncovered_negative','measured_requests','measured_total_tokens','stable_names'],
        'subsets_evaluated':len(scores),'future_semantics_certified':False,
        'measured_test_costs':costs,'not_a_new_subset_solver':True}


def prepare():
    old=read(FOLDER/'protocol.json');data=read(FOLDER/'input.json');bank=read(FOLDER/'validated_bank.json')
    tests=bank['tests']+[generic(data)]
    paths=[Path(__file__).resolve()]+[ROOT/'legal_skill_guard/skill_evolution'/n for n in
        ['refutation_learning.py','refutation_reader.py']]
    p={'run_id':RUN+':independent_probe_measurement','train_sources':old['train_sources'],
        'validation_sources':old['validation_sources'],'executor_profile':old['executor_profile'],
        'bank_sha256':sha(FOLDER/'validated_bank.json'),'input_sha256':sha(FOLDER/'input.json'),
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
        'measurement':'One distinct test per physical source batch, matching runtime test dispatch. Do not infer subset response invariance from joint multi-test batches.',
        'cost_objective':'Measured physical requests then measured prompt+output tokens; no fitted cost weight.',
        'generic_judge_common_candidate':True,'same_goal':True,'goal_complete':False,'no_validation_adaptation':True}
    immutable_json(DEST/'protocol.json',p)
    for q in paths:
        path=DEST/'source_snapshot'/q.relative_to(ROOT);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():assert path.read_bytes()==q.read_bytes()
        else:path.write_bytes(q.read_bytes())
    for name,h in p['source_sha256'].items():assert sha(ROOT/name)==h
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,data,tests,ledger


def measure():
    p,data,tests,ledger=prepare();client=FrozenExecutor(ledger,DEST,p['executor_profile']);client.readiness()
    rows=[];costs={t['name']:{'physical_requests':0,'prompt_tokens':0,'output_tokens':0,'total_tokens':0,'seconds':0} for t in tests}
    for test in tests:
        for source in p['train_sources']:
            path=DEST/test['name']/(source.replace(':','_')+'.json')
            if path.exists():record=read(path)
            else:
                units=data['sources'][source]['units'];queries=[];ops=[];focus={};binding={};observations=[]
                for case in data['training_cases']:
                    if case['source']!=source:continue
                    item=instantiate(test,case,data['operations'][0],units)
                    if item is None:
                        observations.append({'case':case['id'],'test':test['name'],'verdict':'inapplicable','exclude_candidate':False});continue
                    op,q=item;queries.append(q);ops.append(op);focus[q['id']]=case['focus_unit_id'];binding[q['id']]=case
                r=None
                if queries:
                    prompt=messages(ops,queries,units,focus);wire,_=decoder_schema(schema(ops,queries))
                    identity=p['run_id']+':'+test['name']+':'+source
                    r=client.generate(identity,source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
                    if r['finish_reason']!='stop':raise ValueError('Incomplete; retain without unchanged retry')
                    _,answers=decode(ops,queries,units,r['content'])
                    observations += [{'case':binding[a['id']]['id'],'test':test['name'],'verdict':a['choice'],
                        'exclude_candidate':a['choice']==test['exclusion_on'],'answer':a} for a in answers]
                record={'test':test['name'],'source':source,'observations':observations,'queries':queries,'operations':ops,'result':r}
                immutable_json(path,record)
            rows+=record['observations'];r=record['result']
            if r:
                cost=costs[test['name']];cost['physical_requests']+=1
                cost['prompt_tokens']+=r['usage']['prompt_tokens'];cost['output_tokens']+=r['usage']['completion_tokens']
                cost['total_tokens']+=r['usage']['total_tokens'];cost['seconds']+=r['elapsed_seconds']
        selected=select(tests[:tests.index(test)+1],data['training_cases'],
                        [r for r in rows if r['test'] in {t['name'] for t in tests[:tests.index(test)+1]}],
                        {n:v for n,v in costs.items() if n in {t['name'] for t in tests[:tests.index(test)+1]}})
        print(json.dumps({'measured_test':test['name'],'current_best':selected['objective'],'selected':selected['selected_tests']}),flush=True)
    learned=select(tests,data['training_cases'],rows,costs)
    immutable_json(DEST/'learned_policy.json',learned)
    immutable_json(DEST/'completed.json',{'tests':tests,'observations':rows,'policy':learned,
        'training_fit_not_reuse':True,'goal_complete':False})
    print(json.dumps(learned),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        measure()
