"""Verify and rebind the paid common DEV observations to all five B0 arms."""

from contextlib import closing
from functools import lru_cache
import json
import sqlite3

from experiments.convergence_common_airline_actor import CommonAirlineActor, supported_fee_rule
from experiments.convergence_dev_b0 import ARM, CommonInitialActor, POINTER as B0
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_actors import initial_libraries
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.objects import digest


class ReadOnlyLedger:
    def transaction(self):
        return closing(sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True))


class SharedDevReplay:
    """Reference saved predictions, audit their physical reads and keep the library fixed."""

    def __init__(self, baseline, fees, binding):
        self.baseline, self.fees, self.binding = baseline, fees, binding
        prior = read(baseline / 'binding.json')
        self.original_library = verify(read(baseline / 'common_initial_library.json'), 'snapshot_sha256')
        self.original_predictions = baseline / 'dev/B0' / ARM
        self.original_seal = verify(read(self.original_predictions / 'prediction_seal.json'), 'prediction_seal_sha256')
        self.executor = FrozenExecutor(ReadOnlyLedger(), baseline, prior['executor'])
        self.original_actor = CommonInitialActor(self.executor, baseline)
        self.fee_actor = CommonAirlineActor(self.original_actor, self.executor, fees)
        cases = read(fees / 'cases.json')
        if digest(cases) != read(fees / 'binding.json')['cases_sha256']:
            raise ValueError('The measured public fee cohort changed')
        self.fee_sources = {case['source']['key']: case for case in cases}
        self.fee_seal = read(fees / 'prediction_seal.json')
        if self.fee_seal['sources'] != list(self.fee_sources) or digest([
                read(fees / 'measurements' / (digest(case['source']) + '.json'))
                for case in cases]) != self.fee_seal['predictions_sha256']:
            raise ValueError('The shared fee observations differ from the original prediction seal')

    @lru_cache(maxsize=96)
    def _prediction(self, key, public_sha256, public_source):
        source = json.loads(public_source)
        rule = supported_fee_rule(source)
        case = self.fee_sources.get(key)
        if (rule is None) != (case is None):
            raise ValueError('The public Airline routing coverage must match the measured DEV repair')
        if case is not None:
            if case['source'] != source or case['rule'] != rule:
                raise ValueError('The shared fee route must use its exact measured public source and rule')
            path = self.fees / 'measurements' / (public_sha256 + '.json')
            record = read(path)
            result = self.fee_actor._result(rule, record)
            self.fee_actor.verify_saved(source, self.original_library, 'skill_dev', result)
            source_asset = self.fee_seal['predictions_sha256']
        else:
            path = self.original_predictions / 'predictions' / (digest(key) + '.json')
            record = read(path)
            if (digest(record) != self.original_seal['predictions_sha256'][key]
                    or record['public_source_sha256'] != public_sha256
                    or record['library_sha256'] != self.original_library['snapshot_sha256']):
                raise ValueError('The original DEV observation does not bind the measured B0 library and source')
            result = record['result']
            self.original_actor.verify_saved(source, self.original_library, 'skill_dev', result)
            source_asset = self.original_seal['prediction_seal_sha256']
        return {'native': result['native'], 'original_prediction_file': str(path.relative_to(ROOT)),
                'original_prediction_sha256': digest(record), 'original_prediction_seal_sha256': source_asset,
                'common_fee_route': case is not None, 'fallback_executed': False}

    def __call__(self, source, library, purpose):
        verify(library, 'snapshot_sha256')
        if (purpose != 'skill_dev' or library['batch'] != 0 or library['study_binding'] != self.binding
                or library['interface_library'] is not None or library['method_specific_pilot_state_loaded']
                or library['programs'] != dict.fromkeys(ConvergenceEvaluation.datasets, self.original_library['program'])):
            raise ValueError('Shared B0 replay requires the exact pre-pilot program and unadapted library')
        return self._prediction(source['key'], digest(source), json.dumps(source, ensure_ascii=False))

    def verify_saved(self, source, library, purpose, result):
        if result != self(source, library, purpose):
            raise ValueError('The re-bound B0 prediction differs from its original verified physical read')


def materialize():
    baseline = ROOT / read(B0)['artifact_root']
    fee_root = ROOT / read(HANDOFF / 'airline_shared_fee_dev_current.json')['artifact_root']
    prior = read(baseline / 'binding.json')
    dev = read(baseline / 'public_DEV_sources.json')
    test_identities = read(baseline / 'sealed_TEST_identity_metadata_only.json')
    fee_terminal = read(fee_root / 'terminal.json')
    if read(baseline / 'terminal.json')['status'] != 'completed' or fee_terminal['status'] != 'completed':
        raise ValueError('The original B0 and public fee observations must both be terminal')
    fee_binding = read(fee_root / 'binding.json')
    if (prior['executor'] != fee_binding['executor'] or prior['program'] !=
            read(baseline / 'common_initial_library.json')['program']):
        raise ValueError('The frozen executor and original library must match the common baseline')
    binding = {**prior, 'study_id': 'convergence_reusable_shared_DEV_B0_checkpoint',
               'formal_five_arm_binding_pending_external_selection': True,
               'source_baseline_sha256': digest(prior),
               'B0_terminal_sha256': sha(baseline / 'terminal.json'),
               'common_fee_terminal_sha256': sha(fee_root / 'terminal.json'),
               'common_fee_binding_sha256': digest(fee_binding),
               'replay_driver_sha256': sha(ROOT / 'experiments/convergence_shared_dev_checkpoint.py')}
    out = BASE / 'shared_DEV_B0_checkpoint' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    by_source = {row['key']: row['dataset'] for row in dev}

    @lru_cache(maxsize=None)
    def load_grades(path):
        if sha(ROOT / path) != binding['grading_file_sha256'][path]:
            raise ValueError('The original DEV grading file changed')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != set(by_source):
            raise ValueError('Wait for complete DEV prediction sealing before opening grading')
        path = binding['grading_paths'][by_source[key]]
        return load_grades(path)[key]

    def sealed_test():
        raise ValueError('The shared B0 replay cannot open TEST')

    evaluation = ConvergenceEvaluation(out, dev, test_identities, binding=binding, grade_provider=grade,
                                       load_test=sealed_test)
    actor = SharedDevReplay(baseline, fee_root, binding)
    summaries = {}
    for arm, library in initial_libraries(prior['program'], binding).items():
        immutable_json(out / 'libraries' / (arm + '.json'), library)
        report = evaluation.evaluate('dev', arm, 0, dict.fromkeys(ConvergenceEvaluation.datasets, library), actor)
        summaries[arm] = {key: report[key] for key in ('cell_sha256', 'source_scores')}
    first = summaries[ARM]['source_scores']
    if any(summary['source_scores'] != first for summary in summaries.values()):
        raise ValueError('The five unadapted arms must reproduce exactly the same native outputs')
    original_report = read(ROOT / fee_binding['B0_score_artifact'])
    verify(original_report, 'cell_sha256')
    unchanged = [row for row in first if row['source'] not in actor.fee_sources]
    if (sha(ROOT / fee_binding['B0_score_artifact']) != fee_binding['B0_score_sha256'] or unchanged != [
            row for row in original_report['source_scores'] if row['source'] not in actor.fee_sources]):
        raise ValueError('Every B0 score outside the public fee scope must reproduce exactly')
    airline = [row['grade'] for row in first if row['dataset'] == 'RuleArena_Airline']
    if sum(airline) != fee_terminal['native_exact_counts_before_after'][1]:
        raise ValueError('The common Airline metric must replay its independently sealed DEV result')
    receipt = {'artifact_root': str(out.relative_to(ROOT)), 'arms': {
        arm: value['cell_sha256'] for arm, value in summaries.items()}, 'native_tasks_per_arm': len(first),
        'DEV_mothers': len(dev), 'common_fee_DEV_mothers': len(actor.fee_sources),
        'Airline_native_exact': [sum(airline), len(airline)], 'new_generation_requests': 0,
        'TEST_loaded': False, 'shared_checkpoint_only': True}
    immutable_json(out / 'terminal.json', receipt)
    immutable_json(HANDOFF / 'common_DEV_B0_five_arm_replay_20261118.json', receipt)
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    materialize()
