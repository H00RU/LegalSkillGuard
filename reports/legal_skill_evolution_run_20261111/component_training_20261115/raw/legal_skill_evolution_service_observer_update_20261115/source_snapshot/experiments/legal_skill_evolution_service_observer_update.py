"""Jointly learn source-only service observations and their query conversion.

Continue the fixed TRAIN diagnosis with independent equally expressive teachers.
The host supplies transport and source checks, never missing service facts.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_compiled_observer_learning as education
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenTeacher,FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value,validate
from legal_skill_guard.skill_evolution.sara_statute_kernel import literal_date

ROOT=train.ROOT
RUN='legal_skill_evolution_service_observer_update_20261115'
OUT=ROOT/'artifacts'/RUN
BASE=ROOT/'artifacts/legal_skill_evolution_compiled_observer_whole_validation_20261115'
PRIOR=ROOT/'artifacts/legal_skill_evolution_native_scope_pilot_20261115'
COMPONENT='service_events'
SCHEMA=record_schema({'rationale':{'type':'string'},'candidates':{'type':'array','minItems':2,'maxItems':2,
    'items':record_schema({k:{'type':'string','minLength':1}for k in
        ('rationale','schema_json','prompt','observation_program','conversion_program')})}})
SYSTEM='''Revise one learned factual observation component from its actual TRAIN
semantic failure. Return two self-contained reusable candidate revisions. No tools.
Both candidates jointly define schema_json, a neural reader prompt, a facts-only
observation_program and a conversion_program. This is external program learning,
not model weight training. Both arms have identical information and capabilities.

Actual failure: the weak reader copied the query workday into service dates even
though its prompt prohibited this. The old schema asks is_query_service while
reading facts; that mixes factual reading with query identity. You may replace
this unsuitable schema and converter. Do not preserve obsolete field aliases.

The observation program defines apply(inputs,premises). Runtime inputs has ONLY
facts; premises is empty. No question, query, source ID, reference facts, earlier
case, annotation, legal answer or statute is available. Return the component
VALUE, not a wrapper named service_events. Learn reusable source grammatical and
role patterns, including coordinated payees and passive paid-for-service. Preserve
actual source roles, event-specific periods, kinds and locations. An annual
payment year does not state an exact service period. Enrollment dates are not
service dates. Unsupported/ambiguous source constructions remain unread/null;
do not confidently output empty when actual service language is unsupported.
Facts with no service event may have an explicitly complete empty scan. Include
exact nonempty original facts witnesses. Dates/roles without support stay unknown.
Choose your own useful schema; avoid query-derived fields in the factual view.

The converter also defines apply(inputs,premises). Its keys are component_id,
view, public_case, kernel; it can use the supplied existing shared_helpers. It
returns exactly facts, negative_givens, witnesses, complete, reasons, following
the current component contract. Align observed event identity with native query
arguments only AFTER reading facts, retaining original roles and properties.
Multiple possible referents must remain unresolved or explicit coherent views;
never select whichever makes the target true. Do not infer factual dates from
the query; query values may only identify an actually observed referent. The
converter must not hide a second source-reading algorithm; read semantics belong
in the observation program. Use public_case only to validate witness provenance.
Do not emit legal predicates or native verdicts, change author law, skip facts
which would make the answer wrong, or weaken completeness/source checks.

Both programs are pure Python top-level functions, no imports, IO, nested
functions, lambdas, classes, reflection or recursion. Standard re is prebound;
supported string/list/dict operations and pure calendar helpers are available.
Observer code cannot use converter shared helpers; include what it needs.
Never branch on training person/company names, exact case strings, source IDs,
dates or years. Extract current entities/dates instead. General month names,
grammatical cues and legal query signatures in converter code are permitted.
No native answer strings in code. Do not run/score your code. Return strict JSON.

Independent ordinary teaching has the same modular architecture, source-only
input, code execution, joint schema/conversion edits, current programs, error
feedback and budget. It may propose the strongest equally expressive approach.
Compilation and input separation alone are shared engineering, not a method
contribution. Do not weaken the ordinary control.
'''


def data():
    bank=train.actor.acquisition.previous.parent.OUT
    public={s['key']:s for s in train.read(bank/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:train.actor.acquisition.current_case_interface(r['kernel'])
        for r in train.read(bank/'SARA_native_kernel_bank.json')}
    return public,kernels


def prepare():
    parent=train.read(education.OUT/'protocol.json');public,kernels=data()
    acquisition=[s for s in public if any(s.startswith('SARA_v2_Binary:'+p)for p in education.ACQUISITION_PREFIXES)]
    reuse=[s for s in public if s.startswith('SARA_v2_Binary:'+education.REUSE_PREFIX)]
    assert len(acquisition)==2 and len(reuse)==1 and not set(acquisition)&set(reuse)
    libraries={a:train.read(BASE/'libraries'/(a+'.json'))for a in train.ARMS}
    prior=train.read(PRIOR/'result.json')['rows'][0]
    source_file=ROOT/kernels[acquisition[0]]['statute_directory']/'section3306.pl'
    task={'current_libraries':libraries,
        'original_TRAIN_cases':[{'source':s,'public':public[s]['views'][0]['public'],
            'kernel':kernels[s]}for s in acquisition],
        'actual_prior_failure':{k:prior[k]for k in ('source','raw_observation','grounded',
            'partial_source_review','learning_signal','native_scope_history')},
        'unchanged_author_section3306':source_file.read_text(),
        'shared_runtime_facts_only_scope':True,'source_feedback':[
            'The university case states a service with Alice worker and the named university employer; the 2017 payment year and query workday do not state service dates.',
            'Agricultural labor has three separately named workers paid by Alice over its stated service period. The next sentence reverses payer/worker and states a different work period; it must not become agricultural labor by copying the previous sentence.',
            'Query alignment changes opaque service event identifiers only; it cannot turn query values into observed properties.'],
        'runtime_observer_input_example':{'facts':'<the current original facts>'},
        'fixed_reuse_source_not_in_teacher_task':True,'original_B8_exposure_disclosed':True}
    immutable_json(OUT/'teacher_task.json',task)
    paths=[Path(__file__),Path(train.actor.__file__),BASE/'protocol.json',OUT/'teacher_task.json']
    paths+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    paths+=[ROOT/'tests/test_skill_evolution_facts_only_component.py']
    paths+=[BASE/'libraries'/(a+'.json')for a in train.ARMS]
    protocol={'run_id':RUN,'same_goal':True,'sources':parent['sources'],'acquisition_sources':acquisition,
        'fixed_reuse_sources':reuse,'teacher_profile':parent['teacher_profile'],
        'executor_profile':parent['executor_profile'],'thinking':False,'shared_native_event_encoding':
        train.read(BASE/'protocol.json')['shared_native_event_encoding'],
        'native_proof_routing':True,'shared_public_pure_calculation':True,
        'both_arms_joint_schema_observer_conversion':True,'facts_only_neural_ablation_same_schema':True,
        'original_128_TRAIN_only_no_new_source':True,'prior_B8_exposure_not_a_blind_split':True,
        'DEV_TEST_loaded':False,'goal_complete':False,'ledger_before':lineage.ledger_snapshot(),
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}}
    immutable_json(OUT/'protocol.json',protocol)
    for p in paths:
        dst=OUT/'source_snapshot'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==p.read_bytes()
        else:dst.write_bytes(p.read_bytes())
    print(json.dumps({'task_characters':len(json.dumps(task)),'acquisition':acquisition,'reuse':reuse}),flush=True)


def checked_protocol():
    p=train.read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def acquire():
    p=checked_protocol();task=train.read(OUT/'teacher_task.json')
    assert not strict_output_schema_issues(SCHEMA)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)
    def one(arm):
        path=OUT/arm/'teacher.json'
        if path.exists():return
        mode=('Use the actual error to jointly revise the observation representation and converter, preserving independently useful states.'
            if arm==train.ARMS[0]else 'Independently generate the strongest ordinary-teacher revisions with all the same information and abilities.')
        response=FrozenTeacher(ledger,OUT,p['teacher_profile']).propose(RUN+':'+arm+':joint_update',
            source_ids=p['acquisition_sources'],system_prompt=SYSTEM+'\n'+mode,
            user_prompt=json.dumps(task,ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(path,response);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in train.ARMS]
        for job in jobs:job.result()


def source_checks(sid,part):
    if not part['complete']or part['reasons']:return {'usable':False,'errors':[],
        'reason':'Explicit unresolved service observation'}
    facts=deepcopy(part['facts'])
    for r in facts:
        if r['predicate']in ('start_','end_'):r['arguments'][1]=literal_date(r['arguments'][1])
    def values(p,e):return [r['arguments'][1]for r in facts if r['predicate']==p and r['arguments'][0]==e]
    observed=[]
    for r in facts:
        if r['predicate']=='service_':
            event=r['arguments'][0]
            observed.append({'worker':values('agent_',event),'employer':values('patient_',event),
                'start':values('start_',event),'end':values('end_',event),'kind':values('purpose_',event)})
    errors=[]
    if ':250fc5' in sid:
        expected=[('Alice','Johns Hopkins University',None,None,None)]
    elif ':d9d6b2' in sid:
        expected=[(w,'Alice','2017-02-01','2017-09-02','agricultural labor')for w in ('Bob','Charlie','Dan')]
        expected.append(('Alice','Bob','2017-04-01','2018-09-02',None))
    elif ':d5e113' in sid:expected=[('Bob','Alice',None,None,'agricultural labor')]
    else:raise ValueError('No new source annotation authorized by this fixed probe')
    if len(observed)!=len(expected):errors.append('Complete service scan has missing or extra original events')
    for worker,employer,start,end,kind in expected:
        matches=[r for r in observed if r['worker']==[worker]and r['employer']==[employer]]
        if len(matches)!=1:errors.append('Source worker/employer service not retained uniquely: '+worker+' / '+employer);continue
        r=matches[0]
        if r['start']!=([start]if start else [])or r['end']!=([end]if end else []):
            errors.append('Wrong, missing or transferred service period: '+worker)
        if kind is not None and r['kind']!=[kind]:errors.append('Source-stated agricultural service kind missing')
        if kind is None and any(k in ('agricultural labor','domestic service')for k in r['kind']):
            errors.append('Unstated restricted service kind')
    return {'usable':not errors,'errors':errors,'observed_service_records':observed,
        'partial_TRAIN_source_annotation_not_native_answer':True}


def validate_updates():
    p=checked_protocol();public,kernels=data();client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=RUN))
    candidates=[];selected={}
    for arm in train.ARMS:
        base=train.read(BASE/'libraries'/(arm+'.json'));old=next(c for c in base['components']if c['id']==COMPONENT);valid=[]
        for i,proposal in enumerate(train.read(OUT/arm/'teacher.json')['value']['candidates']):
            entry={'arm':arm,'candidate':i,'cases':[]}
            component={**deepcopy(old),**{k:v for k,v in proposal.items()if k!='rationale'},'facts_only':True}
            library=deepcopy(base);library['components']=[component if c['id']==COMPONENT else c for c in library['components']]
            try:
                for name in ('observation_program','conversion_program'):
                    validate_adapter(component[name],excluded_source_ids=p['sources'])
                    for n in ast.walk(ast.parse(component[name])):
                        if isinstance(n,ast.Constant):
                            assert n.value not in ('Alice','Bob','Charlie','Dan','Johns Hopkins University'),'Training entity constant'
                            if type(n.value)is int:assert n.value not in (2015,2017,2018,2019),'Training year constant'
                validate(library,kernels[p['acquisition_sources'][0]])
                for sid in p['acquisition_sources']:
                    pub=public[sid]['views'][0]['public'];observed,receipt=train.actor.read_component(client,p,sid,component,kernels[sid],pub,purpose='skill_actor')
                    parts=[component_value(library,component,kernels[sid],pub,v)for v in observed[COMPONENT]['views']]
                    checks=[source_checks(sid,v)for v in parts]
                    entry['cases'].append({'source':sid,'observation':observed,'receipt':receipt,
                        'converted':parts,'checks':checks})
                errors=sum(len(c['errors'])for r in entry['cases']for c in r['checks'])
                usable=sum(all(c['usable']for c in r['checks'])for r in entry['cases'])
                entry.update(source_errors=errors,usable_cases=usable)
                valid.append((errors,-usable,len(component['observation_program'])+len(component['conversion_program']),i,library))
            except Exception as error:entry['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'candidate_results'/arm/(str(i)+'.json'),entry);candidates.append(entry)
        if valid:
            choice=min(valid,key=lambda v:v[:-1])
            if choice[0]==0 and -choice[1]==len(p['acquisition_sources']):
                library=choice[-1];path=OUT/'selected_libraries'/(arm+'.json');immutable_json(path,library)
                selected[arm]={'candidate':choice[3],'path':str(path.relative_to(ROOT)),'sha256':digest(library)}
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only_selection':True})
    reuse=[];whole=[]
    grading=train.read(train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    for arm,choice in selected.items():
        library=train.read(ROOT/choice['path']);component=next(c for c in library['components']if c['id']==COMPONENT)
        for sid in p['fixed_reuse_sources']:
            observed,receipt=train.actor.read_component(client,p,sid,component,kernels[sid],public[sid]['views'][0]['public'],purpose='skill_actor')
            parts=[component_value(library,component,kernels[sid],public[sid]['views'][0]['public'],v)for v in observed[COMPONENT]['views']]
            reuse.append({'arm':arm,'source':sid,'observation':observed,'receipt':receipt,'converted':parts,
                'checks':[source_checks(sid,v)for v in parts]})
        sid=next(s for s in p['acquisition_sources']if ':250fc5' in s)
        row=train.actor.execute_one(client,p,arm,library,sid,kernels[sid],public[sid],'whole_university',purpose='skill_actor')
        whole.append(train.scored(row,public,grading))
    immutable_json(OUT/'result.json',{'candidates':candidates,'selected':selected,'fixed_reuse':reuse,
        'whole_university':whole,'new_executor_calls':0,'DEV_TEST_loaded':False,'goal_complete':False,
        'runtime_observers_received_only_current_facts':True,'source_annotations_not_runtime_facts':True,
        'ordinary_teacher_capability_equal_not_independent_contribution':True})
    print(json.dumps({'selected':selected,'reuse_usable':[all(c['usable']for c in r['checks'])for r in reuse],
        'whole':[{'arm':r['candidate'],'handled':r['execution']['handled'],'native_correct':r['native_score']['correct'],
            'source_errors':r['partial_source_review']['failures'],'error':r.get('error')}for r in whole]}),flush=True)


def neural_ablation():
    p=checked_protocol();public,kernels=data();selected=train.read(OUT/'selected_before_reuse.json')['selected']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=[OUT]
    rows=[]
    sources=[next(s for s in p['acquisition_sources']if ':250fc5' in s)]+p['fixed_reuse_sources']
    for arm,choice in selected.items():
        lib=train.read(ROOT/choice['path']);component=next(c for c in lib['components']if c['id']==COMPONENT)
        neural={k:v for k,v in component.items()if k!='observation_program'}
        for sid in sources:
            row={'arm':arm,'source':sid,'same_schema_converter_and_factual_input':True}
            try:
                observed,receipt=train.actor.read_component(client,p,sid,neural,kernels[sid],public[sid]['views'][0]['public'],purpose='skill_actor')
                parts=[component_value(lib,neural,kernels[sid],public[sid]['views'][0]['public'],v)for v in observed[COMPONENT]['views']]
                row.update(observation=observed,receipt=receipt,converted=parts,checks=[source_checks(sid,v)for v in parts])
            except Exception as error:row['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'neural_same_contract'/arm/(digest(sid)+'.json'),row);rows.append(row)
    immutable_json(OUT/'neural_ablation.json',{'rows':rows,'no_new_sources_or_model_config':True,'DEV_TEST_loaded':False})
    print(json.dumps({'neural_usable':[all(c['usable']for c in r.get('checks',[]))if r.get('checks')else False for r in rows]}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','acquire','validate','neural'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'validate':validate_updates,'neural':neural_ablation}[args.phase]()
