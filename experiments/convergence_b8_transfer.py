"""Measure the B8 DEV effect of masking skills learned from other datasets."""

from functools import lru_cache
import json
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_formal_b1_dev import _routes
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_curves import _effects, pointer as curve_pointer
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


ARM = 'both'
POINTER = HANDOFF / 'formal_B8_transfer_current.json'


def _mask(library, initial, source_datasets, dataset):
    state = {k: v for k, v in library.items() if k != 'snapshot_sha256'}
    state['programs'] = {name: program if name == dataset else initial['programs'][name]
                         for name, program in state['programs'].items()}
    interface = state['interface_library']
    masked = {k: v for k, v in interface.items() if k != 'snapshot_sha256'}
    masked['visible_prefix'] = [key for key in interface['visible_prefix'] if source_datasets[key] == dataset]
    masked['observations'] = [row for row in interface['observations'] if row['dataset'] == dataset]
    if any(source_datasets[row['source']] != dataset for row in masked['observations']):
        raise ValueError('Interface learning evidence has inconsistent provenance')
    state['interface_library'] = sealed(masked, 'snapshot_sha256')
    return sealed(state, 'snapshot_sha256')


def run():
    baseline = ROOT / read(curve_pointer(8))['artifact_root']
    curve, terminal = read(baseline / 'binding.json'), read(baseline / 'terminal.json')
    root = ROOT / curve['checkpoint_root']
    study = read(root / 'binding.json')
    if (terminal['status'] != 'completed_five_arm_DEV' or terminal['batch'] != 8 or terminal['TEST_opened']
            or curve['checkpoint_binding_sha256'] != digest(study)):
        raise ValueError('The independent mask starts after the actual B8 DEV checkpoint')
    before = verify(read(root / 'dev/B8' / ARM / 'scores.json'), 'cell_sha256')
    if before['cell_sha256'] != terminal['cell_sha256'][ARM]:
        raise ValueError('Use the completed joint B8 cell as the unmasked comparison')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    library, initial = journal.library(ARM, 8), journal.library(ARM, 0)
    origins = {row['key']: row['dataset'] for cohort in batches for row in cohort}
    libraries = {dataset: _mask(library, initial, origins, dataset) for dataset in ConvergenceEvaluation.datasets}
    b0 = ROOT / curve['b0_dev_data_root']
    dev, identities = read(b0 / 'public_DEV_sources.json'), read(b0 / 'sealed_TEST_identity_metadata_only.json')
    files = set(curve['source_sha256']) | {'experiments/convergence_b8_transfer.py'}
    prior = {**curve['dev_replay_roots'], str(baseline.relative_to(ROOT)): sha(baseline / 'terminal.json')}
    binding = {'study': 'B8_fixed_DEV_cross_dataset_skill_mask', 'study_binding_sha256': digest(study),
              'unmasked_B8_cell_sha256': before['cell_sha256'], 'unmasked_B8_library_sha256': library['snapshot_sha256'],
              'masked_sha256': {dataset: cell['snapshot_sha256'] for dataset, cell in libraries.items()},
              'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
              'replay_roots': prior, 'executor': study['executor']}
    out = BASE / 'formal_B8_transfer' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json'), sort_keys=True), flush=True)
        return
    if any(sha(ROOT / folder / 'terminal.json') != expected for folder, expected in prior.items()):
        raise ValueError('The exact unmasked DEV evidence changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the active physical request to settle')
    datasets = {row['key']: row['dataset'] for row in dev}
    run_id = 'convergence-formal-B8-mask-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [], 'dev': sorted(datasets), 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / folder for folder in prior]
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    interface = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                               pipeline_binding=binding['source_sha256'])
    actor = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=interface,
                             providers={'LegalBench_Diversity': provider}, train_sources=origins, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(actor, reader, out), reader, out)

    @lru_cache(maxsize=None)
    def annotations(dataset):
        path = study['grading_paths'][dataset]
        if sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('DEV fold grading changed')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != set(datasets):
            raise ValueError('Mask evaluation requires sealed full-cohort predictions before grading')
        return annotations(datasets[key])[key]

    def no_test():
        raise ValueError('The transfer control uses only the fixed DEV data')

    evaluator = ConvergenceEvaluation(out, dev, identities, binding=study, grade_provider=grade, load_test=no_test)
    write_status(out, {'status': 'running', 'DEV_mothers': len(dev)}, POINTER)
    masked = evaluator.evaluate('dev', ARM, 8, libraries, actor)
    with ledger.transaction() as db:
        calls = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in calls):
        raise ValueError('Mask comparison requires physically settled evidence')
    result = {'status': 'completed_B8_DEV_skill_mask', 'masked_cell_sha256': masked['cell_sha256'],
              'masked_minus_unmasked': _effects(before['source_scores'], masked['source_scores']),
              'masked_routes': _routes(evaluator.cell_path('dev', ARM, 8), dev),
              'retained_interface_observations': {d: len(cell['interface_library']['observations'])
                                                  for d, cell in libraries.items()},
              'executor_calls': len(calls), 'executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                  for _, raw in calls), 'new_training': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'DEV_mothers': len(dev)}, POINTER)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
