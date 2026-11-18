"""Evaluate the five actually fitted B1 libraries on the unchanged DEV cohort."""

import argparse
from collections import Counter
from functools import lru_cache
import json
import math
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_dev_b0 import POINTER as DEV_B0
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_b1_primary import POINTER as FIT
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.diversity import score as diversity_score
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_b1_dev_current.json'


def _native_metrics(rows, grade_file, grading_paths):
    metrics = {}
    for dataset in sorted(ConvergenceEvaluation.datasets):
        selected = [row for row in rows if row['dataset'] == dataset]
        views = sorted({row['view'] for row in selected}) if dataset in ('OpenExempt', 'MAUD') else ['all']
        view_metrics = {}
        for view in views:
            cells = [row for row in selected if view == 'all' or row['view'] == view]
            view_metrics[view] = {'native_units': len(cells), 'handled': sum(row['handled'] for row in cells),
                                  'native_utility': math.fsum(row['grade'] for row in cells) / len(cells)}
        failed_mothers = {row['source'] for row in selected if row['grade'] != 1}
        outcome = {'views': view_metrics, 'complete_mothers': len({row['source'] for row in selected} - failed_mothers)}
        if dataset == 'ContractNLI':
            gold = grade_file(grading_paths[dataset])
            scores = [row['native_metrics'].get('evidence_f1', 0.) for row in selected
                      if gold[row['source']][row['view']].get('evidence') is not None]
            outcome['evidence_f1'] = {'native_units': len(scores), 'mean': math.fsum(scores) / len(scores) if scores else None}
        if dataset == 'LegalBench_Diversity':
            answers = {row['source']: row['answer'] for row in selected}
            gold = grade_file(grading_paths[dataset])
            outcome.update(diversity_score(answers, {key: gold[key] for key in answers}))
        metrics[dataset] = outcome
    return metrics


def _routes(directory, dev):
    routes = Counter()
    for source in dev:
        result = read(directory / 'predictions' / (digest(source['key']) + '.json'))['result']
        if 'schema_reads' in result:
            route = 'learned_external_schema'
        elif 'measured' in result:
            route = 'common_compiled_fees'
        else:
            route = result['selection']['route']
        routes[(source['dataset'], route)] += 1
    return {dataset: {route: count for (name, route), count in routes.items() if dataset == name}
            for dataset in sorted({source['dataset'] for source in dev})}


def prepare():
    fitted = ROOT / read(FIT)['artifact_root']
    binding, terminal = read(fitted / 'binding.json'), read(fitted / 'terminal.json')
    root = ROOT / binding['bootstrap_root']
    study = read(root / 'binding.json')
    if (terminal['status'] != 'completed_all_five_B1_updates' or terminal['TEST_opened']
            or digest(study) != binding['study_binding_sha256']):
        raise ValueError('Only actual five-arm TRAIN updates can enter the B1 DEV checkpoint')
    journal = TrainingJournal(root, study, load_roster(study))
    receipts = {arm: journal._completed_batch(arm, 1)['completed_batch_sha256'] for arm in ConvergenceEvaluation.arms}
    if terminal['arm_receipts'] != receipts:
        raise ValueError('Bind every actual committed B1 state before DEV')
    baseline = ROOT / read(DEV_B0)['artifact_root']
    fees = ROOT / read(HANDOFF / 'airline_shared_fee_dev_current.json')['artifact_root']
    previous = read(baseline / 'binding.json')
    if (previous['executor'] != study['executor'] or previous['DEV_public_sha256'] != study['DEV_public_sha256']
            or sha(fees / 'terminal.json') != study['common_fee_terminal_sha256']):
        raise ValueError('Exact-wire cache reuse requires the common model profile and DEV partitions')
    files = set(binding['source_sha256']) | {'experiments/convergence_formal_b1_dev.py',
        'experiments/convergence_parse_runtime.py', 'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
        'legal_skill_guard/paired_interfaces/convergence_effects.py', 'legal_skill_guard/paired_interfaces/diversity_claim_groups.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py', 'legal_skill_guard/paired_interfaces/formal_evaluation.py'}
    spec = {'study': 'convergence_real_five_arm_B1_DEV', 'checkpoint_root': binding['bootstrap_root'],
            'checkpoint_binding_sha256': digest(study), 'arm_library_sha256': {arm: journal.library(arm, 1)['snapshot_sha256']
                for arm in ConvergenceEvaluation.arms}, 'B1_TRAIN_receipts': receipts, 'executor': study['executor'],
            'DEV_profile_receipts': {str(path.relative_to(ROOT)): sha(path / 'terminal.json') for path in (baseline, fees)},
            'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}}
    out = BASE / 'formal_b1_dev' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'DEV_mothers': 80, 'arms': len(receipts)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding = read(out / 'binding.json')
    root = ROOT / binding['checkpoint_root']
    study = read(root / 'binding.json')
    baseline = ROOT / read(DEV_B0)['artifact_root']
    dev = read(baseline / 'public_DEV_sources.json')
    identities = read(baseline / 'sealed_TEST_identity_metadata_only.json')
    if (out.name != digest(binding) or digest(study) != binding['checkpoint_binding_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())
            or any(sha(ROOT / path / 'terminal.json') != expected for path, expected in binding['DEV_profile_receipts'].items())):
        raise ValueError('The checkpoint scope, proof or runtime changed after binding')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    for arm in ConvergenceEvaluation.arms:
        if (journal.library(arm, 1)['snapshot_sha256'] != binding['arm_library_sha256'][arm]
                or journal._completed_batch(arm, 1)['completed_batch_sha256'] != binding['B1_TRAIN_receipts'][arm]):
            raise ValueError('DEV cannot use a changed or selectively chosen learned library')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the previous physical request first')
    keys = {source['key']: source['dataset'] for source in dev}
    ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-DEV-' + out.name[:16],
                             sources={'train': [], 'dev': sorted(keys), 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / path for path in binding['DEV_profile_receipts']]
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    interface = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                               pipeline_binding=binding['source_sha256'])
    primary = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=interface,
                               providers={'LegalBench_Diversity': provider}, train_sources=[s['key'] for s in batches[0]],
                               study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(primary, reader, out), reader, out)

    @lru_cache(maxsize=None)
    def grade_file(path):
        if sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('DEV grading must retain the fixed benchmark file')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != set(keys):
            raise ValueError('Wait for native prediction sealing before reading DEV labels')
        return grade_file(study['grading_paths'][keys[key]])[key]

    def no_test():
        raise ValueError('The B1 evaluator cannot access TEST')

    evaluator = ConvergenceEvaluation(root, dev, identities, binding=study, grade_provider=grade, load_test=no_test)
    rows, cells, verified_scores = {}, {}, {}
    for arm in ConvergenceEvaluation.arms:
        write_status(out, {'status': 'running', 'arm': arm}, POINTER)
        library = journal.library(arm, 1)
        evaluation = evaluator.evaluate('dev', arm, 1, dict.fromkeys(ConvergenceEvaluation.datasets, library), actor)
        cells[arm] = evaluation['cell_sha256']
        before = verify(read(root / 'dev/B0' / arm / 'scores.json'), 'cell_sha256')
        scores = evaluation['source_scores']
        verified_scores[arm] = scores
        effects = {}
        for dataset in sorted(ConvergenceEvaluation.datasets):
            prior = [row for row in before['source_scores'] if row['dataset'] == dataset]
            current = [row for row in scores if row['dataset'] == dataset]
            effects[dataset] = paired_source_effect(prior, current)
        rows[arm] = {'paired_B1_minus_B0': effects, 'native': _native_metrics(scores, grade_file, study['grading_paths']),
                     'routes': _routes(root / 'dev/B1' / arm, dev)}
    comparisons = [('common_teacher_skill_learning', 'method_one_only'),
                   ('common_teacher_skill_learning', 'method_two_only'), ('method_two_only', 'both'),
                   ('method_one_only', 'both'), ('strongest_matched_external_baseline', 'both')]
    ablations = {}
    for earlier, later in comparisons:
        ablations[later + '_minus_' + earlier] = {dataset: paired_source_effect(
            [row for row in verified_scores[earlier] if row['dataset'] == dataset],
            [row for row in verified_scores[later] if row['dataset'] == dataset]) for dataset in sorted(ConvergenceEvaluation.datasets)}
    with ledger.transaction() as db:
        measured = db.execute('select status,result from calls where id like ?', (ledger.run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in measured):
        raise ValueError('Every new B1 DEV physical read must be settled')
    result = {'status': 'completed_five_arm_B1_DEV', 'cell_sha256': cells, 'per_arm': rows,
              'paired_independent_arm_comparisons': ablations, 'DEV_mothers': len(dev),
              'executor_calls': len(measured), 'executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                  for _, raw in measured), 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'cells': len(cells)}, POINTER)
    print(json.dumps({'status': result['status'], 'cells': len(cells)}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
