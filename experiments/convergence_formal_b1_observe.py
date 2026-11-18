"""Collect the same pre-update B1 TRAIN observations for the five locked arms."""

import argparse
from collections import Counter
import json
import math
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor, supported_fee_rule
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_lock_external_pilot import LOCK
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor, common_cells
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_training import training_batches
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_b1_observe_current.json'
BATCH = 1


def load_roster(expected):
    protocol = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'
    roster_info = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_info['artifact_root'] / 'binding.json')
    if (digest(roster) != roster_info['roster_sha256'] or expected['roster_sha256'] != digest(roster)
            or expected['protocol_sha256'] != sha(protocol) or expected['external_pilot_lock_sha256'] != digest(read(LOCK))):
        raise ValueError('Use the exact TRAIN roster, protocol and external family preserved at B0')
    ordered = training_batches(roster, read(ROOT / roster['normalized_root'] / 'train/public.json'),
                               read(protocol)['data']['train_quota'])
    if expected['TRAIN_ordered_batches_sha256'] != digest(ordered):
        raise ValueError('The locked training order may not change')
    return ordered


def prepare():
    bootstrap = ROOT / read(BOOTSTRAP)['artifact_root']
    study, terminal = read(bootstrap / 'binding.json'), read(bootstrap / 'terminal.json')
    if (bootstrap.name != digest(study) or terminal['status'] != 'completed_B0_bootstrap'
            or terminal['TEST_content_opened'] or study['pilot_library_versions_preloaded']
            or study['executor']['enable_thinking'] is not False):
        raise ValueError('Start from the verified common five-arm B0')
    batches = load_roster(study)
    journal = TrainingJournal(bootstrap, study, batches)
    layouts = {arm: journal.library(arm, 0)['snapshot_sha256'] for arm in ConvergenceEvaluation.arms}
    readers = {arm: journal.library(arm, 0)['programs'] for arm in layouts}
    if len({digest(programs) for programs in readers.values()}) != 1 or any(
            journal.library(arm, 0)['interface_library'] is not None for arm in layouts):
        raise ValueError('The first observations must see exactly the same entering program in all five arms')
    paid = {}
    for pointer in ('pilot_b0_current.json', 'cni_indexed_evidence_current.json', 'airline_public_fee_reader_current.json'):
        stage = ROOT / read(HANDOFF / pointer)['artifact_root']
        prior = read(stage / 'binding.json')
        if prior['executor'] != study['executor'] or read(stage / 'terminal.json')['status'] != 'completed':
            raise ValueError('Exact-wire replay requires settled evidence under the same model and settings')
        paid[str(stage.relative_to(ROOT))] = sha(stage / 'terminal.json')
    pilot = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    native = read(pilot / 'binding.json')
    files = set(study['source_sha256']) | {'experiments/convergence_formal_b1_observe.py',
        'experiments/convergence_common_airline_actor.py', 'experiments/convergence_airline_structured_update.py',
        'legal_skill_guard/paired_interfaces/airline_public_fees.py', 'legal_skill_guard/skill_evolution/clients.py'}
    binding = {'study': 'convergence_common_entering_B1_TRAIN_observations', 'batch': BATCH,
               'bootstrap_root': str(bootstrap.relative_to(ROOT)), 'bootstrap_terminal_sha256': sha(bootstrap / 'terminal.json'),
               'study_binding_sha256': digest(study), 'entering_libraries': layouts,
               'ordered_sources_sha256': digest(batches[0]), 'prior_train_replay_roots': paid,
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}, 'executor': study['executor'],
               'native_grade_paths': native['grading_paths'], 'native_grade_sha256': native['grading_file_sha256']}
    out = BASE / 'formal_b1_observe' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    sources = batches[0]
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'batch': BATCH, 'mothers': len(sources),
                           'logical_common_reads': sum(len(common_cells(s)) for s in sources)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding = read(out / 'binding.json')
    root = ROOT / binding['bootstrap_root']
    study = read(root / 'binding.json')
    if (out.name != digest(binding) or sha(root / 'terminal.json') != binding['bootstrap_terminal_sha256']
            or digest(study) != binding['study_binding_sha256']
            or any(sha(ROOT / name) != expected for name, expected in binding['source_sha256'].items())):
        raise ValueError('The first-batch observation runtime or its B0 provenance changed')
    batches = load_roster(study)
    if (digest(batches[0]) != binding['ordered_sources_sha256'] or any(
            sha(ROOT / folder / 'terminal.json') != expected for folder, expected in binding['prior_train_replay_roots'].items())):
        raise ValueError('Use the exact ordered cohort and prior paid observation roots')
    journal = TrainingJournal(root, study, batches)
    if any(journal.library(arm, 0)['snapshot_sha256'] != seal for arm, seal in binding['entering_libraries'].items()):
        raise ValueError('The pre-update library changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the current physical request to settle first')
    cohort = batches[0]
    keys = [source['key'] for source in cohort]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-observe-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / folder for folder in binding['prior_train_replay_roots']]
    reader.readiness()
    program = ProgramActor(reader, out, max_calls=1)
    same = ConvergenceActor(out, program_actor=program, interface_actor=None, providers={},
                            train_sources=keys, study_binding=study)
    actor = CommonAirlineActor(same, reader, out)
    arm_receipts, first = {}, None
    for arm in ConvergenceEvaluation.arms:
        write_status(out, {'status': 'running', 'arm': arm, 'batch': BATCH}, POINTER)
        receipt = journal.observe(arm, BATCH, actor)
        rows = [read(journal.directory(arm, BATCH) / 'predictions' / (digest(key) + '.json'))['result']['native']
                for key in keys]
        if first is None:
            first = rows
        if first != rows:
            raise ValueError('Different primary reads cannot be presented as common under identical entering libraries')
        arm_receipts[arm] = receipt['train_observation_sha256']
    grades = {}
    rows = []
    for source, native in zip(cohort, first, strict=True):
        dataset, key = source['dataset'], source['key']
        path = binding['native_grade_paths'][dataset]
        if path not in grades:
            if sha(ROOT / path) != binding['native_grade_sha256'][path]:
                raise ValueError('The TRAIN grader must remain the one used by the fixed cohort')
            grades[path] = read(ROOT / path)
        values = {task['id']: grade_view(dataset, task, grades[path][key][task['id']], native[task['id']]['answer'],
                   native[task['id']].get('evidence_sentence_ids', []))['grade'] if native[task['id']]['handled'] else 0.0
                  for task in source['views']}
        rows.append({'source': key, 'view_scores': values, 'dataset': dataset, 'native_utility': math.fsum(values.values()) / len(values)})
    immutable_json(out / 'native_scores.json', rows)
    with ledger.transaction() as db:
        settled = db.execute('select status,result from calls where id like ?', (ledger.run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in settled):
        raise ValueError('Every physical B1 observation must be settled')
    result = {'status': 'completed_B1_observations', 'observation_receipts': arm_receipts, 'mothers': len(keys),
              'native_tasks': sum(len(r['view_scores']) for r in rows), 'native_scores_sha256': digest(rows),
              'common_fee_mothers': sum(supported_fee_rule(src) is not None for src in cohort),
              'new_executor_calls': len(settled), 'new_executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                       for _, raw in settled), 'rolled_forward_library_updates': 0, 'TEST_opened': False,
              'mothers_by_dataset': dict(Counter(r['dataset'] for r in rows))}
    immutable_json(out / 'terminal.json', result)
    write_status(out, result, POINTER)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
