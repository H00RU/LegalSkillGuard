"""Finite actual-query refinement on the existing TRAIN acquisition and last pair.

No teacher, new source, changed model, DEV/TEST, or complete-training queue.
The same finite selector is also available to the independent Free program.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe,fit
from legal_skill_guard.skill_evolution.query_refinement import select_query
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories,attach_scored_theories
from experiments.legal_skill_evolution_open_acquisition_train import evaluate_source
from experiments.legal_skill_evolution_diagnosed_update_train import source_material

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_query_refinement_20261114'
FOLDER=ROOT/'artifacts'/RUN
PARENT=ROOT/'artifacts/legal_skill_evolution_source_functions_20261114'
SCALAR=ROOT/'artifacts/legal_skill_evolution_diagnosed_update_scalar_20261114'
PUBLIC=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING=PUBLIC.with_name('grading.json')
LEDGER=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
ARMS=('ConstraintAcquire','FreeUpdate')
VARIANTS=('C_static','C_active','Free_static','Free_active')
read=lambda p:json.loads(p.read_text())
arm_for=lambda v:'ConstraintAcquire' if v.startswith('C_') else 'FreeUpdate'


def query_ids(arm):
    actual={}
    for key in read(PARENT/'protocol.json')['acquisition_sources']:
        o=read(PARENT/'acquisition'/arm/(key.replace(':','_')+'.json'))['observation']
        for q in o['visible_inputs']['queries']:
            actual.setdefault(q['operation'],set()).add(q['id'])
    library=read(PARENT/arm/'learned.json')
    if set(actual)!={o['name'] for o in library['operations']} or any(len(v)!=1 for v in actual.values()):
        raise ValueError('Actual acquired full-window query IDs must be unambiguous')
    return {k:next(iter(v)) for k,v in actual.items()}


def objective(library,source,grading):
    def value(observation):
        feedback=evaluate_source(library,observation,source,grading)['feedback']
        if feedback['reason']=='execution_error':raise ValueError(feedback['error'])
        return sum(bool(v['core_executed']) and
                   (grading is None or bool((v.get('score')or{}).get('correct')))
                   for v in feedback['views'])
    return value


def offline():
    prior=read(PARENT/'protocol.json');public={s['key']:s for s in read(PUBLIC)};grading=read(GRADING);checks=[]
    for arm in ARMS:
        lib=read(PARENT/arm/'learned.json');ids=query_ids(arm)
        for key in prior['acquisition_sources']:
            name=key.replace(':','_')+'.json';old=read(PARENT/'acquisition'/arm/name)
            exact=read(PARENT/arm/'fitted_execution'/name) if arm=='ConstraintAcquire' else old
            actual=evaluate_source(lib,old['observation'],public[key],grading[key])
            if actual['feedback']!=exact['feedback']:raise ValueError('Shared execution-only factoring changed old feedback')
            choice=select_query(lib,old['observation'],objective(lib,public[key],grading[key]),
                objective_name='lawful_TRAIN_native_correct',query_ids=ids)
            checks.append({'arm':arm,'source':key,'original_feedback_exactly_preserved':True,**choice})
    FOLDER.mkdir(exist_ok=True)
    (FOLDER/'offline_actual_selection.json').write_text(json.dumps({'rows':checks,
        'new_model_requests':0,'conditional_choices_are_not_source_observations':True},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'selected':[(r['arm'],r['source'],r['query'])
        for r in checks if r['query']],'new_model_requests':0}),flush=True)


def prepare():
    if (FOLDER/'protocol.json').exists():return read(FOLDER/'protocol.json')
    prior=read(PARENT/'protocol.json')
    if not read(PARENT/'TERMINAL_PRESERVATION.json')['run_boundary_terminal']:
        raise ValueError('The parent must be preserved and terminal first')
    for name,sha in prior['source_snapshot'].items():
        if hashlib.sha256((PARENT/'source_snapshot'/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Original parent source snapshot changed')
    excluded=set(prior['acquisition_sources']+prior['reuse_sources'])
    for name,fields in [
        ('legal_skill_evolution_source_program_acquisition_20261113',('teacher_sources','fixed_TRAIN_reuse_sources')),
        ('legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113',('reuse_sources',)),
        ('legal_skill_evolution_joint_acquisition_evidence_set_20261114',('acquisition_sources','reuse_sources')),
        (SCALAR.name,('acquisition_sources','reuse_sources'))]:
        old=read(ROOT/'artifacts'/name/'protocol.json')
        for field in fields:excluded.update(old[field])
    excluded.update(s['source'] for s in read(PARENT/'shared/initial_library.json')['spec']['seeds'])
    reuse=[s['key'] for s in read(PUBLIC) if s['dataset']=='ContractNLI' and s['key'] not in excluded]
    if len(reuse)!=2:raise ValueError('Exactly the remaining two original TRAIN mothers expected')
    with sqlite3.connect(LEDGER) as db:rows=db.execute('select * from calls order by id').fetchall()
    if any(r[6]=='reserved' for r in rows):raise ValueError('Reconcile physical requests first')
    source_files=[Path(__file__),ROOT/'experiments/legal_skill_evolution_open_acquisition_train.py',
        ROOT/'experiments/legal_skill_evolution_diagnosed_update_train.py',
        *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT/'tests').glob('test_skill_evolution*.py'))]
    data=[PUBLIC,GRADING,FOLDER/'offline_actual_selection.json',PARENT/'protocol.json',
          PARENT/'TERMINAL_PRESERVATION.json',PARENT/'shared/initial_library.json',
          *(PARENT/a/'learned.json' for a in ARMS),
          *(PARENT/'acquisition'/a/(k.replace(':','_')+'.json') for a in ARMS for k in prior['acquisition_sources'])]
    protocol={'run_id':RUN,'same_goal':True,'goal_complete':False,'parent_run':PARENT.name,
        'acquisition_sources':prior['acquisition_sources'],'reuse_sources':reuse,
        'selection':'Last2 original-order TRAIN excluding all prior source-program/fixed-pair/seed studies, before this run. Historical full TRAIN exposure disclosed.',
        'variants':list(VARIANTS),'query_ids_from_actual_training':{a:query_ids(a) for a in ARMS},
        'acquisition_objective':'lawful_TRAIN_native_correct','reuse_objective':'unlabeled_core_coverage',
        'counterfactuals_never_reused_as_actual_observations':True,
        'query_selector_public_to_both_acquisition_architectures':True,
        'no_new_teacher_or_legal_rule':True,'no_new_full_training_DEV_TEST_or_paper':True,
        'executor_profile':prior['executor_profile'],'teacher_profile':prior['teacher_profile'],
        'source_snapshot':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},
        'data_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(FOLDER/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in rows})
    for name in ('base.json','grammar.json','shared/initial_library.json'):
        immutable_json(FOLDER/name,read(PARENT/name))
    for key in prior['acquisition_sources']:
        name=key.replace(':','_')+'.json'
        for sub in ('upstream','shared_source_outputs'):immutable_json(FOLDER/sub/name,read(PARENT/sub/name))
    for file in source_files:
        target=FOLDER/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(file.read_bytes())
    immutable_json(FOLDER/'protocol.json',protocol)
    return protocol


def setup():
    p=prepare()
    for name,sha in {**p['source_snapshot'],**p['data_sha256']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen input changed: '+name)
    ledger=EvolutionLedger(LEDGER,run_id=RUN,
        sources={'train':p['acquisition_sources']+p['reuse_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger,{s['key']:s for s in read(PUBLIC)}


def refine(library,observation,source,grading,client,variant,stage,histories):
    requests=[];decisions=[];current=observation;ids=read(FOLDER/'protocol.json')['query_ids_from_actual_training'][arm_for(variant)]
    while True:
        decision=select_query(library,current,objective(library,source,grading),query_ids=ids,
            objective_name='lawful_TRAIN_native_correct' if grading is not None else 'unlabeled_core_coverage')
        decisions.append(decision)
        if decision['query'] is None:break
        requests.append(decision['query']);v=observation['visible_inputs']
        upstream=read(FOLDER/'shared_source_outputs'/(source['key'].replace(':','_')+'.json'))['source_output']
        current=observe(client,RUN+':'+stage+':'+variant+':'+source['key'],source['key'],library,
            source_text=v['source_text'],units=v['units'],source_output=upstream,
            previous_observations=[current,*histories],requested_queries=requests,
            save_event=lambda e:immutable_json(FOLDER/stage/variant/'events'/(digest(e['call_id'])+'.json'),e))
    return current,decisions


def train():
    p,ledger,public=setup();grading=read(GRADING)
    for variant in VARIANTS:
        arm=arm_for(variant);library=read(PARENT/arm/'learned.json');observations=[];profiles=[]
        if (FOLDER/variant/'learned.json').exists():continue
        for key in p['acquisition_sources']:
            name=key.replace(':','_')+'.json';dst=FOLDER/'acquisition'/variant/name
            if dst.exists():row=read(dst)
            else:
                old=read(PARENT/'acquisition'/arm/name);o=old['observation'];decisions=[]
                if variant.endswith('_active'):
                    histories=[read(root/'acquisition'/a/name)['observation'] for root in (PARENT,SCALAR) for a in ARMS]
                    o,decisions=refine(library,o,public[key],grading[key],FrozenExecutor(ledger,FOLDER,p['executor_profile']),variant,'acquisition',histories)
                row={'source':key,'observation':o,'query_selection':decisions,
                     **evaluate_source(library,o,public[key],grading[key])}
                if arm=='ConstraintAcquire':
                    enumerator=admissible_theories if o['context']['unknown_groups'] else admissible_direct_compositions
                    profile=enumerator(library,o,contract_checker(library['spec'],public[key],grading[key]),timeout_seconds=90)
                    if profile['status']!='complete':
                        immutable_json(FOLDER/variant/'incomplete_profiles'/name,profile)
                        raise ValueError('Preserve actual reads before repairing the finite search')
                    row['profile']=profile
                immutable_json(dst,row)
                print(json.dumps({'stage':'acquisition','variant':variant,'source':key,
                    'correct':objective(library,public[key],grading[key])(o),'extra_queries':len(decisions)-1 if decisions else 0}),flush=True)
            observations.append(row['observation'])
            if 'profile' in row:profiles.append(row['profile'])
        if arm=='ConstraintAcquire':
            library,result=fit(library,[attach_scored_theories(o,a) for o,a in zip(observations,profiles)],timeout_seconds=90)
            immutable_json(FOLDER/variant/'fit.json',result)
            if result['status']!='sat':raise ValueError('Inspect real fit failure; do not ask the teacher again')
        immutable_json(FOLDER/variant/'learned.json',library)
        for key,o in zip(p['acquisition_sources'],observations):
            immutable_json(FOLDER/variant/'fitted_execution'/(key.replace(':','_')+'.json'),evaluate_source(library,o,public[key],grading[key]))
    immutable_json(FOLDER/'library_freeze.json',{'libraries':{v:digest(read(FOLDER/v/'learned.json')) for v in VARIANTS},
        'reuse_sources':p['reuse_sources'],'reuse_labels_not_used':True,'goal_complete':False})


def reuse():
    p,ledger,public=setup()
    if not (FOLDER/'library_freeze.json').exists():raise ValueError('Freeze all four libraries first')
    for variant in VARIANTS:
        library=read(FOLDER/variant/'learned.json')
        for key in p['reuse_sources']:
            name=key.replace(':','_')+'.json';dst=FOLDER/'reuse'/variant/name
            if dst.exists():continue
            pub,units,shared=source_material(FOLDER,public,key);history=[]
            if variant.endswith('_active'):history=[read(FOLDER/'reuse'/variant.replace('_active','_static')/name)['observation']]
            client=FrozenExecutor(ledger,FOLDER,p['executor_profile'])
            o=observe(client,RUN+':reuse:'+variant+':'+key,key,library,
                source_text=pub['source_text'],units=units,source_output=shared,previous_observations=history,
                save_event=lambda e:immutable_json(FOLDER/'reuse'/variant/'events'/(digest(e['call_id'])+'.json'),e))
            decisions=[]
            if variant.endswith('_active'):o,decisions=refine(library,o,public[key],None,client,variant,'reuse',history)
            immutable_json(dst,{'source':key,'observation':o,'query_selection':decisions,
                **evaluate_source(library,o,public[key],None),'native_labels_used_in_selection':False})
            print(json.dumps({'stage':'reuse_unscored','variant':variant,'source':key,
                'core_coverage':objective(library,public[key],None)(o),'extra_queries':len(decisions)-1 if decisions else 0}),flush=True)


def score():
    p,_,public=setup()
    if any(not (FOLDER/'reuse'/v/(k.replace(':','_')+'.json')).exists() for v in VARIANTS for k in p['reuse_sources']):
        raise ValueError('Complete and save all unlabeled executions before scoring any new pair')
    grading=read(GRADING)
    for variant in VARIANTS:
        library=read(FOLDER/variant/'learned.json')
        for key in p['reuse_sources']:
            name=key.replace(':','_')+'.json';row=read(FOLDER/'reuse'/variant/name)
            immutable_json(FOLDER/'reuse_scores'/variant/name,evaluate_source(library,row['observation'],public[key],grading[key]))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['offline','prepare','train','reuse','score']);args=ap.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'offline':offline,'prepare':prepare,'train':train,'reuse':reuse,'score':score}[args.phase]()
