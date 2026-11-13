"""Fixed original-TRAIN comparison after the property-interface repair.

The two teachers independently acquire from the same new-to-this-prototype law,
without case text, native questions or labels. All three cases freeze before
the first executor request. This early screen is not final two-factor evidence.
"""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_rule_refactor import RESULT
from experiments.legal_skill_evolution_callable_rule_audit import trace
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_evaluate import READ_QUESTION, validate_case_bindings
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import compile_library, entry_program, evaluate, plan
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_callable_source_trial_20261113'
OUT = ROOT / 'artifacts' / RUN
ARMS = ['ProofSkills', 'IndependentCache']
COMMON = '''You are the existing authorized skill teacher. Independently acquire
an executable reusable legal source program. All supplied materials are original
TRAIN law. There are NO case facts, native case questions, case labels or another
arm's program. Both teacher and executor weights stay fixed. Return working pure
Python functions and exact source-backed unit metadata, not a design report.

Common public interface: each independently callable property function takes
one dictionary facts and returns exactly {'value': bool/number/null,
'used_units':[declared acquired unit ids], 'open_dependencies':[strings]}.
Expose exact canonical source clause heads with kind predicate or quantity.
Predicate is the clause's applicability/qualification; quantity computes its
intrinsic legal amount/percentage. A conditional numerical clause can expose
BOTH kinds through different functions. An inapplicable consequence need not
mean its applicability is unknown, and a quantity>0 is not a generic predicate.
No need to invent applicability for unconditional definitions. One property
per literal clause/kind, no aliases or question-answer templates.

Only pure function definitions, no imports, globals, classes, file/network/tool
access, introspection, decorators or model calls. Exactly one apply(inputs,
premises) stub is needed for existing validation; it may return None because
the host directly calls each declared one-argument function. Available calls
and methods are supplied. Local helpers and recursion are allowed.

The program NEVER receives a native question, asserted quantity, case label,
source identity or example position. The host handles literal query syntax and
compares the property's computed value with the claim. A function's fields
describe case-fact reading questions about the person and year in the current
native query. Ask primitive facts, relations, dates and amounts, or legal
intermediates explicitly GIVEN in case facts; never ask the executor to decide
the native verdict or rederive the law. Keep the requested subject and counterparty
clear. A stated legal intermediate is usable as a premise and does not require
reconstructing unavailable antecedents; it must not be copied from the question.
Missing facts stay unknown; do not use closed-world False/zero/empty defaults.
An unambiguously disproven condition can be False even when other conditions
are unknown. Report remaining proof obligations for underdetermined properties.

All legal constants and conditions come from the supplied law. Honor caps,
exceptions, dependency relations, spouse roles and temporal qualifications.
Every unit quote is an exact substring of the named law_material source_field,
and its declared function actually computes that property. New source-derived
units use origin new_source_acquisition. Neither helper counts nor amount of
generated code count as a method success. Return unresolved limitations honestly.
The same interface, law scope, generic parsing and correctness checks are shared
by the strong control. No new sources, tests, model tuning or weight updates.
''' + INSTRUCTION
METHOD = '''Use teacher-distilled legal proof skills. Identify independently
meaningful source heads, then acquire their support, defeat/exception conditions
and source-defined computations as reusable functions. Close dependencies using
the supplied referenced sections or explicit GIVEN case premises. Avoid a narrow
program specialized to one visible query: different legal subgoals should call
the already learned condition/computation rather than trigger new formalization.
Keep a precise source witness and unresolved support/exception obligations.
'''
CONTROL = '''Independently learn the strongest ordinary executable whole-source
policy/cache in free Python. Choose your own organization, functions, decomposition,
proof organization, lazy evaluation and memory to maximize reliable subsequent
native task accuracy at comparable complete acquisition and execution cost.
The same unit API, source information, primitive reader and public repairs are
available. You may use the same architecture, compile the full law, expose all
relevant clauses and conditions, and implement complete exceptions or dependency
handling. Do not weaken yourself or artificially omit reusable behavior. No
prescribed candidate algorithm or code from the other arm is provided.
'''


def prepared():
    p = read(OUT / 'protocol.json')
    public = {s['key']: s for s in read(ROOT / p['public_manifest'])}
    return p, public, read(OUT/'source_only_input.json')


def prepare():
    public_path = ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    sources = [s for s in read(public_path) if s['dataset'] == 'SARA_v2_Binary'
               and s['views'][0]['public']['source_text'].startswith('§151.')]
    assert len(sources) == 3
    first = sources[0]['views'][0]['public']
    assert all(s['views'][0]['public']['source_text'] == first['source_text'] and
               s['views'][0]['public']['referenced_public_sections'] == first['referenced_public_sections']
               for s in sources)
    material = {'source_text': first['source_text'], **{
        'referenced_public_sections.'+k: v for k,v in first['referenced_public_sections'].items()}}
    prior = read(ROOT/'artifacts/legal_skill_evolution_callable_rule_refactor_20261113/protocol.json')
    task = {'law_material': material, 'allowed_calls': sorted(CALLS),
        'allowed_methods': sorted(METHODS),
        'generic_native_task_formats': ['whether a named clause applies or permits a claimed exemption',
                                        'whether a named clause computes an asserted amount or percentage'],
        'actual_case_text_questions_labels_and_other_arm_programs': 'not supplied'}
    paths = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
        ROOT/'tests/test_skill_evolution_callable_rules.py', ROOT/'legal_skill_guard/skill_evolution/source_python.py',
        ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT/'legal_skill_guard/skill_evolution/runtime.py',
        ROOT/'experiments/legal_skill_evolution_teacher_proof_evaluate.py',
        ROOT/'experiments/legal_skill_evolution_callable_rule_audit.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'After condition/effect interface repair, does the proof-skill recipe improve real source reuse over an independently acquired free whole-source program?',
        'scope': 'Three original TRAIN mother cases, one shared statute; no new blind evaluation claim or final two-contribution attribution.',
        'source_ids': [s['key'] for s in sources], 'arms': ARMS,
        'public_manifest': str(public_path.relative_to(ROOT)), 'public_manifest_sha256': sha(public_path),
        'teacher_profile': prior['teacher_profile'], 'executor_profile': prior['executor_profile'],
        'source_only_task_sha256': digest(task),
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'primary_metric': 'Native exact-match core-correct count over all three fixed cases; unsupported/unknown requires separately marked fallback, not a core success.',
        'comparison_information': 'Independent source-only acquisition, same complete law, generic task descriptions, public interface and frozen reader. No shared acquired source rules.',
        'workload': 'Two independent teacher acquisitions, then at most one physical reader request for each supported arm/case. No automatic feedback repair or extension.',
        'freeze_before_first_executor_and_grading': True,
        'decision_if_effect_absorbed': 'Do not enlarge the experiment; record that this recipe has no observed extra task effect and retain the public callable execution asset.',
        'new_full_training_DEV_TEST_or_paper': False}
    immutable_json(OUT/'protocol.json', protocol)
    immutable_json(OUT/'source_only_input.json', task)
    immutable_json(OUT/'output_schema.json', RESULT)
    for p in paths:
        target = OUT/'source_snapshot'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): assert target.read_bytes() == p.read_bytes()
        else: target.write_bytes(p.read_bytes())
    print(json.dumps({'prepared': True, 'sources': protocol['source_ids'], 'no_model_call': True}),flush=True)


def ledger_for(p):
    return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))


def check_bound(p):
    amendment = OUT/'clause_normalization_source_amendment.json'
    if amendment.exists():
        revised = read(amendment)
        assert revised['original_protocol_sha256'] == digest(p)
        source_hashes = revised['source_sha256']
    else:
        source_hashes = p['source_sha256']
    for name,h in source_hashes.items(): assert sha(ROOT/name) == h, name
    assert sha(ROOT/p['public_manifest']) == p['public_manifest_sha256']


def acquire(arm):
    p,public,task = prepared();check_bound(p)
    ledger = ledger_for(p)
    if not (OUT/'ledger_before.json').exists():
        with ledger.transaction() as db:
            rows = [list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json', {'rows': rows})
    r = FrozenTeacher(ledger,OUT/arm,p['teacher_profile']).propose(RUN+':initial:'+arm,
        source_ids=p['source_ids'],system_prompt=COMMON+(METHOD if arm=='ProofSkills' else CONTROL),
        user_prompt=json.dumps(pack(task),ensure_ascii=False),output_schema=RESULT)
    immutable_json(OUT/arm/'teacher.json',r)
    try:
        library = compile_library(r['value'],task['law_material'])
        immutable_json(OUT/arm/'library.json',library)
        immutable_json(OUT/arm/'offline_check.json',{'pure_functions_source_quotes_distinct_heads':True,
            'unit_count':len(library['units']),'semantic_and_actual_case_checks_pending':True,
            'contribution_established':False})
        print(json.dumps({'arm':arm,'units':[(u['clause'],u['kind']) for u in library['units'].values()],
                          'seconds':r['elapsed_seconds']},ensure_ascii=False),flush=True)
    except Exception as error:
        immutable_json(OUT/arm/'offline_check.json',{'error':type(error).__name__+': '+str(error)})
        print(json.dumps({'arm':arm,'error':str(error)}),flush=True)


def execute_trial():
    p,public,task=prepared();check_bound(p)
    libs={arm:read(OUT/arm/'library.json') for arm in ARMS}
    ledger=ledger_for(p)
    with ledger.transaction() as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
        teacher_ids=[r[0] for r in db.execute("select id from calls where role='teacher' order by id")]
    freeze={'protocol_sha256':digest(p),'source_ids':p['source_ids'],
        'library_sha256':{arm:digest(lib) for arm,lib in libs.items()},
        'teacher_ids_at_freeze':teacher_ids,'all_cases_frozen_before_first_reader':True,
        'no_post_case_repair':True,'same_goal':True,'goal_complete':False}
    immutable_json(OUT/'freeze.json',freeze)
    client=FrozenExecutor(ledger,OUT/'execution',p['executor_profile']);client.readiness()
    reads=FrozenReads(client)
    grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    for key in p['source_ids']:
        source=public[key];view=source['views'][0];q=view['public']['question']
        case=deepcopy(view);case['public']={k:v for k,v in view['public'].items() if k in ('facts','question')}
        for arm,lib in libs.items():
            check_bound(p)
            target=OUT/'execution'/arm/key.replace(':','_')/'result.json'
            if target.exists():
                print(json.dumps({'preserved':str(target)}),flush=True);continue
            planned=plan(lib,q,task['law_material'])
            values,event,rejected,error={},None,[],None
            if planned['supported'] and planned['fields']:
                try:
                    raw,event=reads.read(source,case,question=READ_QUESTION,fields=planned['fields'],
                        locator='facts and question',purpose='skill_replay',allow_unresolved=True,require_case_support=True)
                    values,rejected=validate_case_bindings(planned['fields'],raw,event)
                except LocalReadError as e:event=e.event;error=str(e)
            result=evaluate(lib,planned,values)
            execution=trace(entry_program(lib,planned['unit']),{'facts':values}) if planned['supported'] else None
            core=error is None and result['answer'] in ('Entailment','Contradiction')
            record={'source':key,'arm':arm,'question':q,'plan':planned,
                'read_event':event,'read_error':error,'validated_case_values':values,
                'rejected_reader_bindings':rejected,'result':result,'execution':execution,
                'core_executed':core,'fallback_required':not core,'fallback_executed':False,
                'native_score':grade_view(source['dataset'],view,grading[key][view['id']],result['answer']) if core else None,
                'source_and_factual_semantics_review_pending':True,'goal_complete':False}
            immutable_json(target,record)
            print(json.dumps({'arm':arm,'source':key,'answer':result['answer'],'score':record['native_score'],
                'read_error':error,'rejected':rejected}),flush=True)
    with ledger.transaction() as db:
        assert teacher_ids==[r[0] for r in db.execute("select id from calls where role='teacher' order by id")]


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','acquire','execute'])
    parser.add_argument('--arm',choices=ARMS);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_callable_source_trial.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare()
        elif args.action=='acquire':
            assert args.arm;acquire(args.arm)
        else:execute_trial()
