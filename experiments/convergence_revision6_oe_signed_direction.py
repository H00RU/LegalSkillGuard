"""Test source-attributed cross-task screening on the original OpenExempt proposals."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_oe_oregon_eligibility as oregon
from experiments import convergence_revision6_oe_item_categories as common
from experiments import convergence_revision6_oe_missing_forward_fit as missing
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_signed_direction as direction
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_signed_direction'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, portfolio = common.archive, common.portfolio
competing = common.competing
PORTS = portfolio.PORTS


def proofs(row, category):
    views = row['views']
    titles, exact_ec, normalized = archive.facts(views)
    excluded = {}
    for port in PORTS:
        view = normalized[port]
        ignored, instruments = oregon.local_terms(view)
        extra = {(asset, oregon.VEHICLE) for asset in ignored}
        excluded[port] = (extra | archive.pa_items.exclusions(view)
                          | common.previous.policy.exclusions(views[port]) | set(map(tuple, category[port]['exclude'])))
        if port == 'EC':
            exact_ec.update(dict.fromkeys(excluded[port], False))
            exact_ec.update({(asset, citation): True for asset, facts in category[port]['add'].items()
                             for citation in facts})
            exact_ec.update({(asset, oregon.PICTURES): True for asset in instruments})
    values, item_cap = archive.archive.acquisition.public_bounds(normalized['EV'])
    return titles, exact_ec, values, item_cap, excluded['EV']


def restore_reads(db, spec, previous):
    cases, _, ev, grade = archive.archive.history(db)
    ec = archive.extract(db, cases)
    stamps, external = common.prior.prior.extend_with_archived_candidates(
        db, {batch: cases[batch] for batch in common.prior.prior.BATCHES},
    )
    ids = set(ev) | set(ec) | external
    if (digest(sorted(ids)) != spec['physical_ids_sha256']
            or stamps != {int(k): v for k, v in competing.bound_prior_candidates(spec).items()}):
        raise ValueError('Use the original independently verified physical candidate reads')
    banks = {}
    for batch, pair in cases.items():
        fit = previous['fit'][str(batch)]
        if not fit['evidence'] or len(pair['train']) != 4 or len(pair['forward']) != 4:
            raise ValueError('Use the complete original candidate and next-batch source cohorts')
        banks[batch] = {phase: {key: common.prior.prior.same_controls(row) for key, row in pair[phase].items()}
                        for phase in ('train', 'forward')}
    return banks, grade, ids


def fit_choices(bank, roles, category, labels):
    routes = portfolio.routes(roles)
    native, measured = {}, {}
    for key, row in bank.items():
        answer = row['answers']
        common_native = {role: common.project(a, category[key]) for role, a in answer.items()}
        native[key] = {path: portfolio.compose(common_native, path) for path in routes}
        if all(cell is not None for value in answer.values() for cell in value.values()):
            source_inputs = proofs(row, category[key])
            entering = portfolio.compose(answer, portfolio.BASE)
            measured[row['position']] = {path: direction.screen(entering, portfolio.compose(answer, path), *source_inputs)
                                         for path in routes}
    scores = archive.scored(bank, native, labels)
    average = {path: mean(r['grade'] for r in rows) for path, rows in scores.items()}
    gains = {path: value - average[portfolio.BASE] for path, value in average.items()}
    unsigned = {pos: {path: {**row, 'introduced_cross_conflicts': row['introduced_undirected_conflicts']}
                      for path, row in group.items()} for pos, group in measured.items()}
    selectors = {name: portfolio.select(groups, gains, roles, common.prior.GROUP_BUDGET)
                 for name, groups in (('signed', measured), ('unsigned', unsigned))}
    result = {name: {role: {**v, 'route': list(v['route'])} for role, v in compare.items()}
              for name, compare in selectors.items()}
    result['native_fit_gain'] = {'+'.join(path): value for path, value in gains.items()}
    result['groups'] = {pos: {'+'.join(path): value for path, value in group.items()} for pos, group in measured.items()}
    return result


def run():
    proof_root, proof_spec, latest = common.prior.checked.bound_result(common)
    _, old_spec, previous = common.prior.checked.bound_result(common.prior)
    _, missing_spec, missed = common.prior.checked.bound_result(missing)
    source = read(proof_root / 'source_proofs.json')
    if digest(source) != proof_spec['evidence_sha256'] or old_spec['grade_sha256'] != missing_spec['grade_sha256']:
        raise ValueError('Continue from the exact cumulative proof and original fit archive')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        banks, (grade_ref, grade_hash), train_reads = restore_reads(db, old_spec, previous)
        only_fit, extra = {}, set()
        for batch in (2, 5):
            rows, ids, tag, _ = missing.original_fit(db, batch)
            if tag != (grade_ref, grade_hash) or ids & extra:
                raise ValueError('Use the original fit-only responses under the same TRAIN references')
            only_fit[batch] = rows
            extra.update(ids)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    grade = ROOT / grade_ref
    if ('train' not in grade.parts or sha(grade) != grade_hash or len(extra) != 32 or ledger.get('reserved')
            or digest(sorted(extra)) != missing_spec['requests_sha256']):
        raise ValueError('Bind the original TRAIN grades and every physical fit-only response')
    paths = (__file__, direction.__file__, common.__file__, missing.__file__, oregon.__file__, portfolio.__file__, archive.__file__)
    binding = {
        'stage': STAGE, 'prior_common_source_proofs': latest['terminal_sha256'],
        'prior_portfolio': previous['terminal_sha256'], 'prior_fit_only': missed['terminal_sha256'],
        'TRAIN_grade_sha256': grade_hash, 'matched_forward_transitions': sorted(banks), 'fit_only_transitions': sorted(only_fit),
        'physical_request_ids_sha256': digest(sorted(train_reads | extra)),
        'groups_per_screened_policy': common.prior.GROUP_BUDGET, 'TEST_opened': False, 'DEV_scores_used': False,
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    common.prior.snapshot(out, binding['source_sha256'])
    labels = read(grade)
    fits, forward, predictions = {}, {}, {}
    for batch in sorted(banks.keys() | only_fit.keys()):
        train = banks[batch]['train'] if batch in banks else only_fit[batch]
        readers = tuple(next(iter(train.values()))['answers'])
        fit_labels = {key: labels[key] for key in train}
        result = fit_choices(train, readers, source['train'], fit_labels)
        fits[batch] = result
        immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}.json', sealed({
            'binding_sha256': out.name, 'decisions': {scope: result[scope] for scope in ('signed', 'unsigned')},
            'readers': list(readers),
        }, 'snapshot_sha256'))
        for key, row in banks.get(batch, {}).get('forward', {}).items():
            if key in forward:
                raise ValueError('A forward TRAIN mother can only count once')
            forward[key] = row
            shared = {role: common.project(x, source['train'][key]) for role, x in row['answers'].items()}
            predictions[key] = {name: portfolio.compose(shared, result[scope][policy]['route'])
                                for name, scope, policy in (
                                    ('candidate_driven', 'signed', 'candidate_driven'),
                                    ('chronological', 'signed', 'chronological'),
                                    ('answer_disagreement', 'signed', 'answer_disagreement'),
                                    ('incumbent_risk', 'signed', 'incumbent_risk'),
                                    ('undirected_candidate_driven', 'unsigned', 'candidate_driven'),
                                    ('native_fit_only', 'signed', 'native_fit_only'),
                                )}
    changed = {batch: {name: fit['signed'][name]['route'] != fit['unsigned'][name]['route']
                       for name in fit['signed']} for batch, fit in fits.items()}
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    native = archive.summary(forward, predictions, labels)
    b7 = fits[7]['groups'][1]['incumbent+proposal']
    end = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'fits': fits, 'signed_changed_adoption': changed, 'forward_TRAIN': native, 'forward_mothers': len(forward),
        'known_B7_conflict_directions': {'unsigned_count': b7['introduced_undirected_conflicts'],
                                         'EC': len(b7['new_cross_task_witnesses']['EC']),
                                         'EV': len(b7['new_cross_task_witnesses']['EV']),
                                         'unresolved': len(b7['new_cross_task_witnesses']['unresolved'])},
        'fit_only_requires_new_reads': {batch: any(fits[batch]['signed']['candidate_driven']['route']
                                                   != fits[batch]['signed'][role]['route']
                                                   for role in ('chronological', 'answer_disagreement'))
                                       for batch in only_fit},
        'reused_ARCHIVE_requests': len(train_reads | extra),
        'source_bank_request_counts': {'matched': len(train_reads), 'fit_only': len(extra), 'overlap': len(train_reads & extra)},
        'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'DEV_opened': False, 'ledger': ledger,
        'supports_expanded_validation': all(native['paired_candidate_driven'][role]['paired_source_bootstrap_95'][0] > 0
                                            for role in ('chronological', 'answer_disagreement')),
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', end)
    write_status(out, {'status': end['status'], 'terminal_sha256': end['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
