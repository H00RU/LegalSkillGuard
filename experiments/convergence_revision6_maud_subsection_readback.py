"""Replay the same express subsection scope rule on all matched MAUD readers."""

import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision6_maud_covenant_anchors as exp
from experiments import convergence_revision6_maud_section_reference as release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import maud_subsection_proviso as proviso
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_subsection_readback'
POINTER = HANDOFF / 'revision6_maud_subsection_readback_current.json'


def proof(source):
    views = {view['id']: view['public']['source_text'] for view in source['views']}
    return proviso.attachment(*(views[task] for task in exp.fit.TASKS.values()))


def run():
    config, cases, _, grade, _ = exp.materials()
    root = ROOT / read(exp.POINTER)['artifact_root']
    binding, wire = (read(root / name) for name in ('binding.json', 'wire_tasks.json'))
    terminal = verify(read(root / 'terminal.json'), 'terminal_sha256')
    predictions = root / 'sealed_predictions.json'
    if (digest(binding) != root.name or root.name != terminal['binding_sha256'] or terminal['TEST_opened']
            or sha(grade) != binding['TRAIN_grade_sha256'] or digest(wire) != binding['wire_sha256']
            or sha(predictions) != terminal['predictions_sha256']):
        raise ValueError('Use the exact settled clause-anchor comparison')
    predictions = read(predictions)
    _, _, roster = exp.fit.previous.archive_context()
    train = {s['key']: ([b, i], s) for b, rows in enumerate(roster, 1)
             for i, s in enumerate(row for row in rows if row['dataset'] == exp.fit.MAUD)}
    _, dev_cohort, _, _, _ = release.base_actor()
    dev = [s for s in dev_cohort if s['dataset'] == exp.fit.MAUD]
    if len(train) != 24 or len(dev) != 16 or any(s['project_split'] != 'dev' for s in dev):
        raise ValueError('Require the original MAUD TRAIN and fixed DEV rosters')
    all_proofs = {key: proof(source) for key, (_, source) in train.items()}
    dev_proofs = [proof(source) for source in dev]
    train_hits = {key: {**p, 'position': train[key][0]} for key, p in all_proofs.items() if p is not None}
    matched = {k: p for k, p in train_hits.items() if k in cases}
    corrected = {role: {k: ({'ordinary': {'answer': 'Yes', 'focus': None},
                            'negative': {'answer': 'No', 'focus': None}} if k in matched else native)
                        for k, native in bank.items()} for role, bank in predictions.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved'):
            raise ValueError('Settle the matched comparison before replay')
        executor = exp.fit.FrozenExecutor(None, root, config)
        calls = {}
        for key, case in cases.items():
            for role in exp.fit.ROLES:
                call = f'{exp.STAGE}-{root.name[:12]}:{digest(key)}:{role}'
                physical_wire(db, set(cases), call, key)
                result, = db.execute('select result from calls where id=?', (call,)).fetchone()
                raw = json.loads(result)
                messages, schema = wire[key][role]
                payload = read(Path(raw['artifact_directory']) / 'request.json')['payload']
                if payload != executor.payload(messages=messages, thinking=False, schema=schema):
                    raise ValueError('The actual request must have the same wire and source')
                if exp.decode(case, schema, role, raw)[0] != predictions[role][key]:
                    raise ValueError('Score the original native output for every reader')
                calls[call] = raw['request_hash']
    hashes = {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in
              (__file__, exp.__file__, proviso.__file__, proviso.section.__file__)}
    spec = {'previous_TRAIN_terminal': terminal['terminal_sha256'], 'TRAIN_grade_sha256': sha(grade),
            'TRAIN_proofs_sha256': digest(train_hits), 'DEV_proofs_sha256': digest(dev_proofs),
            'physical_requests_sha256': digest(calls), 'source_sha256': hashes, 'TEST_opened': False}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    exp.fit.snapshot(out, hashes)
    immutable_json(out / 'TRAIN_proofs.json', train_hits)
    tag = immutable_json(out / 'sealed_predictions.json', corrected)
    labels = read(grade)
    scores, effects = exp.fit.score(cases, corrected, labels)
    outcome = sealed({'status': 'settled_revision6_maud_subsection_readback', 'binding_sha256': out.name,
                      'TRAIN_proofs': list(train_hits.values()), 'DEV_proof_count': sum(p is not None for p in dev_proofs),
                      'matched_TRAIN_proofs': len(matched), 'TRAIN_original_requests_verified': len(calls),
                      'before': terminal['scores'], 'shared_source_rule_scores': scores, 'effects': effects,
                      'predictions_sha256': tag, 'ledger': ledger,
                      'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', outcome)
    write_status(out, {'status': outcome['status'], 'terminal_sha256': outcome['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
