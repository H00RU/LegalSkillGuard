"""Attribute settled physical evaluation costs to exact sealed five-arm predictions."""

import argparse
from collections import Counter, defaultdict
import json
import math
import sqlite3

from experiments.convergence_formal_b1_dev import POINTER as FIRST_DEV
from experiments.convergence_formal_curves import pointer as curve_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def _physical_refs(value):
    if isinstance(value, dict):
        for field, item in value.items():
            if field == 'physical_call_id' and isinstance(item, str):
                yield item
            else:
                yield from _physical_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _physical_refs(item)


def _usage(records):
    rows = list(records)
    return {'physical_calls': len(rows), 'executor_tokens': sum(row['tokens'] for row in rows),
            'executor_elapsed_seconds': math.fsum(row['elapsed_seconds'] for row in rows),
            'finish_reasons': dict(Counter(row['finish_reason'] for row in rows))}


def _settled(exposure, identity, source, purpose):
    row = exposure.execute('select role,status,source,purpose,result,reserved_at from calls where id=?',
                           (identity,)).fetchone()
    if row is None or row[:4] != ('executor', 'completed', source, purpose):
        raise ValueError('A prediction reference has no exact settled source/purpose executor response')
    result = json.loads(row[4])
    return {'tokens': result['usage']['total_tokens'], 'finish_reason': result['finish_reason'],
            'elapsed_seconds': result['elapsed_seconds'], 'reserved_at': row[5]}


def _cell_refs(db, cell, expected_cell, partition, cohort_size):
    score = verify(read(cell / 'scores.json'), 'cell_sha256')
    seal = verify(read(cell / 'prediction_seal.json'), 'prediction_seal_sha256')
    task = read(cell / 'task.json')
    if (score['cell_sha256'] != expected_cell or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']
            or seal['task_sha256'] != digest(task) or task['partition'] != partition
            or len(seal['predictions_sha256']) != cohort_size):
        raise ValueError('Only the exact settled arm may be used to attribute cost')
    by_dataset = defaultdict(dict)
    for source, expected in sorted(seal['predictions_sha256'].items()):
        prediction = read(cell / 'predictions' / (digest(source) + '.json'))
        if digest(prediction) != expected or prediction['source'] != source:
            raise ValueError('An original prediction changed after sealing')
        dataset = prediction['dataset']
        records = by_dataset[dataset]
        for identity in set(_physical_refs(prediction['result'])):
            measures = _settled(db, identity, source, 'skill_' + partition)
            if identity in records and records[identity] != measures:
                raise ValueError('Physical cost provenance changed within the arm')
            records[identity] = measures
    return seal, by_dataset


def completed_stage(partition, batch):
    pointer = (HANDOFF / 'formal_B8_TEST_current.json' if partition == 'test'
               else FIRST_DEV if batch == 1 else curve_pointer(batch))
    stage = ROOT / read(pointer)['artifact_root']
    terminal, binding = (read(stage / filename) for filename in ('terminal.json', 'binding.json'))
    if stage.name != digest(binding) or not terminal['status'].startswith('completed_'):
        raise ValueError('This audit requires the exact completed evaluation')
    checkpoint = ROOT / binding.get('checkpoint_root', binding.get('bootstrap_root', ''))
    arm_seals = (terminal['cell_sha256'] if partition == 'dev'
                 else {arm: row['cell_sha256'] for arm, row in terminal['per_arm'].items()})
    if set(arm_seals) != set(ConvergenceEvaluation.arms):
        raise ValueError('Only a complete five-arm checkpoint supplies the report')
    return stage, checkpoint, terminal, arm_seals


def run(partition, batch):
    stage, checkpoint, terminal, arm_seals = completed_stage(partition, batch)
    cohort_size = 160 if partition == 'test' else 80
    prefix = f'convergence-formal-B{batch}-{partition.upper()}-{stage.name[:16]}:'
    cells = {arm: (checkpoint / partition / f'B{batch}' / arm, score)
             for arm, score in arm_seals.items()}
    if partition == 'test':
        reference = terminal['static_initial_reference']
        binding = read(stage / 'binding.json')['static_initial_reference']
        if (reference['reference_only'] is not True or reference['checkpoint_batch'] != 0
                or reference['reference_freeze_sha256'] != binding['freeze_sha256']):
            raise ValueError('The observed reference must bind the original pre-inference B0 selection')
        initial_arm, = binding['choices']
        cells['static_initial_reference'] = (stage / 'initial_reference' / 'test' / 'B8' / initial_arm,
                                             reference['cell_sha256'])
    all_refs, combined, costs = Counter(), {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        physical = db.execute('select id,source from calls where id like ?', (prefix + '%',)).fetchall()
        current = {identity: _settled(db, identity, source, 'skill_' + partition) for identity, source in physical}
        for label, (cell, score) in cells.items():
            seal, by_dataset = _cell_refs(db, cell, score, partition, cohort_size)
            refs = {identity: cost for bucket in by_dataset.values() for identity, cost in bucket.items()}
            if label != 'static_initial_reference':
                all_refs.update(refs.keys())
            combined.update(refs)
            costs[label] = {'prediction_seal_sha256': seal['prediction_seal_sha256'],
                            'referenced_physical': _usage(refs.values()),
                            'referenced_by_dataset': {name: _usage(rows.values()) for name, rows in by_dataset.items()},
                            'new_stage_calls_referenced': len(refs.keys() & current.keys())}
    attributable = _usage(current.values())
    if (attributable['physical_calls'] != terminal['executor_calls']
            or attributable['executor_tokens'] != terminal['executor_tokens'] or not current.keys() <= combined.keys()):
        raise ValueError('Stage physical costs differ from the saved terminal or are absent from sealed predictions')
    wall = (max(row['reserved_at'] + row['elapsed_seconds'] for row in current.values())
            - min(row['reserved_at'] for row in current.values()) if current else 0)
    reference_costs = costs.pop('static_initial_reference', None)
    result = {'partition': partition, 'batch': batch, 'terminal_sha256': sha(stage / 'terminal.json'),
              'arms': costs, 'new_physical_usage': attributable, 'union_referenced_physical': _usage(combined.values()),
              'physical_reads_used_by_multiple_arms': sum(count > 1 for count in all_refs.values()),
              'observed_request_window_seconds_including_pauses': wall,
              'billing_basis': 'existing_local_service_no_per_request_API_invoice', 'new_model_requests': 0}
    if reference_costs is not None:
        result['static_initial_reference'] = reference_costs
    out = BASE / 'evaluation_cost_audit' / digest(result) / 'terminal.json'
    immutable_json(out, result)
    immutable_json(HANDOFF / f'{partition.upper()}_B{batch}_physical_cost_audit_20261118.json',
                   {'receipt': str(out.relative_to(ROOT)), 'new_physical_usage': attributable})
    print(json.dumps({'new_physical_usage': attributable, 'audit': str(out.relative_to(ROOT))}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partition', choices=('dev', 'test'), default='dev')
    parser.add_argument('--batch', type=int, choices=(1, 2, 4, 8), required=True)
    args = parser.parse_args()
    if args.partition == 'test' and args.batch != 8:
        parser.error('the fixed TEST checkpoint is B8')
    run(args.partition, args.batch)
