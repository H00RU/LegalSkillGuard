"""Compare the actual B1 OpenExempt candidate pool with common household exclusions."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_motor_vehicle as motor
from experiments import convergence_revision6_oe_signed_direction as signed
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_parse_runtime import EXTERNAL_ARM as EXTERNAL
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from experiments.convergence_revision6_oe_candidate_group import restore_parse, same_controls
from legal_skill_guard.paired_interfaces import convergence_oe_illinois_household as household
from legal_skill_guard.paired_interfaces.convergence_oe_pa_item_forms import filter_claims
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_b1_household_fit'
POINTER = HANDOFF / f'{STAGE}_current.json'
OE, PORTS = motor.OE, signed.PORTS
joint, forward = signed.archive, signed.archive.archive
formal = joint.FORMAL
ORDINARY = formal.ORDINARY
BASE_ROUTE = ('incumbent', 'incumbent')


def select_native(db, source, result, program):
    ec, ec_id, _ = joint.matching_ec(db, source, result, program)
    view = forward.assets.dev_archive.ev_view(source)
    ev_id, amount = forward.exact.verified_ev(db, source, view, result, program)
    ev = forward.assets.scopes(view, amount)['same_public_jurisdiction']
    return {'EC': ec, 'EV': ev}, {ec_id, ev_id}


def public_inputs(db, ids):
    """Compare exact questions and model settings while allowing a reversible schema."""
    signatures = []
    for identity in ids:
        row, = db.execute('select result from calls where id=?', (identity,)).fetchone()
        result = json.loads(row)
        payload = read(Path(result['artifact_directory']) / 'request.json')['payload']
        signatures.append(digest({**{k: v for k, v in payload.items() if k not in ('messages', 'response_format')},
                                  'public': [m for m in payload['messages'] if m['role'] == 'user']}))
    return tuple(sorted(signatures))


def materials(db):
    bound_stage = forward.prior.archive.bound_stage
    fit, fit_config, end = bound_stage(HANDOFF / 'formal_b1_fit_current.json')
    first = bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    following = bound_stage(observe_pointer(2))
    root = ROOT / fit_config['bootstrap_root']
    study = read(root / 'binding.json')
    roster = formal.load_roster(study)
    journal = forward.exact.TrainingJournal(root, study, roster)
    if (fit_config['observations_terminal_sha256'] != sha(first[0] / 'terminal.json')
            or any(study['executor'] != row['executor'] for row in (fit_config, first[1], following[1]))):
        raise ValueError('Use the identical original B1 and B2 frozen executors')
    predictions, receipts = {}, {}
    for arm in (ORDINARY, EXTERNAL):
        folder = fit / 'candidates' / arm / OE
        decision = read(folder / 'decision.json')
        rows = read(folder / 'predictions.json')
        sealed_update = read(journal.directory(arm, 1) / 'update_evidence.json')
        if (journal._completed_batch(arm, 1) != end['arms'][arm] or decision != sealed_update['selected_candidates'][OE]
                or digest(rows) != decision['predictions_sha256'] or decision['status'] != 'measured'):
            raise ValueError('Use both exact measured B1 proposals and their sealed fit decisions')
        predictions[arm], receipts[arm] = rows, decision
    libraries = {role: journal.library(arm, 1) for role, arm in (('incumbent', ORDINARY), ('parse', EXTERNAL))}
    original = digest(journal.library(ORDINARY, 0)['programs'][OE])
    schema = libraries['parse']['schema_proposals'][OE]
    programs = {'incumbent': original, 'proposal': receipts[ORDINARY]['candidate_sha256'], 'parse': digest(schema)}
    if (programs['parse'] != receipts[EXTERNAL]['candidate_sha256'] or receipts[EXTERNAL]['selected'] != 'candidate'
            or receipts[ORDINARY]['selected'] != 'incumbent' or digest(libraries['incumbent']['programs'][OE]) != original):
        raise ValueError('Keep the original fit programs and the original round-two carrier')

    banks, identities, grades = {}, set(), set()
    for number, (folder, config, terminal) in enumerate((first, following), 1):
        phase = 'fit' if number == 1 else 'forward'
        grades.add(forward.assets.grades_ref(config))
        cases = [source for source in roster[number - 1] if source['dataset'] == OE]
        if len(cases) != 4 or any(s['project_split'] != 'train' for s in cases):
            raise ValueError('Use all four original sources in both chronological batches')
        for arm in (ORDINARY, EXTERNAL):
            if journal._observations(arm, number)['train_observation_sha256'] != terminal['observation_receipts'][arm]:
                raise ValueError('The original TRAIN observation receipt changed')
        banks[phase] = {}
        for position, source in enumerate(cases):
            key = source['key']
            views = {v['id']: v for v in source['views']}
            incumbent = forward.raw_prediction(journal, ORDINARY, number, key)
            alt = predictions[EXTERNAL][key] if number == 1 else forward.raw_prediction(journal, EXTERNAL, number, key)
            if number == 2 and alt['schema_library_sha256'] != libraries['parse']['snapshot_sha256']:
                raise ValueError('The second batch must execute the captured first-batch PARSE artifact')
            readings, signatures = {}, []
            routes = {'incumbent': incumbent, 'parse': alt}
            if number == 1:
                routes['proposal'] = predictions[ORDINARY][key]
            for role, row in routes.items():
                result, ids = (restore_parse(db, source, row, schema, config) if role == 'parse'
                               else select_native(db, source, row, programs[role]))
                readings[role] = result
                signatures.append(public_inputs(db, ids))
                identities.update(ids)
            if len(set(signatures)) != 1:
                raise ValueError('Require the same actual public inputs and executor settings for every route')
            banks[phase][key] = same_controls({'position': position, 'views': views, 'answers': readings})
    if len(identities) != 40:
        raise ValueError('Use all 40 distinct actual EC and EV responses from B1 and B2')
    return banks, identities, grades.pop() if len(grades) == 1 else (), programs, {
        'B1_fit': sha(fit / 'terminal.json'), 'B1_observe': sha(first[0] / 'terminal.json'),
        'B2_observe': sha(following[0] / 'terminal.json')}


def report_forward(banks, routes, labels):
    outputs = {key: {name: signed.portfolio.compose(row['answers'], choice) for name, choice in routes.items()}
               for key, row in banks.items()}
    return joint.summary(banks, outputs, labels), outputs


def run():
    shared = signed.common
    parent, bound, terminal = shared.prior.checked.bound_result(motor)
    original_dev = read(parent / 'sealed_predictions.json')['fixed_DEV']
    _, cohort, dev_arms, study, _ = shared.previous.release.base_actor()
    _, _, roster = shared.previous.release.parallel.adoption.archive_context()
    train = {s['key']: s for batch in roster for s in batch if s['dataset'] == OE}
    dev = {s['key']: s for s in cohort if s['dataset'] == OE}
    if (len(train), len(dev), len(dev_arms)) != (32, 16, 5):
        raise ValueError('Require the original TRAIN cohort, public DEV cohort and all five fixed DEV arms')
    views = {split: {key: shared.previous.views_of(s) for key, s in sources.items()}
             for split, sources in (('train', train), ('dev', dev))}
    exclusions = {split: {key: {task: sorted(household.exclusions(view)) for task, view in bundle.items()}
                          for key, bundle in by_source.items()} for split, by_source in views.items()}
    category = {key: {task: shared.categories.source_proof(v) for task, v in bundle.items()}
                for key, bundle in views['train'].items()}
    amount = {key: motor.motor.source_proof(bundle['EV']) for key, bundle in views['train'].items()}

    def project(native, excluded):
        return {task: filter_claims(task, value, set(map(tuple, excluded[task]))) for task, value in native.items()}

    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        banks, reads, (name, train_hash), programs, seals = materials(db)
        dev_banks, dev_reads = {}, set()
        for arm, (folder, seal, score) in dev_arms.items():
            before = original_dev[arm]['after']
            after = {key: project(row, exclusions['dev'][key]) for key, row in before.items()}
            dev_banks[arm] = {'before': before, 'after': after}
            for key, row in before.items():
                changed = {task for task in PORTS if row[task] != after[key][task]}
                if changed:
                    shared.previous.physical_dev(db, dev[key], folder, seal, score, dev_reads, changed)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Use the exact original settled call records')
    matched = {}
    for phase, bank in banks.items():
        previous = {key: {**row, 'answers': {
            role: motor.project(shared.project(native, category[key]), amount[key]) for role, native in row['answers'].items()
        }} for key, row in bank.items()}
        after = {key: {**row, 'answers': {role: project(native, exclusions['train'][key])
                                         for role, native in row['answers'].items()}} for key, row in previous.items()}
        matched[phase] = {'before': previous, 'after': after}
    dev_grade = study['grading_paths'][OE]
    dev_hash = study['grading_file_sha256'][dev_grade]
    if ('train' not in Path(name).parts or sha(ROOT / name) != train_hash or 'dev' not in Path(dev_grade).parts
            or sha(ROOT / dev_grade) != dev_hash or bound['grade_sha256'] != {'train': train_hash, 'dev': dev_hash}):
        raise ValueError('Use the sealed original grading files')
    files = (__file__, household.__file__, household.illinois.__file__, signed.__file__, motor.__file__)
    binding = {'stage': STAGE, 'TEST_opened': False, 'frozen_B1_B2_receipts': seals, 'actual_programs': programs,
               'prior_fixed_DEV_terminal': terminal['terminal_sha256'], 'train_grade_sha256': train_hash,
               'dev_grade_sha256': dev_hash, 'exclusions_sha256': digest(exclusions), 'group_budget': 2,
               'archived_calls_sha256': {'TRAIN': digest(sorted(reads)), 'DEV': digest(sorted(dev_reads))},
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', exclusions)
    tag = immutable_json(out / 'sealed_predictions.json', {'chronological': matched, 'fixed_DEV': dev_banks})
    labels, dev_labels = read(ROOT / name), read(ROOT / dev_grade)
    audit = {split: shared.previous.validate_source_proofs(rows, reference) for split, rows, reference in (
        ('train', exclusions['train'], labels), ('dev', exclusions['dev'], dev_labels))}
    fit = {phase: signed.fit_choices(rows, ('incumbent', 'proposal', 'parse'), category,
                                     {key: labels[key] for key in rows}) for phase, rows in matched['fit'].items()}
    selected = {name: tuple(pick['route']) for name, pick in fit['after']['signed'].items()}
    supported = {role: route for role, route in selected.items() if 'proposal' not in route}
    routes = {**supported, 'historical_parse': ('parse', 'parse'), 'historical_incumbent': BASE_ROUTE}
    forward = {phase: report_forward(bank, routes, labels)[0] for phase, bank in matched['forward'].items()}
    for role, choice in selected.items():
        programs_for_task = {task: programs[reader] for task, reader in zip(PORTS, choice, strict=True)}
        payload = {'binding_sha256': out.name, 'filtered_B1_decision': fit['after']['signed'][role],
                   'B1_programs': programs_for_task, 'B2_archive_available': role in supported}
        immutable_json(out / 'TRAIN_batch_libraries' / f'{role}.json', sealed(payload, 'snapshot_sha256'))
    dev_scores = {arm: shared.previous.dev_compare(views['dev'], dev_labels, bank) for arm, bank in dev_banks.items()}
    release = (not any(v['known_exclusion_conflicts'] for v in audit.values())
               and not any(v['regressed'] for arm in dev_scores.values() for v in arm.values())
               and any(v['improved'] for arm in dev_scores.values() for v in arm.values()))
    summary = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag, 'fit': fit,
        'B2_native_scores': forward, 'unobserved_selected_routes': sorted(set(selected) - set(supported)),
        'source_exclusion_audit': audit, 'fixed_DEV': dev_scores, 'shared_DEV_release': release,
        'archived_TRAIN_reads': len(reads), 'archived_DEV_reads': len(dev_reads), 'ledger': ledger,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', summary)
    write_status(out, {'status': summary['status'], 'terminal_sha256': summary['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
