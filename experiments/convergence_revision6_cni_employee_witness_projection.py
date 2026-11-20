"""Use verified employee-access paths when the archived reader misses them."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_employee_permission as base
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.cni_employee_witness_projection import project
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_employee_witness_projection'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK = base.TASK
CNI = base.existing.DATASET


def project_native(native, proof):
    observed = native[TASK]
    revised = project(observed, proof)
    return native if revised is observed else {**native, TASK: {**revised, 'handled': True, 'reason': None}}


class EmployeeWitnessActor:
    """Apply the same permission witness before evaluation in every DEV arm."""

    def __init__(self, parent, sources, witnesses):
        self.parent = parent
        self.digests = {key: digest(source) for key, source in sources.items()}
        self.witnesses = witnesses

    def __call__(self, source, library, purpose):
        result = self.parent(source, library, purpose)
        key = source['key']
        if (source['dataset'] != CNI or source['project_split'] != 'dev' or purpose != 'skill_dev'
                or library['batch'] != 8 or key not in self.witnesses):
            return result
        if digest(source) != self.digests[key]:
            raise ValueError('Keep the witness bound to the verified fixed public text')
        native = project_native(result['native'], self.witnesses[key])
        return result if native is result['native'] else {**result, 'native': native}


def calibrate_coverage(proofs, labels):
    matched = [(next(iter(paths.values())), labels[key][TASK]) for key, paths in proofs.items() if len(paths) == 1]
    return {
        'mothers': len(proofs), 'unique_witnesses': len(matched),
        'positive_native_labels': sum(row['answer'] == 'Entailment' for _, row in matched),
        'exact_reference_evidence': sum(set(witness) == set(row['evidence']) for witness, row in matched),
    }


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != base.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Use the latest terminal before running the employee-witness projection')
    prev, config, terminal = base.portfolio.fit.terminal(base)
    first = read(prev / 'formal_predictions.json')
    explicit_paths = read(prev / 'source_proofs.json')
    if digest(first) != config['formal_banks_sha256'] or digest(explicit_paths) != config['public_paths_sha256']:
        raise ValueError('Preserve the previous common correction and fixed scores')
    _, parent, dev, originals, study, _ = base.prior.prepare_dev()
    train, archived, train_grade, observations = base.prior.archive.collect(*base.prior.archive.archive_context(), 'train')
    dev_grade = ROOT / study['grading_paths'][CNI]
    assert {'TRAIN': sha(train_grade), 'fixed_DEV': sha(dev_grade)} == {
        'TRAIN': config['TRAIN_grade_sha256'], 'fixed_DEV': config['DEV_grade_sha256'],
    }
    assert 'train' in train_grade.parts and 'dev' in dev_grade.parts and observations == config['TRAIN_observations']
    cohorts = {'TRAIN': train, 'fixed_DEV': dev}
    witnesses = {name: {key: base.existing.source_paths(source) for key, source in sources.items()}
                 for name, sources in cohorts.items()}
    with_new_forms = base.EmployeePermissionActor(parent, dev, explicit_paths['fixed_DEV'])
    actor = EmployeeWitnessActor(with_new_forms, dev, witnesses['fixed_DEV'])
    revised, physical = {}, {'TRAIN': {}, 'fixed_DEV': {}}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert ledger == terminal['ledger'] and not ledger.get('reserved')
        for name, source_map in cohorts.items():
            revised[name] = {}
            for arm, phases in first[name].items():
                old = phases['shared_permission']
                after = {key: project_native(native, witnesses[name][key]) for key, native in old.items()}
                if name == 'fixed_DEV':
                    library = {'arm': arm, 'batch': 8}
                    for reader, expected in ((with_new_forms, old), (actor, after)):
                        bank = {arm: {key: reader(s, library, 'skill_dev')['native'] for key, s in dev.items()}}
                        if base.prior.native_rows(bank) != base.prior.native_rows({arm: expected}):
                            raise ValueError('Reproduce every revised answer and evidence span in the DEV actor')
                for key, source in source_map.items():
                    if old[key] == after[key]:
                        continue
                    if name == 'TRAIN':
                        original = archived[arm][key]
                    else:
                        folder, seal, cell = originals[arm]
                        saved = read(folder / 'predictions' / f'{digest(key)}.json')
                        assert digest(saved) == seal['predictions_sha256'][key]
                        assert saved['library_sha256'] == cell['libraries'][CNI]
                        assert saved['public_source_sha256'] == digest(source)
                        original = saved['result']
                    base.prior.archive.checked_result(db, source, original, physical[name], dev=name == 'fixed_DEV')
                revised[name][arm] = {'before': old, 'shared_permission': after}
    hashes = {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
        __file__, Path(project.__code__.co_filename), base.existing.graph.__file__, base.__file__, base.prior.__file__,
    )}
    binding = {'stage': STAGE, 'source_sha256': hashes, 'public_witnesses_sha256': digest(witnesses),
               'previous_terminal': terminal['terminal_sha256'], 'reference_sha256': [sha(train_grade), sha(dev_grade)],
               'verified_physical_reads_sha256': {key: digest(sorted(rows)) for key, rows in physical.items()},
               'TEST_opened': False}
    root = BASE / STAGE / digest(binding)
    immutable_json(root / 'binding.json', binding)
    base.prior.cumulative.snapshot(root, hashes)
    immutable_json(root / 'source_proofs.json', witnesses)
    prediction_hash = immutable_json(root / 'sealed_predictions.json', revised)
    references = {'TRAIN': read(train_grade), 'fixed_DEV': read(dev_grade)}
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': root.name, 'predictions_sha256': prediction_hash,
        'source_coverage': {name: calibrate_coverage(witnesses[name], references[name]) for name in cohorts},
        'paired': {name: base.paired_arms(cohorts[name], references[name], revised[name]) for name in cohorts},
        'before_and_after_fixed_DEV_cumulative': {phase: base.prior.full_scores(
            {arm: row[phase] for arm, row in revised['fixed_DEV'].items()}, dev, references['fixed_DEV'],
        ) for phase in ('before', 'shared_permission')},
        'verified_reused_physical_reads': {name: len(rows) for name, rows in physical.items()},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(root / 'terminal.json', report)
    write_status(root, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(root)


if __name__ == '__main__':
    run()
