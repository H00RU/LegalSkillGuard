"""Attribute the two-group classification difference to its original disclosure clause."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_complementary_acquisition as study
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_contractor_permission as contractor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_complement_contractor_control'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK = 'nda-7'


def source_proof(source):
    view = next(row for row in source['views'] if row['id'] == TASK)
    return contractor.proof(study.disposition.scope.retention.spans_for(view))


def cases_for():
    _, _, roster = study.b4.archive.archive_context()
    train = study.b5.roster_cells(roster, slice(None, None), 1)
    _, _, original, _, _, _ = study.disposition.employee.base.prior.prepare_dev()
    return train, original


def score(cases, bank, labels):
    controls = {'candidate_driven' if role == study.CANDIDATE else role: rows for role, rows in bank.items()}
    return study.replay.compare(cases, controls, labels)


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != study.disposition.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Use the settled cumulative DEV and frozen TRAIN acquisition')
    root, binding, result = study.b4.terminal(study)
    reference_input, _ = study.replay_fits()
    _, reference, _, _, _ = study.replay.inputs(reference_input)
    if sha(root / 'sealed_predictions.json') != result['predictions_sha256'] or sha(reference) != binding['TRAIN_grade_sha256']:
        raise ValueError('Use exactly the previous two-group bank and original TRAIN labels')
    train, dev = cases_for()
    later = {key: row for key, row in train.items() if row[1][0] >= 5}
    if len(train) != 24 or len(later) != 12 or len(dev) != 16:
        raise ValueError('Use the complete original chronological cohort')
    found = {key: source_proof(source) for key, (source, _) in train.items()}
    fixed = {key: source_proof(source) for key, source in dev.items()}
    before = read(root / 'sealed_predictions.json')
    after = {role: {key: {**rows, TASK: {**rows[TASK], **found[key]}} if TASK in rows and found[key] else rows
                    for key, rows in bank.items()} for role, bank in before.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger != result['ledger']:
        raise ValueError('The attribution uses only already sealed reads')
    source_paths = {str(Path(path).relative_to(ROOT)): sha(Path(path)) for path in (
        __file__, study.__file__, contractor.__file__, contractor.employees.__file__,
    )}
    spec = {'stage': STAGE, 'source_sha256': source_paths, 'acquisition_terminal': result['terminal_sha256'],
            'original_TRAIN_grade_sha256': sha(reference), 'source_proofs_sha256': digest([found, fixed]),
            'original_allocations_preserved': True, 'TEST_opened': False}
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    study.b4.archive.snapshot(out, source_paths)
    immutable_json(out / 'source_proofs.json', {'TRAIN': found, 'fixed_DEV': fixed})
    prediction_hash = immutable_json(out / 'sealed_predictions.json', after)
    labels = read(reference)
    original_metrics = score(later, before, labels)
    if result['B4_archived_native'] != original_metrics:
        raise ValueError('Reproduce the exact settled B4 outcome before applying the common source path')
    matched = [{'position': train[key][1], 'source_witness': proof,
                'reference_class_matches': labels[key][TASK]['answer'] == proof['answer'],
                'reference_evidence_matches': labels[key][TASK]['evidence'] == proof['evidence_sentence_ids']}
               for key, proof in found.items() if proof]
    output = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_hash,
        'TRAIN_proofs': matched, 'public_fixed_DEV_witnesses': sum(bool(x) for x in fixed.values()),
        'public_fixed_DEV_mothers': len(fixed), 'fixed_DEV_labels_opened': False,
        'after_shared_permission': score(later, after, labels), 'selections_held_fixed': True,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', output)
    write_status(out, {'status': output['status'], 'terminal_sha256': output['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
