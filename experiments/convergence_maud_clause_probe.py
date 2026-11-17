"""Exact reference replay and matched local M1 reads on audited MAUD TRAIN spans.

The pilot mother and audit already exist. This probe isolates local attachment
reading while the full-contract answer remains unresolved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from legal_skill_guard.paired_interfaces import maud_scope_relational as scope
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
POINTER = HANDOFF / 'maud_clause_probe_current.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_check(source, observation, view, plan):
    unit = plan['relational_program']['units']['focused_exception']
    state = observation['state']
    reading = {'focused_exception': {
        'status': 'complete',
        'observation': {'source_anchor': 'focused_exception',
                        'relations': residual.encode(unit['asset']['features'], state)},
        'evidence': [{'field': 'source_text', 'quote': observation['anchor']['condition_quote']}],
    }}
    expected = scope.local_consumer(state, {})
    decoded = decode_response(source, view, plan, {
        'content': json.dumps(reading, ensure_ascii=False), 'finish_reason': 'stop',
    })
    actual = {name: result['answer'] for name, result in decoded['native'].items()}
    if decoded['production_errors'] or actual != expected:
        raise ValueError('Exact local scope reference failed the production decoder')
    return expected


def prepare():
    inputs = ROOT / read(HANDOFF / 'normalized_inputs_current.json')['artifact_root']
    audit = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root']
    report_path, = (audit / 'audit_results').glob('*.json')
    report = read(report_path)
    raw_record, = (audit / 'calls').glob('*/result.json')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        settled = db.execute('select role,status,source,result from calls where id=?',
                             (report['call_id'],)).fetchone()
    if (not settled or tuple(settled[:3]) != ('teacher', 'completed', report['source'])
            or json.loads(settled[3]) != read(raw_record)
            or read(raw_record)['value'] != report['audit']
            or not report['grounding_receipt']['grounding_checks_passed']):
        raise ValueError('Archive must contain the settled, grounded source-only audit')
    mother = next(source for source in read(inputs / 'train/public.json') if source['key'] == report['source'])
    if report['source'] not in {row['source'] for row in read(audit / 'pilot20.json')}:
        raise ValueError('Diagnostic source must be in the fixed TRAIN pilot')
    observations = scope.anchored_observations(mother, report['audit'])
    if len({row['target_families'] for row in observations}) < 2:
        raise ValueError('Both distinct scope families must have exact audited anchors')
    cases = []
    for observation in observations:
        source, view = scope.case_view(mother, observation)
        # The first candidate after the fixed control comes from the certified
        # finite ordering. No reader output enters this diagnostic choice.
        plans = view['plans'][:2]
        expected = reference_check(source, observation, view, plans[0])
        for plan in plans[1:]:
            reference_check(source, observation, view, plan)
        cases.append({'public_source': source, 'view': {**view, 'plans': plans},
                      'expected_local_projection': expected, 'audited_state': observation['state']})
    paths = [
        'experiments/convergence_maud_clause_probe.py',
        'legal_skill_guard/paired_interfaces/maud_scope_relational.py',
        'legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/relational_program.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/paired_interfaces/production_decode.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py',
    ]
    binding = {
        'study_id': 'convergence_MAUD_local_clause_scope_01',
        'source_sha256': {name: sha(ROOT / name) for name in paths},
        'source_audit_sha256': sha(report_path),
        'mother': mother['key'],
        'cases_sha256': digest(cases),
        'executor': read(HANDOFF / 'executor_readiness.json')['executor_config'],
        'full_native_question_scored': False,
    }
    out = BASE / 'maud_clause_scope_probe' / digest(binding)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'binding.json', binding)
    status = {'artifact_root': str(out.relative_to(ROOT)), 'status': 'prepared', 'reader_cells': 2 * len(cases)}
    POINTER.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status), flush=True)


def run():
    state = read(POINTER)
    out = ROOT / state['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0, 'reused_terminal': True}), flush=True)
        return
    binding = read(out / 'binding.json')
    for name, expected in binding['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Bound diagnostic source changed: ' + name)
    cases = read(out / 'cases.json')
    if digest(cases) != binding['cases_sha256']:
        raise ValueError('Bound diagnostic cases changed')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-maud-clause-' + digest(binding)[:16],
                             sources={'train': [binding['mother']], 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    actor = InterfaceActor(executor, out, plan_assets={}, source_inputs=None,
                           pipeline_binding=binding['source_sha256'])
    state.update(status='running', pid=os.getpid())
    POINTER.write_text(json.dumps(state, indent=2) + '\n')
    observations = []
    try:
        for case in cases:
            source, view = case['public_source'], case['view']
            for plan in view['plans']:
                result = actor.measure(source, view, plan, 'skill_actor')
                expected = case['expected_local_projection']
                actual = {name: answer['answer'] for name, answer in result['native'].items()}
                row = {
                    'view': view['view'], 'plan': plan['name'],
                    'actual': actual, 'expected': expected,
                    'correct_projections': sum(actual[n] == value for n, value in expected.items()),
                    'production_errors': result['production_errors'],
                    'physical_call_id': result['physical_call_id'], 'usage': result['usage'],
                    'reused_paid_response': result['reused_paid_response'],
                }
                immutable_json(out / 'comparison_rows' / (digest({'view': view['view'], 'plan': plan['version']}) + '.json'), row)
                observations.append(row)
        state.update(status='completed', observations=observations, full_native_question_scored=False)
        immutable_json(out / 'terminal.json', state)
    except Exception:
        state.update(status='interrupted_or_failed', completed_reader_cells=len(observations))
        raise
    finally:
        POINTER.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'run'])
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)()
