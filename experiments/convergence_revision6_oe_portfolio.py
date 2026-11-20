"""Replay two-group OpenExempt acquisition with independently assignable ports."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_agreement_disclosure_release as checked
from experiments import convergence_revision6_oe_candidate_group as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import convergence_oe_portfolio as portfolio
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_portfolio'
POINTER = HANDOFF / f'{STAGE}_current.json'
GROUP_BUDGET = 2
archive = prior.archive


def group(row, all_routes):
    titles, exact, normalized = archive.facts(row['views'])
    exact.update(dict.fromkeys(archive.pa_items.exclusions(normalized['EC']), False))
    ev_exclusions = archive.pa_items.exclusions(normalized['EV'])
    values, cap = archive.archive.acquisition.public_bounds(normalized['EV'])
    before = portfolio.compose(row['answers'], portfolio.BASE)
    return {route: archive.joint.evidence(
        before, portfolio.compose(row['answers'], route), titles, exact, values, cap,
        require_category=True, ev_excluded=ev_exclusions,
    ) for route in all_routes}


def fit(cases, labels, readers):
    all_routes = portfolio.routes(readers)
    training = {key: {route: portfolio.compose(row['answers'], route) for route in all_routes}
                for key, row in cases.items()}
    score = archive.scored(cases, training, labels)
    fit_scores = {route: mean(unit['grade'] for unit in values) for route, values in score.items()}
    gain = {route: value - fit_scores[portfolio.BASE] for route, value in fit_scores.items()}
    groups = {
        row['position']: group(row, all_routes)
        for row in cases.values()
        if all(port is not None for values in row['answers'].values() for port in values.values())
    }
    return groups, gain, portfolio.select(groups, gain, readers, GROUP_BUDGET)


def run():
    _, old_spec, old = checked.bound_result(prior)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, excluded, ev, grade_ref = archive.archive.history(db)
        ec = archive.extract(db, cases)
        stamps, extra = prior.extend_with_archived_candidates(db, {b: cases[b] for b in prior.BATCHES})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    owned = set(ev) | set(ec) | extra
    if (list(cases) != [3, 4, 6, 7] or ledger.get('reserved') or extra & (set(ev) | set(ec))
            or stamps != {int(k): v for k, v in old_spec['matched_portfolios'].items()}):
        raise ValueError('Use the four originally matched forward transitions and the same external readers')
    filename, tag = grade_ref
    grade = ROOT / filename
    if 'train' not in grade.parts or sha(grade) != tag:
        raise ValueError('Use the exact original OpenExempt TRAIN grade')
    for entry in cases.values():
        for split in ('train', 'forward'):
            entry[split] = {k: prior.same_controls(row) for k, row in entry[split].items()}
    files = (__file__, portfolio.__file__, archive.__file__, prior.__file__, archive.joint.__file__)
    spec = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False,
        'prior_whole_reader_portfolio': old['terminal_sha256'], 'matched_transitions': list(cases),
        'excluded_transitions': excluded, 'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files},
        'grade_sha256': tag, 'controlled_cases_sha256': digest(cases), 'physical_ids_sha256': digest(sorted(owned)),
        'groups_per_selector': GROUP_BUDGET, 'logical_eval_requests_per_source': 2,
        'design': 'Archived TRAIN replay. All selectors can combine the same actual EC and EV reader versions. '
                  'Screened policies verify a source repair per changed port and check the assembled route for '
                  'new conflicts. Rank on the fit batch alone, then score the original next batch.',
    }
    root = BASE / STAGE / digest(spec)
    immutable_json(root / 'binding.json', spec)
    snapshot(root, spec['source_sha256'])
    fits, forward, bank = {}, {}, {}
    for batch, pair in cases.items():
        train = pair['train']
        labels = {key: value for key, value in read(grade).items() if key in train}
        readers = tuple(reader for reader in prior.ROLES if reader in pair['programs'])
        groups, gains, decisions = fit(train, labels, readers)
        fits[batch] = {
            'program_count': len(readers), 'compound_candidates': len(gains),
            'native_fit_gain': {'+'.join(route): value for route, value in gains.items()},
            'selected': {policy: {**choice, 'route': dict(zip(portfolio.PORTS, choice['route'], strict=True))}
                         for policy, choice in decisions.items()},
            'available_groups': sorted(groups),
            'evidence': {position: {'+'.join(route): row for route, row in values.items()}
                         for position, values in groups.items()},
        }
        for policy, choice in fits[batch]['selected'].items():
            assigned = {task: pair['programs'][reader] for task, reader in choice['route'].items()}
            compiled = sealed({'batch': batch, 'binding_sha256': root.name, 'decision': choice,
                               'reader_versions': assigned}, 'snapshot_sha256')
            immutable_json(root / 'TRAIN_batch_libraries' / f'B{batch}' / f'{policy}.json', compiled)
        for key, row in pair['forward'].items():
            if key in forward:
                raise ValueError('Forward source cannot contribute twice to the native estimate')
            forward[key] = row
            bank[key] = {'incumbent': portfolio.compose(row['answers'], portfolio.BASE), **{
                name: portfolio.compose(row['answers'], choice['route']) for name, choice in decisions.items()}}
    pred = immutable_json(root / 'sealed_predictions.json', bank)
    labels = read(grade)
    summary = archive.summary(forward, bank, labels)
    per_batch = {batch: archive.summary(pair['forward'], {k: bank[k] for k in pair['forward']}, labels)
                 for batch, pair in cases.items()}
    effects = summary['paired_candidate_driven']
    advance = all(effects[name]['paired_source_bootstrap_95'][0] > 0
                  for name in portfolio.candidates.POLICIES if name != 'candidate_driven')
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': root.name, 'predictions_sha256': pred,
        'forward_mothers': len(forward), 'all_forward_TRAIN': summary, 'forward_TRAIN': per_batch,
        'fit': fits, 'support_expanded_validation': advance, 'verified_archive_requests': len(owned),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(root / 'terminal.json', terminal)
    write_status(root, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(root)


if __name__ == '__main__':
    run()
