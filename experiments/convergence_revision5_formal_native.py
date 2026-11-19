"""Attach the verified shared native controls to the revised B8 DEV procedure."""

import json
from collections import Counter
from functools import lru_cache

from experiments import convergence_revision5_common_native_dev as common
from experiments import convergence_revision5_diversity_formal as diversity_formal
from experiments.convergence_formal_b1_dev import _native_metrics
from experiments.convergence_formal_curves import DEV_B0
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.formal_evaluation import (
    ConvergenceEvaluation,
    sealed,
    verify,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_formal_native_20261119'
CURRENT = HANDOFF / 'revision5_formal_native_current.json'
DATASET = diversity_formal.DATASET


def evidence_bank():
    published = read(common.TABLE)
    for stage in common.HOME.iterdir():
        if not (stage / 'terminal.json').is_file() or read(stage / 'terminal.json') != published:
            continue
        spec = read(stage / 'binding.json')
        if stage.name != digest(spec) or sha(stage / 'predictions.json') != published['prediction_sha256']:
            raise ValueError('The shared predictions differ from the original replay')
        if (any(sha(ROOT / path) != h for path, h in spec['source_versions'].items())
                or sha(common.airline.BENCHMARK) != spec['tariff_reference_sha256']):
            raise ValueError('The applicable compiled public rules must match the archived replay')
        return published, spec, read(stage / 'predictions.json')
    raise FileNotFoundError('Expected the verified B8 shared native replay')


class CombinedActor:
    def __init__(self, revised, originals, replay, cohort):
        self.revised = revised
        self.originals = originals
        self.replay = replay
        routes = common.airline.public_geography()
        self.rules = {s['key']: common.compile_source(s, routes) for s in cohort if s['dataset'] != DATASET}

    @lru_cache(maxsize=None)
    def load(self, key, arm, phase):
        folder, seal, score = (self.revised if phase == 'revised' else self.originals)[arm]
        saved = read(folder / 'predictions' / (digest(key) + '.json'))
        if (digest(saved) != seal['predictions_sha256'][key]
                or saved['library_sha256'] != score['libraries'][saved['dataset']]):
            raise ValueError('A B8 prediction does not bind the exact archived library')
        return saved

    def __call__(self, source, library, purpose):
        if purpose != 'skill_dev' or source['project_split'] != 'dev' or library['batch'] != 8:
            raise ValueError('The combined revised route is restricted to the original B8 DEV cohort')
        key, dataset, arm = source['key'], source['dataset'], library['arm']
        phase = 'revised' if dataset == DATASET else 'original'
        original = self.load(key, arm, phase)
        if (original['public_source_sha256'] != digest(source)
                or original['library_sha256'] != library[f'{phase}_snapshot_sha256']):
            raise ValueError('The revised formal actor must bind its original source and library')
        strict = original['result']
        if dataset == DATASET:
            return strict
        rules = self.rules[key]
        calculated = common.apply_compiled(source, strict['native'], rules)
        if calculated != self.replay[arm][key]:
            raise ValueError('A shared native output differs from the verified B8 replay')
        changed = sorted(task for task, pair in calculated.items() if pair['original'] != pair['common'])
        revised = dict(strict['native'])
        for task in changed:
            output = calculated[task]['common']
            revised[task] = {**revised[task], **output, 'handled': output['answer'] is not None}
        return {'native': revised, 'fallback_executed': False, 'revision5': {
            'route': 'same_information_public_rules',
            'original_prediction_sha256': digest(original),
            'public_rule_checks': sorted(rules),
            'changed_native_outputs': changed,
            'mechanism_activated': False}}

    def verify_saved(self, source, library, purpose, result):
        if self(source, library, purpose) != result:
            raise ValueError('Saved predictions must reproduce their bound source and rule')


def run():
    ledger = diversity_formal.ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Reconcile active paid requests before local formal DEV')
    revised_root = ROOT / read(diversity_formal.CURRENT)['artifact_root']
    revision = verify(read(revised_root / 'terminal.json'), 'terminal_sha256')
    revised_binding = read(revised_root / 'binding.json')
    if revision['binding_sha256'] != digest(revised_binding) or revision['TEST_opened']:
        raise ValueError('Complete the isolated Diversity DEV integration first')
    cohort, originals, study, original_terminal = common.archive()
    common_replay, replay_spec, bank = evidence_bank()
    if (replay_spec['original_B8_DEV_terminal_sha256'] != original_terminal
            or replay_spec['public_sources_sha256'] != digest(cohort)
            or replay_spec['original_cells'] != {arm: value[2]['cell_sha256'] for arm, value in originals.items()}):
        raise ValueError('The shared native rules must use the same original B8 sources and arms')
    revised = {}
    for arm in ConvergenceEvaluation.arms:
        folder = revised_root / 'dev' / 'B8' / arm
        seal = verify(read(folder / 'prediction_seal.json'), 'prediction_seal_sha256')
        scores = verify(read(folder / 'scores.json'), 'cell_sha256')
        if (scores['cell_sha256'] != revision['DEV_cells'][f'B8/{arm}']
                or scores['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(read(folder / 'task.json'))):
            raise ValueError('Expected the exact revised Diversity B8 predictions')
        revised[arm] = folder, seal, scores
    spec = {'study': 'revision5_integrated_five_library_B8_DEV', 'revision': 5,
            'Diversity_terminal_sha256': revision['terminal_sha256'],
            'shared_B8_DEV_predictions_sha256': common_replay['prediction_sha256'],
            'source_sha256': sha(ROOT / 'experiments/convergence_revision5_formal_native.py'),
            'DEV_public_sha256': study['DEV_public_sha256'], 'TEST_identities_sha256': study['TEST_identities_sha256'],
            'enforce_physical_actor_audit': True, 'new_model_calls': 0, 'TEST_content_or_labels_used': False}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    CURRENT.write_text(json.dumps({'status': 'running_LOCAL_no_requests', 'artifact_root': str(out.relative_to(ROOT)),
                                  'binding_sha256': digest(spec)}, indent=2) + '\n')
    actor = CombinedActor(revised, originals, bank, cohort)
    datasets = {s['key']: s['dataset'] for s in cohort}
    identities = read(ROOT / read(DEV_B0)['artifact_root'] / 'sealed_TEST_identity_metadata_only.json')

    @lru_cache(maxsize=None)
    def labels(path):
        if sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('Expected the original native DEV grades')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or seal['predictions_sha256'].keys() != datasets.keys():
            raise ValueError('Cannot grade outside the sealed DEV cohort')
        return labels(study['grading_paths'][datasets[key]])[key]

    evaluator = ConvergenceEvaluation(out, cohort, identities, binding=spec, grade_provider=grade,
                                      load_test=diversity_formal.no_test)
    result = {}
    native_bank = {}
    for arm in evaluator.arms:
        _, _, left = originals[arm]
        _, _, right = revised[arm]
        original_snapshot, = set(left['libraries'].values())
        revised_snapshot, = set(right['libraries'].values())
        library = sealed({'arm': arm, 'batch': 8, 'binding_sha256': digest(spec),
                          'original_snapshot_sha256': original_snapshot,
                          'revised_snapshot_sha256': revised_snapshot}, 'snapshot_sha256')
        immutable_json(out / 'libraries' / f'{arm}.json', library)
        report = evaluator.evaluate('dev', arm, 8, dict.fromkeys(evaluator.datasets, library), actor)
        if ([r for r in report['source_scores'] if r['dataset'] == DATASET]
                != [r for r in right['source_scores'] if r['dataset'] == DATASET]):
            raise ValueError('The other libraries may not alter the settled Diversity results')
        per_dataset = {}
        native_bank[arm] = {}
        for dataset in sorted(evaluator.datasets):
            counts = Counter()
            for key in (s['key'] for s in cohort if s['dataset'] == dataset):
                path = evaluator.cell_path('dev', arm, 8) / 'predictions' / (digest(key) + '.json')
                saved = read(path)['result']
                native_bank[arm][key] = saved['native']
                route = saved['revision5']
                counts['public_rule_checked_mothers'] += bool(route.get('public_rule_checks'))
                counts['public_rule_checked_views'] += len(route.get('public_rule_checks', []))
                counts['public_rule_changed_mothers'] += bool(route.get('changed_native_outputs'))
                counts['changed_native_views'] += len(route.get('changed_native_outputs', []))
                counts['literal_reader_mothers'] += route['route'] == 'verified_public_literal_v1'
                counts['M1_activated_mothers'] += route['mechanism_activated']
            per_dataset[dataset] = dict(counts)
        result[arm] = {'cell_sha256': report['cell_sha256'], 'activation': per_dataset,
                       'native_before': _native_metrics(left['source_scores'], labels, study['grading_paths']),
                       'native_after': _native_metrics(report['source_scores'], labels, study['grading_paths'])}
        print(f'completed integrated B8 DEV {arm}', flush=True)
    mismatches = {}
    for name, (candidate, fixed) in common.CONTRASTS.items():
        mismatches[name] = dict.fromkeys(sorted(evaluator.datasets), 0)
        for key, dataset in datasets.items():
            a, b = native_bank[candidate][key], native_bank[fixed][key]
            mismatches[name][dataset] += sum(
                (a[task]['answer'], a[task]['evidence_sentence_ids']) !=
                (b[task]['answer'], b[task]['evidence_sentence_ids']) for task in a)
    if diversity_formal.ledger_status() != ledger:
        raise ValueError('The ledger changed during the local experiment')
    summary = sealed({'status': 'completed_revised_five_library_B8_DEV',
                      'binding_sha256': digest(spec), 'Diversity_terminal_sha256': revision['terminal_sha256'],
                      'per_arm': result, 'native_output_disagreements': mismatches, 'TEST_opened': False,
                      'new_model_calls': 0, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', summary)
    CURRENT.write_text(json.dumps({'status': summary['status'], 'artifact_root': str(out.relative_to(ROOT)),
                                  'terminal_sha256': summary['terminal_sha256']}, indent=2) + '\n')
    print(out, flush=True)


if __name__ == '__main__':
    run()
