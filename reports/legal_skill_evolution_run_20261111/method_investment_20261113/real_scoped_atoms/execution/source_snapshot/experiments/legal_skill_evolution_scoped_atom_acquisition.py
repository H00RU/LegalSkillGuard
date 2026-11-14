"""Local program-concept acquisition for actual source-scope failures.

Same Goal and original TRAIN. Strong ordinary-program acquisition shares all
inputs and the routing/format infrastructure. This is not a new training run.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_field_binding_acquisition as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import CONSTRUCTOR
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations, signatures
from legal_skill_guard.skill_evolution.open_acquisition import observe, execute_source_program, fit
from legal_skill_guard.skill_evolution.open_acquisition import statement_fingerprint
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort
from legal_skill_guard.skill_evolution.span_compiler import execute_json,validate_procedure
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,unpack_programs,INSTRUCTION,PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues,render_structured_codex_prompt,CODEX_TURN_INPUT_CHARACTER_LIMIT

ROOT=prior.ROOT
PARENT=prior.OUT
RUN='legal_skill_evolution_scoped_atoms_typed_20261114'
OUT=ROOT/'artifacts/legal_skill_evolution_scoped_atoms_20261114'
ARMS=prior.ARMS
read=prior.read
name_for=prior.name_for
SCOPE_MARKER={'name':'source_program_scope_supported','sort':'Description','arguments':['text'],
 'meaning':'The learned atom extractor supports this current disposal scope; support_ids identify its actual source units. This is computational coverage metadata, not a legal conclusion or full-document completeness.'}
MODE_MARKER={'name':'source_disposal_backend','sort':'Description','arguments':['text'],
 'meaning':'The actual observer selected program or neural residual handling after comparing current locator anchors to supported source scopes; not legal evidence.'}
CONTROL={
 'ConstraintAcquire':{'locator':'locate_disposal_windows_v2','blocked':['disposal_action_connection_v2','return_trigger_v2','destroy_trigger_v2','return_material_scope_v2','destroy_material_scope_v2']},
 'FreeUpdate':{'locator':'positive_disposal_locator_v2','blocked':['disposal_action_connection_v2','return_trigger_binding_v1','destroy_trigger_binding_v1','return_material_scope_v1','destroy_material_scope_v1']}}
FIELDS={'rationale':{'type':'string'},'atom_functions':{'type':'array','items':{'type':'string'}},
 'new_constructors':{'type':'array','items':CONSTRUCTOR},'decision_functions':{'type':'array','items':{'type':'string'}}}
C_SCHEMA=record_schema({**FIELDS,'composition':{'type':'string'},'renderers_json':{'type':'string'},
 'suggested_rule_ids':{'type':'array','items':{'type':'string'}}})
FREE_SCHEMA=record_schema({**FIELDS,'composition_functions':{'type':'array','items':{'type':'string'}}})

COMMON=r'''One local update within the SAME original TRAIN and chosen C/U method.
The current source input is sufficient. Both factual field decomposition and
explicit target focus were actually tried; they did not fix destruction-trigger
and material errors. The model is being asked to perform COMPOSITION in fields
such as "trigger of destroy" rather than extract the condition in its actual
header and let the executable composition attach it to the child action.
C currently has four whole-module rules, so its finite selector cannot repair
these actual readings (optimistic maximum5/8 on the fixed two TRAIN mothers).
The source-scope compiler itself is ordinary infrastructure, NOT a new research
claim. Do not resurrect the old deterministic scope-restorer as an innovation.
We test acquisition and faithful use, not the existence of a parser or new IR.

Acquire executable SOURCE-LOCAL ATOMS and their actual composition. Use the
actual sources, previous programs and failures supplied. Prefer a compact pure
program for explicit clause headers, actions, material heads, connectors and
source-defined references. Preserve source clause identity and actual parent/
child structure rather than label an entire mixed window once. Clause numbers
are current-source data, never hard-coded guards. In e82b the request condition
is in the header, and return/destroy have different material scopes; in4607
an authorization qualifies destruction as an alternative. Preserve AND versus
OR, authorization, request versus end events, copy ownership and unresolved
qualifiers. Do not copy return materials into destroy, infer an end event from
"destroy", or turn an unread exception into no_exception. Unknown remains
unresolved. No synthetic example, source/company-ID branch, native-answer
classifier or label in source atoms. Raw current text stays available.

This updates the actual previous library, not a reset. Both independently
acquire from the same full sources, lawful feedback, supplied past libraries
and local failure records. The ordinary Free arm may use the same atom route,
strong raw parsing and all previous helpers. It is not restricted to weak
lexical gates or a shallow patch. Complete program expressivity is preserved.
No already scored4-mother reuse material/labels/postscore feedback is supplied.
No new source, seed, sampling configuration or full training/DEV/TEST/paper.

Return atom_functions: complete NEW pure functions, including entry
acquire_atoms(inputs,premises). They execute AFTER the unchanged old source
program in one assembled pure module, so its helpers remain available. Inputs
are {source_text,source_spans:[{id,text}],source_output:<actual old source result>},
premises={}. Return exactly {statements:[{term:<typed SOURCE ATOM>,support_ids:
[current unit IDs]}],complete:bool,unresolved:[string]}. Do not return native
answers or already assembled disposal Norms from acquire_atoms. New root atoms
must be descriptions/structured primitive facts for composition. Name helper
functions atoms_*. Existing source helpers may be reused when semantically
correct, not when they collapse the distinction being repaired. No imports,
network, files, nested functions or lambdas. Do not assume offset fields or
dense IDs. Any current numeric clause labels are parsed from current text.

Two shared computational Description constructors are already installed:
source_program_scope_supported(scope_key:text), with support_ids covering the
actual units of a disposal scope whose needed condition/action/material atoms
are supported by your parser; and source_disposal_backend('program'|'neural'),
added by the observer. They are NOT legal facts. Do not redeclare them.
The common router keeps the exact previous queries until the actual disposal
locator returns anchors. If every such anchor is covered by your supported
scopes, it omits only the five old action/trigger/material classifier operations;
it retains the old retention questions and every disclosure question unchanged.
Otherwise the old neural route remains. The observer records the real route.
Your composition can use actual retained retention observations; do not fill
unasked fields or treat the backend marker as a legal proof.

All operations and reading contracts remain unchanged in this local update.
The old source program's outputs remain; atoms are appended. decision_functions
replace/add complete functions in your actual old consumer. A handled answer
still needs actual typed legal source roots. Preserve valid old abilities,
never use nonoperative bundles, metadata or a default answer as core evidence.
Unknown/missing rules do not become False. Explain actual new knowledge and
unresolved scope; no claims of U transfer or overall Goal completion.
'''


def entry_alias(program,name):
    tree=ast.parse(program)
    assert not any(isinstance(n,ast.FunctionDef) and n.name==name for n in tree.body)
    entry=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='apply')
    assert not any(isinstance(n,ast.Name) and n.id=='apply' and isinstance(n.ctx,ast.Load) for n in ast.walk(entry))
    alias=deepcopy(entry);alias.name=name;tree.body.append(alias);ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def append_atoms(previous,functions):
    modules=prior.prior.functions(functions)
    names={n.name for text in modules for n in ast.parse(text).body}
    old_names={n.name for n in ast.parse(previous).body}
    assert 'acquire_atoms' in names and not names & old_names
    base=entry_alias(previous,'_scope_previous_source')
    wrapper="""def apply(inputs,premises):
    old=_scope_previous_source(inputs,premises)
    extra=acquire_atoms({'source_text':inputs['source_text'],'source_spans':inputs['source_spans'],'source_output':old},premises)
    return {'statements':old['statements']+extra['statements'],
        'complete':old['complete'] and extra['complete'],
        'unresolved':old['unresolved']+extra['unresolved']}
"""
    result=function_update(base,modules+[wrapper]);validate_procedure(result,allow_helpers=True)
    return result


def routed_plan(previous,control):
    base=entry_alias(previous,'_scope_previous_plan')
    wrapper="""def apply(inputs,premises):
    plan=_scope_previous_plan(inputs,premises)
    supported=set()
    for row in inputs.get('source_output',{}).get('statements',[]):
        if row['term'][0]=='source_program_scope_supported':
            for uid in row['support_ids']:
                supported.add(uid)
    anchors=[]
    for answer in inputs.get('semantic_answers',[]):
        if answer.get('operation')==LOCATOR and answer.get('choice')=='candidate_found':
            for evidence in answer.get('evidence',[]):
                anchors.append(evidence['unit_id'])
    if anchors and all(uid in supported for uid in anchors):
        plan['queries']=[q for q in plan['queries'] if q['operation'] not in BLOCKED]
    return plan
""".replace('LOCATOR',repr(control['locator'])).replace('BLOCKED',repr(control['blocked']))
    return function_update(base,[wrapper])


def actual_record(key,arm):
    row=read(PARENT/'acquisition'/arm/name_for(key))
    executed=row['NoFit'] if arm=='ConstraintAcquire' else row
    return {'source':key,'observation':row['observation'],'execution':executed['execution'],'feedback':executed['feedback']}


def offline():
    before=prior.rows();assert not any(r[6]=='reserved' for r in before)
    pp=read(PARENT/'protocol.json');keys=[pp['acquisition_sources'][-4],pp['acquisition_sources'][-1]]
    public={s['key']:s for s in read(prior.prior.PUBLIC)};grading=read(prior.prior.GRADING)
    libraries={a:read(PARENT/a/'compiled.json') for a in ARMS}
    for a,lib in libraries.items():
        lib=deepcopy(lib);lib['spec']['constructors']+=deepcopy([SCOPE_MARKER,MODE_MARKER])
        if a=='FreeUpdate':lib['composition_program']=entry_alias(lib['composition_program'],'previous_compose')
        immutable_json(OUT/'previous'/a/'library.json',lib)
    tasks=[]
    for key in keys:
        actual={}
        for arm in ARMS:
            row=actual_record(key,arm);immutable_json(OUT/'history'/arm/name_for(key),row)
            actual[arm]={'visible_inputs':row['observation']['visible_inputs'],'native_feedback':row['feedback']}
        tasks.append({'source':public[key],'native_TRAIN_supervision':grading[key],'actual_previous':actual})
    probe=read(ROOT/'artifacts/legal_skill_evolution_field_scope_probe_20261114/result.json')
    task={'tasks':tasks,'actual_previous_libraries_both_available':{a:read(OUT/'previous'/a/'library.json') for a in ARMS},
        'shared_router_control':CONTROL,'common_observed_signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
        'fact_encoder_source':(ROOT/'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'actual_field_scope_probe':probe,'current_C_space_bound':read(PARENT/'unbound_C_probe_current_space_bounds.json'),
        'same_raw_sources_supervision_and_history':True,'no_prior4_reuse_material':True,
        'old_deterministic_source_scope_assets_are_infrastructure_not_new_contributions':True}
    text=json.dumps(task,ensure_ascii=False)
    previous4=read(prior.PARENT/'protocol.json')['reuse_sources'];assert not any(k in text for k in previous4)
    packed=pack_programs(task);assert unpack_programs(packed)==task
    immutable_json(OUT/'teacher_task.json',task)
    # A real before/after identity check for the source append codec and alias.
    stub=["def acquire_atoms(inputs,premises):\n    return {'statements':[],'complete':True,'unresolved':[]}\n"]
    checks=[]
    for arm in ARMS:
        old=read(OUT/'previous'/arm/'library.json');program=append_atoms(old['source_program'],stub)
        for key in pp['acquisition_sources']:
            pub,units,up=prior.prior.source_material(PARENT,public,key)
            inputs={'source_text':pub['source_text'],'source_spans':units,'source_output':up}
            direct=execute_json(old['source_program'],inputs,{},allow_helpers=True)
            appended=execute_json(program,inputs,{},allow_helpers=True);assert direct==appended
            plan_inputs={'source_text':pub['source_text'],'source_spans':units,'source_output':direct,'semantic_answers':[]}
            before_plan=execute_json(old['planner_program'],plan_inputs,{},allow_helpers=True)
            after_plan=execute_json(routed_plan(old['planner_program'],CONTROL[arm]),plan_inputs,{},allow_helpers=True)
            assert before_plan==after_plan
            checks.append({'arm':arm,'source':key,'old_source_output_and_unactivated_plan_exact':True})
    assert before==prior.rows()
    immutable_json(OUT/'offline_check.json',{'checks':checks,'task_transport_roundtrip_exact':True,
        'task_sha256':digest(task),'packed_characters':len(json.dumps(packed,ensure_ascii=False,separators=(',',':'))),
        'old_rows_unchanged':len(before),'new_model_requests':0})
    immutable_json(OUT/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before})
    print(json.dumps({'checks':len(checks),'packed_characters':read(OUT/'offline_check.json')['packed_characters'],'new_model_requests':0}),flush=True)


def setup():
    if not (OUT/'protocol.json').exists():
        pp=read(PARENT/'protocol.json');task=read(OUT/'teacher_task.json');proof=read(OUT/'offline_check.json')
        files=[Path(__file__),Path(prior.__file__),Path(prior.prior.__file__),
               ROOT/'experiments/legal_skill_evolution_open_acquisition_train.py',
               ROOT/'experiments/legal_skill_evolution_diagnosed_update_train.py',
               *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))]
        data=[OUT/'teacher_task.json',OUT/'offline_check.json',*sorted((OUT/'previous').glob('*/*.json')),
              *sorted((OUT/'history').glob('*/*.json')),prior.prior.PUBLIC,prior.prior.GRADING,
              PARENT/'base.json',PARENT/'grammar.json',PARENT/'shared/initial_library.json',
              *sorted((PARENT/'upstream').glob('*.json')),*sorted((PARENT/'shared_source_outputs').glob('*.json'))]
        p={'run_id':RUN,'same_goal':True,'goal_complete':False,'parent_run':PARENT.name,
           'sources':[t['source']['key'] for t in task['tasks']],
           'executor_profile':pp['executor_profile'],'teacher_profile':pp['teacher_profile'],
           'task_sha256':digest(task),'offline_proof_sha256':digest(proof),'teacher_dispatch':'serial','automatic_retries':0,
           'U_dictionary':[],'no_new_source_or_full_training_DEV_TEST_or_paper':True,
           'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
           'data_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
        for f in files:
            dst=OUT/'source_snapshot'/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(f.read_bytes())
        immutable_json(OUT/'protocol.json',p)
    p=read(OUT/'protocol.json')
    for name,value in {**p['source_sha256'],**p['data_sha256']}.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,name
    ledger=EvolutionLedger(prior.prior.LEDGER,run_id=RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger,{s['key']:s for s in read(prior.prior.PUBLIC)}


def request(arm):
    p,ledger,_=setup();task=read(OUT/'teacher_task.json')
    system=COMMON+'\n'+(prior.prior.C_SPEC if arm=='ConstraintAcquire' else
        "composition_functions add/replace complete pure functions in your actual previous composition_program. previous_compose(inputs,premises) preserves the old behavior. apply receives source_text,source_spans,source_output,semantic_answers; return typed statements,complete,unresolved. All raw source and atom routes remain available. No capacity restriction to a small patch.")
    system+='\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION+'\nAllowed pure attributes: '+','.join(sorted(prior.prior.METHODS))
    system+='\nAllowed pure calls: '+','.join(sorted(prior.prior.CALLS))
    user=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':'));schema=C_SCHEMA if arm=='ConstraintAcquire' else FREE_SCHEMA
    issues=strict_output_schema_issues(schema);size=len(render_structured_codex_prompt(system,user))
    immutable_json(OUT/arm/'preflight.json',{'schema_issues':issues,'input_characters':size,'task_sha256':digest(task),'new_model_requests':0})
    if issues or size>CODEX_TURN_INPUT_CHARACTER_LIMIT:raise ValueError('Fix full offline request before dispatch')
    return p,ledger,{'source_ids':p['sources'],'system_prompt':system,'user_prompt':user,'output_schema':schema}


def acquire():
    for arm in ARMS:
        if (OUT/arm/'teacher.json').exists():continue
        p,ledger,args=request(arm)
        result=FrozenTeacher(ledger,OUT,p['teacher_profile']).propose(RUN+':'+arm+':teacher',**args)
        immutable_json(OUT/arm/'teacher.json',result)
        print(json.dumps({'arm':arm,'paid_source_atom_update_saved':True}),flush=True)


def compile_all():
    p,_,public=setup()
    for arm in ARMS:
        if (OUT/arm/'compiled.json').exists():continue
        old=read(OUT/'previous'/arm/'library.json');patch=read(OUT/arm/'teacher.json')['value']
        source=append_atoms(old['source_program'],patch['atom_functions'])
        full={'rationale':patch['rationale'],'operations':old['operations'],'scope':'window',
            'reading_contracts':[{'operation':o['name'],'scope':old['operation_scopes'][o['name']],
               'complete_source_absence_choices':old['complete_source_absence_choices'].get(o['name'],[])} for o in old['operations']],
            'planner_functions':prior.prior.functions([routed_plan(old['planner_program'],CONTROL[arm])]),
            'source_functions':prior.prior.functions([source]),'new_constructors':patch['new_constructors'],
            'decision_functions':patch['decision_functions'],'renderers_json':patch.get('renderers_json','[]'),
            'suggested_rule_ids':patch.get('suggested_rule_ids',[]),
            'composition':patch['composition'] if arm=='ConstraintAcquire' else
                function_update(old['composition_program'],prior.prior.functions(patch['composition_functions']))}
        lib,receipt=compile_proposal(old,full,arm,{k:public[k] for k in p['sources']},source_functions=full['source_functions'])
        immutable_json(OUT/arm/'canonical_proposal.json',full);immutable_json(OUT/arm/'compiled.json',lib)
        immutable_json(OUT/arm/'compilation_receipt.json',receipt)
        print(json.dumps({'arm':arm,'compiled':True,'new_atom_functions':len(patch['atom_functions'])}),flush=True)


def annotate_backend(observation,arm):
    """Record routing from actual supported units/locator evidence, never labels."""
    v=observation['visible_inputs'];support=set();anchors=[]
    for row in v['source_output']['statements']:
        if row['term'][0]==SCOPE_MARKER['name']:support.update(row['support_ids'])
    for answer in v['answers']:
        if answer.get('operation')==CONTROL[arm]['locator'] and answer['choice']=='candidate_found':
            anchors.extend(e['unit_id'] for e in answer['evidence'])
    mode='program' if anchors and set(anchors)<=support else 'neural'
    if mode=='program':
        assert not any(q['operation'] in CONTROL[arm]['blocked'] for q in v['queries'])
    output=deepcopy(v['source_output'])
    output['statements'].append({'term':[MODE_MARKER['name'],mode],
        'support_ids':sorted(set(anchors)) or [u['id'] for u in v['units']]})
    encoded=encode_source_observations(observation['context']['id'],source_text=v['source_text'],units=v['units'],
        source_output=output,operations=v['operations'],queries=v['queries'],answers=v['answers'],scope=v['scope'],
        query_scopes=v['query_scopes'],complete_source_absence_choices=v.get('complete_source_absence_choices'))
    encoded['execution']=deepcopy(observation['execution'])
    trace=encoded['execution'].get('acquired_source_program')
    if trace is not None:
        trace['output_sha256']=digest(output)
        trace['statement_origins'][statement_fingerprint(output['statements'][-1])]='source_program_new_or_changed'
        trace['observer_added_computational_metadata_fingerprints']=[statement_fingerprint(output['statements'][-1])]
    encoded['execution']['disposal_backend']={'mode':mode,'locator_anchors':sorted(set(anchors)),
        'supported_units':sorted(support),'legal_fact':False,'program_output_before_metadata_sha256':digest(v['source_output'])}
    return encoded


def probe():
    p,ledger,public=setup();grading=read(prior.prior.GRADING)
    for arm in ARMS:
        lib=read(OUT/arm/'compiled.json');checks=[]
        # Check the actual acquired atoms before any additional executor request.
        for key in p['sources']:
            pub,units,up=prior.prior.source_material(PARENT,public,key)
            inputs={'source_text':pub['source_text'],'source_spans':units,'source_output':
                execute_json(read(OUT/'previous'/arm/'library.json')['source_program'],
                    {'source_text':pub['source_text'],'source_spans':units,'source_output':up},{},allow_helpers=True)}
            patch=read(OUT/arm/'teacher.json')['value']
            # Helpers of the unchanged old source module remain accessible as promised.
            atom_program=function_update(read(OUT/'previous'/arm/'library.json')['source_program'],
                prior.prior.functions(patch['atom_functions'])+['def apply(inputs,premises):\n    return acquire_atoms(inputs,premises)\n'])
            atoms=execute_json(atom_program,inputs,{},allow_helpers=True)
            for row in atoms['statements']:
                assert term_sort(row['term'],constructors(lib['spec']))!='Norm','Source atoms must be composed in G'
                assert set(row['support_ids'])<={u['id'] for u in units}
            output,trace=execute_source_program(lib['source_program'],lib['spec'],source_text=pub['source_text'],units=units,source_output=up)
            checks.append({'source':key,'atoms':atoms,'actual_source_execution':trace})
        immutable_json(OUT/arm/'offline_actual_atoms.json',{'checks':checks,'new_model_requests':0,
            'type_and_current_support_checks_are_not_semantic_certification':True})
        client=FrozenExecutor(ledger,OUT,p['executor_profile'])
        client.exact_replay_roots=(PARENT,prior.FIELD_PARENT,prior.PARENT,prior.prior.READING_PARENT)
        for key in p['sources']:
            dst=OUT/'acquisition'/arm/name_for(key)
            if dst.exists():continue
            pub,units,up=prior.prior.source_material(PARENT,public,key)
            histories=[read(OUT/'history'/a/name_for(key))['observation'] for a in ARMS]
            raw=observe(client,RUN+':'+arm+':'+key,key,lib,source_text=pub['source_text'],units=units,
                source_output=up,previous_observations=histories,
                save_event=lambda e:immutable_json(OUT/arm/'events'/(digest(e['call_id'])+'.json'),e))
            immutable_json(OUT/arm/'raw_observations'/name_for(key),raw)
            observation=annotate_backend(raw,arm)
            direct=deepcopy(lib)
            if arm=='ConstraintAcquire':direct['selected_rule_ids']=lib['suggested_rule_ids']
            actual=prior.prior.evaluate_source(direct,observation,public[key],grading[key])
            result={'source':key,'observation':observation,'direct':actual}
            if arm=='ConstraintAcquire':
                direct_bodies=all(lib['language']['signatures'][a['predicate']]['kind']=='observed'
                    for rule in lib['language']['rules'] for a in rule['body'])
                enum=prior.prior.admissible_theories if observation['context']['unknown_groups'] else \
                    prior.prior.admissible_direct_compositions if direct_bodies else prior.prior.admissible_program_compositions
                profile=enum(lib,observation,prior.prior.checker(lib,public[key],grading[key]),timeout_seconds=90)
                immutable_json(OUT/arm/'profiles'/name_for(key),profile)
                assert profile['status']=='complete','Actual observation saved; inspect deterministic fit before more calls'
                result['profile']=profile
            immutable_json(dst,result)
            print(json.dumps({'arm':arm,'source':key,'backend':observation['execution']['disposal_backend']['mode'],
                'physical':observation['execution']['new_physical_requests'],
                'correct':sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views'])}),flush=True)
    arm='ConstraintAcquire';lib=read(OUT/arm/'compiled.json')
    records=[read(OUT/'acquisition'/arm/name_for(k)) for k in p['sources']]
    lib,result=fit(lib,[prior.prior.attach_scored_theories(r['observation'],r['profile']) for r in records],
        prior_rule_ids=lib['suggested_rule_ids'],timeout_seconds=90)
    immutable_json(OUT/arm/'fit.json',result)
    if result['status']=='sat':
        immutable_json(OUT/arm/'learned.json',lib)
        for row in records:
            key=row['source'];immutable_json(OUT/arm/'fitted_execution'/name_for(key),
                prior.prior.evaluate_source(lib,row['observation'],public[key],grading[key]))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['offline','preflight','acquire','compile','probe']);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='offline':offline()
        elif args.phase=='preflight':
            for arm in ARMS:request(arm)
        elif args.phase=='acquire':acquire()
        elif args.phase=='compile':compile_all()
        else:probe()
