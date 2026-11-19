"""Integrate the shared source repair into B8 DEV and check the saved TRAIN gates."""

from copy import deepcopy
from math import fsum
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_cni_disposition_roles as roles
from experiments import convergence_revision5_formal_native as formal
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, _mean, pointer
from experiments.convergence_pilot_b0 import LEDGER
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal

events = roles.events
DATASET = events.legacy.DATASET
TASK = roles.TASK


def revised_native(cohort, predictions):
    patched = deepcopy(predictions)
    for source in cohort:
        view = next(v for v in source['views'] if v['id'] == TASK)
        prior = events.source_proof(view)
        proof = roles.revised_proof(view, prior, use_performative=False)
        if prior['answer'] is None and proof['answer'] == events.N:
            native = patched[source['key']]['native'][TASK]
            native.update(answer=events.N, evidence_sentence_ids=[], handled=True)
    return patched


def analyze():
    checkpoint, study, roster = events.archive.archive_context()
    journal = TrainingJournal(checkpoint, study, roster)
    batch = 8
    cohort = [s for s in roster[batch - 1] if s['dataset'] == DATASET]
    stage = events.ROOT / events.read(pointer(batch))['artifact_root']
    binding = events.read(stage / 'binding.json')
    terminal = events.read(stage / 'terminal.json')
    decisions = events.read(stage / 'matched_decisions.json')
    if (binding['batch'] != batch or stage.name != events.digest(binding)
            or terminal['TEST_opened'] or events.digest(decisions) != terminal['matched_decisions_sha256']
            or any(events.sha(stage / 'source_snapshot' / f) != h for f, h in binding['source_sha256'].items())):
        raise ValueError('Use the original TRAIN-only B8 candidates and snapshot')
    _, _, grade, _ = events.archive.collect(checkpoint, study, roster, 'train')
    decisions_out, calls = {}, set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for arm in (ORDINARY, EXTERNAL_ARM):
            decision = decisions['teacher'][arm][DATASET]
            candidate = events.read(stage / 'candidates' / arm / DATASET / 'measurements.json')['predictions']
            if events.digest(candidate) != decision['predictions_sha256']:
                raise ValueError('Candidate predictions changed')
            incumbent = {}
            observations = journal._observations(arm, batch)
            for source in cohort:
                key = source['key']
                cell = events.read(journal.directory(arm, batch) / 'predictions' / (events.digest(key) + '.json'))
                if events.digest(cell) != observations['predictions'][key]:
                    raise ValueError('Incumbent predictions changed')
                incumbent[key] = cell['result']
                calls.update(verify_prediction(db, key, p[key]) for p in (candidate, incumbent))

            def scores(predictions):
                return _mean(DATASET, cohort, predictions, lambda _: labels)

            def gain(after, before):
                return fsum(after[k] - before[k] for k in before) / len(before)

            labels = events.read(grade)
            archived = gain(scores(candidate), scores(incumbent))
            if archived != decision['native_utility_delta']:
                raise ValueError('The original native utility must reproduce')
            repaired = gain(scores(revised_native(cohort, candidate)), scores(revised_native(cohort, incumbent)))
            decisions_out[arm] = {
                'b8_TRAIN_mothers': len(cohort), 'archived_candidate_utility_delta': archived,
                'both_programs_role_scoped_candidate_utility_delta': repaired,
                'original_selection': decision['selected'],
                'repaired_current_batch_passes_gain_gate': repaired > 0,
            }
    return {
        'fit_terminal_sha256': events.sha(stage / 'terminal.json'),
        'physical_responses_verified': len(calls),
        'branches': decisions_out,
        'new_model_requests': 0,
        'source_sha256': events.sha(Path(__file__)),
    }


def integrate_dev(out):
    composed = events.composed
    stage = events.ROOT / events.read(composed.POINTER)['artifact_root']
    baseline = events.verify(events.read(stage / 'terminal.json'), 'terminal_sha256')
    parent = events.ROOT / events.read(roles.POINTER)['artifact_root']
    revision = events.verify(events.read(parent / 'terminal.json'), 'terminal_sha256')
    formal_root = events.ROOT / events.read(formal.CURRENT)['artifact_root']
    formal_terminal = events.verify(events.read(formal_root / 'terminal.json'), 'terminal_sha256')
    composed_binding = events.read(stage / 'binding.json')
    paths = stage / 'dev_predictions.json', parent / 'dev_predictions.json'
    if (any(x['TEST_opened'] for x in (baseline, revision, formal_terminal))
            or baseline['binding_sha256'] != events.digest(composed_binding)
            or composed_binding['parent_B8_terminal_sha256'] != formal_terminal['terminal_sha256']
            or any(events.sha(p) != x['predictions_sha256']['dev']
                   for p, x in zip(paths, (baseline, revision), strict=True))):
        raise ValueError('The integrated prediction inputs must be sealed DEV')
    before, amendment = (events.read(p) for p in paths)
    result = {}
    for arm, cells in before.items():
        result[arm] = {}
        for key, views in cells.items():
            replacement = amendment[arm][key]['role_scope']
            result[arm][key] = {**views, TASK: replacement}
    prediction_hash = events.immutable_json(out / 'formal_cni_dev_predictions.json', result)
    cohort, _, grade, _ = events.archive.collect(*events.archive.archive_context(), 'dev')
    if 'dev' not in grade.parts or events.sha(grade) != events.read(stage / 'binding.json')['DEV_grade_sha256']:
        raise ValueError('Use the original fixed B8 native labels')
    labels = events.read(grade)
    score = {arm: composed.score(cohort, cells, result[arm], labels) for arm, cells in before.items()}
    contrasts = [
        (ORDINARY, 'method_one_only'),
        ('method_two_only', 'both'),
        (ORDINARY, 'method_two_only'),
        ('method_one_only', 'both'),
    ]
    return {
        'predictions_sha256': prediction_hash,
        'composition_parent_terminal_sha256': baseline['terminal_sha256'],
        'reused_formal_B8_DEV_terminal_sha256': formal_terminal['terminal_sha256'],
        'role_scope_terminal_sha256': revision['terminal_sha256'],
        'updated_slot': TASK,
        'DEV_mothers': len(cohort),
        'CNI_views_per_arm': sum(len(s['views']) for s in cohort.values()),
        'other_library_views_reused_per_arm': 112,
        'proposal': 'role_scope',
        'exploratory_performative_enabled': False,
        'native_output_differences_by_factorial_contrast': {
            f'{a}__{b}': sum(result[a][key][task] != result[b][key][task]
                              for key in cohort for task in result[a][key]) for a, b in contrasts},
        'arms': score,
    }


if __name__ == '__main__':
    import json

    print(json.dumps(analyze(), sort_keys=True))
