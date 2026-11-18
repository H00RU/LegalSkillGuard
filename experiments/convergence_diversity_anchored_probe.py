"""Evaluate a public source-binding repair on the two previously measured Diversity mothers."""

import argparse
import json
import sqlite3

from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_replay_diversity_references import reference_reading
from legal_skill_guard.paired_interfaces import diversity_source_binding
from legal_skill_guard.paired_interfaces.convergence_m1_batch import diversity_unit_reviews
from legal_skill_guard.paired_interfaces.convergence_training import calibrate_source
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'diversity_anchored_train_current.json'


def prepare():
    prior = ROOT / read(HANDOFF / 'diversity_reader_probe_current.json')['artifact_root']
    diagnostic, terminal = read(prior / 'binding.json'), read(prior / 'terminal.json')
    if (diagnostic['name'] != 'convergence_Diversity_relation_polarity_diagnosis'
            or terminal['status'] != 'completed' or [row['native_correct'] for row in terminal['completed']] != [True, False]):
        raise ValueError('The revision requires the settled reader polarity failure on the fixed TRAIN source')
    library = ROOT / read(HANDOFF / 'actual_interface_library_current.json')['artifact_root']
    previous = read(library / 'binding.json')
    positive = ROOT / previous['calibration_root']
    original = read(positive / 'binding.json')
    if digest(original) != previous['calibration_binding_sha256']:
        raise ValueError('The original measured calibration mother changed')
    roster_pointer = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_pointer['artifact_root'] / 'binding.json')
    if digest(roster) != roster_pointer['roster_sha256']:
        raise ValueError('The fixed TRAIN roster changed')
    pilot_ids = {row['source']: row['public_sha256'] for row in roster['fixed_pilot']}
    sources = [read(root / 'public_TRAIN_source.json') for root in (positive, prior)]
    observed = []
    provider = diversity_source_binding.Provider()
    for source in sources:
        if (source['dataset'] != 'LegalBench_Diversity' or source['project_split'] != 'train'
                or pilot_ids.get(source['key']) != digest(source)):
            raise ValueError('Re-use both already measured original pilot mothers exactly')
        view, = provider.views(source)
        plans = [view['plans'][0], view['plans'][-1]]
        for plan in plans:
            provider.verify_plan(source, view, plan)
            raw, _ = reference_reading(source, plan)
            for request in view['read_input']['unit_requests']:
                raw[request['source_anchor']]['evidence'] = [{'field': 'source_text', 'quote': quote}
                                                           for quote in request['source_excerpts']]
            predicted = decode_response(source, view, plan, {'content': json.dumps(raw), 'finish_reason': 'stop'})
            if predicted['production_errors'] or not predicted['native']['native']['handled']:
                raise ValueError('The anchor change must pass the original production decoder')
            observed.append({'plan': plan['version'], 'reference_native': predicted['native']['native']['answer'],
                             'reference_diagnostics': predicted['decoder_receipt']['diagnostics']})
    files = set(diagnostic['source_sha256']) | {'experiments/convergence_diversity_anchored_probe.py',
        'legal_skill_guard/paired_interfaces/diversity_source_binding.py',
        'legal_skill_guard/paired_interfaces/convergence_m1_batch.py',
        'legal_skill_guard/paired_interfaces/convergence_training.py',
        'legal_skill_guard/paired_interfaces/formal_training.py'}
    grading = read(HANDOFF / 'diversity_train_current.json')['artifact_root'] + '/grading.json'
    binding = {'study': 'Diversity_pair_bound_source_excerpts_fixed_mothers', 'executor': diagnostic['executor'],
        'reason': 'The synthesized reader cited same-state text but reversed one local citizenship comparison.',
        'expected_change': 'Separate pair-specific literal statements improve source faithfulness and native accuracy.',
        'prior_terminal_sha256': {str(root.relative_to(ROOT)): sha(root / 'terminal.json') for root in (positive, prior)},
        'original_sources_sha256': digest(sources), 'reference_decodes_sha256': digest(observed),
        'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
        'grading_path': grading, 'grading_sha256': sha(ROOT / grading),
        'common_library_sha256': diagnostic['common_external_library_sha256'],
        'all_layouts_receive_same_public_excerpts': True}
    out = BASE / 'diversity_anchored_train' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'sources.json', sources)
    immutable_json(out / 'reference_decodes.json', observed)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'matched_mothers': 2, 'reader_cells': 4}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding, sources = read(out / 'binding.json'), read(out / 'sources.json')
    if (out.name != digest(binding) or digest(sources) != binding['original_sources_sha256']
            or any(sha(ROOT / name) != value for name, value in binding['source_sha256'].items())
            or digest(read(out / 'reference_decodes.json')) != binding['reference_decodes_sha256']):
        raise ValueError('The prepared source, production references or reader code changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as database:
        if database.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the current physical request before continuing')
    source_ids = [source['key'] for source in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-Diversity-anchored-' + out.name[:16],
                             sources={'train': source_ids, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    provider = diversity_source_binding.Provider()
    actor = InterfaceActor(executor, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=binding['source_sha256'])
    learner = RelationalInterfaceLibrary(out, actor=actor, train_sources=source_ids,
                                        initial_common_library_sha256=binding['common_library_sha256'])

    def grade(key):
        path = ROOT / binding['grading_path']
        if sha(path) != binding['grading_sha256']:
            raise ValueError('The native TRAIN grades changed')
        return read(path)[key]

    rows = []
    write_status(out, {'status': 'running', 'matched_mothers': 2, 'reader_cells': 4}, POINTER)
    try:
        for source in sources:
            view, = actor.views(source)
            view = {**view, 'plans': [view['plans'][0], view['plans'][-1]]}
            rows.extend(calibrate_source(learner, source, view, unit_reviews=diversity_unit_reviews(source, view),
                                         grade_provider=grade, visible_prefix=source_ids))
        result = {'status': 'completed', 'matched_mothers': 2,
                  'paired_scores': [{'profile': row['profile'], 'native': row['native_utility'],
                    'all_local_relations_source_faithful': row['source_fidelity']['all_local_relations_source_faithful'],
                    'physical_call_id': row['physical_call_id']} for row in rows],
                  'executor_tokens': sum(row['usage']['total_tokens'] for row in rows), 'TEST_opened': False}
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
