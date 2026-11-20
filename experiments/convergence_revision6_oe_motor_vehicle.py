"""Verify same-information motor-vehicle caps on original OpenExempt outputs."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_item_categories as previous
from experiments import convergence_revision6_oe_missing_forward_fit as fit
from experiments import convergence_revision6_oe_signed_direction as selection
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import convergence_oe_motor_vehicle as motor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_motor_vehicle'
POINTER = HANDOFF / f'{STAGE}_current.json'
OE = previous.archive.OE


def project(answers, source_proof):
    return {**answers, 'EV': motor.apply(answers['EV'], source_proof)}


def audit(sources, labels):
    count, conflicts = 0, []
    for key, assets in sources.items():
        native = previous.archive.joint.port_claims(labels[key]['EV']['answer'], 'EV')
        for asset, values in assets.items():
            for law, proof in values.items():
                count += 1
                if (asset, law, proof['expected_cents'] / 100) not in native:
                    conflicts.append({'source_sha256': digest(key), 'citation': law})
    return {'verified_pairs': count, 'disagreements': conflicts}


def run():
    checked = previous.prior.checked
    last, lock, terminal = checked.bound_result(previous)
    _, _, old_fit = checked.bound_result(selection)
    predecessor = read(last / 'sealed_predictions.json')['fixed_DEV']
    old_rules = read(last / 'source_proofs.json')
    if digest(old_rules) != lock['evidence_sha256']:
        raise ValueError('Require the exact prior OpenExempt source proofs')
    _, cohort, originals, study, _ = previous.previous.release.base_actor()
    _, _, roster = previous.previous.release.parallel.adoption.archive_context()
    train = {s['key']: s for batch in roster for s in batch if s['dataset'] == OE}
    dev = {s['key']: s for s in cohort if s['dataset'] == OE}
    if (len(train), len(dev), len(originals)) != (32, 16, 5):
        raise ValueError('Keep the complete original OpenExempt cohorts and five arms')
    cohorts = {'train': train, 'dev': dev}
    views = {split: {key: previous.previous.views_of(s) for key, s in sources.items()}
             for split, sources in cohorts.items()}
    for split, sources in cohorts.items():
        if any(s['project_split'] != split for s in sources.values()):
            raise ValueError('Restrict revision to original TRAIN and fixed DEV')
    proofs = {split: {key: motor.source_proof(row['EV']) for key, row in values.items()}
              for split, values in views.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        b2, fit_reads, (train_grade, train_hash), proposal = fit.original_fit(db, 2)
        if any(key not in b2 for key, rule in proofs['train'].items() if rule):
            raise ValueError('B2 is the recorded candidate archive for the scoped TRAIN comparison')
        revised_b2 = {key: {**row, 'answers': {side: project(values, proofs['train'][key])
                                              for side, values in row['answers'].items()}}
                      for key, row in b2.items()}
        banks, dev_reads = {}, set()
        for role, (folder, seal, cell) in originals.items():
            before = predecessor[role]['after']
            after = {key: project(row, proofs['dev'][key]) for key, row in before.items()}
            banks[role] = {'before': before, 'after': after}
            for key in before:
                if after[key] != before[key]:
                    previous.previous.physical_dev(db, dev[key], folder, seal, cell, dev_reads, {'EV'})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Use the original settled response bank')
    dev_grade = study['grading_paths'][OE]
    grade_paths = {'train': train_grade, 'dev': dev_grade}
    hashes = {'train': train_hash, 'dev': lock['DEV_grade_sha256']}
    for split, path in grade_paths.items():
        if split not in Path(path).parts or sha(ROOT / path) != hashes[split] or lock[f'{split.upper()}_grade_sha256'] != hashes[split]:
            raise ValueError('Retain the original TRAIN and fixed DEV native references')
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'prior_fixed_DEV_terminal': terminal['terminal_sha256'],
        'prior_signed_fit_terminal': old_fit['terminal_sha256'], 'B2_proposal': proposal,
        'source_proofs_sha256': digest(proofs), 'grade_sha256': hashes,
        'reused_reads_sha256': {'B2': digest(sorted(fit_reads)), 'DEV': digest(sorted(dev_reads))},
        'DEV_analysis': 'Exploratory common repair on the previously viewed fixed development cohort.',
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, motor.__file__, motor.federal.__file__, previous.__file__, fit.__file__, selection.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)
    pred_sha = immutable_json(out / 'sealed_predictions.json', {'fixed_DEV': banks, 'B2_with_motor_proof': revised_b2})
    labels = {part: read(ROOT / path) for part, path in grade_paths.items()}
    audits = {part: audit(scope, labels[part]) for part, scope in proofs.items()}
    dev_scores = {role: previous.previous.dev_compare(views['dev'], labels['dev'], row)
                  for role, row in banks.items()}
    readers = tuple(next(iter(b2.values()))['answers'])
    selected = {phase: selection.fit_choices(bank, readers, old_rules['train'], labels['train'])['signed']
                for phase, bank in (('before', b2), ('after', revised_b2))}
    if digest(selected['before']) != digest(old_fit['fits']['2']['signed']):
        raise ValueError('Reproduce the original same-budget signed B2 selector')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred_sha,
        'B2_motor_scope_program_outputs_unchanged': b2 == revised_b2,
        'B2_selection': selected, 'B2_mothers': len(b2), 'source_audit': audits, 'fixed_DEV': dev_scores,
        'coverage': {part: [sum(map(bool, scope.values())), len(scope)] for part, scope in proofs.items()},
        'supports_common_DEV_release': (not any(row['disagreements'] for row in audits.values())
                                        and not any(row['EV']['regressed'] for row in dev_scores.values())
                                        and any(row['EV']['improved'] for row in dev_scores.values())),
        'reused_TRAIN_requests': len(fit_reads), 'reused_DEV_requests': len(dev_reads),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
