"""Replay complementary two-group acquisition from the exact B4 and B5 fit archives."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_b5_candidate_conflicts as b5
from experiments import convergence_revision6_cni_disposition_sequence as disposition
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_complementary_acquisition as selector
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_complementary_acquisition'
POINTER = HANDOFF / f'{STAGE}_current.json'
b4, replay = b5.b4, b5.replay
CANDIDATE = 'candidate_complement'


def replay_fits():
    original, binding, terminal = b4.terminal(b4)
    _, later_spec, later = b4.terminal(b5)
    attachment = ROOT / read(b5.POINTER)['artifact_root']
    fit = read(attachment / 'fit_receipt.json')
    if (sha(original / 'sealed_predictions.json') != terminal['predictions_sha256']
            or digest(terminal['screened_groups']) != binding['groups_sha256']
            or digest([fit['groups'], fit['ranked'], fit['native_fit']]) != later_spec['fit_rows_sha256']
            or digest(fit['locked_choices']) != later_spec['fit_choices_sha256']
            or binding['TRAIN_grade_sha256'] != later_spec['TRAIN_grade_sha256']):
        raise ValueError('Bind the original fit data and groups before assembling pairs')
    ranked = {task: sorted(b4.ROLES, key=scores.__getitem__, reverse=True)
              for task, scores in terminal['B1_B4_native'].items()}
    if digest({task: tuple(readers) for task, readers in ranked.items()}) != binding['native_ranks_sha256']:
        raise ValueError('Use the exact original native tie direction')
    groups = [{
        'position': row['position'], 'veto_by_task': row['losses'], 'leader_recoveries': list(row['recoveries']),
        'answer_disagreements': row['disagreements'], 'proof_tasks': row['proof_tasks'],
    } for row in terminal['screened_groups']]
    outputs = {}
    for batch, current, order, receipt in (
        ('B4', groups, ranked, terminal), ('B5', fit['groups'], fit['ranked'], later),
    ):
        choices, feasible = selector.choose(current, order, group_width=len(b4.ROLES))
        ref = choices[CANDIDATE]['programs']
        outputs[batch] = {
            'original_fit_terminal': receipt['terminal_sha256'],
            'eligible_single_groups': len(current), 'feasible_pairs': feasible, 'choices': choices,
            'identical_program_controls': sorted(role for role, row in choices.items()
                                                 if role != CANDIDATE and row['programs'] == ref),
        }
    return binding, outputs


def forward_proof(source):
    known, copied, access = b5.proofs(source)
    if closure := disposition.source_proof(source):
        known[disposition.TASK] = {'answer': 'Contradiction', 'evidence_sentence_ids': closure['evidence']}
    return known, copied, access


def forward(db, sources, readers, schema, executor, allocations, tasks, common):
    bank, receipts, uncovered, public = {role: {} for role in allocations}, {}, [], {}
    for key, (source, position) in sources.items():
        known, copy, access = common[key]
        public[key] = {task: known[task] for task in tasks if task in known}
        unresolved = set(tasks) - public[key].keys()
        required = {row['programs'][task] for row in allocations.values() for task in unresolved}
        physical, signatures, records = {}, set(), {}
        for role in sorted(required):
            codec = schema if role == 'parse_proposal' else None
            wire = (replay.parse.schema_wire(source, codec, executor) if codec else
                    replay.replay.input_wire(source, readers[role], executor))
            signatures.add(digest({
                'public': [msg for msg in wire['messages'] if msg['role'] == 'user'],
                'settings': {k: v for k, v in wire.items() if k not in ('messages', 'response_format')},
            }))
            identity, raw = replay.exact(db, source, wire, codec)
            if identity is not None:
                physical[role] = b5.project(source, raw, known, copy, access)
                records[role] = identity
        if len(signatures) > 1 or len(set(records.values())) != len(records):
            raise ValueError('Keep identical input, distinct readers and original physical settings')
        receipts[key] = records
        assessable = sorted(public[key].keys() | {
            task for task in unresolved if all(s['programs'][task] in physical for s in allocations.values())
        })
        if missing := set(tasks) - set(assessable):
            uncovered.append({'position': position, 'missing_hypotheses': sorted(missing),
                              'reader_roles_without_exact_read': sorted(required - records.keys())})
        for role, row in allocations.items():
            bank[role][key] = {
                task: public[key][task] if task in public[key] else physical[row['programs'][task]][task]
                for task in assessable
            }
    return bank, receipts, uncovered, public


def run():
    handoff = read(HANDOFF / 'run_state.json')
    if handoff['active_tasks'] or handoff['phase'] != disposition.STAGE + '_settled':
        raise ValueError('Continue after the archived cumulative DEV results settle')
    previous, fits = replay_fits()
    if fits['B4']['identical_program_controls'] or not fits['B5']['identical_program_controls']:
        raise ValueError('Only B4 has a fitted difference against every acquisition control')
    _, last, previous_result = b4.terminal(disposition)
    _, reference, readers, executor, schema = replay.inputs(previous)
    _, _, roster = b4.archive.archive_context()
    sources = b5.roster_cells(roster, slice(4, None), 5)
    allocations = fits['B4']['choices']
    tasks = sorted(task for task in allocations[CANDIDATE]['programs']
                   if len({row['programs'][task] for row in allocations.values()}) > 1)
    if len(sources) != 12 or 'train' not in reference.parts or sha(reference) != last['reference_hashes'][0]:
        raise ValueError('Use only the original B5 through B8 TRAIN and its unchanged grade')
    common = {key: forward_proof(source) for key, (source, _) in sources.items()}
    hashes = {str(Path(name).relative_to(ROOT)): sha(Path(name)) for name in (
        __file__, selector.__file__, b4.__file__, b5.__file__, replay.__file__, disposition.__file__,
    )}
    spec = {'stage': STAGE, 'source_sha256': hashes, 'original_B4_fit_sha256': digest(previous),
            'complete_disposition_terminal': previous_result['terminal_sha256'], 'locked_choices_sha256': digest(fits),
            'public_source_sha256': digest(sources), 'source_proofs_sha256': digest(common),
            'TRAIN_grade_sha256': sha(reference), 'changed_hypotheses': tasks, 'TEST_opened': False}
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'fitted_pairs.json', fits)
    b4.archive.snapshot(out, hashes)
    for role, choice in allocations.items():
        immutable_json(out / 'TRAIN_batch_libraries' / f'{role}.json', sealed({
            'binding_sha256': out.name, 'batch': 4, 'groups': choice['groups'],
            'programs_by_hypothesis': {task: previous['programs'][value] for task, value in choice['programs'].items()},
        }, 'snapshot_sha256'))
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger != previous_result['ledger'] or ledger.get('reserved'):
            raise ValueError('Reuse archived requests at the recorded settled boundary')
        bank, receipts, missing, witnessed = forward(db, sources, readers, schema, executor, allocations, tasks, common)
    prediction_hash = immutable_json(out / 'sealed_predictions.json', bank)
    receipt_hash = immutable_json(out / 'forward_physical_receipts.json', receipts)
    core_names = {'candidate_driven' if role == CANDIDATE else role: maps for role, maps in bank.items()}
    grades = read(reference)
    if not all(core_names['candidate_driven'].values()):
        raise ValueError('Retain at least one equally observed hypothesis on each forward source')
    native = replay.compare(sources, core_names, {key: grades[key] for key in sources})
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_hash,
        'physical_receipts_sha256': receipt_hash, 'fitted_pairs': fits,
        'B4_forward_mothers': len(sources), 'changed_hypotheses': tasks,
        'B4_planned_native_units': len(tasks) * len(sources), 'B4_archived_native': native,
        'shared_proof_units': sum(map(len, witnessed.values())), 'missing_on_exact_forward': missing,
        'unique_forward_physical_reads': len({cid for group in receipts.values() for cid in group.values()}),
        'B5_no_distinct_route_against_all_controls': True, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
