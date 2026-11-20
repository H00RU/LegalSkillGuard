"""Forward TRAIN comparison of the joint scope code on unresolved MAUD excerpts."""

import argparse
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision6_maud_covenant_anchors as archived
from experiments import convergence_revision6_maud_joint_scope_controls as calibration
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_joint_forward'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit, joint = calibration.fit, calibration.joint


def select(cases, by_source):
    """Keep the complete later cohort with one-sided cues and unresolved scope."""
    known = {key: calibration.resolved(calibration.public_proofs(by_source[key])) for key in cases}
    selected = {}
    for key, case in cases.items():
        public = case['public']
        cue_excerpts = {marker['excerpt'] for marker in public['focus_markers'].values()}
        if len(public['original_excerpts']) == 2 and len(cue_excerpts) == 1 and set(known[key]) != set(fit.TASKS):
            selected[key] = case
    return selected, {key: known[key] for key in selected}


def query(case):
    messages, schema = joint.query(case)
    detail = messages[0]['content'].removeprefix(fit.GUIDANCE + '\n')
    messages[0]['content'] = f'{archived.GUIDANCE}\n{archived.INSTRUCTIONS}\n{detail}'
    return messages, schema


def restore(config, cases, grade, prompts):
    root, binding, terminal = calibration.branch.archive.bound_result(archived)
    wire = read(root / 'wire_tasks.json')
    predictions = read(root / 'sealed_predictions.json')
    if (binding['executor'] != config or binding['TRAIN_grade_sha256'] != sha(grade)
            or digest(wire) != binding['wire_sha256']):
        raise ValueError('Use the exact prior fixed and direct MAUD reads')
    bank = {role: {} for role in ('fixed', 'direct', 'previous_synthesized')}
    identity_records = set()
    client = fit.FrozenExecutor(None, root, config)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            for role in fit.ROLES:
                identity = f'{archived.STAGE}-{root.name[:12]}:{digest(key)}:{role}'
                physical_wire(db, set(cases), identity, key)
                result, = db.execute('select result from calls where id=?', (identity,)).fetchone()
                raw = json.loads(result)
                payload = read(Path(raw['artifact_directory']) / 'request.json')['payload']
                messages, schema = wire[key][role]
                native, error = archived.decode(case, schema, role, raw)
                if (messages[1] != prompts[key][0][1] or archived.query(case, role) != (messages, schema)
                        or payload != client.payload(messages=messages, thinking=False, schema=schema)
                        or native != predictions[role][key] or error is not None):
                    raise ValueError('Use the same exact source and successfully read original controls')
                identity_records.add(identity)
                bank['previous_synthesized' if role == 'synthesized' else role][key] = native
        current = dict(db.execute('select status,count(*) from calls group by status'))
    if current.get('reserved') or len(identity_records) != 3 * len(cases):
        raise ValueError('Keep the exact settled matched controls for all eligible sources')
    return terminal['terminal_sha256'], bank, digest(sorted(identity_records))


def prepare():
    _, _, prior = calibration.branch.archive.bound_result(calibration)
    evidence = prior['residual_classification_differences']
    if not all(sum(r['joint_minus_control'] for r in evidence
                   if r['control'] == role and r['parent_supports_reference']) >= 2
               and not any(r['joint_minus_control'] < 0 for r in evidence if r['control'] == role)
               for role in calibration.CONTROLS):
        raise ValueError('Require supported beneficial calibration hits against both input-matched readers')
    config, all_cases, _, grade, exclusions = archived.materials()
    _, _, roster = fit.previous.archive_context()
    candidates = {s['key']: s for batch in roster[4:] for s in batch
                  if s['dataset'] == fit.MAUD and s['project_split'] == 'train'}
    cases, known = select(all_cases, candidates)
    if not cases or joint.check_equivalence() != 100:
        raise ValueError('A locked joint code and eligible later cohort are required for a forward replay')
    prompts = {key: query(case) for key, case in cases.items()}
    previous, outputs, old_requests = restore(config, cases, grade, prompts)
    files = (__file__, calibration.__file__, archived.__file__, joint.__file__, fit.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'executor': config,
        'TRAIN_grade_sha256': sha(grade), 'early_scope_terminal': prior['terminal_sha256'],
        'original_anchored_terminal': previous, 'verification_requests_sha256': old_requests,
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files},
        'eligible_positions': sorted(c['position'] for c in cases.values()),
        'known_scope_sha256': digest(known), 'public_cohort_sha256': digest(cases),
        'wire_sha256': digest(prompts), 'controls_sha256': digest(outputs),
        'new_executor_request_count': len(cases),
        'broader_archived_scope': {'covered': len(all_cases), 'excluded': exclusions},
        'registered_rule': 'Use every later original two-excerpt anchor case whose cues occur on one side '
                           'and whose public source proofs leave at least one covenant unresolved.',
        'advance_rule': 'Require a strictly positive paired 95% lower bound against fixed and direct '
                        'on this structural cohort before considering a fixed DEV comparison.',
    }
    root = BASE / STAGE / digest(binding)
    immutable_json(root / 'binding.json', binding)
    immutable_json(root / 'wire_tasks.json', prompts)
    fit.snapshot(root, binding['source_sha256'])
    return root, binding, cases, known, prompts, outputs, grade


def execute(out, binding, cases, known, prompts, outputs, grade):
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': list(cases), 'dev': [], 'test': []}, binding=binding)
    executor = fit.FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    limit = binding['executor']['context_tokens'] - binding['executor']['max_tokens']
    if any(executor.tokenize(messages, thinking=False)['count'] > limit for messages, _ in prompts.values()):
        raise ValueError('All same-information inputs must fit without truncation')
    candidate, receipts = {}, {}
    for index, (key, (messages, schema)) in enumerate(prompts.items()):
        identity = f'{ledger.run_id}:{digest(key)}'
        write_status(out, {'status': 'running', 'completed_mothers': index,
                           'current_request': identity}, POINTER)
        raw = executor.generate(identity, source=key, purpose='skill_actor', messages=messages,
                                schema=schema, thinking=False)
        fit.verify_physical_response(executor, identity=identity, source=key, purpose='skill_actor',
                                     content_sha256=digest(raw['content']), usage=raw['usage'],
                                     finish_reason=raw['finish_reason'])
        candidate[key], error = joint.decode(schema, raw)
        receipts[key] = {'id': identity, 'tokens': raw['usage']['total_tokens'], 'decode_error': error}
        immutable_json(out / 'responses' / f'{digest(key)}.json', {
            **receipts[key], 'native': candidate[key],
        })
        print(f'Forward TRAIN read {index + 1}/{len(cases)} settled', flush=True)
    banks = {**outputs, 'synthesized': candidate}
    comparable = {role: {key: {family: native if family not in known[key] else
                              {'answer': known[key][family], 'focus': None}
                              for family, native in row.items()} for key, row in bank.items()}
                  for role, bank in banks.items()}
    tag = immutable_json(out / 'sealed_predictions.json', {'raw': banks, 'same_information': comparable})
    if 'train' not in grade.parts or sha(grade) != binding['TRAIN_grade_sha256']:
        raise ValueError('Grading may use only the sealed original TRAIN references')
    labels = read(grade)
    scores = calibration.differences(cases, comparable, labels)
    advance = all(scores['paired_joint_scope'][role]['paired_source_bootstrap_95'][0] > 0
                  for role in calibration.CONTROLS)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        run = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                              (ledger.run_id + ':%',)))
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if totals.get('reserved') or run != {'completed': len(cases)}:
        raise ValueError('Require the same three conditions and a settled physical ledger')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'same_information': scores, 'raw': calibration.differences(cases, banks, labels),
        'eligible_positions': binding['eligible_positions'], 'eligible_mothers': len(cases),
        'reused_executor_requests': 3 * len(cases), 'new_executor_requests': run['completed'],
        'new_executor_tokens': sum(row['tokens'] for row in receipts.values()),
        'decode_errors': sum(row['decode_error'] is not None for row in receipts.values()),
        'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': totals,
        'supports_expanded_validation': advance,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


def run(dispatch):
    out, binding, cases, known, prompts, outputs, grade = prepare()
    if (out / 'terminal.json').exists():
        print(out)
        return
    if not dispatch:
        write_status(out, {'status': 'prepared', 'planned_executor_requests': len(cases)}, POINTER)
        print(out)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Dispatch only the unchanged prepared TRAIN comparison')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(out, binding, cases, known, prompts, outputs, grade)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args().execute)
