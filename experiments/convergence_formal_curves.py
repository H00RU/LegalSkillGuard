"""Evaluate the fixed B2, B4 and B8 development checkpoints with exact replay."""

import argparse
from functools import lru_cache
import json
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_dev_b0 import POINTER as DEV_B0
from experiments.convergence_formal_b1_dev import POINTER as FIRST_DEV, _native_metrics, _routes
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_oe_metrics import summarize as openexempt_metrics
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


CHECKPOINTS = (2, 4, 8)
COMPARISONS = (('common_teacher_skill_learning', 'method_one_only'),
               ('common_teacher_skill_learning', 'method_two_only'), ('method_two_only', 'both'),
               ('method_one_only', 'both'), ('strongest_matched_external_baseline', 'both'))


def pointer(batch):
    return HANDOFF / f'formal_B{batch}_DEV_current.json'


def prepare(batch):
    fitted = ROOT / read(fit_pointer(batch))['artifact_root']
    binding, fit = read(fitted / 'binding.json'), read(fitted / 'terminal.json')
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if (fit['status'] != 'completed_all_five_TRAIN_updates' or fit['batch'] != batch
            or fit['TEST_opened'] or binding['study_binding_sha256'] != digest(study)):
        raise ValueError('Each DEV checkpoint requires its own completed five-arm TRAIN state')
    journal = TrainingJournal(checkpoint, study, load_roster(study))
    receipts = {arm: journal._completed_batch(arm, batch) for arm in ConvergenceEvaluation.arms}
    if fit['arm_receipts'] != {arm: row['completed_batch_sha256'] for arm, row in receipts.items()}:
        raise ValueError('Use the same five snapshots committed by the measured update')
    first = ROOT / read(FIRST_DEV)['artifact_root']
    first_binding = read(first / 'binding.json')
    prior = [first, *(ROOT / read(pointer(index))['artifact_root'] for index in CHECKPOINTS if index < batch)]
    replay = dict(first_binding['DEV_profile_receipts'])
    for stage in prior:
        document = read(stage / 'terminal.json')
        if document['TEST_opened'] or read(stage / 'binding.json')['executor'] != study['executor']:
            raise ValueError('DEV replay requires verified settled evidence from the same executor profile')
        replay[str(stage.relative_to(ROOT))] = sha(stage / 'terminal.json')
    b0 = ROOT / read(DEV_B0)['artifact_root']
    if str(b0.relative_to(ROOT)) not in replay:
        raise ValueError('Recover the original DEV public sources and TEST metadata')
    files = set(binding['source_sha256']) | set(first_binding['source_sha256']) | {
        'experiments/convergence_formal_curves.py', 'experiments/convergence_oe_metrics.py'}
    spec = {'study': 'convergence_fixed_DEV_curve', 'batch': batch,
            'checkpoint_root': binding['checkpoint_root'], 'checkpoint_binding_sha256': digest(study),
            'train_receipts': receipts, 'b0_dev_data_root': str(b0.relative_to(ROOT)), 'executor': study['executor'],
            'dev_replay_roots': replay, 'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}}
    out = BASE / 'formal_curves' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'batch': batch, 'DEV_mothers': 80, 'arms': len(receipts)}, pointer(batch))
    print(json.dumps(read(pointer(batch)), sort_keys=True), flush=True)


def _effects(earlier, later, *, diversity_annotations=None):
    effects = {}
    for dataset in sorted(ConvergenceEvaluation.datasets):
        before = [row for row in earlier if row['dataset'] == dataset]
        after = [row for row in later if row['dataset'] == dataset]
        result = paired_source_effect(before, after)
        if dataset == 'LegalBench_Diversity' and diversity_annotations is not None:
            strata = {row['source']: diversity_annotations[row['source']]['native']['answer'] for row in before}
            if not set(strata.values()) <= {'Yes', 'No'}:
                raise ValueError('Use the original native Diversity classes for balanced accuracy')
            result['balanced_accuracy_effect'] = paired_source_effect(before, after, strata=strata)
        effects[dataset] = result
    return effects


def run(batch):
    out = ROOT / read(pointer(batch))['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json'), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    checkpoint, b0 = ROOT / binding['checkpoint_root'], ROOT / binding['b0_dev_data_root']
    study = read(checkpoint / 'binding.json')
    if (binding['batch'] != batch or out.name != digest(binding) or digest(study) != binding['checkpoint_binding_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())
            or any(sha(ROOT / root / 'terminal.json') != expected for root, expected in binding['dev_replay_roots'].items())):
        raise ValueError('Exact DEV checkpoint bindings changed')
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    if any(journal._completed_batch(arm, batch) != row for arm, row in binding['train_receipts'].items()):
        raise ValueError('Changing the selected TRAIN snapshot invalidates the DEV checkpoint')
    dev, identities = read(b0 / 'public_DEV_sources.json'), read(b0 / 'sealed_TEST_identity_metadata_only.json')
    keys = {source['key']: source['dataset'] for source in dev}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the previous physical request first')
    run_id = f'convergence-formal-B{batch}-DEV-{out.name[:16]}'
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [], 'dev': sorted(keys), 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / root for root in binding['dev_replay_roots']]
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    interface = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                               pipeline_binding=binding['source_sha256'])
    visible = [source['key'] for cohort in batches[:batch] for source in cohort]
    primary = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=interface,
                               providers={'LegalBench_Diversity': provider}, train_sources=visible, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(primary, reader, out), reader, out)

    @lru_cache(maxsize=None)
    def grade_file(path):
        if sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('The independent DEV scorer changed')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != set(keys):
            raise ValueError('DEV labels require a complete sealed DEV prediction cohort')
        return grade_file(study['grading_paths'][keys[key]])[key]

    def no_test():
        raise ValueError('This evaluator only measures DEV')

    evaluator = ConvergenceEvaluation(checkpoint, dev, identities, binding=study, grade_provider=grade, load_test=no_test)
    per_arm, scores, cells = {}, {}, {}
    for arm in ConvergenceEvaluation.arms:
        write_status(out, {'status': 'running', 'batch': batch, 'arm': arm}, pointer(batch))
        library = journal.library(arm, batch)
        cell = evaluator.evaluate('dev', arm, batch, dict.fromkeys(ConvergenceEvaluation.datasets, library), actor)
        cells[arm], scores[arm] = cell['cell_sha256'], cell['source_scores']
        b0_cell = verify(read(evaluator.cell_path('dev', arm, 0) / 'scores.json'), 'cell_sha256')
        diversity_annotations = grade_file(study['grading_paths']['LegalBench_Diversity'])
        per_arm[arm] = {'native': _native_metrics(scores[arm], grade_file, study['grading_paths']),
                        'official_OpenExempt': openexempt_metrics(scores[arm]),
                        'paired_minus_B0': _effects(b0_cell['source_scores'], scores[arm],
                                                    diversity_annotations=diversity_annotations),
                        'routes': _routes(evaluator.cell_path('dev', arm, batch), dev)}
    effects = {later + '_minus_' + earlier: _effects(scores[earlier], scores[later],
                                                    diversity_annotations=diversity_annotations)
               for earlier, later in COMPARISONS}
    with ledger.transaction() as db:
        measured = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in measured):
        raise ValueError('All new physical DEV reads must be settled')
    result = {'status': 'completed_five_arm_DEV', 'batch': batch, 'cell_sha256': cells, 'per_arm': per_arm,
              'paired_independent_arm_comparisons': effects, 'DEV_mothers': len(dev),
              'executor_calls': len(measured), 'executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                  for _, raw in measured), 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'batch': batch, 'cells': len(cells)}, pointer(batch))
    print(json.dumps(read(pointer(batch)), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('--batch', type=int, required=True, choices=CHECKPOINTS)
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)(args.batch)
