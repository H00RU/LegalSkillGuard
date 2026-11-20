"""Validate the frozen B4 PARSE screening decision on all later TRAIN contracts."""

import argparse
import fcntl
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from experiments import convergence_revision6_cni_task_screen_b4_later as ordinary_later
from experiments import convergence_revision6_cni_task_screen_parse as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_schema_control import measure_schema
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_task_screen_parse_later'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, screen, CNI = prior.archive, prior.screen, prior.CNI
replay, parent = ordinary_later.replay, ordinary_later.parent
ROLES = (screen.INCUMBENT, screen.PROPOSAL)


class WireCaptured(Exception):
    pass


class CaptureWire:
    """Intercept the production schema reader before any dispatch."""

    ledger = SimpleNamespace(run_id='offline-exact-wire')

    def generate(self, identity, *, source, purpose, messages, schema, thinking):
        self.parameters = {'messages': messages, 'schema': schema, 'thinking': thinking}
        raise WireCaptured


def schema_wire(source, candidate, executor):
    reader = CaptureWire()
    cell, = parent.common_cells(source)
    try:
        measure_schema(reader, ROOT, cell, candidate, 'skill_actor')
    except WireCaptured:
        return parent.request_payload(executor, **reader.parameters)
    raise ValueError('The production schema read did not construct a request')


def prepare():
    pointer = read(prior.POINTER)
    origin = ROOT / pointer['artifact_root']
    old = verify(read(origin / 'terminal.json'), 'terminal_sha256')
    fit = read(origin / 'binding.json')
    if (digest(fit) != origin.name or old['terminal_sha256'] != pointer['terminal_sha256']
            or sha(origin / 'sealed_predictions.json') != old['predictions_sha256']
            or old['hypotheses_with_different_adoption'] != ['nda-7'] or old['TEST_opened']):
        raise ValueError('Reuse the locked positive B4 PARSE contrast and its exact candidate')
    (task,) = old['hypotheses_with_different_adoption']
    policies = {name: spec['programs'][task] for name, spec in old['policies'].items()}
    root, study, roster = archive.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    protocol, _, _, schema, _, grade_path = archive.b4.materials()
    grade = ROOT / grade_path
    executor = study['executor']
    entering = journal.library(archive.EXTERNAL_ARM, 3)['programs'][CNI]
    versions = {screen.INCUMBENT: digest(entering), screen.PROPOSAL: digest(schema)}
    if ('train' not in grade.parts or sha(grade) != fit['TRAIN_grade_sha256']
            or versions[screen.PROPOSAL] != protocol['proposal_sha256'] or protocol['executor'] != executor):
        raise ValueError('Preserve the original TRAIN, programs and frozen executor')
    for name, role in policies.items():
        library = verify(read(origin / 'TRAIN_batch_libraries' / f'{name}.json'), 'snapshot_sha256')
        if library['binding_sha256'] != origin.name or library['hypothesis_programs'][task] != versions[role]:
            raise ValueError('Carry the exact same B4 program assignment into the later cohort')
    cases = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch in (6, 7, 8):
            for position, source in enumerate((s for s in roster[batch - 1] if s['dataset'] == CNI), 1):
                key = source['key']
                if source['project_split'] != 'train':
                    raise ValueError('Only the nine original later TRAIN contracts may enter this comparison')
                proof = prior.ordinary.proof_for(source)
                if task in proof:
                    raise ValueError('The registered comparison screens only after checking common source determinacy')
                wires = {screen.INCUMBENT: replay.input_wire(source, entering, executor),
                         screen.PROPOSAL: schema_wire(source, schema, executor)}
                if len({digest({k: val for k, val in wire.items() if k not in ('messages', 'response_format')})
                        for wire in wires.values()}) != 1 or len({digest(wire['messages'][1:]) for wire in wires.values()}) != 1:
                    raise ValueError('Both readers must receive the same unmodified public input and executor settings')
                matches = {role: [pair for pair in replay.existing_requests(db, key, wire)
                                  if not pair[0].startswith(STAGE + '-')] for role, wire in wires.items()}
                cases[key] = {'source': source, 'position': [batch, position], 'proof': proof, 'wires': wires, 'replay': matches}
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise ValueError('Wait for any current frozen executor request')
    if len(cases) != 9:
        raise ValueError('Keep the full later-cohort denominator')
    paths = (__file__, prior.__file__, prior.ordinary.__file__, ordinary_later.__file__, replay.__file__,
             Path(measure_schema.__code__.co_filename))
    lock = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'B4_PARSE_selection': old['terminal_sha256'],
            'hypothesis': task, 'frozen_hypothesis_routes': policies, 'programs': versions,
            'public_positions': [row['position'] for row in cases.values()], 'executor': executor, 'grade_sha256': sha(grade),
            'wires_sha256': digest({key: row['wires'] for key, row in cases.items()}),
            'exact_replay_ids': sorted(identity for row in cases.values() for pairs in row['replay'].values() for identity, _ in pairs),
            'planned_new_requests': sum(not pairs for row in cases.values() for pairs in row['replay'].values()),
            'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in paths}}
    return lock, cases, entering, schema, grade, origin


def measure(out, lock, cases, entering, schema, grade, origin):
    task = lock['hypothesis']
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                            sources={'train': list(cases), 'dev': [], 'test': []}, binding=lock)
    executor = parent.FrozenExecutor(ledger, out, lock['executor'])
    executor.exact_replay_roots = sorted({path for row in cases.values() for pairs in row['replay'].values() for _, path in pairs})
    executor.readiness()
    limit = lock['executor']['context_tokens'] - lock['executor']['max_tokens']
    if any(executor.tokenize(wire['messages'], thinking=False)['count'] > limit
           for row in cases.values() for wire in row['wires'].values()):
        raise ValueError('All original full-input readers must fit the frozen model')
    actor = parent.ProgramActor(executor, out, max_calls=1)
    predictions, paid = {}, {}
    for index, (key, row) in enumerate(cases.items()):
        source = row['source']
        cell, = parent.common_cells(source)
        bank = {}
        roles = ROLES if index % 2 == 0 else ROLES[::-1]
        for role in roles:
            write_status(out, {'status': 'running', 'position': row['position'], 'reader': role,
                               'settled_reads': len(paid)}, POINTER)
            if role == screen.INCUMBENT:
                response = actor.execute(entering, cell, 'skill_actor')
                actor.verify_program_result(cell, entering, 'skill_actor', response)
                record = {'reads': [response], 'native': response['native']}
            else:
                response = measure_schema(executor, out, cell, schema, 'skill_actor')
                record = {'schema_reads': [response], 'native': response['native']}
            with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
                identity, _ = archive.physical(db, source, record, entering, schema if role == screen.PROPOSAL else None)
                raw, = db.execute('select result from calls where id=?', (identity,)).fetchone()
            request = read(Path(json.loads(raw)['artifact_directory']) / 'request.json')['payload']
            if request != row['wires'][role]:
                raise ValueError('The measured request differs from the bound original native or reversible wire')
            paid[identity] = [row['position'], role]
            bank[role] = prior.ordinary.apply_proofs(source, record['native'], row['proof'])[task]
            print('Settled', row['position'], role, bank[role]['handled'], flush=True)
        predictions[key] = {name: {task: bank[role]} for name, role in lock['frozen_hypothesis_routes'].items()}
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    immutable_json(out / 'physical_receipts.json', paid)
    if sha(grade) != lock['grade_sha256'] or len(paid) != 18:
        raise ValueError('Preserve the original labels and both physical responses for each source')
    scores = ordinary_later.score(task, cases, predictions, read(grade))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        total = dict(db.execute('select status,count(*) from calls group by status'))
        own = dict(db.execute('select status,count(*) from calls where id like ? group by status', (ledger.run_id+':%',)))
    expected = lock['planned_new_requests']
    if own != ({'completed': expected} if expected else {}) or total.get('reserved'):
        raise ValueError('Every planned original reader must settle on the continuous ledger')
    prior_b5 = verify(read(origin / 'terminal.json'), 'terminal_sha256')
    result = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
                     'later_original_TRAIN': scores, 'later_mothers': len(cases),
                     'earlier_B5_same_screen_terminal': prior_b5['terminal_sha256'], 'TEST_opened': False,
                     'new_executor_requests': expected, 'new_teacher_requests': 0, 'ledger': total}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(execute):
    lock, *materials = prepare()
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    archive.snapshot(out, lock['source_sha256'])
    if (out / 'terminal.json').is_file():
        print(out)
    elif not execute:
        write_status(out, {'status': 'prepared', 'planned_new_requests': lock['planned_new_requests']}, POINTER)
        print(out, lock['public_positions'], lock['planned_new_requests'])
    else:
        if ROOT / read(POINTER)['artifact_root'] != out:
            raise ValueError('Dispatch the prepared full-cohort comparison only')
        with (out / 'driver.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            measure(out, lock, *materials)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args().execute)
