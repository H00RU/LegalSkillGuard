"""Complete raw-rule acquisition on the original 24 ContractNLI TRAIN parents.

This continues the repaired C source path, without restarting the mixed study.
The same teacher independently updates the method and strong ordinary control.
Only actual function/rule deltas are generated; unchanged reader definitions,
planner, model configuration and paid histories are retained by the host.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_C_scope_runtime as prior
from experiments import legal_skill_evolution_positive_binding_acquisition as core
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema, source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION, validate_operations
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import (
    execution_source_units, CALLS, METHODS, validate_procedure)
from legal_skill_guard.skill_evolution.teacher_transport import (
    pack_programs, INSTRUCTION, PROGRAM_INSTRUCTION)

ROOT=prior.ROOT
RUN='legal_skill_evolution_C_TRAIN_completion_20261115'
OUT=ROOT/'artifacts'/RUN
SCHEMA=record_schema({
    'rationale':{'type':'string'},
    'source_functions':{'type':'array','items':{'type':'string'}},
    'program_operations':{'type':'array','items':OPERATION},
    'program_operation_scopes_json':{'type':'string'},
    'signature_additions_json':{'type':'string'},
    'constant_additions_json':{'type':'string'},
    'rule_edits_json':{'type':'string'},
    'removed_rule_ids':{'type':'array','items':{'type':'string'}},
    'renderer_edits_json':{'type':'string'},
    'suggested_rule_ids':{'type':'array','items':{'type':'string'}}})
SYSTEM='''Continue the CURRENT legal-skill learning study. No tools. Complete
the repaired RAW source-acquisition path on the original 24 TRAIN contracts.
This is not a new topic, data expansion, DEV/TEST access or weight training.
The unchanged 8B reads supplied text; its memorized legal knowledge is not the
research target. Acquire reusable external source-processing skill functions.

Both arms have the SAME full original TRAIN source, native supervision, shared
source reviews, type/consumer specification, pure-code capabilities and model
settings. Each independently updates its own previous library and actual reads.
All 24 are now TRAIN, not a fresh blind set. The last fixed pair gave C4/8,
ordinary teacher2/8, direct8B4/8; C with old program, without G fit or without
clause binding was also4/8. Those results do NOT establish a contribution.
Do not merely patch the last two cases. Learn general source structures across
the full existing TRAIN corpus, keeping valid learned capabilities.

Return ONLY real pure function replacements/additions in source_functions:
one complete top-level function per string, no unchanged functions. The host
merges functions by name into previous_source_program and validates all code.
This saves regenerating unchanged helpers and reader definitions. You may
replace apply and introduce helpers. No imports, IO, reflection, locals/globals,
recursion or nested functions. re is prebound; actual permitted calls/methods
are supplied. No source/company-ID dispatch, memorized native labels, native
question dispatch or use of expected answers as source facts. Raw current
source is the only factual input; old demonstrations are not current facts.

C: apply(inputs,premises) receives source_text, source_spans (actual unit IDs),
empty source_output, and actual neural semantic_answers. Return exactly
{queries:[{id,operation,unit_ids}], answers:[{id,choice,evidence_unit_ids}],
fragments:[{term,support_ids,query_ids}], unresolved:[string]}.
These program answers are computed concepts, NOT new neural readings. Keep
fragment terms only Participant, Information, Action, Trigger, Condition,
Exception or ExceptionSet, including nested terms. Never hide a complete Norm,
Definition, Description or answer in a fragment. All unknowns stay unresolved.
Only actual complete-source NEURAL audits can support source absence.

Every fragment's query_ids must explicitly include its actual producing CLAUSE
GROUP query, shared by all parts of a single legal frame. Conditions and
exceptions belong to that exact frame, not just an overlapping evidence window.
The host supplies observed fragment_query(term,query) from these actual edges,
alongside reader_query, query_choice, legacy_root, root_support, term_type and
the existing structural facts. G must use shared producing-query bindings for
new scoped compositions; merely sharing a unit can produce a Cartesian product
of unrelated triggers/conditions. The previous real retention regression went
from16mixed outputs to1correct clause-bound output. This is a necessary semantic
binding mechanism, not permission to add legal facts.

G edits start from the COMPLETE previous language/renderers. New signatures
may be derived/output only; observed fragment_query is already supplied.
Rules={id,cost,head,body}; atom={predicate,arguments,sign}; variables={var:Name}.
Renderer templates use {term_argument:i}/{scalar_argument:i}, with actual
support arguments/terms/queries. suggested_rule_ids is the unfit control; host
selects source-valid TRAIN candidates and freezes before any DEV. Empty edit
JSONs are valid when no change is warranted. Do not delete a whole legitimate
production globally to fix a differently scoped source.

The existing neural operations, examples, scope declarations, absence choices
and planner are LOCKED for this update; do not regenerate them. program_operations
may APPEND only PROGRAM-COMPUTED concept declarations, with corresponding scopes
in program_operation_scopes_json. They never enter the unchanged neural planner.
All old operations remain available. Examples, if any, quote an actual supplied
TRAIN source. Never declare program-computed complete-source absence.

Ordinary FreeTeacher: independently repair your strongest ordinary reusable
source-to-Norm compiler using the SAME full raw corpus and pure-code capacity.
Your source_functions update previous_source_program, whose apply gets the same
raw source_text, source_spans, empty source_output and actual semantic_answers,
and returns {statements:[{term,support_ids}],complete:boolean,unresolved:[string]}.
You may resolve definitions, parse lists, keep clause scopes, implement helper
grammars and preserve exact old functions. You are not forced into an inferior
local regex or failing neural classification. Return empty rule/renderer/signature/
constant edits and selected IDs for this ordinary-program arm.

Both arms must distinguish ACTOR from disclosure RECIPIENT, including 'neither
it nor its Representatives ... disclose ... to any other person'; resolve actual
definitions/aliases and coordinated verbs under one negation. Alphabetic and
numeric lists may inherit governing obligations. Preserve recipient ownership,
AND/OR, consent/purpose/service/legal-process exceptions, full disposal material
scope, and post-disposal retention versus ordinary no-copy or secrecy survival.
An NDA-signing requirement and foreign-hosting ban are not standalone disclosure
permissions. Do not turn a definition/mention into permission or missing parse
into no rule. TRAIN-native correctness does not certify all source semantics.
Do not force an unsupported native label by changing the actual legal meaning.
Return the strict JSON deltas, not a research summary or unchanged large library.
'''


def read(path):return json.loads(path.read_text())


def prepare():
    old=prior.protocol();public,grading=prior.g.previous.base.history.bank()
    assert len(public)==24 and set(public)==set(old['sources'])
    bank={};sources=[]
    for sid,source in public.items():
        text=source['views'][0]['public']['source_text']
        units,_=execution_source_units(text,source_spans(material_public(source['views'][0]['public'])))
        bank[sid]={'source':source,'units':units,'empty_upstream':{'statements':[],'complete':False,'unresolved':[]}}
        sources.append({'source':sid,'source_text':text,'units':units,
            'native_TRAIN_supervision':grading[sid],
            'native_hypotheses':[{'id':v['id'],'question':v['public']['question']}for v in source['views']]})
    shared={'TRAIN_sources':sources,'common_spec':read(prior.g.OUT/'common_spec.json'),
        'shared_source_reviews':read(prior.g.previous.base.history.OUT/'teacher_task.json')['shared_partial_reviews'],
        'actual_scope_binding_regression':{
            'source':read(prior.OUT/'fragment_query_regression.json')['source'],
            'before_output_count':16,'after_output_count':1,
            'mechanism':'Roots must be linked to the same actual producing clause query; no source legal fact is added',
            'compiler_signature':{'fragment_query':{'arguments':['term','query'],'kind':'observed'}}},
        'same_input_causal_summary':[
            {'source':row['source'],
             'native_correct':{k:row[k]['native_correct']for k in (
                 'Full','NoClauseBinding','NoFitSameSelectedProgram','PreviousFrozenLibrary')}}
            for row in read(prior.OUT/'C/causal_attribution.json')['rows']],
        'supported_pure_calls':sorted(CALLS),'supported_pure_methods':sorted(METHODS)}
    for arm in ('C','FreeTeacher'):
        previous=read(prior.OUT/arm/'selected_before_reuse.json')['library']
        field='source_concept_program'if arm=='C'else'composition_program'
        observations=[]
        for sid in public:
            path=prior.OUT/arm/'raw_observations'/(digest(sid)+'.json')
            if path.exists():observations.append({'source':sid,'visible_inputs':read(path)['visible_inputs']})
        task={**shared,'previous_own_library':previous,'previous_source_program':previous[field],
            'actual_own_neural_reads':observations,'actual_own_results':read(prior.OUT/arm/'result.json')}
        immutable_json(OUT/arm/'teacher_task.json',task)
        immutable_json(OUT/arm/'previous_library.json',previous)
    immutable_json(OUT/'raw_source_bank.json',bank)
    immutable_json(OUT/'TRAIN_grading.json',grading)
    p={k:deepcopy(old[k])for k in ('sources','executor_profile','teacher_profile')}
    p.update(run_id=RUN,same_goal=True,goal_complete=False,source_branch_training_completion=True,
        new_full_mixed_training=False,new_DEV_TEST=False,all24_are_original_TRAIN=True,
        acquisition_sources=list(public),fixed_reuse_sources=[],
        ledger_before=prior.g.previous.base.lineage.ledger_snapshot(),
        delta_only_teacher_output=True,neural_operations_and_planner_unchanged=True)
    files=[Path(__file__),Path(prior.__file__),Path(core.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT/n for n in ('raw_source_bank.json','TRAIN_grading.json','C/teacher_task.json','FreeTeacher/teacher_task.json','C/previous_library.json','FreeTeacher/previous_library.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    sizes={a:len(json.dumps(pack_programs(read(OUT/a/'teacher_task.json'))))for a in ('C','FreeTeacher')}
    print(json.dumps({'prepared':RUN,'original_TRAIN_mothers':24,'packed_task_chars':sizes}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def acquire():
    p=protocol();ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)
    client=FrozenTeacher(ledger,OUT,p['teacher_profile'])
    def one(arm):
        if(OUT/arm/'teacher.json').exists():return
        value=client.propose(RUN+':'+arm+':TRAIN_completion',source_ids=p['sources'],
            system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(read(OUT/arm/'teacher_task.json')),ensure_ascii=False,separators=(',',':')),
            output_schema=SCHEMA)
        immutable_json(OUT/arm/'teacher.json',value);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('C','FreeTeacher')]
        for job in jobs:job.result()


def compile_functions():
    p=protocol();bank=read(OUT/'raw_source_bank.json');libraries={}
    for arm in ('C','FreeTeacher'):
        v=read(OUT/arm/'teacher.json')['value'];lib=read(OUT/arm/'previous_library.json')
        field='source_concept_program'if arm=='C'else'composition_program'
        lib[field]=function_update(lib[field],v['source_functions']);validate_procedure(lib[field],allow_helpers=True)
        new=v['program_operations'];assert not({o['name']for o in new}&{o['name']for o in lib['operations']})
        validate_operations(new,{sid:bank[sid]['source']['views'][0]['public']['source_text']for sid in p['sources']})
        scopes=json.loads(v['program_operation_scopes_json']);assert set(scopes)=={o['name']for o in new}
        assert all(s in ('window','focus_last')for s in scopes.values())
        lib['operations']+=new;lib['operation_scopes'].update(scopes)
        # Rule deltas are validated and installed by the execution binding after
        # the generated functions pass actual-input regression; no model retry.
        libraries[arm]={'library':lib,'rule_delta':v}
    return libraries


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','acquire','validate'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'validate':compile_functions}[args.phase]()
