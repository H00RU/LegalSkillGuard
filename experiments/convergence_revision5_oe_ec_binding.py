"""Replay source-exact OpenExempt EC key binding on settled TRAIN and B8 DEV."""

import json
import sqlite3
from collections import Counter
from statistics import mean

from experiments import convergence_revision5_common_native_dev as common
from experiments import convergence_revision5_oe_category_scope as category
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_formal_native import CURRENT as INTEGRATED
from legal_skill_guard.paired_interfaces import convergence_ec_inventory as binding
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_oe_ec_binding_20261119'
POINTER = HANDOFF / 'revision5_oe_ec_binding_current.json'
DATASET = 'OpenExempt'
TASK = 'EC'
ARMS = ('common_teacher_skill_learning', 'strongest_matched_external_baseline')


def view_for(source):
    view, = (v for v in source['views'] if v['id'] == TASK)
    return view


def variants(source, original):
    view = view_for(source)
    rule = common.exemption_rules(source)[TASK]

    def run(answer):
        return rule({'answer': answer, 'evidence_sentence_ids': []})['answer']

    base = run(original)
    if not isinstance(original, dict):
        return {'shared': base, 'normalize_final': base, 'normalize_before_policy': base}
    entered = binding.bind_classification(view, original)
    return {'shared': base, 'normalize_final': binding.bind_classification(view, base),
            'normalize_before_policy': run(entered)}


def train_bank(study, paths):
    checkpoint = ROOT / read(category.BOOTSTRAP)['artifact_root']
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    cohort, predictions = {}, {arm: {} for arm in ARMS}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('SELECT status, count(*) FROM calls GROUP BY status'))
        if counts.get('reserved'):
            raise ValueError('Reconcile existing paid requests before the local replay')
        physical = set()
        for batch, mothers in enumerate(batches, 1):
            stage = category.FIRST if batch == 1 else category.observe_pointer(batch)
            _, spec, end = category.bound_stage(stage)
            grade = spec['native_grade_paths'][DATASET]
            paths[grade] = spec['native_grade_sha256'][grade]
            for arm in ARMS:
                receipt = journal._observations(arm, batch)
                if receipt['train_observation_sha256'] != end['observation_receipts'][arm]:
                    raise ValueError('The original TRAIN observation changed')
                for source in (s for s in mothers if s['dataset'] == DATASET):
                    key = source['key']
                    cohort[key] = source
                    saved = read(journal.directory(arm, batch) / 'predictions' / (digest(key) + '.json'))
                    if digest(saved) != receipt['predictions'][key] or source['project_split'] != 'train':
                        raise ValueError('The replay must use the original measured TRAIN reads')
                    answer = category.ec_read(db, source, saved, physical, 'train')
                    predictions[arm][key] = variants(source, answer)
    if len(cohort) != 32 or len(paths) != 1:
        raise ValueError('Expected the complete original 32-source EC TRAIN roster')
    return cohort, predictions, len(physical), counts


def archive_dev(cohort, original_arms):
    current = read(INTEGRATED)
    root = ROOT / current['artifact_root']
    end = verify(read(root / 'terminal.json'), 'terminal_sha256')
    if end['terminal_sha256'] != current['terminal_sha256'] or end['TEST_opened']:
        raise ValueError('The replay must use the settled revised integrated DEV')
    bank = {}
    for arm, (old_root, old_seal, old_score) in original_arms.items():
        folder = root / 'dev' / 'B8' / arm
        scores = verify(read(folder / 'scores.json'), 'cell_sha256')
        seal = verify(read(folder / 'prediction_seal.json'), 'prediction_seal_sha256')
        if (scores['cell_sha256'] != end['per_arm'][arm]['cell_sha256']
                or scores['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(read(folder / 'task.json'))):
            raise ValueError('The integrated B8 evaluator seal changed')
        bank[arm] = {}
        for key, source in cohort.items():
            filename = digest(key) + '.json'
            old = read(old_root / 'predictions' / filename)
            settled = read(folder / 'predictions' / filename)
            if (digest(old) != old_seal['predictions_sha256'][key]
                    or old['library_sha256'] != old_score['libraries'][DATASET]
                    or digest(settled) != seal['predictions_sha256'][key]
                    or settled['library_sha256'] != scores['libraries'][DATASET]
                    or old['public_source_sha256'] != digest(source) or settled['public_source_sha256'] != digest(source)
                    or source['project_split'] != 'dev'):
                raise ValueError('The original and integrated DEV inputs must match')
            pair = variants(source, old['result']['native'][TASK]['answer'])
            if pair['shared'] != settled['result']['native'][TASK]['answer']:
                raise ValueError('Unchanged shared condition must reproduce the integrated EC answers')
            bank[arm][key] = pair
    return bank, end['terminal_sha256']


def summarize(cohort, bank, grade):
    def measure(condition, predictions):
        return [{'source': k, 'view': TASK,
                 'grade': grade_view(DATASET, view_for(s), grade[k][TASK], predictions[k][condition])['grade']}
                for k, s in sorted(cohort.items())]

    scores = {}
    for arm, predictions in bank.items():
        base = measure('shared', predictions)
        summary = {}
        for mode in ('normalize_final', 'normalize_before_policy'):
            other = measure(mode, predictions)
            changes = Counter((b['grade'] > a['grade']) - (b['grade'] < a['grade'])
                              for a, b in zip(base, other, strict=True))
            summary[mode] = {'f1': mean(r['grade'] for r in other),
                             'answers_changed': sum(p['shared'] != p[mode] for p in predictions.values()),
                             'asset_key_delta': sum(len(p['shared'] or {}) - len(p[mode] or {})
                                                    for p in predictions.values()),
                             'improved_mothers': changes[1], 'regressed_mothers': changes[-1],
                             'effect': paired_source_effect(base, other)}
        scores[arm] = {'shared_f1': mean(r['grade'] for r in base), **summary}
    return scores


def run():
    cohort, original_arms, study, original_terminal = common.archive()
    dev = {s['key']: s for s in cohort if s['dataset'] == DATASET}
    grade_paths = {}
    train, train_records, physical, ledger = train_bank(study, grade_paths)
    dev_records, parent = archive_dev(dev, original_arms)
    dev_path = study['grading_paths'][DATASET]
    train_path, = grade_paths
    grade_paths[dev_path] = study['grading_file_sha256'][dev_path]
    files = (ROOT / 'experiments/convergence_revision5_oe_ec_binding.py', binding.__file__,
             common.__file__, category.__file__)
    spec = {'study': 'revision5_EC_asset_identity', 'original_DEV_terminal_sha256': original_terminal,
            'revised_DEV_terminal_sha256': parent, 'TRAIN_public_sha256': digest(train),
            'DEV_public_sha256': digest(dev), 'grade_hashes': grade_paths,
            'source_sha256': {str(path.relative_to(ROOT)): sha(path) for path in map(ROOT.joinpath, files)}}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    predictions_hash = immutable_json(out / 'predictions.json', {'train': train_records, 'dev': dev_records})
    for path, h in grade_paths.items():
        if sha(ROOT / path) != h:
            raise ValueError('Original EC grading has changed')
    if 'train' not in train_path.split('/') or 'dev' not in dev_path.split('/'):
        raise ValueError('Only the original TRAIN and DEV grade files can be used')
    scores = {partition: summarize(sources, bank, read(ROOT / path))
              for partition, sources, bank, path in (('train', train, train_records, train_path),
                                                     ('dev', dev, dev_records, dev_path))}
    result = sealed({'status': 'settled_revised_EC_source_key_replay', 'binding_sha256': digest(spec),
                     'source_sha256': spec['source_sha256'], 'predictions_sha256': predictions_hash, 'scores': scores,
                     'TRAIN_physical_reads_verified': physical, 'DEV_mothers': len(dev),
                     'new_model_calls': 0, 'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'status': result['status'],
                                   'terminal_sha256': result['terminal_sha256']}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
