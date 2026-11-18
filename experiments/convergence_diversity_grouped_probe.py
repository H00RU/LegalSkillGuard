"""Certify and measure source-grounded shared claim observations on fixed TRAIN."""

import argparse
from itertools import product
import json
import sqlite3

from experiments.convergence_diversity_anchored_probe import POINTER as ANCHORED
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_replay_diversity_references import reference_reading
from legal_skill_guard.paired_interfaces import diversity_claim_groups, diversity_source_binding, relational_program
from legal_skill_guard.paired_interfaces.convergence_training import calibrate_source
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'diversity_grouped_train_current.json'


def verify_grouped_outputs(source, original, grouped):
    before, after = original['plans'][0]['relational_program'], grouped['plans'][0]['relational_program']
    groups = after['composition_certificate']['shared_clause_bindings']
    aliases = {unit: name for name, group in groups.items() for unit in group['original_units']}
    names = list(after['units'])
    checked = 0
    for values in product((None, False, True), repeat=len(names)):
        updated = {name: {'enough' if name in groups else 'different': value} for name, value in zip(names, values)}
        initial = {name: updated[aliases.get(name, name)] for name in before['units']}
        for key in ('outputs', 'diagnostics'):
            if {name: relational_program.evaluate(expr, initial) for name, expr in before[key].items()} != {
                    name: relational_program.evaluate(expr, updated) for name, expr in after[key].items()}:
                raise ValueError('Clause sharing changed the original three-valued consumer')
        checked += 1
    diversity_claim_groups.unit_reviews(source, grouped)
    for old_plan, new_plan in zip(original['plans'], grouped['plans'], strict=True):
        ref, _ = reference_reading(source, old_plan)
        raw = {}
        for request in grouped['read_input']['unit_requests']:
            anchor = request['source_anchor']
            old_anchor = groups[anchor]['original_units'][0] if anchor in groups else anchor
            raw[anchor] = {**ref[old_anchor], 'observation': {**ref[old_anchor]['observation'], 'source_anchor': anchor},
                           'evidence': [{'field': 'source_text', 'quote': quote} for quote in request['source_excerpts']]}
        measured = decode_response(source, grouped, new_plan, {'content': json.dumps(raw), 'finish_reason': 'stop'})
        previous = decode_response(source, original, old_plan, {'content': json.dumps(ref), 'finish_reason': 'stop'})
        if (measured['production_errors'] or previous['production_errors'] or measured['native'] != previous['native']
                or measured['decoder_receipt']['diagnostics'] != previous['decoder_receipt']['diagnostics']):
            raise ValueError('The new reader/decoder pair changed an independently reviewed reference result')
    return {'source': source['key'], 'before_units': len(before['units']), 'after_units': len(after['units']),
            'reachable_local_outcome_assignments_checked': checked, 'candidate_reference_decodes': len(grouped['plans'])}


def prepare():
    prior = ROOT / read(ANCHORED)['artifact_root']
    original, terminal = read(prior / 'binding.json'), read(prior / 'terminal.json')
    sources = read(prior / 'sources.json')
    if (digest(original) != prior.name or terminal['status'] != 'completed'
            or digest(sources) != original['original_sources_sha256'] or len(sources) != 2
            or any(source['project_split'] != 'train' for source in sources)):
        raise ValueError('Use both original mothers and the terminal anchored experiment')
    lock = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / lock['artifact_root'] / 'binding.json')
    if digest(roster) != lock['roster_sha256']:
        raise ValueError('The original TRAIN roster changed')
    train = [row for row in read(ROOT / roster['normalized_root'] / 'train/public.json')
             if row['dataset'] == 'LegalBench_Diversity']
    if len(train) != 24 or not {digest(source) for source in sources} <= {digest(source) for source in train}:
        raise ValueError('Keep the locked 24 Diversity TRAIN mothers and unchanged paired test inputs')
    before, after = diversity_source_binding.Provider(), diversity_claim_groups.Provider()
    proof = [verify_grouped_outputs(source, *before.views(source), *after.views(source)) for source in train]
    if not any(row['before_units'] > row['after_units'] for row in proof):
        raise ValueError('The proposed revision must affect the observed repeated-claim bottleneck')
    files = set(original['source_sha256']) | {'experiments/convergence_diversity_grouped_probe.py',
                                             'legal_skill_guard/paired_interfaces/diversity_claim_groups.py'}
    binding = {**original, 'study': 'Diversity_shared_claim_observation_fixed_mothers',
               'reason': 'The fixed reader misread the second amount in both shared clauses, duplicating four errors.',
               'expected_change': 'One bound read per original claim clause reduces duplicated amount errors. '
                                  'Mixed layouts separate amount errors from the citizenship polarity error.',
               'anchored_binding_sha256': digest(original), 'anchored_terminal_sha256': sha(prior / 'terminal.json'),
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
               'reference_decodes_sha256': digest(proof), 'all_four_certified_layouts': True}
    out = BASE / 'diversity_grouped_train' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'sources.json', sources)
    immutable_json(out / 'reference_proof.json', proof)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'matched_mothers': 2, 'reader_cells': 8}, POINTER)
    print(json.dumps({'binding': out.name, 'verified_sources': len(proof),
                      'changed_sources': sum(row['before_units'] > row['after_units'] for row in proof),
                      'local_outcome_assignments': sum(row['reachable_local_outcome_assignments_checked'] for row in proof),
                      'reference_decodes': sum(row['candidate_reference_decodes'] for row in proof)}), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding, sources = read(out / 'binding.json'), read(out / 'sources.json')
    if (out.name != digest(binding) or digest(sources) != binding['original_sources_sha256']
            or digest(read(out / 'reference_proof.json')) != binding['reference_decodes_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())):
        raise ValueError('The exact production or equivalence inputs have changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the current physical request before continuing')
    keys = [source['key'] for source in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-Diversity-grouped-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    provider = diversity_claim_groups.Provider()
    actor = InterfaceActor(executor, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=binding['source_sha256'])
    learner = RelationalInterfaceLibrary(out, actor=actor, train_sources=keys,
                                        initial_common_library_sha256=binding['common_library_sha256'])

    def grade(key):
        path = ROOT / binding['grading_path']
        if sha(path) != binding['grading_sha256']:
            raise ValueError('The native TRAIN grades changed')
        return read(path)[key]

    rows = []
    write_status(out, {'status': 'running', 'matched_mothers': 2, 'reader_cells': 8}, POINTER)
    try:
        for source in sources:
            view, = actor.views(source)
            observed = calibrate_source(learner, source, view, unit_reviews=diversity_claim_groups.unit_reviews(source, view),
                                        grade_provider=grade, visible_prefix=keys)
            rows.extend({'native_config': source['native_config'], 'profile': row['profile'],
                         'native': row['native_utility'], 'source_fidelity': row['source_fidelity'],
                         'executor_tokens': row['usage']['total_tokens'], 'physical_call_id': row['physical_call_id']}
                        for row in observed)
        result = {'status': 'completed', 'matched_mothers': 2, 'paired_scores': rows,
                  'executor_tokens': sum(row['executor_tokens'] for row in rows), 'TEST_opened': False}
        immutable_json(out / 'terminal.json', result)
        write_status(out, {'status': 'completed', 'matched_mothers': 2, 'reader_cells': 8,
                           'executor_tokens': result['executor_tokens']}, POINTER)
        print(json.dumps({**result, 'paired_scores': [{k: v for k, v in row.items() if k != 'source_fidelity'}
                                                      for row in rows]}), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
