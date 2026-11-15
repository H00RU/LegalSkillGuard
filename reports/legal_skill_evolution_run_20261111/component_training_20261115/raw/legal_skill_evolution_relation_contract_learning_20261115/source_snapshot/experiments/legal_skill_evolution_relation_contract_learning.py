"""Actual error-triggered observation refinement on the fixed original TRAIN.

The method constructs a split candidate from a learned coupled contract. A
same-information ordinary teacher independently proposes two unrestricted views.
All candidates are selected using real frozen-8B acquisition execution, not only
compiled observer programs. Reuse begins after the selected contract is saved.
"""
import argparse
import ast
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import jsonschema

from experiments import legal_skill_evolution_service_observer_update as previous
from experiments import legal_skill_evolution_residual_reader_matched as prior_reads
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.case_observation_contract import execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import validate as validate_contract, schema, split, pullback
from legal_skill_guard.skill_evolution.runtime import render_messages
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from legal_skill_guard.skill_evolution.observation_source_review import review
from legal_skill_guard.skill_evolution.generic_event_observation import PROMPT as GENERIC_PROMPT, schema_for as generic_schema, lower as generic_lower
from legal_skill_guard.skill_evolution.statute_input_dependencies import dependency_graph, query_event_inputs
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, INSTRUCTION, PROGRAM_INSTRUCTION

ROOT=previous.ROOT
RUN='legal_skill_evolution_relation_contract_learning_20261115'
OUT=ROOT/'artifacts'/RUN
BASE=ROOT/'artifacts/legal_skill_evolution_service_observer_dictionary_abi_20261115/selected_libraries/CoverageRecombine.json'
COMPONENTS=('service_events','family_relationship_residence')
ENTRY=record_schema({'id':{'type':'string'},'contract_json':{'type':'string'}})
SCHEMA=record_schema({'rationale':{'type':'string'},
    'base_components':{'type':'array','items':ENTRY},'partitions_json':{'type':'string'},
    'alternate_components':{'type':'array','items':ENTRY},'observation_programs_json':{'type':'string'}})
SYSTEM='''Learn observation contracts from actual frozen-8B failures. No tools.
Return strict JSON. Keep the author law fixed. This is external library learning;
no model weights, new sources or DEV/TEST data are available. Both arms start from
the SAME supplied library and get the same source material, failures, feedback,
runtime abilities and model budget. FreeTeacher is a strong independent control.

Actual failures: the family reader called Bob Alice's daughter although the source
says her father Bob; copied WORK dates into KINSHIP dates; invented a shared home.
The service reader omitted an expressly stated home. Correct schema and long
instructions did not prevent these errors. The new representation must be easier
for the weak reader to recover and must preserve which attributes belong to the
same SOURCE event. Query persons/dates/labels must never become factual inputs.

The supplied relational_observation_contract.py is the COMPLETE executable API.
Use it, not a new language. For each target component return a JSON contract with:
key_domain:string; enumerator:relation name; constants:list of static scalar cues;
relations:[{name,key,fields:[{name,type,copy,nullable,normalizer,enum?}],prompt}];
covered_families:list of public unary native input predicates;
covered_properties:list of public binary factual role/property predicates;
rules:[{id,cost,head:{predicate,arguments,sign:"positive"},
body:[{predicate,arguments,sign:"positive"}]}]. A variable is {"var":"Name"}.
All fields use scalar sorts. Supported field types are string, integer, number,
boolean. Key is non-null string. nullable is false unless a completed source scan
can explicitly establish that optional attribute is not stated. Ambiguity is
unread, not null/false. normalizer is null or literal_date (exact calendar
canonicalization only). A copy field MUST literally occur in a current witness,
before calendar transport. A copied kinship cue can differ from a normalized
relation label; learn its forward meaning and role orientation. Do not hard-code
training entity names, dates, source IDs or native answer strings.
Use an optional finite enum for copied cues that must match rule constants;
keep current entity names open. An unrepresentable source cue is unread. The
author code may test alternative input ports, e.g. purpose_/type_; unobserved
alternative ports cannot be used as known-false facts. Express all coverage.

Each neural relation response has status complete/unread, records (array/null),
and exact facts witnesses. Each complete relation enumerates ALL relevant source
records, retaining identical source keys across relations. Fields absent in one
relation must not erase another event or copy an unrelated date/place. The first
relation is the enumerator; additional reads see actual prior source records and
their opaque keys, never the legal query. Key transport is automatic. Rules are
positive conjunctive queries over observation relations; no native legal rule,
default negation, Python logic or recursion. Head predicates must be declared
native FACTUAL inputs. Skip a head with a null attribute; it is not a negative fact.
The rule-based scopes close only properties whose input relations have actually
been read. Do not claim coverage for a meaning your rules cannot represent.

Service: preserve worker/employer, literal labor kind, service-specific dates,
home/venue and geographic country independently. A payment year and enrollment
period are not service dates. Unknown employer remains unknown. Existing source
event linking is shared. Kinship: preserve the bearer of the copied kinship word
and the person whose relative they are; work dates/place do not establish a
kinship period or residence. Keep supported family meanings and explicit scope;
unsupported families remain unrepresented, not complete empty defaults.

Method arm: base_components contains two learned contracts (the target IDs),
each with ONE initially coupled relation including the genuine role, kind/cue
and optional period/venue fields relevant to that source concept. Do not invent a
new required fact merely to make the base fail. Supply partitions_json mapping
component ID to [{name,fields:[non-key field names],prompt}]. It partitions each
base's non-key fields once; key is added automatically. Group fields according
to the real errors and observation dependencies. Host split copies semantic
rules and derives only needed joined field groups; it does not add legal logic.
Host compares base and split with REAL weak reads on acquisition sources.
alternate_components must be empty. A useless split is allowed to lose.

FreeTeacher arm: base_components and alternate_components each contain two full
contracts, your independently strongest candidates. You may directly choose the
same decomposed architecture, copy cues, joint fields, arbitrary supported
relations and optimized prompts. partitions_json is {}. Do not stay coupled just
to weaken the control. Both of your candidates get identical real acquisition
selection. You see all the method's prior information, not its new learned output.

Both arms may also return observation_programs_json as {"0":{component_id:code},
"1":{component_id:code}} or {}. These optional pure source-only programs define
apply(inputs,premises), inputs={facts:current facts}, and return a COMPLETE view
mapping relation names to the same status/records/witnesses schema. They are
evaluated separately as equally expressive strong compiled controls, never used
to pretend the weak-reader path succeeded. No imports, IO, nested functions,
classes or training names/years. Supplied existing observers remain common assets.
'''


def read(path):
    return json.loads(path.read_text())


def prepare():
    public,kernels=previous.data()
    parent=read(previous.OUT/'protocol.json')
    acquisition=[next(s for s in public if ':'+p in s)for p in ('3e22604a','bb6b0bc1')]
    reuse=[next(s for s in public if ':'+p in s)for p in ('250fc5e7','ed3f34d3')]
    assert not set(acquisition)&set(reuse) and all(public[s]['split']=='train'for s in acquisition+reuse)
    cache_origins={}
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)as db:
        paid=set()
        for identity,source,result in db.execute("select id,source,result from calls where role='executor' and status='completed'"):
            if source not in acquisition+reuse:continue
            record=json.loads(result or '{}');directory=record.get('artifact_directory')
            path=ROOT/directory/'wire_request.json'if directory else None
            if path is None or not path.exists():continue
            wire=json.loads(base64.b64decode(read(path)['body_b64']))
            profile=parent['executor_profile']
            if wire.get('chat_template_kwargs',{}).get('enable_thinking')is not False:continue
            if any(wire.get(k)!=profile[k]for k in ('max_tokens','temperature','seed','top_p','top_k')):continue
            paid.add((identity.rsplit(':',1)[-1],source))
    for folder in sorted((ROOT/'artifacts').glob('legal_skill_evolution*')):
        if any(word in folder.name.lower()for word in ('dev','test')):continue
        for path in sorted((folder/'component_reads').glob('*.json')):
            value=read(path);sid=value.get('source');key=path.stem
            if sid not in acquisition+reuse or (key,sid)not in paid:continue
            if not value.get('receipt') or 'OfflineReadUnavailable' in str(value.get('error')):continue
            target=OUT/'component_reads'/path.name
            if target.exists():
                existing=read(target)
                assert all(existing.get(k)==value.get(k)for k in ('source','component_id','value','error'))
            else:immutable_json(target,value)
            cache_origins.setdefault(key,[]).append(str(path.relative_to(ROOT)))
    immutable_json(OUT/'paid_background_cache_origins.json',cache_origins)
    library=read(BASE)
    paired=read(prior_reads.OUT/'result.json')['pairs']
    family=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_recovery_20261115/common_family_result.json')
    task={'common_current_components':[c for c in library['components']if c['id']in COMPONENTS],
        'common_shared_helpers':library['shared_helpers'],
        'acquisition_sources':[{'source':s,'public':public[s]['views'][0]['public'],
            'native_factual_vocabulary':kernels[s]['fact_arities'],'native_query':kernels[s]['native_query']}for s in acquisition],
        'author_native_programs':{name:(ROOT/kernels[acquisition[0]]['statute_directory']/name).read_text()
            for name in ('section3306.pl','utils.pl','events.pl')},
        'actual_service_failures':[r for r in paired if r['source']in acquisition],
        'actual_family_failure':family,
        'source_feedback':['Bob is the father of Alice, not her daughter. Work dates/place do not assert kinship period or shared residence.',
                           'The domestic service is expressly in her home; omitting that source venue is incomplete.'],
        'relational_observation_contract.py':(ROOT/'legal_skill_guard/skill_evolution/relational_observation_contract.py').read_text(),
        'whole_original_B8_exposure_disclosed_not_a_blind_split':True}
    immutable_json(OUT/'teacher_task.json',task)
    grading=read(previous.train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in acquisition+reuse})
    files=[Path(__file__),Path(previous.__file__),Path(prior_reads.__file__),
           Path(previous.train.actor.__file__),BASE,OUT/'teacher_task.json',OUT/'TRAIN_grading.json']
    source_bank=previous.train.actor.acquisition.previous.parent.OUT
    files += [source_bank/name for name in ('SARA_native_kernel_bank.json','SARA_corrected_TRAIN_views.json')]
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p={k:deepcopy(parent[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        same_initial_library_both_arms=str(BASE.relative_to(ROOT)),
        new_component_scope='service and kinship; unrelated old library entries retained',
        first_comparison='Learned source/transform contracts against coupled/no-split, fixed current interface, and independent ordinary teacher.',
        second_comparison='Same selected contract/initial source records: inverse-native demand vs strong direct/static ordinary supplement.',
        original_TRAIN_only=True,no_full_training_DEV_TEST=True,goal_complete=False,
        ledger_before=lineage.ledger_snapshot(),
        source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files})
    assert not strict_output_schema_issues(SCHEMA)
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'acquisition':acquisition,'reuse':reuse,'task_characters':len(json.dumps(pack_programs(task)))}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def ledger_for(p):
    return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol();ledger=ledger_for(p);task=read(OUT/'teacher_task.json')
    def one(arm):
        path=OUT/arm/'teacher.json'
        if path.exists():return
        value=FrozenTeacher(ledger,OUT,p['teacher_profile']).propose(RUN+':'+arm+':contracts',
            source_ids=p['acquisition_sources'],system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(path,value);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('Method','FreeTeacher')]
        for job in jobs:job.result()


def candidate_libraries():
    public,kernels=previous.data();p=protocol();result={};base=read(BASE)
    for arm in ('Method','FreeTeacher'):
        value=read(OUT/arm/'teacher.json')['value']
        pairs=[value['base_components']]
        if arm=='Method':
            plans=json.loads(value['partitions_json']);second=[]
            for item in pairs[0]:
                contract=json.loads(item['contract_json'])
                assert len(contract['relations'])==1
                second.append({'id':item['id'],'contract_json':json.dumps(split(contract,contract['relations'][0]['name'],plans[item['id']]))})
            pairs.append(second)
        else:pairs.append(value['alternate_components'])
        for index,items in enumerate(pairs):
            assert {v['id']for v in items}==set(COMPONENTS)and len(items)==len(COMPONENTS)
            library=deepcopy(base)
            for item in items:
                contract=json.loads(item['contract_json']);validate_contract(contract,kernels[p['acquisition_sources'][0]])
                group_schema=schema(contract);group_schema['required']=[]
                old=next(c for c in library['components']if c['id']==item['id'])
                new={'id':old['id'],'meaning':old['meaning'],'prompt':'Read the acquired source relations.',
                    'schema_json':json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':group_schema}})),
                    'relation_contract':contract,'complete_native_families':[],'facts_only':True}
                library['components']=[new if c['id']==old['id']else c for c in library['components']]
            result[arm+'/'+str(index)]=library
    return result


def group_read(client,p,sid,component,relation,public,prior):
    contract=component['relation_contract'];group=next(r for r in contract['relations']if r['name']==relation)
    task={'current_facts':public['facts'],'actual_prior_source_records':prior,
          'requested_relation':relation,'shared_key_domain':contract['key_domain']}
    original=schema(contract,[relation]);wire,_=decoding_schema(original)
    messages=render_messages(group['prompt']+'\nRead facts only. Preserve current source keys. Do not infer missing dates, people or places. '
        'Complete scans enumerate every relevant source record. Ambiguity is unread. Return the named relation wrapper.',task,original)
    key=digest({'source':sid,'messages':messages,'schema':wire})
    target=OUT/'relation_reads'/(key+'.json')
    if target.exists():
        saved=read(target)
        if saved.get('error'):raise ValueError(saved['error'])
        return saved['value'],{**saved['receipt'],'cache_hit':True}
    saved={'source':sid,'component':component['id'],'relation':relation,'messages':messages,'schema':original}
    try:
        size=client.tokenize(messages,thinking=False)['count']
        assert size+p['executor_profile']['max_tokens']<=p['executor_profile']['context_tokens']
        raw=client.generate(RUN+':relation:'+key,source=sid,purpose='skill_actor',messages=messages,thinking=False,schema=wire)
        immutable_json(OUT/'raw_relation_responses'/(key+'.json'),raw)
        saved['receipt']={k:raw.get(k)for k in ('usage','elapsed_seconds','finish_reason','cache_hit')}
        assert raw['finish_reason']=='stop','Incomplete relation generation'
        value=json.loads(raw['content']);jsonschema.validate(value,original)
        saved['value']=value
    except Exception as error:
        saved['error']=type(error).__name__+': '+str(error)
    immutable_json(target,saved)
    if saved.get('error'):raise ValueError(saved['error'])
    return saved['value'],saved['receipt']


def run_case(client,p,name,library,sid,public,kernel,*,policy='residual'):
    target=OUT/'cases'/name/(policy+'_'+digest(sid)+'.json')
    if target.exists():return read(target)
    observation={};reads=[];failures=[]
    # Preserve already-computed independent education input; no model dispatch.
    from experiments.legal_skill_evolution_residual_reader_matched import NoNewPaidEvidence
    offline=NoNewPaidEvidence()
    offline.artifacts=OUT/'offline_background'
    for c in library['components']:
        if c['id']not in COMPONENTS and c.get('observation_program'):
            value,receipt=previous.train.actor.read_component(offline,p,sid,c,kernel,public,purpose='skill_actor')
            observation.update(value)
    attempted=set()
    static_inputs=set(dependency_graph(kernel)['input_predicates'])
    direct_families={r['family']for r in query_event_inputs(kernel)}
    while True:
        execution=evaluate(library,kernel,public,observation,sid)
        if execution['handled']:break
        if any(w['source_review']['failures']for w in execution['binding_executions']):break
        if any(v.get('error')for rows in execution['component_conversions'].values()for v in rows):break
        choices=[]
        scopes=[s for w in execution['binding_executions']for s in w['execution'].get('unread_factual_scopes',[])]
        requested={s['predicate']for s in scopes if kernel['fact_arities'].get(s['predicate'])==1}
        legacy=[c for c in library['components']if 'relation_contract'not in c and c['id']not in observation
                and ('legacy',c['id'])not in attempted and set(c['complete_native_families'])&requested]
        needed_new=False
        for c in library['components']:
            if 'relation_contract'not in c:continue
            for s in scopes:
                arity=kernel['fact_arities'].get(s['predicate'])
                if not arity:continue
                demands=pullback(c['relation_contract'],{'predicate':s['predicate'],
                    'arguments':[s['event']]+[{'var':'Provider'+str(i)}for i in range(arity-1)]})
                if any((c['id'],d['relation'])not in attempted for b in demands['branches']for d in b['joined_demands']):
                    needed_new=True
        if legacy and not needed_new:
            c=min(legacy,key=lambda c:(len(c['schema_json']),c['id']))
            attempted.add(('legacy',c['id']))
            try:
                value,receipt=previous.train.actor.read_component(client,p,sid,c,kernel,public,purpose='skill_actor')
                observation.update(value);reads.append({'component':c['id'],'shared_unchanged_legacy_input':True,**receipt})
            except Exception as error:failures.append({'component':c['id'],'error':type(error).__name__+': '+str(error)})
            continue
        for c in library['components']:
            if 'relation_contract'not in c:continue
            contract=c['relation_contract'];view=observation.get(c['id'],{'views':[{}]})['views'][0]
            wanted=set()
            if policy=='residual':
                for s in scopes:
                    arity=kernel['fact_arities'].get(s['predicate'])
                    if not arity:continue
                    demand=pullback(contract,{'predicate':s['predicate'],
                        'arguments':[s['event']]+[{'var':'Unbound'+str(i)}for i in range(arity-1)]})
                    wanted.update(d['relation']for b in demand['branches']for d in b['joined_demands'])
            else:
                wanted={a['predicate']for r in contract['rules']if r['head']['predicate']in static_inputs for a in r['body']}
            for rank,group in enumerate(contract['relations']):
                key=(c['id'],group['name'])
                if key in attempted:continue
                # All sides can identify an unread group and enumerate keys first.
                closed=set().union(*(set(w['complete_families'])|set((w.get('scope_contract')or {}).get('family_scans',[]))
                                     for w in execution['binding_executions']))
                priority=(0 if wanted else 1,
                          0 if set(contract['covered_families'])&(direct_families-closed) else 1,
                          0 if group['name']==contract['enumerator'] and contract['enumerator']not in view else 1,
                          0 if group['name']in wanted else 1,rank,c['id'],group['name'])
                choices.append((priority,c,group))
        if not choices:break
        _,component,group=min(choices,key=lambda v:v[0]);key=(component['id'],group['name']);attempted.add(key)
        view=observation.setdefault(component['id'],{'views':[{}]})['views'][0]
        try:
            value,receipt=group_read(client,p,sid,component,group['name'],public,view)
            view.update(value);reads.append({'component':component['id'],'relation':group['name'],**receipt})
        except Exception as error:failures.append({'component':component['id'],'relation':group['name'],'error':type(error).__name__+': '+str(error)})
    grading=read(OUT/'TRAIN_grading.json')
    source=previous.data()[0][sid]
    native_score=grade_view(source['dataset'],source['views'][0],grading[sid][source['views'][0]['id']],execution['answer'])
    result={'source':sid,'candidate':name,'policy':policy,'observation':observation,'execution':execution,
        'reads':reads,'failures':failures,'native_score':native_score,
        'source_failures':sum(w['source_review']['failures']for w in execution['binding_executions']),
        'core_correct':execution['handled']and native_score['correct']and
            not any(w['source_review']['failures']for w in execution['binding_executions'])}
    immutable_json(target,result)
    print(json.dumps({'candidate':name,'source':sid.split(':')[1][:8],'policy':policy,
        'handled':execution['handled'],'core_correct':result['core_correct'],'reads':len(reads)}),flush=True)
    return result


def fixed_generic(client,p,sid,source,kernel):
    target=OUT/'fixed_generic'/(digest(sid)+'.json')
    if target.exists():return read(target)
    public=source['views'][0]['public'];original=generic_schema(kernel,public)
    messages=render_messages(GENERIC_PROMPT+'\nShared native event meanings: '+p['shared_native_event_encoding'],
        {'current_case':{k:public[k]for k in ('facts','question')},
         'current_legal_query':{k:kernel[k]for k in ('native_query','query_clause')}},original)
    row={'source':sid,'condition':'unchanged_fixed_generic_native_event_view','fallback':False}
    try:
        wire,_=decoding_schema(original);size=client.tokenize(messages,thinking=False)['count']
        assert size+p['executor_profile']['max_tokens']<=p['executor_profile']['context_tokens']
        value=client.generate(RUN+':fixed_generic:'+digest(sid),source=sid,purpose='skill_actor',
            messages=messages,thinking=False,schema=wire)
        immutable_json(OUT/'fixed_generic_raw'/(digest(sid)+'.json'),value)
        assert value['finish_reason']=='stop','Incomplete fixed generic observation'
        observation=json.loads(value['content']);grounded=generic_lower(observation,kernel,public)
        execution=execute_alternatives(kernel,grounded)
        checked=review(sid,grounded,complete_families=[p for p,a in kernel['fact_arities'].items()if a==1])
        grading=read(OUT/'TRAIN_grading.json')
        score=grade_view(source['dataset'],source['views'][0],grading[sid][source['views'][0]['id']],execution['answer'])
        row.update(observation=observation,grounded=grounded,execution=execution,source_review=checked,native_score=score,
            core_correct=execution['handled']and score['correct']and not checked['failures'],
            receipt={k:value.get(k)for k in ('usage','elapsed_seconds','finish_reason','cache_hit','reused_physical_call_id')})
    except Exception as error:row.update(error=type(error).__name__+': '+str(error),core_correct=False)
    immutable_json(target,row);return row


def compiled_controls(p,libraries,public,kernels):
    result=[]
    for name,library in libraries.items():
        arm,index=name.split('/')
        programs=json.loads(read(OUT/arm/'teacher.json')['value']['observation_programs_json']).get(index,{})
        if not programs:continue
        for sid in p['acquisition_sources']+p['fixed_reuse_sources']:
            observation={};row={'candidate':name,'source':sid,'source_program_control_not_weak_reader_success':True}
            try:
                for cid,program in programs.items():
                    assert cid in COMPONENTS
                    validate_adapter(program,excluded_source_ids=p['sources'])
                    for n in ast.walk(ast.parse(program)):
                        if isinstance(n,ast.Constant):assert n.value not in ('Alice','Bob','Johns Hopkins University'),'Current entity constant'
                    view=execute_json(program,{'facts':public[sid]['views'][0]['public']['facts']},{},allow_helpers=True)
                    observation[cid]={'views':[view]}
                # Use independent, already-paid education observations when needed.
                for c in library['components']:
                    if c['id']not in COMPONENTS and c.get('observation_program'):
                        offline=prior_reads.NoNewPaidEvidence();offline.artifacts=OUT/'offline_background'
                        value,_=previous.train.actor.read_component(offline,p,sid,c,kernels[sid],public[sid]['views'][0]['public'],purpose='skill_actor')
                        observation.update(value)
                execution=evaluate(library,kernels[sid],public[sid]['views'][0]['public'],observation,sid)
                grading=read(OUT/'TRAIN_grading.json')
                score=grade_view(public[sid]['dataset'],public[sid]['views'][0],grading[sid][public[sid]['views'][0]['id']],execution['answer'])
                row.update(observation=observation,execution=execution,native_score=score,
                    source_failures=sum(w['source_review']['failures']for w in execution['binding_executions']),
                    core_correct=execution['handled']and score['correct']and not any(
                        w['source_review']['failures']for w in execution['binding_executions']))
            except Exception as error:row.update(error=type(error).__name__+': '+str(error),core_correct=False)
            result.append(row)
    immutable_json(OUT/'compiled_controls.json',{'rows':result,'new_executor_requests':0,
        'missing_unchanged_background_evidence_is_not_a_program_error':True})
    return result


def execute():
    p=protocol();public,kernels=previous.data();libraries=candidate_libraries()
    client=FrozenExecutor(ledger_for(p),OUT,p['executor_profile'])
    client.exact_replay_roots=[OUT]+list((ROOT/'artifacts').glob('legal_skill_evolution_generic_view_train*'))
    selected={};acquisition=[]
    for name,library in libraries.items():
        immutable_json(OUT/'candidate_libraries'/(name+'.json'),library)
        rows=[run_case(client,p,name,library,s,public[s]['views'][0]['public'],kernels[s])for s in p['acquisition_sources']]
        acquisition.append({'candidate':name,'rows':rows})
    for arm in ('Method','FreeTeacher'):
        candidates=[v for v in acquisition if v['candidate'].startswith(arm+'/')]
        best=min(candidates,key=lambda v:(-sum(r['core_correct']for r in v['rows']),
            sum(r['source_failures']for r in v['rows']),sum(x.get('elapsed_seconds')or 0 for r in v['rows']for x in r['reads']),v['candidate']))
        selected[arm]=best['candidate']
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only':True})
    reuse=[]
    for arm,name in selected.items():
        for sid in p['fixed_reuse_sources']:
            reuse.append(run_case(client,p,name,libraries[name],sid,public[sid]['views'][0]['public'],kernels[sid]))
    paired=[]
    chosen=selected['Method']
    for sid in p['fixed_reuse_sources']:
        paired.append(run_case(client,p,chosen,libraries[chosen],sid,public[sid]['views'][0]['public'],kernels[sid],policy='ordinary'))
    generic=[fixed_generic(client,p,s,public[s],kernels[s])for s in p['acquisition_sources']+p['fixed_reuse_sources']]
    programs=compiled_controls(p,libraries,public,kernels)
    immutable_json(OUT/'result.json',{'acquisition':acquisition,'selected':selected,'fixed_reuse':reuse,
        'same_contract_ordinary_reuse':paired,'fixed_generic':generic,'compiled_controls':programs,
        'DEV_TEST_loaded':False,'goal_complete':False,
        'coupled_and_split_comparison_not_innovation_by_itself':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','acquire','execute'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'execute':execute}[args.phase]()
