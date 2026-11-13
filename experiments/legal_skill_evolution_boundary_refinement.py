"""Finite TRAIN test of learned perception/computation boundary refinement.

One exposed date failure supplies feedback. Three original TRAIN sources are
fixed before dispatch; their case text/questions/labels never enter teachers.
FreeReflect shares the actual seed to isolate updating. PrimitiveGiven learns
independently from the same source and feedback with the strongest simple rule.
This is an early screen, not a final two-contribution ablation or full training.
"""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_callable_rule_audit import trace
from experiments.legal_skill_evolution_scoped_premise_repair import RESULT as PATCH_RESULT
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_evaluate import READ_QUESTION, validate_case_bindings
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import bind_case_premises, compile_library, entry_program, evaluate, plan
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError
from legal_skill_guard.skill_evolution.source_python import CALENDAR_CALLS, merge_functions
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_boundary_refinement_role_grounding_20261113'
OUT = ROOT/'artifacts'/RUN
PARENT = ROOT/'artifacts/legal_skill_evolution_scoped_premise_repair_20261113'
PREFLIGHT = ROOT/'artifacts/legal_skill_evolution_boundary_refinement_20261113'
ARMS = ['BoundaryRefine', 'FreeReflect', 'PrimitiveGiven']
FACT_READING = READ_QUESTION + '''
Role descriptions in field questions are references to be grounded using this
case and query; they do not assert an entity's identity or factual relation.
Return unknown if the role is ambiguous or cannot be grounded from the case.
For a requested explicit calendar date, normalize a fully stated date to
YYYY-MM-DD and cite the original date wording. Do not invent month/day for a
year-only event, or dates for an unstated event. Do not perform the source
program's date arithmetic as a supposedly GIVEN legal intermediate.
'''
CALIBRATION = 'SARA_v2_Binary:5c29a3a22f755d6a6253919de3327553f029a75827c72238547ebb6701b5ace7'
TRANSFER = [
    'SARA_v2_Binary:cd2ab8fce3d25740d6ad04c3da6bdf402d073fbda38e436514495535e29d54d2',
    'SARA_v2_Binary:982d531617be833561b376c657b68c25ddbbd8dffa5972076a8c8e8d23264bf9',
    'SARA_v2_Binary:250fc5e766b40779976e11126e6d495d8606971c0e3287c28a0400fcc2683362',
]
HEADS = ['152(c)(1)', '2(a)(1)(A)', '3306(c)(21)', '3306(c)(10)(A)(i)']
CONTRACT = record_schema({'name': {'type':'string'}, 'function': {'type':'string'},
    'consumers': {'type':'array','items':{'type':'string'}},
    'observations': {'type':'array','items':{'type':'string'}}, 'description': {'type':'string'}})
RESULT = record_schema({**PATCH_RESULT['properties'],
    'refinement_contracts': {'type':'array','items':CONTRACT}})
COMMON = '''You are the authorized skill teacher. Implement this finite original
TRAIN learning screen, not a design report. All arms have identical original
law, old factual feedback, public arithmetic, model and scope interfaces.
No later case text, native question or grading label is supplied. No weights
are changed. Focus only on the four listed callable source heads. Preserve
other acquired behavior. Acquire genuinely missing source rules from the given
law, and label new source acquisition honestly. Exact source witnesses remain
mandatory. Do not invent facts, legal connections or example-specific branches.

Return function_updates (one complete pure function each), unit_updates, notes
and refinement_contracts (actual shared observation/resolution helpers, if any).
Unit functions take a single facts mapping and return exactly value (bool or
null for these predicates), used_units and open_dependencies. The host calls
the declared function; apply(inputs,premises) is a required stub. It supplies
declared literal query arguments and independently supported case fields, never
the asserted claim, original question, grading label, source id or position.
Unit arguments declare name,type,selector (year/subject/taxpayer/individual/
employer/employee). Fields declare name,type,question; question placeholders
must be declared argument names. Exact current interface/schema are provided.
Use parameters; no fixed names/years/outcomes from the calibration case.

Truth of an explicit GIVEN legal intermediate can be consumed as a premise,
with the correct roles/year/source. A GIVEN subcondition is not its entire
parent clause. Neither query text nor absence of a GIVEN is such a premise.
Missing neural reads and missing learned rules remain unresolved. The native
SARA task is binary Prolog with local negation-as-failure and documented local
event defaults: do not require explicit negative sentences for every guard,
but never turn unparsed text or a missing rule into false. Calendar tax years
match calendar years. No separate individual evidence gate is needed for an
already GIVEN personal exemption entitlement. These are public task semantics,
not extra supervision from official case formalizations or answer labels.

The observed failure is a known-True high-level residence predicate that is
inconsistent with its actual dates. Unknown-only proof-frontier repair misses
it. Raw dates and case quotations must be read anew by the frozen executor;
the host will not copy the reference counterexample value into case bindings.
Retain direct GIVEN entry points, so moving computation to Python does not
force rebuilding antecedents that the original case already stipulates.

Pure functions only, no imports, IO, globals, classes, models or introspection.
The shared runtime provides calendar_year(ISO), year_days(int),
inclusive_year_overlap_days(startISO,endISO,year), and
elapsed_year_overlap_days(startISO,endISO,year); all validate inputs and raise
on missing/invalid dates. The last uses midnight timestamp differences; it is
not the inclusive count. These utilities contain no legal thresholds/rules.
Every source-specific comparison/condition/role must come from supplied law.
Unknown dates are not made up. Date normalization to ISO may quote the actual
spelled-out date; it is factual formatting, not legal inference. Ordinary
factual event grounding is allowed; do not add new evidentiary requirements.
Same-source aliases and repeated code are not learning gains. Report limits.
''' + INSTRUCTION
POLICY = {
    'BoundaryRefine': '''Learn a reusable refinement of the faulty perception/
computation boundary. Localize the causal known-input counterexample, replace
the opaque derived predicate with raw observation ports plus a source-backed
resolver, preserve the explicit GIVEN branch, and use the learned temporal
observation/resolution contract in the new source consumers where appropriate.
The source-specific temporal relation may differ: acquire it from its law,
never copy the half-year threshold to unrelated rules. Persist the actual
shared contract and its consumers in refinement_contracts; code must call it.
Do not merely add a case-specific string match or more coarse boolean questions.
''',
    'FreeReflect': '''Use the strongest ordinary free reflection/update from
the same actual seed, original law and factual feedback. Freely repair any
function, reader contract and consumer, introduce shared helpers, use primitive
dates, preserve GIVEN, and choose the same architecture if useful. There is no
candidate-specific update recipe or restriction to prompt-only edits. Optimize
native reliability at comparable complete acquisition/update/reading cost.
''',
    'PrimitiveGiven': '''Independently acquire the strongest simple full-source
program for these heads, without another arm's program. Use primitive-first
and GIVEN-first from the start: have Python perform date/numerical comparisons,
and consume explicit scoped legal premises before reconstructing antecedents.
Use all common utilities, source material and factual feedback. Choose any
organization/shared helpers and expose all four heads where supported. You may
use the same architecture. Do not artificially keep coarse neural arithmetic
or omit meaningful rules. Include a pure apply stub in function_updates.
'''
}


def prepare():
    old = read(PARENT/'protocol.json')
    public_path = ROOT/old['public_manifest']
    public = {s['key']:s for s in read(public_path)}
    seed = read(PARENT/'ProofSkills/library.json')
    material = deepcopy(seed['law_material'])
    for key in TRANSFER:
        text = public[key]['views'][0]['public']['source_text']
        section = text.split('.')[0].lstrip('§')
        name = 'transfer_source_'+section
        assert name not in material or material[name] == text
        material[name] = text
    actual = read(PARENT/'execution/transfer/ProofSkills'/CALIBRATION.replace(':','_')/'result.json')
    # No result.native_score, grading labels or future material bodies enter feedback.
    feedback = {'case': {k:public[CALIBRATION]['views'][0]['public'][k] for k in ('facts','question')},
        'original_plan': actual['plan'], 'actual_case_values': actual['case_values'],
        'raw_read_event': actual['read_event'], 'actual_execution': actual['execution'],
        'calendar_counterexample': read(PARENT/'calendar_boundary_refutation.json')}
    shared = {'law_material':material,'focused_callable_heads':HEADS,
        'old_TRAIN_factual_feedback':feedback,
        'shared_calendar_primitives':(ROOT/'legal_skill_guard/skill_evolution/calendar_ops.py').read_text(),
        'host_contract':(ROOT/'legal_skill_guard/skill_evolution/callable_rules.py').read_text(),
        'allowed_calls':sorted(CALLS|CALENDAR_CALLS),'allowed_methods':sorted(METHODS|{'setdefault'}),
        'later_case_text_questions_labels': 'not supplied'}
    paths = [Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
        ROOT/'legal_skill_guard/skill_evolution/query_scope.py',ROOT/'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT/'legal_skill_guard/skill_evolution/source_python.py',ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT/'legal_skill_guard/skill_evolution/runtime.py',ROOT/'legal_skill_guard/skill_evolution/clients.py']
    p = {'run_id':RUN,'same_goal':True,'goal_complete':False,'arms':ARMS,
        'calibration_source':CALIBRATION,'transfer_sources':TRANSFER,
        'source_ids':[CALIBRATION]+TRANSFER,'public_manifest':old['public_manifest'],
        'public_sha256':sha(public_path),'teacher_profile':old['teacher_profile'],
        'executor_profile':old['executor_profile'],'source_sha256':{str(f.relative_to(ROOT)):sha(f) for f in paths},
        'focused_source_heads':HEADS,'offline_regressions_passed':36,
        'preflight_parent_protocol_sha256':sha(PREFLIGHT/'protocol.json'),
        'public_pre_executor_change':'Factual role references need not have literal query names; missing periods remain blocked. Shared query arguments and all learned legal code remain factual-value-free. Explicit dates request ISO formatting.',
        'reused_settled_teachers':{a:sha(PREFLIGHT/a/'teacher.json') for a in ARMS[:2]},
        'comparison':'Shared actual seed for BoundaryRefine/FreeReflect isolates update; PrimitiveGiven independently acquires from same original source and factual feedback. All historical acquisition/update costs must be reported; not a final independent two-factor ablation.',
        'workload':'One teacher per arm; freeze all before one facts-only reader per supported arm/case. Old152 calibration separately from three fixed original TRAIN checks. No same-input repeats; no post-transfer retuning.',
        'decision':'Check actual learned resolver use and native/source correctness versus strong simple controls. If absorbed, do not expand this instance or count it as a contribution.',
        'no_new_sources_full_training_DEV_TEST_or_paper':True}
    immutable_json(OUT/'protocol.json',p);immutable_json(OUT/'output_schema.json',RESULT)
    immutable_json(OUT/'shared_input.json',shared)
    for arm in ARMS:
        task=deepcopy(shared)
        if arm!='PrimitiveGiven':task['actual_seed']={'program':seed['program'],'units':list(seed['units'].values())}
        # Metadata keys that could inadvertently leak evaluation must be absent.
        def check(value):
            if isinstance(value,dict):
                assert not set(value)&{'native_score','grade','correct','grading_label','expected_answer','original_raw_score'}
                for v in value.values():check(v)
            elif isinstance(value,list):
                for v in value:check(v)
        check(task)
        if arm in ARMS[:2]:
            # Reuse settled acquisitions byte-for-byte. They are not repeated
            # after this public host-only correction or relabelled as new calls.
            for name in ('input.json','system.json','teacher.json','library.json','offline_check.json'):
                immutable_json(OUT/arm/name,read(PREFLIGHT/arm/name))
        else:
            immutable_json(OUT/arm/'input.json',task)
            immutable_json(OUT/arm/'system.json',{'system':COMMON+POLICY[arm]})
    for f in paths:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==f.read_bytes()
        else:target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':True,'calibration':1,'fixed_transfer':len(TRANSFER),'arms':ARMS,'new_calls':0}),flush=True)


def state():
    p=read(OUT/'protocol.json')
    assert sha(ROOT/p['public_manifest'])==p['public_sha256']
    assert all(sha(ROOT/n)==h for n,h in p['source_sha256'].items())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['source_ids'],'dev':[],'test':[]},binding=digest(p))
    return p,ledger


def acquire(arm):
    p,ledger=state();task=read(OUT/arm/'input.json')
    if arm in p['reused_settled_teachers']:
        assert sha(OUT/arm/'teacher.json')==p['reused_settled_teachers'][arm]
        print(json.dumps({'arm':arm,'reused_settled_acquisition':True,'new_physical_requests':0}),flush=True)
        return
    if not (OUT/'ledger_before.json').exists():
        with ledger.transaction() as db:rows=[list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6]=='reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json',{'rows':rows})
    r=FrozenTeacher(ledger,OUT/arm,p['teacher_profile']).propose(RUN+':learn:'+arm,
        source_ids=[p['calibration_source']]+p['transfer_sources'],
        system_prompt=read(OUT/arm/'system.json')['system'],user_prompt=json.dumps(pack(task),ensure_ascii=False),output_schema=RESULT)
    immutable_json(OUT/arm/'teacher.json',r)
    try:
        old=task.get('actual_seed',{'program':'def apply(inputs,premises):\n    return None\n','units':[]})
        change=r['value'];units={u['id']:u for u in old['units']};seen=set()
        for u in change['unit_updates']:
            assert u['id'] not in seen;seen.add(u['id'])
            if u['id'] in units:assert (u['clause'],u['kind'])==(units[u['id']]['clause'],units[u['id']]['kind'])
            units[u['id']]=u
        lib=compile_library({'program':merge_functions(old['program'],change['function_updates']),
                             'units':list(units.values())},task['law_material'])
        immutable_json(OUT/arm/'library.json',lib)
        immutable_json(OUT/arm/'offline_check.json',{'typed_contracts_exact_source_quotes':True,
            'updated_functions':len(change['function_updates']),'updated_units':len(change['unit_updates']),
            'learned_contracts':change['refinement_contracts'],'real_execution_pending':True})
        print(json.dumps({'arm':arm,'functions':len(change['function_updates']),'units':len(change['unit_updates']),
                          'seconds':r['elapsed_seconds']},ensure_ascii=False),flush=True)
    except Exception as e:
        immutable_json(OUT/arm/'offline_check.json',{'error':type(e).__name__+': '+str(e)})
        print(json.dumps({'arm':arm,'error':str(e)}),flush=True)


def execute():
    p,ledger=state();libs={a:read(OUT/a/'library.json') for a in ARMS}
    with ledger.transaction() as db:assert not db.execute("select id from calls where status='reserved'").fetchall()
    immutable_json(OUT/'freeze.json',{'protocol_sha256':digest(p),'libraries':{a:digest(l) for a,l in libs.items()},
        'before_first_new_executor':True,'future_cases_not_supplied_to_teachers':True})
    public={s['key']:s for s in read(ROOT/p['public_manifest'])}
    grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    client=FrozenExecutor(ledger,OUT/'execution',p['executor_profile']);client.readiness();reads=FrozenReads(client)
    for stage,keys in [('calibration',[CALIBRATION]),('transfer',TRANSFER)]:
        for key in keys:
            source=public[key];view=source['views'][0];raw=view['public']
            material={'source_text':raw['source_text'],**{'referenced_public_sections.'+k:v for k,v in raw['referenced_public_sections'].items()}}
            for arm,lib in libs.items():
                state();target=OUT/'execution'/stage/arm/key.replace(':','_')/'result.json'
                if target.exists():continue
                planned=plan(lib,raw['question'],material);values,event,rejected,error={},None,[],None
                if planned['supported'] and planned['fields']:
                    try:
                        fresh,event=reads.read(source,{**view,'public':{'facts':raw['facts']}},question=FACT_READING,
                            fields=planned['fields'],locator='case facts only; literal query arguments supplied as scope',
                            invocation_arguments={'current_question':raw['question'],'query_arguments':planned['query_arguments']},
                            purpose='skill_replay',allow_unresolved=True,require_case_support=True)
                        checked,rejected=validate_case_bindings(planned['fields'],fresh,event)
                        values,more=bind_case_premises(checked,event);rejected+=more
                    except LocalReadError as e:event=e.event;error=str(e)
                result=evaluate(lib,planned,values)
                execution=trace(entry_program(lib,planned['unit']),{'facts':{**planned['query_arguments'],**values}}) if planned['supported'] else None
                core=error is None and result['answer'] in ('Entailment','Contradiction')
                declared=read(OUT/arm/'teacher.json')['value']['refinement_contracts']
                called={c['function'] for c in (execution or {}).get('calls',[])}
                record={'stage':stage,'arm':arm,'source':key,'query':raw['question'],'plan':planned,
                    'read_event':event,'read_error':error,'case_values':values,'rejected':rejected,'result':result,
                    'execution':execution,'declared_contract_functions_actually_called':[c['function'] for c in declared if c['function'] in called],
                    'core_executed':core,'fallback_required':not core,'fallback_executed':False,
                    'native_score':grade_view(source['dataset'],view,grading[key][view['id']],result['answer']) if core else None,
                    'semantic_review_pending':True,'final_two_contribution_ablation':False,'goal_complete':False}
                immutable_json(target,record)
                print(json.dumps({k:record[k] for k in ('stage','arm','source','result','native_score','read_error')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','acquire','execute']);parser.add_argument('--arm',choices=ARMS)
    args=parser.parse_args()
    lock_path=ROOT/'artifacts/rr_v2_preflight/current_boundary_refinement.lock'
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare()
        elif args.action=='acquire':assert args.arm;acquire(args.arm)
        else:execute()
