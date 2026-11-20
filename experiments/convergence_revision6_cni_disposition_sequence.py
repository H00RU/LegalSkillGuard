"""Compare complete-disposition proofs in formal DEV and the B5 M2 transfer."""

import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_b5_candidate_conflicts as previous
from experiments import convergence_revision6_cni_employee_witness_projection as employee
from experiments import convergence_revision6_retention_scope as scope
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disposition_sequence as sequence
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_disposition_sequence'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK = scope.RETENTION
CNI = employee.CNI


def view(source):
    return next(row for row in source['views'] if row['id'] == TASK)


def source_proof(source):
    return sequence.proof(scope.retention.spans_for(view(source)))


def project(native, proof):
    observed = native[TASK]
    revised = sequence.project(observed, proof)
    if revised is observed:
        return native
    return {**native, TASK: {**revised, 'handled': True, 'reason': None}}


class DispositionSequenceActor:
    """Apply the complete disposition proof with the same source in each arm."""

    def __init__(self, parent, dev, proofs):
        self.parent = parent
        self.sources = {key: digest(source) for key, source in dev.items()}
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        original = self.parent(source, library, purpose)
        key = source['key']
        if (source['dataset'] != CNI or source['project_split'] != 'dev'
                or purpose != 'skill_dev' or library['batch'] != 8 or not self.proofs.get(key)):
            return original
        if digest(source) != self.sources[key]:
            raise ValueError('Bind full disposition to the original fixed public input')
        return {**original, 'native': project(original['native'], self.proofs[key])}


def coverage(paths, labels):
    checked = [(proof, labels[key][TASK]) for key, proof in paths.items() if proof]
    return {'mothers': len(paths), 'complete_proofs': len(checked),
            'reference_class_matches': sum(label['answer'] == 'Contradiction' for _, label in checked),
            'reference_exact_evidence_matches': sum(p['evidence'] == label['evidence'] for p, label in checked),
            'forms': dict(Counter(p['form'] for p, _ in checked))}


def paired(sources, labels, programs):
    def score(outputs):
        values = []
        for key, source in sources.items():
            native = outputs[key][TASK]
            row = grade_view(CNI, view(source), labels[key][TASK], native['answer'], native['evidence_sentence_ids'])
            values.append({'source': key, 'view': TASK, 'correct': row['grade'],
                           'grounded': row['grade'] * row['evidence_f1']})
        return values

    result = {}
    for role, bank in programs.items():
        before, after = (score(bank[phase]) for phase in ('before', 'shared_disposition'))
        result[role] = {
            'correct': [int(sum(r['correct'] for r in rows)) for rows in (before, after)],
            'correct_class_evidence_F1': [mean(r['grounded'] for r in rows) for rows in (before, after)],
            'changes': {m: {'improved': sum(x[m] < y[m] for x, y in zip(before, after, strict=True)),
                            'regressed': sum(x[m] > y[m] for x, y in zip(before, after, strict=True))}
                        for m in ('correct', 'grounded')},
            'paired': {m: paired_source_effect(
                *[[{**r, 'grade': r[m]} for r in rows] for rows in (before, after)]
            ) for m in ('correct', 'grounded')},
        }
    return result


def exact_m2_reads(db, dev):
    transfer = scope.transfer
    fit_root, _, fit = scope.load_parent(transfer.selection)
    stages, spec, terminal = scope.load_parent(transfer)
    if spec['fit_TERMINAL'] != fit['terminal_sha256']:
        raise ValueError('Retain the original M2 candidate and chronological reader versions')
    lib = {role: transfer.verify(read(fit_root / 'TRAIN_batch_libraries' / f'{role}.json'), 'snapshot_sha256')
           for role in transfer.POLICIES}
    if {k: x['snapshot_sha256'] for k, x in lib.items()} != fit['library_sha256']:
        raise ValueError('Require the exact locked B5 skill allocations')
    cases, banks, grade, _, count, inputs = transfer.materials(db, lib)
    path = stages / 'sealed_predictions.json'
    if (cases != dev or sha(path) != terminal['predictions_sha256'] or read(path) != banks
            or spec['matched_public_and_executor_sha256'] != inputs or spec['DEV_grade_sha256'] != grade[1]):
        raise ValueError('Use physical fixed DEV reads with the exact same source, labels and settings')
    return banks, grade, count, terminal['terminal_sha256']


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != previous.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Continue from the verified complete B5 comparison boundary')
    _, _, b5 = previous.b4.terminal(previous)
    old, old_spec, prior = previous.b4.terminal(employee)
    fixed = old / 'sealed_predictions.json'
    if sha(fixed) != prior['predictions_sha256']:
        raise ValueError('Bind the latest cumulative evaluator output')
    _, previous_config, _ = previous.b4.terminal(employee.base)
    _, shared, dev, dev_arms, study, _ = employee.base.prior.prepare_dev()
    explicit = {key: employee.base.source_proof(source) for key, source in dev.items()}
    grants = {key: employee.base.existing.source_paths(source) for key, source in dev.items()}
    configured = employee.EmployeeWitnessActor(employee.base.EmployeePermissionActor(shared, dev, explicit), dev, grants)
    train, train_arms, train_grade, observations = employee.base.prior.archive.collect(
        *employee.base.prior.archive.archive_context(), 'train',
    )
    dev_grade = ROOT / study['grading_paths'][CNI]
    if ('train' not in train_grade.parts or 'dev' not in dev_grade.parts
            or [sha(train_grade), sha(dev_grade)] != old_spec['reference_sha256']
            or observations != previous_config['TRAIN_observations']):
        raise ValueError('Use the existing TRAIN and DEV cohorts and original native graders')
    groups = {'TRAIN': train, 'fixed_DEV': dev}
    proofs = {part: {key: source_proof(source) for key, source in rows.items()} for part, rows in groups.items()}
    actor = DispositionSequenceActor(configured, dev, proofs['fixed_DEV'])
    old_banks, revised, physical = read(fixed), {}, {part: {} for part in groups}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger != b5['ledger'] or ledger.get('reserved'):
            raise ValueError('Reuse archived model calls without dispatching or changing the ledger')
        for part, sources in groups.items():
            revised[part] = {}
            for arm, phases in old_banks[part].items():
                before = phases['shared_permission']
                after = {key: project(row, proofs[part][key]) for key, row in before.items()}
                for key, source in sources.items():
                    if part == 'fixed_DEV':
                        library = {'arm': arm, 'batch': 8}
                        for reader, expected in ((configured, before[key]), (actor, after[key])):
                            readout = reader(source, library, 'skill_dev')['native']
                            assert employee.base.prior.native_rows({arm: {key: readout}}) == (
                                employee.base.prior.native_rows({arm: {key: expected}})
                            )
                    if before[key] == after[key]:
                        continue
                    if part == 'TRAIN':
                        saved_result = train_arms[arm][key]
                    else:
                        directory, seal, cell = dev_arms[arm]
                        saved = read(directory / 'predictions' / f'{digest(key)}.json')
                        assert digest(saved) == seal['predictions_sha256'][key]
                        assert saved['library_sha256'] == cell['libraries'][CNI]
                        assert saved['public_source_sha256'] == digest(source)
                        saved_result = saved['result']
                    employee.base.prior.archive.checked_result(db, source, saved_result, physical[part],
                                                               dev=part == 'fixed_DEV')
                revised[part][arm] = {'before': before, 'shared_disposition': after}
        m2, m2_grade, m2_count, transfer_terminal = exact_m2_reads(db, dev)
    assert m2_grade == (str(dev_grade.relative_to(ROOT)), sha(dev_grade))
    m2_revised = {role: {key: project(native, proofs['fixed_DEV'][key]) for key, native in bank.items()}
                  for role, bank in m2.items()}
    hashes = {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
        __file__, sequence.__file__, sequence.closure.__file__, employee.__file__, scope.transfer.__file__,
    )}
    binding = {'stage': STAGE, 'source_sha256': hashes, 'B5_portfolio_terminal': b5['terminal_sha256'],
               'previous_fixed_DEV_terminal': prior['terminal_sha256'], 'original_M2_transfer_terminal': transfer_terminal,
               'source_paths_sha256': digest(proofs), 'reference_hashes': [sha(train_grade), sha(dev_grade)],
               'formal_reads_sha256': {part: digest(sorted(x)) for part, x in physical.items()}, 'TEST_opened': False}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    employee.base.prior.cumulative.snapshot(out, hashes)
    immutable_json(out / 'source_proofs.json', proofs)
    tag = immutable_json(out / 'sealed_predictions.json', {'formal': revised, 'B5_M2_before': m2, 'B5_M2_after': m2_revised})
    labels = {'TRAIN': read(train_grade), 'fixed_DEV': read(dev_grade)}
    fixed_grade = labels['fixed_DEV']
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'coverage': {part: coverage(paths, labels[part]) for part, paths in proofs.items()},
        'paired': {part: paired(sources, labels[part], revised[part]) for part, sources in groups.items()},
        'fixed_DEV_cumulative': {phase: employee.base.prior.full_scores(
            {arm: rows[phase] for arm, rows in revised['fixed_DEV'].items()}, dev, fixed_grade,
        ) for phase in ('before', 'shared_disposition')},
        'B5_M2_exact_transfer': {phase: scope.transfer.score(dev, bank, fixed_grade)
                                for phase, bank in (('before', m2), ('shared_disposition', m2_revised))},
        'reused_formal_reads': {part: len(calls) for part, calls in physical.items()},
        'reused_M2_paired_reads': m2_count, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
