"""Independent teacher acquisition on fixed original SARA TRAIN material.

The teacher performs learning. This runner reuses pure-Python execution and
the continuous ledger; it does not invent a second host induction algorithm.
Initial acquisition is source-only. No executor call is dispatched here.
"""
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_python import execute, validate
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_teacher_proof_skills_20261113'
OUT = ROOT/'artifacts'/RUN
RESULT = record_schema({
    'learning_object': {'type': 'string'},
    'program': {'type': 'string'},
    'source_rules': {'type': 'array', 'items': record_schema({
        'id': {'type': 'string'}, 'source_field': {'type': 'string'},
        'quote': {'type': 'string'}, 'function': {'type': 'string'}})},
    'expected_reuse': {'type': 'string'},
    'remaining_unknown': {'type': 'array', 'items': {'type': 'string'}},
})
COMMON = '''You are the existing skill teacher. Learn an executable, reusable
external statutory reasoning skill from the supplied original law. Both models
are frozen. YOU perform acquisition and later feedback-driven revision; a new
non-LLM learner is not required. Mature algorithms and module combinations are
allowed. Do not merely describe an algorithm: return working Python.

Common execution API (also available to the independent strong control): pure
function definitions and exactly one apply(inputs, premises). No imports,
files/network/tools, introspection, decorators or model calls in the program.
The supplied allowed_calls and allowed_methods specify the existing execution
environment; re is already available. Return ordinary JSON values.

inputs.phase='plan', inputs.question=<current public native question>:
return {'supported': bool, 'fields': {name: {'type': one of boolean/integer/
number/string, 'question': literal factual extraction question}}}.
Request primitive case facts and quantities from the native question, not
whether the legal query is true, rule applicability, legal entitlement or other
derived legal conclusions. Runtime will ask the frozen executor for these facts.

inputs.phase='evaluate', inputs.question=<same question>, inputs.facts=<known
primitive values only>: return {'answer': 'Entailment'/'Contradiction'/'unknown',
'used_rule_ids': [declared source-rule ids], 'open_dependencies': [strings]}.
Missing factual values stay unknown; never default them to False/0/empty or
invent facts. Compute legal conclusions in the actual acquired program. Public
question citation/claim parsing is allowed; a clause citation is not a verdict.

The acquisition input contains source law and two current task formats, but NO
case facts or labels. Learn parameterized legal behavior usable on later cases
and other questions about this supplied law, rather than caching two answers.
All constants/qualifications must come from the provided law. source_rules
quotes must be exact substrings of their source_field. Cite actual functions
that implement them. This is a finite first prototype, not a demand to formalize
every detail of the entire statute. Honest unsupported/unknown is allowed and
will be reported as uncovered, never as core success.

The control may use the same API, source scope, decomposition, proof organization,
memory and public fixes. Python expressibility and teacher-generated programs
do not refute a contribution. Only actual independent comparisons will decide.
No DEV/TEST, new cases, fabricated rules, source-ID answer branches or weights.
''' + INSTRUCTION

METHOD = '''Implement teacher-distilled legal proof skills. Organize acquired
legal definitions and applicable opposing/exception conditions into reusable
functions. Establish a native conclusion by evaluating source-supported rules;
neural extraction is confined to primitive facts. Preserve relevant unresolved
support and exception obligations. This initial acquisition precedes any source
feedback revision. The same law and public fixes are available to the control.
'''
CONTROL = '''Independently acquire the strongest ordinary executable source
policy/cache in free Python. You may compile the whole supplied law in one pass,
use functions, lazy evaluation, the same proof organization, exceptions, memory
and all source information. Choose whichever approach best supports reliable
reuse at low complete acquisition/execution cost. Do not weaken yourself or
omit relevant exceptions to create a difference. This is independent acquisition,
not a request to copy the other arm's learned code.
'''


def prepare():
    prior = read(ROOT/'artifacts/legal_skill_evolution_refutation_learning_20261113/protocol.json')
    public_path = ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    sources = [s for s in read(public_path) if s['dataset'] == 'SARA_v2_Binary'
               and s['views'][0]['public']['source_text'].startswith('§63.')]
    assert len(sources) == 6
    first = sources[0]['views'][0]['public']
    material = {'source_text': first['source_text'], **{
        'referenced_public_sections.'+k: v
        for k, v in first['referenced_public_sections'].items()}}
    assert all(s['views'][0]['public']['source_text'] == first['source_text']
               and s['views'][0]['public']['referenced_public_sections'] == first['referenced_public_sections']
               for s in sources)
    task = {'law_material': material,
            'initial_task_formats': [s['views'][0]['public']['question'] for s in sources[:2]],
            'allowed_calls': sorted(CALLS), 'allowed_methods': sorted(METHODS),
            'candidate_design_also_available_to_control': METHOD,
            'scope': 'Original six §63 TRAIN mothers, original order; two feedback cases then four frozen checks. No new blind-test claim.'}
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
         'teacher_performs_learning': True, 'no_independent_host_inducer_required': True,
         'source_ids': [s['key'] for s in sources],
         'acquisition_and_feedback_sources': [s['key'] for s in sources[:2]],
         'frozen_check_sources': [s['key'] for s in sources[2:]],
         'initial_teacher_input_excludes_case_facts_labels_and_later_questions': True,
         'comparison': ['TeacherProof', 'IndependentSourceCache'],
         'teacher_profile': prior['teacher_profile'],
         'executor_profile': prior['executor_profile'],
         'initial_workload': 'Two independent teacher acquisitions; executor only after code and factual-interface review. No auto-retry.',
         'later_revision_question': 'Does support/defeat proof feedback improve teacher revision versus ordinary reflection with identical information?',
         'new_full_training_DEV_TEST_or_paper': False,
         'public_manifest_sha256': sha(public_path),
         'implementation_sha256': sha(Path(__file__)), 'task_sha256': digest(task)}
    immutable_json(OUT/'protocol.json', p)
    immutable_json(OUT/'source_only_input.json', task)
    immutable_json(OUT/'output_schema.json', RESULT)
    if not (OUT/'ledger_before.json').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
            rows = [list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json', {'rows': rows})
    return p, task, sources


def one(arm, instruction, protocol, task, sources):
    folder = OUT/arm
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': protocol['source_ids'], 'dev': [], 'test': []},
        binding=digest(protocol))
    teacher = FrozenTeacher(ledger, folder, protocol['teacher_profile'])
    response = teacher.propose(RUN+':initial:'+arm,
        source_ids=protocol['acquisition_and_feedback_sources'],
        system_prompt=COMMON+instruction,
        user_prompt=json.dumps(pack(task), ensure_ascii=False), output_schema=RESULT)
    immutable_json(folder/'teacher.json', response)
    value = response['value']
    # Scientific validation failures do not rewrite a physically completed call.
    try:
        validate(value['program'])
        functions = {n.name for n in ast.parse(value['program']).body}
        for rule in value['source_rules']:
            assert rule['quote'] and rule['quote'] in task['law_material'][rule['source_field']]
            assert rule['function'] in functions
        plans = [execute(value['program'], {'phase': 'plan', 'question': q})
                 for q in task['initial_task_formats']]
        immutable_json(folder/'offline_acquisition_check.json', {
            'pure_python_and_exact_source_quotes_valid': True,
            'initial_plans': plans, 'factual_interface_semantics_review_pending': True,
            'native_execution_or_contribution_established': False})
        return {'arm': arm, 'acquired': True, 'initial_plans': plans,
                'elapsed_seconds': response['elapsed_seconds']}
    except Exception as error:
        immutable_json(folder/'offline_acquisition_check.json', {
            'validation_error': type(error).__name__+': '+str(error),
            'native_execution_or_contribution_established': False})
        return {'arm': arm, 'acquired': False,
                'validation_error': type(error).__name__+': '+str(error)}


def run():
    p, task, sources = prepare()
    print(json.dumps({'stage': 'two_independent_source_only_teacher_acquisitions',
                      'executor_calls_queued': 0}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(one, name, prompt, p, task, sources)
                   for name, prompt in [('TeacherProof', METHOD), ('IndependentSourceCache', CONTROL)]]
        for future in as_completed(pending):
            print(json.dumps(future.result(), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_teacher_proof_skills.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
