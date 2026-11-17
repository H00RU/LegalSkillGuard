"""Measure compositional fee updates on the two already observed Airline failures."""

import argparse
import json
import sqlite3

import jsonschema

from experiments.convergence_airline_joint_relation import BAG
from experiments.convergence_airline_update_probe import PROBE as DIRECT_UPDATE
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'airline_structured_update_current.json'
SYSTEM = (
    'Read this Airline calculation problem. Do not return the final amount. Copy the ticket price from the facts. '
    'Use the public rule text to report each item’s own base check-in, oversize, and overweight charges separately, '
    'before combining charges. Use the original numbered item ID. If an item is not checked, return zero charges '
    'only when the policy establishes zero for it. If the source or rule does not determine a field, use null. '
    'Keep the weight and dimensions attached to the same numbered item. Use compact JSON.'
)
MODES = ('add_charges', 'match_bag_max', 'unpaired_marginals')


def reading_schema(bag_count):
    fee = {'type': ['integer', 'null'], 'minimum': 0}
    row = record_schema({'bag_id': {'type': 'integer', 'minimum': 1, 'maximum': bag_count},
                         'base_fee': fee, 'oversize': fee, 'overweight': fee})
    return record_schema({'ticket': fee, 'items': {'type': 'array', 'items': row,
                                                    'minItems': bag_count, 'maxItems': bag_count}})


def compose(reading, bag_count):
    """Use the identical actually read coordinates for every typed update."""
    rows = reading['items']
    if sorted(row['bag_id'] for row in rows) != list(range(1, bag_count + 1)):
        raise ValueError('The structure must contain every original item exactly once')
    ticket = reading['ticket']
    fields = ('base_fee', 'oversize', 'overweight')
    if ticket is None or any(row[field] is None for row in rows for field in fields):
        return dict.fromkeys(MODES)
    base = ticket + sum(row['base_fee'] for row in rows)
    w = [row['overweight'] for row in rows]
    s = [row['oversize'] for row in rows]
    return {
        'add_charges': base + sum(w) + sum(s),
        'match_bag_max': base + sum(map(max, w, s)),
        'unpaired_marginals': base + sum(map(max, sorted(w), sorted(s))),
    }


def prepare():
    prior = ROOT / read(DIRECT_UPDATE)['artifact_root']
    old = read(prior / 'binding.json')
    terminal = read(prior / 'terminal.json')
    if (terminal['status'] != 'completed' or terminal['native_scores']['baseline'] != 0.0
            or any(terminal['native_scores'].values())):
        raise ValueError('The direct-output comparison must establish the measured decomposition failure')
    pairs = read(prior / 'train_pairs.json')
    if digest(pairs) != old['train_pairs_sha256']:
        raise ValueError('The evidence-bound Airline cases changed')
    for pair in pairs:
        for name in ('original', 'edited'):
            source = pair[name]
            if source['project_split'] != 'train' or len(BAG.findall(source['views'][0]['public']['facts'])) < 2:
                raise ValueError('Use the original structured TRAIN bag inventories')
    paths = [
        'experiments/convergence_airline_structured_update.py',
        'experiments/convergence_airline_joint_relation.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/skill_evolution/native.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py',
    ]
    binding = {
        'study_id': 'convergence_Airline_structured_arithmetic_updates_v1',
        'actual_previous_negative_result_sha256': sha(prior / 'terminal.json'),
        'source_sha256': {name: sha(ROOT / name) for name in paths},
        'pairs_sha256': digest(pairs), 'executor': old['executor'],
        'grading_path': old['native_grading_path'], 'grading_sha256': old['native_grading_sha256'],
        'candidate_pool': list(MODES), 'new_executor_cells': 4, 'new_teacher_cells': 0,
        'candidate_pool_type': 'fixed_controlled_program_level_aggregation_alternatives',
        'native_legal_reference_only_for_validation': True,
    }
    out = BASE / 'airline_structured_update' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', pairs)
    write_status(out, {'status': 'prepared', 'new_executor_cells': 4}, POINTER)
    print(json.dumps({'status': 'prepared', 'binding': digest(binding), 'new_executor_cells': 4}), flush=True)


def measure(executor, source, out):
    public = source['views'][0]['public']
    bag_count = len(BAG.findall(public['facts']))
    schema = reading_schema(bag_count)
    messages = [{'role': 'system', 'content': SYSTEM + '\nSchema: ' + json.dumps(schema, separators=(',', ':'))},
                {'role': 'user', 'content': json.dumps(public, sort_keys=True, ensure_ascii=False)}]
    call_id = executor.ledger.run_id + ':coordinates:' + digest([source['key'], messages])
    response = executor.generate(call_id, source=source['key'], purpose='skill_actor', messages=messages,
                                 schema=schema, thinking=False)
    verify_physical_response(executor, identity=call_id, source=source['key'], purpose='skill_actor',
                             content_sha256=digest(response['content']), usage=response['usage'],
                             finish_reason=response['finish_reason'])
    error = None
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('The structured response was incomplete')
        record = json.loads(response['content'])
        jsonschema.validate(record, schema)
        predictions = compose(record, bag_count)
    except (ValueError, jsonschema.ValidationError) as failure:
        error = str(failure)
        predictions = dict.fromkeys(MODES)
    row = {'physical_call_id': call_id, 'source_sha256': digest(source),
           'predictions': predictions, 'production_error': error, 'usage': response['usage']}
    immutable_json(out / 'measurements' / (digest(source) + '.json'), row)
    return row


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    pairs = read(out / 'cases.json')
    if (digest(pairs) != binding['pairs_sha256'] or sha(ROOT / binding['grading_path']) != binding['grading_sha256']
            or any(sha(ROOT / name) != expected for name, expected in binding['source_sha256'].items())):
        raise ValueError('Keep the original cases and code version bound')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Wait for the current DEV run to settle')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-airline-structured-' + digest(binding)[:16],
        sources={'train': [pair['original']['key'] for pair in pairs], 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    rows = []
    write_status(out, {'status': 'running', 'completed_pairs': 0}, POINTER)
    try:
        for pair in pairs:
            rows.append((measure(executor, pair['original'], out), measure(executor, pair['edited'], out)))
            write_status(out, {'status': 'running', 'completed_pairs': len(rows)}, POINTER)
        grades = read(ROOT / binding['grading_path'])
        evidence = {mode: [] for mode in MODES}
        for pair, (original, edited) in zip(pairs, rows, strict=True):
            source = pair['original']
            for mode in MODES:
                old, new = original['predictions'][mode], edited['predictions'][mode]
                concrete = type(old) is int and type(new) is int
                observed = [old - pair['unchanged_fees'], new - pair['unchanged_fees']] if concrete else None
                allowed = pair['allowed_surcharges']
                utility = grade_view(source['dataset'], source['views'][0],
                                     grades[source['key']]['native'], old)['grade']
                evidence[mode].append({'source': source['key'], 'native_utility': utility,
                    'allowed_surcharge_signature': allowed, 'actual_surcharge_signature': observed,
                    'audited_relation_passed': observed == allowed,
                    'actual_delta': new - old if concrete else None,
                    'physical_call_ids': [original['physical_call_id'], edited['physical_call_id']]})
        scores = {mode: sum(row['native_utility'] for row in entries) / len(entries)
                  for mode, entries in evidence.items()}
        order = sorted(MODES, key=lambda mode: (-scores[mode], MODES.index(mode)))
        vetted = next((mode for mode in order if scores[mode] > 0
                       and all(row['audited_relation_passed'] for row in evidence[mode])), 'incumbent')
        terminal = {'status': 'completed', 'native_scores': scores, 'method_native_choice': order[0] if scores[order[0]] else 'incumbent',
                    'method_relation_choice': vetted, 'same_actual_coordinate_reads_reused': True,
                    'evidence': evidence, 'native_mothers': len(pairs), 'theory_has_single_local_interpretation': True}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, POINTER)
        print(json.dumps({key: value for key, value in terminal.items() if key != 'evidence'}), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
