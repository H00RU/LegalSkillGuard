"""Bind the locked external family, native roster and verified five-arm B0."""

from collections import Counter
from functools import lru_cache
import json
import sqlite3

from experiments.convergence_compact_teacher_pilot import pointer as compact_pointer
from experiments.convergence_dev_b0 import POINTER as DEV
from experiments.convergence_lock_external_pilot import LOCK
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_shared_dev_checkpoint import SharedDevReplay
from legal_skill_guard.paired_interfaces.convergence_actors import initial_libraries
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_training import training_batches
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_bootstrap_current.json'


def prepare():
    protocol_path = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'
    protocol, lock = read(protocol_path), read(LOCK)
    rank = lock['ranking']
    ranked = rank['ranked_candidates']
    if (lock['protocol_sha256'] != sha(protocol_path) or lock['TEST_opened']
            or not rank['includes_all_twenty_TRAIN_sources'] or rank['selected_family'] != ranked[0]['family']
            or {row['family'] for row in ranked} != set(protocol['study_scope']['external_eligible_families'])):
        raise ValueError('Bind the one complete external ranking on the prespecified fixed TRAIN pilot')
    roster_info = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_info['artifact_root'] / 'binding.json')
    if digest(roster) != roster_info['roster_sha256']:
        raise ValueError('The ordered source roster changed')
    train = read(ROOT / roster['normalized_root'] / 'train/public.json')
    batches = training_batches(roster, train, protocol['data']['train_quota'])
    baseline = ROOT / read(DEV)['artifact_root']
    prior = read(baseline / 'binding.json')
    dev = read(baseline / 'public_DEV_sources.json')
    test = read(baseline / 'sealed_TEST_identity_metadata_only.json')
    reuse = read(HANDOFF / 'common_DEV_B0_five_arm_replay_20261118.json')
    if (digest(dev) != prior['DEV_public_sha256'] or digest(test) != prior['TEST_identities_sha256']
            or test != roster['sealed_TEST_identities'] or prior['executor']['enable_thinking'] is not False
            or set(reuse['arms']) != set(ConvergenceEvaluation.arms) or reuse['TEST_loaded']):
        raise ValueError('Use the unchanged common DEV paid reads, locked TEST identities and executor')
    all_keys = [source['key'] for source in train + dev] + [row['source'] for row in test]
    if len(all_keys) != 368 or len(all_keys) != len(set(all_keys)):
        raise ValueError('TRAIN, DEV and TEST mothers must remain disjoint')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger_sources = {row[0] for row in db.execute('select distinct source from calls')}
    if {row['source'] for row in test} & ledger_sources:
        raise ValueError('A sealed TEST identity has appeared in the continuous ledger')
    files = set(prior['source_sha256']) | {'experiments/convergence_formal_bootstrap.py',
        'experiments/convergence_shared_dev_checkpoint.py', 'experiments/convergence_lock_external_pilot.py',
        'legal_skill_guard/paired_interfaces/convergence_journal.py',
        'legal_skill_guard/paired_interfaces/convergence_actors.py',
        'legal_skill_guard/paired_interfaces/convergence_training.py'}
    fees = ROOT / read(HANDOFF / 'airline_shared_fee_dev_current.json')['artifact_root']
    teacher = read(ROOT / read(compact_pointer('ordinary'))['artifact_root'] / 'binding.json')
    if (teacher['executor'] != prior['executor'] or any(teacher['teacher_profile'][key] != teacher['teacher_config'][key]
                                                        for key in ('model', 'reasoning_effort'))):
        raise ValueError('The training bootstrap must retain the matched executor and teacher profiles')
    binding = {**prior, 'study_id': 'convergence_locked_external_five_arm_B0',
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
               'protocol_sha256': sha(protocol_path), 'external_family': rank['selected_family'],
               'external_pilot_lock_sha256': digest(lock), 'TRAIN_ordered_batches_sha256': digest(batches),
               'shared_DEV_replay_sha256': digest(reuse), 'common_fee_terminal_sha256': sha(fees / 'terminal.json'),
               'teacher_profile': teacher['teacher_profile'], 'teacher_config': teacher['teacher_config'],
               'pilot_library_versions_preloaded': False}
    out = BASE / 'formal_bootstrap' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    journal = TrainingJournal(out, binding, batches)
    libraries = initial_libraries(prior['program'], binding)
    journal.initialize(libraries)
    by_source = {source['key']: source['dataset'] for source in dev}

    @lru_cache(maxsize=None)
    def grades(path):
        if sha(ROOT / path) != binding['grading_file_sha256'][path]:
            raise ValueError('The original DEV grade file changed')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != set(by_source):
            raise ValueError('The complete B0 DEV predictions must be sealed before local grading')
        return grades(binding['grading_paths'][by_source[key]])[key]

    def unopened_test():
        raise ValueError('This entrypoint materializes B0 without a B8 prediction freeze')

    actor = SharedDevReplay(baseline, fees, binding)
    evaluator = ConvergenceEvaluation(out, dev, test, binding=binding, grade_provider=grade, load_test=unopened_test)
    dev_records = {}
    for arm, library in libraries.items():
        cells = dict.fromkeys(ConvergenceEvaluation.datasets, library)
        completed = evaluator.evaluate('dev', arm, 0, cells, actor)
        reference = read(ROOT / reuse['artifact_root'] / 'dev/B0' / arm / 'scores.json')
        verify(reference, 'cell_sha256')
        if reference['cell_sha256'] != reuse['arms'][arm] or completed['source_scores'] != reference['source_scores']:
            raise ValueError('Locked external selection must not alter the common paid DEV predictions')
        dev_records[arm] = completed['cell_sha256']
    try:
        journal.seal_B8()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('B0 must not produce a B8 training seal without measured updates')
    receipt = {'status': 'completed_B0_bootstrap', 'external_family': rank['selected_family'], 'TRAIN_batches': len(batches),
               'TRAIN_mothers': len(train), 'TRAIN_native_tasks': sum(len(source['views']) for source in train),
               'next_batch_datasets': dict(Counter(source['dataset'] for source in batches[0])), 'DEV_mothers': len(dev),
               'B0_cells': dev_records, 'TEST_identity_count': len(test), 'TEST_content_opened': False,
               'generation_requests': 0, 'training_batches_executed': 0}
    immutable_json(out / 'terminal.json', receipt)
    write_status(out, receipt, POINTER)
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    prepare()
