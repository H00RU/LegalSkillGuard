"""Attribute duplicate-anchor recovery on the same archived MAUD reader outputs."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_maud_operative_attribution as attribution
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import maud_anchor_idempotence as anchors
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_anchor_idempotence'
POINTER = HANDOFF / f'{STAGE}_current.json'
measured, fit, controls = attribution.measured, attribution.fit, attribution.controls
anchored = measured.anchored


def negative_only(sources, positions):
    eligible = []
    for key, source in sources.items():
        case = fit.group(source, positions[key])
        if case is None:
            continue
        public = case['public']
        tasks = public['task_excerpts']
        cues = {row['excerpt'] for row in public['focus_markers'].values()}
        if tasks['ordinary'] != tasks['negative'] and cues == {tasks['negative']}:
            eligible.append(key)
    return eligible


def independent_coverage(late):
    _, _, roster = fit.previous.archive_context()
    train, coordinates = {}, {}
    for batch, sources in enumerate(roster, 1):
        for index, source in enumerate(row for row in sources if row['dataset'] == fit.MAUD):
            train[source['key']] = source
            coordinates[source['key']] = [batch, index]
    dev_cohort = [row for row in measured.visible.fixed_dev.archive()[0] if row['dataset'] == fit.MAUD]
    dev = {source['key']: source for source in dev_cohort}
    _, early, _, _ = fit.materials()
    if (len(train), len(dev)) != (24, 16) or any(row['project_split'] != 'train' for row in train.values()) \
            or any(row['project_split'] != 'dev' for row in dev.values()):
        raise ValueError('Require the exact registered TRAIN and original fixed DEV rosters')
    training_matches = negative_only(train, coordinates)
    dev_matches = negative_only(dev, {s['key']: i for i, s in enumerate(dev_cohort)})
    return {'TRAIN_total': len(train), 'fixed_DEV_total': len(dev),
            'negative_only_TRAIN_positions': [coordinates[key] for key in training_matches],
            'remaining_unmeasured_TRAIN_positions': [coordinates[key] for key in training_matches if key not in (early | late)],
            'fixed_DEV_matches': len(dev_matches), 'DEV_grades_read': False,
            'public_TRAIN_sha256': digest(train), 'public_DEV_sha256': digest(dev)}


def decode(case, schema, role, raw):
    if role == 'synthesized':
        original = lambda response: measured.decode(case, schema, response)
        first, second = 'first', 'second'
    elif role == 'previous_synthesized':
        original = lambda response: anchored.decode(case, schema, 'synthesized', response)
        first, second = 'first_anchor', 'second_anchor'
    else:
        raise ValueError('Only the two original layouts with two witness slots can repeat an edge')
    native, error = original(raw)
    if error:
        return native, native, {}, error
    observations = json.loads(raw['content'])
    candidates = case['public']['candidate_clause_anchors']
    prior = observations['observations']
    folded = {key: anchors.fold_pair(row, candidates, first, second) for key, row in prior.items()}
    changed = {marker: row[first] for marker, row in folded.items() if row != prior[marker]}
    if not changed:
        return native, native, changed, None
    wire = {**observations, 'observations': folded}
    revised, revised_error = original({**raw, 'content': json.dumps(wire, ensure_ascii=False)})
    return native, revised, changed, revised_error


def run():
    checked = controls.branch.archive.bound_result
    executed, spec, original = checked(measured)
    attributed, bound, past = checked(attribution)
    prior, prior_spec, prior_terminal = checked(anchored)
    config, cases, _, grade, _ = anchored.materials()
    if (bound['operative_edges_terminal'] != original['terminal_sha256']
            or prior_terminal['terminal_sha256'] != spec['original_anchor_terminal']
            or sha(grade) != spec['reference_sha256'] or 'train' not in grade.parts
            or prior_spec['executor'] != config):
        raise ValueError('Retain the exact original late TRAIN groups and executor')
    raw_path = executed / 'sealed_predictions.json'
    if sha(raw_path) != original['predictions_sha256']:
        raise ValueError('The original operative-edge predictions changed')
    before = read(raw_path)['raw']
    known = read(executed / 'same_scope_proofs.json')
    proofs = read(attributed / 'source_proofs.json')
    if (digest([known['known'], known['witness']]) != spec['source_evidence_sha256']
            or digest(proofs) != bound['proofs_sha256']):
        raise ValueError('Apply the same original source controls')
    new_wire, old_wire = (read(stage / 'wire_tasks.json') for stage in (executed, prior))
    if (digest(new_wire) != spec['matched_wire_sha256'] or digest(old_wire) != prior_spec['wire_sha256']):
        raise ValueError('Maintain the byte-exact requests for both read layouts')
    fixed = {role: dict(rows) for role, rows in before.items()}
    client = fit.FrozenExecutor(None, executed, config)
    repeats, call_ids = {}, set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            positions = {}
            for role, query, identity in (
                ('synthesized', new_wire[key], f'{measured.STAGE}-{executed.name[:12]}:{digest(key)}'),
                ('previous_synthesized', old_wire[key]['synthesized'],
                 f'{anchored.STAGE}-{prior.name[:12]}:{digest(key)}:synthesized'),
            ):
                physical_wire(db, set(cases), identity, key)
                encoded, = db.execute('select result from calls where id=?', (identity,)).fetchone()
                actual = json.loads(encoded)
                messages, schema = query
                payload = read(Path(actual['artifact_directory']) / 'request.json')['payload']
                old, recovered, repeated, error = decode(case, schema, role, actual)
                if (old != before[role][key] or error is not None
                        or payload != client.payload(messages=messages, thinking=False, schema=schema)):
                    raise ValueError('Reproduce the original inputs and output before applying idempotence')
                fixed[role][key] = recovered
                call_ids.add(identity)
                if repeated:
                    positions[role] = repeated
            if positions:
                repeats[key] = positions
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if len(call_ids) != 2 * len(cases) or ledger.get('reserved') or ledger != past['ledger']:
        raise ValueError('Use only the 18 already settled anchor-slot responses')
    common_proofs = {key: (proofs['TRAIN'][key] or {}).get('answer', {}) for key in cases}

    def apply_common(bank):
        scoped = measured.visible.common_scope(bank, known['known'])
        visible = measured.visible.revise(scoped, known['witness'])
        return measured.visible.common_scope(visible, common_proofs)

    after_common = apply_common(fixed)
    baseline_common = apply_common(before)
    bound_predictions = attributed / 'sealed_predictions.json'
    if sha(bound_predictions) != past['predictions_sha256'] or baseline_common != read(bound_predictions):
        raise ValueError('Reproduce the last recorded shared-scope comparison')
    coverage = independent_coverage(cases)
    files = (__file__, anchors.__file__, measured.__file__, anchored.__file__, attribution.__file__,
             measured.visible.fixed_dev.__file__, fit.__file__)
    binding = {'stage': STAGE, 'TEST_opened': False, 'prior_anchor_terminal': prior_terminal['terminal_sha256'],
               'operative_terminal': original['terminal_sha256'], 'scope_terminal': past['terminal_sha256'],
               'TRAIN_grade_sha256': sha(grade), 'matched_request_ids_sha256': digest(sorted(call_ids)),
               'public_validation_coverage_sha256': digest(coverage),
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    fit.snapshot(out, binding['source_sha256'])
    tag = immutable_json(out / 'sealed_predictions.json', {'raw': fixed, 'same_scope': after_common})
    labels = read(grade)
    omit = {(key, fit.TASKS['negative']) for key, case in cases.items()
            if case['position'] in past['scope_label_disagreement_positions']}
    scores = {'before': original['scores']['raw'], 'after': controls.differences(cases, fixed, labels),
              'after_same_scope': controls.differences(cases, after_common, labels),
              'source_fidelity_sensitivity': attribution.sensitivity(cases, after_common, labels, omit)}
    repaired = {}
    for role, bank in fixed.items():
        repaired[role] = [{'position': cases[key]['position'], 'question': family, 'before': before[role][key][family],
                           'after': answer, 'retained_shared_source_answer': after_common[role][key][family]}
                          for key, row in bank.items() for family, answer in row.items()
                          if before[role][key][family] != answer]
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'unchanged_shared_native_scores': scores['after_same_scope']['correct'] == past['native_comparison']['correct'],
        'unchanged_source_fidelity_scores': scores['source_fidelity_sensitivity']['correct'] == past['source_fidelity_sensitivity']['correct'],
        'repeated_positive_anchor_counts': {role: sum(len(raw.get(role, {})) for raw in repeats.values())
                                            for role in ('synthesized', 'previous_synthesized')},
        'changed_outputs': repaired, 'scores': scores, 'reverified_physical_responses': len(call_ids),
        'validation_coverage': coverage,
        'unchanged_archived_control_mothers': len(cases), 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
