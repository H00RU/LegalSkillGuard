"""Attribute the operative-edge comparison using public and audited source scope."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_maud_operative_edges as measured
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import maud_covid_law_preambles as preambles
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_operative_attribution'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit, controls = measured.fit, measured.controls


def proof(source):
    text = {v['id']: v['public']['source_text'] for v in source['views']}
    return preambles.proof(*(text[task] for task in fit.TASKS.values()))


def restored(cases, spec, executor, path, raw, wire):
    engine = fit.FrozenExecutor(None, path, executor)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        identities = []
        for key, case in cases.items():
            identity = f'{measured.STAGE}-{path.name[:12]}:{digest(key)}'
            physical_wire(db, set(cases), identity, key)
            encoded, = db.execute('select result from calls where id=?', (identity,)).fetchone()
            actual = json.loads(encoded)
            messages, schema = wire[key]
            payload = read(Path(actual['artifact_directory']) / 'request.json')['payload']
            native, error = measured.decode(case, schema, actual)
            if (measured.query(case) != (messages, schema) or native != raw['synthesized'][key] or error
                    or payload != engine.payload(messages=messages, thinking=False, schema=schema)):
                raise ValueError('Require every exact sealed actual operative-edge request')
            identities.append(identity)
        ledger = dict(db.execute('select status, count(*) from calls group by status'))
    if digest(wire) != spec['matched_wire_sha256'] or ledger.get('reserved'):
        raise ValueError('Keep the matched input and settled ledger')
    return identities, ledger


def sensitivity(cases, banks, labels, omit):
    rows = {role: [row for row in controls.joint.outcomes(cases, bank, labels)
                   if (row['source'], row['view']) not in omit] for role, bank in banks.items()}
    return {'units': len(rows['synthesized']), 'mothers': len(cases),
            'correct': {role: sum(row['grade'] for row in bank) for role, bank in rows.items()},
            'comparisons': {role: paired_source_effect(bank, rows['synthesized'])
                            for role, bank in rows.items() if role != 'synthesized'}}


def run():
    checked = controls.branch.archive.bound_result
    out, scope, run = checked(measured)
    visibility_root, visibility_binding, visibility = checked(measured.visible)
    executor, cases, _, grade, _ = measured.anchored.materials()
    wire = read(out / 'wire_tasks.json')
    prediction_bank = read(out / 'sealed_predictions.json')
    known = read(out / 'same_scope_proofs.json')
    if (sha(grade) != scope['reference_sha256'] or 'train' not in grade.parts
            or sha(out / 'sealed_predictions.json') != run['predictions_sha256']
            or digest([known['known'], known['witness']]) != scope['source_evidence_sha256']
            or visibility['terminal_sha256'] != scope['visibility_terminal']):
        raise ValueError('Use the original frozen comparison and prior visibility audit')
    old, controls_bank, prior_ids = measured.archive.restore(executor, cases, grade, wire)
    raw = prediction_bank['raw']
    if (old != scope['original_anchor_terminal'] or prior_ids != scope['original_control_calls_sha256']
            or any(raw[role] != bank for role, bank in controls_bank.items())):
        raise ValueError('The three archived readers must be identical to the matched comparison')
    calls, ledger = restored(cases, scope, executor, out, raw, wire)
    if ledger != run['ledger']:
        raise ValueError('Only replay the settled experiment with its continuous accounting')
    _, _, roster = fit.previous.archive_context()
    train = {s['key']: s for rows in roster for s in rows if s['dataset'] == fit.MAUD}
    dev = {s['key']: s for s in measured.visible.fixed_dev.archive()[0] if s['dataset'] == fit.MAUD}
    if (len(train), len(dev)) != (24, 16) or any(s['project_split'] != 'dev' for s in dev.values()):
        raise ValueError('Use the original split and public-only fixed DEV coverage')
    proofs = {split: {key: proof(s) for key, s in sources.items()} for split, sources in (('TRAIN', train), ('DEV', dev))}
    raw_parent = read(visibility_root / 'source_evidence.json')
    if digest([raw_parent[k] for k in ('TRAIN', 'DEV', 'parents')]) != visibility_binding['evidence_sha256']:
        raise ValueError('Use the existing source and parent evidence')
    local_exceptions = {key: {name: proof['placement'] for name, proof in entries.items()
                              if proof['placement'] in ('local_branch_closure', 'local_loan_modification')}
                        for key, entries in raw_parent['parents'].items() if key in cases}
    known_corrections = {key: row['answer'] for key, row in proofs['TRAIN'].items() if row and key in cases}
    comparable = measured.visible.common_scope(prediction_bank['comparable'],
                                                {key: known_corrections.get(key, {}) for key in cases})
    files = (__file__, preambles.__file__, preambles.branch.__file__, preambles.anchors.__file__, measured.__file__)
    spec = {'stage': STAGE, 'operative_edges_terminal': run['terminal_sha256'],
            'original_archive_terminal': old, 'visibility_terminal': visibility['terminal_sha256'],
            'TRAIN_grade_sha256': sha(grade), 'actual_calls_sha256': digest(calls),
            'proofs_sha256': digest(proofs), 'local_exception_sha256': digest(local_exceptions),
            'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files},
            'sensitivity_scope': 'Exclude only negative native No labels with a verified in-scope local pandemic exception; '
                                 'retain the complete unchanged native reference scoring in the primary comparison.',
            'DEV_reference_opened': False, 'TEST_opened': False}
    stage = BASE / STAGE / digest(spec)
    immutable_json(stage / 'binding.json', spec)
    fit.snapshot(stage, spec['source_sha256'])
    immutable_json(stage / 'source_proofs.json', proofs)
    tag = immutable_json(stage / 'sealed_predictions.json', comparable)
    labels = read(grade)
    negative = fit.TASKS['negative']
    excluded = {(key, negative) for key, facts in local_exceptions.items()
                if facts and labels[key][negative]['answer'] == 'No'}
    scored = controls.differences(cases, comparable, labels)
    refined = sensitivity(cases, comparable, labels, excluded)
    advance = all(row['paired_source_bootstrap_95'][0] > 0 for check in (
        scored['paired_joint_scope'], refined['comparisons']) for role, row in check.items() if role in controls.CONTROLS)
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': stage.name, 'predictions_sha256': tag,
        'verified_new_reads': len(calls), 'archived_matched_reads': 3 * len(cases),
        'public_preamble_coverage': {split: [sum(map(bool, by_source.values())), len(by_source)]
                                    for split, by_source in proofs.items()},
        'classified_preamble_positions': [cases[key]['position'] for key in known_corrections],
        'native_comparison': scored, 'source_fidelity_sensitivity': refined,
        'scope_label_disagreement_positions': [cases[key]['position'] for key, _ in sorted(excluded)],
        'supports_expanded_validation': advance, 'DEV_reference_opened': False, 'TEST_opened': False,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(stage / 'terminal.json', result)
    write_status(stage, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(stage, flush=True)


if __name__ == '__main__':
    run()
