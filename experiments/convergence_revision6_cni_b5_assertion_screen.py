"""Screen the original B5 ordinary update for source-proved label regressions."""

import argparse
import fcntl
import sqlite3
from pathlib import Path

from experiments import convergence_revision5_cni_oral_scope as oral
from experiments import convergence_revision6_cni_copy_mention_roles as copy
from experiments import convergence_revision6_cni_task_screen_b4_later as later
from experiments import convergence_revision6_retention_grant_replay as retention
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_assertion_channels as channels
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b5_assertion_screen'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, parent, ordinary, screen = later.archive, later.parent, later.ordinary, later.screen
CNI, TASK = later.CNI, oral.TASK
BATCH = 5
PROGRAMS = (screen.INCUMBENT, screen.PROPOSAL)


def proof_for(source):
    by_task = {view['id']: view for view in source['views']}
    spans = oral.spans_for(by_task[TASK])
    witnesses = ordinary.proof_for(source)
    continuance = channels.continued_oral_information(spans)
    for task, paths in ((TASK, [path for _, path in oral.oral_proof(by_task[TASK])]),
                        ('nda-20', retention.source_proofs(spans))):
        if paths:
            witnesses[task] = {'answer': 'Entailment',
                               'evidence_sentence_ids': list(min(paths, key=lambda path: (len(path), path)))}
    if continuance:
        witnesses[TASK] = continuance
    copied = copy.proof(source)
    if copied.get('complete_non_creation'):
        witnesses[copy.TASK] = {'answer': 'NotMentioned', 'evidence_sentence_ids': []}
    elif approved := copy.common.source_proof(source):
        witnesses[copy.TASK] = {field: approved[field] for field in ('answer', 'evidence_sentence_ids')}
    return witnesses, copied, continuance


def shared(source, raw, witnesses, copied):
    result = ordinary.apply_proofs(source, raw, witnesses)
    result[copy.TASK] = copy.project(result[copy.TASK], copied)
    return result


def prepare():
    root, study, roster = archive.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    arm = parent.ORDINARY
    fit, config, terminal = archive.bound_stage(parent.fit_pointer(BATCH))
    obs, _, fit_obs = archive.bound_stage(parent.observe_pointer(BATCH))
    decisions = read(fit / 'matched_decisions.json')
    group = fit / 'candidates' / arm / CNI
    decision = read(group / 'decision.json')
    candidate = read(group / 'measurements.json')
    previous = read(group / 'prior_TRAIN_regression.json')
    if (decision != decisions['teacher'][arm][CNI] or digest(decisions) != terminal['matched_decisions_sha256']
            or decision['selected'] != 'incumbent' or decision['native_utility_delta'] <= 0
            or digest(previous) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or digest(candidate['predictions']) != decision['predictions_sha256']
            or config['observations_terminal_sha256'] != sha(obs / 'terminal.json')
            or config['executor'] != study['executor']):
        raise ValueError('Use the actual rejected B5 ordinary candidate and its paid full-prefix measurements')
    programs = dict(zip(PROGRAMS, (journal.library(arm, BATCH - 1)['programs'][CNI], candidate['candidate']), strict=True))
    train, _, grade, _ = copy.archive.collect(*copy.archive.archive_context(), 'train')
    if len(train) != 24 or 'train' not in grade.parts:
        raise ValueError('Use only the original TRAIN roster and grade')
    cases, initial, revisions, fits, forward = {}, [], [], {}, {}
    known, archive_ids, observations = [], set(), {}
    executor = study['executor']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for number, rows in enumerate(roster, 1):
            for index, source in enumerate((s for s in rows if s['dataset'] == CNI), 1):
                key = source['key']
                if source != train[key] or source['project_split'] != 'train':
                    raise ValueError('Keep the complete original chronological TRAIN')
                proof, copied, continues = proof_for(source)
                position = [number, index]
                if continues is not None:
                    known.append({'position': position, 'proof': continues})
                case = {'source': source, 'position': position, 'proof': proof, 'copy': copied}
                if number > BATCH:
                    forward[key] = case
                    if TASK not in proof:
                        observation, cfg, ending = archive.bound_stage(parent.observe_pointer(number))
                        if cfg['executor'] != executor or journal.library(arm, number - 1)['programs'][CNI] != programs[screen.INCUMBENT]:
                            raise ValueError('Require the actual original later carrier')
                        observations[str(number)] = sha(observation / 'terminal.json')
                        former = archive.observed(journal, arm, number, key, ending)
                        wire = later.replay.input_wire(source, programs[screen.INCUMBENT], executor)
                        identity = parent.archived(db, source, former, programs[screen.INCUMBENT], wire)
                        novel = later.replay.input_wire(source, programs[screen.PROPOSAL], executor)
                        public = [[msg for msg in packet['messages'] if msg['role'] == 'user'] for packet in (wire, novel)]
                        settings = [{k: v for k, v in packet.items() if k not in ('messages', 'response_format')}
                                    for packet in (wire, novel)]
                        if public[0] != public[1] or settings[0] != settings[1]:
                            raise ValueError('Use exactly the same source and executor settings in both conditions')
                        case.update({'entry': former['native'], 'entry_id': identity, 'wire': novel,
                                     'cache': [row for row in later.replay.existing_requests(db, key, novel)
                                               if not row[0].startswith(STAGE + '-')]})
                    continue
                old, new = ((previous['before'][key], previous['candidate'][key]) if number < BATCH else
                            (archive.observed(journal, arm, BATCH, key, fit_obs), candidate['predictions'][key]))
                archive.verify_pair([archive.physical(db, source, old, programs[screen.INCUMBENT], None),
                                     archive.physical(db, source, new, programs[screen.PROPOSAL], None)], archive_ids)
                raw = dict(zip(PROGRAMS, (old['native'], new['native']), strict=True))
                before, after = raw.values()
                disagreements = [task for task in before if before[task]['answer'] != after[task]['answer']]
                initial.append({'position': position, 'disagreements': disagreements,
                                **archive.guard.compatibility(before, after, proof)})
                revisions.append({'position': position, 'disagreements': disagreements,
                                  **channels.compare(before, after, proof)})
                cases[key] = source
                fits[key] = {role: shared(source, values, proof, copied) for role, values in raw.items()}
    if (len(cases), len(archive_ids), len(forward)) != (15, 30, 9):
        raise ValueError('Preserve all original B1–B5 and B6–B8 sources')
    labels = read(grade)
    fit_variants = archive.score_fit(cases, fits, {key: labels[key] for key in cases})
    old_routes, new_routes = (screen.select(rows, fit_variants) for rows in (initial, revisions))
    different = {task for task in fit_variants if
                 len({value['programs'][task] for value in new_routes.values()}) > 1}
    if different != {TASK}:
        raise ValueError('Require evidence that selects differently on exactly the declared oral hypothesis')
    residual = {key: row for key, row in forward.items() if TASK not in row['proof']}
    if not residual or not any(route['programs'][TASK] != new_routes['candidate_driven']['programs'][TASK]
                               for route in new_routes.values()):
        raise ValueError('Require unresolved original sources and a distinct program allocation')
    _, fixed, _, _, _ = copy.common.prior.prepare()
    dev_proof_count = sum(TASK in proof_for(source)[0] for source in fixed.values())
    paths = (__file__, channels.__file__, screen.__file__, oral.__file__, later.__file__,
             retention.__file__, copy.__file__)
    controls = {'groups_with_class': revisions, 'groups_witness_only': initial, 'fit': fit_variants,
                'routes_with_class': new_routes, 'routes_witness_only': old_routes, 'oral_continuance': known}
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'DEV_labels_opened': False,
        'programs': {role: digest(program) for role, program in programs.items()}, 'executor': executor,
        'B5_original_fit_terminal_sha256': sha(fit / 'terminal.json'), 'B5_prior_was_rejected': True,
        'fit_archive_sha256': digest(sorted(archive_ids)), 'fit_archive_reads': len(archive_ids),
        'original_later_observations': observations, 'grade_sha256': sha(grade),
        'fit_controls_sha256': digest(controls),
        'frozen_hypothesis_routes': {name: value['programs'][TASK] for name, value in new_routes.items()},
        'all_later_positions': [row['position'] for row in forward.values()],
        'residual_positions': [row['position'] for row in residual.values()],
        'later_common_proof_sha256': digest({k: x['proof'] for k, x in forward.items()}),
        'fixed_DEV_public_oral_proofs': [dev_proof_count, len(fixed)],
        'exact_wires_sha256': digest({k: x['wire'] for k, x in residual.items()}),
        'archived_entering_calls_sha256': digest({k: x['entry_id'] for k, x in residual.items()}),
        'planned_new_requests': sum(not row['cache'] for row in residual.values()),
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in paths},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    archive.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'fit_controls.json', controls)
    return out, binding, programs, grade, forward, residual


def measure(out, binding, programs, grade, forward, residual):
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                             sources={'train': list(residual), 'dev': [], 'test': []}, binding=binding)
    executor = parent.FrozenExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = sorted({folder for row in residual.values() for _, folder in row['cache']})
    executor.readiness()
    available = binding['executor']['context_tokens'] - binding['executor']['max_tokens']
    if any(executor.tokenize(row['wire']['messages'], thinking=False)['count'] > available for row in residual.values()):
        raise ValueError('Every original source must fit with the same output budget')
    actor = parent.ProgramActor(executor, out, max_calls=1)
    acquisitions, predictions = {}, {}
    for key, case in forward.items():
        source, proof, copied = (case[field] for field in ('source', 'proof', 'copy'))
        if key in residual:
            write_status(out, {'status': 'running', 'position': case['position']}, POINTER)
            cell, = parent.common_cells(source)
            program = programs[screen.PROPOSAL]
            result = actor.execute(program, cell, 'skill_actor')
            actor.verify_program_result(cell, program, 'skill_actor', result)
            if not result['program_execution_completed']:
                raise ValueError('A transport failure cannot represent the real candidate')
            with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
                acquired = parent.archived(db, source, {'reads': [result], 'native': result['native']},
                                           program, case['wire'])
            acquisitions[key] = {'position': case['position'], 'incumbent': case['entry_id'], 'proposal': acquired}
            offered = {role: shared(source, raw, proof, copied)[TASK] for role, raw in
                       ((screen.INCUMBENT, case['entry']), (screen.PROPOSAL, result['native']))}
        else:
            offered = dict.fromkeys(PROGRAMS, proof[TASK])
        predictions[key] = {name: {TASK: offered[role]} for name, role in binding['frozen_hypothesis_routes'].items()}
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    receipts = immutable_json(out / 'paired_physical_reads.json', acquisitions)
    if sha(grade) != binding['grade_sha256']:
        raise ValueError('Score the unchanged original TRAIN references')
    values = later.score(TASK, forward, predictions, read(grade))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        new = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                              (ledger.run_id + ':%',)))
    planned = binding['planned_new_requests']
    if new != ({'completed': planned} if planned else {}) or counts.get('reserved'):
        raise ValueError('Settle each actual frozen request')
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'paired_physical_reads_sha256': receipts, 'later_original_TRAIN': values,
        'proof_resolved_mothers': len(forward) - len(residual), 'later_mothers': len(forward),
        'new_executor_requests': planned, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': counts,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    write_status(out, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(dispatch):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').exists():
        verify(read(out / 'terminal.json'), 'terminal_sha256')
        print(out, flush=True)
        return
    if not dispatch:
        write_status(out, {'status': 'prepared', 'planned_requests': spec['planned_new_requests']}, POINTER)
        print(out, flush=True)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Dispatch only the registered binding')
    with (out / 'driver.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run'))
    run(parser.parse_args().command == 'run')
