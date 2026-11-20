"""Test acquisition that distinguishes two supported OpenExempt reader candidates."""

import argparse
import sqlite3
from itertools import combinations
from pathlib import Path

from experiments import convergence_revision6_oe_portfolio as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_competing_port'
POINTER = HANDOFF / f'{STAGE}_current.json'
portfolio, archive = prior.portfolio, prior.archive


def choose(fit):
    gains = {tuple(key.split('+')): value for key, value in fit['native_fit_gain'].items()}
    groups = {int(pos): {tuple(code.split('+')): row for code, row in group.items()}
              for pos, group in fit['evidence'].items()}
    # Each rival independently clears the same TRAIN gate and changes the same single task.
    single_port = {route: portfolio.changed_ports(route)[0][0] for route, gain in gains.items()
                   if gain > 0 and len(portfolio.changed_ports(route)) == 1}
    options = []
    for positions in combinations(sorted(groups), min(prior.GROUP_BUDGET, len(groups))):
        for route, port in single_port.items():
            if not portfolio.admissible(groups, positions, route):
                continue
            for rival, rival_port in single_port.items():
                if port != rival_port or gains[rival] <= gains[route]:
                    continue
                repairs = {pos for pos in positions if groups[pos][route]['signed_repairs'] > 0}
                conflicts = {pos for pos in positions if groups[pos][rival]['introduced_cross_conflicts'] > 0
                             and not portfolio.candidates.refuted(groups[pos][route])}
                if any(a != b for a in repairs for b in conflicts):
                    rank = (gains[rival], gains[route], len(conflicts), positions, route)
                    options.append((rank, {'positions': list(positions), 'supported_route': list(route),
                                           'refuted_rival': list(rival), 'support_positions': sorted(repairs),
                                           'conflict_positions': sorted(conflicts)}))
    if options:
        return max(options, key=lambda row: row[0])[1]
    baseline = fit['selected']['candidate_driven']
    return {'positions': baseline['positions'], 'supported_route': [baseline['route'][t] for t in portfolio.PORTS],
            'refuted_rival': None, 'support_positions': [], 'conflict_positions': []}


def prepare():
    predecessor, bound, terminal = prior.checked.bound_result(prior)
    choices = {batch: choose(fit) for batch, fit in terminal['fit'].items()}
    if not any(row['refuted_rival'] for row in choices.values()):
        raise ValueError('At least one matched candidate needs a prospective contrast against a stronger rival')
    files = (__file__, prior.__file__, portfolio.__file__, portfolio.candidates.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'DEV_opened': False,
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files},
        'prior_portfolio_terminal': terminal['terminal_sha256'], 'fit_sha256': digest(terminal['fit']),
        'registered_choices_sha256': digest(choices), 'next_batch_grade_sha256': bound['grade_sha256'],
        'design': 'Compare the same two-group budget and candidate pool. Prefer a positive single-port '
                  'route with source-supported repair and distinct evidence of a new cross-task conflict '
                  'in its better-scoring same-port rival. Use the prior candidate strategy otherwise.',
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'fit_choices.json', choices)
    prior.snapshot(out, binding['source_sha256'])
    return out, binding, choices, predecessor, bound, terminal


def run(execute):
    out, binding, choices, predecessor, bound, previous = prepare()
    if (out / 'terminal.json').exists() or not execute:
        print(out)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, _, ev, grade_ref = archive.archive.history(db)
        ec = archive.extract(db, cases)
        stamps, ext = prior.prior.extend_with_archived_candidates(db, {b: cases[b] for b in prior.prior.BATCHES})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    ids = set(ev) | set(ec) | ext
    name, expected = grade_ref
    grade = ROOT / name
    if (ledger.get('reserved') or digest(sorted(ids)) != bound['physical_ids_sha256']
            or stamps != {int(k): v for k, v in bound_prior_candidates(bound).items()}
            or 'train' not in grade.parts or sha(grade) != expected or expected != binding['next_batch_grade_sha256']):
        raise ValueError('Preserve the actual physical candidate reads and original TRAIN grades')
    for entry in cases.values():
        for split in ('train', 'forward'):
            entry[split] = {k: prior.prior.same_controls(v) for k, v in entry[split].items()}
    if digest(cases) != bound['controlled_cases_sha256']:
        raise ValueError('Use exactly the same source pool and common rules as the archived controls')
    predictions = read(predecessor / 'sealed_predictions.json')
    forwards, measured = {}, {}
    for batch, case in cases.items():
        choice = choices[str(batch)]
        program = {task: case['programs'][role] for task, role in
                   zip(portfolio.PORTS, choice['supported_route'], strict=True)}
        immutable_json(out / 'trained_libraries' / f'B{batch}.json', sealed({
            'binding_sha256': out.name, 'choice': choice, 'reader_versions': program,
        }, 'snapshot_sha256'))
        for key, row in case['forward'].items():
            if key in forwards:
                raise ValueError('Each forward mother appears once')
            forwards[key] = row
            controls = predictions[key]
            measured[key] = {**controls, 'prior_candidate_driven': controls['candidate_driven'],
                             'candidate_driven': portfolio.compose(row['answers'], choice['supported_route'])}
    tag = immutable_json(out / 'sealed_predictions.json', measured)
    labels = read(grade)
    scores = archive.summary(forwards, measured, labels)
    per_batch = {batch: archive.summary(v['forward'], {k: measured[k] for k in v['forward']}, labels)
                 for batch, v in cases.items()}
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'fit_choices': choices, 'verified_archive_requests': len(ids), 'forward_mothers': len(forwards),
        'all_forward_TRAIN': scores, 'forward_by_batch': per_batch,
        'supports_expanded_validation': all(scores['paired_candidate_driven'][name]['paired_source_bootstrap_95'][0] > 0
                                            for name in ('answer_disagreement', 'chronological', 'prior_candidate_driven')),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger,
        'TEST_opened': False, 'DEV_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


def bound_prior_candidates(bound):
    _, spec, result = prior.checked.bound_result(prior.prior)
    if result['terminal_sha256'] != bound['prior_whole_reader_portfolio']:
        raise ValueError('Use the original matched external candidate bank')
    return spec['matched_portfolios']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args().execute)
