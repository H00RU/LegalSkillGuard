"""Evaluate the previously measured operative-edge interface on the fixed MAUD DEV roster."""

import argparse
import fcntl
import json
import sqlite3
from collections import Counter
from pathlib import Path

from experiments import convergence_revision6_maud_excerpt_provenance as release
from experiments import convergence_revision6_maud_governor_dev as comparator
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_locked_operative_dev'
POINTER = HANDOFF / f'{STAGE}_current.json'
prior, measured = comparator.prior, comparator.prior.measured
fit, controls, visible = measured.fit, measured.controls, measured.visible
ROLES = comparator.ROLES


def archived_controls(cases, prompts, executor):
    pointer = read(comparator.POINTER)
    folder = ROOT / pointer['artifact_root']
    terminal = verify(read(folder / 'terminal.json'), 'terminal_sha256')
    binding = read(folder / 'binding.json')
    typed_eligibility = {int(key): value for key, value in binding['eligibility'].items()}
    path = folder / 'sealed_predictions.json'
    old_wire = read(folder / 'wire_tasks.json')
    if (digest({**binding, 'eligibility': typed_eligibility}) != folder.name
            or pointer['terminal_sha256'] != terminal['terminal_sha256']
            or binding['executor'] != executor or terminal['TEST_opened']
            or sha(path) != terminal['predictions_sha256']
            or digest(old_wire) != binding['prompts_sha256']):
        raise ValueError('Bind the exact previously measured DEV controls')
    raw_bank = read(path)['raw']
    engine = fit.FrozenExecutor(None, folder, executor)
    archive = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key in old_wire.keys() & cases.keys():
            for role in controls.CONTROLS:
                if digest(old_wire[key][role]) != digest(prompts[key][role]):
                    continue
                identity = f'{comparator.STAGE}-{folder.name[:12]}:{digest(key)}:{role}'
                row, = db.execute(
                    "select result from calls where id=? and status='completed' and source=? and purpose='skill_dev'",
                    (identity, key),
                ).fetchone()
                response = json.loads(row)
                messages, schema = prompts[key][role]
                exact = read(Path(response['artifact_directory']) / 'request.json')
                native, error = comparator.archived.decode(cases[key], schema, role, response)
                if (exact['payload'] != engine.payload(messages=messages, thinking=False, schema=schema)
                        or exact['id'] != identity or native != raw_bank[role][key] or error):
                    raise ValueError('A comparison read must retain its exact input, result and purpose')
                archive.setdefault(key, {})[role] = {'id': identity, 'native': native}
    return archive, terminal['terminal_sha256']


def prepare():
    checked = release.archived
    _, train_binding, train_end = checked(prior)
    _, original_binding, original_end = checked(measured)
    original_scores = train_end['native_comparison']['correct']
    if (train_binding['operative_edges_terminal'] != original_end['terminal_sha256']
            or sum(original_scores['synthesized'].values()) != 17
            or any(sum(original_scores['synthesized'].values()) <= sum(original_scores[name].values())
                   for name in controls.CONTROLS)
            or sha(ROOT / measured.edges.__file__) != original_binding['source_sha256'][str(
                Path(measured.edges.__file__).relative_to(ROOT))]):
        raise ValueError('Lock the measured operative-edge layout, including its original decoder')
    cohort, _, study, fixed_terminal = comparator.ARCHIVE.archive()
    dev = [row for row in cohort if row['dataset'] == fit.MAUD]
    cases, proofs, excluded = {}, {}, {}
    for position, source in enumerate(dev, 1):
        case = fit.group(source, [position])
        if case is None:
            excluded[str(position)] = 'no visible pandemic marker'
            continue
        public = case['public']
        excerpts = public['original_excerpts']
        old = comparator.governors.anchors.inventory(excerpts)
        anchors = {**old, **comparator.governors.supplemental_inventory(excerpts, old)}
        if {row['candidate_family'] for row in anchors.values()} != set(fit.TASKS):
            excluded[str(position)] = 'both covenant anchor families required'
            continue
        public['candidate_clause_anchors'] = anchors
        key = source['key']
        cases[key] = case
        proofs[key] = {
            'scope': controls.resolved(controls.public_proofs(source)),
            'visibility': visible.source_evidence(source, [position]),
            'preamble': (prior.proof(source) or {}).get('answer', {}),
        }
    if (len(dev) != 16 or len(excluded) + len(cases) != len(dev)
            or any(source['project_split'] != 'dev' for source in dev)
            or study['executor'] != original_binding['executor']):
        raise ValueError('Preserve original fixed DEV and frozen model configuration')
    prompts = {key: {
        'synthesized': measured.query(case),
        **{role: comparator.archived.query(case, role) for role in controls.CONTROLS},
    } for key, case in cases.items()}
    for arms in prompts.values():
        if len({messages[1]['content'] for messages, _ in arms.values()}) != 1:
            raise ValueError('Every reader must receive the same complete public source and anchors')
    archive, control_terminal = archived_controls(cases, prompts, study['executor'])
    grade_name = study['grading_paths'][fit.MAUD]
    grade = ROOT / grade_name
    grade_hash = study['grading_file_sha256'][grade_name]
    dev_root, dev_binding, dev_end = checked(release.release)
    formal = read(dev_root / 'sealed_predictions.json')
    if ('dev' not in grade.parts or sha(grade) != grade_hash or dev_binding['DEV_grade_sha256'] != grade_hash
            or set(next(iter(formal.values()))) != {s['key'] for s in dev}):
        raise ValueError('Bind the unchanged development labels and formal cumulative results')
    bound_files = (__file__, measured.__file__, measured.edges.__file__, comparator.__file__,
                   comparator.governors.__file__, comparator.archived.__file__, prior.__file__,
                   fit.__file__, controls.__file__, visible.__file__)
    spec = {
        'stage': STAGE, 'partition': 'DEV', 'TEST_opened': False, 'executor': study['executor'],
        'candidate_TRAIN_terminal': original_end['terminal_sha256'],
        'scope_TRAIN_terminal': train_end['terminal_sha256'],
        'original_fixed_DEV_terminal': fixed_terminal, 'prior_formal_fixed_DEV_terminal': dev_end['terminal_sha256'],
        'same_input_control_terminal': control_terminal, 'source_proofs_sha256': digest(proofs),
        'wire_tasks_sha256': digest(prompts), 'archived_controls_sha256': digest(archive),
        'archived_exact_reads': sum(len(rows) for rows in archive.values()),
        'planned_reads': len(cases) * len(ROLES) - sum(len(rows) for rows in archive.values()),
        'DEV_grade_sha256': grade_hash, 'eligible_positions': [case['position'][0] for case in cases.values()],
        'excluded_positions': excluded,
        'scope': 'All fixed DEV originals with a visible pandemic marker and both source-anchored covenant families.',
        'native_claim': 'Exploratory fixed DEV comparison of the locked TRAIN layout on different mothers. '
                        'The previous TRAIN paired intervals include zero. No TEST access or expansion.',
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in bound_files},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'wire_tasks.json', prompts)
    fit.snapshot(out, spec['source_sha256'])
    return out, spec, cases, prompts, archive, grade, proofs, formal


def evaluate(cases, native, labels, formal):
    result = controls.differences(cases, native, labels)
    full = {}
    for candidate, output in native.items():
        full[candidate] = {}
        for arm, original in formal.items():
            full[candidate][arm] = {}
            for family, task in fit.TASKS.items():
                paired = [(record['after'][task], (output[key][family]['answer'] if key in output
                                                  else record['after'][task]), labels[key][task]['answer'])
                          for key, record in original.items()]
                full[candidate][arm][family] = {
                    'formal_correct': sum(a == gold for a, b, gold in paired),
                    'combined_correct': sum(b == gold for a, b, gold in paired),
                    'repairs': sum(a != gold and b == gold for a, b, gold in paired),
                    'regressions': sum(a == gold and b != gold for a, b, gold in paired),
                }
    return {'paired_readers': result, 'whole_roster_against_existing_formal_arm': full}


def measure(out, spec, cases, prompts, archive, grade, proofs, formal, job):
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': [], 'dev': list(cases), 'test': []}, binding=spec)
    executor = fit.FrozenExecutor(ledger, out, spec['executor'])
    executor.readiness()
    maximum = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(executor.tokenize(messages, thinking=False)['count'] > maximum
           for arms in prompts.values() for messages, _ in arms.values()):
        raise ValueError('All paired inputs must fit without truncating source text')
    bank, actual = {role: {} for role in ROLES}, []
    for index, (key, case) in enumerate(cases.items()):
        offset = index % len(ROLES)
        for role in ROLES[offset:] + ROLES[:offset]:
            if cached := archive.get(key, {}).get(role):
                bank[role][key] = cached['native']
                continue
            messages, schema = prompts[key][role]
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            write_status(out, {'status': 'running', 'settled': len(actual), 'current_position': case['position'][0],
                               'current_role': role, 'current_request': identity}, POINTER)
            raw = executor.generate(identity, source=key, purpose='skill_dev',
                                    messages=messages, thinking=False, schema=schema)
            fit.verify_physical_response(executor, identity=identity, source=key, purpose='skill_dev',
                                         content_sha256=digest(raw['content']), usage=raw['usage'],
                                         finish_reason=raw['finish_reason'])
            native, error = (measured.decode(case, schema, raw) if role == 'synthesized'
                             else comparator.archived.decode(case, schema, role, raw))
            bank[role][key] = native
            record = {'id': identity, 'tokens': raw['usage']['total_tokens'], 'error': error}
            actual.append(record)
            immutable_json(out / 'responses' / f'{digest(identity)}.json', record)
            print(f'MAUD fixed DEV requests settled {len(actual)}/{spec["planned_reads"]}', flush=True)
    same_scope = visible.common_scope(bank, {key: value['scope'] for key, value in proofs.items()})
    shared = visible.common_scope(visible.revise(same_scope, {key: value['visibility'] for key, value in proofs.items()}),
                                  {key: value['preamble'] for key, value in proofs.items()})
    pred = immutable_json(out / 'sealed_predictions.json', {'raw': bank, 'same_information': shared})
    if sha(grade) != spec['DEV_grade_sha256']:
        raise ValueError('Keep the same development labels across readers')
    labels = read(grade)
    results = {phase: evaluate(cases, outputs, labels, formal)
               for phase, outputs in (('raw', bank), ('same_information', shared))}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if len(actual) != spec['planned_reads'] or totals != {
        **job['ledger_before'], 'completed': job['ledger_before']['completed'] + len(actual),
    }:
        raise ValueError('The continuous research ledger must reconcile all physical reads')
    done = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred,
        'fixed_DEV': results, 'applicable_DEV_mothers': len(cases), 'reused_original_requests': spec['archived_exact_reads'],
        'new_executor_requests': len(actual), 'new_tokens': sum(record['tokens'] for record in actual),
        'decode_errors': dict(Counter(record['error'] for record in actual if record['error'])),
        'new_teacher_requests': 0, 'ledger': totals, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', done)
    write_status(out, {'status': done['status'], 'terminal_sha256': done['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(execute):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').is_file():
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'planned_reads': spec['planned_reads']}, POINTER)
        print(out, flush=True)
        return
    state = read(HANDOFF / 'run_state.json')
    job, = state['active_tasks']
    if out != ROOT / read(POINTER)['artifact_root'] or job['binding_sha256'] != out.name:
        raise ValueError('Register the immutable fixed DEV release before dispatching')
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs, job)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
