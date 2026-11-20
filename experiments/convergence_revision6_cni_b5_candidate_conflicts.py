"""Compare joint B5 candidate acquisition on the original ContractNLI TRAIN."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_b4_candidate_portfolio as b4
from experiments import convergence_revision6_cni_b4_portfolio_later as replay
from experiments import convergence_revision6_cni_b5_assertion_screen as assertion
from experiments import convergence_revision6_cni_employee_witness_projection as employee
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_candidate_conflict_screen as screen
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b5_candidate_conflicts'
POINTER = HANDOFF / f'{STAGE}_current.json'
BATCH = 5
CNI, archive, parent = b4.CNI, b4.archive, b4.parent
ARMS = {'ordinary': parent.ORDINARY, 'parse': archive.EXTERNAL_ARM}
ORIGINAL_DECISIONS = {'ordinary': 'incumbent', 'parse': 'candidate'}


def proofs(source):
    assertions, copied, _ = assertion.proof_for(source)
    known = {**b4.current_proofs(source), **assertions}
    if len(paths := employee.base.source_proof(source)) == 1:
        known[employee.TASK] = employee.base.employee.project({}, paths)
    access_graph = employee.base.existing.source_paths(source)
    return known, copied, access_graph


def project(source, native, known, copied, access_graph):
    common = assertion.shared(source, native, known, copied)
    return employee.project_native(common, access_graph)


def original_prefix(db, journal, prefix, executor):
    fit, config, stop = archive.bound_stage(parent.fit_pointer(BATCH))
    observed, obs_config, before = archive.bound_stage(parent.observe_pointer(BATCH))
    decisions = read(fit / 'matched_decisions.json')
    if (digest(decisions) != stop['matched_decisions_sha256']
            or config['observations_terminal_sha256'] != sha(observed / 'terminal.json')
            or config['executor'] != obs_config['executor'] or config['executor'] != executor):
        raise ValueError('Validate the physical source observations and original B5 fit')
    bank = {key: {} for key in prefix}
    receipts = {key: {} for key in prefix}
    readers, incomplete = {}, {}
    for family, arm in ARMS.items():
        folder = fit / 'candidates' / arm / CNI
        choice, proposed, older = (read(folder / name) for name in
                                   ('decision.json', 'measurements.json', 'prior_TRAIN_regression.json'))
        entering = journal.library(arm, BATCH - 1)
        if (choice != decisions['teacher'][arm][CNI] or choice['selected'] != ORIGINAL_DECISIONS[family]
                or digest(proposed['predictions']) != choice['predictions_sha256']
                or digest(older) != choice['earlier_TRAIN_regression']['evidence_sha256']
                or CNI in entering.get('schema_proposals', {})):
            raise ValueError('Retain both actual measured proposals, including the rejected ordinary one')
        program = entering['programs'][CNI]
        codec = proposed['candidate'] if family == 'parse' else None
        start, candidate = f'{family}_incumbent', f'{family}_proposal'
        readers[start] = (program, None)
        readers[candidate] = (program if codec else proposed['candidate'], codec)
        for key, (source, position) in prefix.items():
            prior, current = ((older['before'][key], older['candidate'][key]) if position[0] < BATCH else
                              (archive.observed(journal, arm, BATCH, key, before), proposed['predictions'][key]))
            for role, result in ((start, prior), (candidate, current)):
                unhandled = sum(not cell['handled'] for cell in result['native'].values())
                if unhandled:
                    incomplete.setdefault(key, []).append({'position': position, 'reader': role,
                                                          'unhandled_hypotheses': unhandled})
                receipts[key][role] = archive.physical(db, source, result, *readers[role])
                bank[key][role] = result['native']
    ids = {call for row in receipts.values() for call, _ in row.values()}
    if len(ids) != 60 or any(len(set(value[1] for value in row.values())) != 1 for row in receipts.values()):
        raise ValueError('Require four distinct responses with matched public input and settings per source')
    return readers, bank, receipts, incomplete, sha(fit / 'terminal.json')


def roster_cells(roster, batches, start):
    return {source['key']: (source, [batch, i])
            for batch, rows in enumerate(roster[batches], start)
            for i, source in enumerate((row for row in rows if row['dataset'] == CNI), 1)
            if source['project_split'] == 'train'}


def original_forward(db, cases, common, readers, executor, choices, tasks):
    predictions = {policy: {} for policy in choices}
    receipts, source_resolved = {}, {}
    for key, (source, position) in cases.items():
        known, copied, access = common[key]
        resolved = {task: known[task] for task in tasks if task in known}
        source_resolved[key] = sorted(resolved)
        required = {choice['programs'][task] for choice in choices.values() for task in tasks if task not in resolved}
        rows, signatures = {}, []
        receipts[key] = {}
        for role in sorted(required):
            program, codec = readers[role]
            wire = (replay.parse.schema_wire(source, codec, executor) if codec else
                    replay.replay.input_wire(source, program, executor))
            identity, native = replay.exact(db, source, wire, codec)
            if identity is None:
                raise ValueError(f'The original TRAIN read at {position} for {role} is missing')
            signatures.append(digest({
                'public': [msg for msg in wire['messages'] if msg['role'] == 'user'],
                'executor': {name: value for name, value in wire.items() if name not in ('messages', 'response_format')},
            }))
            receipts[key][role] = identity
            rows[role] = project(source, native, known, copied, access)
        if len(set(signatures)) > 1 or len(set(receipts[key].values())) != len(required):
            raise ValueError('Every forward policy must see the same original public context')
        for policy, allocation in choices.items():
            predictions[policy][key] = {
                task: resolved[task] if task in resolved else rows[allocation['programs'][task]][task]
                for task in tasks
            }
    return predictions, receipts, source_resolved


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != employee.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Start from the settled employee-witness comparison')
    _, prior_config, fixed = b4.terminal(employee)
    root, study, roster = archive.archive_context()
    executor = study['executor']
    journal = parent.TrainingJournal(root, study, roster)
    _, original, _ = archive.bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    reference = ROOT / original['native_grade_paths'][CNI]
    if ('train' not in reference.parts or sha(reference) != prior_config['reference_sha256'][0]
            or sha(reference) != original['native_grade_sha256'][str(reference.relative_to(ROOT))]):
        raise ValueError('Use only the original TRAIN reference')
    prefix = roster_cells(roster, slice(None, BATCH), 1)
    forward = roster_cells(roster, slice(BATCH, None), BATCH + 1)
    if (len(prefix), len(forward)) != (15, 9) or prefix.keys() & forward.keys():
        raise ValueError('Require the complete chronological original cohort')
    common = {key: proofs(source) for key, (source, _) in {**prefix, **forward}.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger != fixed['ledger'] or ledger.get('reserved'):
            raise ValueError('Use original paid reads under the settled continuous ledger')
        readers, raw, prefix_receipts, incomplete, fit_sha = original_prefix(db, journal, prefix, executor)
        eligible = [key for key in prefix if key not in incomplete]
        shared = {key: {role: project(prefix[key][0], native, *common[key]) for role, native in rows.items()}
                  for key, rows in raw.items() if key in eligible}
        labels = read(reference)
        ranked, fit = b4.rankings(shared, {key: prefix[key][0] for key in eligible},
                                  {key: labels[key] for key in eligible})
        groups = [{'position': prefix[key][1], **screen.source_signals(raw[key], common[key][0], ranked)}
                  for key in eligible if common[key][0]]
        choices = screen.choose(groups, ranked, physical_group_width=len(readers))
        tasks = sorted(task for task in ranked if len({v['programs'][task] for v in choices.values()}) > 1)
        if not tasks:
            raise ValueError('Compare only actual differences in fitted hypothesis readers')
        versions = {role: digest(codec if codec is not None else p) for role, (p, codec) in readers.items()}
        hashes = {str(Path(path).relative_to(ROOT)): sha(Path(path)) for path in
                  (__file__, screen.__file__, b4.__file__, replay.__file__, assertion.__file__, employee.__file__)}
        binding = {'stage': STAGE, 'source_sha256': hashes, 'B5_original_fit_terminal_sha256': fit_sha,
                   'shared_employee_witness_terminal': fixed['terminal_sha256'], 'source_proofs_sha256': digest(common),
                   'fit_choices_sha256': digest(choices), 'fit_rows_sha256': digest([groups, ranked, fit]),
                   'incomplete_groups_sha256': digest(incomplete),
                   'prefix_physical_receipts_sha256': digest(prefix_receipts), 'TRAIN_grade_sha256': sha(reference),
                   'reader_versions': versions, 'changed_hypotheses': tasks, 'TEST_opened': False}
        out = BASE / STAGE / digest(binding)
        immutable_json(out / 'binding.json', binding)
        archive.snapshot(out, hashes)
        immutable_json(out / 'fit_receipt.json', {'groups': groups, 'ranked': ranked, 'native_fit': fit,
                                                  'locked_choices': choices, 'incomplete_groups': incomplete})
        for policy, selection in choices.items():
            immutable_json(out / 'TRAIN_batch_libraries' / f'{policy}.json', sealed({
                'batch': BATCH, 'binding_sha256': out.name, 'group': selection['position'],
                'programs_by_hypothesis': {task: versions[role] for task, role in selection['programs'].items()},
            }, 'snapshot_sha256'))
        native, later_receipts, resolved = original_forward(db, forward, common, readers, executor, choices, tasks)
    data = immutable_json(out / 'sealed_predictions.json', native)
    ids = {ident for readers in later_receipts.values() for ident in readers.values()}
    prefix_ids = {entry[0] for row in prefix_receipts.values() for entry in row.values()}
    if ids & prefix_ids or len(ids) != sum(map(len, later_receipts.values())):
        raise ValueError('Keep chronological mother sources and physical executions distinct')
    read_sha = immutable_json(out / 'physical_receipts.json', {'prefix': prefix_receipts, 'forward': later_receipts})
    scores = replay.compare(forward, native, {key: labels[key] for key in forward})
    if any(row['units'] != len(forward) * len(tasks) for row in scores['native'].values()):
        raise ValueError('Complete all policies on the same denominator')
    effects = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': data,
        'physical_receipts_sha256': read_sha, 'reader_screen_width': len(readers), 'prefix_mothers': len(prefix),
        'complete_prefix_mothers': len(eligible), 'eligible_group_count': len(groups),
        'incomplete_readers': [row for members in incomplete.values() for row in members],
        'B6_B8_mothers': len(forward), 'forward_hypotheses': tasks, 'choice': choices,
        'native': scores['native'], 'paired': scores['paired'],
        'common_proof_units': sum(map(len, resolved.values())),
        'direct_conflict_control_same_allocation': choices['candidate_driven'] == choices['source_class_conflict_count'],
        'direct_conflict_control_same_predictions': native['candidate_driven'] == native['source_class_conflict_count'],
        'verified_original_physical_reads': {'prefix': len(prefix_ids), 'forward': len(ids)},
        'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'retrospective_original_TRAIN': True, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', effects)
    write_status(out, {'status': effects['status'], 'terminal_sha256': effects['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
