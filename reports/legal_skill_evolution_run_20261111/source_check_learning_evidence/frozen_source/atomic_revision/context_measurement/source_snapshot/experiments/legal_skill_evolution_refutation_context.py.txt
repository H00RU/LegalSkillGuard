"""Recover identical evidence IDs and test the observed context-plan defect."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_refutation_atomic import FOLDER,generic
from experiments.legal_skill_evolution_refutation_measure import DEST as PREVIOUS,select
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_learning import instantiate,messages,canonical_evidence
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode

DEST=FOLDER/'context_measurement'


def prepare():
    old=read(FOLDER/'protocol.json');data=read(FOLDER/'input.json');original=read(FOLDER/'validated_bank.json')['tests']
    full=generic(data);retention=next(t for t in original if t['name']=='focus_express_retention_grant')
    expanded={**retention,'name':retention['name']+'_complete_source','window_program':full['window_program']}
    assert len({t['window_program'] for t in original})==1
    local={**full,'name':'generic_source_judge_local','window_program':original[0]['window_program']}
    tests=original+[full,expanded,local]
    paths=[Path(__file__).resolve(),ROOT/'experiments/legal_skill_evolution_refutation_measure.py']+[
        ROOT/'legal_skill_guard/skill_evolution'/n for n in ['refutation_learning.py','refutation_reader.py']]
    p={'run_id':RUN+':context_measurement','train_sources':old['train_sources'],
        'validation_sources':old['validation_sources'],'executor_profile':old['executor_profile'],
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
        'tests_sha256':digest(tests),'input_sha256':sha(FOLDER/'input.json'),
        'same_goal':True,'goal_complete':False,'no_validation_material':True,
        'reason':'Observed TRAIN positive51 lacks its cited paragraph6 principal rule47/48 in the learned preceding2 window. Measure the same acquired retention proposition with complete source and same-window generic control, no new teacher or semantic labels.',
        'evidence_adaptation':'Only identical duplicate support IDs removed with receipt; strict decoder still checks choices/keys/scope/source. Original response/ledger unchanged.',
        'old_physical_requests_not_repeated':True,'no_full_training_DEV_TEST_or_paper':True}
    immutable_json(DEST/'protocol.json',p);immutable_json(DEST/'tests.json',tests)
    for q in paths:
        dst=DEST/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==q.read_bytes()
        else:dst.write_bytes(q.read_bytes())
    for name,h in p['source_sha256'].items():assert sha(ROOT/name)==h
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,data,tests,ledger


def run():
    p,data,tests,ledger=prepare();client=FrozenExecutor(ledger,DEST,p['executor_profile'])
    client.exact_replay_roots=(PREVIOUS,DEST);client.readiness();all_rows=[]
    costs={t['name']:{'physical_requests':0,'prompt_tokens':0,'output_tokens':0,'total_tokens':0,'seconds':0} for t in tests}
    for test in tests:
        for source in p['train_sources']:
            target=DEST/test['name']/(source.replace(':','_')+'.json');old=PREVIOUS/test['name']/target.name
            if target.exists():record=read(target)
            elif old.exists():
                record={**read(old),'reused_previous_record':{'path':str(old.relative_to(ROOT)),
                    'sha256':sha(old),'new_physical_requests':0}}
                immutable_json(target,record)
            else:
                units=data['sources'][source]['units'];qs=[];ops=[];focus={};binding={};rows=[]
                for case in data['training_cases']:
                    if case['source']!=source:continue
                    item=instantiate(test,case,data['operations'][0],units)
                    if item is None:
                        rows.append({'case':case['id'],'test':test['name'],'verdict':'inapplicable','exclude_candidate':False});continue
                    op,q=item;qs.append(q);ops.append(op);focus[q['id']]=case['focus_unit_id'];binding[q['id']]=case
                r=None;adapt=[]
                if qs:
                    prompt=messages(ops,qs,units,focus);wire,_=decoder_schema(schema(ops,qs))
                    r=client.generate(p['run_id']+':'+test['name']+':'+source,
                        source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
                    if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
                    normalized,adapt=canonical_evidence(r['content'])
                    _,answers=decode(ops,qs,units,normalized)
                    rows += [{'case':binding[a['id']]['id'],'test':test['name'],'verdict':a['choice'],
                        'exclude_candidate':a['choice']==test['exclusion_on'],'answer':a} for a in answers]
                record={'source':source,'test':test['name'],'observations':rows,'queries':qs,
                    'operations':ops,'result':r,'deterministic_evidence_adaptation':adapt}
                immutable_json(target,record)
            all_rows+=record['observations'];r=record['result']
            if r:
                c=costs[test['name']];c['physical_requests']+=1
                c['prompt_tokens']+=r['usage']['prompt_tokens'];c['output_tokens']+=r['usage']['completion_tokens']
                c['total_tokens']+=r['usage']['total_tokens'];c['seconds']+=r['elapsed_seconds']
        subset=tests[:tests.index(test)+1];names={t['name'] for t in subset}
        result=select(subset,data['training_cases'],[r for r in all_rows if r['test'] in names],
            {n:v for n,v in costs.items() if n in names})
        print(json.dumps({'test':test['name'],'best_objective':result['objective'],'selected':result['selected_tests']}),flush=True)
    result=select(tests,data['training_cases'],all_rows,costs)
    immutable_json(DEST/'learned_policy.json',result)
    immutable_json(DEST/'completed.json',{'tests':tests,'observations':all_rows,'policy':result,
        'training_fit_not_reuse':True,'goal_complete':False})
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
