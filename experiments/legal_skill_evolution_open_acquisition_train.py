"""Finite original-TRAIN prototype of C and a same-information free update.

Preserves the continuous ledger. This is neither full training nor DEV/TEST,
and the independent teacher-artifact comparison is not a two-contribution claim.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import compile_update,observe,fit,execute
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,constructors,term_sort
from legal_skill_guard.skill_evolution.scoped_source_program import run_source,OUTPUT
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,signatures
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,execute_json,METHODS,CALLS
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories,attach_theories,diagnose_inputs
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_open_acquisition_update_20261113'
PARENT_RUN='legal_skill_evolution_open_acquisition_train_20261113'
ARMS=('ConstraintAcquire','FreeUpdate')
read=lambda p:json.loads(Path(p).read_text())
PLANNER="def apply(inputs,premises):\n    return {'queries':[]}\n"
SCHEMA=record_schema({'rationale':{'type':'string'},'operations':{'type':'array','items':OPERATION},
    'planner_functions':{'type':'array','items':{'type':'string'}},'scope':{'type':'string','enum':['focus_last','window']},
    'composition':{'type':'string'},'renderers_json':{'type':'string'},
    'suggested_rule_ids':{'type':'array','items':{'type':'string'}}})

COMMON='''Learn a reusable source-rule acquisition update from the actual original TRAIN materials and native feedback supplied. You are the skill teacher; weights stay frozen. Preserve valid old abilities. Do not branch on source IDs, company names or native labels. Native labels supervise learning, but must never be generated as source concepts, rules or native-answer probes. No new/synthetic training examples. Use verbatim TRAIN examples only in the examples field of acquired operations. A source citation or passing native answer alone does not prove source semantics. Missing semantics stays unresolved, not implicit False. Do not import an old law's rule or actor into a new contract.

The common asset is an actual earlier acquired source compiler and59 typed legal constructors with their unchanged consumer. Both arms receive identical full sources, lawful native supervision, common old program and current actual compiler outputs/feedback. Both can use narrow neural source operations, raw current text, pure helpers, arbitrary decomposition, guards and all supplied history. The common upstream compiler remains available, so this measures learning an update, not independent initial acquisition. All original outcomes/costs remain. No reuse source or label is supplied.

operations contain reusable questions, semantic choices with meanings and grounded original TRAIN demonstrations. unknown is supplied automatically. The executor is frozen Qwen3-8B thinking OFF; it returns {id,choice,evidence:[{unit_id,quote}]} for each actual query. It is fallible. Choose a FEW meaningful source operations rather than repacking complete native answers/IR into choices. A definite choice needs current exact evidence. Absence may be judged only when the operation explicitly examines a complete supplied window. Avoid requiring needless exact details when the source supports a sufficient bound.

planner_functions replace/add complete pure Python functions in the initial empty planner. Supply apply(inputs,premises) returning ONLY {queries:[{id:unique string,operation:declared name,unit_ids:[actual current unit anchors]}]}. inputs={phase:'plan',source_text,source_spans,semantic_answers:[]}. The source_spans list contains punctuation-grouped current {id,text}; anchors need not be dense. Plan necessary legal windows from current material, including actual cross-clause context; no per-contract ID tests. The planner can use pure helpers and prebound re. scope=focus_last means the LAST unit of each window is the clause being classified, others only context; scope=window classifies the whole supplied window. Unknown answers are terminal for an unchanged question/window; no hidden retry. The planner must not require a new model format or emit a final verdict.

The learned downstream composition receives all current raw text, units, the preserved upstream source_output, acquired operation definitions, planned queries, actual grounded answers and scope. Use actual observations; teacher-intended choices are not current facts. Existing unresolved statements and current source-specific effects must be respected. The output is typed statements with current support_ids; native task answering is performed by the unchanged consumer. Do not add default outputs to make handled=True. Explain the concrete reusable learning/repair in rationale. Keep the update executable and compact.'''

C_SPEC='''Use the supplied typed relational learner to learn G under all accumulated native/partial source constraints. composition is a JSON STRING containing exactly {signatures:<additional derived/output signature map>,constants:<sort to distinct scalar vocabulary>,rules:<candidate rule list>}. The host preserves every common observed signature (supplied in input); do not repeat or override it. Each additional signature is {arguments:[nominal sorts],kind:'derived'|'output'}. Each rule is {id:unique string,head:ATOM,body:[ATOM,...],cost:positive integer}. ATOM={predicate:declared name,arguments:[scalar|{var:'UppercaseName'},...],sign:'positive'|'negative'}. Rule heads are positive derived/output. Negative bodies mean explicit negative observations, never missing derived facts. Every variable binds through a body relation and must keep the same nominal sort. Static constants must be declared under their argument sort; current unit/query/term IDs and contract IDs are not static vocabulary. Candidate alternatives should include plausible generalizations/specializations that TRAIN feedback can distinguish; do not give only a fixed answer table. Costs are frozen before scoring.

Useful common facts: legacy_root(term), term_constructor(term,constructor), term_child(term,position,term), term_scalar(term,scalar), root_support(term,unit), reader_query(query,operation), query_focus(query,unit) for focus_last only, query_window(query,unit), query_choice(query,choice) for actual definite readings; source_unit(unit),next_unit(unit,unit),unit_text(unit,text). Unknown/unread observations remain explicit. Full other input is losslessly available via JSON relations; their signatures are supplied. All facts are implicitly scoped to the current law. Relations cannot join different contracts.

The public output keep_root has signature {arguments:['term'],kind:'output'} and explicitly retains an actual upstream root. Other outputs construct new terms using renderers_json, a JSON STRING of [{predicate,term:<constructor template>,support_arguments:[argument indices of sort unit],support_from_terms:[argument indices of sort term]}]. A template is ['acquired_ctor',child,...]. A child is another constructor template, {term_argument:i} to copy a current subtree, or {scalar_argument:i} to use a current scalar. Source-dependent literal strings cannot be hidden in templates. Every output argument is used in its term or provenance. Use the current acquired constructor meanings/types, not imaginary new constructors. Each constructed norm needs current unit or term provenance. All newly constructed terms must be source-supported even if native labels cannot distinguish an error. Include output signatures matching all renderers. keep_root needs no renderer.

suggested_rule_ids is your single chosen initial G before automated constraint learning; the host also learns G from your candidates. This permits an internal NoFit control using identical actual concept observations. It is not the independent strong FreeUpdate control. The source output language is finite during this prototype, not a permanent closed ontology. If a genuine expressive limitation remains, state it in rationale instead of fabricating meaning.'''

FREE_SPEC='''Use the strongest compact ordinary source-program update you judge suitable. composition is a complete pure Python program defining apply(inputs,premises). It receives inputs={source_text,source_spans,source_output,semantic_answers}, premises={}; source_output is the preserved current upstream result. Return ONLY {statements:[{term:typed acquired constructor list,support_ids:[current units]}],complete:bool,unresolved:[string]}. All learned raw source functions from the common asset may be reused or freely revised; you may use current raw text and semantic answers together. You have the same operation/planning/helper/constructor/feedback capabilities as the other arm and may use no neural operation if unnecessary. You may perform arbitrary pure decomposition, ordinary constraint logic and source-conditioned repair. Do not deliberately imitate a weaker lexical baseline. No model-written imports/network/files. Return renderers_json='[]' and suggested_rule_ids=[]. The host validates and executes your actual program. This independent update is a strong same-information whole-acquisition comparison, not a named-paper reproduction.'''



def history_row(parent,arm,key):
    for stage in ('acquisition','reuse'):
        path=parent/stage/arm/(key.replace(':','_')+'.json')
        if path.exists():return read(path)
    raise ValueError('Actual parent observation missing; do not create one')


def split_function_modules(proposal):
    import ast
    result=deepcopy(proposal);functions=[]
    for module in proposal['planner_functions']:
        tree=ast.parse(module)
        if any(not isinstance(n,ast.FunctionDef) for n in tree.body):raise ValueError('Only pure function modules')
        pieces=[ast.get_source_segment(module,n) for n in tree.body]
        if ast.dump(ast.parse('\n\n'.join(pieces)),include_attributes=False)!=ast.dump(tree,include_attributes=False):
            raise ValueError('Function extraction changed the supplied AST')
        functions.extend(pieces)
    result['planner_functions']=functions
    return result


def prepare():
    folder=ROOT/'artifacts'/RUN
    if (folder/'protocol.json').exists():return folder,read(folder/'protocol.json')
    public=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    def key(prefix):
        found=[s['key'] for s in public if s['key'].startswith('ContractNLI:'+prefix)]
        if len(found)!=1:raise ValueError('Fixed original TRAIN source must be unique')
        return found[0]
    profile=read(ROOT/'configs/legal_skill_evolution_formal_v5_20261111.json')
    counts=physical_snapshot(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(v.get('reserved',0) for v in counts.values()):raise ValueError('Reconcile actual in-flight requests first')
    paths=[Path(__file__).resolve(),ROOT/'experiments/legal_skill_evolution_role_TRAIN.py',
        *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT/'tests').glob('test_skill_evolution*.py'))]
    base=ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json'
    grammar=base.with_name('induced_grammar.json')
    data=[base,grammar,ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
        ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json']
    p={'run_id':RUN,'same_goal':True,'goal_complete':False,'arms':list(ARMS),
        'acquisition_sources':[key('35462327'),key('78adf3b3'),key('e7b78d42'),key('de427b59')],
        'parent_run':PARENT_RUN,
        'reuse_sources':[key('5cad3f37'),key('a5b0361f')],
        'selection':'Retain both original acquisition contexts, then update from the two actual frozen reuse failures. Select the next two original-order parents outside previous10 plus current4 before their new scoring. All original TRAIN, not blind evaluation.',
        'question':'Can actual executable concept acquisition plus global partial/native constraint induction produce supported rules used on subsequent original TRAIN sources?',
        'shared_seed':str(base.relative_to(ROOT)),'shared_grammar':str(grammar.relative_to(ROOT)),
        'shared_seed_cost':'Earlier actual acquisition/repair cost is common to both; incremental update comparison is not independent initial acquisition. Final accounting must charge the common seed logically to both.',
        'executor_profile':profile['executor'],'teacher_profile':profile['teacher'],'ledger_before':counts,
        'no_TEST_DEV_full_training_or_paper':True,'no_new_sources_or_seeds':True,'automatic_retries':0,
        'source_snapshot':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},
        'data_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data},
        'prototype_not_contribution_validation':True,'no_fit_control':'same candidate proposal/observations, suggested_rule_ids, no automated global fitting',
        'reuse_labels_not_used_in_learning_before_library_freeze':True}
    immutable_json(folder/'protocol.json',p);immutable_json(folder/'base.json',read(base));immutable_json(folder/'grammar.json',read(grammar))
    for f in paths:
        dest=folder/'source_snapshot'/f.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(f.read_bytes())
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        immutable_json(folder/'ledger_before.json',{'rows':db.execute('select * from calls order by id').fetchall()})
    return folder,p


def setup():
    folder,p=prepare()
    for name,h in {**p['source_snapshot'],**p['data_sha256']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen scientific input changed: '+name)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['acquisition_sources']+p['reuse_sources'],'dev':[],'test':[]},binding=digest(p))
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    return folder,p,ledger,public


def source_material(folder,p,public,key):
    path=folder/'upstream'/(key.replace(':','_')+'.json')
    base=read(folder/'base.json');source=public[key];pub=source['views'][0]['public']
    units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    if not path.exists():
        interpretation,event=run_source(base['source_program'],base['grammar'],read(folder/'grammar.json'),source)
        immutable_json(path,{'source_output':interpretation['source_program_output'],'interpretation':interpretation,'event':event})
    return pub,units,read(path)['source_output']


def acquire(arm):
    folder,p,ledger,public=setup();base=read(folder/'base.json');dst=folder/arm
    if (dst/'compiled.json').exists():return
    supervision=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    tasks=[]
    for key in p['acquisition_sources']:
        pub,units,upstream=source_material(folder,p,public,key)
        checker=contract_checker(base['grammar'],public[key],supervision[key])
        tasks.append({'source':public[key],'actual_current_units':units,'actual_upstream_output':upstream,
            'native_TRAIN_supervision':supervision[key],'actual_upstream_feedback':checker(upstream)})
    parent=ROOT/'artifacts'/PARENT_RUN
    previous=read(parent/arm/'learned.json')
    previous={k:v for k,v in previous.items() if k not in ('fit','exact_structural_adaptation')}
    for task_row in tasks:
        key=task_row['source']['key'];history=history_row(parent,arm,key)
        task_row['actual_previous_observation']=history['observation']
        fitted=parent/arm/'fitted_execution'/(key.replace(':','_')+'.json')
        task_row['actual_previous_execution']=read(fitted) if fitted.exists() else {k:v for k,v in history.items() if k not in ('observation','admission')}
    task={'tasks':tasks,'common_actual_library':base,'common_observed_signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
        'initial_planner_program':previous['planner_program'],'own_previous_learned_library':previous,'same_supervision_and_raw_material_for_both':True,'no_new_reuse_data':True}
    immutable_json(dst/'teacher_input.json',task)
    prompt=COMMON+'\n\n'+(C_SPEC if arm=='ConstraintAcquire' else FREE_SPEC)
    prompt+='\nThis is an actual feedback update after frozen prequential failures. Preserve old successful cases. Both previous planners missed governing/list clauses because their current-sentence lexical filter was too narrow. Repair reusable candidate-window planning, inherited clause scope and downstream composition as needed. Give every demonstration the exact full supplied source key, never TRAIN. Use all four actual history contexts; do not encode these source IDs or native labels. Do not claim a representation certificate: the previous finite output language had no admissible theory on the failed contexts.\nAllowed pure attribute names: '+','.join(sorted(METHODS))
    prompt+='\nAvailable builtin/helper call names: '+','.join(sorted(CALLS))+'. No next, reversed, imports, type or getattr. Only top-level pure functions; no nested functions,lambda or decorators.'
    if not (dst/'teacher.json').exists():
        result=FrozenTeacher(ledger,folder,p['teacher_profile']).propose(RUN+':teacher:'+arm,
            source_ids=p['acquisition_sources'],system_prompt=prompt+'\n'+INSTRUCTION,
            user_prompt=json.dumps(pack(task),ensure_ascii=False),output_schema=SCHEMA)
        immutable_json(dst/'teacher.json',result)
    proposal=read(dst/'teacher.json')['value']
    previous=read(ROOT/'artifacts'/PARENT_RUN/arm/'learned.json')
    proposal=split_function_modules(proposal)
    texts={key:public[key]['views'][0]['public']['source_text'] for key in p['acquisition_sources']}
    if arm=='ConstraintAcquire':
        extension=json.loads(proposal['composition'])
        extension['signatures']={**signatures(),'keep_root':{'arguments':['term'],'kind':'output'},**extension['signatures']}
        compiled=compile_update(previous,{**proposal,'language':extension,'renderers':json.loads(proposal['renderers_json'])},texts)
        if not set(proposal['suggested_rule_ids'])<={r['id'] for r in extension['rules']}:raise ValueError('NoFit uses proposed actual rules')
        compiled['suggested_rule_ids']=proposal['suggested_rule_ids']
    else:
        from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
        validate_operations(proposal['operations'],texts);validate_procedure(proposal['composition'],allow_helpers=True)
        compiled={'operations':proposal['operations'],'planner_program':function_update(previous['planner_program'],proposal['planner_functions']),
            'scope':proposal['scope'],'composition_program':proposal['composition'],'spec':base['grammar']}
    immutable_json(dst/'compiled.json',compiled)


def run_stage(reuse=False):
    folder,p,ledger,public=setup();stage='reuse' if reuse else 'acquisition';keys=p['reuse_sources'] if reuse else p['acquisition_sources']
    if reuse and not (folder/'library_freeze.json').exists():raise ValueError('Freeze learning before reuse')
    for arm in ARMS:
        library_path=folder/arm/('learned.json' if reuse else 'compiled.json')
        if not library_path.exists():raise ValueError('Complete actual acquisition/fit before advancing')
        library=read(library_path);observations=[];admissions=[];client=FrozenExecutor(ledger,folder,p['executor_profile'])
        for key in keys:
            dest=folder/stage/arm/(key.replace(':','_')+'.json')
            if dest.exists():
                row=read(dest)
            else:
                pub,units,upstream=source_material(folder,p,public,key)
                prior=history_row(ROOT/'artifacts'/PARENT_RUN,arm,key) if not reuse else None
                observation=observe(client,RUN+':'+stage+':'+arm+':'+key,key,library,
                    source_text=pub['source_text'],units=units,source_output=upstream,previous_observation=prior['observation'] if prior else None,
                    save_event=lambda e:immutable_json(folder/stage/arm/'events'/(digest(e['call_id'])+'.json'),e))
                # Original TRAIN annotations enter after this source's actual reads.
                grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[key]
                checker=contract_checker(library['spec'],public[key],grading)
                row={'source':key,'arm':arm,'observation':observation,'stage':stage,'goal_complete':False}
                if arm=='ConstraintAcquire':
                    if reuse:
                        execution=execute(library,observation);row.update({'execution':execution,'feedback':checker(execution['source_output'])})
                    else:
                        admission=admissible_theories(library,observation,checker,timeout_seconds=90)
                        row['admission']=admission
                        suggested={**library,'selected_rule_ids':library['suggested_rule_ids']}
                        nofit=execute(suggested,observation);row.update({'no_fit_execution':nofit,'no_fit_feedback':checker(nofit['source_output'])})
                else:
                    output=execute_json(library['composition_program'],{'source_text':pub['source_text'],'source_spans':units,
                        'source_output':upstream,'semantic_answers':observation['visible_inputs']['answers']},{},allow_helpers=True)
                    jsonschema.validate(output,OUTPUT)
                    for r in output['statements']:term_sort(r['term'],constructors(library['spec']))
                    row.update({'source_output':output,'feedback':checker(output)})
                immutable_json(dest,row)
            if arm=='ConstraintAcquire' and not reuse:
                observations.append(row['observation']);admissions.append(row['admission'])
            print(json.dumps({'stage':stage,'arm':arm,'source':key,'queries':row['observation']['execution']['planned_queries'],
                'new_physical':row['observation']['execution']['new_physical_requests'],
                'native_accepted':row.get('feedback',{}).get('accepted'),
                'admission':row.get('admission',{}).get('status')}),flush=True)
        if not reuse:
            if arm=='ConstraintAcquire':
                strict_diagnosis=diagnose_inputs(observations,admissions,'not_run')
                immutable_json(folder/arm/'diagnosis_before_fit.json',strict_diagnosis)
                if any(a['status']!='complete' or not a['allowed_theories'] for a in admissions):
                    immutable_json(folder/arm/'not_fitted.json',{'reason':'No complete admissible theory for all acquisition contexts',
                        'diagnosis':strict_diagnosis,'goal_complete':False});continue
                training=[attach_theories(o,a) for o,a in zip(observations,admissions)]
                learned,result=fit(library,training,timeout_seconds=90)
                immutable_json(folder/arm/'fit.json',result)
                if result['status']!='sat':continue
                immutable_json(folder/arm/'diagnosis_after_fit.json',diagnose_inputs(observations,admissions,'sat'))
            else:learned=library
            immutable_json(folder/arm/'learned.json',learned)
    if not reuse and all((folder/a/'learned.json').exists() for a in ARMS):
        immutable_json(folder/'library_freeze.json',{'libraries':{a:digest(read(folder/a/'learned.json')) for a in ARMS},
            'reuse_sources':p['reuse_sources'],'reuse_labels_not_used_in_learning_by_this_run':True,'goal_complete':False})


def native_loss_reuse():
    """Continue cached actual learning after removing the accidental zero-error gate.

    No new teacher/learning data. Original strict-fit failure stays immutable.
    Bind the changed learner separately before reading the same fixed next pair.
    """
    parent=ROOT/'artifacts'/RUN;old=read(parent/'protocol.json')
    run=RUN.replace('open_acquisition_update','open_acquisition_native_loss')
    folder=ROOT/'artifacts'/run
    if not (folder/'protocol.json').exists():
        counts=physical_snapshot(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
        if any(v.get('reserved',0) for v in counts.values()):raise ValueError('Reconcile pending requests first')
        paths=[Path(__file__).resolve(),*sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
            *sorted((ROOT/'tests').glob('test_skill_evolution*.py'))]
        libs={'ConstraintAcquire':parent/'post_native_loss_fit/learned.json','FreeUpdate':parent/'FreeUpdate/learned.json'}
        data=[*libs.values(),parent/'base.json',parent/'grammar.json',
            ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
            ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json']
        p={'run_id':run,'parent_run':RUN,'same_goal':True,'goal_complete':False,
            'acquisition_sources':old['acquisition_sources'],'reuse_sources':old['reuse_sources'],
            'executor_profile':old['executor_profile'],'ledger_before':counts,
            'change':'Hard type/provenance/explicit source checks unchanged. Select G by original native TRAIN error first and rule cost second; positive residual error remains failure, not success.',
            'no_new_teacher_or_training_observations':True,'same_previously_fixed_reuse_pair':True,
            'source_snapshot':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in paths},
            'data_sha256':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in data}}
        immutable_json(folder/'protocol.json',p)
        for arm,path in libs.items():immutable_json(folder/arm/'learned.json',read(path))
        for name in ('base.json','grammar.json'):immutable_json(folder/name,read(parent/name))
        immutable_json(folder/'library_freeze.json',{'libraries':{a:digest(read(q)) for a,q in libs.items()},
            'native_training_errors_remaining':2,'all_native_training_constraints_satisfied':False,
            'reuse_sources':p['reuse_sources'],'reuse_annotations_not_used_for_training':True,'goal_complete':False})
        for q in paths:
            dest=folder/'source_snapshot'/q.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(q.read_bytes())
        with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
            immutable_json(folder/'ledger_before.json',{'rows':db.execute('select * from calls order by id').fetchall()})
    p=read(folder/'protocol.json')
    for name,h in {**p['source_snapshot'],**p['data_sha256']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen native-loss continuation changed: '+name)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,
        sources={'train':p['reuse_sources'],'dev':[],'test':[]},binding=digest(p))
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    for arm in ARMS:
        library=read(folder/arm/'learned.json');client=FrozenExecutor(ledger,folder,p['executor_profile'])
        for key in p['reuse_sources']:
            dest=folder/'reuse'/arm/(key.replace(':','_')+'.json')
            if dest.exists():continue
            pub,units,upstream=source_material(folder,p,public,key)
            observation=observe(client,run+':reuse:'+arm+':'+key,key,library,
                source_text=pub['source_text'],units=units,source_output=upstream,
                save_event=lambda e:immutable_json(folder/'reuse'/arm/'events'/(digest(e['call_id'])+'.json'),e))
            grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[key]
            checker=contract_checker(library['spec'],public[key],grading)
            row={'source':key,'arm':arm,'observation':observation,'goal_complete':False}
            if arm=='ConstraintAcquire':
                execution=execute(library,observation);row.update({'execution':execution,'feedback':checker(execution['source_output'])})
                nofit=execute({**library,'selected_rule_ids':library['suggested_rule_ids']},observation)
                row.update({'no_fit_execution':nofit,'no_fit_feedback':checker(nofit['source_output'])})
            else:
                output=execute_json(library['composition_program'],{'source_text':pub['source_text'],'source_spans':units,
                    'source_output':upstream,'semantic_answers':observation['visible_inputs']['answers']},{},allow_helpers=True)
                jsonschema.validate(output,OUTPUT)
                for r in output['statements']:term_sort(r['term'],constructors(library['spec']))
                row.update({'source_output':output,'feedback':checker(output)})
            immutable_json(dest,row)
            print(json.dumps({'arm':arm,'source':key,'queries':observation['execution']['planned_queries'],
                'new_physical':observation['execution']['new_physical_requests'],
                'views':[(r['view'],r['core_executed'],(r.get('score') or {}).get('correct')) for r in row['feedback']['views']]}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','acquire','acquisition','reuse','native-loss-reuse'])
    parser.add_argument('--arm',choices=ARMS);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='prepare':prepare()
        elif args.phase=='acquire':acquire(args.arm)
        elif args.phase=='native-loss-reuse':native_loss_reuse()
        else:run_stage(reuse=args.phase=='reuse')
