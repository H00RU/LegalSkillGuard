"""Replay two historical ContractNLI B4 proposals in one fixed candidate pool."""

import json
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_copy_mention_roles as copy
from experiments import convergence_revision6_cni_survival_trigger_roles as survival
from experiments import convergence_revision6_cni_task_screen as ordinary
from experiments import convergence_revision6_cni_task_screen_parse as parse
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_candidate_portfolio as portfolio
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b4_candidate_portfolio'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, parent, scoped, CNI = ordinary.previous, ordinary.parent, ordinary.scoped, ordinary.CNI
ROLES = ('ordinary_incumbent', 'parse_incumbent', 'ordinary_proposal', 'parse_proposal')


def terminal(module):
    pointer = read(module.POINTER)
    root = ROOT / pointer['artifact_root']
    bind = read(root / 'binding.json')
    stop = verify(read(root / 'terminal.json'), 'terminal_sha256')
    if (digest(bind) != root.name or stop['binding_sha256'] != root.name
            or pointer['terminal_sha256'] != stop['terminal_sha256'] or stop['TEST_opened']):
        raise ValueError('Reuse the original sealed source and physical-response experiment')
    return root, bind, stop


def matching_wires(db, physical_ids, keys):
    by_source = {}
    for identity in physical_ids:
        source, status, encoded = db.execute(
            "select source,status,result from calls where id=? and role='executor' and purpose='skill_actor'",
            (identity,),
        ).fetchone()
        if source not in keys or status != 'completed':
            raise ValueError('Use the same original fully settled TRAIN sources')
        response = json.loads(encoded)
        payload = read(Path(response['artifact_directory']) / 'request.json')['payload']
        user = [msg for msg in payload['messages'] if msg['role'] == 'user']
        params = {name: value for name, value in payload.items() if name not in ('messages', 'response_format')}
        by_source.setdefault(source, []).append(digest([params, user]))
    if set(by_source) != keys or any(len(rows) != 4 or len(set(rows)) != 1 for rows in by_source.values()):
        raise ValueError('All four measured readers must receive identical source inputs and executor settings')
    return {key: value[0] for key, value in by_source.items()}


def original_inputs():
    first, ordinary_bind, ordinary_end = terminal(ordinary)
    _, parse_bind, parse_end = terminal(parse)
    b5_point = read(parent.POINTER)
    b5_path = ROOT / b5_point['artifact_root']
    b5_binding = read(b5_path / 'binding.json')
    b5_end = verify(read(b5_path / 'terminal.json'), 'terminal_sha256')
    before, programs, _, _, forward, wires, grade = parent.prepare_materials()
    if (sha(first / 'sealed_predictions.json') != ordinary_end['predictions_sha256']
            or ordinary_bind['B5_paired_execution_terminal'] != b5_end['terminal_sha256']
            or parse_bind['same_screen_ordinary_terminal'] != ordinary_end['terminal_sha256']
            or b5_point['terminal_sha256'] != b5_end['terminal_sha256']
            or b5_path.name != digest(b5_binding) or 'train' not in grade.parts
            or sha(grade) != ordinary_bind['grade_sha256']
            or sha(grade) != parse_bind['TRAIN_grade_sha256']
            or any(before[part] != b5_binding[part] for part in ('programs', 'calibration_archive_sha256'))):
        raise ValueError('Bind both original B4 comparisons and the same fixed TRAIN references')
    ordinary_bank, contexts, first_ids = ordinary.fit_bank(programs, b5_binding)
    later, _ = scoped.restore(b5_path, forward, programs, wires)
    for key, row in forward.items():
        ordinary_bank[key] = {'incumbent': later[key][0], 'proposal': row['proposal']}
        contexts[key] = {'source': row['source']}
    first_ids.update({row[1] for row in later.values()} | {row['archived_choice'] for row in forward.values()})
    root, study, roster = archive.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        other, positions, second_ids, _ = archive.bank_b4(db, journal, roster)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or set(ordinary_bank) != set(other) or len(positions) != 15 or first_ids & second_ids:
            raise ValueError('Do not duplicate a response or change the original chronological sources')
        signatures = matching_wires(db, first_ids | second_ids, set(positions))
    if digest(sorted(second_ids)) != parse_bind['physical_ids_sha256']:
        raise ValueError('Bind the exact original PARSE pair identities')
    version = {
        'ordinary_incumbent': digest(programs['incumbent']), 'ordinary_proposal': digest(programs['proposal']),
        'parse_incumbent': digest(journal.library(archive.EXTERNAL_ARM, 3)['programs'][CNI]),
        'parse_proposal': archive.b4.materials()[0]['proposal_sha256'],
    }
    if len(set(version.values())) != len(ROLES):
        raise ValueError('Preserve each distinct measured compiler or program')
    bank = {key: {**{f'ordinary_{role}': row for role, row in ordinary_bank[key].items()},
                  **{f'parse_{role}': row for role, row in other[key].items()}} for key in positions}
    sources = {key: val['source'] for key, val in contexts.items()}
    positions = {key: [batch, pos + 1] for key, (batch, pos) in positions.items()}
    if set(positions) != set(sources):
        raise ValueError('Use all original 12 prefix and 3 forward TRAIN mothers')
    return bank, sources, positions, version, grade, signatures, first_ids | second_ids, ledger, roster, (
        ordinary_end['terminal_sha256'], parse_end['terminal_sha256'],
    )


def current_proofs(source):
    proofs = ordinary.proof_for(source)
    if paths := survival.compile_scope(source)['paths']:
        proofs[survival.TASK] = survival.scope.project({}, paths, include_antecedent=False)
    source_copy = copy.proof(source)
    judgment = copy.project({'answer': None, 'evidence_sentence_ids': []}, source_copy)
    if judgment['answer'] is not None:
        proofs[copy.TASK] = judgment
    return proofs


def rankings(bank, sources, grade):
    measures = {}
    for key, readers in bank.items():
        for role, native in readers.items():
            for row in scoped.native_rows(sources[key], grade[key], native):
                task = row['view']
                scores = measures.setdefault(task, {name: [0.0, 0.0] for name in ROLES})
                scores[role][0] += row['correct']
                scores[role][1] += row['grounded']
    order = {task: tuple(sorted(ROLES, key=values.__getitem__, reverse=True)) for task, values in measures.items()}
    return order, measures


def evaluate(policies, bank, sources, ground, relevant):
    projections = {}
    for role, allocation in policies.items():
        projections[role] = {
            key: {task: readers[program][task] for task, program in allocation['programs'].items()}
            for key, readers in bank.items()
        }
    summaries = {}
    for name, mask in (('all_hypotheses', set(next(iter(policies.values()))['programs'])),
                       ('changed_hypotheses', set(relevant))):
        if not mask:
            continue
        cells = {role: [row for key, native in rows.items()
                        for row in scoped.native_rows(sources[key], ground[key], native) if row['view'] in mask]
                 for role, rows in projections.items()}
        learner = cells['candidate_driven']
        summaries[name] = {
            'native': {role: {'correct': sum(r['correct'] for r in rows), 'units': len(rows),
                              'correct_class_evidence_F1': mean(r['grounded'] for r in rows)}
                       for role, rows in cells.items()},
            'paired': {role: {metric: paired_source_effect(
                *[[{**row, 'grade': row[metric]} for row in side] for side in (rows, learner)]
            ) for metric in ('correct', 'grounded')} for role, rows in cells.items() if role != 'candidate_driven'},
        }
    return projections, summaries


def run():
    if read(HANDOFF / 'run_state.json')['active_tasks']:
        raise ValueError('Require both original phases to be settled before replaying')
    raw, sources, positions, versions, grade, signatures, identities, ledger, roster, previous = original_inputs()
    proofs = {key: current_proofs(source) for key, source in sources.items()}
    shared = {key: {role: ordinary.apply_proofs(sources[key], output, proofs[key]) for role, output in rows.items()}
              for key, rows in raw.items()}
    prefix = {key: rows for key, rows in shared.items() if positions[key][0] <= 4}
    later = {key: rows for key, rows in shared.items() if positions[key][0] == 5}
    labels = read(grade)
    ordered, native = rankings(prefix, sources, {key: labels[key] for key in prefix})
    groups = []
    for key in prefix:
        if not proofs[key]:
            continue
        losses, repairs, disagreements = portfolio.group_evidence(raw[key], proofs[key], ordered)
        groups.append({'position': positions[key], 'losses': losses, 'recoveries': repairs,
                       'disagreements': disagreements, 'proof_tasks': sorted(proofs[key])})
    choices = portfolio.select(groups, ordered, physical_group_width=len(ROLES))
    different = sorted(task for task in ordered if len({row['programs'][task] for row in choices.values()}) > 1)
    coverage = {}
    for b, batch in enumerate(roster[5:], 6):
        for index, source in enumerate((row for row in batch if row['dataset'] == CNI), 1):
            coverage[f'{b}-{index}'] = sorted(set(different) - current_proofs(source).keys())
    group_receipts = [{**row, 'losses': {task: sorted(v) for task, v in row['losses'].items()},
                       'disagreements': sorted(row['disagreements'])} for row in groups]
    spec = {
        'stage': STAGE, 'partition': 'original_TRAIN', 'TEST_opened': False,
        'original_B4_terminals': previous, 'TRAIN_grade_sha256': sha(grade),
        'matched_public_input_sha256': digest(signatures), 'physical_TRAIN_calls_sha256': digest(sorted(identities)),
        'source_proofs_sha256': digest(proofs), 'native_ranks_sha256': digest(ordered),
        'groups_sha256': digest(group_receipts), 'choices_sha256': digest(choices), 'programs': versions,
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, portfolio.__file__, ordinary.__file__, parse.__file__, archive.__file__,
            copy.__file__, survival.__file__,
        )},
    }
    root = BASE / STAGE / digest(spec)
    immutable_json(root / 'binding.json', spec)
    archive.snapshot(root, spec['source_sha256'])
    made = {name: sealed({'binding_sha256': root.name, 'fit_batch': 4,
                          'programs_by_hypothesis': {task: versions[role] for task, role in row['programs'].items()},
                          'selected_group': row['position']}, 'snapshot_sha256')
            for name, row in choices.items()}
    for name, library in made.items():
        immutable_json(root / 'TRAIN_batch_libraries' / f'{name}.json', library)
    predictions, scored = evaluate(choices, later, sources, {key: labels[key] for key in later}, different)
    pred = immutable_json(root / 'sealed_predictions.json', predictions)
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': root.name, 'predictions_sha256': pred,
        'different_hypotheses': different, 'choices': choices, 'screened_groups': group_receipts,
        'B1_B4_native': native, 'B5_observed': scored, 'B6_B8_public_unresolved': coverage,
        'calibration_mothers': len(prefix), 'forward_mothers': len(later), 'original_TRAIN_requests_reused': len(identities),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(root / 'terminal.json', terminal)
    write_status(root, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(root, flush=True)


if __name__ == '__main__':
    run()
