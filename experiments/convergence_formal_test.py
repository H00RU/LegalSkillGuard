"""Seal the complete B8 study and evaluate the exact five-library TEST cohort."""

import argparse
from functools import lru_cache
import json
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_dev_b0 import POINTER as DEV_B0
from experiments.convergence_formal_b1_dev import _native_metrics, _routes
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import COMPARISONS, _effects, pointer as curve_pointer
from experiments.convergence_oe_metrics import summarize as openexempt_metrics
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_seal_source_roster import OLD, KNOWN_INCIDENT
from experiments.two_method_prepare_sources import CACHE, active_case_input, airline, rulearena_airline
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import (
    ConvergenceEvaluation, FormalEvaluation, check_library, sealed, verify,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_B8_TEST_current.json'
INITIAL_ARM = 'common_teacher_skill_learning'


def _verify_exposure(identities, roster, *, run_id=None):
    keys = {entry['source'] for entry in identities}
    for access in (BASE / 'formal_B8_test').glob('*/TEST_content_access.json'):
        opened_run = 'convergence-formal-B8-TEST-' + access.parent.name[:16]
        if run_id != opened_run:
            raise ValueError('This TEST cohort was opened under a different binding')
    historical = OLD / 'exposure/historical_exposure_index.json'
    index = read(historical)
    if index['failures'] or sha(historical) != roster['historical_exposure_sha256']:
        raise ValueError('Reconcile the current exposure inventory before opening the sealed cohort')
    exposed = set(index['source_keys'])
    incidents = sorted({KNOWN_INCIDENT, *(OLD / 'exposure/incidents').glob('*.json')})
    for path in incidents:
        for group in read(path)['conservative_affected_cohorts'].values():
            exposed.update(group['sources'])
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the previous physical request first')
        for identity, source, purpose in db.execute('select id,source,purpose from calls'):
            if source in keys and not (run_id and identity.startswith(run_id + ':') and purpose == 'skill_test'):
                exposed.add(source)
    if keys & exposed:
        raise ValueError('The exact TEST roster overlaps prior known exposure')
    return {str(path.relative_to(ROOT)): sha(path) for path in incidents}


def _closed(*args, **kwargs):
    raise ValueError('TEST content remains closed while preparing the freeze')


def _initial_reference_freeze(library, final_freeze):
    """Bind the inference-only reference to the same frozen TEST cohort."""
    check_library(library, INITIAL_ARM, 0)
    if (library['study_binding'] != final_freeze['study_binding'] or library['interface_library'] is not None
            or library.get('schema_proposals') or library['method_specific_pilot_state_loaded'] is not False):
        raise ValueError('The static reference requires the original shared initial library')
    return sealed({'batch': 8, 'B8_freeze_sha256': final_freeze['freeze_sha256'],
                   'TEST_identities_sha256': final_freeze['TEST_identities_sha256'],
                   'choices': {INITIAL_ARM: dict.fromkeys(sorted(ConvergenceEvaluation.datasets),
                       {'checkpoint_batch': 0, 'library_sha256': library['snapshot_sha256']})},
                   'reference_only': True}, 'freeze_sha256')


class _InitialReferenceEvaluation(FormalEvaluation):
    arms = (INITIAL_ARM,)

    def __init__(self, stage, final_evaluator, final_freeze, reference_freeze):
        self.final_evaluator = final_evaluator
        self.final_freeze = final_freeze
        self.reference_freeze = reference_freeze
        super().__init__(stage / 'initial_reference', final_evaluator.sources,
                         binding=final_evaluator.binding, grade_provider=final_evaluator.grade_provider)

    def verify_freeze(self, freeze):
        self.final_evaluator.verify_freeze(self.final_freeze)
        verify(freeze, 'freeze_sha256')
        if (freeze != self.reference_freeze or freeze['B8_freeze_sha256'] != self.final_freeze['freeze_sha256']
                or freeze['TEST_identities_sha256'] != self.final_freeze['TEST_identities_sha256']):
            raise ValueError('The initial-library evaluation requires its pre-inference reference binding')
        return freeze


def _archive_frozen_sources(stage, binding):
    for name, expected in binding['source_sha256'].items():
        source, destination = ROOT / name, stage / 'source_snapshot' / name
        if sha(source) != expected:
            raise ValueError('The prospective TEST runtime changed before archiving')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with destination.open('xb') as output:
                output.write(source.read_bytes())
        if sha(destination) != expected:
            raise ValueError('The frozen TEST runtime archive differs from its binding')
    immutable_json(stage / 'source_snapshot_receipt.json',
                   {'frozen_TEST_binding': stage.name, 'files': binding['source_sha256']})


def prepare():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    b0 = ROOT / read(DEV_B0)['artifact_root']
    dev, identities = read(b0 / 'public_DEV_sources.json'), read(b0 / 'sealed_TEST_identity_metadata_only.json')
    evaluator = ConvergenceEvaluation(root, dev, identities, binding=study, grade_provider=_closed, load_test=_closed)
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    training = journal.seal_B8()
    libraries = {(arm, batch): journal.library(arm, batch) for arm in evaluator.arms for batch in evaluator.curves}
    dev_b8 = ROOT / read(curve_pointer(8))['artifact_root']
    curve, terminal = read(dev_b8 / 'binding.json'), read(dev_b8 / 'terminal.json')
    if (terminal['TEST_opened'] or terminal['batch'] != 8 or terminal['status'] != 'completed_five_arm_DEV'
            or curve['checkpoint_binding_sha256'] != digest(study)):
        raise ValueError('Seal only after actual B8 DEV execution of the same study')
    roster_path = ROOT / read(HANDOFF / 'sealed_source_roster_current.json')['artifact_root'] / 'binding.json'
    roster = read(roster_path)
    if digest(roster) != study['roster_sha256'] or identities != roster['sealed_TEST_identities']:
        raise ValueError('The frozen TEST identity metadata changed')
    incidents = _verify_exposure(identities, roster)
    freeze = evaluator.freeze(libraries, training_B8_seal=training)
    initial_reference = _initial_reference_freeze(libraries[INITIAL_ARM, 0], freeze)
    files = set(curve['source_sha256']) | {'experiments/convergence_formal_test.py',
            'experiments/convergence_eval_cost_audit.py', 'experiments/convergence_eval_native_effects.py',
            'legal_skill_guard/paired_interfaces/convergence_effects.py',
            'experiments/two_method_prepare_sources.py', 'experiments/convergence_seal_source_roster.py'}
    spec = {'study': 'convergence_fixed_B8_TEST', 'checkpoint_root': str(root.relative_to(ROOT)),
            'B0_DEV_data_root': str(b0.relative_to(ROOT)), 'study_binding_sha256': digest(study),
            'B8_frozen_selection_sha256': freeze['freeze_sha256'], 'roster_path': str(roster_path.relative_to(ROOT)),
            'static_initial_reference': initial_reference,
            'prior_incidents_sha256': incidents, 'executor': study['executor'],
            'diversity_grading_root': read(HANDOFF / 'diversity_holdout_current.json')['artifact_root'],
            'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
            'TEST_content_opened_at_freeze': False}
    out = BASE / 'formal_B8_test' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    _archive_frozen_sources(out, spec)
    write_status(out, {'status': 'frozen_before_TEST', 'mothers': len(identities), 'arms': len(evaluator.arms),
                       'inference_references': 1}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def _grade_openexempt(targets):
    native = read(OLD / 'prospective_inventory/OpenExempt/construction_and_grading_only.json')
    results = {}
    for row in native['sources']:
        key = 'OpenExempt:' + digest(row['group'])
        if key not in targets:
            continue
        families = {view['id']: view['public']['original_input'] for view in targets[key]['views']}
        if families != {family: active_case_input(row['tasks'][family]) for family in ('EC', 'EV')}:
            raise ValueError('A fixed OpenExempt TEST target does not match its exact native views')
        results[key] = {family: {'family': family, 'answer': row['targets'][family]} for family in ('EC', 'EV')}
    return results


def _grade_airline(targets):
    archive = CACHE / 'RuleArena/airline'
    native = rulearena_airline(archive)
    results = {}
    for row in native.sources:
        if row.key not in targets or row.native_split != targets[row.key]['native_split']:
            continue
        view, = targets[row.key]['views']
        if view['public']['source_text'] != row.public['rules'] or view['public']['facts'] != row.public['prompt']:
            raise ValueError('A fixed Airline TEST target does not match the native case')
        if row.key in results:
            raise ValueError('A fixed Airline TEST target must identify a unique native case')
        key = digest({'key': row.key, 'split': row.native_split, 'content': row.content_key})
        inputs = native.grading[key]['reference_arguments']
        results[row.key] = {'native': {'answer': airline(inputs, root=archive)}}
    return results


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    archived = read(out / 'source_snapshot_receipt.json')
    root, b0 = ROOT / binding['checkpoint_root'], ROOT / binding['B0_DEV_data_root']
    study, freeze = read(root / 'binding.json'), read(root / 'selection_freeze.json')
    roster = read(ROOT / binding['roster_path'])
    dev, identities = read(b0 / 'public_DEV_sources.json'), read(b0 / 'sealed_TEST_identity_metadata_only.json')
    if (out.name != digest(binding) or archived != {'frozen_TEST_binding': out.name, 'files': binding['source_sha256']}
            or any(sha(out / 'source_snapshot' / file) != expected for file, expected in archived['files'].items())
            or study['roster_sha256'] != digest(roster)
            or digest(study) != binding['study_binding_sha256'] or identities != roster['sealed_TEST_identities']
            or freeze['freeze_sha256'] != binding['B8_frozen_selection_sha256']
            or any(sha(ROOT / file) != expected for file, expected in binding['source_sha256'].items())):
        raise ValueError('TEST requires the exact production runtime and sealed B8 cohort')
    run_id = 'convergence-formal-B8-TEST-' + out.name[:16]
    if _verify_exposure(identities, roster, run_id=run_id) != binding['prior_incidents_sha256']:
        raise ValueError('Reconcile the updated exposure records before executing the sealed cohort')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    if journal.seal_B8() != freeze['training_B8_seal']:
        raise ValueError('The completed TRAIN histories differ from the B8 freeze')
    initial = journal.library(INITIAL_ARM, 0)
    reference_freeze = _initial_reference_freeze(initial, freeze)
    if reference_freeze != binding['static_initial_reference']:
        raise ValueError('TEST requires the exact initial-library reference bound before opening the cohort')
    datasets = {entry['source']: entry['dataset'] for entry in identities}
    normalized = ROOT / roster['normalized_root'] / 'sealed_test'
    diversity = ROOT / binding['diversity_grading_root'] / 'sealed_test' / 'grading.json'
    access = {'freeze_sha256': freeze['freeze_sha256'], 'purpose': 'locked_final_test_inference'}
    sources = {}

    def load_test():
        immutable_json(out / 'TEST_content_access.json', access)
        result = read(normalized / 'public.json')
        sources.update({source['key']: source for source in result})
        return result

    @lru_cache(maxsize=None)
    def grades(dataset):
        targets = {key: row for key, row in sources.items() if row['dataset'] == dataset}
        if dataset == 'OpenExempt':
            result = _grade_openexempt(targets)
        elif dataset == 'RuleArena_Airline':
            result = _grade_airline(targets)
        else:
            document = read(diversity if dataset == 'LegalBench_Diversity' else normalized / 'CNI_MAUD_grading_only.json')
            result = {key: document[key] for key in targets}
        if len(targets) != 32 or {key: set(tasks) for key, tasks in result.items()} != {
                key: {view['id'] for view in row['views']} for key, row in targets.items()}:
            raise ValueError('The independent scorer must match the exact TEST mothers and views')
        receipt = {'grading_sha256': digest(result), 'mothers': len(targets), 'freeze_sha256': freeze['freeze_sha256']}
        if dataset == 'ContractNLI':
            receipt['evidence_units'] = sorted([key, view] for key, views in result.items()
                                               for view, annotation in views.items() if annotation.get('evidence') is not None)
        immutable_json(out / 'grading_receipts' / (dataset + '.json'), receipt)
        return result

    def grade(partition, key, seal):
        if partition != 'test' or set(seal['predictions_sha256']) != set(datasets):
            raise ValueError('Open native TEST targets only after sealing this arm’s entire predictions')
        immutable_json(out / 'TEST_label_access.json', {**access, 'purpose': 'sealed_predictions_native_grading'})
        return grades(datasets[key])[key]

    evaluator = ConvergenceEvaluation(root, dev, identities, binding=study, grade_provider=grade, load_test=load_test)
    evaluator.verify_freeze(freeze)
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [], 'dev': [], 'test': sorted(datasets)},
        binding=binding, freeze={'batch': 8, 'artifact_sha256': freeze['freeze_sha256']})
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    interface = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                               pipeline_binding=binding['source_sha256'])
    visible = [row['key'] for part in batches for row in part]
    primary = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=interface,
                               providers={'LegalBench_Diversity': provider}, train_sources=visible, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(primary, reader, out), reader, out)
    scores, per_arm = {}, {}
    for arm in evaluator.arms:
        write_status(out, {'status': 'running', 'arm': arm, 'freeze_sha256': freeze['freeze_sha256']}, POINTER)
        library = journal.library(arm, 8)
        cell = evaluator.evaluate('test', arm, 8, dict.fromkeys(evaluator.datasets, library), actor, freeze=freeze)
        scores[arm] = cell['source_scores']
        per_arm[arm] = {'cell_sha256': cell['cell_sha256'],
            'native': _native_metrics(scores[arm], grades, {dataset: dataset for dataset in evaluator.datasets}),
            'official_OpenExempt': openexempt_metrics(scores[arm]),
            'routes': _routes(evaluator.cell_path('test', arm, 8), evaluator.sources['test'])}
    write_status(out, {'status': 'running', 'arm': 'static_initial_reference',
                       'freeze_sha256': freeze['freeze_sha256']}, POINTER)
    reference = _InitialReferenceEvaluation(out, evaluator, freeze, reference_freeze)
    cell = reference.evaluate('test', INITIAL_ARM, 8, dict.fromkeys(evaluator.datasets, initial), actor,
                              freeze=reference_freeze)
    reference_scores = cell['source_scores']
    initial_report = {'cell_sha256': cell['cell_sha256'], 'reference_freeze_sha256': reference_freeze['freeze_sha256'],
                      'checkpoint_batch': 0, 'reference_only': True,
                      'native': _native_metrics(reference_scores, grades, {d: d for d in evaluator.datasets}),
                      'official_OpenExempt': openexempt_metrics(reference_scores),
                      'routes': _routes(reference.cell_path('test', INITIAL_ARM, 8), evaluator.sources['test']),
                      'joint_minus_initial': _effects(reference_scores, scores['both'],
                                                      diversity_annotations=grades('LegalBench_Diversity'))}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in physical):
        raise ValueError('Reconcile physical TEST reads before certifying the evaluation')
    result = {'status': 'completed_fixed_B8_TEST', 'mothers_per_arm': len(datasets), 'per_arm': per_arm,
              'static_initial_reference': initial_report,
              'paired_effects': {later + '_minus_' + earlier: _effects(scores[earlier], scores[later],
                                 diversity_annotations=grades('LegalBench_Diversity'))
                                 for earlier, later in COMPARISONS},
              'grading_receipts_sha256': {dataset: sha(out / 'grading_receipts' / (dataset + '.json'))
                                          for dataset in sorted(evaluator.datasets)},
              'freeze_sha256': freeze['freeze_sha256'], 'executor_calls': len(physical),
              'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in physical)}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'arms': len(per_arm), 'inference_references': 1}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
