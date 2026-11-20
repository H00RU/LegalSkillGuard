"""Compare the actual B8 OpenExempt readers under the same source proofs."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_b1_household_fit as previous
from experiments import convergence_revision6_wi_homestead_transfer as homestead
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_b8_portfolio'
POINTER = HANDOFF / f'{STAGE}_current.json'
OE, PORTS = previous.OE, previous.PORTS
formal, signed = previous.formal, previous.signed
common = signed.common
ENTRANTS = ('incumbent', 'ordinary_entrant', 'parse_entrant')
ROLES = (*ENTRANTS, 'proposal', 'parse')
ARMS = (formal.M2, formal.ORDINARY, previous.EXTERNAL)


def b8_materials(db):
    bound_stage = previous.forward.prior.archive.bound_stage
    fit, config, fit_end = bound_stage(formal.pointer(8))
    obs, observe_config, observe_end = bound_stage(previous.observe_pointer(8))
    root = ROOT / config['checkpoint_root']
    study = read(root / 'binding.json')
    roster = formal.load_roster(study)
    journal = previous.forward.exact.TrainingJournal(root, study, roster)
    if (fit_end['batch'] != 8 or observe_end['batch'] != 8 or fit_end['TEST_opened'] or observe_end['TEST_opened']
            or config['observations_root'] != str(obs.relative_to(ROOT))
            or config['checkpoint_root'] != observe_config['checkpoint_root']
            or any(stage['executor'] != study['executor'] for stage in (config, observe_config))):
        raise ValueError('Use the original B8 fit and observation with the same frozen executor')
    decisions = read(fit / 'matched_decisions.json')
    if digest(decisions) != fit_end['matched_decisions_sha256']:
        raise ValueError('Use the original sealed B8 decisions')
    prior = {arm: journal.library(arm, 7) for arm in ARMS}
    final = {arm: journal.library(arm, 8) for arm in ARMS}
    programs = dict(zip(ENTRANTS, (prior[formal.M2]['programs'][OE], prior[formal.ORDINARY]['programs'][OE],
                                  prior[previous.EXTERNAL]['schema_proposals'][OE]), strict=True))
    candidates = {}
    for role, arm, collection in (('proposal', formal.ORDINARY, 'programs'),
                                  ('parse', previous.EXTERNAL, 'schema_proposals')):
        folder = fit / 'candidates' / arm / OE
        measurement = read(folder / 'measurements.json')
        decision = decisions['teacher'][arm][OE]
        if (decision != read(folder / 'decision.json') or decision['selected'] != 'candidate'
                or digest(measurement['predictions']) != decision['predictions_sha256']
                or measurement['candidate'] != final[arm][collection][OE]):
            raise ValueError('Use the actual fitted B8 proposals and both adopted carrier checkpoints')
        candidates[role] = measurement['predictions']
        programs[role] = measurement['candidate']
    versions = {role: digest(program) for role, program in programs.items()}
    if (len(set(versions.values())) != len(ROLES)
            or versions['proposal'] != decisions['relation'][OE]['matched_proposal_sha256']
            or digest(final[formal.M2]['programs'][OE]) != versions['proposal']):
        raise ValueError('Require the distinct original readers and the formal B8 M2 adoption')
    for arm in ARMS:
        if (journal._observations(arm, 8)['train_observation_sha256'] != observe_end['observation_receipts'][arm]
                or journal._completed_batch(arm, 8)['completed_batch_sha256'] != fit_end['arm_receipts'][arm]):
            raise ValueError('Retain the original B8 observation and fit receipts')

    sources = [s for s in roster[7] if s['dataset'] == OE]
    if len(sources) != 4 or any(s['project_split'] != 'train' for s in sources):
        raise ValueError('Use all four original OpenExempt B8 TRAIN mothers')
    bank, physical, inputs = {}, set(), {}
    for position, source in enumerate(sources):
        key = source['key']
        readings = {role: previous.forward.raw_prediction(journal, arm, 8, key)
                    for role, arm in zip(ENTRANTS, ARMS, strict=True)}
        readings.update({role: rows[key] for role, rows in candidates.items()})
        if readings['parse_entrant']['schema_library_sha256'] != prior[previous.EXTERNAL]['snapshot_sha256']:
            raise ValueError('Require an actual read of the prior PARSE library')
        native, signatures = {}, set()
        for role, result in readings.items():
            if role in ('parse', 'parse_entrant'):
                saved_config = config if role == 'parse' else observe_config
                native[role], ids = previous.restore_parse(db, source, result, programs[role], saved_config)
            else:
                native[role], ids = previous.select_native(db, source, result, versions[role])
            physical.update(ids)
            signatures.add(previous.public_inputs(db, ids))
        if len(signatures) != 1:
            raise ValueError('Every candidate and entering reader must see identical public inputs and settings')
        inputs[key] = signatures.pop()
        bank[key] = previous.same_controls({'position': position, 'views': common.previous.views_of(source),
                                            'answers': native})
    if len(physical) != 40:
        raise ValueError('Count every distinct B8 TRAIN EC and EV response')
    grades = previous.forward.assets.grades_ref(observe_config)
    return bank, physical, grades, {
        'B8_fit_sha256': sha(fit / 'terminal.json'), 'B8_observe_sha256': sha(obs / 'terminal.json'),
        'programs': versions, 'public_inputs_sha256': digest(inputs),
        'original_teacher_fit_gain': {role: decisions['teacher'][arm][OE]['native_utility_delta']
                                      for role, arm in (('proposal', formal.ORDINARY), ('parse', previous.EXTERNAL))},
    }


def household_controls(native, views, category):
    amount = previous.motor.motor.source_proof(views['EV'])
    projected = previous.motor.project(common.project(native, category), amount)
    return {task: previous.filter_claims(task, answer, previous.household.exclusions(views[task]))
            for task, answer in projected.items()}


def project_homestead(native, proofs):
    """Give every reader the same exact paired title, occupancy and amount proof."""
    projected = dict(native)
    for asset, proof in proofs.items():
        for task in PORTS:
            actual = homestead.observation(projected[task], task, asset)
            if actual != proof['expected'][task]:
                projected[task] = homestead.replace_claim(projected[task], task, asset, proof)
    return projected


def audit(proofs, labels):
    return {'mothers': sum(bool(values) for values in proofs.values()),
            'asset_pairs': sum(map(len, proofs.values())),
            'reference_disagreements': [
                {'source_sha256': digest(key), 'task': task}
                for key, values in proofs.items() for asset, proof in values.items() for task in PORTS
                if homestead.observation(labels[key][task]['answer'], task, asset) != proof['expected'][task]
            ]}


def run():
    parent, parent_binding, parent_end = common.prior.checked.bound_result(previous)
    previous_dev = read(parent / 'sealed_predictions.json')['fixed_DEV']
    if sha(parent / 'sealed_predictions.json') != parent_end['predictions_sha256']:
        raise ValueError('Keep the exact previous cumulative fixed DEV predictions')
    _, cohort, dev_arms, study, _ = common.previous.release.base_actor()
    dev = {s['key']: s for s in cohort if s['dataset'] == OE and s['project_split'] == 'dev'}
    if len(dev) != 16 or len(dev_arms) != 5:
        raise ValueError('Use the fixed original OpenExempt DEV cohort and five arms')
    dev_views = {key: common.previous.views_of(source) for key, source in dev.items()}
    dev_proofs = {key: homestead.group_proof(key, views) for key, views in dev_views.items()}
    dev_reads = set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        train, train_reads, (train_grade, train_hash), provenance = b8_materials(db)
        dev_banks = {}
        for arm, (folder, seal, cell) in dev_arms.items():
            before = previous_dev[arm]['after']
            after = {key: project_homestead(row, dev_proofs[key]) for key, row in before.items()}
            dev_banks[arm] = {'before': before, 'after': after}
            for key, row in before.items():
                changed = {task for task in PORTS if row[task] != after[key][task]}
                if changed:
                    common.previous.physical_dev(db, dev[key], folder, seal, cell, dev_reads, changed)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if set(ledger) - {'completed', 'failed'} or train_reads & dev_reads:
        raise ValueError('Require disjoint archived TRAIN and DEV requests with no calls in flight')
    dev_grade = study['grading_paths'][OE]
    grades = {'train': (train_grade, train_hash), 'dev': (dev_grade, study['grading_file_sha256'][dev_grade])}
    for split, (path, expected) in grades.items():
        if split not in Path(path).parts or sha(ROOT / path) != expected or parent_binding[f'{split}_grade_sha256'] != expected:
            raise ValueError('Use the original TRAIN and fixed DEV grading references')
    labels, dev_labels = (read(ROOT / grades[k][0]) for k in ('train', 'dev'))
    train_proofs = {key: homestead.group_proof(key, row['views']) for key, row in train.items()}
    category = {key: {task: common.categories.source_proof(view) for task, view in row['views'].items()}
                for key, row in train.items()}
    before = {key: {**row, 'answers': {role: household_controls(value, row['views'], category[key])
                                       for role, value in row['answers'].items()}} for key, row in train.items()}
    after = {key: {**row, 'answers': {role: project_homestead(value, train_proofs[key])
                                      for role, value in row['answers'].items()}} for key, row in before.items()}
    train_labels = {key: labels[key] for key in train}
    fits = {phase: signed.fit_choices(bank, ROLES, category, train_labels)
            for phase, bank in (('before', before), ('after', after))}
    for f in fits.values():
        del f['groups']  # Per-asset witnesses stay in the internal bound predictions and source proofs.
    proofs = {'train': train_proofs, 'dev': dev_proofs}
    audits = {'train': audit(train_proofs, train_labels), 'dev': audit(dev_proofs, dev_labels)}
    dev_scores = {role: common.previous.dev_compare(dev_views, dev_labels, bank) for role, bank in dev_banks.items()}
    dev_release = (not any(row['reference_disagreements'] for row in audits.values())
                   and not any(task['regressed'] for row in dev_scores.values() for task in row.values())
                   and any(task['improved'] for row in dev_scores.values() for task in row.values()))
    selectors = fits['after']['signed']
    distinct = {rule: pick['route'] for rule, pick in selectors.items()
                if rule not in ('candidate_driven', 'native_fit_only') and pick['route'] != selectors['candidate_driven']['route']}
    files = (__file__, previous.__file__, homestead.__file__, homestead.local.__file__, signed.__file__,
             signed.direction.__file__, signed.portfolio.__file__)
    binding = {'stage': STAGE, 'provenance': provenance, 'prior_fixed_DEV_terminal': parent_end['terminal_sha256'],
               'source_proofs_sha256': digest(proofs), 'grades_sha256': {k: v[1] for k, v in grades.items()},
               'physical_ids_sha256': {'train': digest(sorted(train_reads)), 'dev': digest(sorted(dev_reads))},
               'group_budget': common.prior.GROUP_BUDGET, 'TEST_opened': False,
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    previous.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)
    prediction_sha = immutable_json(out / 'predictions.json', {'TRAIN': {'before': before, 'after': after}, 'DEV': dev_banks})
    for name, selected in selectors.items():
        programs = {task: provenance['programs'][program] for task, program in zip(PORTS, selected['route'], strict=True)}
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', sealed({
            'binding_sha256': out.name, 'decision': selected, 'programs_by_task': programs,
            'original_frozen_library_changed': False,
        }, 'snapshot_sha256'))
    summary = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
                      'TRAIN_mothers': len(train), 'fixed_DEV_mothers': len(dev), 'fit': fits,
                      'signed_selection_disagreements': distinct, 'source_audit': audits, 'fixed_DEV': dev_scores,
                      'shared_DEV_release': dev_release, 'archived_TRAIN_reads': len(train_reads),
                      'archived_DEV_reads': len(dev_reads), 'new_executor_requests': 0, 'new_teacher_requests': 0,
                      'ledger': ledger, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', summary)
    write_status(out, {'status': summary['status'], 'terminal_sha256': summary['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
