"""Record sealed entering-library predictions on the next original TRAIN batch."""

import argparse
import json
import math
import sqlite3
from functools import lru_cache

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_formal_b1_m1 import POINTER as FIRST_INTERFACE
from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVATIONS, load_roster
from experiments.convergence_formal_b1_primary import POINTER as FIRST_UPDATE
from experiments.convergence_parse_runtime import ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import EVInventoryActor, INVENTORY_FILES
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def pointer(batch):
    return HANDOFF / f'formal_B{batch}_observe_current.json'


def prepare(batch):
    first, interface, first_update = (ROOT / read(p)['artifact_root'] for p in
                                      (FIRST_OBSERVATIONS, FIRST_INTERFACE, FIRST_UPDATE))
    observation, update = read(first / 'binding.json'), read(first_update / 'binding.json')
    checkpoint = ROOT / observation['bootstrap_root']
    study = read(checkpoint / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    if checkpoint.name != digest(study) or update['study_binding_sha256'] != digest(study):
        raise ValueError('Use the same roster and study that produced the verified first update')
    preceding = {arm: journal._completed_batch(arm, batch - 1) for arm in ConvergenceEvaluation.arms}
    if batch == 2 and {arm: value['completed_batch_sha256'] for arm, value in preceding.items()} != (
            read(first_update / 'terminal.json')['arm_receipts']):
        raise ValueError('B2 must enter with all five actual B1 updates')
    prior_stages = [first, interface]
    if batch > 2:
        prior_stages.extend(ROOT / read(pointer(index))['artifact_root'] for index in range(2, batch))
    profiles = dict(observation['prior_train_replay_roots'])
    for stage in prior_stages:
        terminal = read(stage / 'terminal.json')
        if terminal['TEST_opened'] or read(stage / 'binding.json')['executor'] != study['executor']:
            raise ValueError('A reused TRAIN response must have a settled same-model provenance')
        profiles[str(stage.relative_to(ROOT))] = sha(stage / 'terminal.json')
    files = (set(update['source_sha256']) | set(read(interface / 'binding.json')['source_sha256'])
             | {str(__file__.removeprefix(str(ROOT) + '/')), 'experiments/convergence_parse_runtime.py'})
    if batch >= 7:
        files.update(INVENTORY_FILES)
    cohort = batches[batch - 1]
    spec = {'study': 'convergence_ordered_entering_TRAIN_observations', 'batch': batch,
            'checkpoint_root': str(checkpoint.relative_to(ROOT)), 'study_binding_sha256': digest(study),
            'entering_history': preceding, 'ordered_sources_sha256': digest(cohort),
            **({'ev_asset_inventory_wire': True} if batch >= 7 else {}),
            **({'oe_public_jurisdiction_scope': True} if batch == 8 else {}),
            'prior_train_replay_roots': profiles, 'executor': study['executor'],
            'native_grade_paths': observation['native_grade_paths'],
            'native_grade_sha256': observation['native_grade_sha256'],
            'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}}
    out = BASE / 'formal_train_observe' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'batch': batch, 'mothers': len(cohort),
                           'native_tasks': sum(len(source['views']) for source in cohort)}, pointer(batch))
    print(json.dumps(read(pointer(batch)), sort_keys=True), flush=True)


def run(batch):
    out = ROOT / read(pointer(batch))['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json'), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if (binding['batch'] != batch or out.name != digest(binding) or digest(study) != binding['study_binding_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())
            or any(sha(ROOT / root / 'terminal.json') != expected
                   for root, expected in binding['prior_train_replay_roots'].items())):
        raise ValueError('The ordered observation runtime, profile or replay evidence changed')
    batches = load_roster(study)
    cohort = batches[batch - 1]
    journal = TrainingJournal(checkpoint, study, batches)
    if (digest(cohort) != binding['ordered_sources_sha256'] or any(
            journal._completed_batch(arm, batch - 1) != record for arm, record in binding['entering_history'].items())):
        raise ValueError('The entering libraries and original cohort must match the prepared run')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the existing physical request first')
    keys = [source['key'] for source in cohort]
    run_id = f'convergence-formal-B{batch}-observe-{out.name[:16]}'
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [ROOT / root for root in binding['prior_train_replay_roots']]
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    interface = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                               pipeline_binding=binding['source_sha256'])
    visible = [source['key'] for group in batches[:batch - 1] for source in group]
    primary = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=interface,
                               providers={'LegalBench_Diversity': provider}, train_sources=visible, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(primary, reader, out), reader, out)
    if binding.get('ev_asset_inventory_wire'):
        actor = EVInventoryActor(actor, jurisdiction_scope=binding.get('oe_public_jurisdiction_scope', False))
    receipts = {}
    for arm in ConvergenceEvaluation.arms:
        write_status(out, {'status': 'running', 'batch': batch, 'arm': arm}, pointer(batch))
        receipts[arm] = journal.observe(arm, batch, actor)['train_observation_sha256']

    @lru_cache(maxsize=None)
    def grades(dataset):
        path = binding['native_grade_paths'][dataset]
        if sha(ROOT / path) != binding['native_grade_sha256'][path]:
            raise ValueError('TRAIN feedback requires the originally bound grader')
        return read(ROOT / path)

    score_hashes = {}
    for arm in receipts:
        scores = []
        observed = journal._observations(arm, batch)
        directory = journal.directory(arm, batch) / 'predictions'
        for source in cohort:
            key, dataset = source['key'], source['dataset']
            row = read(directory / (digest(key) + '.json'))
            if digest(row) != observed['predictions'][key]:
                raise ValueError('Native feedback needs the physically verified entering prediction')
            native, gold = row['result']['native'], grades(dataset)[key]
            values = {}
            for task in source['views']:
                identity = task['id']
                output = native[identity]
                values[identity] = (grade_view(dataset, task, gold[identity], output['answer'],
                    output.get('evidence_sentence_ids', []))['grade'] if output['handled'] else 0.0)
            scores.append({'source': key, 'dataset': dataset, 'view_scores': values,
                           'native_utility': math.fsum(values.values()) / len(values)})
        immutable_json(out / 'native_scores' / (arm + '.json'), scores)
        score_hashes[arm] = digest(scores)
    with ledger.transaction() as db:
        reads = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in reads):
        raise ValueError('Every new observation must be settled in the continuous ledger')
    terminal = {'status': 'completed_TRAIN_observations', 'batch': batch, 'observation_receipts': receipts,
                'native_scores_sha256': score_hashes, 'mothers': len(cohort),
                'native_tasks': sum(len(source['views']) for source in cohort), 'executor_calls': len(reads),
                'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in reads),
                'TEST_opened': False}
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, terminal, pointer(batch))
    print(json.dumps(terminal, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('--batch', type=int, required=True, choices=range(2, 9))
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)(args.batch)
