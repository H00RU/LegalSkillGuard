"""Trace the B8 admission gap with independently source-bound item claims."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_oe_b8_screened_dev as previous
from experiments import convergence_revision6_oe_joint_item_cap as calibration
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_item_witness as witness
from legal_skill_guard.paired_interfaces import convergence_oe_portfolio as portfolio
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_b8_item_witness'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit = previous.fit
PORTS = portfolio.PORTS


def check_reference(proofs, labels):
    checks = {}
    for task in PORTS:
        rows = [(key, asset, value) for key, claims in proofs.items() for asset, value in claims[task].items()]
        checks[task] = {
            'mothers': len({key for key, _, _ in rows}), 'claims': len(rows),
            'matches': sum(witness.observed(task, labels[key][task]['answer'], asset) ==
                           (value if task == 'EC' else {value}) for key, asset, value in rows),
        }
    return checks


def apply(views, native, proof):
    return {task: witness.project(views[task], native[task], proof[task]) for task in PORTS}


def fit_routes(bank, labels, categories, source_proofs, *, shared):
    combinations = portfolio.routes(fit.ROLES)
    predictions, groups, counts = {}, {}, {}
    for key, row in bank.items():
        src = row['views']
        answers = {name: {**result, 'EC': witness.identity.bind(src['EC'], result['EC'])}
                   for name, result in row['answers'].items()}
        if shared:
            answers = {name: apply(src, result, source_proofs[key]) for name, result in answers.items()}
        entering = answers[portfolio.ENTERING]
        joint = fit.signed.proofs(row, categories[key])
        predictions[key], groups[row['position']], counts[row['position']] = {}, {}, {}
        for route in combinations:
            paired = portfolio.compose(answers, route)
            predictions[key][route] = paired
            new = {task: witness.compare(task, entering[task], paired[task], source_proofs[key][task])
                   for task in PORTS}
            counts[row['position']]['+'.join(route)] = {
                task: {'witnessed_repairs': len(delta[0]), 'new_errors': len(delta[1])}
                for task, delta in new.items()
            }
            evidence = fit.signed.direction.screen(entering, paired, *joint)
            groups[row['position']][route] = {
                **evidence,
                'signed_repairs': evidence['signed_repairs'] + sum(len(d[0]) for d in new.values()),
                'introduced_literal_errors': evidence['introduced_literal_errors'] + sum(len(d[1]) for d in new.values()),
            }
    means = {route: mean(row['grade'] for row in cells)
             for route, cells in fit.signed.archive.scored(bank, predictions, labels).items()}
    gains = {route: value - means[portfolio.BASE] for route, value in means.items()}
    selected = portfolio.select(groups, gains, fit.ROLES, fit.common.prior.GROUP_BUDGET)
    for policy in selected.values():
        policy['positions'] = [i + 1 for i in policy['positions']]
        policy['route'] = list(policy['route'])
    return {
        'selected': selected,
        'native_fit_gain': {'+'.join(path): gain for path, gain in gains.items()},
        'counts_by_train_position': {str(i + 1): v for i, v in counts.items()},
    }


def route(archive, choices):
    missing = {policy: {task: role for task, role in zip(PORTS, pick, strict=True) if role not in archive}
               for policy, pick in choices.items()}
    banks = {policy: {key: {task: archive[role][key][task] for task, role in zip(PORTS, pick, strict=True)}
                      for key in archive['incumbent']} for policy, pick in choices.items() if not missing[policy]}
    return banks, {policy: unavailable for policy, unavailable in missing.items() if unavailable}


def run():
    _, cap, cap_end = previous.release.checked.bound_result(calibration)
    mode = cap_end['TRAIN_convention']
    if (mode != cap['cap_convention'] or cap_end['B7_calibration']['discriminating_positions'] < 2
            or cap_end['B7_calibration'][mode + '_matches'] != cap_end['B7_calibration']['discriminating_positions']):
        raise ValueError('Use the earlier settled benchmark cap convention')
    fit_spec, fit_end, _ = previous.programs()
    fit_path = ROOT / read(fit.POINTER)['artifact_root']
    original = read(fit_path / 'predictions.json')['TRAIN']['after']
    trained_categories = {key: {task: fit.common.categories.source_proof(view)
                                for task, view in row['views'].items()} for key, row in original.items()}
    dev_spec, dev_end, dev_banks = previous.release.previous.previous.locked_result(
        previous.POINTER, 'sealed_predictions.json', 'predictions_sha256',
    )
    if dev_spec['prior_B8_TRAIN_terminal'] != fit_end['terminal_sha256']:
        raise ValueError('Use the exact paired B8 results, including the newly measured incumbent')
    _, spec, sources, dev_grade, categories, _, archived, _ = previous.prepare()
    if spec != dev_spec:
        raise ValueError('Do not change the fixed DEV source or already matched execution')
    dev_views = {key: fit.common.previous.views_of(source) for key, source in sources.items()}
    train_proofs = {key: {task: witness.proof(view, mode) for task, view in row['views'].items()}
                    for key, row in original.items()}
    dev_proofs = {key: {task: witness.proof(view, mode) for task, view in views.items()}
                  for key, views in dev_views.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        train, ids, (name, tag), archived_fit = fit.b8_materials(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if archived_fit != fit_spec['provenance'] or set(train) != set(original) or ledger != dev_end['ledger']:
        raise ValueError('Only use the prior B8 proposal receipts and settled fixed DEV requests')
    grade = ROOT / name
    if 'train' not in grade.parts or sha(grade) != tag:
        raise ValueError('Fit only with the original four TRAIN references')
    original_labels = read(grade)
    labels = {key: original_labels[key] for key in original}
    empty_proofs = {key: {task: {} for task in PORTS} for key in original}
    fits = {
        phase: fit_routes(original, labels, trained_categories, proofs, shared=project)
        for phase, proofs, project in (
            ('category_and_identity_only', empty_proofs, False),
            ('screen_with_item_witnesses', train_proofs, False),
            ('common_item_projection', train_proofs, True),
        )
    }
    common = {role: {key: previous.common_output(row, sources[key], categories['dev']) for key, row in values.items()}
              for role, values in archived.items()}
    common['incumbent'] = dev_banks['common_source_rules']['candidate_driven']
    fixed = {role: {key: apply(dev_views[key], native, dev_proofs[key]) for key, native in rows.items()}
             for role, rows in common.items()}
    comparisons, missing = {}, {}
    for phase, selection in fits.items():
        chosen = {policy: row['route'] for policy, row in selection['selected'].items()}
        chosen['adopted_ordinary'] = ['proposal', 'proposal']
        comparisons[phase], missing[phase] = route(fixed if phase == 'common_item_projection' else common, chosen)
    diagnostics = route(fixed, dev_spec['TRAIN_locked_routes'])[0]
    bindings = {
        'stage': STAGE, 'TEST_opened': False, 'B7_cap_terminal': cap_end['terminal_sha256'],
        'B8_fit_terminal': fit_end['terminal_sha256'], 'B8_fixed_DEV_terminal': dev_end['terminal_sha256'],
        'physical_train_calls_sha256': digest(sorted(ids)), 'TRAIN_grade_sha256': tag,
        'DEV_grade_sha256': sha(dev_grade), 'views_and_claims_sha256': digest([train_proofs, dev_proofs]),
        'TRAIN_fit_sha256': digest(fits), 'source_sha256': {
            str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
                __file__, witness.__file__, witness.federal.__file__, witness.title.__file__,
                previous.__file__, portfolio.__file__,
            )
        },
    }
    out = BASE / STAGE / digest(bindings)
    immutable_json(out / 'binding.json', bindings)
    fit.previous.snapshot(out, bindings['source_sha256'])
    pred = immutable_json(out / 'sealed_predictions.json', {'selected': comparisons, 'common_projection': diagnostics})
    dev_labels = read(dev_grade)
    positions = {key: i for i, key in enumerate(sources, 1)}
    scores = {phase: previous.scores(banks, dev_labels, positions) for phase, banks in comparisons.items()
              if 'candidate_driven' in banks}
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred,
        'train_fits': fits, 'missing_exact_fixed_DEV_carriers': missing, 'fixed_DEV_scores': scores,
        'fixed_original_routes_after_common_projection': previous.scores(diagnostics, dev_labels, positions),
        'source_reference_checks': {'TRAIN_B8': check_reference(train_proofs, labels),
                                    'fixed_DEV': check_reference(dev_proofs, dev_labels)},
        'archived_TRAIN_reads': len(ids),
        'matched_fixed_DEV_reads': dev_end['physical_exact_DEV_calls_reused'] + dev_end['new_executor_requests'],
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
