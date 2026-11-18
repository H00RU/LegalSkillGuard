"""Compute paired mother-level intervals for each fixed native evaluation metric."""

import argparse
import json
import math

from experiments.convergence_eval_cost_audit import completed_stage
from experiments.convergence_formal_curves import COMPARISONS
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def _mean(rows):
    return math.fsum(row['grade'] for row in rows) / len(rows)


def _paired(before, after):
    return {**paired_source_effect(before, after), 'before': _mean(before), 'after': _mean(after)}


def _rows(cell, expected, partition, batch, arm, mothers):
    score = verify(read(cell / 'scores.json'), 'cell_sha256')
    seal = verify(read(cell / 'prediction_seal.json'), 'prediction_seal_sha256')
    if ((score['cell_sha256'], score['arm'], score['partition'], score['batch']) != (expected, arm, partition, batch)
            or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']
            or set(seal['predictions_sha256']) != {row['source'] for row in score['source_scores']}
            or len(seal['predictions_sha256']) != mothers):
        raise ValueError('Use the exact complete scored set for the requested arm')
    return score['source_scores']


def _metric_effects(rows, before, after, terminal, previous_effects, mothers_per_dataset):
    result = {}
    for dataset in sorted(ConvergenceEvaluation.datasets):
        a, b = ([row for row in rows[arm] if row['dataset'] == dataset] for arm in (before, after))
        if len({r['source'] for r in a}) != mothers_per_dataset:
            raise ValueError('The native comparison changed the fixed dataset denominator')
        views = sorted({row['view'] for row in a}) if dataset in ('OpenExempt', 'MAUD') else ['all']
        result[dataset] = {view: _paired([x for x in a if view == 'all' or x['view'] == view],
                                         [x for x in b if view == 'all' or x['view'] == view]) for view in views}
        summary = [terminal['per_arm'][arm]['native'][dataset] for arm in (before, after)]
        for view in views:
            for side, saved in zip(('before', 'after'), summary, strict=True):
                if not math.isclose(result[dataset][view][side], saved['views'][view]['native_utility'], abs_tol=1e-12):
                    raise ValueError('The newly stratified score differs from the published native point estimate')
        if dataset == 'ContractNLI':
            if any(metrics['evidence_f1']['native_units'] != len(cell)
                   for metrics, cell in zip(summary, (a, b), strict=True)):
                raise ValueError('An omitted evidence annotation needs its exact original cohort mask')
            evidence = [[{**r, 'grade': r['native_metrics'].get('evidence_f1', 0.)} for r in side] for side in (a, b)]
            effect = _paired(*evidence)
            for side, saved in zip(('before', 'after'), summary, strict=True):
                if not math.isclose(effect[side], saved['evidence_f1']['mean'], abs_tol=1e-12):
                    raise ValueError('ContractNLI evidence F1 must reproduce the original scorer')
            result[dataset]['evidence_f1'] = effect
        if dataset == 'LegalBench_Diversity':
            initial, revised = (side['balanced_accuracy'] for side in summary)
            effect = previous_effects[dataset].get('balanced_accuracy_effect')
            if effect is None:
                if {r['source']: r['grade'] for r in a} != {r['source']: r['grade'] for r in b}:
                    raise ValueError('A changed Diversity prediction requires its original stratification receipt')
                counts = summary[0]['class_counts']
                if (set(counts) != {'Yes', 'No'} or counts != summary[1]['class_counts']
                        or sum(counts.values()) != mothers_per_dataset):
                    raise ValueError('The original Diversity class marginals changed')
                effect = {**previous_effects[dataset], 'stratum_sizes': counts,
                          'paired_source_bootstrap_95': [0., 0.] if min(counts.values()) > 1 else None}
            if not math.isclose(revised - initial, effect['mean_change'], abs_tol=1e-12):
                raise ValueError('Preserve the original class-stratified Diversity effect')
            result[dataset]['balanced_accuracy'] = {**effect, 'before': initial, 'after': revised}
    return result


def run(partition, batch):
    stage, checkpoint, terminal, arm_seals = completed_stage(partition, batch)
    mothers = 160 if partition == 'test' else 80
    rows = {arm: _rows(checkpoint / partition / f'B{batch}' / arm, expected, partition, batch, arm, mothers)
            for arm, expected in arm_seals.items()}
    native = {}
    earlier = terminal['paired_effects' if partition == 'test' else 'paired_independent_arm_comparisons']
    if partition == 'dev' and batch == 1:
        supplemental = read(ROOT / read(HANDOFF / 'B1_Diversity_BAL_accuracy_20261118.json')['receipt'])
        if supplemental['TEST_opened'] or supplemental['cells'] != arm_seals:
            raise ValueError('The original B1 class strata must bind the same completed arm cells')
        earlier = {pair: {**metrics, 'LegalBench_Diversity': supplemental['paired_contrasts'].get(
            pair, metrics['LegalBench_Diversity'])} for pair, metrics in earlier.items()}
    for before, after in COMPARISONS:
        pair = after + '_minus_' + before
        native[pair] = _metric_effects(rows, before, after, terminal, earlier[pair], mothers // 5)
    result = {'partition': partition, 'batch': batch, 'mothers_per_arm': mothers,
              'terminal_sha256': sha(stage / 'terminal.json'), 'paired_metric_intervals': native,
              'no_annotation_files_opened': True, 'new_model_requests': 0}
    out = BASE / 'evaluation_native_effects' / digest(result) / 'terminal.json'
    immutable_json(out, result)
    index = str(out.relative_to(ROOT))
    immutable_json(HANDOFF / f'{partition.upper()}_B{batch}_native_effects_20261118.json', {'receipt': index})
    print(json.dumps({'receipt': index, 'arm_comparisons': len(native)}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partition', choices=('dev', 'test'), default='dev')
    parser.add_argument('--batch', type=int, choices=(1, 2, 4, 8), required=True)
    args = parser.parse_args()
    if args.partition == 'test' and args.batch != 8:
        parser.error('the fixed TEST checkpoint is B8')
    run(args.partition, args.batch)
