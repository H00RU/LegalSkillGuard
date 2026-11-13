"""Execute learned proof/source-cache programs on the fixed acquisition TRAIN.

Legal computation remains in the actual teacher-produced Python. Shared host
code binds supported case facts, executes it, traces calls and grades natively.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import jsonschema

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_skills import OUT, RUN
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError
from legal_skill_guard.skill_evolution.source_python import execute, validate

PLAN = record_schema({'supported': {'type': 'boolean'}, 'fields': {'type': 'object',
    'additionalProperties': record_schema({'type': {'type': 'string',
        'enum': ['boolean', 'integer', 'number', 'string']},
        'question': {'type': 'string', 'minLength': 1}})}})
ANSWER = record_schema({'answer': {'type': 'string',
    'enum': ['Entailment', 'Contradiction', 'unknown']},
    'used_rule_ids': {'type': 'array', 'items': {'type': 'string'}},
    'open_dependencies': {'type': 'array', 'items': {'type': 'string'}}})


def common_transport_fix(program, questions):
    """Repair the actual applies/apply routing defect, no legal rule changes."""
    old = 'c6 and ("apply" in lower or "applicable" in lower or "inapplicable" in lower)'
    new = 'c6 and ("apply" in lower or "applies" in lower or "applicable" in lower or "inapplicable" in lower)'
    if old not in program:
        return program, {'changed': False, 'common_rule_available_to_both_arms': True}
    assert program.count(old) == 1
    updated = program.replace(old, new)
    before = {f.name: ast.dump(f, include_attributes=False) for f in ast.parse(program).body}
    after = {f.name: ast.dump(f, include_attributes=False) for f in ast.parse(updated).body}
    assert before.keys() == after.keys()
    assert all(before[k] == after[k] for k in before if k != '_kind')
    checks = []
    for q in questions:
        checks.append({'question': q,
            'before': execute(program, {'phase': 'plan', 'question': q}),
            'after': execute(updated, {'phase': 'plan', 'question': q})})
    assert checks[0]['before']['supported'] is False
    assert checks[0]['after']['supported'] is True
    assert checks[1]['before'] == checks[1]['after']
    return updated, {'changed': True, 'only_kind_function_AST_changed': True,
        'common_rule_available_to_both_arms': True, 'original_teacher_output_preserved': True,
        'meaning': 'Native applies must reach the already acquired apply/applicable branch.',
        'actual_failure_regressions': checks, 'new_model_calls': 0}


def traced(program, inputs):
    validate(program)
    worker = ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py'
    r = subprocess.run([sys.executable, '-I', '-S', str(worker)],
        input=json.dumps({'procedure': program, 'inputs': inputs, 'premises': {}, 'trace': True}),
        text=True, capture_output=True, timeout=4, cwd='/tmp', env={'LANG': 'C.UTF-8'})
    if r.returncode:
        raise ValueError(r.stderr[-1500:])
    value = json.loads(r.stdout)
    jsonschema.validate(value['result'], ANSWER)
    return value


def prepare():
    p = read(OUT/'protocol.json')
    assert sha(ROOT/'experiments/legal_skill_evolution_teacher_proof_skills.py') == p['implementation_sha256']
    assert sha(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') == p['public_manifest_sha256']
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    questions = [public[k]['views'][0]['public']['question'] for k in p['acquisition_and_feedback_sources']]
    bundles = {}
    for arm in p['comparison']:
        raw = read(OUT/arm/'teacher.json')['value']
        program, receipt = common_transport_fix(raw['program'], questions)
        bundle = {**raw, 'program': program}
        validate(program)
        for q in questions:
            jsonschema.validate(execute(program, {'phase': 'plan', 'question': q}), PLAN)
        immutable_json(OUT/'initial_execution'/arm/'bundle.json', bundle)
        immutable_json(OUT/'initial_execution'/arm/'common_transport_fix.json', receipt)
        bundles[arm] = bundle
    files = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/runtime.py',
             ROOT/'legal_skill_guard/skill_evolution/source_python.py',
             ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py']
    manifest = {'parent_run': RUN, 'same_goal': True, 'goal_complete': False,
        'phase': 'first_two_acquisition_TRAIN_actual_execution',
        'source_ids': p['acquisition_and_feedback_sources'],
        'both_independent_teacher_results_settled_before_executor': True,
        'case_reader_context': 'original facts and question only, identical shared policy for both arms',
        'literal_given_legal_intermediates_may_be_case_facts': True,
        'missing_facts_not_defaulted': True, 'fallback_not_executed_or_counted_core': True,
        'bundle_sha256': {k: digest(v) for k, v in bundles.items()},
        'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in files}}
    immutable_json(OUT/'initial_execution'/'protocol.json', manifest)
    for f in files:
        target = OUT/'initial_execution'/'source_snapshot'/f.relative_to(ROOT)
        if target.exists():
            assert target.read_bytes() == f.read_bytes()
        else:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    return p, public, bundles, manifest


def run():
    p, public, bundles, manifest = prepare()
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))
    client = FrozenExecutor(ledger, OUT/'initial_execution', p['executor_profile'])
    client.readiness(); reads = FrozenReads(client)
    # Native TRAIN labels are loaded only by the host scorer, never by reader.
    grading = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    for key in p['acquisition_and_feedback_sources']:
        source = public[key]; view = source['views'][0]; question = view['public']['question']
        case_view = deepcopy(view)
        case_view['public'] = {k: v for k, v in view['public'].items() if k in ('facts', 'question')}
        for arm, bundle in bundles.items():
            folder = OUT/'initial_execution'/arm/key.replace(':', '_')
            if (folder/'result.json').exists():
                print(json.dumps({'reused_saved_execution': str(folder/'result.json')}), flush=True); continue
            for name, h in manifest['source_sha256'].items():
                assert sha(ROOT/name) == h
            plan = execute(bundle['program'], {'phase': 'plan', 'question': question})
            jsonschema.validate(plan, PLAN)
            values, event = {}, None
            if plan['supported'] and plan['fields']:
                try:
                    values, event = reads.read(source, case_view,
                        question='Read each acquired field exactly in the current case/question scope. '
                                 'Use explicit GIVEN statements as case premises; do not derive new legal conclusions.',
                        fields=plan['fields'], locator='facts and question', purpose='skill_replay',
                        allow_unresolved=True, require_case_support=True)
                except LocalReadError as error:
                    immutable_json(folder/'read_failure.json', {'error': str(error), 'event': error.event})
                    print(json.dumps({'arm': arm, 'source': key, 'read_error': str(error)}), flush=True)
                    continue
            execution = traced(bundle['program'], {'phase': 'evaluate', 'question': question, 'facts': values})
            answer = execution['result']['answer']; core = answer in ('Entailment', 'Contradiction')
            declared = {r['id'] for r in bundle['source_rules']}
            assert set(execution['result']['used_rule_ids']) <= declared
            record = {'source': key, 'arm': arm, 'question': question, 'plan': plan,
                'known_case_values': values, 'read_event': event, 'execution': execution,
                'program_executed': True, 'core_executed': core, 'fallback_required': not core,
                'fallback_executed': False,
                'native_score': grade_view(source['dataset'], view, grading[key][view['id']], answer) if core else None,
                'source_and_factual_semantics_review_pending': True,
                'acquisition_TRAIN_not_held_out_success': True, 'goal_complete': False}
            immutable_json(folder/'result.json', record)
            print(json.dumps({'arm': arm, 'source': key, 'answer': answer,
                'native_score': record['native_score'], 'unresolved': execution['result']['open_dependencies']}), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_teacher_proof_execute.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
