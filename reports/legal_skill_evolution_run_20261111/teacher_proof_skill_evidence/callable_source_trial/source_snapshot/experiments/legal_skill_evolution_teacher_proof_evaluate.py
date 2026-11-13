"""Calibrate the three fixed revisions, then freeze and check four TRAIN cases.

No teacher dispatch, source-rule invention or native-label repair occurs here.
Literal case bindings are validated before the learned Python consumes them.
"""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import re
import sqlite3

import jsonschema

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_skills import OUT, RUN
from experiments.legal_skill_evolution_teacher_proof_execute import (
    PLAN, common_transport_fix, execute, traced, deepcopy)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError

ARMS = ['Full', 'ProofFree', 'CacheFree']
READ_QUESTION = '''Read the acquired fields about the current case and question.
Use legal intermediate statements explicitly GIVEN in the case as premises;
do not infer unstated legal conclusions. A boolean is the truth of the requested
case proposition, not a text-presence flag: if neither it nor its negation is
supplied, return unknown even if the question says "Does the case explicitly
state". For a requested explicitly stated total, do not calculate a total from
components, and do not use the native claim as a GIVEN. Select stated component
amounts separately. Leave unavailable fields unknown, never False/0/empty.'''


def validate_case_bindings(fields, values, event):
    """Reject unsupported explicit GIVEN quantities; never substitute a value."""
    accepted, rejected = dict(values), []
    if event is None:
        return accepted, rejected
    for name, value in values.items():
        question = fields[name]['question'].casefold()
        explicit_case = 'case' in question and ('explicit' in question or 'state' in question)
        if not explicit_case:
            continue
        support = [s for s in event['fields'][name]['support'] if s['field'] == 'facts']
        error = None
        if not support:
            error = 'An explicit case premise needs support in facts, not just the native hypothesis.'
        elif fields[name]['type'] in ('number', 'integer') and any(w in question for w in ('amount', 'dollar', '$')):
            amounts = [float(v.replace(',', '')) for s in support
                       for v in re.findall(r'\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)', s['text'])]
            if float(value) not in amounts:
                error = 'Requested explicitly stated money amount is absent from its quoted case support.'
        if error:
            rejected.append({'field': name, 'raw_value': value, 'error': error,
                             'raw_status_and_support_preserved_in_read_event': True})
            accepted.pop(name)
    return accepted, rejected


def prepare():
    p = read(OUT/'protocol.json')
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    questions = [public[k]['views'][0]['public']['question'] for k in p['acquisition_and_feedback_sources']]
    bundles = {}
    for arm in ARMS:
        value = read(OUT/'revision'/arm/'teacher.json')['value']
        check = read(OUT/'revision'/arm/'offline_check.json')
        assert check.get('pure_python_exact_quotes_and_plan_types') is True, (arm, check)
        program, fix = common_transport_fix(value['program'], questions)
        bundle = {**value, 'program': program}
        for q in questions:
            jsonschema.validate(execute(program, {'phase': 'plan', 'question': q}), PLAN)
        immutable_json(OUT/'revised_execution'/arm/'bundle.json', bundle)
        immutable_json(OUT/'revised_execution'/arm/'common_transport_fix.json', fix)
        bundles[arm] = bundle
    paths = [Path(__file__).resolve(), ROOT/'experiments/legal_skill_evolution_teacher_proof_execute.py',
             ROOT/'legal_skill_guard/skill_evolution/runtime.py',
             ROOT/'legal_skill_guard/skill_evolution/source_python.py',
             ROOT/'legal_skill_guard/skill_evolution/span_compiler_worker.py']
    protocol = {'parent_run': RUN, 'same_goal': True, 'goal_complete': False,
        'arms': ARMS, 'calibration_sources': p['acquisition_and_feedback_sources'],
        'frozen_check_sources': p['frozen_check_sources'],
        'bundle_sha256': {k: digest(v) for k, v in bundles.items()},
        'shared_reader_question': READ_QUESTION,
        'rejected_bindings_are_not_repaired_or_called_valid_raw_model_outputs': True,
        'unsupported_plans_require_fallback_not_counted_core_no_fallback_call': True,
        'no_later_check_case_body_question_or_label_in_teacher_updates': True,
        'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in paths}}
    immutable_json(OUT/'revised_execution'/'protocol.json', protocol)
    for f in paths:
        target = OUT/'revised_execution'/'source_snapshot'/f.relative_to(ROOT)
        if target.exists(): assert target.read_bytes() == f.read_bytes()
        else:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    return p, public, bundles, protocol


def execute_stage(stage):
    p, public, bundles, protocol = prepare()
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))
    with ledger.transaction() as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
        teacher_ids = [r[0] for r in db.execute('select id from calls where role=? order by id', ('teacher',))]
    if stage == 'frozen':
        review = read(OUT/'revised_execution'/'calibration_review.json')
        assert review['ready_for_fixed_four_TRAIN_checks'] is True
        freeze = {'same_goal': True, 'goal_complete': False, 'TRAIN_only_not_TEST': True,
                  'source_ids': p['frozen_check_sources'], 'protocol_sha256': digest(protocol),
                  'bundle_sha256': protocol['bundle_sha256'], 'teacher_ids_at_freeze': teacher_ids,
                  'no_post_check_repair': True}
        immutable_json(OUT/'revised_execution'/'freeze.json', freeze)
        keys = p['frozen_check_sources']
    else:
        assert not (OUT/'revised_execution'/'freeze.json').exists(), 'No calibration after freeze'
        keys = p['acquisition_and_feedback_sources']
    client = FrozenExecutor(ledger, OUT/'revised_execution'/stage, p['executor_profile'])
    client.readiness(); reads = FrozenReads(client)
    grading = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    for key in keys:
        source = public[key]; view = source['views'][0]; question = view['public']['question']
        case_view = deepcopy(view)
        case_view['public'] = {k: v for k, v in view['public'].items() if k in ('facts', 'question')}
        for arm, bundle in bundles.items():
            for name, h in protocol['source_sha256'].items(): assert sha(ROOT/name) == h
            folder = OUT/'revised_execution'/stage/arm/key.replace(':', '_')
            if (folder/'result.json').exists():
                print(json.dumps({'preserved_result': str(folder/'result.json')}), flush=True); continue
            plan = execute(bundle['program'], {'phase': 'plan', 'question': question})
            jsonschema.validate(plan, PLAN)
            values, event, rejected, read_error = {}, None, [], None
            if plan['supported'] and plan['fields']:
                try:
                    raw_values, event = reads.read(source, case_view, question=READ_QUESTION,
                        fields=plan['fields'], locator='facts and question', purpose='skill_replay',
                        allow_unresolved=True, require_case_support=True)
                    values, rejected = validate_case_bindings(plan['fields'], raw_values, event)
                except LocalReadError as error:
                    event = error.event; read_error = str(error)
            execution = traced(bundle['program'], {'phase': 'evaluate', 'question': question, 'facts': values})
            answer = execution['result']['answer']
            core = plan['supported'] and answer in ('Entailment', 'Contradiction')
            if read_error: core = False
            assert set(execution['result']['used_rule_ids']) <= {r['id'] for r in bundle['source_rules']}
            record = {'source': key, 'arm': arm, 'stage': stage, 'question': question,
                'plan': plan, 'read_event': event, 'read_error': read_error,
                'validated_case_values': values, 'rejected_reader_bindings': rejected,
                'execution': execution, 'program_executed': True, 'core_executed': core,
                'fallback_required': not core, 'fallback_executed': False,
                'native_score': grade_view(source['dataset'], view, grading[key][view['id']], answer) if core else None,
                'actual_source_rule_functions_called': sorted({c['function'] for c in execution['calls']}
                    & {r['function'] for r in bundle['source_rules']}),
                'source_and_factual_semantics_review_pending': True, 'goal_complete': False}
            immutable_json(folder/'result.json', record)
            print(json.dumps({'stage': stage, 'arm': arm, 'source': key, 'answer': answer,
                'core': core, 'grade': record['native_score'], 'rejected_bindings': rejected,
                'read_error': read_error, 'source_functions': record['actual_source_rule_functions_called']}), flush=True)
    if stage == 'frozen':
        with ledger.transaction() as db:
            assert teacher_ids == [r[0] for r in db.execute('select id from calls where role=? order by id', ('teacher',))]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--stage', choices=['calibration', 'frozen'], required=True)
    args = ap.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_teacher_proof_evaluate.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute_stage(args.stage)
