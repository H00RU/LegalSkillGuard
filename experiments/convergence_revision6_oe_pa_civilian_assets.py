"""Test whether explicit civilian-item exclusions improve M2 update selection."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_oe_oregon_property as prior
from experiments import convergence_revision6_oe_signed_direction as screening
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_pa_civilian_assets as civilian
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_pa_civilian_assets'
POINTER = HANDOFF / f'{STAGE}_current.json'
previous = prior.previous
portfolio, common, archive = screening.portfolio, screening.common, screening.archive
checked = common.prior.checked
PORTS = portfolio.PORTS


def proof_for(views):
    return {task: civilian.source_proof(view) for task, view in views.items()}


def project(native, proof):
    return {task: civilian.apply(task, native[task], proof[task]) for task in PORTS}


def shared(row, key, reader, categories, oregon):
    views = row['views']
    bank = prior.fit.controlled_read(
        row['answers'][reader], views, categories[key], prior.fit.b8.homestead.group_proof(key, views),
    )
    bank = {**bank, 'EC': previous.previous.checked_ec(views['EC'], bank['EC'], categories[key]['EC'])}
    amount = prior.motor.motor.source_proof(views['EV'])
    bank = prior.motor.project(prior.motor.project(bank, amount), oregon[key])
    return previous.apply_portfolio(bank, {task: previous.scope.compile_proof(view) for task, view in views.items()})


def fit_update(batch, labels, categories, proofs, oregon):
    readers = tuple(next(iter(batch.values()))['answers'])
    routes = portfolio.routes(readers)
    native, old_groups, route_groups, new_groups, changes = {}, {}, {}, {}, []
    incomplete = {}
    for key, row in batch.items():
        position = row['position']
        raw = {reader: shared(row, key, reader, categories, oregon) for reader in readers}
        repaired = {reader: project(answer, proofs[key]) for reader, answer in raw.items()}
        native[key] = {route: portfolio.compose(repaired, route) for route in routes}
        complete_group = all(value is not None for answers in row['answers'].values() for value in answers.values())
        if not complete_group:
            incomplete[position] = {reader: [task for task, result in answers.items() if result is None]
                                    for reader, answers in row['answers'].items()}
        expected = screening.proofs(row, categories[key])
        entering = portfolio.compose(row['answers'], portfolio.BASE)
        if any(value is None for value in entering.values()):
            continue
        if complete_group:
            old_groups[position] = {}
        route_groups[position] = {}
        new_groups[position] = {}
        raw_entering = portfolio.compose(raw, portfolio.BASE)
        for route in routes:
            candidate = portfolio.compose(row['answers'], route)
            if any(value is None for value in candidate.values()):
                # This assignment has no comparable joint read on the group.
                # The existing paid request stays in the budget and native fit.
                unknown = dict.fromkeys(
                    (*portfolio.candidates.VIOLATIONS, 'signed_repairs', 'answer_disagreement', 'incumbent_risk'), 0,
                )
                route_groups[position][route] = new_groups[position][route] = unknown
                continue
            before = screening.direction.screen(entering, candidate, *expected)
            raw_proposal = portfolio.compose(raw, route)
            checked_rows = {task: civilian.screen(task, raw_entering[task], raw_proposal[task], proofs[key][task])
                            for task in PORTS}
            introduced = sum(len(row['introduced']) for row in checked_rows.values())
            retired = sum(len(row['retired']) for row in checked_rows.values())
            if introduced or retired:
                changes.append({'position': position, 'route': list(route),
                                'new_invalid_claims': introduced, 'explicit_withdrawals': retired})
            if complete_group:
                old_groups[position][route] = before
            route_groups[position][route] = before
            new_groups[position][route] = {
                **before, 'introduced_literal_errors': before['introduced_literal_errors'] + introduced,
                'signed_repairs': before['signed_repairs'] + retired,
            }
    means = {route: mean(unit['grade'] for unit in rows)
             for route, rows in archive.scored(batch, native, labels).items()}
    gains = {route: value - means[portfolio.BASE] for route, value in means.items()}
    budget = common.prior.GROUP_BUDGET
    old_choices, route_choices, new_choices = (
        portfolio.select(groups, gains, readers, budget) for groups in (old_groups, route_groups, new_groups)
    )
    return {'shared_native_fits': {'+'.join(path): value for path, value in means.items()},
            'complete_groups_only': old_choices, 'without_new_category_witnesses': route_choices,
            'with_new_category_witnesses': new_choices, 'added_evidence': changes,
            'incomplete_reader_results': incomplete}


def run():
    frozen, cumulative, fixed = previous.previous.locked_result(prior.POINTER, 'sealed_predictions.json',
                                                                   'predictions_sha256')
    category_root, category_lock, _ = checked.bound_result(common)
    category = read(category_root / 'source_proofs.json')
    if digest(category) != category_lock['evidence_sha256']:
        raise ValueError('Use the shared original asset category evidence')
    _, old_lock, old_endpoint = checked.bound_result(common.prior)
    _, cohort, original, study, _ = previous.compare.release.base_actor()
    _, _, roster = previous.compare.release.parallel.adoption.archive_context()
    dataset = prior.fit.b1.OE
    train = {row['key']: row for batch in roster for row in batch if row['dataset'] == dataset}
    dev = {row['key']: row for row in cohort if row['dataset'] == dataset}
    populations = {'train': train, 'dev': dev}
    if (len(train), len(dev), len(original)) != (32, 16, 5) or any(
        row['project_split'] != split for split, rows in populations.items() for row in rows.values()
    ):
        raise ValueError('Keep original source populations and all fixed DEV readers')
    proofs = {split: {key: proof_for(previous.for_views(row)) for key, row in rows.items()}
              for split, rows in populations.items()}
    oregon = {key: prior.source_proof(row) for key, row in train.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
            raise ValueError('Require a settled match')
        banks, (train_grade, train_hash), train_reads = screening.restore_reads(db, old_lock, old_endpoint)
        dev_banks, dev_reads = {}, set()
        for reader, (folder, seal, grade) in original.items():
            before = fixed['DEV'][reader]['after']
            after = {key: project(answer, proofs['dev'][key]) for key, answer in before.items()}
            dev_banks[reader] = {'before': before, 'after': after}
            for key, native in before.items():
                changed = {task for task in PORTS if native[task] != after[key][task]}
                if changed:
                    previous.compare.physical_dev(db, dev[key], folder, seal, grade, dev_reads, changed)
    dev_grade = study['grading_paths'][dataset]
    grades = {'train': (train_grade, train_hash), 'dev': (dev_grade, study['grading_file_sha256'][dev_grade])}
    if train_reads & dev_reads or any(
        split not in Path(path).parts or sha(ROOT / path) != tag or tag != frozen['grade_sha256'][split]
        for split, (path, tag) in grades.items()
    ):
        raise ValueError('Use the exact original TRAIN and fixed DEV reference bytes')
    train_labels = read(ROOT / train_grade)
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'previous_valuation_terminal': cumulative['terminal_sha256'],
        'prior_portfolio_terminal': old_endpoint['terminal_sha256'], 'proofs_sha256': digest(proofs),
        'groups_per_screen': common.prior.GROUP_BUDGET, 'edited_source_requests': 0,
        'original_response_sha256': digest(sorted(train_reads | dev_reads)),
        'grade_sha256': {split: tag for split, (_, tag) in grades.items()},
        'source_sha256': {str(Path(file).relative_to(ROOT)): sha(Path(file)) for file in (
            __file__, civilian.__file__, screening.__file__, prior.__file__, portfolio.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    prior.fit.b1.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)

    fits, forward, predictions = {}, {}, {}
    for batch, pages in banks.items():
        fit = fit_update(pages['train'], train_labels, category['train'], proofs['train'], oregon)
        fits[batch] = fit
        adopted = fit['with_new_category_witnesses']
        immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}.json', sealed({
            'binding_sha256': out.name, 'fit_batch': batch,
            'original_program_roles': tuple(next(iter(pages['train'].values()))['answers']),
            'decisions': adopted,
        }, 'snapshot_sha256'))
        for key, row in pages['forward'].items():
            if key in forward:
                raise ValueError('Independent forward sources must not be counted twice')
            forward[key] = row
            common_readers = {reader: project(shared(row, key, reader, category['train'], oregon), proofs['train'][key])
                              for reader in row['answers']}
            old = fit['without_new_category_witnesses']['candidate_driven']
            routes = {name: value['route'] for name, value in adopted.items()}
            routes['without_new_category_witnesses'] = old['route']
            routes['complete_groups_only'] = fit['complete_groups_only']['candidate_driven']['route']
            predictions[key] = {name: portfolio.compose(common_readers, path) for name, path in routes.items()}
    if len(forward) != 16:
        raise ValueError('Keep complete next-batch original TRAIN on all four transitions')
    tag = immutable_json(out / 'sealed_predictions.json', {'forward_TRAIN': predictions, 'fixed_DEV': dev_banks})
    labels = {'train': train_labels, 'dev': read(ROOT / dev_grade)}
    audits = {split: {
        task: {'reviewed': sum(sum(len(items) for items in by_task[task][0].values()) for by_task in by_key.values()),
               'reference_conflicts': sum(len(civilian.wrong_claims(
                   task, labels[split][key][task]['answer'], by_task[task])) for key, by_task in by_key.items())}
        for task in PORTS
    } for split, by_key in proofs.items()}
    native = archive.summary(forward, predictions, train_labels)
    fixed_scores = {reader: previous.dev_summary(bank, labels['dev']) for reader, bank in dev_banks.items()}
    shared_improved = (
        all(not row['reference_conflicts'] for split in audits.values() for row in split.values())
        and all(not row['regressed'] for bank in fixed_scores.values() for row in bank.values())
        and any(row['improved'] for bank in fixed_scores.values() for row in bank.values())
    )
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'shared_source_rule': shared_improved, 'source_audit': audits, 'M2_fits': fits,
        'forward_original_TRAIN': native, 'forward_mothers': len(forward), 'fixed_DEV': fixed_scores,
        'reused_response_counts': {'TRAIN': len(train_reads), 'DEV': len(dev_reads)},
        'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
