"""Matched acquisition of case-observation contracts for unchanged kernels.

One actual binding-error episode is training feedback. The other two original
TRAIN facts/labels remain outside both teachers' inputs. FreeHistory has the
same information, schema/adapter capacity and common legal kernels.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_execution_kernel_bank as base
from experiments import legal_skill_evolution_execution_kernel_repair as repair
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS, validate_procedure


ROOT = base.ROOT
RUN = 'legal_skill_evolution_case_observation_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = ('ProgramGuided', 'FreeHistory')
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'contracts': {'type': 'array',
    'items': record_schema({'kernel_name': {'type': 'string'},
        'requires_neural_read': {'type': 'boolean'}, 'observation_prompt': {'type': 'string'},
        'observation_schema_json': {'type': 'string'}, 'binding_program': {'type': 'string'}})}})
COMMON = '''Learn reusable case-observation contracts around the SAME correct
legal kernels. Do not use tools. All model weights remain frozen. Do not change
the legal programs, thresholds, source meanings or answer policy. This experiment
isolates case grounding/execution, not independent legal-rule acquisition.

You have the same actual incorrect paid read, exact case/roles, original correct
family subrule, source review and shared new source-only kernels as the other
arm. The two future original TRAIN case facts and annotations are WITHHELD.
All generic, source-correct factual projections and correct repair reuse are
available. Do not key on source IDs, names such as Alice/Bob, fixed case amounts,
years, native labels or expected answers. No fabricated case examples.

Return one contract per supplied kernel. observation_schema_json is a COMPLETE
JSON Schema for a factual observation requested from the frozen8B if needed.
Keep schema compact, no artificial string length bounds, additionalProperties
false for declared records. You may choose direct fields, source-linked tuples,
events or another factual view. observation_prompt describes the factual task,
not statutory applicability, legal eligibility or the final answer. The runtime
keeps full current law context and distinguishes facts/question from law text.
Facts must retain actual roles and exact current case/question witness quotes.
Unknown is not false, zero or an empty factual record. In the original SARA
finite case semantics, an absent case predicate and a failed extraction differ.

binding_program is a compact pure complete module with apply(inputs,premises).
inputs contains kernel (name,program,input_fields_json,scope), public_case with
facts/question, literal_context (literal current query roles and positive family
mentions), and observation (raw JSON or null before a neural read). It returns
exactly {bindings:[{inputs:{port:value,...},witnesses:[{field:'facts'|'question',
quote:nonempty_verbatim_current_substring},...]}],unresolved:[reason,...]}.
Use original declared kernel port names and JSON types. Unknown inputs are
omitted, not None or default values. Evidence may be copied from literal case
text even when deterministic parsing needs no neural read. Legal-rule text alone
cannot be case evidence. Each binding is one coherent assignment, not unrelated
array elements mixed together. Preserve ambiguity as alternative input views.
Alternatives are internal argument abstractions, never new benchmark cases or
asserted missing genders/dates. Unresolved lists relevant uncertainty NOT covered
by those alternatives; never omit an inconvenient interpretation just to agree.
The common host executes every returned binding through the unchanged kernel:
all must be handled with the same answer, otherwise unresolved. If answers differ
it exposes the actual differing input ports for one factual clarification.
Do not output any native answer in the adapter or independently solve the legal
rule there. Factual role projection, event grouping and date normalization are
allowed; statutory tests stay in the unchanged kernel. Pure regex/string parsing
is allowed to both arms. If a direct literal binding is sufficient it may return
without a model call. requires_neural_read means the host can request the chosen
factual view if the first adapter pass cannot construct a binding.
No imports, nested defs, lambdas, network/files or exception-as-success/default.
Calendar primitives and supported Python calls are shared. Keep output bounded.
'''


def read(p):
    return json.loads(p.read_text())


def kernels():
    raw = read(repair.OUT / 'teacher.json')['value']
    acquired = raw['kernels']
    assert {k['name'] for k in acquired} == {'agricultural_employer_threshold', 'qualifying_child_residence_gate'}
    for k in acquired:
        validate_procedure(k['program'], allow_helpers=True)
        fields = json.loads(k['input_fields_json'])
        assert fields and all(v['type'] in ('string', 'integer', 'number', 'boolean', 'array', 'object') for v in fields.values())
    source_bank = read(ROOT / 'artifacts/legal_skill_evolution_case_support_check_20261112/generated_library.json')
    old = next(iter(source_bank['skills'].values()))
    family = {'name': 'family_employment_A', 'program': old['procedure'],
        'input_fields_json': json.dumps({n: {'type': p['type'], 'description': p['question']} for n, p in old['inputs'].items()}),
        'premises': {n: p['value'] for n, p in old['premises'].items()},
        'scope': 'sufficient_positive_only', 'query_clause': '3306(c)(5)(A) supports parent c(5) when positive',
        'original_skill_hash': read(ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json')['same_skill_hash'],
        'source_quote': next(iter(old['premises'].values()))['origin']['quote']}
    # Existing family procedure reads its actual source constants in premises;
    # the runtime passes those unchanged rather than rewriting the kernel.
    return [family, *deepcopy(acquired)]


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    assert (repair.OUT / 'teacher.json').exists()
    p = read(repair.OUT / 'protocol.json')
    bank = kernels()
    history = read(ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json')
    # Transfer facts are not in this common input, even as proposed programs.
    task = {'unchanged_common_kernels': bank, 'actual_grounding_error_and_source_review': history,
        'runtime_adapter_interface': (ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py').read_text(),
        'positive_literal_context_interface': (ROOT / 'legal_skill_guard/skill_evolution/literal_facts.py').read_text(),
        'future_case_facts_and_native_annotations_withheld': True}
    before = base.rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'kernel_bank.json', bank)
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py', ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py', ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py', ROOT / 'legal_skill_guard/skill_evolution/literal_facts.py',
        ROOT / 'tests/test_skill_evolution_case_observation_contract.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': p['sources'], 'learning_sources': p['sources'][:1],
        'frozen_original_TRAIN_transfer_sources': p['sources'][1:],
        'same_original_case_exposure_not_a_new_blind_test': True,
        'all_three_statute_and_kernel_exposure_disclosed': True,
        'only_first_mother_supplies_actual_case_feedback': True,
        'teacher_profile': p['teacher_profile'], 'executor_profile': p['executor_profile'],
        'independent_controller_teachers': 2, 'teacher_dispatch': 'serial',
        'same_kernel_information_history_and_adapter_capacity': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'task_sha256': hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest()}
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for f, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h
        assert hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest() == p['task_sha256']
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
        for arm in ARMS:
            system = COMMON + ('\nUse the actual error to learn program-conditioned observation views and evidence-bound argument projections. Keep irrelevant ambiguity unresolved when the unchanged program is invariant; use output-relevant differences for factual clarification.\n' if arm == 'ProgramGuided' else
                '\nIndependently construct the strongest compact correct grounding strategy from the same full history and kernels. You may freely use relational observations, source evidence, program behavior, deterministic parsing, ambiguity preservation, previous correct repair reuse and factual clarification.\n')
            system += '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
            user = json.dumps(read(OUT / 'teacher_task.json'), ensure_ascii=False, separators=(',', ':'))
            assert not base.prior.strict_output_schema_issues(SCHEMA)
            assert len(base.prior.render_structured_codex_prompt(system, user)) <= base.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
            immutable_json(OUT / arm / 'preflight.json', {'schema_issues': [], 'task_sha256': digest(read(OUT / 'teacher_task.json'))})
            if phase == 'acquire' and not (OUT / arm / 'teacher.json').exists():
                result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':controller',
                    source_ids=p['sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
                immutable_json(OUT / arm / 'teacher.json', result)
                print(json.dumps({'arm': arm, 'learned_observation_contract_saved': True}), flush=True)


if __name__ == '__main__':
    main()
