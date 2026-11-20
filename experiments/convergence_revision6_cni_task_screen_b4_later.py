"""Check the locked B4 ordinary decision on later original ContractNLI TRAIN sources."""

import argparse
import fcntl
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_task_screen_forward as replay
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_task_screen_b4_later'
POINTER = HANDOFF / f'{STAGE}_current.json'
ordinary, archive, parent, CNI = replay.ordinary, replay.archive, replay.parent, replay.CNI
screen = replay.screen


def prepare():
    pointer = read(ordinary.POINTER)
    origin = ROOT / pointer['artifact_root']
    lock = read(origin / 'binding.json')
    end = verify(read(origin / 'terminal.json'), 'terminal_sha256')
    if (digest(lock) != origin.name or end['terminal_sha256'] != pointer['terminal_sha256']
            or sha(origin / 'sealed_predictions.json') != end['predictions_sha256']
            or end['TEST_opened'] or end['hypotheses_with_different_adoption'] != ['nda-10']):
        raise ValueError('Require the same original ordinary B4 selection and paired forward results')
    (task,) = end['hypotheses_with_different_adoption']
    policies = {name: row['programs'][task] for name, row in end['policies'].items()}
    programs = {}
    root, study, roster = archive.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    route_origin = ROOT / read(parent.POINTER)['artifact_root']
    route_lock = read(route_origin / 'binding.json')
    if lock['prefix'] != sha(route_origin / 'binding.json') or lock['B4_fit'] != route_lock['B4_fit_sha256']:
        raise ValueError('Require the actual B4 candidate and its pre-update program')
    for role, batch in ((screen.INCUMBENT, 3), (screen.PROPOSAL, 4)):
        programs[role] = journal.library(parent.ORDINARY, batch)['programs'][CNI]
        if digest(programs[role]) != route_lock['programs'][role]:
            raise ValueError('Use precisely the original reader versions from B5')
    _, config, _ = archive.bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    grade = ROOT / config['native_grade_paths'][CNI]
    if 'train' not in grade.parts or sha(grade) != lock['grade_sha256']:
        raise ValueError('Preserve native ratings from the original TRAIN partition')
    executor = study['executor']
    selected, cases, measured, provenance = {}, {}, {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch in (6, 7, 8):
            observation, obs_spec, obs_end = archive.bound_stage(parent.observe_pointer(batch))
            if (obs_spec['executor'] != executor or obs_end['TEST_opened']
                    or journal.library(parent.ORDINARY, batch - 1)['programs'][CNI] != programs[screen.PROPOSAL]):
                raise ValueError('Require the original adopted reader to remain the later TRAIN carrier')
            provenance[str(batch)] = sha(observation / 'terminal.json')
            for position, source in enumerate((s for s in roster[batch - 1] if s['dataset'] == CNI), 1):
                key = source['key']
                if source['project_split'] != 'train':
                    raise ValueError('Use all three original TRAIN sources in each later batch')
                common = ordinary.proof_for(source)
                record = archive.observed(journal, parent.ORDINARY, batch, key, obs_end)
                identity = parent.archived(db, source, record, programs[screen.PROPOSAL],
                                           parent.wire(source, programs[screen.PROPOSAL], executor))
                measured[key] = identity
                cases[key] = {'source': source, 'position': [batch, position], 'proof': common,
                              'candidate': ordinary.apply_proofs(source, record['native'], common)[task]}
                if task in common:
                    continue
                wire = parent.wire(source, programs[screen.INCUMBENT], executor)
                candidates = replay.existing_requests(db, key, wire)
                selected[key] = {'wire': wire, 'existing': [pair for pair in candidates
                                                          if not pair[0].startswith(STAGE + '-')]}
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise ValueError('Wait for any live physical request before using the frozen executor')
    if len(cases) != 9 or len(set(measured.values())) != 9 or not selected:
        raise ValueError('Preserve the complete later cohort and its bound B4 carrier')
    paths = (__file__, ordinary.__file__, replay.__file__, parent.__file__)
    binding = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False,
               'ordinary_B4_terminal': end['terminal_sha256'], 'programs': route_lock['programs'],
               'frozen_hypothesis_routes': policies, 'hypothesis': task, 'executor': executor,
               'grade_sha256': sha(grade), 'observation_terminals': provenance,
               'all_positions': [case['position'] for case in cases.values()],
               'residual_positions': [cases[key]['position'] for key in selected],
               'measured_adopted_reader_ids_sha256': digest(measured),
               'proved_outputs_sha256': digest({key: v['proof'] for key, v in cases.items()}),
               'exact_wires_sha256': digest({key: row['wire'] for key, row in selected.items()}),
               'replay_ids': sorted(identity for row in selected.values() for identity, _ in row['existing']),
               'planned_new_requests': sum(not v['existing'] for v in selected.values()),
               'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths}}
    return binding, cases, selected, programs[screen.INCUMBENT], grade, origin


def measure(out, lock, cases, selected, program, grade, origin):
    task = lock['hypothesis']
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                            sources={'train': list(selected), 'dev': [], 'test': []}, binding=lock)
    executor = parent.FrozenExecutor(ledger, out, lock['executor'])
    executor.exact_replay_roots = sorted({path for row in selected.values() for _, path in row['existing']})
    executor.readiness()
    available = lock['executor']['context_tokens'] - lock['executor']['max_tokens']
    if any(executor.tokenize(row['wire']['messages'], thinking=False)['count'] > available for row in selected.values()):
        raise ValueError('Keep the full original native input for every candidate')
    actor = parent.ProgramActor(executor, out, max_calls=1)
    entered = {}
    for key, row in selected.items():
        source = cases[key]['source']
        write_status(out, {'status': 'running', 'position': cases[key]['position']}, POINTER)
        cell, = parent.common_cells(source)
        native = actor.execute(program, cell, 'skill_actor')
        actor.verify_program_result(cell, program, 'skill_actor', native)
        if not native['program_execution_completed']:
            raise ValueError('Do not treat an incomplete original program result as a comparison')
        with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
            parent.archived(db, source, {'reads': [native], 'native': native['native']}, program, row['wire'])
        entered[key] = ordinary.apply_proofs(source, native['native'], cases[key]['proof'])[task]
        print('Settled', cases[key]['position'], flush=True)
    results = {key: {name: {task: entered[key] if key in entered and role == screen.INCUMBENT else row['candidate']}
                     for name, role in lock['frozen_hypothesis_routes'].items()} for key, row in cases.items()}
    tag = immutable_json(out / 'sealed_predictions.json', results)
    if sha(grade) != lock['grade_sha256']:
        raise ValueError('Score only the original declared TRAIN rows')
    labels = read(grade)
    later = score(task, cases, results, labels)
    # Preserve the first B5 check as a separate observed cohort.
    prior = verify(read(origin / 'terminal.json'), 'terminal_sha256')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        own = dict(db.execute('select status,count(*) from calls where id like ? group by status', (ledger.run_id+':%',)))
    if own != ({'completed': lock['planned_new_requests']} if lock['planned_new_requests'] else {}) or counts.get('reserved'):
        raise ValueError('Settle all registered physical requests before reading results')
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
                       'later_original_TRAIN': later, 'proof_resolved_mothers': len(cases) - len(selected),
                       'later_mothers': len(cases), 'B5_original': prior['B5_only_differing_hypotheses'],
                       'new_executor_requests': lock['planned_new_requests'], 'archived_adopted_reader_requests': len(cases),
                       'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': counts}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


def score(task, cases, results, labels):
    units = {name: [] for name in next(iter(results.values()))}
    positions = {}
    for key, options in results.items():
        view = next(v for v in cases[key]['source']['views'] if v['id'] == task)
        comparisons = {}
        for name, results_by_task in options.items():
            native = results_by_task[task]
            grade = grade_view(CNI, view, labels[key][task], native['answer'], native['evidence_sentence_ids'])
            comparisons[name] = {'correct': grade['grade'], 'grounded': grade['grade'] * grade['evidence_f1']}
            units[name].append({'source': key, 'view': task, **comparisons[name]})
        positions['-'.join(map(str, cases[key]['position']))] = comparisons
    return {
        'by_position': positions,
        'metrics': {name: {'correct': sum(v['correct'] for v in values), 'units': len(values),
                           'correct_class_evidence_F1': mean(v['grounded'] for v in values)}
                    for name, values in units.items()},
        'candidate_driven_effects': {name: {metric: paired_source_effect(
            *[[{**v, 'grade': v[metric]} for v in group] for group in (values, units['candidate_driven'])])
            for metric in ('correct', 'grounded')} for name, values in units.items() if name != 'candidate_driven'},
    }


def run(execute):
    lock, *material = prepare()
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    archive.snapshot(out, lock['source_sha256'])
    if (out / 'terminal.json').is_file():
        print(out)
    elif not execute:
        write_status(out, {'status': 'prepared', 'planned_new_requests': lock['planned_new_requests']}, POINTER)
        print(out, lock['residual_positions'], lock['planned_new_requests'])
    else:
        if ROOT / read(POINTER)['artifact_root'] != out:
            raise ValueError('Use only the already sealed later TRAIN comparison')
        with (out / 'driver.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            measure(out, lock, *material)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args().execute)
