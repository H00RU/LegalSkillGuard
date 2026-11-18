"""Fit the M1 interface pool from the journaled first-batch TRAIN sources."""

import argparse
import json
import sqlite3

from experiments.convergence_diversity_grouped_probe import POINTER as GROUPED
from experiments.convergence_diversity_grouped_reuse import POINTER as REUSE
from experiments.convergence_formal_b1_observe import POINTER as OBSERVED, load_roster
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_m1_batch import fit_interface_batch
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_b1_m1_current.json'
ARMS = ('method_one_only', 'both')


def prepare():
    observed = ROOT / read(OBSERVED)['artifact_root']
    native, terminal = read(observed / 'binding.json'), read(observed / 'terminal.json')
    bootstrap = ROOT / native['bootstrap_root']
    study = read(bootstrap / 'binding.json')
    if (terminal['status'] != 'completed_B1_observations' or digest(study) != native['study_binding_sha256']
            or observed.name != digest(native) or terminal['TEST_opened']):
        raise ValueError('Interface calibration needs the verified actual first-batch observation path')
    batches = load_roster(study)
    journal = TrainingJournal(bootstrap, study, batches)
    for arm in ARMS:
        if terminal['observation_receipts'][arm] != journal._observations(arm, 1)['train_observation_sha256']:
            raise ValueError('The same initial primary observations are required in both M1 arms')
    provider = diversity_claim_groups.Provider()
    eligible = [source for source in batches[0] if source['dataset'] == 'LegalBench_Diversity']
    candidates = []
    for source in eligible:
        view, = provider.views(source)
        reference = diversity_claim_groups.unit_reviews(source, view)
        for plan in view['plans']:
            provider.verify_plan(source, view, plan)
            if set(reference) != set(plan['relational_program']['units']):
                raise ValueError('The same local semantic units must be audited for every candidate')
        candidates.append({'source': source['key'], 'source_sha256': digest(source),
                           'ordered_plan_versions': [plan['version'] for plan in view['plans']]})
    if len(candidates) != 3:
        raise ValueError('The complete fixed B1 Diversity cohort is required')
    prior = {}
    for pointer in (GROUPED, REUSE):
        stage = ROOT / read(pointer)['artifact_root']
        if read(stage / 'binding.json')['executor'] != study['executor'] or read(stage / 'terminal.json')['status'] != 'completed':
            raise ValueError('Reuse only settled readings under the same executor and complete actual wire')
        prior[str(stage.relative_to(ROOT))] = sha(stage / 'terminal.json')
    files = set(native['source_sha256']) | {'experiments/convergence_formal_b1_m1.py',
        'legal_skill_guard/paired_interfaces/convergence_m1_batch.py',
        'legal_skill_guard/paired_interfaces/diversity_claim_groups.py',
        'legal_skill_guard/paired_interfaces/diversity_source_binding.py',
        'legal_skill_guard/paired_interfaces/diversity_relational.py',
        'legal_skill_guard/paired_interfaces/formal_training.py',
        'legal_skill_guard/paired_interfaces/relational_program.py',
        'legal_skill_guard/paired_interfaces/production_decode.py',
        'legal_skill_guard/paired_interfaces/residual.py'}
    binding = {'study': 'convergence_real_B1_interface_fit', 'bootstrap_root': native['bootstrap_root'],
               'study_binding_sha256': digest(study), 'observation_terminal_sha256': sha(observed / 'terminal.json'),
               'observation_root': str(observed.relative_to(ROOT)), 'executor': study['executor'],
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}, 'replay_roots': prior,
               'certified_roster': candidates, 'available_providers': ['LegalBench_Diversity'],
               'unsupported_sources_stay_in_native_denominator': True}
    out = BASE / 'formal_b1_m1' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'methods': list(ARMS), 'calibration_mothers': len(candidates),
                           'logical_paired_reads': sum(len(row['ordered_plan_versions']) for row in candidates)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding = read(out / 'binding.json')
    checkpoint, observed = ROOT / binding['bootstrap_root'], ROOT / binding['observation_root']
    study = read(checkpoint / 'binding.json')
    if (out.name != digest(binding) or digest(study) != binding['study_binding_sha256']
            or sha(observed / 'terminal.json') != binding['observation_terminal_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())
            or any(sha(ROOT / path / 'terminal.json') != expected for path, expected in binding['replay_roots'].items())):
        raise ValueError('The authorized native primary evidence, source plan or replay identity changed')
    batches = load_roster(study)
    provider = diversity_claim_groups.Provider()
    keys = []
    for source, saved in zip((s for s in batches[0] if s['dataset'] == 'LegalBench_Diversity'),
                             binding['certified_roster'], strict=True):
        view, = provider.views(source)
        if ([plan['version'] for plan in view['plans']] != saved['ordered_plan_versions']
                or digest(source) != saved['source_sha256'] or source['key'] != saved['source']):
            raise ValueError('Every actual paired read must use the exact certified source context')
        keys.append(source['key'])
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the current training request first')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-M1-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / path for path in binding['replay_roots']]
    reader.readiness()
    actor = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=binding['source_sha256'])
    native = read(observed / 'binding.json')
    grade_path = native['native_grade_paths']['LegalBench_Diversity']
    loaded = {}

    def grade(key):
        if not loaded:
            if sha(ROOT / grade_path) != native['native_grade_sha256'][grade_path]:
                raise ValueError('Keep the independent original TRAIN grader')
            loaded.update(read(ROOT / grade_path))
        return loaded[key]

    journal = TrainingJournal(checkpoint, study, batches)
    paths = {}
    for arm in ARMS:
        write_status(out, {'status': 'running', 'arm': arm}, POINTER)
        snapshot, receipt = fit_interface_batch(journal, arm, 1, actor=actor,
                                                 reviewers={'LegalBench_Diversity': diversity_claim_groups.unit_reviews},
                                                 grade_provider=grade)
        paths[arm] = {'interface_library_sha256': snapshot['snapshot_sha256'], 'interface_fit_sha256': digest(receipt),
                      'actual_calibration_reads': len(snapshot['observations'])}
    if len({value['interface_library_sha256'] for value in paths.values()}) != 1:
        raise ValueError('Identical entering channel conditions must share exactly the same measured B1 interface state')
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (ledger.run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in physical):
        raise ValueError('The shared interface calibration has unsettled physical observations')
    terminal = {'status': 'completed_B1_interface_fit', 'arms': paths, 'calibration_mothers': len(keys),
                'new_executor_calls': len(physical), 'new_executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                        for _, raw in physical), 'full_arm_library_updates_committed': 0, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, terminal, POINTER)
    print(json.dumps(terminal, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
