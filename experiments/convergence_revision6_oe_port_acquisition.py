"""Require support for each replaced native port in the settled OE acquisition replay."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_joint_acquisition as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.convergence_oe_joint_acquisition import ROUTES, TASKS, select
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_port_acquisition'
POINTER = HANDOFF / f'{STAGE}_current.json'


def route_from_seal(predictions, choices, new_route):
    """Compose exact previously measured program/port outputs without new calls."""
    by_program = {}
    for policy, native in predictions.items():
        name = choices[policy]['route'] if policy in choices else 'incumbent'
        for task, program in zip(TASKS, ROUTES[name], strict=True):
            if by_program.setdefault((task, program), native[task]) != native[task]:
                raise ValueError('A previously sealed program and task must reproduce identically')
    return {t: by_program[t, p] for t, p in zip(TASKS, ROUTES[new_route], strict=True)}


def run():
    checkpoint = read(prior.VALIDATED_POINTER)
    previous = ROOT / checkpoint['artifact_root']
    old_binding = read(previous / 'binding.json')
    release = verify(read(previous / 'terminal.json'), 'terminal_sha256')
    storage = previous / 'sealed_predictions.json'
    assert (digest(old_binding) == previous.name == release['binding_sha256']
            and release['terminal_sha256'] == checkpoint['terminal_sha256']
            and release['predictions_sha256'] == sha(storage))
    assert old_binding['require_category_proof_for_joined_repairs'] and not release['TEST_opened']
    assert all(sha(previous / 'source_snapshot' / name) == value for name, value in old_binding['source_sha256'].items())
    old = read(storage)
    fit, by_batch, grade_refs, programs = {}, {}, set(), {}
    for batch in old_binding['transitions']:
        _, spec, _ = prior.archive.prior.archive.bound_stage(prior.FORMAL.pointer(batch))
        grade_refs.add(prior.archive.assets.grades_ref(read(ROOT / spec['observations_root'] / 'binding.json')))
        study = read(ROOT / spec['checkpoint_root'] / 'binding.json')
        mothers = prior.FORMAL.load_roster(study)[batch]
        cohort = [s for s in mothers if s['dataset'] == prior.OE and s['project_split'] == 'train']
        assert len(cohort) == 4
        by_batch[str(batch)] = {s['key']: {'views': {v['id']: v for v in s['views']}} for s in cohort}
        prior_fit = release['fit'][str(batch)]
        routes = select({int(k): v for k, v in prior_fit['group_evidence'].items()},
                        prior_fit['TRAIN_shared_native_gate'], require_each_port=True)
        programs[str(batch)] = {}
        for role, choice in prior_fit['choices'].items():
            entry = verify(read(previous / 'TRAIN_batch_libraries' / f'B{batch}' / f'{role}.json'), 'snapshot_sha256')
            assert entry['binding_sha256'] == previous.name and entry['choice'] == choice
            for task, identity in zip(TASKS, ROUTES[choice['route']], strict=True):
                h = entry['programs'][task]
                assert programs[str(batch)].setdefault((task, identity), h) == h
        fit[str(batch)] = {'choices': routes, 'prior_choices': prior_fit['choices'], 'screened_read_uses_per_policy': 4}
    grade_name, expected = grade_refs.pop()
    grade = ROOT / grade_name
    assert not grade_refs and 'train' in grade.parts and sha(grade) == expected == old_binding['grade_sha256']
    cases = {key: row for cohort in by_batch.values() for key, row in cohort.items()}
    assert len(cases) == 16 and all(set(rows) == set(cases) for rows in old.values())
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    assert ledger == release['ledger'] and not ledger.get('reserved')
    paths = (__file__, prior.__file__, prior.joint.__file__)
    binding = {'stage': STAGE, 'prior_joint_acquisition': release['terminal_sha256'], 'partition': 'TRAIN',
               'prior_program_port_predictions_sha256': sha(storage), 'grade_sha256': expected,
               'transitions': old_binding['transitions'], 'TEST_opened': False,
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in paths}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    predictions = {mode: {} for mode in old}
    for batch, cohort in by_batch.items():
        choices = fit[batch]['choices']
        for policy, choice in choices.items():
            selected = {t: programs[batch][t, p] for t, p in zip(TASKS, ROUTES[choice['route']], strict=True)}
            lib = sealed({'batch': int(batch), 'programs': selected, 'choice': choice, 'binding_sha256': out.name},
                         'snapshot_sha256')
            immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}' / f'{policy}.json', lib)
        for key in cohort:
            for mode, bank in old.items():
                predictions[mode][key] = {'incumbent': bank[key]['incumbent'], **{
                    name: route_from_seal(bank[key], fit[batch]['prior_choices'], choice['route'])
                    for name, choice in choices.items()}}
    prediction_sha = immutable_json(out / 'sealed_predictions.json', predictions)
    labels = read(grade)
    totals = {mode: prior.summary(cases, row, labels) for mode, row in predictions.items()}
    results = {batch: {mode: prior.summary(cohort, {k: row[k] for k in cohort}, labels)
                       for mode, row in predictions.items()} for batch, cohort in by_batch.items()}
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
                       'fit': fit, 'forward_mothers': len(cases), 'forward_TRAIN': results, 'all_forward_TRAIN': totals,
                       'same_control_as_prior': True, 'archived_forward_requests_in_predecessor': release['old_physical_requests_verified'],
                       'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger},
                      'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
