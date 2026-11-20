"""Select the actual B4 recipient update and compare the routes on original B5 TRAIN."""

import argparse
import base64
import fcntl
import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_recipient_acquisition as roles
from experiments.convergence_formal_train_fit import ORDINARY
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b4_recipient_selection'
POINTER = HANDOFF / f'{STAGE}_current.json'
ROUTES = ('incumbent', 'proposal')
TASKS = roles.TASKS


def wire(source, program, executor):
    cell, = common_cells(source)
    bundle = source_bundle(cell)
    predicate, = program['predicates']
    if (predicate['schema_mode'] != 'native' or predicate['id'] != 'read' or program['extractors']
            or program['composition'].strip() != 'def compose(inputs, predict, extractors):\n'
            '    return predict("read", {"public": inputs["public"], "answer_schema": inputs["native_answer_schema"]})'):
        raise ValueError('Use the two original one-read native programs')
    schema = record_schema({'value': wire_schema(roles.CNI, bundle)})
    messages = [
        {'role': 'system', 'content': predicate['prompt'] + '\nReturn compact JSON matching this exact schema: '
         + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))},
        {'role': 'user', 'content': json.dumps({'public': bundle['public'], 'answer_schema': bundle['answer_schema']},
                                             ensure_ascii=False, sort_keys=True)},
    ]
    return request_payload(executor, messages=messages, thinking=False, schema=schema)


def archived(db, source, result, program, expected):
    identity = roles.RETENTION.verify_prediction(db, source['key'], result)
    roles.verify_public_wire(db, source, identity)
    readout, = result['reads']
    if readout['execution']['program_sha256'] != digest(program) or readout['native'] != result['native']:
        raise ValueError('Reproduce the original program and native decoding')
    raw, = db.execute('select result from calls where id=?', (identity,)).fetchone()
    request = read(Path(json.loads(raw)['artifact_directory']) / 'request.json')['payload']
    if request != expected:
        raise ValueError('The reconstructed one-read input differs from the original physical request')
    return identity


def common(source, native):
    views = {v['id']: v for v in source['views']}
    paired = roles.complete_group(views[TASKS[0]])
    employee = roles.employees.witness(views[TASKS[0]])
    result = {task: native[task] for task in TASKS}
    if paired:
        return paired[1]
    result[TASKS[0]] = roles.employees.project(result[TASKS[0]], employee)
    return result


def select(groups, residual_gain):
    """Ranking can use the shared archive. Each policy screens one complete group."""
    latest = max(groups, key=lambda row: row['position'])
    disagree = max(groups, key=lambda row: (row['disagreement'], row['position']))
    candidate = max(groups, key=lambda row: (row['source_confirmed_repairs'], row['position']))
    result = {}
    for policy, row in (('chronological', latest), ('answer_disagreement', disagree),
                        ('candidate_driven', candidate)):
        adopt = residual_gain > 0 and row['source_confirmed_repairs'] > 0
        result[policy] = {'position': row['position'], 'route': 'proposal' if adopt else 'incumbent',
                          'screened_reads': 2}
    result['native_fit_only'] = {'position': None, 'route': 'proposal' if residual_gain > 0 else 'incumbent',
                                 'screened_reads': 0}
    return result


def score(sources, bank, grade):
    values, effects = roles.grades(sources, bank, grade)
    return {'scores': values, 'paired_candidate_driven': effects}


def prepare_materials():
    fit, spec, terminal = roles.replay.bound.bound_stage(fit_pointer(4))
    dev, observation, observed = roles.replay.bound.bound_stage(observe_pointer(5))
    decisions = read(fit / 'matched_decisions.json')
    folder = fit / 'candidates' / ORDINARY / roles.CNI
    candidate = read(folder / 'measurements.json')
    prior = read(folder / 'prior_TRAIN_regression.json')
    teacher = decisions['teacher'][ORDINARY][roles.CNI]
    if (spec['checkpoint_root'] != observation['checkpoint_root'] or spec['executor'] != observation['executor']
            or terminal['batch'] != 4 or observed['batch'] != 5
            or digest(decisions) != terminal['matched_decisions_sha256'] or teacher['selected'] != 'candidate'
            or teacher['predictions_sha256'] != digest(candidate['predictions'])
            or teacher['earlier_TRAIN_regression']['evidence_sha256'] != digest(prior)):
        raise ValueError('Require the original B4 adopted ordinary proposal and B5 observation')
    root = ROOT / spec['checkpoint_root']
    study = read(root / 'binding.json')
    roster = roles.RETENTION.load_roster(study)
    journal = TrainingJournal(root, study, roster)
    libraries = {route: journal.library(ORDINARY, b) for route, b in zip(ROUTES, (3, 4), strict=True)}
    programs = {route: library['programs'][roles.CNI] for route, library in libraries.items()}
    if (programs['proposal'] != candidate['candidate']
            or any(roles.CNI in x.get('schema_proposals', {}) for x in libraries.values())):
        raise ValueError('Keep actual native programs and the original adoption')

    original = {b: [s for s in roster[b - 1] if s['dataset'] == roles.CNI] for b in range(1, 6)}
    if any(len(group) != 3 or any(s['project_split'] != 'train' for s in group) for group in original.values()):
        raise ValueError('The calibration cutoff and B5 must be unchanged original TRAIN sources')
    grade_rel = observation['native_grade_paths'][roles.CNI]
    grade = ROOT / grade_rel
    grade_sha = observation['native_grade_sha256'][grade_rel]
    if 'train' not in grade.parts or sha(grade) != grade_sha:
        raise ValueError('Require the original TRAIN grading file')
    training_keys = {source['key'] for batch in range(1, 5) for source in original[batch]}
    labels = {key: value for key, value in read(grade).items() if key in training_keys}
    groups, calibration, forward, received = [], {}, {}, set()
    matched_wires = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for b, sources in original.items():
            for i, source in enumerate(sources):
                key = source['key']
                wires = {route: wire(source, p, spec['executor']) for route, p in programs.items()}
                if {**wires['proposal'], 'messages': wires['incumbent']['messages']} != wires['incumbent'] or (
                        wires['proposal']['messages'][1:] != wires['incumbent']['messages'][1:]):
                    raise ValueError('Programs must see the same full public source, schema and executor')
                if b == 5:
                    result = read(journal.directory(ORDINARY, b) / 'predictions' / f'{digest(key)}.json')
                    seal = journal._observations(ORDINARY, b)
                    if (digest(result) != seal['predictions'][key]
                            or seal['train_observation_sha256'] != observed['observation_receipts'][ORDINARY]):
                        raise ValueError('Verify the exact adopted B5 archive')
                    paid = archived(db, source, result['result'], programs['proposal'], wires['proposal'])
                    needle = json.dumps(wires['incumbent'], ensure_ascii=False).encode()
                    existing = []
                    for call, payload in db.execute(
                        "select id,result from calls where source=? and role='executor' and purpose='skill_actor' "
                        "and status='completed' and id not like ? order by reserved_at", (key, STAGE + '-%')
                    ):
                        folder = Path(json.loads(payload)['artifact_directory'])
                        wire_path = folder / 'wire_request.json'
                        if wire_path.is_file() and base64.b64decode(read(wire_path)['body_b64']) == needle:
                            existing.append((call, folder.parent.parent))
                    forward[key] = {'source': source, 'proposal': result['result']['native'],
                                    'archived_choice': paid, 'entry_replays': existing}
                    matched_wires[key] = wires
                    continue
                if b < 4:
                    old, new = prior['before'][key], prior['candidate'][key]
                else:
                    saved = read(journal.directory(ORDINARY, b) / 'predictions' / f'{digest(key)}.json')
                    if digest(saved) != journal._observations(ORDINARY, b)['predictions'][key]:
                        raise ValueError('Verify the original B4 entering prediction seal')
                    old, new = saved['result'], candidate['predictions'][key]
                raw = dict(zip(ROUTES, (old, new), strict=True))
                paid = {archived(db, source, z, programs[route], wires[route]) for route, z in raw.items()}
                if len(paid) != 2 or received & paid:
                    raise ValueError('Count each original matched response once')
                received.update(paid)
                calibration[key] = {route: common(source, record['native']) for route, record in raw.items()}
                view = next(v for v in source['views'] if v['id'] == TASKS[0])
                found = roles.complete_group(view)
                if not found:
                    continue
                form, proof = found
                correct = [proof[task]['answer'] for task in TASKS]
                if correct != [labels[key][task]['answer'] for task in TASKS]:
                    raise ValueError('The independent role proof must agree with original TRAIN labels')
                reads = {route: [record['native'][task]['answer'] for task in TASKS] for route, record in raw.items()}
                screen = roles.screen(key, view, proof, reads)
                groups.append({'position': [b, i], 'form': form, 'same_information_screen': screen,
                               'disagreement': sum(a != z for a, z in zip(*reads.values(), strict=True)),
                               'source_confirmed_repairs': sum(a != y for a, y in
                                                               zip(reads['incumbent'], correct, strict=True))
                               if screen['proposal'] and not screen['incumbent'] else 0})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(received) != 24 or len(groups) < 2:
        raise ValueError('Require all original calibration reads and a settled ledger')
    correct = {route: sum(r[route][task]['answer'] == labels[key][task]['answer']
                          for key, r in calibration.items() for task in TASKS) for route in ROUTES}
    choices = select(groups, correct['proposal'] - correct['incumbent'])
    paths = (__file__, roles.__file__, roles.employees.__file__, ProgramActor.__module__.replace('.', '/') + '.py',
             'legal_skill_guard/paired_interfaces/control_programs.py',
             'legal_skill_guard/paired_interfaces/control_answers.py', 'legal_skill_guard/rr/client.py')
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'partition': 'TRAIN', 'executor': spec['executor'],
        'B4_fit_sha256': sha(fit / 'terminal.json'), 'B5_observation_sha256': sha(dev / 'terminal.json'),
        'programs': {route: digest(p) for route, p in programs.items()}, 'grade_sha256': grade_sha,
        'scope': list(TASKS), 'calibration_correct': correct, 'screens_sha256': digest(groups),
        'selection_sha256': digest(choices), 'calibration_archive_sha256': digest(sorted(received)),
        'B5_wires_sha256': digest(matched_wires), 'B5_proposal_calls_sha256': digest(
            [info['archived_choice'] for info in forward.values()]),
        'B5_incumbent_replay_ids': sorted(call for row in forward.values() for call, _ in row['entry_replays']),
        'planned_new_calls': sum(not info['entry_replays'] for info in forward.values()),
        'source_sha256': {str((ROOT / f).resolve().relative_to(ROOT)): sha(ROOT / f) for f in paths},
        'advance_rule': 'Require a positive source-paired classification lower bound against the one-group '
                        'chronological and disagreement controls, with no decrease in correct-class evidence.',
    }
    return binding, programs, groups, choices, forward, matched_wires, grade


def run(phase):
    binding, programs, groups, choices, forward, wires, grade = prepare_materials()
    if (choices['candidate_driven']['route'] == choices['chronological']['route']
            and choices['candidate_driven']['route'] == choices['answer_disagreement']['route']):
        raise ValueError('Neither equal-budget comparison would change the trained route')
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    immutable_json(out / 'screening.json', {'groups': groups, 'policies': choices})
    for name, choice in choices.items():
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', sealed({
            'fit_batch': 4, 'binding_sha256': out.name, 'scope': list(TASKS), 'selection': choice,
            'program_sha256': binding['programs'][choice['route']],
        }, 'snapshot_sha256'))
    if (out / 'terminal.json').is_file():
        print(out)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'physical_requests_planned': binding['planned_new_calls']}, POINTER)
        print(out)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Run only the prepared B5 comparison')
    with (out / 'driver.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, binding, programs, choices, forward, wires, grade)


def measure(out, binding, programs, choices, forward, wires, grade):
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                            sources={'train': list(forward), 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = sorted({root for info in forward.values() for _, root in info['entry_replays']})
    executor.readiness()
    actor = ProgramActor(executor, out, max_calls=1)
    banks = {phase: {name: {} for name in choices} for phase in ('archived_native', 'shared_source_rules')}
    receipts = set()
    for i, (key, info) in enumerate(forward.items()):
        source = info['source']
        write_status(out, {'status': 'running', 'settled_mothers': i}, POINTER)
        cell, = common_cells(source)
        result = actor.execute(programs['incumbent'], cell, 'skill_actor')
        actor.verify_program_result(cell, programs['incumbent'], 'skill_actor', result)
        with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
            call = archived(db, source, {'reads': [result], 'native': result['native']},
                            programs['incumbent'], wires[key]['incumbent'])
        receipts.add(call)
        raw = {'incumbent': result['native'], 'proposal': info['proposal']}
        for name, choice in choices.items():
            row = raw[choice['route']]
            banks['archived_native'][name][key] = {task: row[task] for task in TASKS}
            banks['shared_source_rules'][name][key] = common(source, row)
        print(f'B5 reads settled {i + 1}/{len(forward)}', flush=True)
    prediction_sha = immutable_json(out / 'sealed_predictions.json', banks)
    if sha(grade) != binding['grade_sha256']:
        raise ValueError('Require original B5 grades only after sealing')
    scores = {phase: score({key: row['source'] for key, row in forward.items()}, bank, grade)
              for phase, bank in banks.items()}
    gate = scores['shared_source_rules']['paired_candidate_driven']
    advance = all(gate[control]['grade']['paired_source_bootstrap_95'][0] > 0
                  and gate[control]['correct_evidence_f1']['mean_change'] >= 0
                  for control in ('chronological', 'answer_disagreement'))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                 (ledger.run_id + ':%',)))
        total = dict(db.execute('select status,count(*) from calls group by status'))
    expected = binding['planned_new_calls']
    if counts != ({'completed': expected} if expected else {}) or total.get('reserved'):
        raise ValueError('Keep the original planned cost and settled physical ledger')
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'scores': scores,
                       'advance': advance, 'forward_mothers': len(forward), 'predictions_sha256': prediction_sha,
                       'archive_requests_reused': 27 + len(receipts) - expected,
                       'new_executor_requests': expected, 'new_teacher_requests': 0, 'ledger': total,
                       'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
