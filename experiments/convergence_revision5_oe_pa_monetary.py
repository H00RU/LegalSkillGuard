"""Compare the new PA literal guard on settled B8 and archived M1 conditions."""

import json
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_oe_ec_formal as ec
from experiments import convergence_revision5_oe_scoped_forms as tr
from experiments import convergence_revision5_oe_scoped_forms_dev as dv
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_common_native_dev import archive
from experiments.convergence_revision5_diversity_formal import ledger_status
from legal_skill_guard.paired_interfaces import convergence_oe_pa_monetary as pa
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_oe_pa_monetary_20261119'
POINTER = HANDOFF / 'revision5_oe_pa_monetary_current.json'
DATASET = 'OpenExempt'
TASKS = ('EC', 'EV')


def compare(views, conditions, labels):
    reports = {}
    for task in TASKS:
        rows = [(key, view) for (key, family), view in views.items() if family == task]
        predictions = {}
        for name, bank in conditions.items():
            predictions[name] = [
                {'source': key, 'view': task,
                 'grade': grade_view(DATASET, view, labels[key][task], bank[key][task])['grade']}
                for key, view in rows]
        base = next(iter(predictions.values()))
        reports[task] = {name: {'f1': mean(r['grade'] for r in scores),
                                'improved': sum(b['grade'] > a['grade'] for a, b in zip(base, scores, strict=True)),
                                'regressed': sum(b['grade'] < a['grade'] for a, b in zip(base, scores, strict=True)),
                                'versus_entering': paired_source_effect(base, scores)}
                         for name, scores in predictions.items()}
        if 'relation_raw_PA' in predictions:
            reports[task]['relation_vs_fixed_after'] = paired_source_effect(
                predictions['fixed_raw_PA'], predictions['relation_raw_PA'])
    return reports


def original_comparison(pointer, role):
    stage = ROOT / read(pointer)['artifact_root']
    binding, terminal, cases, predictions = [read(stage / f'{name}.json')
                                             for name in ('binding', 'terminal', 'cases', 'predictions')]
    path_key, hash_key = ('grade', 'grade_sha256') if role == 'train' else ('grading_path', 'grading_sha256')
    cases_key = 'cases_sha256' if role == 'train' else 'case_sha256'
    path = ROOT / binding[path_key]
    if stage.name != digest(binding) or digest(cases) != binding[cases_key]:
        raise ValueError('M1 must use the original source-bound cases')
    if (terminal.get('TEST_opened', terminal.get('DEV_or_TEST_used')) or role not in path.parts
            or sha(path) != binding[hash_key] or sha(stage / 'predictions.json') != terminal['predictions_sha256']
            or any(sha(stage / 'source_snapshot' / key) != h for key, h in binding['source_sha256'].items())):
        raise ValueError('Expected the measured original paired M1 comparison')
    views, by_arm = {}, {}
    for case, result in zip(cases, predictions, strict=True):
        key, task, view = case['source'], case['family'], case['native']
        views[key, task] = view
        bank = {'fixed_raw': result[tr.FIXED]['raw'], 'relation_raw': result[tr.RELATION]['raw'],
                'fixed_audited': result[tr.FIXED]['audited'], 'relation_audited': result[tr.RELATION]['audited']}
        if role == 'dev':
            bank['same_information_review_direct'] = result['source_review']
        positives = pa.claims(view)
        for name, answer in bank.items():
            by_arm.setdefault(name, {}).setdefault(key, {})[task] = answer
            by_arm.setdefault(name + '_PA', {}).setdefault(key, {})[task] = pa.apply(task, answer, positives)
    return views, by_arm, path, sha(stage / 'terminal.json')


def b8_development():
    cohort, _, study, _ = archive()
    current = read(ec.POINTER)
    stage = ROOT / current['artifact_root']
    revised = verify(read(stage / 'terminal.json'), 'terminal_sha256')
    parent = ROOT / read(ec.ec.INTEGRATED)['artifact_root']
    parent_terminal = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    if (revised['terminal_sha256'] != current['terminal_sha256'] or revised['TEST_opened']
            or read(stage / 'binding.json')['parent_terminal_sha256'] != parent_terminal['terminal_sha256']):
        raise ValueError('Use the exact latest OpenExempt B8 revision')
    views, mothers = {}, {}
    for source in cohort:
        if source['dataset'] == DATASET:
            mothers[source['key']] = source
            views.update({(source['key'], view['id']): view for view in source['views']})
    arms = {}
    for arm, cell in revised['cells'].items():
        folder = stage / 'dev/B8' / arm
        if (sha(folder / 'EC_predictions.json') != cell['new_EC_predictions_sha256']
                or cell != verify(read(folder / 'EC_scores.json'), 'cell_sha256')):
            raise ValueError('The OpenExempt EC route must bind the exact revised B8 predictions')
        archive_cell = read(folder / 'EC_predictions.json')
        seal = verify(read(parent / 'dev/B8' / arm / 'prediction_seal.json'), 'prediction_seal_sha256')
        if cell['preserved_parent_predictions_sha256'] != seal['prediction_seal_sha256']:
            raise ValueError('Inherit exact EV predictions from the integrated B8 cell')
        arm_base = {}
        for key, receipt in archive_cell.items():
            if receipt['old_prediction_sha256'] != seal['predictions_sha256'][key]:
                raise ValueError('A revised source prediction lost its native parent')
            arm_base[key] = {t: receipt['native'][t]['answer'] for t in TASKS}
        if set(arm_base) != set(mothers):
            raise ValueError('Every original B8 OpenExempt mother should remain in the denominator')
        updated = {key: {t: pa.apply(t, answer, pa.claims(views[key, t])) for t, answer in values.items()}
                   for key, values in arm_base.items()}
        arms[arm] = {'shared': arm_base, 'shared_PA': updated}
    path = ROOT / study['grading_paths'][DATASET]
    if 'dev' not in path.parts or sha(path) != study['grading_file_sha256'][study['grading_paths'][DATASET]]:
        raise ValueError('Keep native labels bound to the original DEV split')
    return views, arms, path, revised['terminal_sha256']


def run():
    ledger = ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Reconcile existing requests before changing a development binding')
    train, dev = original_comparison(tr.POINTER, 'train'), original_comparison(dv.POINTER, 'dev')
    b8_views, b8_arms, dev_grade, revised_stage = b8_development()
    binding = {'stage': 'PA_source_bound_monetary_benchmark', 'M1_TRAIN_terminal_sha256': train[3],
               'M1_DEV_terminal_sha256': dev[3], 'B8_EC_terminal_sha256': revised_stage,
               'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (__file__, pa.__file__)},
               'scope': 'positive source-bound Section 8123 claims in EC and EV', 'new_model_calls': 0}
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    prediction_sha = immutable_json(out / 'predictions.json', {'B8': b8_arms, 'M1_TRAIN': train[1], 'M1_DEV': dev[1]})
    scores = {arm: compare(b8_views, bank, read(dev_grade)) for arm, bank in b8_arms.items()}
    arm_metrics = {name: compare(views, arms, read(path)) for name, (views, arms, path, _) in
                   (('TRAIN', train), ('DEV', dev))}
    counts = {task: {'covered_mothers': sum(bool(pa.claims(v)) for (_, t), v in b8_views.items() if task == t),
                     'literal_claims': sum(len(pa.claims(v)) for (_, t), v in b8_views.items() if task == t)}
              for task in TASKS}
    if ledger_status() != ledger:
        raise ValueError('The continuous ledger changed during the local-only comparison')
    report = sealed({'status': 'settled_PA_general_exemption_replay', 'binding_sha256': digest(binding),
                     'predictions_sha256': prediction_sha, 'B8_scores': scores, 'B8_source_coverage': counts,
                     'archived_M1_scores': arm_metrics, 'model_calls': 0, 'ledger': ledger,
                     'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'status': report['status'],
                                   'terminal_sha256': report['terminal_sha256']}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
