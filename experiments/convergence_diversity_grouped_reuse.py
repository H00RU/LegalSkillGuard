"""Exercise the learned grouped interface on different, preselected TRAIN mothers."""

import argparse
import json
import sqlite3

from experiments.convergence_diversity_grouped_probe import POINTER as GROUPED
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_shared_dev_checkpoint import ReadOnlyLedger
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor, initial_libraries
from legal_skill_guard.paired_interfaces.convergence_training import calibrate_source
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'diversity_grouped_reuse_current.json'
ARM = 'method_one_only'


def prepare():
    original = ROOT / read(GROUPED)['artifact_root']
    prior, report, initial = (read(original / f'{name}.json') for name in ('binding', 'terminal', 'sources'))
    if (original.name != digest(prior) or report['status'] != 'completed' or len(report['paired_scores']) != 8
            or digest(initial) != prior['original_sources_sha256']):
        raise ValueError('The two original supervised mothers must have complete measured layout pools')
    roster_info = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_info['artifact_root'] / 'binding.json')
    if digest(roster) != roster_info['roster_sha256']:
        raise ValueError('The fixed TRAIN roster changed')
    sources = {row['key']: row for row in read(ROOT / roster['normalized_root'] / 'train/public.json')}
    excluded = {row['source'] for row in roster['fixed_pilot']}
    selected = [source['key'] for source in initial]
    allowed = {key for key, source in sources.items() if source['dataset'] == 'LegalBench_Diversity'}
    provider = diversity_claim_groups.Provider()
    reader = FrozenExecutor(ReadOnlyLedger(), original, prior['executor'])
    actor = InterfaceActor(reader, original, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=prior['source_sha256'])
    observations = {row['physical_call_id']: row for path in (original / 'interface_learning_observations').glob('*.json')
                    if (row := read(path))['source'] in selected}
    physical = {row['physical_call_id']: row for path in (original / 'interface_reads').glob('*/decoded.json')
                if (row := read(path))['source'] in selected}
    if set(observations) != set(physical) or set(physical) != {r['physical_call_id'] for r in report['paired_scores']}:
        raise ValueError('Every measured candidate needs its physical and source-fidelity evidence')
    files = set(prior['source_sha256']) | {'experiments/convergence_diversity_grouped_reuse.py',
        'experiments/convergence_shared_dev_checkpoint.py', 'legal_skill_guard/paired_interfaces/convergence_actors.py',
        'legal_skill_guard/paired_interfaces/formal_evaluation.py'}
    binding = {'study': 'Diversity_grouped_actual_learning_and_different_mother_reuse',
               'terminal_sha256': sha(original / 'terminal.json'), 'calibration_observations_sha256': digest(observations),
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}, 'executor': prior['executor'],
               'grading_path': prior['grading_path'], 'grading_sha256': prior['grading_sha256'],
               'common_library_sha256': prior['common_library_sha256'], 'roster_sha256': digest(roster),
               'target_rule': 'first compatible, non-pilot TRAIN mother in each observed native variant, in locked batch order'}
    out = BASE / 'diversity_grouped_reuse' / digest(binding)
    learner = RelationalInterfaceLibrary(out, actor=actor, train_sources=allowed,
                                         initial_common_library_sha256=prior['common_library_sha256'])
    for source in initial:
        view, = actor.views(source)
        for plan in view['plans']:
            reading, = (row for row in physical.values() if row['source'] == source['key']
                        and row['raw_read_version'] == plan['version'])
            row = observations[reading['physical_call_id']]
            restored = learner.observe(source, view, plan, reading, native_utility=row['native_utility'],
                                       source_fidelity=row['source_fidelity'], visible_prefix=selected)
            if digest(restored) != digest(row):
                raise ValueError('The restored calibration observation differs from the paid observation')
    snapshot = learner.snapshot(batch=1, visible_prefix=selected)
    learner = RelationalInterfaceLibrary.restore(out, actor=actor, train_sources=allowed, snapshot=snapshot)
    remaining = {source['native_config'] for source in initial}
    targets, choices = [], []
    for row in (row for batch in roster['fixed_training_batches'] for row in batch):
        key = row['source']
        if key not in allowed or key in excluded or sources[key]['native_config'] not in remaining:
            continue
        source = sources[key]
        view, = actor.views(source)
        choice, receipt = learner.choose(source, view)
        if choice['is_correct_fixed_raw_control'] or receipt['paired_learning_sources'] != sorted(selected):
            continue
        targets.append(source)
        choices.append({'source': key, 'source_sha256': digest(source), 'plan_version': choice['version'], **receipt})
        remaining.remove(source['native_config'])
    if remaining or len(targets) != 2:
        raise ValueError('The fixed target rule must find an untouched compatible mother for each native variant')
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'targets.json', {'sources': targets, 'before_read_choices': choices,
                                           'interface_library_sha256': snapshot['snapshot_sha256']})
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'target_mothers': len(targets), 'reader_cells': 4,
                           'preselected_profile': choices[0]['selected_profile']}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding, targets = read(out / 'binding.json'), read(out / 'targets.json')
    if out.name != digest(binding) or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items()):
        raise ValueError('The saved calibration pipeline or production actor changed')
    snapshot = read(out / 'interface_libraries' / (targets['interface_library_sha256'] + '.json'))
    keys = [source['key'] for source in targets['sources']]
    trained = snapshot['visible_prefix']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the current physical request before continuing')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-Diversity-grouped-reuse-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    provider = diversity_claim_groups.Provider()
    reader = InterfaceActor(executor, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                            pipeline_binding=binding['source_sha256'])
    learner = RelationalInterfaceLibrary.restore(out, actor=reader, train_sources=trained + keys, snapshot=snapshot)
    evaluator = RelationalInterfaceLibrary(out, actor=reader, train_sources=trained + keys,
                                           initial_common_library_sha256=binding['common_library_sha256'])
    runtime = ConvergenceActor(out, program_actor=None, interface_actor=reader, providers={'LegalBench_Diversity': provider},
                               train_sources=trained, study_binding=binding)
    common = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    library = initial_libraries(read(common / 'binding.json')['program'], binding)[ARM]
    library = sealed({**{k: v for k, v in library.items() if k != 'snapshot_sha256'}, 'batch': 1,
                      'interface_library': snapshot}, 'snapshot_sha256')

    def grade(key):
        if sha(ROOT / binding['grading_path']) != binding['grading_sha256']:
            raise ValueError('The original TRAIN native labels changed')
        return read(ROOT / binding['grading_path'])[key]

    rows = []
    write_status(out, {'status': 'running', 'target_mothers': len(keys), 'reader_cells': 4}, POINTER)
    try:
        for source, decision in zip(targets['sources'], targets['before_read_choices'], strict=True):
            view, = reader.views(source)
            choice, receipt = learner.choose(source, view)
            if (source['project_split'] != 'train' or source['key'] in trained or
                    decision != {'source': source['key'], 'source_sha256': digest(source),
                                 'plan_version': choice['version'], **receipt}):
                raise ValueError('The printed preselection must be recoverable without the new source read or labels')
            result = runtime(source, library, 'skill_actor')
            runtime.verify_saved(source, library, 'skill_actor', result)
            if result['selection']['route'] != 'synthesized_interface' or result['reads'][0]['raw_read_version'] != choice['version']:
                raise ValueError('The ordinary production route must execute the learned interface')
            fixed, = (plan for plan in view['plans'] if plan['is_correct_fixed_raw_control'])
            pair = {**view, 'plans': [fixed, choice]}
            compared = calibrate_source(evaluator, source, pair, unit_reviews=diversity_claim_groups.unit_reviews(source, pair),
                                        grade_provider=grade, visible_prefix=trained + keys)
            rows.append({'variant': source['native_config'], 'native_utility': [r['native_utility'] for r in compared],
                         'grounded': [r['source_fidelity']['all_local_relations_source_faithful'] for r in compared],
                         'executor_tokens': sum(row['usage']['total_tokens'] for row in compared),
                         'choice_sha256': digest(decision), 'physical_call_ids': [row['physical_call_id'] for row in compared]})
        result = {'status': 'completed', 'paired_fixed_then_learned': rows, 'new_mothers': len(keys), 'TEST_opened': False}
        immutable_json(out / 'terminal.json', result)
        write_status(out, result, POINTER)
        print(json.dumps(result), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
