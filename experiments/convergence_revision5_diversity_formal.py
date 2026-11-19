"""Run the revised Diversity TRAIN prefix and the original five-arm DEV topology."""

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_curves import DEV_B0, FIRST_DEV, pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_m1_incumbent_audit import M1, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m1_quote_amount_control import HOME as TRAIN_LITERAL
from legal_skill_guard.paired_interfaces import diversity, diversity_claim_groups, diversity_literal as literal
from legal_skill_guard.paired_interfaces.convergence_actors import M1_ARMS
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


DATASET = literal.DATASET
HOME = BASE / 'revision5_diversity_formal_20261119'
CURRENT = HANDOFF / 'revision5_diversity_formal_current.json'
PAIRS = (('common_teacher_skill_learning', M1), ('method_two_only', 'both'))


def ledger_status():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        return dict(db.execute('SELECT status, count(*) FROM calls GROUP BY status'))


def dev_archives(checkpoint):
    stages = {0: checkpoint, 1: ROOT / read(FIRST_DEV)['artifact_root']}
    stages.update({batch: ROOT / read(pointer(batch))['artifact_root'] for batch in (2, 4, 8)})
    by_batch = {}
    for batch, stage in stages.items():
        terminal = read(stage / 'terminal.json')
        if terminal['TEST_content_opened' if batch == 0 else 'TEST_opened']:
            raise ValueError('Expected the original DEV-only terminal')
        hashes = terminal['B0_cells' if batch == 0 else 'cell_sha256']
        by_batch[batch] = {}
        for arm in ConvergenceEvaluation.arms:
            folder = checkpoint / 'dev' / f'B{batch}' / arm
            task = read(folder / 'task.json')
            seal = verify(read(folder / 'prediction_seal.json'), 'prediction_seal_sha256')
            scores = verify(read(folder / 'scores.json'), 'cell_sha256')
            if (seal['task_sha256'] != digest(task) or scores['cell_sha256'] != hashes[arm]
                    or scores['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                    or scores['partition'] != 'dev' or scores['arm'] != arm or scores['batch'] != batch):
                raise ValueError('An archived DEV result does not bind its original terminal')
            by_batch[batch][arm] = folder, seal, scores
    return by_batch


def literal_train(out, batches, journal, grade_path):
    observations = journal.library(M1, 8)['interface_library']['observations']
    _verify_reads(observations)
    old = {(row['source'], row['plan_version']): row for row in observations}
    provider = diversity_claim_groups.Provider()
    snapshots = {0: literal.snapshot(0, None, [], [])}
    labels = read(grade_path)
    if len(old) != len(observations) or len(old) != 96:
        raise ValueError('Expected the complete original four-candidate Diversity TRAIN bank')
    used = set()
    training = {}
    for batch, source_rows in enumerate(batches, 1):
        keys, candidates, forward = [], [], []
        for source in source_rows:
            if source['dataset'] != DATASET:
                continue
            key = source['key']
            task, = source['views']
            view, = provider.views(source)
            if len({literal.template(p) for p in view['plans']}) != 4:
                raise ValueError('Each Diversity TRAIN mother must offer all four distinct layouts')
            keys.append(key)
            fixed, _ = literal.choose(source, view, snapshots[batch - 1], learned=False)
            learned, selection = literal.choose(source, view, snapshots[batch - 1], learned=True)
            reference = diversity.reference_outputs(diversity.audit_source(task['public']['source_text']))
            rows = {}
            for plan in view['plans']:
                result = literal.measure(source, view, plan)
                version = plan['version']
                label = labels[key][task['id']]
                grade = grade_view(DATASET, task, label, result['outputs'][task['id']])['grade']
                faithful = (result['outputs'][task['id']] == reference['answer']
                            and all(result['diagnostics'][k] == reference[k]
                                    for k in ('parties_are_diverse', 'aic_is_met')))
                used.add((key, version))
                original = old[key, version]
                record = {'source': key, 'template': literal.template(plan), 'version': version,
                          'grounded_native': int(grade == 1 and faithful), 'native_grade': grade,
                          'whole_source_trace_agrees': faithful, 'coordinate_count': result['coordinate_count'],
                          'literal_read_sha256': result['literal_read_sha256'],
                          'original_observation_sha256': digest(original)}
                rows[version] = record
                candidates.append(record)
            forward.append({'source': key, 'selection': selection, 'fixed': rows[fixed['version']],
                            'selected': rows[learned['version']]})
        if len(keys) != 3:
            raise ValueError('Preserve the original three Diversity mothers in each TRAIN batch')
        snapshots[batch] = literal.snapshot(batch, snapshots[batch - 1], keys, candidates)
        training[f'B{batch}'] = forward
    if used != set(old) or set(snapshots[8]['visible_TRAIN']) != set(labels):
        raise ValueError('The revised TRAIN bank must bind precisely the original observations and grades')
    for batch, snapshot in snapshots.items():
        immutable_json(out / 'train' / f'B{batch}.json', snapshot)
    immutable_json(out / 'train' / 'forward.json', training)
    return snapshots, training


class RevisedActor:
    """Audit deterministic Diversity reads and reuse predictions in unaffected cells."""

    def __init__(self, archives, snapshots):
        self.archives = archives
        self.snapshots = snapshots
        self.provider = diversity_claim_groups.Provider()

    @lru_cache(maxsize=None)
    def archived(self, key, arm, batch):
        folder, seal, _ = self.archives[batch][arm]
        value = read(folder / 'predictions' / (digest(key) + '.json'))
        if digest(value) != seal['predictions_sha256'][key]:
            raise ValueError('An original prediction lost its seal')
        return value

    def __call__(self, source, library, purpose):
        if purpose != 'skill_dev' or source['project_split'] != 'dev':
            raise ValueError('The revised actor can only access the original development sources')
        arm, batch, dataset = library['arm'], library['batch'], source['dataset']
        snapshot = self.snapshots[batch]
        if snapshot['snapshot_sha256'] != library['diversity_snapshot_sha256']:
            raise ValueError('The literal route must use its own complete chronological TRAIN prefix')
        original = self.archived(source['key'], arm, batch)
        if (original['library_sha256'] != library['original_snapshot_sha256']
                or original['public_source_sha256'] != digest(source)):
            raise ValueError('Original and revised DEV must use the same mother and original arm state')
        binding = {'original_prediction_sha256': digest(original), 'mechanism_activated': False}
        if batch == 0 or dataset != DATASET:
            return {**original['result'], 'revision5': {**binding, 'route': 'original_DEV_reuse'}}
        view, = self.provider.views(source)
        plan, selection = literal.choose(source, view, snapshot, learned=arm in M1_ARMS)
        result = literal.measure(source, view, plan)
        native = {key: {'handled': value is not None, 'answer': value, 'evidence_sentence_ids': []}
                  for key, value in result['outputs'].items()}
        return {'native': native, 'fallback_executed': False, 'revision5': {
            **binding, 'route': result['channel'], 'mechanism_activated': not plan['is_correct_fixed_raw_control'],
            'selection': selection, 'reading': result}}

    def verify_saved(self, source, library, purpose, result):
        if result != self(source, library, purpose):
            raise ValueError('A revised DEV result lost its exact proof or archived prediction trace')


def metrics(scores, labels):
    rows = [row for row in scores['source_scores'] if row['dataset'] == DATASET]
    totals, correct = Counter(), Counter()
    for row in rows:
        label = labels[row['source']]['native']['answer']
        totals[label] += 1
        correct[label] += int(row['grade'] == 1)
    return {'correct': sum(correct.values()), 'mothers': sum(totals.values()),
            'correct_by_class': dict(correct), 'mothers_by_class': dict(totals),
            'balanced_accuracy': sum(correct[k] / totals[k] for k in totals) / len(totals)}


def compare_by_dataset(before, after, routes):
    report = {}
    for dataset in sorted(ConvergenceEvaluation.datasets):
        old = [r for r in before['source_scores'] if r['dataset'] == dataset]
        new = [r for r in after['source_scores'] if r['dataset'] == dataset]
        if dataset != DATASET and old != new:
            raise ValueError('The Diversity revision may not change other native predictions or metrics')
        selected = [routes[key] for key in {r['source'] for r in new}]
        report[dataset] = {'native_views': len(old), 'mothers': len(selected),
                           'old_native': before['datasets'][dataset], 'new_native': after['datasets'][dataset],
                           'native_rows_changed': sum(a != b for a, b in zip(old, new, strict=True)),
                           'literal_route': sum('reading' in row for row in selected),
                           'M1_activated': sum(row['mechanism_activated'] for row in selected),
                           'coordinates': sum(row.get('reading', {}).get('coordinate_count', 0) for row in selected)}
    return report


def no_test():
    raise ValueError('This entrypoint is a TRAIN/DEV revision with no TEST loader')


def run():
    ledger = ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Check the outstanding request before revising an experimental binding')
    b8 = ROOT / read(pointer(8))['artifact_root']
    b8_binding = read(b8 / 'binding.json')
    checkpoint = ROOT / b8_binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if digest(study) != b8_binding['checkpoint_binding_sha256']:
        raise ValueError('A revised route must start from the exact original TRAIN checkpoint')
    train_seal = verify(read(checkpoint / 'training_B8.json'), 'training_seal_sha256')
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    archives = dev_archives(checkpoint)
    b0 = ROOT / read(DEV_B0)['artifact_root']
    cohort = read(b0 / 'public_DEV_sources.json')
    test_identities = read(b0 / 'sealed_TEST_identity_metadata_only.json')
    train_binding = read(ROOT / read(observe_pointer(8))['artifact_root'] / 'binding.json')
    grade_name = train_binding['native_grade_paths'][DATASET]
    train_grade = ROOT / grade_name
    prior_control = TRAIN_LITERAL / 'literal_amount_control.json'
    if not (sha(train_grade) == train_binding['native_grade_sha256'][grade_name]
            == read(prior_control)['original_train_grade_sha256']):
        raise ValueError('Expected the original Diversity TRAIN grades from the verified literal control')
    code = (*Path(__file__).parent.glob('convergence_revision5_diversity_formal.py'),
            *(ROOT / path for path in study['source_sha256']),
            Path(literal.__file__))
    spec = {'study': 'revision5_diversity_literal_development', 'revision': 5,
            'original_TRAIN_B8_sha256': train_seal['training_seal_sha256'],
            'original_DEV_cells': {f'B{batch}/{arm}': archive[2]['cell_sha256']
                                   for batch, arms in archives.items() for arm, archive in arms.items()},
            'TRAIN_literal_control_sha256': sha(prior_control), 'TRAIN_grade_sha256': sha(train_grade),
            'DEV_public_sha256': study['DEV_public_sha256'], 'TEST_identities_sha256': study['TEST_identities_sha256'],
            'enforce_physical_actor_audit': True, 'no_TEST_content_or_grading': True,
            'scope': 'Diversity shared literal reader and prefix-only interface selection, with original DEV reuse elsewhere',
            'source_sha256': {str(path.resolve().relative_to(ROOT)): sha(path) for path in code}}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    CURRENT.write_text(json.dumps({'status': 'running_LOCAL_no_requests', 'artifact_root': str(out.relative_to(ROOT)),
                                  'binding_sha256': digest(spec)}, indent=2) + '\n')
    snapshots, train = literal_train(out, batches, journal, train_grade)
    actor = RevisedActor(archives, snapshots)
    datasets_by_key = {source['key']: source['dataset'] for source in cohort}

    @lru_cache(maxsize=None)
    def labels(dataset):
        path = study['grading_paths'][dataset]
        if sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('An original DEV grade file changed')
        return read(ROOT / path)

    def grade(partition, key, seal):
        if partition != 'dev' or seal['predictions_sha256'].keys() != datasets_by_key.keys():
            raise ValueError('Seal the entire fixed DEV cell before grading')
        return labels(datasets_by_key[key])[key]

    evaluator = ConvergenceEvaluation(out, cohort, test_identities, binding=spec, grade_provider=grade, load_test=no_test)
    per_batch, comparisons, cells = {}, {}, {}
    for batch in evaluator.curves:
        reports = {}
        per_batch[f'B{batch}'] = {}
        for arm in evaluator.arms:
            original = journal.library(arm, batch)
            if batch and (journal._completed_batch(arm, batch)['completed_batch_sha256']
                          != train_seal['complete_train_histories'][arm][batch - 1]):
                raise ValueError('Invalid original TRAIN checkpoint')
            revised = sealed({'arm': arm, 'batch': batch, 'original_snapshot_sha256': original['snapshot_sha256'],
                              'diversity_snapshot_sha256': snapshots[batch]['snapshot_sha256'],
                              'revision_binding_sha256': digest(spec)}, 'snapshot_sha256')
            immutable_json(out / 'libraries' / f'B{batch}' / f'{arm}.json', revised)
            libraries = dict.fromkeys(evaluator.datasets, revised)
            report = evaluator.evaluate('dev', arm, batch, libraries, actor)
            reports[arm] = report
            cells[f'B{batch}/{arm}'] = report['cell_sha256']
            before = archives[batch][arm][2]
            folder = evaluator.cell_path('dev', arm, batch)
            routes = {key: read(folder / 'predictions' / (digest(key) + '.json'))['result']['revision5']
                      for key in datasets_by_key}
            per_batch[f'B{batch}'][arm] = {
                'datasets': compare_by_dataset(before, report, routes),
                'Diversity_exact_and_balanced': {'original': metrics(before, labels(DATASET)),
                                                 'revised': metrics(report, labels(DATASET))}}
        diversity_rows = {arm: [r for r in report['source_scores'] if r['dataset'] == DATASET]
                          for arm, report in reports.items()}
        strata = {r['source']: labels(DATASET)[r['source']]['native']['answer'] for r in diversity_rows[M1]}
        comparisons[f'B{batch}'] = {
            a + '->' + b: {'exact': paired_source_effect(diversity_rows[a], diversity_rows[b]),
                           'balanced': paired_source_effect(diversity_rows[a], diversity_rows[b], strata=strata)}
            for a, b in PAIRS}
        print(f'completed revised B{batch} DEV', flush=True)
    revised_train = [row for batch in train.values() for row in batch]
    all_candidates = snapshots[8]['candidate_records']
    if ledger_status() != ledger:
        raise ValueError('Ledger changed during a local-only comparison. Reconcile before issuing a receipt.')
    result = sealed({'status': 'completed_Diversity_revised_formal_DEV', 'binding_sha256': digest(spec),
                     'original_TRAIN_mothers': train_seal['unique_TRAIN_mothers_per_arm'],
                     'Diversity_TRAIN': {'mothers': len(revised_train), 'candidates': len(all_candidates),
                         'grounded_native_candidates': sum(r['grounded_native'] for r in all_candidates),
                         **{k: {'correct': sum(r[k]['grounded_native'] for r in revised_train),
                                'coordinates': sum(r[k]['coordinate_count'] for r in revised_train)}
                            for k in ('fixed', 'selected')}},
                     'DEV_cells': cells, 'checkpoints': per_batch, 'Diversity_same_information_M1': comparisons,
                     'new_model_calls': 0, 'ledger': ledger, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    CURRENT.write_text(json.dumps({'status': result['status'], 'artifact_root': str(out.relative_to(ROOT)),
                                  'terminal_sha256': result['terminal_sha256']}, indent=2) + '\n')
    print(out, flush=True)


if __name__ == '__main__':
    run()
