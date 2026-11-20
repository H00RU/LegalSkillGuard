"""Evaluate sealed B8 adoption policies on the same OpenExempt DEV requests."""

import argparse
import fcntl
import json
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_formal_curves as curves
from experiments import convergence_revision6_oe_b8_portfolio as fit
from experiments import convergence_revision6_oe_pa_civilian_assets as release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_ev_inventory
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_b8_screened_dev'
POINTER = HANDOFF / f'{STAGE}_current.json'
PORTS = ('EC', 'EV')
CARRIERS = {
    'proposal': (8, 'common_teacher_skill_learning'),
    'parse': (8, 'strongest_matched_external_baseline'),
}


def programs():
    spec, terminal, _ = release.previous.previous.locked_result(
        fit.POINTER, 'predictions.json', 'predictions_sha256',
    )
    out = ROOT / read(fit.POINTER)['artifact_root']
    if terminal['TRAIN_mothers'] != 4:
        raise ValueError('Require the sealed original B8 TRAIN decisions')
    selected = terminal['fit']['after']['signed']
    routes = {name: decision['route'] for name, decision in selected.items()}
    for name, route in routes.items():
        checkpoint = verify(read(out / 'TRAIN_batch_libraries' / f'{name}.json'), 'snapshot_sha256')
        if (checkpoint['binding_sha256'] != out.name or checkpoint['decision'] != selected[name]
                or checkpoint['programs_by_task'] != dict(zip(PORTS, (spec['provenance']['programs'][role]
                                                                    for role in route), strict=True))):
            raise ValueError('Each composed route must match its sealed TRAIN decision and library')
    routes['adopted_ordinary'] = ['proposal', 'proposal']
    if {role for route in routes.values() for role in route} != {*CARRIERS, 'incumbent'}:
        raise ValueError('Use only the reader versions actually carried by the original DEV cells')
    return spec, terminal, routes


def signature(payload):
    """Allow a reversible answer layout while matching all legal input and settings."""
    user, = (json.loads(row['content']) for row in payload['messages'] if row['role'] == 'user')
    if set(user) != {'answer_schema', 'public'}:
        raise ValueError('Match the entire legal input in its native public container')
    native_view, = user['public']['native_views']
    settings = {key: value for key, value in payload.items() if key not in ('messages', 'response_format')}
    return native_view['id'], digest([settings, user['public']])


def input_signature(db, identities, source):
    signatures = {}
    for identity in identities:
        record, = db.execute(
            "select result from calls where id=? and source=? and status='completed' and purpose='skill_dev'",
            (identity, source),
        ).fetchone()
        result = json.loads(record)
        payload = read(Path(result['artifact_directory']) / 'request.json')['payload']
        task, finger = signature(payload)
        if task in signatures:
            raise ValueError('Each reader must have exactly one actual read per native task')
        signatures[task] = finger
    if set(signatures) != set(PORTS):
        raise ValueError('Use both fixed DEV tasks for every reader')
    return signatures


def restore(db, root, journal, cohort, versions, carriers):
    bank, receipts, identities, signatures = {}, {}, set(), {}
    compare = fit.common.previous
    for role, (batch, arm) in carriers.items():
        library = journal.library(arm, batch)
        program = library.get('schema_proposals', {}).get(fit.OE) or library['programs'][fit.OE]
        folder = root / 'dev' / f'B{batch}' / arm
        seal, cell, task = (read(folder / name) for name in ('prediction_seal.json', 'scores.json', 'task.json'))
        if (digest(program) != versions[role] or task['partition'] != 'dev'
                or task['arm'] != arm or task['batch'] != batch
                or task['public_cohort_sha256'] != digest(cohort)
                or cell['libraries'] != task['libraries']
                or cell['libraries'][fit.OE] != library['snapshot_sha256']
                or cell['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(task)):
            raise ValueError('Verify exact fitted program versions against the formal fixed DEV cells')
        verify(cell, 'cell_sha256')
        verify(seal, 'prediction_seal_sha256')
        bank[role] = {}
        for source in cohort:
            if source['dataset'] != fit.OE:
                continue
            key = source['key']
            used = set()
            compare.physical_dev(db, source, folder, seal, cell, used, PORTS)
            fingerprint = input_signature(db, used, key)
            if signatures.setdefault(key, fingerprint) != fingerprint:
                raise ValueError('All paired readers must see the exact same public source and frozen settings')
            identities.update(used)
            record = read(folder / 'predictions' / f'{digest(key)}.json')
            bank[role][key] = {task: row['answer'] for task, row in record['result']['native'].items()}
        receipts[role] = {
            'cell_sha256': cell['cell_sha256'], 'prediction_seal_sha256': seal['prediction_seal_sha256'],
            'program_sha256': digest(program), 'DEV_batch': batch, 'DEV_arm': arm,
        }
    if len(signatures) != 16 or any(len(rows) != 16 for rows in bank.values()):
        raise ValueError('Every OpenExempt DEV mother must appear in every reader')
    return bank, receipts, identities, signatures


def common_output(native, source, category):
    key = source['key']
    views = fit.common.previous.views_of(source)
    row = fit.previous.same_controls({'views': views, 'answers': {'role': native}})
    checks = release.shared(row, key, 'role', category, {key: release.prior.source_proof(source)})
    return release.project(checks, release.proof_for(views))


def scores(banks, labels, positions):
    units = {role: [{
        'source': key, 'view': task, 'grade': release.prior.fit.grade(task, row[task], labels[key][task]),
    } for key, row in values.items() for task in PORTS] for role, values in banks.items()}
    native = {role: {task: mean(row['grade'] for row in rows if row['view'] == task)
                     for task in PORTS} for role, rows in units.items()}
    learner = units['candidate_driven']
    effects = {}
    for role, rows in units.items():
        if role == 'candidate_driven':
            continue
        by_task = {}
        for task in PORTS:
            before, after = ([row for row in group if row['view'] == task] for group in (rows, learner))
            diffs = [(a['source'], b['grade'] - a['grade']) for a, b in zip(before, after, strict=True)]
            by_task[task] = {
                **paired_source_effect(before, after),
                'repairs': [positions[key] for key, val in diffs if val > 0],
                'regressions': [positions[key] for key, val in diffs if val < 0],
            }
        effects[role] = {'average_native_F1': paired_source_effect(rows, learner), **by_task}
    return {'F1': native, 'candidate_driven_minus_control': effects}


def prepare():
    fit_spec, fit_terminal, routes = programs()
    _, cohort, _, study, _ = fit.common.previous.release.base_actor()
    dev = {source['key']: source for source in cohort if source['dataset'] == fit.OE}
    if len(dev) != 16 or any(source['project_split'] != 'dev' for source in dev.values()):
        raise ValueError('Use all original OpenExempt DEV sources')
    _, cfg, _ = fit.previous.forward.prior.archive.bound_stage(fit.formal.pointer(8))
    root = ROOT / cfg['checkpoint_root']
    if read(root / 'binding.json') != study:
        raise ValueError('Require the same underlying fixed study')
    journal = fit.previous.forward.exact.TrainingJournal(root, study, fit.formal.load_roster(study))
    versions = fit_spec['provenance']['programs']
    incumbent = journal.library('method_two_only', 7)['programs'][fit.OE]
    if digest(incumbent) != versions['incumbent']:
        raise ValueError('B4 must carry the exact B7 entering program during fixed DEV')
    curve_out, curve, curve_end = fit.previous.forward.prior.archive.bound_stage(curves.pointer(8))
    if (curve['executor'] != study['executor'] or curve_end['TEST_opened']
            or not curve['ev_asset_inventory_wire'] or not curve['oe_public_jurisdiction_scope']):
        raise ValueError('Use the exact frozen B8 DEV executor and source augmentations')
    category_root, category_lock, _ = release.checked.bound_result(fit.common)
    categories = read(category_root / 'source_proofs.json')
    if digest(categories) != category_lock['evidence_sha256']:
        raise ValueError('Use the sealed common source category proofs')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        archive, receipts, calls, signatures = restore(db, root, journal, cohort, versions, CARRIERS)
        _, rejected_receipt, historical, b4_users = restore(
            db, root, journal, cohort, versions, {'incumbent': (4, 'method_two_only')},
        )
        exact_roots = set()
        for source in dev:
            for (encoded,) in db.execute(
                "select result from calls where source=? and role='executor' and purpose='skill_dev' "
                "and status='completed' and id not like ?", (source, STAGE + '-%'),
            ):
                folder = Path(json.loads(encoded)['artifact_directory'])
                if folder.parent.name == 'calls' and (folder / 'wire_request.json').is_file():
                    exact_roots.add(str(folder.parent.parent.relative_to(ROOT)))
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(calls) != 64 or len(historical) != 32 or calls & historical:
        raise ValueError('Count the exact current control responses and the distinct mismatched B4 reads')
    differences = {task: sum(b4_users[key][task] != signatures[key][task] for key in dev) for task in PORTS}
    if differences != dict.fromkeys(PORTS, len(dev)):
        raise ValueError('Check which previously executed incumbents need exact current reads')
    name = study['grading_paths'][fit.OE]
    grade = ROOT / name
    grade_hash = study['grading_file_sha256'][name]
    if 'dev' not in grade.parts or sha(grade) != grade_hash:
        raise ValueError('Keep the exact originally labeled DEV partition')
    dependencies = (__file__, fit.__file__, release.__file__, release.prior.__file__,
                    release.civilian.__file__, release.previous.__file__, fit.common.__file__, fit.previous.__file__,
                    convergence_ev_inventory.__file__, curves.__file__,
                    *(ROOT / f for f in ('legal_skill_guard/paired_interfaces/formal_actors.py',
                                         'legal_skill_guard/paired_interfaces/control_programs.py',
                                         'legal_skill_guard/skill_evolution/clients.py')))
    spec = {
        'stage': STAGE, 'partition': 'DEV', 'TEST_opened': False, 'prior_B8_TRAIN_terminal': fit_terminal['terminal_sha256'],
        'TRAIN_locked_routes': routes, 'DEV_carriers': receipts, 'public_inputs_sha256': digest(signatures),
        'physical_DEV_calls_sha256': digest(sorted(calls)), 'DEV_grade_sha256': grade_hash,
        'DEV_mothers': len(dev), 'native_tasks': list(PORTS), 'executor': curve['executor'],
        'formal_current_DEV_terminal_sha256': sha(curve_out / 'terminal.json'),
        'incumbent_sha256': digest(incumbent), 'mismatched_historical_DEV_carrier': rejected_receipt,
        'mismatched_historical_DEV_reads': differences, 'exact_replay_roots': sorted(exact_roots),
        'planned_matched_incumbent_reads': len(dev) * len(PORTS),
        'source_sha256': {str(Path(file).relative_to(ROOT)): sha(Path(file)) for file in dependencies},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    fit.previous.snapshot(out, spec['source_sha256'])
    return out, spec, dev, grade, categories, signatures, archive, incumbent


class MatchedExecutor(FrozenExecutor):
    def generate(self, identity, *, source, purpose, messages, thinking, schema):
        task, finger = signature(self.payload(messages=messages, thinking=thinking, schema=schema))
        if finger != self.expected[source][task]:
            raise ValueError('The registered incumbent must receive the exact same B8 public input')
        return super().generate(identity, source=source, purpose=purpose, messages=messages,
                                thinking=thinking, schema=schema)


def measure(out, spec, dev, grade, categories, fingerprints, archive, incumbent, job):
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                             sources={'train': [], 'dev': list(dev), 'test': []}, binding=spec)
    client = MatchedExecutor(ledger, out, spec['executor'])
    client.expected = fingerprints
    client.exact_replay_roots = [ROOT / path for path in spec['exact_replay_roots']]
    client.readiness()
    actor = ProgramActor(client, out, max_calls=1)
    archive['incumbent'] = {}
    used = set()
    for index, (key, source) in enumerate(dev.items()):
        scoped = convergence_ev_inventory.with_ev_inventory(source, jurisdiction_scope=True)
        native = {}
        for one in common_cells(scoped):
            task, = [view['id'] for view in one['views']]
            write_status(out, {'status': 'running', 'matched_reads_settled': len(used),
                               'current_mother_index': index + 1, 'current_task': task}, POINTER)
            result = actor.execute(incumbent, one, 'skill_dev')
            trace, = [row for row in result['execution']['traces'] if row.get('type', 'predicate') == 'predicate']
            if 'raw_content' not in trace:
                raise ValueError('Every completed comparison requires an actual frozen physical receipt')
            used.add(trace['physical_call_id'])
            native[task] = result['native'][task]['answer']
        archive['incumbent'][key] = native
        print(f'Paired DEV sources settled {index + 1}/{len(dev)}', flush=True)
    if len(used) != spec['planned_matched_incumbent_reads']:
        raise ValueError('Every incumbent native task must have its own exact physical response')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
        added = {identity: json.loads(result)['usage']['total_tokens'] for (identity, result) in db.execute(
            'select id,result from calls where id like ? and status=?',
            (f'{ledger.run_id}:%', 'completed'),
        )}
    if set(added) - used or totals.get('reserved') or totals != {
        **job['ledger_before'], 'completed': job['ledger_before']['completed'] + len(added),
    }:
        raise ValueError('The continuous ledger must reconcile all matched incumbent requests')
    common = {arm: {key: common_output(row, dev[key], categories['dev'])
                    for key, row in values.items()} for arm, values in archive.items()}
    routes = spec['TRAIN_locked_routes']
    route_banks = {
        stage: {name: {key: {task: rows[role][key][task] for task, role in zip(PORTS, route, strict=True)}
                       for key in dev} for name, route in routes.items()}
        for stage, rows in (('matched_wire', archive), ('common_source_rules', common))
    }
    immutable_json(out / 'matched_incumbent_call_ids.json', sorted(used))
    tag = immutable_json(out / 'sealed_predictions.json', route_banks)
    if sha(grade) != spec['DEV_grade_sha256']:
        raise ValueError('The fixed DEV annotations must remain immutable')
    labels = read(grade)
    positions = {key: index for index, key in enumerate(dev, 1)}
    results = {stage: scores(bank, labels, positions) for stage, bank in route_banks.items()}
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'paired_fixed_DEV': results, 'TRAIN_locked_routes': routes, 'DEV_mothers': len(dev),
        'physical_exact_DEV_calls_reused': 64 + len(used) - len(added), 'new_executor_requests': len(added),
        'new_tokens': sum(added.values()), 'incumbent_physical_ids_sha256': digest(sorted(used)),
        'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': totals,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(execute):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').exists():
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'matched_incumbent_reads': spec['planned_matched_incumbent_reads']}, POINTER)
        print(out, flush=True)
        return
    state = read(HANDOFF / 'run_state.json')
    job, = state['active_tasks']
    if ROOT / read(POINTER)['artifact_root'] != out or job['binding_sha256'] != out.name:
        raise ValueError('Dispatch only the registered replay binding')
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs, job)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
