"""Independent shared-base repairs, then fixed original-TRAIN transfer checks.

The repair is public correctness work for both independently acquired programs,
not either proposed contribution. Old calibration replays and new-to-this-pilot
transfer checks are reported separately. No TEST or extra source is used.
"""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_source_trial import ARMS, OUT as PARENT
from experiments.legal_skill_evolution_callable_rule_refactor import UNIT as OLD_UNIT
from experiments.legal_skill_evolution_callable_rule_audit import trace
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_evaluate import READ_QUESTION, validate_case_bindings
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import bind_case_premises, compile_library, entry_program, evaluate, plan
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.query_scope import literal_query_arguments
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError
from legal_skill_guard.skill_evolution.source_python import merge_functions
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN='legal_skill_evolution_scoped_premise_repair_20261113'
OUT=ROOT/'artifacts'/RUN
ARGUMENT=record_schema({'name':{'type':'string'},'type':{'type':'string','enum':['integer','string']},
    'selector':{'type':'string','enum':['year','subject','taxpayer','individual','employer','employee']}})
UNIT=record_schema({**OLD_UNIT['properties'],'arguments':{'type':'array','items':ARGUMENT}})
RESULT=record_schema({'function_updates':{'type':'array','items':{'type':'string'}},
    'unit_updates':{'type':'array','items':UNIT},'change_explanation':{'type':'string'},
    'unresolved':{'type':'array','items':{'type':'string'}}})
SYSTEM='''You are the existing authorized skill teacher. Repair your own actual
acquired source program and its factual contracts. This is the SAME PUBLIC
CORRECTNESS repair for both independently acquired arms, not a proposed research
contribution and not an opportunity to copy another arm. You see only your own
program, the original law, the three old TRAIN cases and your own actual traces.
There are no future case bodies/questions/labels and no grading labels here.

Return complete replacement/addition function definitions in function_updates,
and complete metadata records only for changed/new units in unit_updates.
Preserve unrelated functions and rules. Do not regenerate the whole library.
Existing unit ids must retain their clause/kind identity; new source-backed
rules may be acquired but origin and exact source quotes must be honest. Pure
Python only, same restricted environment. Each legal function takes one mapping
and returns value, used_units and open_dependencies as before. Never hardcode
case ids, persons, question amounts, native labels or example positions.

The public host now separates query arguments from CASE PREMISES. A unit's
arguments:[{name,type,selector}] declares literal argument ports. Selectors year,
subject,taxpayer,individual,employer,employee bind ONLY literal names/periods from
recognized query forms. They never assert dependency, marriage or eligibility.
The host injects these declared arguments into the legal function's mapping
alongside supported factual values. A selector cannot obtain the native claim.
Each field remains a case-fact question, but can use argument-port placeholders
such as {taxpayer_name} and {individual_name}; the host renders them with literal
query participants before asking the frozen reader. Use correct query roles;
do not let Alice's marriage toCharlie become Bob's relationship toAlice.

All old units have mechanically initialized arguments:[]; this supplies no
semantics. Use new explicit argument declarations where actually meaningful.
Context year is the period the native legal query asks about; do not ask the
reader to reconstruct it as an unmentioned factual prerequisite. Missing or
ambiguous query arguments stay absent. Ordinary unknown case values stay
unknown, never default False/zero/empty. Predicate/quantity must remain separate.

Known concrete issues, derived from source and actual execution rather than
future answers:
1. A given applicable amount under68(b) can be a case premise. Do not force
reconstruction from unspecified filing_status. The percentage definition151d3B
is a different property from the final exemption amount; do not introduce a
global exemption/suspension prerequisite not belonging to that query property.
2. The case explicitly stipulates an exemption entitlement for another person;
151(a) states the legal connection to deductions. Acquire/execute that source
connection in code if needed, rather than asking a primitive reader to derive
an unstated legal entitlement. Read the explicit GIVEN premise with its roles.
3. A stipulated dependent/qualifying-child premise can be consumed where valid
under the source, without rederiving unprovided antecedents. The native question
is NOT such a premise. Only facts have evidence span IDs; the query is scope
context. Question-only support was rejected, never repaired into evidence.
4. Unrecognized relationship strings are not proved non-relatives, and absent
claimant-dependency statements are not proved False. Preserve true unknowns.

Make parameterized repairs consistent across your existing units and acquired
helpers. Do not tailor to three answers or add fixed answer routes. You may
expose existing source helper definitions as independent properties, but do not
invent missing source law. Record limitations. The supplied host code specifies
the actual interface. No weights, no extra data, no model calls inside programs.
''' + INSTRUCTION


def prepare():
    prior=read(PARENT/'protocol.json');public_path=ROOT/prior['public_manifest']
    public={s['key']:s for s in read(public_path)}
    transfer=[s['key'] for s in public.values() if s['dataset']=='SARA_v2_Binary'
              and s['views'][0]['public']['source_text'].startswith('§152.')]
    assert len(transfer)==2
    task=read(PARENT/'source_only_input.json');material=task['law_material']
    assert all(public[k]['views'][0]['public']['source_text']==material['referenced_public_sections.152'] for k in transfer)
    paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
        ROOT/'legal_skill_guard/skill_evolution/query_scope.py',ROOT/'legal_skill_guard/skill_evolution/task_roles.py',
        ROOT/'legal_skill_guard/skill_evolution/source_python.py',ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT/'legal_skill_guard/skill_evolution/runtime.py',ROOT/'tests/test_skill_evolution_callable_rules.py',
        ROOT/'tests/test_skill_evolution_query_scope.py']
    p={'run_id':RUN,'same_goal':True,'goal_complete':False,'source_ids':prior['source_ids']+transfer,
        'repair_feedback_sources':prior['source_ids'],'transfer_sources':transfer,'arms':ARMS,
        'public_manifest':prior['public_manifest'],'public_sha256':sha(public_path),
        'teacher_profile':prior['teacher_profile'],'executor_profile':prior['executor_profile'],
        'source_sha256':{str(f.relative_to(ROOT)):sha(f) for f in paths},
        'scope':'Public engineering repair to both independently acquired libraries. Three previously exposed151 cases are calibration only; two original152 cases are fixed source-reference transfer checks, not new blind TEST.',
        'comparison':'Both receive the same public repair instructions, original law and old TRAIN cases, but only own acquired program and own observations. No other-arm code, new labels, sources or future cases.',
        'workload':'Two independent teacher deltas; freeze both before real reads. One reader request per supported arm/case; old3 calibration and next2 transfer reported separately. No unchanged automatic retries or post-transfer retuning.',
        'not_either_candidate_contribution_or_final_ablation':True,'no_full_training_DEV_TEST_or_paper':True}
    immutable_json(OUT/'protocol.json',p);immutable_json(OUT/'output_schema.json',RESULT)
    evidence=[]
    for key in prior['source_ids']:
        q=public[key]['views'][0]['public']['question'];evidence.append({'source':key,'literal_scope':literal_query_arguments(q)})
    immutable_json(OUT/'offline_scope_evidence.json',{'original_query_bindings':evidence,
        'next_main_source_exactly_equals_already_acquired_reference':True,'offline_regressions_passed':27,
        'case_or_legal_propositions_filled':False,'new_model_requests':0})
    for f in paths:
        t=OUT/'source_snapshot'/f.relative_to(ROOT);t.parent.mkdir(parents=True,exist_ok=True)
        if t.exists():assert t.read_bytes()==f.read_bytes()
        else:t.write_bytes(f.read_bytes())
    for arm in ARMS:
        lib=read(PARENT/arm/'library.json')
        seed={'program':lib['program'],'units':[{**u,'arguments':[]} for u in lib['units'].values()]}
        assert compile_library(seed,material)['program']==lib['program']
        own=[]
        for key in prior['source_ids']:
            r=read(PARENT/'execution'/arm/key.replace(':','_')/'result.json')
            provenance=read(PARENT/'facts_only_replay'/arm/key.replace(':','_')/'result.json')
            own.append({'source':key,'case':{k:v for k,v in public[key]['views'][0]['public'].items() if k in ('facts','question')},
                'plan':r['plan'],'read_event':r['read_event'],'case_values':r['validated_case_values'],
                'execution':r['execution'],'question_only_provenance_check':{k:provenance[k] for k in
                    ('accepted_case_values','rejected_question_only_bindings','actual_program_result','execution')}})
        task={'law_material':material,'actual_own_program_and_units':seed,'own_old_TRAIN_observations':own,
            'actual_host_interface':(ROOT/'legal_skill_guard/skill_evolution/callable_rules.py').read_text(),
            'literal_query_argument_selector':(ROOT/'legal_skill_guard/skill_evolution/query_scope.py').read_text(),
            'no_future_case_body_question_label_or_other_arm_program':True}
        immutable_json(OUT/arm/'input.json',task)
    print(json.dumps({'prepared':True,'feedback_cases':len(prior['source_ids']),'fixed_transfer_cases':len(transfer),'new_model_calls':0}),flush=True)


def state():
    p=read(OUT/'protocol.json')
    assert all(sha(ROOT/n)==h for n,h in p['source_sha256'].items())
    assert sha(ROOT/p['public_manifest'])==p['public_sha256']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['source_ids'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger


def acquire(arm):
    p,ledger=state();task=read(OUT/arm/'input.json')
    if not (OUT/'ledger_before.json').exists():
        with ledger.transaction() as db:rows=[list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6]=='reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json',{'rows':rows})
    r=FrozenTeacher(ledger,OUT/arm,p['teacher_profile']).propose(RUN+':repair:'+arm,
        source_ids=p['repair_feedback_sources'],system_prompt=SYSTEM,
        user_prompt=json.dumps(pack(task),ensure_ascii=False),output_schema=RESULT)
    immutable_json(OUT/arm/'teacher.json',r)
    try:
        old=task['actual_own_program_and_units'];updates=r['value']
        units={u['id']:u for u in old['units']};seen=set()
        for u in updates['unit_updates']:
            assert u['id'] not in seen;seen.add(u['id'])
            if u['id'] in units:assert (u['clause'],u['kind'])==(units[u['id']]['clause'],units[u['id']]['kind'])
            units[u['id']]=u
        combined={'program':merge_functions(old['program'],updates['function_updates']),'units':list(units.values())}
        lib=compile_library(combined,task['law_material'])
        immutable_json(OUT/arm/'library.json',lib)
        immutable_json(OUT/arm/'offline_check.json',{'typed_scoped_contracts_and_source_witnesses':True,
            'changed_functions':len(updates['function_updates']),'changed_units':len(updates['unit_updates']),
            'real_case_or_contribution_validation_pending':True})
        print(json.dumps({'arm':arm,'changed_functions':len(updates['function_updates']),
            'changed_units':len(updates['unit_updates']),'seconds':r['elapsed_seconds']},ensure_ascii=False),flush=True)
    except Exception as e:
        immutable_json(OUT/arm/'offline_check.json',{'error':type(e).__name__+': '+str(e)})
        print(json.dumps({'arm':arm,'error':str(e)}),flush=True)


def execute():
    p,ledger=state();libs={arm:read(OUT/arm/'library.json') for arm in ARMS}
    with ledger.transaction() as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
        teacher_ids=[r[0] for r in db.execute("select id from calls where role='teacher' order by id")]
    immutable_json(OUT/'freeze.json',{'protocol_sha256':digest(p),'library_sha256':{k:digest(v) for k,v in libs.items()},
        'teacher_ids':teacher_ids,'all_calibration_and_transfer_before_first_new_reader':True})
    public={s['key']:s for s in read(ROOT/p['public_manifest'])}
    grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    client=FrozenExecutor(ledger,OUT/'execution',p['executor_profile']);client.readiness();reads=FrozenReads(client)
    for stage,keys in [('calibration',p['repair_feedback_sources']),('transfer',p['transfer_sources'])]:
        for key in keys:
            source=public[key];view=source['views'][0];query=view['public']['question']
            material={'source_text':view['public']['source_text'],**{
                'referenced_public_sections.'+k:v for k,v in view['public']['referenced_public_sections'].items()}}
            for arm,lib in libs.items():
                state();target=OUT/'execution'/stage/arm/key.replace(':','_')/'result.json'
                if target.exists():continue
                planned=plan(lib,query,material);values,event,rejected,error={},None,[],None
                case={**view,'public':{'facts':view['public']['facts']}}
                if planned['supported'] and planned['fields']:
                    try:
                        raw,event=reads.read(source,case,question=READ_QUESTION,fields=planned['fields'],
                            locator='case facts; literal query arguments supplied only as scope',
                            invocation_arguments={'current_question':query,'query_arguments':planned['query_arguments']},
                            purpose='skill_replay',allow_unresolved=True,require_case_support=True)
                        checked,rejected=validate_case_bindings(planned['fields'],raw,event)
                        values,more=bind_case_premises(checked,event);rejected+=more
                    except LocalReadError as e:event=e.event;error=str(e)
                result=evaluate(lib,planned,values)
                execution=trace(entry_program(lib,planned['unit']),{'facts':{**planned['query_arguments'],**values}}) if planned['supported'] else None
                core=error is None and result['answer'] in ('Entailment','Contradiction')
                record={'stage':stage,'arm':arm,'source':key,'query':query,'plan':planned,
                    'read_event':event,'read_error':error,'case_values':values,'rejected':rejected,
                    'result':result,'execution':execution,'core_executed':core,'fallback_required':not core,'fallback_executed':False,
                    'native_score':grade_view(source['dataset'],view,grading[key][view['id']],result['answer']) if core else None,
                    'semantic_review_pending':True,'engineering_repair_not_method_ablation':True,'goal_complete':False}
                immutable_json(target,record)
                print(json.dumps({'stage':stage,'arm':arm,'source':key,'answer':result['answer'],'score':record['native_score'],'error':error}),flush=True)
    with ledger.transaction() as db:assert teacher_ids==[r[0] for r in db.execute("select id from calls where role='teacher' order by id")]


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','acquire','execute']);parser.add_argument('--arm',choices=ARMS)
    args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_scoped_premise_repair.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare()
        elif args.action=='acquire':assert args.arm;acquire(args.arm)
        else:execute()
