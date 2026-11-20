"""Separate B5 candidate removals from common, source-proved Illinois exclusions."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_agreement_disclosure_release as archive
from experiments import convergence_revision6_maud_section_reference as release
from experiments import convergence_revision6_oe_joint_item_cap as previous_dev
from experiments import convergence_revision6_oe_missing_forward_fit as previous_fit
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import convergence_oe_illinois_eligibility as policy
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_pa_item_forms import filter_claims
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_illinois_eligibility'
POINTER = HANDOFF / f'{STAGE}_current.json'
joint = previous_fit.residual.previous


def views_of(source):
    return {view['id']: view for view in source['views']}


def physical_dev(db, source, folder, seal, cell, known, tasks):
    key = source['key']
    record = read(folder / 'predictions' / f'{digest(key)}.json')
    if (digest(record) != seal['predictions_sha256'][key] or record['public_source_sha256'] != digest(source)
            or record['library_sha256'] != cell['libraries'][joint.OE]):
        raise ValueError('Require the original fixed DEV response and library')
    if 'EC' in tasks:
        joint.category.ec_read(db, source, record, known, 'dev')
    if 'EV' in tasks:
        previous_dev.prior_ev.wire.read_ev(db, source, record, known, 'dev')


def change_counts(answers, exclusions, task):
    a, b = (joint.joint.port_claims(answers[arm][task], task) for arm in ('incumbent', 'proposal'))
    return {
        'source_excluded_removed': sum(row[:2] in exclusions for row in a - b),
        'source_excluded_added': sum(row[:2] in exclusions for row in b - a),
        'other_claim_changes': sum(row[:2] not in exclusions for row in a ^ b),
    }


def grade_bank(views, labels, banks):
    units = {
        phase: {task: [{'source': key, 'view': task,
                       'grade': joint.archive.native_grade(views[key][task], labels[key][task], row[task])}
                      for key, row in bank.items()]
                for task in joint.PORTS}
        for phase, bank in banks.items()
    }
    return {name: {task: mean(r['grade'] for r in rows) for task, rows in by_task.items()}
            for name, by_task in units.items()}, units


def dev_compare(views, labels, banks):
    metrics, units = grade_bank(views, labels, banks)
    return {task: {
        'F1': [metrics[phase][task] for phase in ('before', 'after')],
        'paired': paired_source_effect(units['before'][task], units['after'][task]),
        'improved': sum(new['grade'] > old['grade']
                        for old, new in zip(units['before'][task], units['after'][task], strict=True)),
        'regressed': sum(new['grade'] < old['grade']
                         for old, new in zip(units['before'][task], units['after'][task], strict=True)),
    } for task in joint.PORTS}


def validate_source_proofs(proofs, labels):
    conflicts = sum(
        (asset, law) in {claim[:2] for claim in joint.joint.port_claims(labels[key][task]['answer'], task)}
        for key, found in proofs.items() for task, pairs in found.items() for asset, law in pairs
    )
    return {'mothers': sum(any(v.values()) for v in proofs.values()),
            'asset_citations_by_task': {task: sum(len(found[task]) for found in proofs.values())
                                        for task in joint.PORTS},
            'known_exclusion_conflicts': conflicts}


def run():
    _, _, last_fit = archive.bound_result(previous_fit)
    prior_root, prior_spec, prior = archive.bound_result(previous_dev)
    prior_ev = read(prior_root / 'sealed_predictions.json')['fixed_DEV']
    parent, cohort, originals, study, actor_receipt = release.base_actor()
    _, _, train_batches = release.parallel.adoption.archive_context()
    original_train = {s['key']: s for rows in train_batches for s in rows
                      if s['dataset'] == joint.OE and s['project_split'] == 'train'}
    dev = {s['key']: s for s in cohort if s['dataset'] == joint.OE and s['project_split'] == 'dev'}
    if len(original_train) != 32 or len(dev) != 16 or set(originals) != set(prior_ev) or len(originals) != 5:
        raise ValueError('Keep the original TRAIN and all five fixed DEV arms')
    train_views = {key: views_of(s) for key, s in original_train.items()}
    dev_views = {key: views_of(s) for key, s in dev.items()}
    proofs = {split: {key: {task: sorted(policy.exclusions(view)) for task, view in cells.items()}
                      for key, cells in bank.items()} for split, bank in (('TRAIN', train_views), ('DEV', dev_views))}
    dev_predictions = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        b5, original_reads, (train_grade, train_hash), fit_receipt = previous_fit.original_fit(db, 5)
        dev_reads = set()
        for arm, (folder, seal, cell) in originals.items():
            baseline, corrected = {}, {}
            for key, source in dev.items():
                rows = parent(source, {'arm': arm, 'batch': 8}, 'skill_dev')['native']
                baseline[key] = {'EC': rows['EC']['answer'], 'EV': prior_ev[arm][key]['after']}
                corrected[key] = {task: filter_claims(task, answer, set(proofs['DEV'][key][task]))
                                  for task, answer in baseline[key].items()}
                changed = {task for task in joint.PORTS if corrected[key][task] != baseline[key][task]}
                if changed:
                    physical_dev(db, source, folder, seal, cell, dev_reads, changed)
            dev_predictions[arm] = {'before': baseline, 'after': corrected}
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or not b5.keys() <= original_train.keys():
        raise ValueError('Require the settled continuous ledger and the original B5 sources')

    corrected_b5 = {}
    for key, row in b5.items():
        if row['views'] != train_views[key]:
            raise ValueError('Use only each original view’s own source proof')
        corrected_b5[key] = {**row, 'answers': {
            arm: {task: filter_claims(task, value, set(proofs['TRAIN'][key][task])) for task, value in reads.items()}
            for arm, reads in row['answers'].items()
        }}
    diagnosed = {
        r['position']: {task: change_counts(r['answers'], set(proofs['TRAIN'][key][task]), task)
                        for task in joint.PORTS}
        for key, r in b5.items()
    }
    dev_grade = study['grading_paths'][joint.OE]
    lock = {
        'stage': STAGE, 'TEST_opened': False, 'fixed_DEV_actor': actor_receipt,
        'inherited_EV_terminal': prior['terminal_sha256'], 'B5_selection_terminal': last_fit['terminal_sha256'],
        'B5_candidate_provenance': fit_receipt, 'B5_physical_requests_sha256': digest(sorted(original_reads)),
        'TRAIN_grade_sha256': train_hash, 'DEV_grade_sha256': study['grading_file_sha256'][dev_grade],
        'source_proofs_sha256': digest(proofs), 'inputs_sha256': digest({'TRAIN': b5, 'DEV': dev_views}),
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, policy.__file__, previous_fit.__file__, previous_dev.__file__, release.__file__,
        )},
    }
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    snapshot(out, lock['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)
    tag = immutable_json(out / 'sealed_predictions.json', {
        'B5': {key: row['answers'] for key, row in corrected_b5.items()}, 'fixed_DEV': dev_predictions,
    })
    if ('train' not in Path(train_grade).parts or 'dev' not in Path(dev_grade).parts or
            sha(ROOT / train_grade) != train_hash or sha(ROOT / dev_grade) != lock['DEV_grade_sha256'] or
            lock['DEV_grade_sha256'] != prior_spec['dev_grade_sha256']):
        raise ValueError('Score only the exact original TRAIN and DEV reference after sealing')
    train_ref, dev_ref = read(ROOT / train_grade), read(ROOT / dev_grade)
    fits = {phase: previous_fit.measure(bank, train_ref)
            for phase, bank in (('before', b5), ('after', corrected_b5))}
    original_fit = last_fit['fit_ONLY']['5']
    if digest(fits['before']) != digest(original_fit):
        raise ValueError('Resume the exact prior B5 choices, gates and native outcomes')
    scores = {arm: dev_compare(dev_views, dev_ref, banks) for arm, banks in dev_predictions.items()}
    scope = {split: validate_source_proofs(proofs[split], labels)
             for split, labels in (('TRAIN', train_ref), ('DEV', dev_ref))}
    for name, selection in fits['after']['choices'].items():
        programs = fit_receipt['programs']
        assigned = {task: programs[program] for task, program in
                    zip(joint.PORTS, joint.joint.ROUTES[selection['route']], strict=True)}
        library = sealed({'fit_batch': 5, 'selection': selection, 'programs': assigned, 'binding_sha256': out.name},
                         'snapshot_sha256')
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', library)
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'B5_per_group_claim_changes': diagnosed,
        'B5_fit': fits, 'fixed_DEV': scores, 'scope': scope,
        'reused_responses': {'B5': len(original_reads), 'changed_DEV': len(dev_reads)},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
