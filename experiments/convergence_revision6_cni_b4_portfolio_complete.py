"""Complete the single missing exact read in the locked B4 portfolio."""

import argparse
import fcntl
import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_b4_candidate_portfolio as fit
from experiments import convergence_revision6_cni_b4_portfolio_later as later
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b4_portfolio_complete'
POINTER = HANDOFF / f'{STAGE}_current.json'


def prepare():
    _, selection, enrolled = fit.terminal(fit)
    archive, previous, measured = fit.terminal(later)
    before = archive / 'sealed_predictions.json'
    missing = measured['missing_by_position']
    if (previous['B4_portfolio_terminal'] != enrolled['terminal_sha256']
            or measured['native_units_without_exact_matched_reads'] != 1
            or sha(before) != measured['predictions_sha256'] or len(missing) != 1):
        raise ValueError('Require one exact missing later evaluation in the locked portfolio')
    (location, absent), = missing.items()
    (task, readers), = absent.items()
    (role,) = readers
    if role != 'ordinary_incumbent':
        raise ValueError('Use only the archived ordinary entering program for the missing read')
    cases, grade, programs, executor, schema = later.inputs(selection)
    key, source = next((key, row) for key, (row, pos) in cases.items() if '-'.join(map(str, pos)) == location)
    proof = fit.current_proofs(source)
    if task in proof or task not in enrolled['different_hypotheses']:
        raise ValueError('A new request requires an unresolved switched hypothesis')
    program = programs[role]
    wire = later.replay.input_wire(source, program, executor)
    needed = {choice['programs'][task] for choice in enrolled['choices'].values()} - {role}
    controls, receipts = {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for name in sorted(needed):
            candidate = name == 'parse_proposal'
            expected = (later.parse.schema_wire(source, schema, executor) if candidate else
                        later.replay.input_wire(source, programs[name], executor))
            if expected['messages'][1:] != wire['messages'][1:] or {
                k: v for k, v in expected.items() if k not in ('messages', 'response_format')
            } != {k: v for k, v in wire.items() if k not in ('messages', 'response_format')}:
                raise ValueError('Every comparison reader must receive identical original public source and settings')
            receipt, native = later.exact(db, source, expected, schema if candidate else None)
            if receipt is None:
                raise ValueError('Only one exact measurement may be missing')
            controls[name] = fit.ordinary.apply_proofs(source, native, proof)[task]
            receipts[name] = receipt
    spec = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'executor': executor,
        'locked_B4_choice_terminal': enrolled['terminal_sha256'], 'partial_B6_B8_terminal': measured['terminal_sha256'],
        'source_position': location, 'program_sha256': digest(program), 'hypothesis': task,
        'exact_wire_sha256': digest(wire), 'controls_sha256': digest(controls), 'archived_control_reads_sha256': digest(receipts),
        'TRAIN_grade_sha256': sha(grade), 'planned_requests': 1, 'previous_pair_sha256': measured['predictions_sha256'],
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, fit.__file__, later.__file__, fit.parent.__file__, Path(ProgramActor.execute.__code__.co_filename),
        )},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    fit.archive.snapshot(out, spec['source_sha256'])
    return out, spec, wire, source, program, role, controls, cases, enrolled['choices'], grade, read(before)


def measure(out, spec, wire, source, program, role, controls, cases, choices, grade, banks, job):
    key = source['key']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if later.replay.existing_requests(db, key, wire):
            raise ValueError('An exact carrier already exists; recover it instead of dispatching again')
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                             sources={'train': [key], 'dev': [], 'test': []}, binding=spec)
    executor = FrozenExecutor(ledger, out, spec['executor'])
    executor.readiness()
    cap = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if executor.tokenize(wire['messages'], thinking=False)['count'] > cap:
        raise ValueError('Keep the complete original source text in the matched read')
    write_status(out, {'status': 'running', 'settled': 0, 'source_position': spec['source_position']}, POINTER)
    actor = ProgramActor(executor, out, max_calls=1)
    cell, = fit.parent.common_cells(source)
    observed = actor.execute(program, cell, 'skill_actor')
    actor.verify_program_result(cell, program, 'skill_actor', observed)
    bundle = {'reads': [observed], 'native': observed['native']}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        identity = fit.parent.archived(db, source, bundle, program, wire)
        totals = dict(db.execute('select status,count(*) from calls group by status'))
        encoded, = db.execute('select result from calls where id=?', (identity,)).fetchone()
    if totals != {**job['ledger_before'], 'completed': job['ledger_before']['completed'] + 1}:
        raise ValueError('The continuous ledger must reconcile the one new physical response')
    task = spec['hypothesis']
    controls[role] = fit.ordinary.apply_proofs(source, observed['native'], fit.current_proofs(source))[task]
    for name, choice in choices.items():
        banks[name][key][task] = controls[choice['programs'][task]]
    tag = immutable_json(out / 'sealed_predictions.json', banks)
    if 'train' not in grade.parts or sha(grade) != spec['TRAIN_grade_sha256']:
        raise ValueError('Use only the byte-identical original TRAIN grade')
    scores = later.compare(cases, banks, read(grade))
    if any(rows['units'] != 27 for rows in scores['native'].values()) or len(cases) != 9:
        raise ValueError('Score every one of the 27 locked hypothesis instances')
    done = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'match': {'physical_call': identity, 'source_position': spec['source_position'], 'task': task,
                  'tokens': json.loads(encoded)['usage']['total_tokens'], 'candidate_answers': controls},
        'B6_B8_paired': scores, 'new_executor_requests': 1,
        'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': totals,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', done)
    write_status(out, {'status': done['status'], 'terminal_sha256': done['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(execute):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').exists():
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'planned_requests': 1}, POINTER)
        print(out, flush=True)
        return
    state = read(HANDOFF / 'run_state.json')
    job, = state['active_tasks']
    if out != ROOT / read(POINTER)['artifact_root'] or job['binding_sha256'] != out.name:
        raise ValueError('Register the exact one-call binding before dispatch')
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs, job)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
