"""Apply the locked per-hypothesis screen to the other measured B4 candidate."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_task_screen as ordinary
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_cni_task_screen_parse'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, CNI, screen = ordinary.previous, ordinary.CNI, ordinary.screen


def run():
    point = read(ordinary.POINTER)
    parent = ROOT / point['artifact_root']
    old = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    bound = read(parent / 'binding.json')
    selector_path = Path(screen.__file__).relative_to(ROOT)
    if (old['TEST_opened'] or old['terminal_sha256'] != point['terminal_sha256'] or digest(bound) != parent.name
            or sha(ROOT / selector_path) != bound['source_sha256'][str(selector_path)]):
        raise ValueError('Reuse the same screen that was evaluated on the ordinary B4 proposal')
    root, study, roster = archive.archive_context()
    journal = archive.b4.TrainingJournal(root, study, roster)
    sources = {s['key']: s for cohort in roster[:5] for s in cohort if s['dataset'] == CNI and s['project_split'] == 'train'}
    _, config, _ = archive.bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    path = ROOT / config['native_grade_paths'][CNI]
    if len(sources) != 15 or 'train' not in path.parts or sha(path) != bound['grade_sha256']:
        raise ValueError('Use the exact original five TRAIN batches')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        bank, positions, ids, bindings = archive.bank_b4(db, journal, roster)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if set(bank) != set(sources) or len(ids) != 30 or ledger != old['ledger'] or set(ledger) - {'completed', 'failed'}:
        raise ValueError('Use all settled same-input PARSE pairs')
    proofs = {key: ordinary.proof_for(source) for key, source in sources.items()}
    fit = {key: choices for key, choices in bank.items() if positions[key][0] < 5}
    fit_sources = {key: sources[key] for key in fit}
    shared = {key: {role: ordinary.apply_proofs(sources[key], row, proofs[key]) for role, row in choices.items()}
              for key, choices in bank.items()}
    labels = {key: row for key, row in read(path).items() if key in fit}
    native_fit = archive.score_fit(fit_sources, {key: shared[key] for key in fit}, labels)
    groups = [{'position': [positions[key][0], positions[key][1] + 1],
               **archive.guard.compatibility(choices['incumbent'], choices['proposal'], proofs[key]),
               'disagreements': sorted(task for task in native_fit
                                       if choices['incumbent'][task]['answer'] != choices['proposal'][task]['answer'])}
              for key, choices in fit.items() if proofs[key]]
    choices = screen.select(groups, native_fit)
    routes = {name: row['programs'] for name, row in choices.items()}
    routes.update({screen.INCUMBENT: dict.fromkeys(native_fit, screen.INCUMBENT),
                   'whole_proposal': dict.fromkeys(native_fit, screen.PROPOSAL)})
    tasks = sorted(task for task in native_fit if len({routes[name][task] for name in choices}) > 1)
    files = (__file__, ordinary.__file__, screen.__file__, archive.__file__)
    lock = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'B4_original_bindings': bindings,
            'same_screen_ordinary_terminal': old['terminal_sha256'], 'source_proofs_sha256': digest(proofs),
            'physical_ids_sha256': digest(sorted(ids)), 'TRAIN_grade_sha256': sha(path),
            'selection_sha256': digest({'groups': groups, 'choices': choices, 'native_fit': native_fit}),
            'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files}}
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    archive.snapshot(out, lock['source_sha256'])
    immutable_json(out / 'fit_choices.json', {'groups': groups, 'choices': choices, 'native_fit': native_fit})
    materials, _, _, proposal, _, _ = archive.b4.materials()
    versions = {screen.INCUMBENT: digest(journal.library(archive.EXTERNAL_ARM, 3)['programs'][CNI]),
                screen.PROPOSAL: materials['proposal_sha256']}
    if versions[screen.PROPOSAL] != digest(proposal):
        raise ValueError('Use only the already measured schema')
    for name, route in routes.items():
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', sealed({
            'binding_sha256': out.name, 'fit_batch': 4, 'hypothesis_programs': {
                task: versions[role] for task, role in route.items()},
            'physical_screen_budget': choices.get(name, {}).get('physical_screen_budget', 0),
        }, 'snapshot_sha256'))
    forward = {key: sources[key] for key in bank if key not in fit}
    predictions = {name: {key: {task: shared[key][role][task] for task, role in route.items()}
                           for key in forward} for name, route in routes.items()}
    pred_sha = immutable_json(out / 'sealed_predictions.json', predictions)
    metrics = ordinary.scoped.evaluate(forward, predictions, read(path))['all']
    paired = metrics['paired_candidate_driven']
    advance = all(paired[name]['correct']['mean_change'] >= 0
                  and paired[name]['grounded']['paired_source_bootstrap_95'][0] > 0
                  for name in (*screen.SCREENED[1:], 'native_per_hypothesis'))
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred_sha,
                       'hypotheses_with_different_adoption': tasks, 'policies': choices, 'B5_TRAIN': metrics,
                       'reused_fit_requests': 24, 'reused_forward_requests': 6, 'new_executor_requests': 0,
                       'new_teacher_requests': 0, 'same_forward_mothers_as_ordinary': len(forward),
                       'supports_later_validation': advance, 'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
