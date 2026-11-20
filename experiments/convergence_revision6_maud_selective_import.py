"""Evaluate source-bound preamble imports on original MAUD TRAIN and fixed DEV."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_maud_branch_preamble as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import maud_selective_import as links
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_selective_import'
POINTER = HANDOFF / f'{STAGE}_current.json'
NEGATIVE = prior.fit.TASKS['negative']


def proof(source):
    excerpts = {v['id']: v['public']['source_text'] for v in source['views']}
    return links.compile_import(*(excerpts[task] for task in prior.fit.TASKS.values()))


def apply(answer, evidence):
    if evidence is not None and evidence['negative_import_includes_pandemic_condition']:
        return 'Yes'
    return answer


def archived_anchors(db, keys, cases, grade):
    original = prior.previous.exp
    root, binding, terminal = prior.archive.bound_result(original)
    wires = read(root / 'wire_tasks.json')
    decoded = read(root / 'sealed_predictions.json')
    if sha(grade) != binding['TRAIN_grade_sha256'] or digest(wires) != binding['wire_sha256']:
        raise ValueError('Use the exact original clause-anchor comparison')
    measured = {}
    for key in keys:
        measured[key] = {}
        for role in prior.fit.ROLES:
            messages, schema = wires[key][role]
            identity = f'{original.STAGE}-{root.name[:12]}:{digest(key)}:{role}'
            physical_wire(db, set(keys), identity, key)
            (body,) = db.execute('select result from calls where id=?', (identity,)).fetchone()
            raw = json.loads(body)
            request = read(Path(raw['artifact_directory']) / 'request.json')['payload']
            executor = prior.fit.FrozenExecutor(None, root, binding['executor'])
            native, error = original.decode(cases[key], schema, role, raw)
            if (request != executor.payload(messages=messages, thinking=False, schema=schema)
                    or error is not None or native != decoded[role][key]):
                raise ValueError('Confirm the actual matched TRAIN requests and native decisions')
            measured[key][role] = native
    return measured, terminal['terminal_sha256']


def run():
    _, cases, _, grade, _ = prior.previous.exp.materials()
    _, _, batches = prior.fit.previous.archive_context()
    train = {s['key']: ([b, i], s) for b, rows in enumerate(batches, 1)
             for i, s in enumerate(r for r in rows if r['dataset'] == prior.fit.MAUD)}
    _, cohort, originals, study, _ = prior.release.base_actor()
    dev = {s['key']: s for s in cohort if s['dataset'] == prior.fit.MAUD and s['project_split'] == 'dev'}
    if len(train) != 24 or len(dev) != 16 or any(s['project_split'] != 'train' for _, s in train.values()):
        raise ValueError('Require the full original MAUD TRAIN and fixed DEV rosters')
    training = {k: p for k, (_, s) in train.items() if (p := proof(s)) is not None}
    development = {k: p for k, s in dev.items() if (p := proof(s)) is not None}
    if not training or not training.keys() <= cases.keys():
        raise ValueError('Require matched original reads for every TRAIN proof in this archive')
    earlier, earlier_bind, prior_dev = prior.archive.bound_result(prior.release)
    fixed = read(earlier / 'sealed_predictions.json')
    if fixed.keys() != originals.keys() or any(rows.keys() != dev.keys() for rows in fixed.values()):
        raise ValueError('Preserve the fixed DEV controls from the previous section release')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        observations, prior_fit = archived_anchors(db, training, cases, grade)
        dev_calls = prior.release.parallel.verify_original_inputs(db, originals, dev, development)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('The total ledger must be settled')
    predictions = {
        arm: {key: {'before': pair['after'], 'after': {
            **pair['after'], NEGATIVE: apply(pair['after'][NEGATIVE], development.get(key)),
        }} for key, pair in rows.items()}
        for arm, rows in fixed.items()
    }
    dev_rel = study['grading_paths'][prior.fit.MAUD]
    dev_grade = ROOT / dev_rel
    hashes = {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
        __file__, links.__file__, links.parallel.__file__, links.section.__file__, links.anchors.__file__,
        prior.release.__file__, prior.previous.exp.__file__,
    )}
    spec = {
        'stage': STAGE, 'TEST_opened': False, 'TRAIN_grade_sha256': sha(grade),
        'DEV_grade_sha256': earlier_bind['DEV_grade_sha256'], 'previous_TRAIN_terminal': prior_fit,
        'previous_fixed_DEV_terminal': prior_dev['terminal_sha256'], 'source_sha256': hashes,
        'proofs_sha256': digest({'TRAIN': training, 'DEV': development}),
        'rule': 'An explicit affirmative preamble import proves Yes. An excluded import does not '
                'establish the absence of an independent local exception.',
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    prior.fit.snapshot(out, hashes)
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    immutable_json(out / 'source_proofs.json', {'TRAIN': training, 'DEV': development})
    if ('train' not in grade.parts or 'dev' not in dev_grade.parts
            or sha(dev_grade) != spec['DEV_grade_sha256'] or sha(grade) != spec['TRAIN_grade_sha256']):
        raise ValueError('Read the original labels only after sealing the scope proofs and predictions')
    labels = read(grade)
    detail = []
    for key, p in training.items():
        native = {arm: value['negative'] for arm, value in observations[key].items()}
        detail.append({
            **p, 'position': train[key][0], 'original_negative_reference': labels[key][NEGATIVE]['answer'],
            'observed_answers_and_markers': native,
            'projected_after': {arm: apply(row['answer'], p) for arm, row in native.items()},
        })
    dev_scores = prior.release.score(dev, predictions, read(dev_grade))
    if any(task[NEGATIVE]['correct'][0] != prior_dev['score'][arm][NEGATIVE]['correct'][-1]
           for arm, task in dev_scores.items()):
        raise ValueError('Preserve the exact cumulative fixed DEV references')
    new_release = any(row[NEGATIVE]['repairs'] for row in dev_scores.values()) and all(
        not row[NEGATIVE]['regressions'] for row in dev_scores.values())
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'TRAIN_proofs': detail, 'TRAIN_mothers': len(train), 'DEV_proofs': list(development.values()),
        'DEV_mothers': len(dev), 'fixed_DEV': dev_scores, 'positive_common_DEV_gain': new_release,
        'archived_reads_verified': {'TRAIN': len(training) * len(prior.fit.ROLES), 'DEV': dev_calls},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
