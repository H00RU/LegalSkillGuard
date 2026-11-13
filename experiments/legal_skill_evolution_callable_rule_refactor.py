"""Teacher refactors acquired source logic into independently callable heads.

Engineering acquisition only: the previous four checks remain closed. No
executor or validation queue is created by obtaining this interface artifact.
"""
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import compile_library
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_callable_rule_refactor_20261113'
OUT = ROOT/'artifacts'/RUN
FIELD = record_schema({'name': {'type': 'string'},
    'type': {'type': 'string', 'enum': ['boolean', 'integer', 'number', 'string']},
    'question': {'type': 'string'}})
UNIT = record_schema({'id': {'type': 'string'}, 'clause': {'type': 'string'},
    'kind': {'type': 'string', 'enum': ['predicate', 'quantity']},
    'property': {'type': 'string'}, 'function': {'type': 'string'},
    'fields': {'type': 'array', 'items': FIELD},
    'source_field': {'type': 'string'}, 'quote': {'type': 'string'},
    'origin': {'type': 'string', 'enum': ['reused_acquired_logic', 'new_source_acquisition']}})
RESULT = record_schema({'program': {'type': 'string'},
    'units': {'type': 'array', 'items': UNIT},
    'refactor_notes': {'type': 'string'},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}}})
SYSTEM = '''You are the authorized existing skill teacher. Refactor your actual
acquired legal program into independently callable source-backed properties.
The previous artifact learned source clauses inside aggregate calculations but
only exposed two native question routes. We are fixing this implementation gap,
not declaring a new contribution or requiring a host induction algorithm.

Return working pure Python plus rule-unit metadata. Reuse actually acquired
legal logic and GIVEN handling; do not reproduce a question-answer classifier.
Expose separately meaningful source subclauses already used inside compound
calculations, not just the two old native roots. A positive rule and its source
qualifications must remain together. Preserve old field names/meanings where
possible. Unavailable conditions stay unknown; do not invent missing rules.
If you acquire additional provided-source logic, label it new_source_acquisition
rather than pretending it was a deterministic adaptation of the old program.

Each unit has a canonical clause identifier such as63(c)(6)(A), a kind predicate
or quantity, a precise intrinsic property description, factual input questions,
an actual function and an exact source quote. Predicate means the truth of the
source clause's applicability condition. Quantity means the applicable source
quantity for the bound case, not a truth label and not an unconstrained amount
parameter. If no unambiguous property can be exposed, report it unresolved.
The host matches one literal query citation and compares the computed property
with the native claim. Do not put native questions, amounts asserted in the
question, labels, source IDs or example positions into a legal decision branch.

Exactly one apply(inputs,premises) entry and pure function definitions; no imports,
files/network/tools, introspection, model calls or decorators. Allowed primitive
calls/methods and the actual host implementation are supplied. apply receives
ONLY {'unit': acquired_unit_id, 'facts': supported_known_case_values}; no native
question, claimed amount or labels. It returns exactly {'value': boolean/number/
null, 'used_units': [acquired ids], 'open_dependencies': [strings]}.
Return null when required facts or rules are unresolved. A definite value must
have no blocking open_dependencies. Do not turn unknown intoFalse/0/empty.

Factual questions may use the taxpayer/spouse/period named in the current native
question, which the common reader receives as context. They must request case
facts or legal intermediates explicitly GIVEN in case facts, not inferred
entitlement or the native verdict. Preserve the distinction between a stated
component amount and a total computed from components. The host, not your norm
functions, gets the native claim for comparison. No old frozen-check case texts,
questions, labels or results are supplied, and obtaining units alone is not a
new empirical validation or proof of two contributions.
''' + INSTRUCTION


def run():
    parent = ROOT/'artifacts/legal_skill_evolution_teacher_proof_skills_20261113'
    old = read(parent/'protocol.json')
    material = read(parent/'source_only_input.json')['law_material']
    acquired = read(parent/'revised_execution/Full/bundle.json')
    task = {'law_material': material, 'actual_acquired_program_and_source_rules': acquired,
        'actual_host_interface': (ROOT/'legal_skill_guard/skill_evolution/callable_rules.py').read_text(),
        'allowed_calls': sorted(CALLS), 'allowed_methods': sorted(METHODS),
        'no_current_or_closed_validation_case_text_question_label': True}
    files = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
             ROOT/'tests/test_skill_evolution_callable_rules.py',
             ROOT/'legal_skill_guard/skill_evolution/source_python.py',
             ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py',
             ROOT/'legal_skill_guard/skill_evolution/claim_scope.py']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'scope': 'Semantic refactor/re-acquisition of actual prior TRAIN source logic; not an independently acquired new method or fresh held-out success.',
        'source_ids': old['acquisition_and_feedback_sources'],
        'teacher_profile': old['teacher_profile'], 'executor_profile': old['executor_profile'],
        'parent_learned_bundle_sha256': digest(acquired), 'law_material_sha256': digest(material),
        'task_sha256': digest(task), 'system_sha256': digest(SYSTEM),
        'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in files},
        'workload': 'One teacher refactor acquisition; no executor/validation auto-start. Existing four checks remain closed.',
        'standalone_host_learner_or_new_low_level_algorithm_required': False,
        'no_new_source_seed_full_training_DEV_TEST_or_paper': True}
    immutable_json(OUT/'protocol.json', p); immutable_json(OUT/'input.json', task)
    immutable_json(OUT/'output_schema.json', RESULT)
    if not (OUT/'ledger_before.json').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
            rows = [list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json', {'rows': rows})
    for f in files:
        target = OUT/'source_snapshot'/f.relative_to(ROOT)
        if target.exists(): assert target.read_bytes() == f.read_bytes()
        else:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))
    r = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN+':one',
        source_ids=p['source_ids'], system_prompt=SYSTEM,
        user_prompt=json.dumps(pack(task), ensure_ascii=False), output_schema=RESULT)
    immutable_json(OUT/'teacher.json', r)
    try:
        library = compile_library(r['value'], material)
        immutable_json(OUT/'library.json', library)
        immutable_json(OUT/'offline_check.json', {'pure_code_unique_heads_exact_source_quotes': True,
            'unit_count': len(library['units']), 'semantic_review_and_actual_replay_pending': True,
            'goal_complete': False})
        print(json.dumps({'units': [(u['clause'],u['kind'],u['origin']) for u in r['value']['units']],
                          'seconds': r['elapsed_seconds']}, ensure_ascii=False), flush=True)
    except Exception as error:
        immutable_json(OUT/'offline_check.json', {'validation_error': type(error).__name__+': '+str(error)})
        print(json.dumps({'validation_error': str(error)}), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_callable_rule_refactor.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
