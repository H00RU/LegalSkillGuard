"""C's actual concept-to-rule acquisition, without pre-supplied source norms.

Same Goal, original TRAIN and continuous ledger. Preserve all older learned
compilers as explicit controls; this finite stage tests the previously bypassed
core path. It starts no full mixed training, DEV or TEST run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
from itertools import combinations
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_source_frame_update as history
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.source_composition import validate_renderers,validate_template_constructors
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,validate_procedure
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,INSTRUCTION,PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT=history.ROOT
GENERATION=ROOT/'artifacts/legal_skill_evolution_C_direct_acquisition_20261115'
RUN='legal_skill_evolution_C_direct_acquisition_runtime_20261115'
OUT=ROOT/'artifacts'/RUN
SCHEMA=record_schema({'rationale':{'type':'string'},'operations':{'type':'array','items':OPERATION},
    'planner_program':{'type':'string'},'operation_scopes_json':{'type':'string'},
    'language_json':{'type':'string'},'renderers_json':{'type':'string'},
    'recommended_rule_ids':{'type':'array','items':{'type':'string'}},
    'free_composition_program':{'type':'string'},'complete_source_absence_choices_json':{'type':'string'}})
SYSTEM='''Implement the existing C source-concept/rule-acquisition method on the
same original TRAIN. No tools. The old experiment was bypassed: the source
program already supplied normalized norms, and the fitted G used none of the
new concepts. This stage therefore supplies RAW current source units and NO
normalized current source_output, source parser, saved concept answers or case
rules. All older results/expenses remain; this is not a reset or a blind claim.
Both arms independently acquire from exactly the same original text, native
TRAIN supervision, partial source feedback, output vocabulary and fixed consumer.

Return reusable semantic operations, their executable query planner and either
relational composition (C) or your strongest ordinary acquisition program (Free).
The source reader is frozen Qwen3-8B thinking OFF. It executes actual learned
questions and returns source-grounded choice/evidence, never an intended answer.
No parameter updates, per-source ID/name dispatch, answer choices or native-label
postprocessing. Source meaning, qualifiers, parties and clause scope are real
constraints; native correctness alone does not certify them. Do not silently
discard an OR branch, change a request into termination, merge affiliate-owned
employees into the recipient's employees, or turn a definition into permission.

Operations use {name,question,choices:[{name,meaning}],examples:[{source,quote,choice}]}.
unknown is supplied by the host. Examples are contiguous exact quotations from
the acquisition sources only. Use a small set of reusable legal distinctions,
not a Cartesian product of whole output IRs or renamed benchmark answers. The
planner is pure apply(inputs,premises) -> {queries:[{id,operation,unit_ids}]}.
Its inputs are source_text, source_spans:[{id,text,...}], source_output (always
empty in this stage), and semantic_answers already actually read. It may locate
clauses then read meanings. Exact IDs are current input anchors, not training
constants. operation_scopes_json maps EVERY operation to focus_last or window.
focus_last classifies the last unit with earlier context; window classifies the
whole supplied window. Unchanged unknowns are not retried. Negative/absent
meanings require actual evidence; complete-source absence must be explicitly
declared in complete_source_absence_choices_json as {operation:[choice,...]} and
actually inspect all current source units. No empty/default source rules.

The supplied output grammar/consumer are common inherited assets, without any
example seeds or source-specific normalizer. Return statements with current
support_ids. No native consumer changes are allowed in this finite isolation.
Output types include normal legal obligations/permissions/prohibitions and
complete-source category-absence markers. All qualifiers must retain their
source meaning. Opaque source-clause parser/backend constructors are excluded so
that the frozen consumer does not secretly reacquire the law from raw text.

C: free_composition_program is empty. language_json is {signatures:<additional
derived/output signatures>,constants:<sort to scalar domain>,rules:[...]}. The
host adds all supplied observed signatures. A signature is {arguments:[sorts],
kind:derived|output}. A rule is {id,cost:positive integer,head:ATOM,body:[ATOM]}.
ATOM={predicate,arguments:[scalar|{var:UppercaseName}],sign:positive|negative}.
Use the supplied nominal sorts. Negative means explicit negative observations,
not missing facts. Every emitted Norm must depend on actual query_choice from
your learned source concepts and grounded source evidence. Raw unit text can
bind a qualifier, not independently act as a hidden normative parser. No legacy
roots exist. Alternatives should let lawful native/source feedback distinguish
G choices; the host learns the selected set. recommended_rule_ids supplies a
NoFit control on identical actual observations. Do not assume its choice wins.

renderers_json is [{predicate,term:<constructor template>,support_arguments:[unit
argument positions],support_from_terms:[term positions],support_from_queries:
[query positions]}]. Template children use {scalar_argument:i}, {term_argument:i}
or nested fixed constructors. Every output argument is used in term or evidence.
Current source units/quotes are dynamic values, never static training constants.
Use precise evidence-unit anchors for positive clauses; a broad source window
does not make its definition an operative assertion. No source/company names,
dates or labels may be hardcoded in programs/rules. Constants may be reusable
semantic vocabulary. Refer to the complete validators/renderer API supplied.

FreeTeacher: independently use the SAME reading operations, decomposition,
finite concept choices, raw source, partial feedback and code capacity, or a
pure source-only text-to-norm compiler if stronger. It may implement the same
source-frame strategy. free_composition_program is pure apply(inputs,premises),
inputs={source_text,source_spans,source_output:empty,semantic_answers:[actual]},
return {statements:[{term,support_ids}],complete:boolean,unresolved:[string]}.
Do not answer a benchmark directly. language_json={},renderers_json=[],
recommended_rule_ids=[] for that program path. An independently proposed
relational path is also allowed with the same fit/NoFit and execution interface.
No artificial weak-control restrictions, omitted fields or shared learned output
from the new C proposal. All actual acquisition, repair and execution cost counts.

All programs are pure top-level Python with prebound re; no imports/IO/nested
functions/classes/lambdas/recursion/reflection. Keep candidates compact and valid.
Return the strict requested JSON, with complete executable modules as strings.
'''


def read(path):return json.loads(path.read_text())


def prepare_runtime():
    """Bind runtime support without regenerating or altering paid proposals."""
    import sqlite3
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
    p=read(GENERATION/'protocol.json')
    for relative in ('teacher_task.json','raw_source_bank.json','TRAIN_grading.json','common_spec.json',
                     'C/teacher.json','FreeTeacher/teacher.json'):
        target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True)
        payload=(GENERATION/relative).read_bytes()
        if target.exists():assert target.read_bytes()==payload
        else:target.write_bytes(payload)
    p.update(run_id=RUN,generation_run=p['run_id'],ledger_before=lineage.ledger_snapshot(),
        runtime_change='Pure repr builtin supported equally; original teacher proposals byte-identical; no semantic adaptation')
    files=[Path(__file__),Path(history.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=[OUT/n for n in ('teacher_task.json','raw_source_bank.json','TRAIN_grading.json','common_spec.json','C/teacher.json','FreeTeacher/teacher.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'runtime_prepared':RUN,'new_teacher_calls':0}),flush=True)


def prepare():
    public,grading=history.bank();old=read(history.OUT/'protocol.json')
    acquisition=old['acquisition_sources'];reuse=old['fixed_reuse_sources']
    current=read(history.OUT/'ConstraintAcquire/selected_before_reuse.json')['library']['spec']
    early=read(ROOT/'artifacts/legal_skill_evolution_open_acquisition_native_loss_20261113/base.json')['grammar']
    allowed={c['name']for c in early['constructors']}|{'controlled_entities_of','relationship_termination',
        'relationship_nonformation_deadline','complete_source_no_disclosure_permission',
        'complete_source_no_disposal_obligation','complete_source_no_retention_effect',
        'source_action_conjunction','source_action_alternative','source_authorized_action_alternative'}
    spec={'constructors':[deepcopy(c)for c in current['constructors']if c['name']in allowed],
        'decision_program':current['decision_program'],'seeds':[],
        'rationale':'Shared existing typed consumer, with no example seeds, source parser or normalized input norms.'}
    task={'common_output_spec':spec,'observed_signatures':signatures(),
        'acquisition_sources':[],'source_feedback':[],
        'relative_diagnosis':'Earlier normalized source roots bypassed new phi/G. This stage removes the normalized INPUT route equally for both arms, retaining complete original text, supervision and public output semantics.',
        'full_original_TRAIN_history_exposure_disclosed_not_blind':True,
        'original_larger_compilers_retained_as_separate_history_controls':True}
    bank={}
    for sid in acquisition+reuse:
        source=public[sid];text=source['views'][0]['public']['source_text']
        units,_=execution_source_units(text,source_spans(material_public(source['views'][0]['public'])))
        # Reuse only structural source segmentation, never old source norms.
        bank[sid]={'source':source,'units':units,'empty_upstream':{'statements':[],'complete':False,'unresolved':[]}}
        if sid in acquisition:
            task['acquisition_sources'].append({'source':sid,'source_text':text,'units':units,
                'native_TRAIN_supervision':grading[sid],'native_hypotheses':[{'id':v['id'],'question':v['public']['question']}for v in source['views']]})
    task['source_feedback']=[{'source':acquisition[0],'review':{
        'unit13':'An operative permission for recipient-affiliate employees, not the recipient\'s own employees.',
        'unit14':'Affiliate definition; not independently a permission.',
        'unit20':'A separate operative permission for the recipient\'s own employees.'}}]
    for name in ('relational_rules.py','source_composition.py','source_observations.py'):
        task[name]=(ROOT/'legal_skill_guard/skill_evolution'/name).read_text()
    assert all(sid not in json.dumps(task)for sid in reuse)
    assert not strict_output_schema_issues(SCHEMA)
    immutable_json(OUT/'teacher_task.json',task);immutable_json(OUT/'raw_source_bank.json',bank)
    immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in bank})
    immutable_json(OUT/'common_spec.json',spec)
    p={k:deepcopy(old[k])for k in ('sources','executor_profile','teacher_profile')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        input_route='Complete raw source; no source compiler or normalized source rules in either arm',
        same_goal=True,goal_complete=False,full_training_DEV_TEST=False,
        same_inherited_output_consumer_and_no_hidden_acquisition_backend=True,
        fitting_wall_time_seconds=120,ledger_before=lineage.ledger_snapshot())
    files=[Path(__file__),Path(history.__file__),OUT/'teacher_task.json',OUT/'raw_source_bank.json',OUT/'TRAIN_grading.json',OUT/'common_spec.json']
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'raw_acquisition_sources':acquisition,'fixed_reuse':reuse,'output_constructors':len(spec['constructors']),
        'teacher_task_chars':len(json.dumps(pack_programs(task))),'normalized_source_statements_supplied':0}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def ledger(p):return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
    sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol();l=ledger(p);task=read(OUT/'teacher_task.json')
    def one(arm):
        target=OUT/arm/'teacher.json'
        if target.exists():return
        value=FrozenTeacher(l,OUT,p['teacher_profile']).propose(RUN+':'+arm+':raw_acquisition',
            source_ids=p['acquisition_sources'],system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(target,value);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('C','FreeTeacher')]
        for job in jobs:job.result()


def compile_proposals():
    p=protocol();bank=read(OUT/'raw_source_bank.json');spec=read(OUT/'common_spec.json');result={}
    for arm in ('C','FreeTeacher'):
        v=read(OUT/arm/'teacher.json')['value'];operations=v['operations']
        validate_operations(operations,{sid:bank[sid]['source']['views'][0]['public']['source_text']for sid in p['acquisition_sources']})
        scopes=json.loads(v['operation_scopes_json']);assert set(scopes)=={o['name']for o in operations}
        assert all(x in ('focus_last','window')for x in scopes.values())
        validate_procedure(v['planner_program'],allow_helpers=True)
        library={'operations':operations,'operation_scopes':scopes,'scope':'window','planner_program':v['planner_program'],
            'spec':spec,'complete_source_absence_choices':json.loads(v['complete_source_absence_choices_json'])}
        if v['free_composition_program']:
            assert arm=='FreeTeacher'and json.loads(v['language_json'])=={}and not json.loads(v['renderers_json'])
            validate_procedure(v['free_composition_program'],allow_helpers=True)
            library['composition_program']=v['free_composition_program']
        else:
            language=json.loads(v['language_json']);assert not set(language['signatures'])&set(signatures())
            language['signatures']={**signatures(),**language['signatures']}
            language['constants'].setdefault('operation',[])
            language['constants']['operation']=list(dict.fromkeys(language['constants']['operation']+[o['name']for o in operations]))
            language['constants'].setdefault('choice',[])
            language['constants']['choice']=list(dict.fromkeys(language['constants']['choice']+[c['name']for o in operations for c in o['choices']]))
            renderers=json.loads(v['renderers_json']);validate_language(language);validate_renderers(language,renderers);validate_template_constructors(renderers,spec)
            assert set(v['recommended_rule_ids'])<={r['id']for r in language['rules']}
            library.update(language=language,renderers=renderers,selected_rule_ids=v['recommended_rule_ids'])
        result[arm]=library
    return result


def assess(library,observation,sid):
    source=read(OUT/'raw_source_bank.json')[sid]['source'];grading=read(OUT/'TRAIN_grading.json')[sid]
    core=history.previous.update.train.previous.old.previous.prior.prior
    actual=core.evaluate_source(library,observation,source,None)
    from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
    prior=read(history.OUT/'teacher_task.json')['shared_partial_reviews']
    check=with_disposal_review(core.checker(library,source,grading),sid,prior.get('shared_reviewed_source_scope_checks')or[],
        library['spec']['decision_program'],authorization_review=prior.get('shared_branch_authorization_review'))
    feedback=check(actual['execution']['source_output']);frame=history.frame_review(sid,actual['execution']['source_output'])
    return {'source':sid,'feedback':feedback,'frame_review':frame,
        'source_output':actual['execution']['source_output'],'hard_source_pass':feedback.get('source_review_passed',True)and not frame['failures'],
        'native_correct':sum(bool(v['score']and v['score']['correct'])for v in feedback['views']),
        'native_total':len(feedback['views']),'unresolved':sum(not v['core_executed']for v in feedback['views'])}


def execute():
    p=protocol();libraries=compile_proposals();bank=read(OUT/'raw_source_bank.json');client=FrozenExecutor(ledger(p),OUT,p['executor_profile'])
    results=[]
    for arm,library in libraries.items():
        folder=OUT/arm;observations={}
        def observation(sid):
            path=folder/'observations'/(digest(sid)+'.json')
            if path.exists():return read(path)
            value=bank[sid]
            def event(record):immutable_json(folder/'read_events'/(digest(record['call_id'])+'.json'),record)
            obs=observe(client,RUN+':'+arm+':'+digest(sid),sid,library,source_text=value['source']['views'][0]['public']['source_text'],
                units=value['units'],source_output=value['empty_upstream'],save_event=event)
            immutable_json(path,obs);return obs
        for sid in p['acquisition_sources']:observations[sid]=observation(sid)
        nofit=[assess(library,observations[s],s)for s in p['acquisition_sources']]
        if 'language'in library:
            names=[r['id']for r in library['language']['rules']];recommended=library['selected_rule_ids'];costs={r['id']:r['cost']for r in library['language']['rules']}
            # Evaluate executable hypotheses, not arbitrary subsets of rendered
            # atoms. Preserve the best source-valid candidate at the time bound.
            candidates=[recommended,[],names]
            for name in names:
                candidates.append(sorted(set(recommended)^{name}))
            best=None;seen=set();start=time.monotonic();trials=[]
            for ids in candidates:
                key=tuple(sorted(ids))
                if key in seen:continue
                if trials and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
                seen.add(key);candidate=deepcopy(library);candidate['selected_rule_ids']=list(key)
                rows=[assess(candidate,observations[s],s)for s in p['acquisition_sources']]
                rank=(-sum(r['native_correct']for r in rows),sum(costs[x]for x in key),len(key),key)
                valid=all(r['hard_source_pass']for r in rows)
                trials.append({'rule_ids':list(key),'rows':rows,'hard_source_pass':valid,'rank':rank})
                if valid and(best is None or rank<best[0]):best=(rank,candidate)
            immutable_json(folder/'fit_receipt.json',{'trials':trials,'optimization_complete':False,'finite_local_candidate_selection':True,'new_model_calls':0})
            if best is None:
                immutable_json(folder/'unresolved.json',{'reason':'No source-valid acquired G in evaluated hypotheses','paid_reads_preserved':True});continue
            library=best[1]
        immutable_json(folder/'selected_before_reuse.json',{'library':library,'acquisition_only':True,'prior_reuse_exposure_disclosed':True})
        acquired=[assess(library,observations[s],s)for s in p['acquisition_sources']]
        reuse=[assess(library,observation(s),s)for s in p['fixed_reuse_sources']]
        value={'arm':arm,'acquisition':acquired,'fixed_reuse':reuse,'NoFit_acquisition':nofit,'goal_complete':False}
        immutable_json(folder/'result.json',value);results.append(value)
        print(json.dumps({'arm':arm,'acquisition':[r['native_correct']for r in acquired],
            'reuse':[r['native_correct']for r in reuse]}),flush=True)
    immutable_json(OUT/'result.json',{'arms':results,'goal_complete':False,'no_DEV_TEST':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare_runtime','validate','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare_runtime':prepare_runtime,'validate':compile_proposals,'execute':execute}[args.phase]()
