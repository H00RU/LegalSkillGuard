"""Fixed4/2 original-TRAIN MAUD source-rule acquisition, same active Goal."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.maud_source_feedback import evaluate_view,view_checker,view_units
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute_source_program,observe,fit
from legal_skill_guard.skill_evolution.program_composition_profiles import admissible_program_compositions
from legal_skill_guard.skill_evolution.source_observations import signatures,encode_source_observations
from legal_skill_guard.skill_evolution.span_compiler import METHODS,CALLS,execute_json
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories,attach_scored_theories
from legal_skill_guard.inference.codex_cli_client import (
    strict_output_schema_issues,render_structured_codex_prompt,CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_diagnosed_update_train import SCHEMA
from experiments.legal_skill_evolution_joint_acquisition_train import COMMON
from experiments.legal_skill_evolution_open_acquisition_train import C_SPEC,FREE_SPEC

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_MAUD_compact_20261114'
FOLDER=ROOT/'artifacts'/RUN
TEACHER_PARENT=ROOT/'artifacts/legal_skill_evolution_MAUD_rule_acquisition_20261114'
PARENT=ROOT/'artifacts/legal_skill_evolution_query_refinement_20261114'
SOURCE_ASSET=ROOT/'artifacts/legal_skill_evolution_source_functions_20261114/FreeUpdate/learned.json'
SELECTION=PARENT/'next_MAUD_fixed_selection.json'
PUBLIC=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING=PUBLIC.with_name('grading.json')
LEDGER=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
ARMS=('ConstraintAcquire','FreeUpdate')
read=lambda p:json.loads(p.read_text())
name_for=lambda key,view:digest({'source':key,'view':view['id']})+'.json'

DOMAIN=r'''This continuation is native MAUD source-rule learning. Each mother has
three ORIGINAL native views with DIFFERENT source materials. Each actual reader
and source_program invocation sees ONLY that view's source_text/source_spans and
shared incoming source_output, never its question, other views or their omitted
text. Do not import a definition, exception or subsection from another view of
the same mother. The four acquisition mothers/12 views and their lawful native
labels are supplied. The next2 original TRAIN mothers are fixed but withheld.
Their labels/materials are not available for this update.

The unchanged native questions classify knowledge definitions and identify
pandemic-response exceptions in ordinary/negative interim covenants. A strong
simple raw-text control already scores12/12 on these acquisition views; its
exact code and results are common to both arms. That control is NOT a source
oracle, learned C/U asset, or permitted reason to turn its native label into a
source fact. Do not manufacture G alternatives or a poor suggested_rule_ids to
make this easy control look weak. A real possibility is that the strong control
absorbs the effect; report this instead of inventing a distinct gain.

Learn actual source semantics: knowledge holders, an operative inquiry duty and
its matter scope/exclusions; covenant effects, applicable exceptions and their
source binding/references. Ordinary knowledge of a supplied clause and native
classification are distinct. Do not emit Yes/No/Actual knowledge/Constructive
knowledge, native-answer probes or a copy of the whole material as source roots.
Source code must not inspect a task/question ID. Do not use company/person IDs
as applicability gates. Do not add a missing rule or treat parser non-match or
unknown as a legal negative. Full-window neural absence judgments need the
explicit existing reading contract and actually supplied complete window.

source_functions adds/replaces COMPLETE pure functions in the shared actual
source_program. apply(inputs,premises) receives {source_text,source_spans:
[{id,text}],source_output:<actual shared initial output>}, premises={}. Return
exactly {statements:[{term:<typed constructor list>,support_ids:[current IDs]}],
complete:bool,unresolved:[string]}. Both architectures have this same executable
source-function capability. It runs BEFORE planning and G. All needed helpers
must be supplied; no imports, nested functions/lambda, file/network or reflection.
Use structural constructor sorts or text arguments, not undeclared nominal
scalar types. Each newly added constructor needs an explicit semantic meaning.

decision_functions updates the same actual typed consumer for both arms. It
receives inputs={task_id:<the native view ID>,question:<that view question>},
premises={nodes:[{id,term,sort,support_ids,child_ids,ambiguous,
source_semantics_verified}],roots:[current root IDs],complete:bool,unresolved:[]}.
Return exactly {handled:bool,answer:null|<exact current native label>,
used_nodes:[actual current root IDs]}. A handled answer needs a non-null valid
native label and at least one actual source-rule root. An incomplete theory is
not automatically negative. The native scorer is unchanged. Typed/provenance
checks are not source truth; preserve source scopes even when native labels
cannot distinguish them. Demonstrations may quote any INDIVIDUAL supplied view
of the declared TRAIN mother, never a concatenation of different views.

The old common raw-source program is a genuine paid acquired asset, available
equally. Its NDA-specific neural operations are not dispatched on this different
task family; their old library/results remain. There is no retained MAUD-specific
skill in the old Full/Free B8 libraries. Initial execution on these12 materials is
recorded, not silently replaced by correct labels. Source functions, planners,
relations, output vocabulary and consumer may all be updated. Actual C/U/Free
history and inherited costs remain. No representation collision is asserted.
U's acquired phi/G update dictionary remains empty; do not claim U ran.
Initial observation facts and term/JSON-node tables are serialized canonically:
they are reconstructed exactly from complete visible_inputs using the supplied
encoder. This removes only duplicate deterministic tables, not any source,
label, actual reading, shared program, scope or feedback. The original paid C
proposal is reused; its full original input remains preserved separately.
'''


def initial_library():
    old=deepcopy(read(SOURCE_ASSET))
    old['operations']=[]
    old['planner_program']='def apply(inputs,premises):\n    return {"queries":[]}\n'
    old['operation_scopes']={};old['complete_source_absence_choices']={}
    old['MAUD_namespace_initialization']={'paid_source_asset':str(SOURCE_ASSET.relative_to(ROOT)),
        'old_NDA_neural_dispatch_not_selected_for_MAUD':True,'no_MAUD_fact_or_answer_supplied':True}
    return old


def initial_record(library,source,view):
    units=view_units(view);empty={'statements':[],'complete':False,'unresolved':[]}
    upstream,event=execute_source_program(library['source_program'],library['spec'],
        source_text=view['public']['source_text'],units=units,source_output=empty)
    o=observe(object(),'offline-initial',source['key'],library,
        source_text=view['public']['source_text'],units=units,source_output=upstream)
    o['context']['id']=digest({'source':source['key'],'view':view['id']})
    return {'source':source['key'],'view':view['id'],'upstream':upstream,
            'upstream_trace':event,'observation':o,**evaluate_view(library,o,source,view)}


def compact_task(task):
    result=deepcopy(task)
    for source in result['tasks']:
        for item in source['individually_scoped_views']:
            o=item['actual_initial']['observation']
            if o['context']['required'] or o['context']['forbidden']:
                raise ValueError('Do not omit actual partial semantic constraints')
            for key in ('context','legacy_roots','term_nodes','term_supports'):o.pop(key)
    result['deterministic_initial_observation_encoding']='Reconstruct full initial observation from visible_inputs with the supplied encoder; context id is digest({source,view}). Execution and all other actual metadata are retained.'
    return result


def restore_task(task):
    result=deepcopy(task);result.pop('deterministic_initial_observation_encoding')
    for source in result['tasks']:
        for item in source['individually_scoped_views']:
            actual=item['actual_initial'];saved=actual['observation'];v=saved['visible_inputs']
            rebuilt=encode_source_observations(actual['source'],source_text=v['source_text'],
                units=v['units'],source_output=v['source_output'],operations=v['operations'],
                queries=v['queries'],answers=v['answers'],scope=v['scope'],
                query_scopes=v.get('query_scopes'),complete_source_absence_choices=v.get('complete_source_absence_choices'))
            rebuilt['context']['id']=digest({'source':actual['source'],'view':actual['view']})
            rebuilt['execution']=saved['execution']
            if any(rebuilt.get(k)!=value for k,value in saved.items()):
                raise ValueError('The actual initial observation did not reconstruct exactly')
            actual['observation']=rebuilt
    return result


def offline():
    FOLDER.mkdir(exist_ok=True)
    if not read(TEACHER_PARENT/'TERMINAL_PRESERVATION.json')['run_boundary_terminal']:
        raise ValueError('Preserve the stopped original teacher request first')
    for name in ('common_simple_control.json','common_simple_control_acquisition.json'):
        immutable_json(FOLDER/name,read(TEACHER_PARENT/name))
    selection=read(SELECTION);public={s['key']:s for s in read(PUBLIC)};library=initial_library();checks=[]
    for item in selection['acquisition']:
        source=public[item['source']]
        for view in source['views']:
            row=initial_record(library,source,view)
            if row['feedback']['reason']=='execution_error':raise ValueError(row['feedback']['error'])
            immutable_json(FOLDER/'initial'/name_for(source['key'],view),row)
            checks.append({'source':source['key'],'view':view['id'],
                'source_statement_count':len(row['upstream']['statements']),
                'core_executed':row['feedback']['views'][0]['core_executed'],
                'new_model_requests':0})
    immutable_json(FOLDER/'offline_initial_check.json',{'checks':checks,
        'shared_library_sha256':digest(library),'new_model_requests':0})
    original=read(TEACHER_PARENT/'ConstraintAcquire/teacher_input.json')
    if original!=read(TEACHER_PARENT/'FreeUpdate/teacher_input.json'):
        raise ValueError('Original independent teacher tasks must have identical information')
    compact=compact_task(original)
    if restore_task(compact)!=original:raise ValueError('Canonical projection changed supplied information')
    immutable_json(FOLDER/'offline_compact_transport.json',{
        'original_full_task_sha256':digest(original),'compact_task_sha256':digest(compact),
        'full_object_roundtrip_exact':True,'actual_initial_views_reconstructed':12,
        'source_labels_programs_actual_readings_feedback_unchanged':True,
        'original_packed_task_characters':len(json.dumps(pack(original),ensure_ascii=False,separators=(',',':'))),
        'compact_packed_task_characters':len(json.dumps(pack(compact),ensure_ascii=False,separators=(',',':'))),
        'new_model_requests':0,'original_timeout_not_erased':True})
    print(json.dumps({'initial_view_executions':len(checks),'new_model_requests':0}),flush=True)


def prepare():
    if (FOLDER/'protocol.json').exists():return read(FOLDER/'protocol.json')
    selection=read(SELECTION);prior=read(PARENT/'protocol.json')
    if not read(PARENT/'TERMINAL_PRESERVATION.json')['run_boundary_terminal']:
        raise ValueError('Preserve the completed parent first')
    with sqlite3.connect(LEDGER) as db:rows=db.execute('select * from calls order by id').fetchall()
    if any(r[6]=='reserved' for r in rows):raise ValueError('Reconcile actual requests first')
    files=[Path(__file__),ROOT/'experiments/legal_skill_evolution_MAUD_simple_control.py',
        ROOT/'experiments/legal_skill_evolution_diagnosed_update_train.py',
        ROOT/'experiments/legal_skill_evolution_joint_acquisition_train.py',
        ROOT/'experiments/legal_skill_evolution_open_acquisition_train.py',
        *sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT/'tests').glob('test_skill_evolution*.py'))]
    data=[SELECTION,PUBLIC,GRADING,SOURCE_ASSET,PARENT/'TERMINAL_PRESERVATION.json',
        FOLDER/'common_simple_control.json',FOLDER/'common_simple_control_acquisition.json',FOLDER/'offline_initial_check.json',
        FOLDER/'offline_compact_transport.json',TEACHER_PARENT/'TERMINAL_PRESERVATION.json',
        TEACHER_PARENT/'ConstraintAcquire/teacher.json',TEACHER_PARENT/'ConstraintAcquire/compiled.json',
        ROOT/'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json',
        ROOT/'artifacts/legal_skill_evolution_20261111/formal_v5/FreeEvolution/B8.json']
    initial=initial_library()
    if read(FOLDER/'offline_initial_check.json')['shared_library_sha256']!=digest(initial):
        raise ValueError('Offline-check the exact shared initial code first')
    p={'run_id':RUN,'same_goal':True,'goal_complete':False,'parent_run':TEACHER_PARENT.name,
        'acquisition_sources':[r['source'] for r in selection['acquisition']],
        'reuse_sources':[r['source'] for r in selection['reuse']],
        'independent_mothers':6,'acquisition_native_views':12,'reuse_native_views':6,
        'each_view_uses_its_own_original_material':True,'native_scoring':'original_MAUD_exact_match',
        'common_simple_acquisition_correct':12,'common_simple_acquisition_total':12,
        'executor_profile':prior['executor_profile'],'teacher_profile':prior['teacher_profile'],
        'teacher_dispatch':'serial','automatic_retries':0,'no_new_mechanical_cap':True,
        'same_teacher_information_after_exact_roundtrip':True,
        'C_paid_original_full_input_reused_not_dispatched_again':True,
        'Free_retry_follows_lossless_derived_table_removal':True,'U_dictionary':[],
        'no_new_full_training_DEV_TEST_or_paper':True,
        'source_snapshot':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(FOLDER/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in rows})
    immutable_json(FOLDER/'shared/initial_library.json',initial)
    for name in ('teacher.json','compiled.json','compilation_receipt.json'):
        immutable_json(FOLDER/'ConstraintAcquire'/name,read(TEACHER_PARENT/'ConstraintAcquire'/name))
    immutable_json(FOLDER/'ConstraintAcquire/actual_original_teacher_input.json',
                   read(TEACHER_PARENT/'ConstraintAcquire/teacher_input.json'))
    immutable_json(FOLDER/'ConstraintAcquire/teacher_reuse.json',{
        'physical_call_id':read(TEACHER_PARENT/'protocol.json')['run_id']+':ConstraintAcquire:teacher',
        'new_physical_requests':0,'raw_proposal_unchanged':True,
        'raw_wire_was_original_full_input_not_this_compact_preflight':True})
    for f in files:
        target=FOLDER/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    immutable_json(FOLDER/'protocol.json',p)
    return p


def setup():
    p=prepare()
    for name,expected in {**p['source_snapshot'],**p['data_sha256']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Frozen input changed: '+name)
    ledger=EvolutionLedger(LEDGER,run_id=RUN,sources={
        'train':p['acquisition_sources']+p['reuse_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger,{s['key']:s for s in read(PUBLIC)}


def teacher_request(arm):
    p,ledger,public=setup();grading=read(GRADING);tasks=[]
    for key in p['acquisition_sources']:
        source=public[key];records=[]
        for view in source['views']:
            records.append({'native_view':view,'actual_initial':read(FOLDER/'initial'/name_for(key,view)),
                            'lawful_TRAIN_annotation':grading[key][view['id']]})
        tasks.append({'source':key,'parent_id':source['parent_id'],'individually_scoped_views':records})
    task={'tasks':tasks,'shared_actual_initial_library':read(FOLDER/'shared/initial_library.json'),
        'common_simple_control':{k:v for k,v in read(FOLDER/'common_simple_control.json').items() if k!='selection'},
        'common_simple_control_TRAIN_result':read(FOLDER/'common_simple_control_acquisition.json'),
        'common_observed_signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
        'fact_encoder_source':(ROOT/'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'no_future_material_or_labels':True}
    proof=read(FOLDER/'offline_compact_transport.json')
    if digest(task)!=proof['original_full_task_sha256']:
        raise ValueError('Original teacher information changed before compact dispatch')
    task=compact_task(task)
    if digest(task)!=proof['compact_task_sha256'] or restore_task(task)!=read(TEACHER_PARENT/'ConstraintAcquire/teacher_input.json'):
        raise ValueError('Compact task does not exactly restore the paid C input')
    if any(key in json.dumps(task,ensure_ascii=False) for key in p['reuse_sources']):
        raise ValueError('Future mother identity/material entered teacher task')
    system=COMMON+'\n'+DOMAIN+'\n'+(C_SPEC if arm=='ConstraintAcquire' else FREE_SPEC)+'\n'+INSTRUCTION
    system+='\nAllowed pure attributes: '+','.join(sorted(METHODS))+'\nAllowed calls: '+','.join(sorted(CALLS))
    user=json.dumps(pack(task),ensure_ascii=False,separators=(',',':'))
    args={'source_ids':p['acquisition_sources'],'system_prompt':system,'user_prompt':user,'output_schema':SCHEMA}
    size=len(render_structured_codex_prompt(system,user));issues=strict_output_schema_issues(SCHEMA)
    immutable_json(FOLDER/arm/'teacher_input.json',task)
    immutable_json(FOLDER/arm/'preflight.json',{'input_characters':size,'schema_issues':issues,
        'task_sha256':digest(task),'request_sha256':digest(args),'new_model_requests':0,
        'this_preflight_dispatched':arm=='FreeUpdate','C_actual_original_full_input_preserved':True})
    if issues or size>CODEX_TURN_INPUT_CHARACTER_LIMIT:raise ValueError('Fix complete wire offline before dispatch')
    return p,ledger,args


def acquire():
    for arm in ARMS:
        dst=FOLDER/arm/'teacher.json'
        if dst.exists():continue
        p,ledger,args=teacher_request(arm)
        result=FrozenTeacher(ledger,FOLDER,p['teacher_profile']).propose(RUN+':'+arm+':teacher',**args)
        immutable_json(dst,result)


def compile_all():
    p,_,public=setup()
    for arm in ARMS:
        dst=FOLDER/arm/'compiled.json'
        if dst.exists():continue
        proposal=read(FOLDER/arm/'teacher.json')['value'];jsonschema.validate(proposal,SCHEMA)
        library,receipt=compile_proposal(read(FOLDER/'shared/initial_library.json'),proposal,arm,
            {key:public[key] for key in p['acquisition_sources']},source_functions=proposal['source_functions'])
        immutable_json(FOLDER/arm/'compilation_receipt.json',receipt);immutable_json(dst,library)


def run_stage(reuse=False):
    p,ledger,public=setup();stage='reuse' if reuse else 'acquisition'
    if reuse and not (FOLDER/'library_freeze.json').exists():raise ValueError('Freeze both libraries first')
    grading=None if reuse else read(GRADING)
    for arm in ARMS:
        if not reuse and (FOLDER/arm/'learned.json').exists():continue
        library=read(FOLDER/arm/('learned.json' if reuse else 'compiled.json'));observations=[];profiles=[]
        for key in p['reuse_sources'] if reuse else p['acquisition_sources']:
            source=public[key]
            for view in source['views']:
                name=name_for(key,view);dst=FOLDER/stage/arm/name
                if dst.exists():row=read(dst)
                else:
                    initial=read(FOLDER/'initial'/name) if not reuse else initial_record(read(FOLDER/'shared/initial_library.json'),source,view)
                    if reuse:immutable_json(FOLDER/'reuse_initial'/name,initial)
                    history=[initial['observation']]
                    counterpart=FOLDER/stage/'ConstraintAcquire'/name
                    if arm=='FreeUpdate' and counterpart.exists():history.append(read(counterpart)['observation'])
                    o=observe(FrozenExecutor(ledger,FOLDER,p['executor_profile']),RUN+':'+stage+':'+arm+':'+name,
                        key,library,source_text=view['public']['source_text'],units=view_units(view),
                        source_output=initial['upstream'],previous_observations=history,
                        save_event=lambda e:immutable_json(FOLDER/stage/arm/'events'/(digest(e['call_id'])+'.json'),e))
                    o['context']['id']=digest({'source':key,'view':view['id']})
                    actual=evaluate_view(library,o,source,view,None if reuse else grading[key][view['id']]) if reuse or arm=='FreeUpdate' else None
                    if actual is None:
                        direct=deepcopy(library);direct['selected_rule_ids']=library['suggested_rule_ids']
                        actual={'NoFit':evaluate_view(direct,o,source,view,grading[key][view['id']])}
                        direct_bodies=all(library['language']['signatures'][a['predicate']]['kind']=='observed'
                            for rule in library['language']['rules'] for a in rule['body'])
                        enumerator=admissible_theories if o['context']['unknown_groups'] else \
                            admissible_direct_compositions if direct_bodies else admissible_program_compositions
                        profile=enumerator(library,o,view_checker(library['spec'],source,view,grading[key][view['id']]),timeout_seconds=90)
                        if profile['status']!='complete':
                            immutable_json(FOLDER/arm/'incomplete_profiles'/name,profile)
                            raise ValueError('Preserve real reads before refining incomplete deterministic search')
                        actual['profile']=profile
                    row={'source':key,'view':view['id'],'observation':o,**actual}
                    immutable_json(dst,row)
                    print(json.dumps({'stage':stage,'arm':arm,'source':key,'view':view['id'],
                        'queries':o['execution']['planned_queries'],'new_physical':o['execution']['new_physical_requests']}),flush=True)
                observations.append(row['observation'])
                if 'profile' in row:profiles.append(row['profile'])
        if not reuse:
            if arm=='ConstraintAcquire':
                library,result=fit(library,[attach_scored_theories(o,a) for o,a in zip(observations,profiles)],timeout_seconds=90)
                immutable_json(FOLDER/arm/'fit.json',result)
                if result['status']!='sat':raise ValueError('Inspect actual hard-constraint/fit failure before further calls')
                for key in p['acquisition_sources']:
                    for view in public[key]['views']:
                        name=name_for(key,view);o=read(FOLDER/'acquisition'/arm/name)['observation']
                        immutable_json(FOLDER/arm/'fitted_execution'/name,evaluate_view(library,o,public[key],view,grading[key][view['id']]))
            immutable_json(FOLDER/arm/'learned.json',library)
    if not reuse:
        immutable_json(FOLDER/'library_freeze.json',{'libraries':{a:digest(read(FOLDER/a/'learned.json')) for a in ARMS},
            'reuse_labels_not_used':True,'goal_complete':False})


def score_reuse():
    p,_,public=setup()
    if any(not (FOLDER/'reuse'/a/name_for(k,v)).exists() for a in ARMS for k in p['reuse_sources'] for v in public[k]['views']):
        raise ValueError('Save both arms on all six unlabeled views before scoring')
    grading=read(GRADING);control=read(FOLDER/'common_simple_control.json')['program']
    for key in p['reuse_sources']:
        for view in public[key]['views']:
            name=name_for(key,view)
            for arm in ARMS:
                row=read(FOLDER/'reuse'/arm/name);library=read(FOLDER/arm/'learned.json')
                immutable_json(FOLDER/'reuse_scores'/arm/name,evaluate_view(library,row['observation'],public[key],view,grading[key][view['id']]))
            from legal_skill_guard.skill_evolution.native import grade_view
            value=execute_json(control,{'source_text':view['public']['source_text'],'task_id':view['id']},{},allow_helpers=True)
            immutable_json(FOLDER/'reuse_scores/SimpleControl'/name,{'source':key,'view':view['id'],'actual':value,
                'score':grade_view('MAUD',view,grading[key][view['id']],value['answer']) if value['handled'] else None})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['offline','prepare','preflight','acquire','compile','train','reuse','score']);args=ap.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='offline':offline()
        elif args.phase=='prepare':prepare()
        elif args.phase=='preflight':
            for arm in ARMS:teacher_request(arm)
        elif args.phase=='acquire':acquire()
        elif args.phase=='compile':compile_all()
        elif args.phase=='score':score_reuse()
        else:run_stage(args.phase=='reuse')
