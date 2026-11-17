"""Evaluate the shared B0 program on the fixed DEV roster, with TEST closed."""

import argparse
from collections import Counter
import json
import os
import sqlite3

from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, cells_for, read, sha, write_status
from legal_skill_guard.paired_interfaces.diversity import score as diversity_score
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'dev_b0_current.json'
ARM = ConvergenceEvaluation.arms[0]


def prepare():
    roster_pointer = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_pointer['artifact_root'] / 'binding.json')
    if digest(roster) != roster_pointer['roster_sha256']:
        raise ValueError('The sealed roster changed')
    normalized = ROOT / roster['normalized_root']
    dev = read(normalized / 'dev/public.json')
    identities = {row['source']: row for row in read(normalized / 'identity_metadata.json')
                  if row['project_split'] == 'dev'}
    if {source['key']: digest(source) for source in dev} != {
            name: entry['public_content_sha256'] for name, entry in identities.items()}:
        raise ValueError('Use the exact masked DEV public roster')
    cni = ROOT / read(HANDOFF / 'cni_indexed_evidence_current.json')['artifact_root']
    if read(cni / 'terminal.json')['status'] != 'completed':
        raise ValueError('The shared evidence layout must have a terminal TRAIN comparison')
    b0 = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    b0_binding = read(b0 / 'binding.json')
    legacy = ROOT / 'artifacts/two_method_followthrough_20261116/prepared/dev/grading.json'
    contracts = normalized / 'dev/CNI_MAUD_grading_only.json'
    diversity = ROOT / read(HANDOFF / 'diversity_holdout_current.json')['artifact_root'] / 'dev/grading.json'
    grades = {'OpenExempt': legacy, 'RuleArena_Airline': legacy,
              'ContractNLI': contracts, 'MAUD': contracts, 'LegalBench_Diversity': diversity}
    task_index = {path: {key: set(tasks) for key, tasks in read(path).items()} for path in set(grades.values())}
    for source in dev:
        if task_index[grades[source['dataset']]].get(source['key']) != {view['id'] for view in source['views']}:
            raise ValueError('A fixed DEV mother does not have the exact original native grading tasks')
    paths = set(b0_binding['source_sha256']) | {
        'experiments/convergence_dev_b0.py',
        'legal_skill_guard/paired_interfaces/formal_evaluation.py',
        'legal_skill_guard/paired_interfaces/pilot_metrics.py',
        'legal_skill_guard/paired_interfaces/diversity.py',
    }
    binding = {
        'study_id': 'convergence_shared_DEV_B0_v1', 'enforce_physical_actor_audit': True,
        'roster_sha256': digest(roster), 'DEV_public_sha256': digest(dev),
        'TEST_identities_sha256': digest(roster['sealed_TEST_identities']),
        'source_sha256': {name: sha(ROOT / name) for name in sorted(paths)},
        'grading_paths': {name: str(path.relative_to(ROOT)) for name, path in grades.items()},
        'grading_file_sha256': {str(path.relative_to(ROOT)): sha(path) for path in set(grades.values())},
        'executor': b0_binding['executor'], 'program': b0_binding['program'],
        'CNI_TRAIN_layout_comparison_sha256': sha(cni / 'terminal.json'),
        'public_CNI_layout': 'explicit_zero_based_spans', 'separate_OpenExempt_EC_EV': True,
        'same_initial_program_for_all_five_arms': True, 'DEV_labels_never_enter_actor_or_teacher': True,
    }
    out = BASE / 'dev_B0' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'public_DEV_sources.json', dev)
    immutable_json(out / 'sealed_TEST_identity_metadata_only.json', roster['sealed_TEST_identities'])
    write_status(out, {'status': 'prepared', 'DEV_mothers': len(dev),
                       'logical_executor_cells': sum(len(list(cells_for(source))) for source in dev)}, POINTER)
    print(json.dumps({'status': 'prepared', 'binding': digest(binding), 'DEV_mothers': len(dev)}), flush=True)


class CommonInitialActor:
    def __init__(self, executor, out):
        self.actor = ProgramActor(executor, out, max_calls=1)

    @staticmethod
    def cells(source):
        if source['dataset'] == 'ContractNLI':
            source = {**source, 'evidence_presentation': 'explicit_zero_based_spans'}
        return list(cells_for(source))

    def __call__(self, source, library, purpose):
        results = [self.actor.execute(library['program'], cell, purpose) for cell in self.cells(source)]
        native = {key: value for result in results for key, value in result['native'].items()}
        return {'native': native, 'cell_executions': results, 'fallback_executed': False}

    def verify_saved(self, source, library, purpose, result):
        cells = self.cells(source)
        executions = result['cell_executions']
        for cell, execution in zip(cells, executions, strict=True):
            self.actor.verify_program_result(cell, library['program'], purpose, execution)
        actual = {key: value for execution in executions for key, value in execution['native'].items()}
        if result['native'] != actual:
            raise ValueError('DEV native predictions lost their verified physical execution')


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').is_file():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    dev = read(out / 'public_DEV_sources.json')
    identities = read(out / 'sealed_TEST_identity_metadata_only.json')
    if any(sha(ROOT / name) != expected for name, expected in binding['source_sha256'].items()):
        raise ValueError('The shared B0 execution changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle any current research request before the DEV baseline')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-DEV-B0-' + digest(binding)[:16],
                             sources={'train': [], 'dev': [row['key'] for row in dev], 'test': []},
                             binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    annotations, by_source = {}, {row['key']: row['dataset'] for row in dev}

    def grade(partition, source_key, prediction_seal):
        if partition != 'dev':
            raise ValueError('Only the DEV grader is available in this stage')
        verify(prediction_seal, 'prediction_seal_sha256')
        if len(prediction_seal['predictions_sha256']) != len(dev):
            raise ValueError('Wait for the complete DEV prediction matrix before grading')
        path = binding['grading_paths'][by_source[source_key]]
        if path not in annotations:
            if sha(ROOT / path) != binding['grading_file_sha256'][path]:
                raise ValueError('The sealed native DEV grade file changed')
            annotations[path] = read(ROOT / path)
        return annotations[path][source_key]

    def sealed_test():
        raise ValueError('This development stage does not load TEST content')

    evaluation = ConvergenceEvaluation(out, dev, identities, binding=binding, grade_provider=grade, load_test=sealed_test)
    actor = CommonInitialActor(executor, out)
    library = sealed({'arm': ARM, 'batch': 0, 'program': binding['program'],
                     'study_binding': binding, 'initialization_shared': True}, 'snapshot_sha256')
    immutable_json(out / 'common_initial_library.json', library)
    write_status(out, {'status': 'running', 'pid': os.getpid(), 'DEV_mothers': len(dev)}, POINTER)
    try:
        cell = evaluation.evaluate('dev', ARM, 0, dict.fromkeys(ConvergenceEvaluation.datasets, library), actor)
        rows = cell['source_scores']
        metrics = {}
        for library_name in sorted(ConvergenceEvaluation.datasets):
            task_rows = [row for row in rows if row['dataset'] == library_name]
            families = sorted({row['view'] for row in task_rows}) if library_name in ('OpenExempt', 'MAUD') else ['native']
            metrics[library_name] = {}
            for family in families:
                selected = [row for row in task_rows if row['view'] == family or families == ['native']]
                metrics[library_name][family] = {
                    'native_utility': sum(row['grade'] for row in selected) / len(selected),
                    'native_units': len(selected), 'handled': sum(row['handled'] for row in selected),
                }
            complete = Counter(row['source'] for row in task_rows if row['grade'] != 1.0)
            metrics[library_name]['complete_mothers'] = 16 - len(complete)
        cni_rows = [row for row in rows if row['dataset'] == 'ContractNLI']
        if cni_rows:
            cni_annotations = annotations[binding['grading_paths']['ContractNLI']]
            evidence = [row['native_metrics'].get('evidence_f1', 0.0) for row in cni_rows
                        if cni_annotations[row['source']][row['view']].get('evidence') is not None]
            metrics['ContractNLI']['evidence_f1'] = {
                'mean': sum(evidence) / len(evidence) if evidence else None, 'native_units': len(evidence),
            }
        diversity = {row['source']: row['answer'] for row in rows if row['dataset'] == 'LegalBench_Diversity'}
        if diversity:
            gold = annotations[binding['grading_paths']['LegalBench_Diversity']]
            metrics['LegalBench_Diversity'].update(diversity_score(diversity, {name: gold[name] for name in diversity}))
        terminal = {'status': 'completed', 'DEV_mothers': len(dev), 'native_metrics': metrics,
                    'cell_sha256': cell['cell_sha256'], 'shared_B0_library_sha256': library['snapshot_sha256'],
                    'TRAIN_or_TEST_labels_loaded': False}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, POINTER)
        print(json.dumps(terminal), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
