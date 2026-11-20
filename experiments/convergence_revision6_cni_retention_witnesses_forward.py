"""Run the locked retention witness layout on the three original later TRAIN contracts."""

import argparse
import fcntl
import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_retention_witnesses as fit
from experiments import convergence_revision6_cni_task_screen_forward as wire_archive
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_retention_witnesses_forward'
POINTER = HANDOFF / f'{STAGE}_current.json'
ROLES = fit.ROLES


def decode(case, role, schema, result):
    if role == 'synthesized':
        return fit.witness.decode(case['payload'], schema, result)
    return fit.archived.interface.decode(case['payload'], role, schema, result)


def prepare():
    state = read(HANDOFF / 'run_state.json')
    if (state['phase'] not in (fit.STAGE + '_fit_settled', STAGE + '_running')
            or any(job['stage'] != STAGE for job in state['active_tasks'])):
        raise ValueError('Continue with the locked favorable early TRAIN layout')
    original = state[fit.STAGE]
    source = ROOT / read(fit.POINTER)['artifact_root']
    binding = read(source / 'binding.json')
    terminal = verify(read(source / 'terminal.json'), 'terminal_sha256')
    lib = verify(read(source / 'TRAIN_batch_libraries/B4.json'), 'snapshot_sha256')
    if (not terminal['advance'] or terminal['TEST_opened'] or original['terminal_sha256'] != terminal['terminal_sha256']
            or lib['TRAIN_terminal'] != terminal['terminal_sha256'] or lib['binding_sha256'] != source.name
            or binding['later_unresolved_positions'] != lib['forward_scope']
            or digest(binding) != source.name or sha(source / 'sealed_predictions.json') != terminal['predictions_sha256']
            or any(sha(ROOT / name) != key for name, key in binding['source_sha256'].items())):
        raise ValueError('Do not change any fitted layout or scoring source')
    train, _, grade, observations = fit.prior.notice.archived.collect(*fit.prior.notice.archived.archive_context(), 'train')
    positions = {tuple(pos) for pos in lib['forward_scope']}
    if len(positions) != 3 or 'train' not in grade.parts or sha(grade) != binding['grade_sha256']:
        raise ValueError('Evaluate only the three prespecified later TRAIN cases')
    cases = {key: {**fit.archived.case(row), 'position': [idx // 3 + 1, idx % 3 + 1]}
             for idx, (key, row) in enumerate(train.items()) if (idx // 3 + 1, idx % 3 + 1) in positions}
    if len(cases) != len(positions):
        raise ValueError('The original chronological evaluation roster changed')
    rules = {key: fit.common_proof(case) for key, case in cases.items()}
    wires = {key: {role: (fit.witness.query(case['payload']) if role == 'synthesized' else
                         fit.archived.interface.request(case['payload'], role))
                   for role in ROLES} for key, case in cases.items()}
    if any(len({messages[1]['content'] for messages, _ in variants.values()}) != 1 for variants in wires.values()):
        raise ValueError('All three roles must receive the exact same question, source and evidence index')
    executor = fit.archived.FrozenExecutor(None, source, binding['executor'])
    cached = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, arms in wires.items():
            cached[key] = {}
            for role, (messages, schema) in arms.items():
                wire = executor.payload(messages=messages, thinking=False, schema=schema)
                for identity, _ in wire_archive.existing_requests(db, key, wire):
                    if identity.startswith(STAGE + '-'):
                        continue
                    encoded, = db.execute('select result from calls where id=?', (identity,)).fetchone()
                    native, issue = decode(cases[key], role, schema, json.loads(encoded))
                    if issue is None:
                        cached[key][role] = {'identity': identity, 'native': native}
                        break
    paths = {**binding['source_sha256'], str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))}
    spec = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'executor': binding['executor'],
            'fit_terminal': terminal['terminal_sha256'], 'fit_library': lib['snapshot_sha256'],
            'TRAIN_grade_sha256': sha(grade), 'public_sources_sha256': digest(cases), 'wire_sha256': digest(wires),
            'shared_proofs_sha256': digest(rules), 'archive_cache_sha256': digest(cached),
            'planned_new_requests': len(cases) * len(ROLES) - sum(len(rows) for rows in cached.values()),
            'positions': [row['position'] for row in cases.values()], 'observed_original_TRAIN': observations,
            'source_sha256': paths}
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    fit.prior.previous.employee.base.prior.cumulative.snapshot(out, paths)
    immutable_json(out / 'wire_tasks.json', wires)
    immutable_json(out / 'common_rules_and_exact_cache.json', {'shared': rules, 'cached': cached})
    return out, spec, cases, wires, rules, cached, grade


def measure(out, spec, cases, wires, rules, cached, grade):
    state = read(HANDOFF / 'run_state.json')
    job, = state['active_tasks']
    if job['stage'] != STAGE or job['binding_sha256'] != out.name or job['planned_requests'] != spec['planned_new_requests']:
        raise ValueError('Use the registered forward comparison and continuous ledger')
    ledger = fit.archived.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                          sources={'train': list(cases), 'dev': [], 'test': []}, binding=spec)
    model = fit.archived.FrozenExecutor(ledger, out, spec['executor'])
    model.readiness()
    cap = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(model.tokenize(messages, thinking=False)['count'] > cap
           for arms in wires.values() for messages, _ in arms.values()):
        raise ValueError('Each comparison uses the complete original source')
    bank, calls = {role: {} for role in ROLES}, []
    for index, (key, case) in enumerate(cases.items()):
        for role in ROLES[index % len(ROLES):] + ROLES[:index % len(ROLES)]:
            if prior := cached[key].get(role):
                bank[role][key] = prior['native']
                continue
            messages, schema = wires[key][role]
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            write_status(out, {'status': 'running', 'settled': len(calls), 'position': case['position'], 'role': role}, POINTER)
            response = model.generate(identity, source=key, purpose='skill_actor', messages=messages, schema=schema, thinking=False)
            verify_physical_response(model, identity=identity, source=key, purpose='skill_actor',
                                     content_sha256=digest(response['content']), usage=response['usage'],
                                     finish_reason=response['finish_reason'])
            native, error = decode(case, role, schema, response)
            bank[role][key] = native
            row = {'identity': identity, 'position': case['position'], 'role': role, 'error': error,
                   'tokens': response['usage']['total_tokens']}
            immutable_json(out / 'responses' / f'{digest(identity)}.json', {**row, 'prediction': native})
            calls.append(row)
    after = {role: {key: rules[key] or native for key, native in rows.items()} for role, rows in bank.items()}
    tag = immutable_json(out / 'sealed_predictions.json', {'raw': bank, 'shared': after})
    if sha(grade) != spec['TRAIN_grade_sha256'] or 'train' not in grade.parts:
        raise ValueError('Use the same original TRAIN grade after sealing')
    labels = read(grade)
    raw, _ = fit.archived.score(cases, bank, labels)
    matched, effects = fit.archived.score(cases, after, labels)
    reliable = all(
        max(effects[role]['grade']['paired_source_bootstrap_95'][0],
            effects[role]['grounded']['paired_source_bootstrap_95'][0]) > 0
        and min(effects[role]['grade']['mean_change'], effects[role]['grounded']['mean_change']) >= 0
        for role in ('fixed', 'direct')
    )
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls group by status'))
    if len(calls) != spec['planned_new_requests'] or counts != {
        **job['ledger_before'], 'completed': job['ledger_before']['completed'] + len(calls),
    }:
        raise ValueError('Reconcile all physical requests in the continuous ledger')
    endpoint = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'n_forward_mothers': len(cases), 'raw_native': raw, 'same_information': matched, 'paired': effects,
        'common_proof_count': sum(bool(v) for v in rules.values()), 'errors': sum(row['error'] is not None for row in calls),
        'new_executor_requests': len(calls), 'reused_archive_requests': sum(len(rows) for rows in cached.values()),
        'new_teacher_requests': 0, 'tokens': sum(row['tokens'] for row in calls), 'ledger': counts,
        'independent_forward_gate_passed': reliable, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', endpoint)
    write_status(out, {'status': endpoint['status'], 'terminal_sha256': endpoint['terminal_sha256']}, POINTER)
    print(out)


def run(action):
    out, spec, *rest = prepare()
    if (out / 'terminal.json').exists():
        return
    if action == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_requests': spec['planned_new_requests']}, POINTER)
        print(out, spec['planned_new_requests'])
        return
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *rest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
