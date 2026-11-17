"""Replay the original TRAIN predictions and run only the two source edits."""

import argparse
import json
import sqlite3

from experiments.convergence_pilot_b0 import (
    BASE, HANDOFF, LEDGER, POINTER, ROOT, read, sha, write_status,
)
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

PROBE = HANDOFF / 'airline_joint_reader_current.json'


def prepare():
    compiled = ROOT / read(HANDOFF / 'airline_joint_relation_current.json')['artifact_root']
    baseline = ROOT / read(POINTER)['artifact_root']
    original_binding = read(baseline / 'binding.json')
    original_sources = read(baseline / 'public_TRAIN_pilot.json')
    if (not (baseline / 'terminal.json').is_file()
            or digest(original_sources) != original_binding['sources_digest']):
        raise ValueError('Use the original five-library common B0 outcomes')
    sources = {source['key']: source for source in original_sources if source['dataset'] == 'RuleArena_Airline'}
    cells = []
    for row in read(compiled / 'quantitative_source_edits.json'):
        mother = sources[row['source']]
        original, edited = row['source_pair']
        view, = mother['views']
        if original != view['public'] or {**edited, 'facts': original['facts']} != original:
            raise ValueError('The edited source changed more than the reviewed native facts')
        original_row = read(baseline / 'source_results' / (digest(mother['key']) + '.json'))
        if original_row['source'] != mother['key'] or not original_row['native']['native']['handled']:
            raise ValueError('A concrete original answer is required for the observed paired delta')
        left, right = row['nonlinear_native_rule_surcharge_pair']
        cells.append({'source': {**mother, 'views': [{**view, 'public': edited}]},
                      'original_native': original_row['native']['native']['answer'],
                      'original_native_result_sha256': digest(original_row),
                      'original_utility': original_row['grades']['native']['grade'],
                      'required_fee_delta': right - left})
    if len(cells) != 2:
        raise ValueError('Use both locked source edits')
    paths = set(original_binding['source_sha256']) | {'experiments/convergence_airline_joint_probe.py'}
    binding = {'case_sha256': digest(cells), 'compiled_edits_sha256': sha(compiled / 'quantitative_source_edits.json'),
               'baseline_summary_sha256': sha(baseline / 'terminal.json'),
               'source_sha256': {name: sha(ROOT / name) for name in sorted(paths)},
               'executor': original_binding['executor'], 'program': original_binding['program'],
               'fixed_new_calls': 2, 'no_new_native_gold': True}
    out = BASE / 'airline_joint_reader' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cells.json', cells)
    write_status(out, {'status': 'prepared', 'new_cells': 2}, PROBE)
    print(json.dumps({'status': 'prepared', 'binding': digest(binding), 'new_cells': 2}), flush=True)


def run():
    out = ROOT / read(PROBE)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    cases = read(out / 'cells.json')
    if digest(cases) != binding['case_sha256'] or any(
            sha(ROOT / name) != expected for name, expected in binding['source_sha256'].items()):
        raise ValueError('The fixed Airline probe changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle existing research requests first')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-airline-joint-' + digest(binding)[:16],
        sources={'train': [case['source']['key'] for case in cases], 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    actor = ProgramActor(executor, out, max_calls=1)
    rows = []
    write_status(out, {'status': 'running', 'completed': 0}, PROBE)
    try:
        for case in cases:
            source, program = case['source'], binding['program']
            output = actor.execute(program, source, 'skill_actor')
            actor.verify_program_result(source, program, 'skill_actor', output)
            original, edited = case['original_native'], output['native']['native']['answer']
            actual_delta = edited - original if type(edited) is int and type(original) is int else None
            row = {'source': source['key'], 'original_native_utility': case['original_utility'],
                   'required_fee_delta': case['required_fee_delta'], 'observed_delta': actual_delta,
                   'violated_relation': actual_delta is not None and actual_delta != case['required_fee_delta'],
                   'concrete_paired_signature': actual_delta is not None,
                   'new_executor_call_ids': [r['physical_call_id'] for r in output['execution']['traces']
                                             if 'finish_reason' in r and 'physical_call_id' in r]}
            immutable_json(out / 'pair_results' / (digest(source['key']) + '.json'), row)
            rows.append(row)
        terminal = {'status': 'completed', 'comparison_rows': rows, 'scored_native_mothers_added': 0,
                    'old_native_reads_reused': len(rows), 'TRAIN_scope_only': True}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, PROBE)
        print(json.dumps(terminal), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'completed': len(rows),
                           'error_type': type(error).__name__}, PROBE)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
