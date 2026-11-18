"""Measure the B8 DEV effect of masking skills learned from other datasets."""

from functools import lru_cache
import json
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_eval_cost_audit import _physical_refs
from experiments.convergence_formal_b1_dev import _routes
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_b1_primary import POINTER as B1_PRIMARY
from experiments.convergence_formal_curves import _effects, pointer as curve_pointer
from experiments.convergence_formal_train_fit import ORDINARY, pointer as fit_pointer
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import EVInventoryActor
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


ARM = 'both'
POINTER = HANDOFF / 'formal_B8_transfer_current.json'


def _proposal_origin(db, journal, fit, batch, dataset, program, matched):
    candidate = fit / 'candidates' / ORDINARY / dataset
    if batch == 1:
        decision = read(candidate / 'decision.json')
        if decision['selected'] != 'candidate' or decision['candidate_sha256'] != digest(program):
            raise ValueError('The B1 program needs its measured winning proposal')
        call, proposal = decision['teacher_physical_call_id'], decision['teacher_proposal_sha256']
    else:
        decision = matched['teacher'][ORDINARY][dataset]
        relation = matched['relation'][dataset]
        if relation['status'] != 'eligible_train_update' or relation['matched_proposal_sha256'] != digest(program):
            raise ValueError('The joint program needs its actual accepted TRAIN update')
        call, proposal = decision['teacher_call'], decision['proposal_sha256']
    expected = [row['key'] for row in journal.batches[batch - 1] if row['dataset'] == dataset]
    settled = db.execute('select role,status,source,purpose,result from calls where id=?', (call,)).fetchone()
    if not expected or not settled or settled[:4] != ('teacher', 'completed', expected[0], 'skill_teacher'):
        raise ValueError('A changed program needs an exact physically settled teacher request')
    response = json.loads(settled[-1])
    if response['source_ids'] != expected or digest(response['value']) != proposal:
        raise ValueError('A learned program lost its actual proposal source links')
    return {'batch': batch, 'artifact_sha256': digest(program), 'proposal_source_ids': expected,
            'teacher_physical_call_id': call, 'training_datasets': [dataset]}


def _program_provenance(journal, through=8):
    initial = journal.library(ARM, 0)['programs']
    origin = {dataset: {'artifact_sha256': digest(program), 'training_datasets': [], 'proposal_history': []}
              for dataset, program in initial.items()}
    before = initial
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch in range(1, through + 1):
            stage = ROOT / read(B1_PRIMARY if batch == 1 else fit_pointer(batch))['artifact_root']
            bind, terminal = read(stage / 'binding.json'), read(stage / 'terminal.json')
            current = journal.library(ARM, batch)['programs']
            if (digest(bind) != stage.name or bind['study_binding_sha256'] != digest(journal.binding)
                    or terminal['TEST_opened'] or terminal['arm_receipts'][ARM] != journal._completed_batch(
                        ARM, batch)['completed_batch_sha256']):
                raise ValueError('Transfer provenance requires the verified joint training history')
            fit, matched = stage, None
            if batch == 1:
                receipt = bind['stages']['controls']
                fit = ROOT / receipt['root']
                if sha(fit / 'terminal.json') != receipt['terminal_sha256']:
                    raise ValueError('The original B1 teacher comparison changed')
            else:
                matched = read(stage / 'matched_decisions.json')
                if digest(matched) != terminal['matched_decisions_sha256']:
                    raise ValueError('The matched teacher and update decisions changed')
            for dataset, program in current.items():
                if program == before[dataset]:
                    continue
                version = _proposal_origin(db, journal, fit, batch, dataset, program, matched)
                lineage = origin[dataset]['proposal_history'] + [version]
                origin[dataset] = {'artifact_sha256': version['artifact_sha256'], 'proposal_history': lineage,
                                   'training_datasets': [] if program == initial[dataset] else version['training_datasets']}
            before = current
    return origin


def _mask(library, initial, source_datasets, program_origins, dataset):
    state = {k: v for k, v in library.items() if k != 'snapshot_sha256'}
    state['programs'] = {}
    for name, program in library['programs'].items():
        origins = program_origins[name]
        if origins['artifact_sha256'] != digest(program):
            raise ValueError('The mask must use the origins of the exact selected program version')
        datasets = origins['training_datasets']
        state['programs'][name] = initial['programs'][name] if datasets and dataset not in datasets else program
    interface = state['interface_library']
    masked = {k: v for k, v in interface.items() if k != 'snapshot_sha256'}
    masked['visible_prefix'] = [key for key in interface['visible_prefix'] if source_datasets[key] == dataset]
    masked['observations'] = [row for row in interface['observations'] if row['dataset'] == dataset]
    if any(source_datasets[row['source']] != dataset for row in masked['observations']):
        raise ValueError('Interface learning evidence has inconsistent provenance')
    state['interface_library'] = sealed(masked, 'snapshot_sha256')
    return sealed(state, 'snapshot_sha256')


def _execution_provenance(directory, report, cohort, libraries, program_origins, training_datasets):
    seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
    if (seal['prediction_seal_sha256'] != report['prediction_seal_sha256']
            or set(seal['predictions_sha256']) != {row['key'] for row in cohort}):
        raise ValueError('Transfer traces must identify the same complete fixed DEV cohort')
    evidence = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for source in cohort:
            key, dataset = source['key'], source['dataset']
            row = read(directory / 'predictions' / (digest(key) + '.json'))
            library = libraries[dataset]
            if digest(row) != seal['predictions_sha256'][key] or row['library_sha256'] != library['snapshot_sha256']:
                raise ValueError('The mask comparison lost its actual routed library or source')
            result = row['result']
            origins, route = set(), 'common_compiled_fees'
            selected_program, selected_sources = None, []
            if 'selection' in result:
                route = result['selection']['route']
                if route == 'synthesized_interface':
                    supported = {r['source'] for r in library['interface_library']['observations']}
                    selected_sources = sorted({key for choice in result['selection']['choices']
                                               for key in choice['paired_learning_sources']})
                    if not set(selected_sources) <= supported:
                        raise ValueError('A selected interface refers to missing calibration observations')
                    origins = {training_datasets[k] for k in selected_sources}
                elif route == 'common_program':
                    selected_program = digest(library['programs'][dataset])
                    if any(readout['execution']['program_sha256'] != selected_program for readout in result['reads']):
                        raise ValueError('Saved DEV reads do not use the attributed program version')
                    current = program_origins[dataset]
                    if current['artifact_sha256'] == selected_program:
                        origins = set(current['training_datasets'])
                        if origins:
                            selected_sources = current['proposal_history'][-1]['proposal_source_ids']
                else:
                    raise ValueError('The joint transfer comparison has an unexpected inference route')
            elif 'measured' not in result:
                raise ValueError('The common fee route needs its actual rule measurement')
            physical = sorted(set(_physical_refs(result)))
            if any(db.execute('select role,status,source,purpose from calls where id=?', (ident,)).fetchone()
                   != ('executor', 'completed', key, 'skill_dev') for ident in physical):
                raise ValueError('Every transfer read must retain its original physical DEV request')
            evidence[key] = {'dataset': dataset, 'route': route, 'selected_program_sha256': selected_program,
                             'selected_training_sources': selected_sources,
                             'training_datasets': sorted(origins), 'physical_call_ids': physical,
                             'uses_cross_dataset_learning': bool(physical and origins - {dataset})}
    return evidence


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
    programs = _program_provenance(journal)
    libraries = {dataset: _mask(library, initial, origins, programs, dataset) for dataset in ConvergenceEvaluation.datasets}
    b0 = ROOT / curve['b0_dev_data_root']
    dev, identities = read(b0 / 'public_DEV_sources.json'), read(b0 / 'sealed_TEST_identity_metadata_only.json')
    files = set(curve['source_sha256']) | {'experiments/convergence_b8_transfer.py',
                                           'experiments/convergence_eval_cost_audit.py'}
    prior = {**curve['dev_replay_roots'], str(baseline.relative_to(ROOT)): sha(baseline / 'terminal.json')}
    binding = {'study': 'B8_fixed_DEV_cross_dataset_skill_mask', 'study_binding_sha256': digest(study),
              'unmasked_B8_cell_sha256': before['cell_sha256'], 'unmasked_B8_library_sha256': library['snapshot_sha256'],
              'masked_sha256': {dataset: cell['snapshot_sha256'] for dataset, cell in libraries.items()},
              'actual_program_provenance_sha256': digest(programs),
              'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
              **({'ev_asset_inventory_wire': True} if curve.get('ev_asset_inventory_wire') else {}),
              'replay_roots': prior, 'executor': study['executor']}
    out = BASE / 'formal_B8_transfer' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'program_provenance.json', programs)
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
    if binding.get('ev_asset_inventory_wire'):
        actor = EVInventoryActor(actor)

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
    evidence = {'unmasked': _execution_provenance(root / 'dev/B8' / ARM, before, dev,
                                                 dict.fromkeys(evaluator.datasets, library), programs, origins),
                'masked': _execution_provenance(evaluator.cell_path('dev', ARM, 8), masked, dev, libraries, programs, origins)}
    immutable_json(out / 'execution_provenance.json', evidence)
    with ledger.transaction() as db:
        calls = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in calls):
        raise ValueError('Mask comparison requires physically settled evidence')
    result = {'status': 'completed_B8_DEV_skill_mask', 'masked_cell_sha256': masked['cell_sha256'],
              'execution_provenance_sha256': digest(evidence),
              'cross_dataset_learning_hits': {d: {name: sum(row['uses_cross_dataset_learning']
                  for row in traces.values() if row['dataset'] == d) for name, traces in evidence.items()}
                  for d in sorted(evaluator.datasets)},
              'masked_minus_unmasked': _effects(before['source_scores'], masked['source_scores'],
                                                diversity_annotations=annotations('LegalBench_Diversity')),
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
