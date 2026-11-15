"""Execute acquired source concepts as programs, then learn G over fragments.

One focused C repair after categorical reader gaps were measured. No Norm can
enter through phi. Whole-source absence still needs an actual retained neural
audit. Public type facts are common infrastructure, not a learned legal rule.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_C_fragment_update as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations,validate_queries
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,signatures,fact
from legal_skill_guard.skill_evolution.unit_evidence import ground_selected_units
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.source_composition import validate_renderers,validate_template_constructors
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,constructors,term_sort
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,execute_json,validate_procedure,CALLS,METHODS
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,INSTRUCTION,PROGRAM_INSTRUCTION

ROOT=previous.ROOT
RUN='legal_skill_evolution_C_program_concepts_20261115'
OUT=ROOT/'artifacts'/RUN
SCHEMA=record_schema({
    'rationale':{'type':'string'},'operations':{'type':'array','items':OPERATION},
    'operation_scopes_json':{'type':'string'},'absence_choices_json':{'type':'string'},
    'planner_program':{'type':'string'},'source_concept_program':{'type':'string'},
    'signature_additions_json':{'type':'string'},'constant_additions_json':{'type':'string'},
    'rule_edits_json':{'type':'string'},'removed_rule_ids':{'type':'array','items':{'type':'string'}},
    'renderer_edits_json':{'type':'string'},'suggested_rule_ids':{'type':'array','items':{'type':'string'}},
    'free_composition_program':{'type':'string'}})
SYSTEM='''Repair the CURRENT C method, not a new topic. No tools. Both arms have
the same original TRAIN text, lawful supervision, partial source reviews,
runtime/code capacity and fixed native consumer. No source/company-ID dispatch,
hardcoded party names or native-answer postprocessing. Preserve actual scope,
conditions, parties, exceptions, OR connectors and complete material scope.

The measured categorical C path got 14/16 acquisition, 4/8 frozen reuse;
ordinary teacher 13/16, 7/8. G fitting corrected one acquisition answer but no
reuse answer. A fixed set of whole recipient combinations cannot represent
agents plus professional advisers. The C planner missed plural third parties;
weak readings sometimes attributed a preceding permission to a current ban.
These six parents are now development, never claimed blind. Two further original
TRAIN parents were fixed by original insertion order before this task and are
omitted. No DEV/TEST. All failures, historical exposure and costs are retained.

Acquire source concepts as compact reusable PURE programs, instead of asking a
weak reader to repeatedly reconstruct whole legal combinations. Programs are
learned content, not host-provided legal rules. Norms must still be composed
by G. Deterministic source parsing, typed fragments and public type information
are infrastructure, not automatically a contribution. Do not hide a complete
norm or answer in a fragment. A source concept is an executable extractor or
classifier of an actual legal distinction, with current evidence.

operations retain explicit {name,question,choices:[{name,meaning}],examples}.
Use compositional sets in typed fragments, not a new enum for every recipient
combination. For example a resolved source recipient set may be represented
by a generic definite concept plus an actual Participant expression containing
the individually resolved recipient kinds. This is not an unknown filled with
the intended target. Distinguish source permission, prohibition and definition.
Examples must be exact acquisition-source quotations, no fabricated source.

planner_program apply(inputs,premises) returns {queries:[{id,operation,unit_ids}]}.
These queries are ACTUALLY read by frozen Qwen3-8B thinking OFF; inputs are
source_text,source_spans,empty source_output,actual semantic_answers. Prefer the
existing unchanged whole-source audit definitions so paid identical audits can
be reused; no changed meaning is cached. Do not repeatedly ask answered unknowns.
operation_scopes_json declares every operation as focus_last or window.
absence_choices_json declares operation->[complete absence choices]. Absence
requires actual complete-source neural audit; zero parser matches is not proof.

source_concept_program apply(inputs,premises) gets the same RAW source_text,
source_spans,empty source_output and ACTUAL neural semantic_answers. Return
{queries:[{id,operation,unit_ids}],answers:[{id,choice,evidence_unit_ids}],
fragments:[{term,support_ids,query_ids}],unresolved:[string]}.
The returned questions/answers are PROGRAM-COMPUTED concepts, not new neural
responses and never described as neural readings. Every source program answer
must quote current evidence unit IDs and use a declared actual operation/choice.
Program IDs cannot overwrite a neural reading. Unsupported meanings stay
unknown/unresolved, never fabricated. The program may parse raw current source
with reusable learned lexical/structural productions, resolve clause references
and construct precise recipient sets and conditions. Preserve exact source
qualifiers as bound text. Do not infer legal absence from failed parsing.
Program-computed complete-source absence choices are forbidden.

Each fragment needs definite actual program/neural query_ids and support_ids
contained in their evidence. Only Participant,Information,Action,Trigger,
Condition,Exception,ExceptionSet nodes are permitted anywhere. Norm,Definition
and Description are forbidden everywhere, including nested nodes. Thus only G
can build norms. Keep roles and cross-clause scope explicit; an NDA-signing
requirement alone is not disclosure permission and a foreign-hosting ban is not
third-party permission. Conditional consent exceptions cannot disappear.

The host encodes real fragments using existing legacy_root,term_constructor,
term_child,root_support and actual query_choice. It additionally supplies public
term_type(term,sort) for typed fragment nodes from the COMMON constructor table.
term_type conveys existing type declarations only, no semantic truth. This lets
G use any current Condition/Participant expression without enumerating every
combination. Same common interface is available to the control.

C starts from its complete current candidate language/renderers, preserves
useful pieces, and returns edits: signature_additions_json maps predicate to
{arguments:[sorts],kind:derived|output}; term_type observed is already supplied.
constant_additions_json maps sort to additional scalars; host supplies the public
constructor and type names. rule_edits_json is an array of COMPLETE added or
replacement {id,cost,head,body} rules, removed_rule_ids removes old IDs.
Atom={predicate,arguments:[scalar|{var:Uppercase}],sign:positive|negative}.
renderer_edits_json adds/replaces complete renderer records by predicate with
{predicate,term,support_arguments,support_from_terms,support_from_queries}.
Term templates use actual {term_argument:i}/{scalar_argument:i}; all output
positions are used. No raw-text Norm parser through the consumer. All G outputs
need actual concept support; current dynamic source constants are not static
training constants. suggested_rule_ids is a NoFit control, not a claimed optimum.
The host fits source-valid candidates on lawful native TRAIN feedback, freezes,
then evaluates the two omitted parents. free_composition_program is empty for C.

FreeTeacher independently returns its strongest ordinary reusable source-to-norm
program, or uses the SAME concept/fragment/G interface from an empty rule base.
It may parse raw source deterministically, refine the audits, use executable
concepts or retain useful prior program functions. It is not forced to keep a
failing neural classifier or an inferior architecture. A free composition program
apply(inputs,premises) receives raw source_text,source_spans,actual source_output
fragments if any, and actual neural/program semantic_answers. It returns
{statements:[{term,support_ids}],complete:boolean,unresolved:[string]}.
Use no fake default norm/label. source_concept_program may be '' if unused.
If free_composition_program is nonempty return no rule/renderer edits or selected
IDs. Complete-source absence markers still require real declared neural audits.

Pure top-level Python only, prebound re, supported builtins supplied. No imports,
IO, nested functions, reflection, recursion. Do not regenerate an unchanged
whole candidate language: edits only. Keep programs compact and valid. Return
the strict JSON, complete program strings, no tools.
'''


def read(path):return json.loads(path.read_text())


def prepare():
    prior=read(previous.OUT/'protocol.json');public,grading=previous.base.history.bank()
    acquisition=prior['acquisition_sources']+prior['fixed_reuse_sources']
    reuse=[sid for sid in public if sid not in acquisition][:2]
    immutable_json(OUT/'source_selection.json',{'acquisition_sources':acquisition,'fixed_reuse_sources':reuse,
        'selection':'first two remaining original TRAIN bank entries; no contents or labels used',
        'prior_B8_exposure_disclosed':True})
    bank={};sources=[]
    for sid in acquisition+reuse:
        source=public[sid];text=source['views'][0]['public']['source_text']
        units,_=execution_source_units(text,source_spans(material_public(source['views'][0]['public'])))
        bank[sid]={'source':source,'units':units,'empty_upstream':{'statements':[],'complete':False,'unresolved':[]}}
        if sid in acquisition:sources.append({'source':sid,'source_text':text,'units':units,
            'native_TRAIN_supervision':grading[sid],'native_hypotheses':[{'id':v['id'],'question':v['public']['question']}for v in source['views']]})
    spec=read(previous.OUT/'common_spec.json');seed=read(previous.OUT/'C/selected_before_reuse.json')['library']
    immutable_json(OUT/'seed_C.json',seed);immutable_json(OUT/'common_spec.json',spec)
    task={'common_output_spec':spec,'observed_signatures':{**signatures(),'term_type':{'arguments':['term','sort'],'kind':'observed'}},
        'acquisition_sources':sources,'shared_source_feedback':[
            {'source':next(s for s in acquisition if ':e671' in s),'unit':10,'issue':'Explicit access permission is limited to agents and professional advisers; represent their exact set and purpose condition. Following unit11 imposes agreement compliance, not a new permission.'},
            {'source':next(s for s in acquisition if ':354623' in s),'units':[24,27,48],'issue':'Actual nondisclosure clauses include plural third parties and any other person; retain written-consent and service-purpose exceptions. Definition unit6 is not permission.'},
            {'source':next(s for s in acquisition if ':e7b78' in s),'units':[42,62,63],'issue':'Unit42 requires NDA signatures, not independently disclosure permission. Unit62 has actual conditional permission. Unit63 bans information outside the country; not third-party permission.'}],
        'shared_prior_reviews':read(previous.base.history.OUT/'teacher_task.json')['shared_partial_reviews'],
        'supported_pure_builtins':sorted(CALLS),'supported_pure_methods':sorted(METHODS)}
    assert not any(s in json.dumps(task)for s in reuse)
    for name in ('relational_rules.py','source_composition.py','source_observations.py'):
        task[name]=(ROOT/'legal_skill_guard/skill_evolution'/name).read_text()
    for arm in ('C','FreeTeacher'):
        own={'previous_own_proposal':read(previous.OUT/arm/'teacher.json')['value'],
            'actual_own_results':read(previous.OUT/arm/'result.json'),
            'actual_own_readings':[{'source':sid,'visible_inputs':read(previous.OUT/arm/'observations'/(digest(sid)+'.json'))['visible_inputs']}for sid in acquisition]}
        if arm=='C':own['current_candidate_library']=seed
        immutable_json(OUT/arm/'teacher_task.json',{**task,**own})
    immutable_json(OUT/'raw_source_bank.json',bank);immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in bank})
    p={k:deepcopy(prior[k])for k in ('sources','executor_profile','teacher_profile')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,same_goal=True,
        goal_complete=False,full_training_DEV_TEST=False,fitting_wall_time_seconds=120,
        ledger_before=previous.base.lineage.ledger_snapshot(),program_concepts_not_neural_responses=True)
    files=[Path(__file__),Path(previous.__file__),Path(previous.base.history.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=[OUT/n for n in ('seed_C.json','common_spec.json','raw_source_bank.json','TRAIN_grading.json','source_selection.json','C/teacher_task.json','FreeTeacher/teacher_task.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files};immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'acquisition':len(acquisition),'reuse':reuse,
        'task_chars':{a:len(json.dumps(pack_programs(read(OUT/a/'teacher_task.json'))))for a in ('C','FreeTeacher')}}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def ledger(p):return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
    sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol();client=FrozenTeacher(ledger(p),OUT,p['teacher_profile'])
    def one(arm):
        if(OUT/arm/'teacher.json').exists():return
        result=client.propose(RUN+':'+arm+':program_concepts',source_ids=p['acquisition_sources'],
            system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(read(OUT/arm/'teacher_task.json')),ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(OUT/arm/'teacher.json',result);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('C','FreeTeacher')]
        for job in jobs:job.result()


def compile_proposals():
    p=protocol();bank=read(OUT/'raw_source_bank.json');spec=read(OUT/'common_spec.json');libraries={}
    for arm in ('C','FreeTeacher'):
        v=read(OUT/arm/'teacher.json')['value'];ops=v['operations'];validate_operations(ops,{s:bank[s]['source']['views'][0]['public']['source_text']for s in p['acquisition_sources']})
        scopes=json.loads(v['operation_scopes_json']);assert set(scopes)=={o['name']for o in ops}and all(s in ('window','focus_last')for s in scopes.values())
        validate_procedure(v['planner_program'],allow_helpers=True)
        lib={'operations':ops,'operation_scopes':scopes,'scope':'window','planner_program':v['planner_program'],
            'spec':spec,'complete_source_absence_choices':json.loads(v['absence_choices_json'])}
        if v['source_concept_program']:
            validate_procedure(v['source_concept_program'],allow_helpers=True);lib['source_concept_program']=v['source_concept_program']
        if v['free_composition_program']:
            assert arm=='FreeTeacher';validate_procedure(v['free_composition_program'],allow_helpers=True)
            assert not json.loads(v['rule_edits_json'])and not json.loads(v['renderer_edits_json'])and not v['suggested_rule_ids']
            lib['composition_program']=v['free_composition_program']
        else:
            seed=read(OUT/'seed_C.json')if arm=='C'else{'language':{'signatures':signatures(),'constants':{},'rules':[]},'renderers':[]}
            language=deepcopy(seed['language']);language['signatures']['term_type']={'arguments':['term','sort'],'kind':'observed'}
            additions=json.loads(v['signature_additions_json']);assert all(s['kind']in ('derived','output')for s in additions.values())
            language['signatures'].update(additions)
            for sort,values in json.loads(v['constant_additions_json']).items():language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            for sort,values in [('operation',[o['name']for o in ops]),('choice',[c['name']for o in ops for c in o['choices']]),('constructor',list(constructors(spec))),('sort',sorted({c['sort']for c in spec['constructors']}))]:
                language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            rules={r['id']:r for r in language['rules']}
            for identity in v['removed_rule_ids']:del rules[identity]
            rules.update({r['id']:r for r in json.loads(v['rule_edits_json'])});language['rules']=list(rules.values())
            renderers={r['predicate']:r for r in seed['renderers']};renderers.update({r['predicate']:r for r in json.loads(v['renderer_edits_json'])})
            validate_language(language);validate_renderers(language,list(renderers.values()));validate_template_constructors(list(renderers.values()),spec)
            assert set(v['suggested_rule_ids'])<=set(rules)
            lib.update(language=language,renderers=list(renderers.values()),selected_rule_ids=v['suggested_rule_ids'])
        libraries[arm]=lib
    return libraries


def program_concepts(library,raw):
    if'source_concept_program'not in library:return typed(raw,library['spec'])
    v=raw['visible_inputs'];value=execute_json(library['source_concept_program'],{
        'source_text':v['source_text'],'source_spans':v['units'],'source_output':v['source_output'],'semantic_answers':v['answers']},{},allow_helpers=True)
    assert set(value)=={'queries','answers','fragments','unresolved'}
    queries=validate_queries(value['queries'],library['operations'],v['units']);answers={a['id']:a for a in value['answers']}
    assert len(answers)==len(value['answers'])and set(answers)=={q['id']for q in queries}
    assert not set(answers)&{q['id']for q in v['queries']},'Program must not overwrite an actual neural query'
    grounded=[]
    for query in queries:
        answer=answers[query['id']];assert set(answer)=={'id','choice','evidence_unit_ids'}
        assert answer['choice']not in library['complete_source_absence_choices'].get(query['operation'],[]),'Program cannot invent a complete-source absence audit'
        grounded+=ground_selected_units(library['operations'],[query],v['units'],{'answers':{query['id']:{k:answer[k]for k in ('choice','evidence_unit_ids')}}},scope=library['operation_scopes'][query['operation']],complete_source_absence_choices=library['complete_source_absence_choices'])
    all_answers=v['answers']+grounded;by_id={a['id']:a for a in all_answers};schema=constructors(library['spec']);rows=[]
    def check_part(term):
        if isinstance(term,list):
            assert schema[term[0]]['sort']in {'Participant','Information','Action','Trigger','Condition','Exception','ExceptionSet'}
            for child in term[1:]:check_part(child)
    for fragment in value['fragments']:
        assert set(fragment)=={'term','support_ids','query_ids'}and fragment['support_ids']and fragment['query_ids']
        term_sort(fragment['term'],schema);check_part(fragment['term'])
        assert all(q in by_id and by_id[q]['choice']!='unknown'for q in fragment['query_ids'])
        assert set(fragment['support_ids'])<={w['unit_id']for q in fragment['query_ids']for w in by_id[q]['evidence']}
        rows.append({'term':fragment['term'],'support_ids':fragment['support_ids']})
    all_queries=v['queries']+queries
    encoded=encode_source_observations(raw['context']['id'],source_text=v['source_text'],units=v['units'],
        source_output={'statements':rows,'complete':False,'unresolved':value['unresolved']},operations=library['operations'],queries=all_queries,answers=all_answers,scope=v['scope'],
        query_scopes={q['id']:library['operation_scopes'][q['operation']]for q in all_queries},
        complete_source_absence_choices=library['complete_source_absence_choices'],query_aliases=v.get('query_aliases'))
    encoded['source_concept_execution']={'program_sha256':digest(library['source_concept_program']),'program_output':value,
        'neural_query_ids':[q['id']for q in v['queries']],'program_query_ids':[q['id']for q in queries],
        'program_answers_are_not_neural_readings':True,'whole_norms_forbidden':True,'new_model_requests':0}
    return typed(encoded,library['spec'])


def typed(observation,spec):
    value=deepcopy(observation);schema=constructors(spec)
    for identity,node in value['term_nodes'].items():
        if isinstance(node,list):value['context']['facts'].append(fact('term_type',identity,schema[node[0]]['sort']))
    value['public_type_annotation']={'source':'unchanged common constructor types','new_legal_semantics':False}
    return value


def assess(library,observation,sid):
    source=read(OUT/'raw_source_bank.json')[sid]['source'];grading=read(OUT/'TRAIN_grading.json')[sid]
    core=previous.base.history.previous.update.train.previous.old.previous.prior.prior
    output=core.evaluate_source(library,observation,source,None)['execution']['source_output']
    from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
    prior=read(previous.base.history.OUT/'teacher_task.json')['shared_partial_reviews']
    feedback=with_disposal_review(core.checker(library,source,grading),sid,prior.get('shared_reviewed_source_scope_checks')or[],
        library['spec']['decision_program'],authorization_review=prior.get('shared_branch_authorization_review'))(output)
    frame=previous.base.history.frame_review(sid,output)
    return {'source':sid,'feedback':feedback,'frame_review':frame,'source_output':output,
        'hard_source_pass':feedback.get('source_review_passed',True)and not frame['failures'],
        'native_correct':sum(bool(v['score']and v['score']['correct'])for v in feedback['views']),
        'native_total':len(feedback['views']),'unresolved':sum(not v['core_executed']for v in feedback['views'])}


def execute():
    p=protocol();libraries=compile_proposals();bank=read(OUT/'raw_source_bank.json');client=FrozenExecutor(ledger(p),OUT,p['executor_profile']);results=[]
    for arm,library in libraries.items():
        folder=OUT/arm
        def observation(sid):
            target=folder/'observations'/(digest(sid)+'.json')
            if target.exists():return read(target)
            prior=previous.OUT/arm/'observations'/target.name;histories=[read(prior)]if prior.exists()else[];item=bank[sid]
            raw=observe(client,RUN+':'+arm+':'+digest(sid),sid,library,source_text=item['source']['views'][0]['public']['source_text'],units=item['units'],source_output=item['empty_upstream'],previous_observations=histories,
                save_event=lambda event:immutable_json(folder/'read_events'/(digest(event['call_id'])+'.json'),event))
            immutable_json(folder/'raw_observations'/target.name,raw);value=program_concepts(library,raw);immutable_json(target,value);return value
        observations={s:observation(s)for s in p['acquisition_sources']};nofit=[assess(library,observations[s],s)for s in p['acquisition_sources']]
        if'language'in library:
            names=[r['id']for r in library['language']['rules']];suggested=library['selected_rule_ids'];costs={r['id']:r['cost']for r in library['language']['rules']}
            candidates=[suggested,[],names]+[sorted(set(suggested)^{name})for name in names]
            best=None;trials=[];seen=set();start=time.monotonic()
            for ids in candidates:
                key=tuple(sorted(ids))
                if key in seen:continue
                if trials and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
                seen.add(key);candidate=deepcopy(library);candidate['selected_rule_ids']=list(key)
                rows=[assess(candidate,observations[s],s)for s in p['acquisition_sources']];valid=all(r['hard_source_pass']for r in rows)
                rank=(-sum(r['native_correct']for r in rows),sum(costs[i]for i in key),len(key),key)
                trials.append({'rule_ids':list(key),'rows':rows,'hard_source_pass':valid})
                if valid and(best is None or rank<best[0]):best=(rank,candidate)
            immutable_json(folder/'fit_receipt.json',{'trials':trials,'optimization_complete':False,'new_model_requests':0})
            if best is None:
                immutable_json(folder/'unresolved.json',{'reason':'No source-valid executable acquired G','paid_reads_preserved':True});continue
            library=best[1]
        immutable_json(folder/'selected_before_reuse.json',{'library':library,'acquisition_only':True})
        acquisition=[assess(library,observations[s],s)for s in p['acquisition_sources']];reuse=[assess(library,observation(s),s)for s in p['fixed_reuse_sources']]
        result={'arm':arm,'acquisition':acquisition,'fixed_reuse':reuse,'NoFit_acquisition':nofit,'goal_complete':False};immutable_json(folder/'result.json',result);results.append(result)
        print(json.dumps({'arm':arm,'acquisition':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in acquisition],
            'reuse':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in reuse]}),flush=True)
    immutable_json(OUT/'result.json',{'arms':results,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','acquire','validate','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'validate':compile_proposals,'execute':execute}[args.phase]()
