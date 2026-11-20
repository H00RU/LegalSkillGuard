"""Replay negative-covenant witness attribution on exact original MAUD TRAIN reads."""

import json
import sqlite3
from collections import Counter
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from experiments import convergence_revision5_common_native_dev as fixed_dev
from experiments import convergence_revision6_maud_joint_forward as forward
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import maud_negative_witness as witness
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_negative_witness'
POINTER = HANDOFF / f'{STAGE}_current.json'
calibration = forward.calibration
fit, archive, joint = forward.fit, calibration.archive, forward.joint
bound_result = calibration.branch.archive.bound_result
UNCHANGED = {'in_task_excerpt', 'cross_excerpt_unresolved'}


def source_evidence(source, position):
    case = fit.group(source, position)
    if case is None:
        return {}
    return witness.inventory(case['public'], calibration.selective.proof(source))


def check_parents(train, evidence):
    """Verify exact TRAIN witness excerpts against their already audited source parents."""
    proof = {}
    with ZipFile(archive.ARCHIVE) as parents:
        for key, (position, source) in train.items():
            marked = {m: row for m, row in evidence[key].items() if row['placement'] not in UNCHANGED}
            if not marked:
                continue
            public = fit.group(source, position)['public']
            parent = parents.read(f'data/contracts/{source["parent_id"]}.txt')
            if sha256(parent).hexdigest() != source['fulltext_raw_sha256']:
                raise ValueError('Use the exact parent of each original TRAIN excerpt')
            text = archive.unpage(parent.decode('utf-8-sig')).casefold()
            proof[key] = {}
            for marker, row in marked.items():
                excerpt = public['original_excerpts'][row['excerpt']]
                start, end = public['focus_markers'][marker]['range']
                left, right = row['span'] or [max(0, start - 72), min(len(excerpt), end + 72)]
                span = archive.unpage(excerpt[left:right]).casefold()
                if text.count(span) != 1:
                    raise ValueError('The focus and its scope must align to a unique original TRAIN span')
                proof[key][marker] = {'placement': row['placement'], 'span_sha256': digest(span),
                                      'parent_sha256': source['fulltext_raw_sha256']}
    return proof


def forward_reads(cases, known, grade):
    out, binding, terminal = bound_result(forward)
    bank = read(out / 'sealed_predictions.json')
    prompts = read(out / 'wire_tasks.json')
    executor = fit.FrozenExecutor(None, out, binding['executor'])
    if (binding['TRAIN_grade_sha256'] != sha(grade) or digest(prompts) != binding['wire_sha256']
            or digest(cases) != binding['public_cohort_sha256'] or digest(known) != binding['known_scope_sha256']):
        raise ValueError('Require the exact settled forward context, grading, and scope proofs')
    hashes = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            identity = f'{forward.STAGE}-{out.name[:12]}:{digest(key)}'
            physical_wire(db, set(cases), identity, key)
            result, = db.execute('select result from calls where id=?', (identity,)).fetchone()
            raw = json.loads(result)
            payload = read(Path(raw['artifact_directory']) / 'request.json')['payload']
            messages, schema = prompts[key]
            native, error = joint.decode(schema, raw)
            if (forward.query(case) != (messages, schema) or error is not None
                    or payload != executor.payload(messages=messages, thinking=False, schema=schema)
                    or native != bank['raw']['synthesized'][key]):
                raise ValueError('Keep actual joint predictions from the unchanged physical forward requests')
            hashes[key] = digest({'identity': identity, 'request': payload, 'response': raw['content']})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Settle the research ledger before replay')
    return bank, terminal['terminal_sha256'], hashes, ledger


def common_scope(banks, proofs):
    return {role: {key: {family: {'answer': proofs[key][family], 'focus': None}
                        if family in proofs[key] else answer for family, answer in row.items()}
                   for key, row in bank.items()} for role, bank in banks.items()}


def revise(banks, evidence):
    return {role: {key: {**row, 'negative': witness.require_visible_witness(row['negative'], evidence[key])}
                   for key, row in bank.items()} for role, bank in banks.items()}


def score(cases, baseline, after, grade):
    changes = []
    totals = {}
    task = fit.TASKS['negative']
    for role, bank in baseline.items():
        correct, positive, unresolved = [0, 0], [0, 0], [0, 0]
        for key, row in bank.items():
            label = grade[key][task]['answer']
            a, b = row['negative']['answer'], after[role][key]['negative']['answer']
            for i, value in enumerate((a, b)):
                correct[i] += value == label
                positive[i] += value == 'Yes'
                unresolved[i] += value is None
            if a != b:
                changes.append({'role': role, 'position': cases[key]['position'],
                                'reference': label, 'before': a, 'after': b})
        totals[role] = {'negative_correct': correct, 'negative_yes': positive,
                        'negative_unresolved': unresolved, 'units': len(bank)}
    return {'by_role': totals, 'changes': changes}


def run():
    early_config, early_cases, _, early_grade = fit.materials()
    config, later_cases, _, grade, _ = forward.archived.materials()
    _, _, roster = fit.previous.archive_context()
    train = {s['key']: ([batch, i], s) for batch, rows in enumerate(roster, 1)
             for i, s in enumerate(r for r in rows if r['dataset'] == fit.MAUD)}
    dev_roster, _, _, dev_receipt = fixed_dev.archive()
    dev = {s['key']: s for s in dev_roster if s['dataset'] == fit.MAUD}
    if (early_config != config or early_grade != grade or 'train' not in grade.parts
            or len(train) != 24 or len(dev) != 16 or any(s['project_split'] != 'train' for _, s in train.values())
            or any(s['project_split'] != 'dev' for s in dev.values())):
        raise ValueError('Use only original MAUD TRAIN estimates and sealed public DEV coverage')
    evidence = {key: source_evidence(source, position) for key, (position, source) in train.items()}
    dev_evidence = {key: source_evidence(source, None) for key, source in dev.items()}
    parents = check_parents(train, evidence)
    sources = {key: source for key, (_, source) in train.items()}
    proofs = {key: calibration.resolved(calibration.public_proofs(s)) for key, s in sources.items()}
    early, early_receipt, early_calls, _ = calibration.restore(config, early_cases, grade)
    later_receipt, later, later_calls = forward.restore(
        config, later_cases, grade, {key: forward.query(case) for key, case in later_cases.items()},
    )
    beyond, known = forward.select(later_cases, sources)
    measured, forward_receipt, forward_calls, ledger = forward_reads(beyond, known, grade)
    if measured['raw'] != {**{role: {k: bank[k] for k in beyond} for role, bank in later.items()},
                           'synthesized': measured['raw']['synthesized']}:
        raise ValueError('Forward comparisons must reuse the same exact controls as the larger later archive')
    cohorts = {'early': early_cases, 'later_archived': later_cases, 'forward': beyond}
    baseline = {name: common_scope(bank, proofs) for name, bank in
                (('early', early), ('later_archived', later), ('forward', measured['raw']))}
    if baseline['forward'] != measured['same_information']:
        raise ValueError('Keep the original joint-scope forward comparator unchanged')
    revised = {name: revise(bank, evidence) for name, bank in baseline.items()}
    files = (__file__, witness.__file__, forward.__file__, forward.archived.__file__,
             calibration.__file__, archive.__file__, fixed_dev.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN and public DEV coverage', 'TRAIN_grade_sha256': sha(grade),
        'earlier_joint_terminal': early_receipt, 'earlier_joint_requests_sha256': digest(early_calls),
        'later_anchored_terminal': later_receipt, 'later_anchored_requests_sha256': later_calls,
        'forward_terminal': forward_receipt, 'forward_joint_requests_sha256': digest(forward_calls),
        'fixed_DEV_terminal': dev_receipt, 'evidence_sha256': digest([evidence, dev_evidence, parents]),
        'common_proofs_sha256': digest(proofs), 'original_predictions_sha256': digest(baseline), 'TEST_opened': False,
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    fit.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_evidence.json', {'TRAIN': evidence, 'DEV': dev_evidence, 'parents': parents})
    tag = immutable_json(out / 'sealed_predictions.json', {'baseline': baseline, 'visible_witness': revised})
    labels = read(grade)
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'scope_by_train_position': [{'position': train[key][0], 'markers': {m: row['placement'] for m, row in rows.items()},
                                     'negative_reference': labels[key][fit.TASKS['negative']]['answer']}
                                    for key, rows in parents.items()],
        'placement_counts': {split: dict(Counter(row['placement'] for markers in rows.values()
                                                for row in markers.values())) for split, rows in
                             (('TRAIN', evidence), ('public_DEV', dev_evidence))},
        'replay': {name: score(cases, baseline[name], revised[name], labels) for name, cases in cohorts.items()},
        'forward_pair_with_same_scope': calibration.differences(beyond, revised['forward'], labels),
        'TRAIN_mothers': len(train), 'fixed_DEV_public_mothers': len(dev),
        'original_physical_responses': 40 + 3 * len(later_cases) + len(forward_calls), 'new_executor_requests': 0,
        'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False, 'DEV_grades_used': False,
        'parent_only_used_for_attribution': True,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
