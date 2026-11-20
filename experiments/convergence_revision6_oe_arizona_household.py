"""Re-evaluate the B2 valuation proposal with the same Arizona source proof in both readers."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_illinois_eligibility as previous
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import convergence_oe_arizona_household as rule
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_arizona_household'
POINTER = HANDOFF / f'{STAGE}_current.json'
PORTS = previous.joint.PORTS


def project(answers, proof):
    return {task: rule.apply(task, answers[task], proof[task]) for task in PORTS}


def audit(proofs, labels):
    expected, rejected, conflicts = dict.fromkeys(PORTS, 0), dict.fromkeys(PORTS, 0), []
    for key, tasks in proofs.items():
        for task, facts in tasks.items():
            claims = previous.joint.joint.port_claims(labels[key][task]['answer'], task)
            for asset, value in facts['eligible'].items():
                expected[task] += 1
                claim = (asset, rule.HOUSEHOLD) if task == 'EC' else (asset, rule.HOUSEHOLD, value / 100)
                if claim not in claims:
                    conflicts.append((task, 'positive'))
            excluded = set(map(tuple, facts['excluded']))
            rejected[task] += len(excluded)
            conflicts.extend((task, 'negative') for row in claims if row[:2] in excluded)
    return {'positive_claims': expected, 'excluded_claims': rejected, 'label_disagreements': conflicts}


def run():
    prior_root, fixed, prior = previous.archive.bound_result(previous)
    _, _, old_b2 = previous.archive.bound_result(previous.previous_fit)
    _, cohort, original_dev, study, fixed_actor = previous.release.base_actor()
    _, _, train_batches = previous.release.parallel.adoption.archive_context()
    train = {s['key']: s for batch in train_batches for s in batch
             if s['dataset'] == previous.joint.OE and s['project_split'] == 'train'}
    dev = {s['key']: s for s in cohort if s['dataset'] == previous.joint.OE and s['project_split'] == 'dev'}
    if (len(train), len(dev), len(original_dev)) != (32, 16, 5) or fixed['fixed_DEV_actor'] != fixed_actor:
        raise ValueError('Use the original OpenExempt cohorts and latest released OpenExempt DEV stage')
    sources = {'TRAIN': train, 'DEV': dev}
    views = {part: {key: previous.views_of(s) for key, s in bank.items()} for part, bank in sources.items()}
    proofs = {part: {key: {task: rule.source_proof(view) for task, view in cells.items()}
                     for key, cells in bank.items()} for part, bank in views.items()}
    prior_dev = read(prior_root / 'sealed_predictions.json')['fixed_DEV']
    revised_dev = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        b2, requests, (train_grade, train_sha), provenance = previous.previous_fit.original_fit(db, 2)
        fixed_reads = set()
        for role, (folder, seal, cell) in original_dev.items():
            before = prior_dev[role]['after']
            after = {key: project(native, proofs['DEV'][key]) for key, native in before.items()}
            revised_dev[role] = {'before': before, 'after': after}
            for key, native in before.items():
                changed = {task for task in PORTS if after[key][task] != native[task]}
                if changed:
                    previous.physical_dev(db, dev[key], folder, seal, cell, fixed_reads, changed)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(requests) != 16:
        raise ValueError('Only reuse settled original native requests')
    revised_fit = {key: {**case, 'answers': {
        role: project(native, proofs['TRAIN'][key]) for role, native in case['answers'].items()
    }} for key, case in b2.items()}
    dev_grade = study['grading_paths'][previous.joint.OE]
    files = (__file__, rule.__file__, previous.__file__, previous.previous_fit.__file__)
    lock = {
        'stage': STAGE, 'TEST_opened': False, 'fixed_DEV_prior_terminal': prior['terminal_sha256'],
        'prior_B2_selection_terminal': old_b2['terminal_sha256'], 'B2_original_fit': provenance,
        'B2_native_reads_sha256': digest(sorted(requests)), 'proof_sha256': digest(proofs),
        'TRAIN_grade_sha256': train_sha, 'DEV_grade_sha256': fixed['DEV_grade_sha256'],
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files},
    }
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    snapshot(out, lock['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)
    tag = immutable_json(out / 'sealed_predictions.json', {'B2': revised_fit, 'fixed_DEV': revised_dev})
    if ('train' not in Path(train_grade).parts or 'dev' not in Path(dev_grade).parts
            or sha(ROOT / train_grade) != train_sha or sha(ROOT / dev_grade) != lock['DEV_grade_sha256']):
        raise ValueError('Use only original TRAIN and fixed DEV references after sealing')
    train_labels, dev_labels = read(ROOT / train_grade), read(ROOT / dev_grade)
    fits = {phase: previous.previous_fit.measure(bank, train_labels)
            for phase, bank in (('before', b2), ('after', revised_fit))}
    if digest(fits['before']) != digest(old_b2['fit_ONLY']['2']):
        raise ValueError('The original B2 gate and physical readouts must reproduce')
    for name, selection in fits['after']['choices'].items():
        assignment = {task: provenance['programs'][role] for task, role in zip(
            PORTS, previous.joint.joint.ROUTES[selection['route']], strict=True)}
        library = sealed({'fit_batch': 2, 'selection': selection, 'programs': assignment,
                          'binding_sha256': out.name}, 'snapshot_sha256')
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', library)
    fixed_dev = {arm: previous.dev_compare(views['DEV'], dev_labels, bank) for arm, bank in revised_dev.items()}
    checked = {split: audit(proofs[split], labels)
               for split, labels in (('TRAIN', train_labels), ('DEV', dev_labels))}
    release = all(not row['label_disagreements'] for row in checked.values()) and all(
        not row['regressed'] for cells in fixed_dev.values() for row in cells.values()
    ) and any(row['improved'] for cells in fixed_dev.values() for row in cells.values())
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'B2_fit': fits, 'fixed_DEV': fixed_dev, 'proof_audit': checked,
        'B2_residual_valuation_F1': {phase: 2 * row['native_gain_after_shared_rules']['EV_only']
                                    for phase, row in fits.items()},
        'B2_same_information_routing_identical': len({r['route'] for r in fits['after']['choices'].values()}) == 1,
        'support_common_DEV_release': release, 'reused_responses': {'B2': len(requests), 'changed_DEV': len(fixed_reads)},
        'ledger': ledger, 'TEST_opened': False, 'new_executor_requests': 0, 'new_teacher_requests': 0,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
