"""Evaluate the full B5 output of the B4 recipient-scoped update."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_b4_recipient_selection as parent
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_cni_scoped_adoption'
POINTER = HANDOFF / f'{STAGE}_current.json'
INCUMBENT, PROPOSAL = parent.ROUTES
CNI = parent.roles.CNI


def native_rows(source, label, native):
    for view in source['views']:
        task = view['id']
        row = native[task]
        grade = grade_view(CNI, view, label[task], row['answer'], row['evidence_sentence_ids'])
        yield {'source': source['key'], 'view': task, 'correct': grade['grade'],
               'grounded': grade['grade'] * grade['evidence_f1']}


def with_shared_proofs(source, native):
    return native | parent.common(source, native)


def fit_task_routes(sources, raw, labels):
    for_policy = {}
    for key, source in sources.items():
        for role, values in raw[key].items():
            for row in native_rows(source, labels[key], with_shared_proofs(source, values)):
                counts = for_policy.setdefault(row['view'], {route: [0.0, 0.0] for route in parent.ROUTES})
                counts[role][0] += row['correct']
                counts[role][1] += row['grounded']
    learned = {task: PROPOSAL if values[PROPOSAL] > values[INCUMBENT] else INCUMBENT
               for task, values in for_policy.items()}
    return for_policy, learned


def calibration(programs, grade):
    fit, spec, terminal = parent.roles.replay.bound.bound_stage(parent.fit_pointer(4))
    root = ROOT / spec['checkpoint_root']
    roster = parent.roles.RETENTION.load_roster(read(root / 'binding.json'))
    journal = parent.TrainingJournal(root, read(root / 'binding.json'), roster)
    folder = fit / 'candidates' / parent.ORDINARY / CNI
    past = read(folder / 'prior_TRAIN_regression.json')
    candidate = read(folder / 'measurements.json')
    decisions = read(fit / 'matched_decisions.json')
    decision = decisions['teacher'][parent.ORDINARY][CNI]
    if (digest(decisions) != terminal['matched_decisions_sha256']
            or digest(past) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or digest(candidate['predictions']) != decision['predictions_sha256']):
        raise ValueError('The native task control must use the exact original fit bank')
    sources, outputs, calls = {}, {}, set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch, cohort in enumerate(roster[:4], 1):
            for source in (s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'train'):
                key = source['key']
                if batch < 4:
                    entries = {INCUMBENT: past['before'][key], PROPOSAL: past['candidate'][key]}
                else:
                    record = read(journal.directory(parent.ORDINARY, 4) / 'predictions' / f'{digest(key)}.json')
                    if digest(record) != journal._observations(parent.ORDINARY, 4)['predictions'][key]:
                        raise ValueError('Preserve the B4 incumbent observation seal')
                    entries = {INCUMBENT: record['result'], PROPOSAL: candidate['predictions'][key]}
                for role, row in entries.items():
                    expected = parent.wire(source, programs[role], spec['executor'])
                    calls.add(parent.archived(db, source, row, programs[role], expected))
                sources[key] = source
                outputs[key] = {role: row['native'] for role, row in entries.items()}
    if (len(sources), len(calls)) != (12, 24) or 'train' not in grade.parts:
        raise ValueError('Fit only on the 12 original B1–B4 mothers and 24 bound responses')
    labels = {key: label for key, label in read(grade).items() if key in sources}
    return fit_task_routes(sources, outputs, labels), calls


def restore(out, forward, programs, wires):
    saved = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for path in (out / 'program_executions').glob('*/result.json'):
            row = read(path)
            trace, = row['traces']
            identity = trace['physical_call_id']
            key, = db.execute('select source from calls where id=?', (identity,)).fetchone()
            if key in saved or key not in forward or not row['core_executed']:
                raise ValueError('Require the three original, successful incumbent executions')
            native = parent.ProgramActor._native(forward[key]['source'], row)
            readout = {'execution': row, 'native': native}
            if parent.archived(db, forward[key]['source'], {'reads': [readout], 'native': native},
                               programs[INCUMBENT], wires[key][INCUMBENT]) != identity:
                raise ValueError('The restored execution differs from the original read')
            saved[key] = (native, identity)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if set(saved) != set(forward) or ledger.get('reserved'):
        raise ValueError('Every original B5 mother must keep both exact responses')
    return saved, ledger


def evaluate(sources, banks, labels):
    comparisons = {}
    for segment in ('all', 'verified_recipient_scope', 'other_hypotheses'):
        rows = {role: [
            row for key, output in bank.items() for row in native_rows(sources[key], labels[key], output)
            if segment == 'all' or (row['view'] in parent.TASKS) == (segment == 'verified_recipient_scope')
        ] for role, bank in banks.items()}
        comparisons[segment] = {
            'native': {role: {'units': len(cells), 'correct': sum(row['correct'] for row in cells),
                              'correct_class_evidence_F1': mean(row['grounded'] for row in cells)}
                       for role, cells in rows.items()},
            'paired_candidate_driven': {role: {
                measure: paired_source_effect(*[[{**row, 'grade': row[measure]} for row in cells]
                                                for cells in (controls, rows['candidate_driven'])])
                for measure in ('correct', 'grounded')
            } for role, controls in rows.items() if role != 'candidate_driven'},
        }
    return comparisons


def run():
    past_pointer = read(parent.POINTER)
    past = ROOT / past_pointer['artifact_root']
    lock = read(past / 'binding.json')
    prev = verify(read(past / 'terminal.json'), 'terminal_sha256')
    prepared, programs, _, choices, forward, wires, grade = parent.prepare_materials()
    keys = ('programs', 'B4_fit_sha256', 'calibration_archive_sha256', 'B5_wires_sha256', 'selection_sha256')
    if (past.name != digest(lock) or prev['terminal_sha256'] != past_pointer['terminal_sha256']
            or any(lock[key] != prepared[key] for key in keys) or prev['TEST_opened']
            or sha(grade) != lock['grade_sha256']
            or sha(past / 'sealed_predictions.json') != prev['predictions_sha256']):
        raise ValueError('Retain the locked B4 group choices and original B5 inputs')
    (fit_scores, native_scope), cal_reads = calibration(programs, grade)
    if digest(sorted(cal_reads)) != lock['calibration_archive_sha256']:
        raise ValueError('Use the exact matched fit requests for the stronger control')
    old, ledger = restore(past, forward, programs, wires)
    current = read(HANDOFF / 'run_state.json').get(STAGE, {})
    if (ledger != current.get('ledger_before')
            or any(ledger.get(status, 0) < total for status, total in prev['ledger'].items())):
        raise ValueError('This comparison only reuses settled physical requests on the continuous ledger')

    def group_route(choice):
        return {task: choice['route'] if task in parent.TASKS else INCUMBENT for task in native_scope}

    full_scores = {role: tuple(sum(values[role][i] for values in fit_scores.values()) for i in range(2))
                   for role in parent.ROUTES}
    full_route = max(parent.ROUTES, key=full_scores.__getitem__)
    routes = {role: group_route(choices[role]) for role in ('candidate_driven', 'chronological', 'answer_disagreement')}
    routes.update({
        'whole_native_fit': dict.fromkeys(native_scope, full_route),
        'per_hypothesis_native_fit': native_scope,
        'same_scope_native_fit': {task: role if task in parent.TASKS else INCUMBENT
                                  for task, role in native_scope.items()},
        'incumbent': dict.fromkeys(native_scope, INCUMBENT),
    })
    sources = {key: row['source'] for key, row in forward.items()}
    raws = {key: {INCUMBENT: old[key][0], PROPOSAL: row['proposal']} for key, row in forward.items()}
    shares = {key: {role: with_shared_proofs(sources[key], bank) for role, bank in rows.items()}
              for key, rows in raws.items()}
    banks = {policy: {key: {task: row[role][task] for task, role in assignments.items()}
                      for key, row in shares.items()} for policy, assignments in routes.items()}
    prior = read(past / 'sealed_predictions.json')['shared_source_rules']
    if any({key: {task: bank[key][task] for task in parent.TASKS} for key in bank} != prior[policy]
           for policy, bank in banks.items() if policy in ('candidate_driven', 'chronological', 'answer_disagreement')):
        raise ValueError('The full router must reproduce the prior recipient-only decisions')
    files = (__file__, parent.__file__, parent.roles.__file__, parent.ProgramActor.__module__.replace('.', '/') + '.py')
    spec = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'B4_selection_terminal': prev['terminal_sha256'],
        'B1_B4_grade_sha256': sha(grade), 'fit_scores_sha256': digest(fit_scores),
        'B5_archived_reads_sha256': digest(sorted({v[1] for v in old.values()} |
                                                 {v['archived_choice'] for v in forward.values()})),
        'source_sha256': {str((ROOT / path).resolve().relative_to(ROOT)): sha(ROOT / path) for path in files},
        'comparison': 'Retrospective use of full B5 native outputs. No B5 targets participate in choosing routes.',
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    snapshot(out, spec['source_sha256'])
    for name, assignments in routes.items():
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', sealed({
            'fit_batch': 4, 'binding_sha256': out.name, 'programs': {
                task: lock['programs'][role] for task, role in assignments.items()},
        }, 'snapshot_sha256'))
    tag = immutable_json(out / 'sealed_predictions.json', banks)
    performance = evaluate(sources, banks, read(grade))
    degree = performance['all']['paired_candidate_driven']
    advance = all(
        degree[arm]['correct']['paired_source_bootstrap_95'][0] > 0
        and degree[arm]['grounded']['mean_change'] >= 0
        for arm in ('chronological', 'answer_disagreement', 'whole_native_fit', 'per_hypothesis_native_fit',
                    'same_scope_native_fit')
    )
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'B1_B4_score_by_hypothesis': fit_scores, 'B1_B4_full_scores': full_scores,
        'B5_TRAIN': performance, 'hypotheses_using_proposal': {
            policy: sorted(task for task, role in assignments.items() if role == PROPOSAL)
            for policy, assignments in routes.items()
        }, 'archived_requests': {'fit': len(cal_reads), 'forward': 2 * len(forward)}, 'ledger': ledger,
        'support_expanded_validation': advance, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
