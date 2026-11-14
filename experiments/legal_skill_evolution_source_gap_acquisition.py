"""Incremental source acquisition from the fixed eight actual TRAIN failures.

Same Goal, libraries, data, models and continuous ledger. Complete source modules
replace redundant old helpers; composition/consumer edits use current semantics.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import jsonschema

from experiments import legal_skill_evolution_scoped_atom_acquisition as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe,execute_source_program,fit
from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
from legal_skill_guard.skill_evolution.semantic_operations import prepare_queries
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.source_composition import statement_fingerprint
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,term_sort
from legal_skill_guard.skill_evolution.span_compiler import execute_json,validate_procedure,METHODS,CALLS
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,unpack_programs,INSTRUCTION,PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues,render_structured_codex_prompt,CODEX_TURN_INPUT_CHARACTER_LIMIT

ROOT=previous.ROOT
RUN='legal_skill_evolution_source_gap_20261114'
OUT=ROOT/'artifacts'/RUN
ARMS=previous.ARMS
read=previous.read
name_for=previous.name_for
C_SCHEMA=deepcopy(previous.prior.prior.SCHEMA)
del C_SCHEMA['properties']['source_functions'];C_SCHEMA['required'].remove('source_functions')
C_SCHEMA['properties']['source_program']={'type':'string'};C_SCHEMA['required'].append('source_program')
FREE_SCHEMA=deepcopy(C_SCHEMA)
del FREE_SCHEMA['properties']['composition'];FREE_SCHEMA['required'].remove('composition')
FREE_SCHEMA['properties']['composition_functions']={'type':'array','items':{'type':'string'}}
FREE_SCHEMA['required'].append('composition_functions')

COMMON=r'''One actual incremental acquisition on the SAME fixed8 original TRAIN
mothers in the supplied task. Same Goal, models/weights, data and ledger. Both
arms see the same full sources, lawful native TRAIN supervision, current actual
libraries, real outputs, exact current-G diagnosis and partial source reviews.
No new source, synthetic example, DEV/TEST, seed/sampling change or full training.
No now-scored2 frozen-reuse text/feedback is supplied as a repair task; existing
library/example exposure from earlier TRAIN remains disclosed and unchanged.

C currently scores15/32 on these eight. Exact current-G fitting remains15/32;
every mother individually has the same best reachable score as its actual score.
Thus adding more selection search to unchanged concepts cannot solve this loss.
Current-G rules do not use reader facts at all: four ACTUAL executions preserve
all legal Norms and consumer decisions when all reader facts are removed. Do
not retain expensive neural queries whose answers cannot affect your program.
The correct next update is missing source concepts, relations and a legitimate
residual channel, not the same broad field questions or guessed native labels.

Specific actual source gaps, not desired answers:
- 6fce separately says return on request OR destroy ten business days after
  Project end, and elsewhere return on Agreement end/request. It qualifies
  backup/archival copies and a SINGLE legal-department copy for dispute purposes
  with continuing confidentiality. Preserve each action's own trigger/material,
  qualifiers, timing and exception scope. Do not flatten to one event/profile.
- 8fb says If requested return any/all materials. Do not add Agreement end to
  fit its native annotation. Its elliptical permission sentence must remain as
  written; preserve unresolved interpretation instead of supplying missing words.
- a5b0 has no currently acquired operative Norm. Parser failure is not proof of
  absence. Missing/unread/unknown cannot become False or a default NotMentioned.
  You may acquire a genuinely supported complete-source absence judgment or use
  a declared residual/unknown path. Not all sources must have zero fallback.
- Other full sources and actual failures are supplied. Acquire role, condition,
  action, material and exception distinctions where actually stated. A complete
  program can be learned; do not repeatedly ask the weak8B to do source scope
  composition that your executable G/program should perform.

Use typed source-local atoms and actual source references/condition connections
where needed. Reuse valid prior semantics and the lawful negative/residual path;
do not erase prior capabilities by replacing every rule with positive-only G.
Keep claims current-source conditioned, never global law. No source/company-ID
branches, native-answer operation or native labels in the source program.
Source truth and native interpretation remain separate; native correctness does
not certify an omitted condition, changed role or invented event. Existing source
reviews are partial; unreviewed assertions are not false. Residual errors remain
in denominators and do not make a zero-error installation gate.

source_program is a COMPLETE SELF-CONTAINED pure module, not a delta. It runs
BEFORE neural queries. Define apply(inputs,premises), helpers as needed, with
inputs={source_text,source_spans:[{id,text}],source_output:<common upstream>},
premises={}; return exactly {statements:[{term,support_ids:[current IDs]}],
complete:bool,unresolved:[str]}. No imports, nested functions, lambdas, network or
files. re and the supplied allowed pure Python calls are available. Define any
other helper you use. BOTH OLD INHERITED source programs (before the newly
acquired atom extractors) on all12 mothers were verified equal to the incoming
common source_output. The current libraries additionally contain real learned
atom-extraction functions; reuse their valid logic. You can directly reuse the
incoming result without copying the redundant inherited helpers and wrappers.
Preserve valid incoming statements; replace a false incoming claim only when the
actual current source justifies the correction. Do not delete valid old roots to
manufacture a mechanism gain. Current clauses/actors/numbers are parsed data,
not hard-coded source keys or ungrounded rule constants.

The actual observer/encoder code and signatures are supplied. No host-added
source_disposal_backend marker is added in this run. Any coverage metadata must
come from your actual source program, is not a legal fact, and must not certify
source absence merely because your patterns did not match. No function/field
aliases are inferred. planner_functions add/replace actual previous pure
functions: apply(inputs,premises) returns ONLY {queries:[{id,operation,unit_ids}]},
inputs={phase:'plan',source_text,source_spans,source_output,semantic_answers}.
The host repeats until no new IDs; no ID churn or same unknown retries. Use []
queries when the acquired code already suffices. operations declares actual
questions/choices/examples; each reading_contract declares its exact scope and
complete_source_absence_choices. Only a meaning explicitly assessing absence on
ALL current units may declare such a choice. Other definite reads need evidence.
Examples must be contiguous verbatim TRAIN, no ellipses or invented bridges.

new_constructors declares ONLY genuinely new names absent from the actual
current spec. Keep existing meanings. decision_functions add/replace current
consumer helpers; original native scorer/type/provenance checks remain. Do not
redeclare existing controlled_entities_of/action_conjunction/etc. All constructor
arity tests must match 1+declared argument count; the previous6-field connector
branch had erroneously required>=7 and is already repaired in the supplied Free
library. Keep pure functions compact and schema-consistent.

No U transfer claim: U real phi/G dictionary remains empty. Explain the actual
source/representation change and its limit, rather than promising gains.
'''
C_PART=r'''Your source_program acquires current source ATOMS/primitives to be
composed in G. Existing upstream Norms may be preserved; do not bypass G by
producing new complete policy Norms in this source stage. G must actually bind
conditions/actions/material/exception scopes where required. Use meaningful
candidate alternatives, not one opaque switch per complete module, and do not
intentionally weaken suggested_rule_ids. New variables read from term_scalar
have nominal sort scalar, not text; source constructor arguments can still be
text and are runtime checked. text is used by source_text/unit_text. Every output
argument must be used in its template or provenance; omit join-only variables
from the head. Static constants are declared under the correct nominal sort.
'''
FREE_PART=r'''Acquire the strongest ordinary source/program update. You have
identical raw data, source/planner/neural/constructor/consumer capabilities,
all supplied prior libraries, and may use pure code, neural concepts, arbitrary
pure decomposition and source-conditioned repair. Your source_program may emit
typed policy Norms directly, or atoms consumed by ordinary composition. No forced
weak lexical gate or capacity restriction. composition_functions adds/replaces
complete pure functions in your actual current Free composition_program. You can
replace all functions or define a simple forwarding composition if your source
program already constructs faithful Norms. Return renderers_json='[]' and
suggested_rule_ids=[]. This is independent incremental acquisition from common
information, not merely replaying the newly generated C result.
'''


def offline():
    before=previous.prior.rows();assert not any(r[6]=='reserved' for r in before)
    packet=read(previous.OUT/'next_acquisition_diagnosis.json');public={s['key']:s for s in read(previous.prior.prior.PUBLIC)}
    libraries={'ConstraintAcquire':read(previous.OUT/'execution/ConstraintAcquire/learned.json'),
               'FreeUpdate':read(previous.OUT/'arity_repair/FreeUpdate/library.json')}
    tasks=[];checks=[]
    for arm,lib in libraries.items():immutable_json(OUT/'previous'/arm/'library.json',lib)
    for task in packet['tasks']:
        key=task['source_id'];pub,units,up=previous.prior.prior.source_material(previous.PARENT,public,key)
        immutable_json(OUT/'upstream'/name_for(key),{'source_output':up})
        before_outputs={}
        for arm,lib in libraries.items():
            source_out=execute_json(lib['source_program'],{'source_text':pub['source_text'],'source_spans':units,'source_output':up},{},allow_helpers=True)
            inherited=read(previous.OUT/'previous'/arm/'library.json')
            inherited_out=execute_json(inherited['source_program'],{'source_text':pub['source_text'],'source_spans':units,'source_output':up},{},allow_helpers=True)
            assert inherited_out==up
            row=read(previous.OUT/'offline_remaining_TRAIN/sources'/arm/name_for(key))
            history_path=OUT/'history'/arm/name_for(key)
            if history_path.exists():
                saved=read(history_path);assert saved['observation']==row['observation']
                actual=saved['actual']
            else:
                actual=previous.prior.prior.evaluate_source(lib,row['observation'],public[key],task['native_TRAIN_supervision'])
                immutable_json(history_path,{'source':key,'observation':row['observation'],'actual':actual})
            paid=read(previous.PARENT/'history'/arm/name_for(key))
            immutable_json(OUT/'paid_reading_history'/arm/name_for(key),{'source':key,'observation':paid['observation']})
            before_outputs[arm]={'source_output':source_out,'actual_composed_output':actual['execution']['source_output'],
                                'native_feedback':actual['feedback']}
            checks.append({'arm':arm,'source':key,'incoming_source_output_exactly_equals_old_inherited_source_program':True,
                'current_acquired_source_atoms_retained_in_before_output':True})
        tasks.append({'source_id':key,'full_source_text':pub['source_text'],'source_units':units,
                      'incoming_source_output':up,'native_TRAIN_supervision':task['native_TRAIN_supervision'],
                      'actual_before':before_outputs,'current_C_actual_correct':task['current_C_actual_correct'],
                      'current_C_best_reachable_correct':task['current_C_best_reachable_correct']})
    task={'tasks':tasks,'actual_current_libraries_both_available':libraries,
        'common_observed_signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
        'encoder_code':(ROOT/'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'observer_code':(ROOT/'legal_skill_guard/skill_evolution/open_acquisition.py').read_text(),
        'partial_source_diagnosis':packet['specific_scope'],'same_information_and_full_program_capability':True,
        'frozen_reuse_is_not_a_repair_task':True,'U_real_phi_G_dictionary_empty':True}
    packed=pack_programs(task);assert unpack_programs(packed)==task
    immutable_json(OUT/'teacher_task.json',task)
    immutable_json(OUT/'offline_check.json',{'checks':checks,'task_transport_roundtrip_exact':True,
        'task_sha256':digest(task),'packed_characters':len(json.dumps(packed,ensure_ascii=False,separators=(',',':'))),
        'new_model_requests':0,'previous_ledger_rows_unchanged':len(before)})
    immutable_json(OUT/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before})
    assert previous.prior.rows()==before
    print(json.dumps({'offline_checks':len(checks),'new_model_requests':0,'packed_chars':read(OUT/'offline_check.json')['packed_characters']}),flush=True)


def setup():
    if not (OUT/'protocol.json').exists():
        task=read(OUT/'teacher_task.json');pp=read(previous.OUT/'protocol.json')
        files=[Path(__file__),ROOT/'tests/test_skill_evolution_source_gap_protocol.py',
               *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))]
        data=[OUT/'teacher_task.json',OUT/'offline_check.json',previous.prior.prior.PUBLIC,previous.prior.prior.GRADING,
              *sorted((OUT/'previous').glob('*/*.json')),*sorted((OUT/'upstream').glob('*.json')),*sorted((OUT/'history').glob('*/*.json')),
              *sorted((OUT/'paid_reading_history').glob('*/*.json'))]
        p={'run_id':RUN,'same_goal':True,'goal_complete':False,'acquisition_sources':[t['source_id'] for t in task['tasks']],
            'reuse_sources':[],'no_frozen_reuse_repair':True,'no_new_full_training_DEV_TEST_or_paper':True,
            'source_program_mode':'complete_replacement_both_arms','executor_profile':pp['executor_profile'],'teacher_profile':pp['teacher_profile'],
            'teacher_dispatch':'serial','automatic_retries':0,'U_dictionary':[],
            'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            'data_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
        for f in files:
            dst=OUT/'source_snapshot'/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(f.read_bytes())
        immutable_json(OUT/'protocol.json',p)
    p=read(OUT/'protocol.json')
    for name,value in {**p['source_sha256'],**p['data_sha256']}.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,name
    ledger=EvolutionLedger(previous.prior.prior.LEDGER,run_id=RUN,sources={'train':p['acquisition_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger,{s['key']:s for s in read(previous.prior.prior.PUBLIC)}


def request(arm):
    p,ledger,_=setup();task=read(OUT/'teacher_task.json')
    system=COMMON+'\n'+(C_PART+'\n'+previous.prior.prior.C_SPEC if arm=='ConstraintAcquire' else FREE_PART)
    system+='\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION+'\nAllowed pure attributes:'+','.join(sorted(METHODS))+'\nAllowed pure calls:'+','.join(sorted(CALLS))
    user=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':'));schema=C_SCHEMA if arm=='ConstraintAcquire' else FREE_SCHEMA
    issues=strict_output_schema_issues(schema);size=len(render_structured_codex_prompt(system,user))
    immutable_json(OUT/arm/'preflight.json',{'schema_issues':issues,'request_characters':size,'task_sha256':digest(task),'new_model_requests':0})
    if issues or size>CODEX_TURN_INPUT_CHARACTER_LIMIT:raise ValueError('Fix schema/full transport offline before dispatch')
    return p,ledger,{'source_ids':p['acquisition_sources'],'system_prompt':system,'user_prompt':user,'output_schema':schema}


def acquire():
    for arm in ARMS:
        if (OUT/arm/'teacher.json').exists():continue
        p,ledger,args=request(arm)
        result=FrozenTeacher(ledger,OUT,p['teacher_profile']).propose(RUN+':'+arm+':teacher',**args)
        immutable_json(OUT/arm/'teacher.json',result);print(json.dumps({'arm':arm,'paid_incremental_source_update_saved':True}),flush=True)


def compile_raw(old,raw,arm,public):
    jsonschema.validate(raw,C_SCHEMA if arm=='ConstraintAcquire' else FREE_SCHEMA)
    validate_procedure(raw['source_program'],allow_helpers=True)
    parts=previous.prior.prior.functions([raw['source_program']]);proposal={k:deepcopy(v) for k,v in raw.items() if k not in ('source_program','composition_functions')}
    proposal['scope']='window';proposal['source_functions']=parts
    if arm=='FreeUpdate':proposal['composition']=function_update(old['composition_program'],previous.prior.prior.functions(raw['composition_functions']))
    # Existing original TRAIN examples are validated without new model input.
    lib,receipt=compile_proposal(old,proposal,arm,public,source_functions=parts)
    lib['source_program']=raw['source_program']
    lib['source_program_update']={'previous_program_sha256':digest(old['source_program']),'program_sha256':digest(raw['source_program']),
        'mode':'complete_replacement','original_and_new_programs_retained':True,'structural_change_is_not_method_credit':True}
    return lib,receipt,proposal


def compile_all():
    p,_,public=setup()
    for arm in ARMS:
        if (OUT/arm/'compiled.json').exists():continue
        old=read(OUT/'previous'/arm/'library.json');raw=read(OUT/arm/'teacher.json')['value']
        lib,receipt,proposal=compile_raw(old,raw,arm,public)
        checks=[]
        for key in p['acquisition_sources']:
            pub,units,_=previous.prior.prior.source_material(previous.PARENT,public,key);up=read(OUT/'upstream'/name_for(key))['source_output']
            output,trace=execute_source_program(lib['source_program'],lib['spec'],source_text=pub['source_text'],units=units,source_output=up)
            if arm=='ConstraintAcquire':
                old_norms={statement_fingerprint(r) for r in up['statements'] if term_sort(r['term'],constructors(lib['spec']))=='Norm'}
                assert all(term_sort(r['term'],constructors(lib['spec']))!='Norm' or statement_fingerprint(r) in old_norms for r in output['statements']), 'C source atoms must be composed into new Norms by G'
            plan=prepare_queries(lib['planner_program'],lib['operations'],pub['source_text'],units,answers=[],source_output=output)
            checks.append({'source':key,'actual_source_output':output,'source_trace':trace,'initial_plan':plan})
        immutable_json(OUT/arm/'canonical_proposal.json',proposal);immutable_json(OUT/arm/'compiled.json',lib)
        immutable_json(OUT/arm/'compilation_receipt.json',receipt);immutable_json(OUT/arm/'offline_actual_source_check.json',{'checks':checks,'new_model_requests':0})
        print(json.dumps({'arm':arm,'compiled':True,'source_functions':len(ast.parse(lib['source_program']).body),'operations':len(lib['operations'])}),flush=True)


def train():
    p,ledger,public=setup();grading=read(previous.prior.prior.GRADING)
    for arm in ARMS:
        lib=read(OUT/arm/'compiled.json');client=FrozenExecutor(ledger,OUT,p['executor_profile'])
        client.exact_replay_roots=(previous.OUT,previous.OUT/'frozen_reuse',previous.PARENT,previous.prior.FIELD_PARENT,previous.prior.PARENT)
        # Deterministic preflight must reject known dead reader work before dispatch.
        if arm=='ConstraintAcquire':
            reading={'reader_query','query_window','query_focus','reader_observed_value','query_choice','query_unknown','query_unread','evidence_unit','evidence_quote',
                     'json_root','json_kind','json_entry','json_item','json_scalar'}
            needs_reading=any(a['predicate'] in reading for rule in lib['language']['rules'] for a in rule['body'])
            plans=read(OUT/arm/'offline_actual_source_check.json')['checks']
            if not needs_reading and any(x['initial_plan'] for x in plans):raise ValueError('Offline preflight: G ignores reader/JSON facts but planner issues queries; fix the actual planner before any physical request')
        for key in p['acquisition_sources']:
            dst=OUT/'acquisition'/arm/name_for(key)
            if dst.exists():continue
            pub,units,_=previous.prior.prior.source_material(previous.PARENT,public,key);up=read(OUT/'upstream'/name_for(key))['source_output']
            history=[read(OUT/'history'/a/name_for(key))['observation'] for a in ARMS]
            history += [read(OUT/'paid_reading_history'/a/name_for(key))['observation'] for a in ARMS]
            o=observe(client,RUN+':'+arm+':'+key,key,lib,source_text=pub['source_text'],units=units,source_output=up,
                previous_observations=history,save_event=lambda event:immutable_json(OUT/arm/'events'/(digest(event['call_id'])+'.json'),event))
            immutable_json(OUT/arm/'observations'/name_for(key),o)
            direct=deepcopy(lib)
            if arm=='ConstraintAcquire':direct['selected_rule_ids']=lib['suggested_rule_ids']
            actual=previous.prior.prior.evaluate_source(direct,o,public[key],grading[key]);record={'source':key,'observation':o,'direct':actual}
            if arm=='ConstraintAcquire':
                profile=admissible_projected_compositions(lib,o,previous.prior.prior.checker(lib,public[key],grading[key]),timeout_seconds=90)
                immutable_json(OUT/arm/'profiles'/name_for(key),profile)
                if profile['status']!='complete':raise ValueError('Actual outputs saved; repair deterministic admission before more calls')
                record['profile']=profile
            immutable_json(dst,record);print(json.dumps({'arm':arm,'source':key,'correct':sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                'new_requests':o['execution']['new_physical_requests']}),flush=True)
    lib=read(OUT/'ConstraintAcquire/compiled.json');records=[read(OUT/'acquisition/ConstraintAcquire'/name_for(k)) for k in p['acquisition_sources']]
    learned,result=fit(lib,[previous.prior.prior.attach_scored_theories(r['observation'],r['profile']) for r in records],
        prior_rule_ids=lib['suggested_rule_ids'],timeout_seconds=90)
    immutable_json(OUT/'ConstraintAcquire/fit.json',result)
    if result['status']=='sat':
        immutable_json(OUT/'ConstraintAcquire/learned.json',learned)
        for r in records:
            key=r['source'];immutable_json(OUT/'ConstraintAcquire/fitted_execution'/name_for(key),previous.prior.prior.evaluate_source(learned,r['observation'],public[key],grading[key]))
    immutable_json(OUT/'FINITE_TRAIN_COMPLETE.json',{'same_goal':True,'goal_complete':False,'G_fit_status':result['status'],'U_dictionary':[]})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['offline','preflight','acquire','compile','train']);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='offline':offline()
        elif args.phase=='preflight':
            for arm in ARMS:request(arm)
        elif args.phase=='acquire':acquire()
        elif args.phase=='compile':compile_all()
        else:train()
