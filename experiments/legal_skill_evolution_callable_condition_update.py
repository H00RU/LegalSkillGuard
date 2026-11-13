"""Acquire missing condition heads from the actual learned source program.

This is an engineering completion, not a new contribution or a fresh case
validation. No executor is dispatched and the four old checks remain closed.
"""
import ast
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_rule_refactor import UNIT
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import compile_library
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_python import merge_functions
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_callable_conditions_20261113'
OUT = ROOT / 'artifacts' / RUN
RESULT = record_schema({'function_updates': {'type': 'array', 'items': {'type': 'string'}},
    'units_additions': {'type': 'array', 'items': UNIT},
    'change_explanation': {'type': 'string'},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}}})
SYSTEM = '''You are the existing authorized skill teacher. Complete the actual
acquired program's interface by exposing source applicability separately from
quantitative consequences. This is a concrete interface repair, not a new
research contribution. No new task or previously checked case is supplied.

Return only NEW one-argument functions taking facts and their new predicate
unit metadata. Preserve ALL existing functions and their meanings. Reuse actual
existing condition calculations where suitable. For a quantitative source head
with a meaningful independently testable legal condition, expose that condition
as predicate. An unconditional definition does not need an invented predicate.
Do not define applicability as amount>0 or any numerical truthiness shortcut.
The original source and existing program determine the condition, including
applicable qualifications, not native query answers or missing field defaults.
Each function returns exactly value:bool/null, used_units:[acquired ids], and
open_dependencies:[strings]. Preserve unknown. All source quotes must be exact
substrings of the supplied source_field. Only predicate additions; no changes
to quantities, original functions, host code or source. Functions use the
existing restricted pure Python environment and can call existing helpers.
Retain the existing factual field names/meanings; the runtime receives only
facts, never a native question, claim or label. The host directly calls the
declared function: do not rewrite apply or add dispatch code. If something is
not derivable from the acquired logic/source, report unresolved rather than
inventing a rule. Mark origin honestly. No case labels or future cases appear.
''' + INSTRUCTION


def run():
    parent = ROOT / 'artifacts/legal_skill_evolution_callable_rule_refactor_20261113'
    prior = read(parent / 'protocol.json')
    response = read(parent / 'teacher.json')['value']
    material = read(parent / 'input.json')['law_material']
    task = {'law_material': material, 'actual_acquired_program_and_units': response,
        'precise_offline_issue': 'Quantitative conditional rules have no separate predicate output; an applicability query cannot be answered by a quantity head.',
        'host_now_calls_declared_function_directly': True,
        'no_native_cases_questions_labels_or_old_check_results': True}
    paths = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
        ROOT/'tests/test_skill_evolution_callable_rules.py', ROOT/'legal_skill_guard/skill_evolution/source_python.py',
        ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'source_ids': prior['source_ids'], 'teacher_profile': prior['teacher_profile'],
        'executor_profile': prior['executor_profile'], 'task_sha256': digest(task),
        'system_sha256': digest(SYSTEM), 'new_executor_queue': False,
        'workload': 'One changed-code condition-interface teacher completion, no native validation.',
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}}
    immutable_json(OUT/'protocol.json', protocol)
    immutable_json(OUT/'input.json', task)
    immutable_json(OUT/'output_schema.json', RESULT)
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        rows = [list(r) for r in db.execute('select * from calls order by id')]
    assert not any(r[6] == 'reserved' for r in rows)
    immutable_json(OUT/'ledger_before.json', {'rows': rows})
    for p in paths:
        target = OUT/'source_snapshot'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): assert target.read_bytes() == p.read_bytes()
        else: target.write_bytes(p.read_bytes())
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': prior['source_ids'], 'dev': [], 'test': []}, binding=digest(protocol))
    result = FrozenTeacher(ledger, OUT, prior['teacher_profile']).propose(RUN+':one',
        source_ids=prior['source_ids'], system_prompt=SYSTEM,
        user_prompt=json.dumps(pack(task), ensure_ascii=False), output_schema=RESULT)
    immutable_json(OUT/'teacher.json', result)
    try:
        updates = result['value']
        old = {n.name: ast.dump(n) for n in ast.parse(response['program']).body}
        new_names = [ast.parse(code).body[0].name for code in updates['function_updates']]
        assert not set(new_names) & set(old), 'Existing source functions must stay unchanged'
        assert all(u['kind'] == 'predicate' for u in updates['units_additions'])
        combined = {**response, 'program': merge_functions(response['program'], updates['function_updates']),
                    'units': response['units'] + updates['units_additions']}
        library = compile_library(combined, material)
        after = {n.name: ast.dump(n) for n in ast.parse(library['program']).body}
        assert all(after[name] == tree for name, tree in old.items())
        immutable_json(OUT/'library.json', library)
        immutable_json(OUT/'combined_response.json', combined)
        immutable_json(OUT/'offline_check.json', {'existing_legal_functions_AST_unchanged': True,
            'pure_source_quoted_distinct_heads': True, 'new_predicate_count': len(updates['units_additions']),
            'native_validation_or_contribution_gain': False, 'goal_complete': False})
        print(json.dumps({'new_predicates': [(u['clause'],u['function']) for u in updates['units_additions']],
            'seconds': result['elapsed_seconds']},ensure_ascii=False),flush=True)
    except Exception as error:
        immutable_json(OUT/'offline_check.json', {'error': type(error).__name__+': '+str(error)})
        print(json.dumps({'error': str(error)}),flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_callable_conditions.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
