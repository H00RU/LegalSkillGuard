"""Fixed three-arm teacher revision from the two actual TRAIN executions.

Full vs ProofFree isolates revision; ProofFree vs CacheFree compares acquisition
under ordinary revision. Independent histories remain independent. All arms get
the same source, native TRAIN supervision and explicit-GIVEN clarification.
"""
import ast
from collections import Counter
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_skills import OUT, RUN, RESULT, COMMON
from experiments.legal_skill_evolution_teacher_proof_execute import PLAN, execute, validate
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import pack
import jsonschema


SPEC = [
    ('Full', 'TeacherProof', 'proof_frontier_revision'),
    ('ProofFree', 'TeacherProof', 'unconstrained_reflection'),
    ('CacheFree', 'IndependentSourceCache', 'unconstrained_reflection'),
]

REVISED_COMMON = COMMON.replace(
    'Request primitive case facts and quantities from the native question, not\n'
    'whether the legal query is true, rule applicability, legal entitlement or other\n'
    'derived legal conclusions. Runtime will ask the frozen executor for these facts.',
    'Request case facts and quantities, including legal intermediates ONLY when\n'
    'explicitly GIVEN in the case text. A stated entitlement/amount is a legitimate\n'
    'case premise; its prerequisites need not be re-inferred. Do not ask the reader\n'
    'to derive an unstated legal conclusion or the final answer. Runtime asks the\n'
    'frozen executor for these supported values.')
REVISED_COMMON = REVISED_COMMON.replace(
    'The acquisition input contains source law and two current task formats, but NO\n'
    'case facts or labels.',
    'This revision input contains source law and the two acquisition TRAIN cases,\n'
    'their actual executions and native feedback. Later four case bodies, questions\n'
    'and labels are excluded. Initial acquisition was source-only; this is now\n'
    'explicitly a supervised TRAIN update.')

DIRECTED = '''Perform a support/defeat proof-frontier revision of this actual skill.
1. For each observed query, match the source-supported derivation to explicit
case premises; distinguish GIVEN intermediate statements from unstated conditions.
2. Locate which open support/exception obligations actually block this query.
Revise factual acquisition when premises exist but were not read; revise rule
code when source behavior is missing or wrong. Do not replace unknown by default.
3. Reuse existing source-backed helpers and retain applicable qualifications;
do not relearn a complete current-case answer. Preserve the actual correct route.
4. Keep a reusable source-rule/claim projection rather than two fixed question
answers. Where supplied source and already acquired definitions support related
native claim forms, make that reuse executable; report remaining uncovered scope.
Do not invent source content or fabricate cases. Teacher performs all learning.
Return the revised complete program and honest source-rule receipts.
'''

FREE = '''Perform the strongest ordinary free reflection/revision of your own
actual program using this complete source, actual cases, results and diagnostics.
All supplied proof-frontier metadata, GIVEN clarification, reusable helpers,
source decomposition and public fixes are available to you. You may adopt the
same organization as the directed arm, rewrite the whole policy or apply local
changes. Optimize reliable reuse and full acquisition/execution cost. Preserve
the correct route and improve the unsupported one without question-answer
memorization. Support related supplied-law claim forms where useful and source
justified; report actual uncovered scope. Do not weaken yourself for comparison.
Return the revised complete program and honest source-rule receipts.
'''


def diagnostic(record):
    trace = record['execution']
    return {k: record[k] for k in ('source', 'question', 'plan', 'known_case_values',
        'native_score', 'core_executed', 'fallback_required')} | {
        'actual_program_result': trace['result'],
        'actual_function_call_counts': dict(Counter(c['function'] for c in trace['calls'])),
        'actual_trace_truncated': trace['trace_truncated'],
        'unresolved_case_fields': record['read_event']['unresolved_fields'] if record['read_event'] else [],
        'read_fields_with_exact_case_support': record['read_event']['fields'] if record['read_event'] else {},
        'raw_execution_record_sha256': digest(record),
        'diagnostic_is_selected_view_not_claimed_full_trace': True}


def prepare():
    p = read(OUT/'protocol.json'); inp = read(OUT/'source_only_input.json')
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    cases = [{
        'source': k, 'facts': public[k]['views'][0]['public']['facts'],
        'question': public[k]['views'][0]['public']['question'],
        'native_annotation': grading[k][public[k]['views'][0]['id']]}
        for k in p['acquisition_and_feedback_sources']]
    review = {
        'same_information_clarification_for_all_arms': True,
        'actual_gap': 'Second case explicitly gives two $600 component entitlements under63f1A/B, but both actual programs request unstated raw age/blindness/income facts and return unknown. Source63c3 requires summing given allowable components.',
        'givens_are_premises_not_new_legal_rules': True,
        'initial_API_correction': 'Forbid inferring unstated legal conclusions, not use of legal intermediates explicitly stated as GIVEN in native cases.',
        'first_case': 'Both independently acquired programs actually evaluated the63c6A condition and matched original native Entailment. The applies routing transport fix is shared and retained.',
        'scope_inventory': 'Both actual programs currently route only two observed claim formats despite holding several source-backed related helpers. Reuse/generalization must be executable, not an answer lookup.',
        'not_new_global_acceptance_gate': 'No demand for full-law formalization, zero fallback or all-branch validation.',
        'no_later_case_text_or_labels': True}
    targets = {}
    for name, parent, mode in SPEC:
        bundle = read(OUT/'initial_execution'/parent/'bundle.json')
        records = [read(OUT/'initial_execution'/parent/k.replace(':', '_')/'result.json')
                   for k in p['acquisition_and_feedback_sources']]
        targets[name] = {'law_material': inp['law_material'], 'current_own_library': bundle,
            'actual_acquisition_TRAIN_cases': cases,
            'actual_own_execution_diagnostics': [diagnostic(r) for r in records],
            'common_source_and_interface_review': review,
            'directed_revision_algorithm_also_available_to_free_controls': DIRECTED,
            'allowed_calls': inp['allowed_calls'], 'allowed_methods': inp['allowed_methods']}
    q = {'parent_run': RUN, 'same_goal': True, 'goal_complete': False,
         'phase': 'three_independent_teacher_updates', 'arms': SPEC,
         'contrasts': {'revision': ['Full', 'ProofFree'], 'acquisition_with_ordinary_revision': ['ProofFree', 'CacheFree']},
         'source_ids': p['acquisition_and_feedback_sources'],
         'later_four_case_text_questions_labels_excluded': True,
         'initial_source_only_claim_does_not_extend_to_supervised_revision': True,
         'free_controls_receive_all_same_diagnostics_and_algorithm_description': True,
         'source_and_case_feedback_identical_own_history_preserved': True,
         'serial_teacher_dispatch_matches_existing_bound_ledger_policy': True,
         'new_mechanical_call_cap': None, 'no_unchanged_retry': True,
         'execution_model_thinking': False,
         'implementation_sha256': sha(Path(__file__)),
         'common_system_sha256': digest(REVISED_COMMON),
         'task_sha256': {k: digest(v) for k, v in targets.items()}}
    immutable_json(OUT/'revision'/'protocol.json', q)
    immutable_json(OUT/'revision'/'common_review.json', review)
    for name, task in targets.items():
        immutable_json(OUT/'revision'/name/'input.json', task)
    if not (OUT/'revision'/'ledger_before.json').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
            rows = [list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT/'revision'/'ledger_before.json', {'rows': rows})
    return p, q, targets


def run():
    p, q, targets = prepare()
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))
    for arm, _, mode in SPEC:
        assert sha(Path(__file__)) == q['implementation_sha256']
        folder = OUT/'revision'/arm
        if (folder/'teacher.json').exists():
            print(json.dumps({'existing_revision_preserved': arm}), flush=True); continue
        response = FrozenTeacher(ledger, folder, p['teacher_profile']).propose(
            RUN+':revision:'+arm, source_ids=q['source_ids'],
            system_prompt=REVISED_COMMON+(DIRECTED if mode == 'proof_frontier_revision' else FREE),
            user_prompt=json.dumps(pack(targets[arm]), ensure_ascii=False), output_schema=RESULT)
        immutable_json(folder/'teacher.json', response)
        bundle = response['value']
        try:
            validate(bundle['program'])
            functions = {f.name for f in ast.parse(bundle['program']).body}
            for r in bundle['source_rules']:
                assert r['quote'] and r['quote'] in targets[arm]['law_material'][r['source_field']]
                assert r['function'] in functions
            plans = [execute(bundle['program'], {'phase': 'plan', 'question': c['question']})
                     for c in targets[arm]['actual_acquisition_TRAIN_cases']]
            for plan in plans: jsonschema.validate(plan, PLAN)
            immutable_json(folder/'offline_check.json', {'pure_python_exact_quotes_and_plan_types': True,
                'plans': plans, 'native_and_source_semantic_validation_pending': True})
            print(json.dumps({'arm': arm, 'program_chars': len(bundle['program']), 'plans': plans,
                              'seconds': response['elapsed_seconds']}, ensure_ascii=False), flush=True)
        except Exception as error:
            immutable_json(folder/'offline_check.json', {'validation_error': type(error).__name__+': '+str(error)})
            print(json.dumps({'arm': arm, 'validation_error': str(error)}), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_teacher_proof_revision.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
