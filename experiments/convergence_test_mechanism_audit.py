"""Audit executed M1 and M2 comparisons after the final TEST seal."""

from collections import Counter, defaultdict
import sqlite3

from experiments.convergence_eval_cost_audit import _physical_refs, _settled, completed_stage
from experiments.convergence_eval_native_effects import _metric_effects, _rows
from experiments.convergence_formal_test import INITIAL_ARM, POINTER
from experiments.convergence_m1_dev_source_audit import _unit_checks
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.diversity_claim_groups import Provider
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ORDINARY = 'common_teacher_skill_learning'
M1 = 'method_one_only'
M2 = 'method_two_only'
JOINT = 'both'


def read_cell(directory, expected, keys):
    score = verify(read(directory / 'scores.json'), 'cell_sha256')
    seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
    if (score['cell_sha256'] != expected or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']
            or seal['task_sha256'] != digest(read(directory / 'task.json'))
            or set(seal['predictions_sha256']) != keys):
        raise ValueError('Audit only the complete original TEST prediction seal')
    rows = defaultdict(dict)
    for row in score['source_scores']:
        rows[row['source']][row['view']] = row
    if set(rows) != keys or sum(map(len, rows.values())) != len(score['source_scores']):
        raise ValueError('Each TEST mother and native view needs its own saved grade')
    predictions = {}
    for key, expected in seal['predictions_sha256'].items():
        prediction = read(directory / 'predictions' / (digest(key) + '.json'))
        if digest(prediction) != expected or prediction['source'] != key:
            raise ValueError('A TEST prediction differs from the frozen evaluator record')
        result = prediction['result']
        predictions[key] = (result, frozenset(_physical_refs(result)))
    return rows, predictions


def m1_rows(db, provider, cohort, cells, comparison):
    control, learned = comparison
    rows, predicted = cells[learned]
    prior, _ = cells[control]
    for source in cohort:
        key = source['key']
        before, = prior[key].values()
        after, = rows[key].values()
        result, physical = predicted[key]
        route = result['selection']['route']
        checks = {}
        if route == 'synthesized_interface':
            reading, = result['reads']
            for identity in physical:
                _settled(db, identity, key, 'skill_test')
            view, = provider.views(source)
            plan, = (p for p in view['plans'] if p['version'] == reading['raw_read_version'])
            checks = _unit_checks(source, reading, plan)
        yield {'route': route, 'executed_fallback': result['fallback_executed'],
               'grade_change': after['grade'] - before['grade'], 'checks': checks}


def summarize_m1(rows):
    repaired = [r for r in rows if r['grade_change'] > 0]
    faithful = [r for r in rows if r['checks'] and all(c['source_fidelity_verified'] for c in r['checks'].values())]
    counts = defaultdict(Counter)
    for row in rows:
        for check in row['checks'].values():
            counts[check['kind']][check['status']] += 1
    return {'mothers': len(rows), 'routes': dict(Counter(r['route'] for r in rows)),
            'executed_fallback': sum(r['executed_fallback'] for r in rows),
            'repairs': len(repaired), 'regressions': sum(r['grade_change'] < 0 for r in rows),
            'fully_source_faithful': len(faithful),
            'repairs_fully_source_faithful': sum(r['grade_change'] > 0 for r in faithful),
            'tested_local_units_by_kind': {kind: dict(totals) for kind, totals in counts.items()}}


def compare_m2(before, after, datasets):
    earlier, prior_predictions = before
    later, new_predictions = after
    totals = defaultdict(Counter)
    for key, dataset in datasets.items():
        if earlier[key].keys() != later[key].keys():
            raise ValueError('The two M2 conditions must predict the same native tasks')
        group = totals[dataset]
        group['mothers'] += 1
        group['native_views'] += len(earlier[key])
        group['identical_native_views'] += sum(row == later[key][view] for view, row in earlier[key].items())
        group['same_physical_response_set'] += prior_predictions[key][1] == new_predictions[key][1]
    return {dataset: dict(row) for dataset, row in totals.items()}


def compare_initial(stage, checkpoint, terminal, binding):
    reference = terminal['static_initial_reference']
    if (reference['reference_only'] is not True or reference['checkpoint_batch'] != 0
            or reference['reference_freeze_sha256'] != binding['static_initial_reference']['freeze_sha256']):
        raise ValueError('The initial comparison must use the reference fixed before TEST inference')
    initial = stage / 'initial_reference/test/B8' / INITIAL_ARM
    joint = checkpoint / 'test/B8' / JOINT
    count = terminal['mothers_per_arm']
    initial_rows = _rows(initial, reference['cell_sha256'], 'test', 8, INITIAL_ARM, count)
    joint_rows = _rows(joint, terminal['per_arm'][JOINT]['cell_sha256'], 'test', 8, JOINT, count)
    grading_path = stage / 'grading_receipts/ContractNLI.json'
    grading = read(grading_path)
    if (sha(grading_path) != terminal['grading_receipts_sha256']['ContractNLI']
            or grading['freeze_sha256'] != terminal['freeze_sha256']):
        raise ValueError('The initial interval must keep the same original evidence scope')
    return _metric_effects({INITIAL_ARM: initial_rows, JOINT: joint_rows}, INITIAL_ARM, JOINT,
                           {'per_arm': {INITIAL_ARM: reference, JOINT: terminal['per_arm'][JOINT]}},
                           reference['joint_minus_initial'], count // 5, {tuple(r) for r in grading['evidence_units']})


def run():
    if read(POINTER)['status'] != 'completed_fixed_B8_TEST':
        raise ValueError('Wait for all five frozen TEST cells and the static reference')
    stage, checkpoint, terminal, expected = completed_stage('test', 8)
    binding = read(stage / 'binding.json')
    roster = read(ROOT / binding['roster_path'])
    if (terminal['freeze_sha256'] != binding['B8_frozen_selection_sha256']
            or not terminal['static_initial_reference']['reference_only']):
        raise ValueError('The TEST evidence must use the prespecified freeze')
    datasets = {r['source']: r['dataset'] for r in roster['sealed_TEST_identities']}
    if len(datasets) != terminal['mothers_per_arm'] or len(datasets) != 160:
        raise ValueError('The final roster changed')
    cells = {arm: read_cell(checkpoint / 'test/B8' / arm, expected[arm], datasets.keys())
             for arm in (ORDINARY, M1, M2, JOINT)}
    public = read(ROOT / roster['normalized_root'] / 'sealed_test/public.json')
    diversity = [s for s in public if s['dataset'] == 'LegalBench_Diversity']
    if {s['key'] for s in diversity} != {k for k, d in datasets.items() if d == 'LegalBench_Diversity'}:
        raise ValueError('The fidelity audit must cover the exact frozen Diversity mothers')
    provider = Provider()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        m1 = {learned + '_minus_' + control:
              summarize_m1(list(m1_rows(db, provider, diversity, cells, (control, learned))))
              for control, learned in ((ORDINARY, M1), (M2, JOINT))}
    m2 = {learned + '_minus_' + control: compare_m2(cells[control], cells[learned], datasets)
          for control, learned in ((ORDINARY, M2), (M1, JOINT))}
    receipt = {'terminal_sha256': sha(stage / 'terminal.json'), 'freeze_sha256': terminal['freeze_sha256'],
               'M1_Diversity_source_fidelity': m1, 'M2_matched_native_outputs_and_responses': m2,
               'joint_minus_static_B0_native_metrics': compare_initial(stage, checkpoint, terminal, binding),
               'new_model_requests': 0, 'native_annotations_accessed': False}
    out = BASE / 'test_mechanism_audit' / digest(receipt) / 'terminal.json'
    immutable_json(out, receipt)
    immutable_json(HANDOFF / 'B8_TEST_mechanism_audit.json', {'receipt': str(out.relative_to(ROOT))})
    print(out.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    run()
