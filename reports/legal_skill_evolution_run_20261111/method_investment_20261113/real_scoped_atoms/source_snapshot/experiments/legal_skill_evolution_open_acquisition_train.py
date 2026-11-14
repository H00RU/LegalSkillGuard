"""Current finite semantic-routing/open-vocabulary continuation of the same Goal.

Earlier runners/results are frozen in source_snapshot and git. One current entry;
no full training, DEV/TEST, replacement ledger or changed model configuration.
"""
import argparse
import ast
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
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker,contract_execution
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import compile_update,observe,fit,execute
from legal_skill_guard.skill_evolution.scoped_grammar import CONSTRUCTOR,constructors,term_sort,material_public
from legal_skill_guard.skill_evolution.scoped_source_program import run_source,OUTPUT
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations,prepare_queries
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,execute_json,validate_procedure,METHODS,CALLS
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories,attach_scored_theories,diagnose_inputs
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack
from legal_skill_guard.inference.codex_cli_client import render_structured_codex_prompt,strict_output_schema_issues,CODEX_TURN_INPUT_CHARACTER_LIMIT
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113'
REPLAY_RUNS=('legal_skill_evolution_open_acquisition_semantic_route_absence_20261113',
    'legal_skill_evolution_open_acquisition_semantic_route_recovery_20261113',
    'legal_skill_evolution_open_acquisition_semantic_route_grounded_20261113',
    'legal_skill_evolution_open_acquisition_semantic_route_scoped_20261113')
TEACHER_RUN='legal_skill_evolution_open_acquisition_semantic_route_v3_20261113'
PARENT_RUN='legal_skill_evolution_open_acquisition_native_loss_20261113'
ARMS=('ConstraintAcquire','FreeUpdate')
ABSENCE_CHOICES={
    'ConstraintAcquire':{'disclosure_permission_scout':['none_in_complete_source'],
        'disposal_obligation_scout':['none_in_complete_source']},
    'FreeUpdate':{'protected_disclosure_structure':['no_disclosure_norm'],
        'source_disposal_trigger_structure':['no_disposal_duty'],
        'post_disposal_retention_structure':['no_retention_rule']}}
read=lambda p:json.loads(Path(p).read_text())
SCHEMA=record_schema({'rationale':{'type':'string'},'operations':{'type':'array','items':OPERATION},
    'planner_functions':{'type':'array','items':{'type':'string'}},'scope':{'type':'string','enum':['focus_last','window']},
    'composition':{'type':'string'},'renderers_json':{'type':'string'},
    'suggested_rule_ids':{'type':'array','items':{'type':'string'}},
    'new_constructors':{'type':'array','items':CONSTRUCTOR},
    'decision_functions':{'type':'array','items':{'type':'string'}}})

COMMON=r'''Learn a reusable source-rule acquisition update from the actual original TRAIN materials and native feedback supplied. You are the skill teacher; weights stay frozen. Preserve valid old abilities. Do not branch on source IDs, company names or native labels. Native labels supervise learning, but must never be generated as source concepts, rules or native-answer probes. No new/synthetic training examples. Use verbatim TRAIN examples only in the examples field of acquired operations. A source citation or passing native answer alone does not prove source semantics. Missing semantics stays unresolved, not implicit False. Do not import an old law's rule or actor into a new contract.

The common asset is an actual earlier acquired source compiler and59 typed legal constructors as an initial vocabulary, with the existing consumer. Both arms receive identical full sources, lawful native supervision, common old program and current actual compiler outputs/feedback. Both can use narrow neural source operations, raw current text, pure helpers, arbitrary decomposition, guards and all supplied history. The common upstream compiler remains available, so this measures learning an update, not independent initial acquisition. All original outcomes/costs remain. No reuse source or label is supplied.

operations contain reusable questions, semantic choices with meanings and grounded original TRAIN demonstrations. unknown is supplied automatically. The executor is frozen Qwen3-8B thinking OFF; it returns {id,choice,evidence:[{unit_id,quote}]} for each actual query. It is fallible. Choose a FEW meaningful source operations rather than repacking complete native answers/IR into choices. A definite choice needs current exact evidence. Absence may be judged only when the operation explicitly examines a complete supplied window. Avoid requiring needless exact details when the source supports a sufficient bound.

planner_functions replace/add complete pure Python functions in the previous actual planner. Supply apply(inputs,premises) returning ONLY {queries:[{id:unique string,operation:declared name,unit_ids:[actual current unit anchors]}]}. inputs={phase:'plan',source_text,source_spans,source_output,semantic_answers:actual answers already obtained in this execution}. The source_spans list contains punctuation-grouped current {id,text}; anchors need not be dense. Plan necessary legal windows from current material, including actual cross-clause context; no per-contract ID tests. The planner can use pure helpers and prebound re. scope=focus_last means the LAST unit of each window is the clause being classified, others only context; scope=window classifies the whole supplied window. Unknown answers are terminal for an unchanged question/window; no hidden retry. The planner must not require a new model format or emit a final verdict.

The learned downstream composition receives all current raw text, units, the preserved upstream source_output, acquired operation definitions, planned queries, actual grounded answers and scope. Use actual observations; teacher-intended choices are not current facts. Existing unresolved statements and current source-specific effects must be respected. The output is typed statements with current support_ids; native task answering is performed by the typed consumer; the original benchmark scorer stays unchanged. Do not add default outputs to make handled=True. Explain the concrete reusable learning/repair in rationale. Keep the update executable and compact.

CURRENT EXECUTABLE CAPABILITIES AND ACTUAL FAILURE EVIDENCE:
The host repeatedly calls the planner with actual answers until no new logical query is planned. You may first perform broad semantic discovery and then request specific roles, relations, triggers or scopes from its actual evidence. Pure lexical gates previously produced ZERO queries on two successive reuse pairs. Do not keep a hard gate requiring the literal "Confidential Information", employees and a fixed permission phrase in the same sentence. The protected information may be called "information it receives" and a permission may refer to a separately defined class. Inspect source meaning; do not merely add these six cases' literal phrases to a whitelist. A useful scout may read a complete current window and identify supporting units via evidence; fine questions then use actual scout results. Queries may contain multiple evidence units; quotes must be exact inside each single unit. Never concatenate separated original passages into one example quote. Full-source absence is only an actual source-level observation of a specified semantic category over a complete supplied source, not the default absence of parsed rules. Do not ask the executor for a native hypothesis verdict.

Each query ID must keep its operation/window through an execution. Query identity is its operation definition plus ordered actual window and scope. Reissuing the same question under a different ID is rejected; an old unknown is not retried. A stable unchanged prior reading can be reused even when only its opaque ID changes. No new request limit is imposed; request real new information only. If scope=window, operation questions define what to inspect; an operation may explicitly say its last unit is the target with earlier units as context, whereas a complete-source question inspects all supplied units.

new_constructors is an explicit array of {name,meaning,sort,arguments:[sort,...]}; decision_functions is an array of pure function modules added/replaced in your previous typed consumer. Empty arrays are valid. Both arms may extend the output language/consumer, not only questions. Preserve the meanings of existing constructors. In particular, "purpose_completion" means EXPRESS completion of the agreement's stated purpose; failure to enter a business relationship by a deadline must not be renamed to it merely to fit a label. Preserve a source event through a truthful new type when needed and learn any native interpretation separately. Do not omit source-explicit copies to obtain a preferred retention answer, or claim complete=True with relevant unresolved scope. The six native TRAIN annotation sets are lawful supervision, not source facts. Original source/scorer/type/provenance checks remain. Residual TRAIN errors are reported and minimized, not made an installation stop condition. Unknown source information stays unresolved.

Return each complete new planner/consumer function in its own string. All example source values must be the exact full supplied key, never TRAIN. No source/company-ID applicability tests or native labels in source programs/concepts. Acquisition examples must be contiguous verbatim original passages; use separate examples when needed, not an ellipsis or invented bridge. Keep the learning update compact, executable, and useful beyond a single supplied contract.
'''

C_SPEC=r'''Use the supplied typed relational learner to learn G under all accumulated native/partial source constraints. composition is a JSON STRING containing exactly {signatures:<additional derived/output signature map>,constants:<sort to distinct scalar vocabulary>,rules:<candidate rule list>}. The host preserves every common observed signature (supplied in input); do not repeat or override it. Each additional signature is {arguments:[nominal sorts],kind:'derived'|'output'}. Each rule is {id:unique string,head:ATOM,body:[ATOM,...],cost:positive integer}. ATOM={predicate:declared name,arguments:[scalar|{var:'UppercaseName'},...],sign:'positive'|'negative'}. Rule heads are positive derived/output. Negative bodies mean explicit negative observations, never missing derived facts. Every variable binds through a body relation and must keep the same nominal sort. Static constants must be declared under their argument sort; current unit/query/term IDs and contract IDs are not static vocabulary. Candidate alternatives should include plausible generalizations/specializations that TRAIN feedback can distinguish; do not give only a fixed answer table. Costs are frozen before scoring.

Useful common facts: legacy_root(term), term_constructor(term,constructor), term_child(term,position,term), term_scalar(term,scalar), root_support(term,unit), reader_query(query,operation), query_focus(query,unit) for focus_last only, query_window(query,unit), query_choice(query,choice) for actual definite readings; source_unit(unit),next_unit(unit,unit),unit_text(unit,text). Unknown/unread observations remain explicit. Full other input is losslessly available via JSON relations; their signatures are supplied. All facts are implicitly scoped to the current law. Relations cannot join different contracts.

The public output keep_root has signature {arguments:['term'],kind:'output'} and explicitly retains an actual upstream root. Other outputs construct new terms using renderers_json, a JSON STRING of [{predicate,term:<constructor template>,support_arguments:[argument indices of sort unit],support_from_terms:[argument indices of sort term],support_from_queries:[argument indices of sort query]}]. A template is ['acquired_ctor',child,...]. A child is another constructor template, {term_argument:i} to copy a current subtree, or {scalar_argument:i} to use a current scalar. Source-dependent literal strings cannot be hidden in templates. Every output argument is used in its term or provenance. Use the current acquired constructor meanings/types or your explicitly declared new_constructors. Each constructed norm needs current unit or term provenance. All newly constructed terms must be source-supported even if native labels cannot distinguish an error. Include output signatures matching all renderers. keep_root needs no renderer.

suggested_rule_ids is your single chosen initial G before automated constraint learning; the host also learns G from your candidates. This permits an internal NoFit control using identical actual concept observations. It is not the independent strong FreeUpdate control. The source output language is finite during this prototype, not a permanent closed ontology. If a genuine expressive limitation remains, state it in rationale instead of fabricating meaning.
Query provenance copies the actual answered query's full unit window into support_ids. An unknown/unanswered query cannot support a constructed assertion. This is grounding, not a source-truth certificate. Renderer support_from_queries is optional when unused; include it for claims about a complete queried window. Unknown/unread observations are never filled by solver guesses.
The teacher's suggested_rule_ids is the actual direct initial composition; the learner separately optimizes native TRAIN mistakes before frozen rule cost. Keep meaningful candidate alternatives; do not intentionally weaken your suggested program to manufacture an ablation effect. The finite solver does not certify English source meaning. In this study exact observation conflicts have not occurred, so do not claim a representation certificate from differing full raw sources or a restricted output failure.
'''

FREE_SPEC=r'''Use the strongest compact ordinary source-program update you judge suitable. composition is a complete pure Python program defining apply(inputs,premises). It receives inputs={source_text,source_spans,source_output,semantic_answers}, premises={}; source_output is the preserved current upstream result. Return ONLY {statements:[{term:typed acquired constructor list,support_ids:[current units]}],complete:bool,unresolved:[string]}. All learned raw source functions from the common asset may be reused or freely revised; you may use current raw text and semantic answers together. You have the same operation/planning/helper/constructor/feedback capabilities as the other arm and may use no neural operation if unnecessary. You may perform arbitrary pure decomposition, ordinary constraint logic and source-conditioned repair. Do not deliberately imitate a weaker lexical baseline. No model-written imports/network/files. Return renderers_json='[]' and suggested_rule_ids=[]. The host validates and executes your actual program. This independent update is a strong same-information whole-acquisition comparison, not a named-paper reproduction.
Both your new_constructors and decision_functions use the same update semantics as the other arm. The original benchmark scorer is unchanged. You may use the same adaptive semantic discovery or strong pure-code alternative. Choose the strongest approach from the same raw material/supervision; do not preserve the old failing lexical gate merely to look different.'''

def functions(modules):
    result=[]
    for module in modules:
        tree=ast.parse(module)
        if any(not isinstance(n,ast.FunctionDef) for n in tree.body):raise ValueError('Only complete pure functions')
        pieces=[ast.get_source_segment(module,n) for n in tree.body]
        if ast.dump(ast.parse('\n\n'.join(pieces)),include_attributes=False)!=ast.dump(tree,include_attributes=False):
            raise ValueError('Function extraction changed AST')
        result.extend(pieces)
    return result


def history_row(parent,arm,key):
    seen=set()
    while parent.name not in seen:
        seen.add(parent.name)
        for stage in ('reuse','acquisition'):
            path=parent/stage/arm/(key.replace(':','_')+'.json')
            if path.exists():return read(path)
        protocol=read(parent/'protocol.json')
        if not protocol.get('parent_run'):break
        parent=ROOT/'artifacts'/protocol['parent_run']
    raise ValueError('Actual TRAIN history missing; no fabricated observation')


def prepare():
    folder=ROOT/'artifacts'/RUN
    if (folder/'protocol.json').exists():return folder,read(folder/'protocol.json')
    parent=ROOT/'artifacts'/PARENT_RUN;old=read(parent/'protocol.json')
    public=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    def key(prefix):
        keys=[s['key'] for s in public if s['key'].startswith('ContractNLI:'+prefix)]
        if len(keys)!=1:raise ValueError('Original TRAIN identity must be unique')
        return keys[0]
    counts=physical_snapshot(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(v.get('reserved',0) for v in counts.values()):raise ValueError('Reconcile actual pending requests first')
    profile=read(ROOT/'configs/legal_skill_evolution_formal_v5_20261111.json')
    files=[Path(__file__).resolve(),ROOT/'experiments/legal_skill_evolution_role_TRAIN.py',
        *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT/'tests').glob('test_skill_evolution*.py'))]
    teacher=ROOT/'artifacts'/TEACHER_RUN
    data=[parent/'base.json',parent/'grammar.json',*(parent/a/'learned.json' for a in ARMS),
        *(teacher/a/'scoped_compiled.json' for a in ARMS),*(teacher/a/'teacher.json' for a in ARMS),
        ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
        ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json',
        *(ROOT/'artifacts'/name/'protocol.json' for name in REPLAY_RUNS)]
    acquisition=old['acquisition_sources']+old['reuse_sources'];reuse=[key('8fb38aee'),key('6fce8464')]
    sources={s['key']:s for s in public}
    if len({sources[k]['parent_id'] for k in acquisition+reuse})!=8:raise ValueError('Distinct original mother sources required')
    p={'run_id':RUN,'parent_run':PARENT_RUN,'teacher_artifacts_from':TEACHER_RUN,'same_goal':True,'goal_complete':False,
        'acquisition_sources':acquisition,'reuse_sources':reuse,'arms':list(ARMS),
        'exact_replay_from':list(REPLAY_RUNS),
        'selection':'Use the six actual existing TRAIN histories; next two original-order TRAIN mothers outside the previous10 and these6 fixed before new scoring. No new dataset/source/seed or blind TEST claim.',
        'executor_profile':profile['executor'],'teacher_profile':profile['teacher'],'ledger_before':counts,
        'shared_seed_cost':'The actual older compiler/grammar cost is inherited equally; each arm retains its own real update/repair costs.',
        'source_snapshot':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in files},
        'data_sha256':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in data},
        'no_full_training_DEV_TEST_paper':True,'no_new_mechanical_request_cap':True,'automatic_retries':0,
        'reuse_annotations_not_used_for_learning':True,
        'change':'Honor acquired choices that explicitly mean absence after inspecting the complete source. Require actual window scope and every current source unit; retain the actual model choice and record full-source query provenance, never invent quotes or derive negatives from unknown/unread. Same declaration mechanism in both arms; prompts, choices, meanings, learned programs and scoring unchanged. Reuse all existing identical physical requests; no teacher reacquisition.'}
    immutable_json(folder/'protocol.json',p)
    for name in ('base.json','grammar.json'):immutable_json(folder/name,read(parent/name))
    for a in ARMS:
        immutable_json(folder/'previous'/a/'learned.json',read(parent/a/'learned.json'))
        immutable_json(folder/a/'teacher.json',read(teacher/a/'teacher.json'))
        library=read(teacher/a/'scoped_compiled.json')
        library['complete_source_absence_choices']=ABSENCE_CHOICES[a]
        definitions=[]
        by_op={o['name']:o for o in library['operations']}
        for operation,choices in ABSENCE_CHOICES[a].items():
            by_choice={c['name']:c for c in by_op[operation]['choices']}
            definitions.extend({'operation':operation,'question':by_op[operation]['question'],
                'choice':by_choice[choice]} for choice in choices)
        immutable_json(folder/a/'compiled.json',library)
        immutable_json(folder/a/'absence_contract_declarations.json',{
            'grounded_in_existing_acquired_meanings':definitions,
            'previous_library_sha256':digest(read(teacher/a/'scoped_compiled.json')),
            'new_library_sha256':digest(library),'model_prompt_or_choice_changed':False,
            'new_legal_rule_or_answer_added':False,'new_model_requests':0})
        immutable_json(folder/a/'scope_contract_adaptation.json',read(teacher/a/'scope_contract_adaptation.json'))
    for q in files:
        dst=folder/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(q.read_bytes())
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


def source_material(folder,public,key):
    path=folder/'upstream'/(key.replace(':','_')+'.json');base=read(folder/'base.json');source=public[key]
    pub=source['views'][0]['public'];units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    if not path.exists():
        interpretation,event=run_source(base['source_program'],base['grammar'],read(folder/'grammar.json'),source)
        immutable_json(path,{'source_output':interpretation['source_program_output'],'event':event})
    return pub,units,read(path)['source_output']


def evaluate_source(library,observation,source,grading):
    if 'language' in library:result=execute(library,observation);output=result['source_output']
    else:
        v=observation['visible_inputs']
        output=execute_json(library['composition_program'],{'source_text':v['source_text'],'source_spans':v['units'],
            'source_output':v['source_output'],'semantic_answers':v['answers']},{},allow_helpers=True)
        jsonschema.validate(output,OUTPUT)
        for r in output['statements']:term_sort(r['term'],constructors(library['spec']))
        result={'source_output':output}
    check=contract_execution(library['spec'],source) if grading is None else contract_checker(library['spec'],source,grading)
    return {'execution':result,'feedback':check(output)}


def teacher_request(arm):
    folder,p,ledger,public=setup();previous=read(folder/'previous'/arm/'learned.json')
    path=folder/arm/'teacher_input.json'
    if path.exists():
        task=read(path)
    else:
        grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json');tasks=[]
        for key in p['acquisition_sources']:
            pub,units,upstream=source_material(folder,public,key);row=history_row(ROOT/'artifacts'/PARENT_RUN,arm,key);o=row['observation']
            actual=evaluate_source(previous,o,public[key],grading[key])
            tasks.append({'source':public[key],'actual_current_units':units,'actual_upstream_output':upstream,
                'native_TRAIN_supervision':grading[key],'actual_previous_reading':{
                    'visible_inputs':o['visible_inputs'],'execution':o['execution'],
                    'visible_inputs_sha256':o['visible_inputs_sha256'],'contract_sha256':o['contract_sha256']},
                'actual_previous_execution':actual})
        state={k:v for k,v in previous.items() if k not in ('fit','exact_structural_adaptation')}
        fit_record=previous.get('fit',{}).get('result')
        if fit_record:state['previous_fit_summary']={k:fit_record[k] for k in ('status','selected_rule_ids','cost','native_loss','native_loss_by_context','countermodels','all_supplied_native_constraints_satisfied') if k in fit_record}
        task={'tasks':tasks,'common_actual_library':read(folder/'base.json'),'own_previous_learned_library':state,
            'common_observed_signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
            'fact_encoder_source':(ROOT/'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
            'derived_fact_encoding':'The previous context triples/term-node maps are exactly determined by complete visible_inputs and the supplied encoder; they are losslessly re-encoded here, never additional legal facts. Full original records remain in artifacts.',
            'same_original_material_and_native_supervision':True,'no_reuse_data':True}
    task=json.loads(json.dumps(task,ensure_ascii=False,sort_keys=True))
    system=COMMON+'\n\n'+(C_SPEC if arm=='ConstraintAcquire' else FREE_SPEC)+'\n'+INSTRUCTION
    system+='\nAllowed pure attributes: '+','.join(sorted(METHODS))+'\nAllowed builtin/helper calls: '+','.join(sorted(CALLS))+'. No nested functions,lambda,imports,next,reversed,type or getattr.'
    user=json.dumps(pack(task),ensure_ascii=False)
    args={'source_ids':p['acquisition_sources'],'system_prompt':system,'user_prompt':user,'output_schema':SCHEMA}
    immutable_json(folder/arm/'teacher_input.json',task)
    issues=strict_output_schema_issues(SCHEMA);size=len(render_structured_codex_prompt(system,user))
    immutable_json(folder/arm/'teacher_preflight.json',{'input_characters':size,'transport_limit':CODEX_TURN_INPUT_CHARACTER_LIMIT,
        'schema_issues':issues,'new_model_requests':0,'frozen_task_sha256':digest(task),'frozen_request_sha256':digest(args),'all_original_G_inputs_preserved':True,'derived_triplets_reconstructible':True})
    if issues or size>CODEX_TURN_INPUT_CHARACTER_LIMIT:raise ValueError('Fix actual teacher transport offline before dispatch')
    return folder,p,ledger,public,args


def compile_arm(arm):
    folder,p,ledger,public=setup();dst=folder/arm
    if (dst/'compiled.json').exists():return
    proposal=read(dst/'teacher.json')['value'];jsonschema.validate(proposal,SCHEMA)
    previous=read(folder/'previous'/arm/'learned.json');texts={k:public[k]['views'][0]['public']['source_text'] for k in p['acquisition_sources']}
    validate_operations(proposal['operations'],texts)
    planner_parts=functions(proposal['planner_functions']);decision_parts=functions(proposal['decision_functions'])
    forbidden_ids={v for k in p['acquisition_sources'] for v in (k,public[k]['parent_id'])}
    codes=planner_parts+decision_parts+([proposal['composition']] if arm=='FreeUpdate' else [])
    for code in codes:
        if any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in forbidden_ids for n in ast.walk(ast.parse(code))):
            raise ValueError('A source identifier is not a learned applicability condition')
    semantic={'constructors':proposal['new_constructors'],'decision_functions':decision_parts}
    if arm=='ConstraintAcquire':
        language=json.loads(proposal['composition']);language['signatures']={**signatures(),'keep_root':{'arguments':['term'],'kind':'output'},**language['signatures']}
        if any(language['constants'].get(s) for s in ('unit','term','query','json_node')):raise ValueError('Opaque current identities cannot be static vocabulary')
        compiled=compile_update(previous,{**proposal,'planner_functions':planner_parts,'language':language,
            'renderers':json.loads(proposal['renderers_json'])},texts,semantic_update=semantic)
        if not set(proposal['suggested_rule_ids'])<={r['id'] for r in language['rules']}:raise ValueError('NoFit names an unproposed rule')
        compiled['suggested_rule_ids']=proposal['suggested_rule_ids']
    else:
        validate_procedure(proposal['composition'],allow_helpers=True);spec=deepcopy(previous['spec'])
        spec['constructors'].extend(deepcopy(proposal['new_constructors']));spec['decision_program']=function_update(spec['decision_program'],decision_parts);constructors(spec)
        compiled={'operations':proposal['operations'],'planner_program':function_update(previous['planner_program'],planner_parts),
            'scope':proposal['scope'],'composition_program':proposal['composition'],'spec':spec}
    plans=[]
    for key in p['acquisition_sources']:
        pub,units,upstream=source_material(folder,public,key)
        plans.append({'source':key,'initial_queries':prepare_queries(compiled['planner_program'],compiled['operations'],pub['source_text'],units,source_output=upstream)})
    immutable_json(dst/'offline_initial_plans.json',{'rows':plans,'new_model_requests':0})
    immutable_json(dst/'compiled.json',compiled)


def acquire(arm):
    folder,p,ledger,public=setup()
    if (folder/arm/'compiled.json').exists():return
    raise ValueError('Reconcile the existing paid teacher artifacts; do not duplicate acquisition')

def run_stage(reuse=False):
    folder,p,ledger,public=setup();stage='reuse' if reuse else 'acquisition'
    if reuse and not (folder/'library_freeze.json').exists():raise ValueError('Freeze acquired libraries before reuse')
    keys=p['reuse_sources'] if reuse else p['acquisition_sources']
    for arm in ARMS:
        library=read(folder/arm/('learned.json' if reuse else 'compiled.json'));client=FrozenExecutor(ledger,folder,p['executor_profile']);rows=[]
        client.exact_replay_roots=[ROOT/'artifacts'/name for name in p['exact_replay_from']]
        for key in keys:
            dst=folder/stage/arm/(key.replace(':','_')+'.json')
            if dst.exists():rows.append(read(dst));continue
            pub,units,upstream=source_material(folder,public,key)
            prior=None if reuse else history_row(ROOT/'artifacts'/PARENT_RUN,arm,key)['observation']
            try:
                o=observe(client,RUN+':'+stage+':'+arm+':'+key,key,library,source_text=pub['source_text'],units=units,
                    source_output=upstream,previous_observation=prior,
                    save_event=lambda e:immutable_json(folder/stage/arm/'events'/(digest(e['call_id'])+'.json'),e))
            except (ValueError,jsonschema.ValidationError) as error:
                # Rejected semantics is neither a successful observation nor
                # a negative legal fact. Keep every view and raw event, skip
                # no source silently, and do not replay the failed question.
                row={'source':key,'arm':arm,'goal_complete':False,
                    'status':'observation_rejected','error':type(error).__name__+': '+str(error),
                    'feedback':{'views':[{'view':v['id'],'core_executed':False,'score':None,
                        'reason':'source_reading_rejected'} for v in public[key]['views']]},
                    'retained_in_all_source_denominators':True,'observation_used_for_learning':False,
                    'raw_events_directory':str((folder/stage/arm/'events').relative_to(ROOT))}
                immutable_json(dst,row);rows.append(row)
                print(json.dumps({'stage':stage,'arm':arm,'source':key,'status':row['status'],'error':row['error']}),flush=True)
                continue
            immutable_json(folder/stage/arm/'observations'/(key.replace(':','_')+'.json'),o)
            grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[key]
            row={'source':key,'arm':arm,'observation':o,'goal_complete':False}
            if arm=='ConstraintAcquire' and not reuse:
                row['admission']=admissible_theories(library,o,contract_checker(library['spec'],public[key],grading),timeout_seconds=90)
                nofit=evaluate_source({**library,'selected_rule_ids':library['suggested_rule_ids']},o,public[key],grading)
                row.update({'no_fit_execution':nofit['execution'],'no_fit_feedback':nofit['feedback']})
            else:row.update(evaluate_source(library,o,public[key],grading))
            if arm=='ConstraintAcquire' and reuse:
                nofit=evaluate_source({**library,'selected_rule_ids':library['suggested_rule_ids']},o,public[key],grading)
                row.update({'no_fit_execution':nofit['execution'],'no_fit_feedback':nofit['feedback']})
            immutable_json(dst,row);rows.append(row)
            print(json.dumps({'stage':stage,'arm':arm,'source':key,'logical_queries':o['execution']['planned_queries'],
                'rounds':len(o['execution']['planning_rounds']),'new_physical':o['execution']['new_physical_requests'],
                'native':[(v['view'],v['core_executed'],(v.get('score') or {}).get('correct')) for v in row.get('feedback',row.get('no_fit_feedback',{})).get('views',[])]}),flush=True)
        if not reuse:
            if arm=='ConstraintAcquire':
                observed_rows=[r for r in rows if r.get('status')!='observation_rejected']
                immutable_json(folder/arm/'learning_source_status.json',{
                    'fixed_sources':keys,'observed_sources':[r['source'] for r in observed_rows],
                    'rejected_sources':[r['source'] for r in rows if r.get('status')=='observation_rejected'],
                    'all_sources_remain_in_report_denominator':True,'no_default_legal_facts_or_retry':True})
                if not observed_rows:raise ValueError('No valid current observations to learn from')
                admissions=[r['admission'] for r in observed_rows];observations=[r['observation'] for r in observed_rows]
                immutable_json(folder/arm/'strict_diagnosis.json',diagnose_inputs(observations,admissions,'not_run'))
                if any(a['status']!='complete' for a in admissions):raise ValueError('Incomplete finite theory search; no pretend completion')
                learned,result=fit(library,[attach_scored_theories(o,a) for o,a in zip(observations,admissions)],timeout_seconds=90)
                immutable_json(folder/arm/'fit.json',result)
                if result['status']!='sat':raise ValueError('No source-consistent current composition; diagnose exact result')
                for row in observed_rows:
                    key=row['source'];grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[key]
                    immutable_json(folder/arm/'fitted_execution'/(key.replace(':','_')+'.json'),evaluate_source(learned,row['observation'],public[key],grading))
            else:learned=library
            immutable_json(folder/arm/'learned.json',learned)
    if not reuse:
        immutable_json(folder/'library_freeze.json',{'libraries':{a:digest(read(folder/a/'learned.json')) for a in ARMS},
            'reuse_sources':p['reuse_sources'],'reuse_annotations_not_used_in_learning':True,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','teacher-preflight','acquire','train','reuse']);parser.add_argument('--arm',choices=ARMS);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='prepare':prepare()
        elif args.phase=='teacher-preflight':teacher_request(args.arm)
        elif args.phase=='acquire':acquire(args.arm)
        else:run_stage(reuse=args.phase=='reuse')
