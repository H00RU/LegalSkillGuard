"""Replay employee-permission witnesses on settled TRAIN and fixed DEV reads."""

import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_b4_portfolio_complete as portfolio
from experiments import convergence_revision6_cni_recipient_evidence as existing
from experiments import convergence_revision6_cni_survival_trigger_roles as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_employee_permission as employee
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_employee_permission'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK = existing.TASK


def source_proof(source):
    spans = existing.control.linked.linked.span_inventory(existing.view_of(source))
    return employee.support(spans)


def project(native, verified):
    if TASK not in native:
        return native
    observed = native[TASK]
    revised = employee.project(observed, verified)
    return native if revised == observed else {**native, TASK: {**revised, 'handled': True, 'reason': None}}


class EmployeePermissionActor:
    """Apply verified source-local paths to every fixed DEV arm."""

    def __init__(self, parent, sources, proofs):
        self.parent = parent
        self.source_digests = {key: digest(source) for key, source in sources.items()}
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        original = self.parent(source, library, purpose)
        key = source['key']
        if (source['dataset'] != existing.DATASET or source['project_split'] != 'dev'
                or purpose != 'skill_dev' or library['batch'] != 8 or key not in self.proofs):
            return original
        if digest(source) != self.source_digests[key]:
            raise ValueError('Bind the verified permission to the exact original source')
        revised = project(original['native'], self.proofs[key])
        return original if revised is original['native'] else {**original, 'native': revised}


def source_coverage(proofs, labels):
    observed = Counter()
    for key, paths in proofs.items():
        if len(paths) != 1:
            continue
        path, = paths
        ref = labels[key][TASK]
        supplied = {path['operative'], path['governing']}
        observed.update({
            'matched_mothers': 1, 'native_positive': int(ref['answer'] == 'Entailment'),
            'operative_citation_matches': int(path['operative'] in ref['evidence']),
            'complete_evidence_matches': int(supplied == set(ref['evidence'])),
        })
    return {'observed': dict(observed), 'mothers': len(proofs),
            'forms': dict(Counter(rows[0]['form'] for rows in proofs.values() if len(rows) == 1))}


def paired_arms(sources, labels, variants):
    def score(bank):
        rows = []
        for key, source in sources.items():
            prediction = bank[key][TASK]
            observed = grade_view(existing.DATASET, existing.view_of(source), labels[key][TASK],
                                  prediction['answer'], prediction['evidence_sentence_ids'])
            rows.append({'source': key, 'view': TASK, 'correct': observed['grade'],
                         'grounded': observed['grade'] * observed['evidence_f1']})
        return rows

    result = {}
    for arm, phases in variants.items():
        before, after = (score(phases[name]) for name in ('before', 'shared_permission'))
        result[arm] = {
            'correct': [int(sum(row['correct'] for row in phase)) for phase in (before, after)],
            'correct_class_evidence_F1': [mean(row['grounded'] for row in phase) for phase in (before, after)],
            'paired': {metric: paired_source_effect(
                *[[{**row, 'grade': row[metric]} for row in phase] for phase in (before, after)]
            ) for metric in ('correct', 'grounded')},
            'changes': {metric: {
                'improved': sum(a[metric] < b[metric] for a, b in zip(before, after, strict=True)),
                'regressed': sum(a[metric] > b[metric] for a, b in zip(before, after, strict=True)),
            } for metric in ('correct', 'grounded')},
        }
    return result


def paired_portfolio(done, binding, terminal, train, paths, labels):
    _, config, fit = portfolio.fit.terminal(portfolio.fit)
    cases, grade, _, _, _ = portfolio.later.inputs(config)
    assert config['TRAIN_grade_sha256'] == sha(grade) == binding['TRAIN_grade_sha256']
    assert all(source == train[key] for key, (source, _) in cases.items())
    if sha(done / 'sealed_predictions.json') != terminal['predictions_sha256']:
        raise ValueError('Reuse only the full exact-read locked portfolio')
    before = read(done / 'sealed_predictions.json')
    revised = {role: {key: project(native, paths[key]) for key, native in cell.items()}
               for role, cell in before.items()}
    assert portfolio.later.compare(cases, before, labels) == terminal['B6_B8_paired']
    report = portfolio.later.compare(cases, revised, labels)
    position = {'-'.join(map(str, coordinates)): paths[key] for key, (_, coordinates) in cases.items() if paths[key]}
    return {'before': terminal['B6_B8_paired'], 'after_shared_permission': report,
            'source_paths_by_position': position, 'B4_policy_choices_held_fixed': True,
            'candidate_still_equals_both_disagreement_policies': all(
                fit['choices'][policy] == fit['choices']['candidate_driven']
                and revised[policy] == revised['candidate_driven']
                for policy in ('answer_disagreement', 'in_scope_disagreement')
            )}, revised


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != portfolio.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Use the latest settled fixed-read boundary')
    _, parent, dev, originals, study, _ = prior.prepare_dev()
    previous, previous_binding, preceding = portfolio.fit.terminal(prior)
    done, portfolio_binding, complete = portfolio.fit.terminal(portfolio)
    previous_predictions = previous / 'sealed_predictions.json'
    if sha(previous_predictions) != preceding['predictions_sha256']:
        raise ValueError('Bind the latest cumulative five-arm ContractNLI development predictions')
    train, archived, grade_train, observed = prior.archive.collect(*prior.archive.archive_context(), 'train')
    grade_dev = ROOT / study['grading_paths'][existing.DATASET]
    if ('train' not in grade_train.parts or 'dev' not in grade_dev.parts
            or sha(grade_train) != previous_binding['TRAIN_grade_sha256']
            or sha(grade_dev) != study['grading_file_sha256'][str(grade_dev.relative_to(ROOT))]
            or (len(train), len(dev), len(originals)) != (24, 16, 5)):
        raise ValueError('Retain the original TRAIN and fixed DEV partitions and reference files')
    groups = {'TRAIN': train, 'fixed_DEV': dev}
    paths = {name: {key: source_proof(source) for key, source in sources.items()} for name, sources in groups.items()}
    before = {
        'TRAIN': prior.native_rows({arm: {key: row['native'] for key, row in bank.items()}
                                    for arm, bank in archived.items()}),
        'fixed_DEV': prior.native_rows({arm: bank['operative_only'] for arm, bank in
                                       read(previous_predictions)['DEV'].items()}),
    }
    actor = EmployeePermissionActor(parent, dev, paths['fixed_DEV'])
    variants, matched = {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert ledger == complete['ledger'] and not ledger.get('reserved')
        for name, banks in before.items():
            variants[name], matched[name] = {}, {}
            for arm, old in banks.items():
                after = {key: project(predictions, paths[name][key]) for key, predictions in old.items()}
                variants[name][arm] = {'before': old, 'shared_permission': after}
                if name == 'fixed_DEV':
                    library = {'arm': arm, 'batch': 8}
                    for reader, expected in ((parent, old), (actor, after)):
                        bank = {arm: {key: reader(source, library, 'skill_dev')['native'] for key, source in dev.items()}}
                        if prior.native_rows(bank)[arm] != expected:
                            raise ValueError('Verify the cumulative DEV actor and revised outputs item by item')
                for key, source in groups[name].items():
                    if len(paths[name][key]) != 1:
                        continue
                    if name == 'TRAIN':
                        result = archived[arm][key]
                    else:
                        folder, seal, cell = originals[arm]
                        saved = read(folder / 'predictions' / f'{digest(key)}.json')
                        if (digest(saved) != seal['predictions_sha256'][key]
                                or saved['public_source_sha256'] != digest(source)
                                or saved['library_sha256'] != cell['libraries'][existing.DATASET]):
                            raise ValueError('Verify unchanged original public input, library and native output')
                        result = saved['result']
                    prior.archive.checked_result(db, source, result, matched[name], dev=name == 'fixed_DEV')
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'fixed_DEV_terminal': preceding['terminal_sha256'],
        'portfolio_terminal': complete['terminal_sha256'], 'TRAIN_observations': observed,
        'TRAIN_grade_sha256': sha(grade_train), 'DEV_grade_sha256': sha(grade_dev),
        'public_paths_sha256': digest(paths), 'formal_banks_sha256': digest(variants),
        'physical_receipts_sha256': {name: digest(sorted(ids)) for name, ids in matched.items()},
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, employee.__file__, existing.graph.__file__, existing.__file__, prior.__file__,
            portfolio.__file__, portfolio.fit.__file__, portfolio.later.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    prior.cumulative.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', paths)
    immutable_json(out / 'formal_predictions.json', variants)
    labels = {'TRAIN': read(grade_train), 'fixed_DEV': read(grade_dev)}
    comparison, priority_predictions = paired_portfolio(
        done, portfolio_binding, complete, train, paths['TRAIN'], labels['TRAIN'],
    )
    prediction_sha = immutable_json(out / 'sealed_predictions.json', priority_predictions)
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
        'source_coverage': {name: source_coverage(proofs, labels[name]) for name, proofs in paths.items()},
        'employee_permission_paired': {name: paired_arms(groups[name], labels[name], variants[name]) for name in paths},
        'fixed_DEV_cumulative': prior.full_scores({arm: row['shared_permission'] for arm, row in
                                                 variants['fixed_DEV'].items()}, dev, labels['fixed_DEV']),
        'TRAIN_B6_B8_locked_portfolio': comparison,
        'reused_verified_formal_reads': {name: len(ids) for name, ids in matched.items()},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    write_status(out, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
