"""The registered Full-B8 foreign-skill-on/off contrast; no retraining."""
from datetime import datetime, timezone
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import Library
from reports.legal_skill_evolution_run_20261111.native_statistics import (
    DATASETS, summarize, paired_source_bootstrap)
from reports.legal_skill_evolution_run_20261111.skill_lineage import (
    accepted_lineage, foreign_off, actual_use, load, sha)


def prepare_masks(formal, destination, library, source_datasets):
    """Called by the B8-gated freeze, before any frozen model prediction."""
    formal, destination = Path(formal), Path(destination)
    lineage = accepted_lineage(formal, 'Full', 8, source_datasets)
    if lineage['library_hash'] != library.hash:raise ValueError('Transfer ancestry is not the frozen Full B8')
    immutable_json(destination / 'Full_accepted_lineage.json', lineage)
    masks = {}
    paths = [destination / 'Full_accepted_lineage.json']
    for dataset in DATASETS:
        masked, receipt = foreign_off(library, lineage, dataset)
        path = destination / 'libraries' / ('Full_target_only_' + dataset + '.json')
        if path.exists() and Library.load(path).hash != masked.hash:
            raise ValueError('An already prepared fixed transfer mask changed')
        masked.save(path)
        paths.append(path)
        masks[dataset] = receipt
    immutable_json(destination / 'registered_transfer_masks.json', masks)
    paths.append(destination / 'registered_transfer_masks.json')
    return paths, {formal / relative: expected for relative, expected in lineage['source_file_sha256'].items()}


def run():
    # The frozen initializer verifies every bound source/data hash and exposes
    # no teacher. The main matrix must finish before this registered contrast.
    from experiments.legal_skill_evolution_frozen import FrozenStudy, FOLDER
    if not (FOLDER / 'TEST_completed.json').exists():
        raise ValueError('Complete the already frozen seven-system TEST matrix before transfer masks')
    runner = FrozenStudy()
    complete = load(FOLDER / 'TEST_completed.json')
    if complete['freeze_artifact_sha256'] != runner.profile['freeze']['artifact_sha256']:
        raise ValueError('TEST completion belongs to another freeze')
    for relative, expected in complete['result_file_sha256'].items():
        if sha(FOLDER / relative) != expected:raise ValueError('A completed TEST result changed')
    destination = FOLDER / 'transfer'
    done = destination / 'completed.json'
    if done.exists():
        receipt = load(done)
        if receipt['freeze_artifact_sha256'] != runner.profile['freeze']['artifact_sha256']:
            raise ValueError('Transfer completion belongs to another freeze')
        for relative, expected in receipt['result_sha256'].items():
            if sha(destination / relative) != expected:raise ValueError('A completed transfer result changed')
        print(json.dumps({'frozen_transfer_already_complete': True, 'new_model_calls': 0}), flush=True)
        return
    lineage = load(FOLDER / 'Full_accepted_lineage.json')
    full = runner.libraries['Full']
    masks = load(FOLDER / 'registered_transfer_masks.json')
    all_on, all_off, usage, differences = [], [], [], []
    for dataset in DATASETS:
        masked = Library.load(FOLDER / 'libraries' / ('Full_target_only_' + dataset + '.json'))
        if masked.hash != masks[dataset]['masked_library_hash']:
            raise ValueError('The predeclared transfer mask changed')
        for source in runner.records.values():
            if source['dataset'] != dataset:continue
            on_path = FOLDER / 'predictions' / 'Full'
            from legal_skill_guard.skill_evolution.objects import digest
            on = load(on_path / (digest(source['key']) + '.json'))
            off = runner.parent(source, masked, 'Full_foreign_off/' + dataset)
            all_on.append(on);all_off.append(off)
            usage.extend(actual_use(on, full, lineage))
            difference = (on['native_grade'] - off['native_grade']
                          if on['native_grade'] is not None and off['native_grade'] is not None else None)
            differences.append({'source': source['key'], 'dataset': dataset,
                'foreign_on_native_grade': on['native_grade'], 'foreign_off_native_grade': off['native_grade'],
                'paired_difference': difference,
                'result': 'unknown' if difference is None else 'beneficial' if difference > 0
                          else 'harmful' if difference < 0 else 'unchanged'})
            print(json.dumps({'stage': 'frozen_transfer', **differences[-1]}), flush=True)
    interval = paired_source_bootstrap(all_on, all_off)
    # This is the one registered transfer contrast, not one of the four primary
    # system contrasts; do not relabel its interval as a primary family test.
    interval.pop('four_contrast_Bonferroni_98_75_percent_interval')
    immutable_json(destination / 'actual_use.json', usage)
    immutable_json(destination / 'parent_differences.json', differences)
    immutable_json(destination / 'summary.json', {'Full_foreign_on': summarize(all_on),
        'Full_target_only': summarize(all_off), 'paired_source_uncertainty': interval,
        'parents': len(differences), 'actual_foreign_final_path_views': sum(bool(r['foreign_final_answer_skill_ids']) for r in usage),
        'fully_correct_foreign_core_views': sum(r['fully_correct_foreign_core'] for r in usage),
        'parent_outcomes': {name: sum(r['result'] == name for r in differences)
                            for name in ('beneficial', 'harmful', 'unchanged', 'unknown')},
        'fallback_correct_not_counted_as_core': True, 'teacher_used': False,
        'skill_updates': False, 'new_sources_or_seeds': False, 'masks_fixed_before_TEST_predictions': True,
        'interpretation': masks[DATASETS[0]]['interpretation']})
    with runner.ledger.transaction() as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('A physical request remains in flight')
        if db.execute("select 1 from calls where id like ? and role='teacher'", (runner.profile['run_id'] + ':%',)).fetchone():
            raise ValueError('Frozen evaluation accessed the teacher')
    immutable_json(done, {'completed_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_artifact_sha256': runner.profile['freeze']['artifact_sha256'],
        'result_sha256': {name: sha(destination / name) for name in (
            'actual_use.json', 'parent_differences.json', 'summary.json')},
        'teacher_calls': 0, 'library_updates': False, 'goal_complete': False})


if __name__ == '__main__':run()
