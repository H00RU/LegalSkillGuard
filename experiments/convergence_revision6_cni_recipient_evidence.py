"""Complete evidence from the same cited recipient clauses in every archived arm."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_agreement_disclosure_release as archive
from experiments import convergence_revision6_contract_link_control as control
from experiments import convergence_revision6_contract_referenced_definitions as previous
from experiments import convergence_revision6_maud_section_reference as release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import cni_recipient_evidence as graph
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_recipient_evidence'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK, DATASET = control.linked.linked.TASK, control.linked.linked.DATASET
ROLES = ('fixed_referenced', 'learned_referenced', 'direct_same_input_referenced')


def view_of(source):
    return next(view for view in source['views'] if view['id'] == TASK)


def source_paths(source):
    return graph.paths(control.linked.linked.span_inventory(view_of(source)))


def paired_metrics(sources, labels, variants):
    rows = {
        phase: [
            {'source': key, 'view': TASK, **grade_view(
                DATASET, view_of(sources[key]), labels[key][TASK], native['answer'], native['evidence_sentence_ids'],
            )}
            for key, native in bank.items()
        ]
        for phase, bank in variants.items()
    }
    a, b = rows.values()
    if any(old['grade'] != new['grade'] for old, new in zip(a, b, strict=True)):
        raise ValueError('Evidence completion must preserve the classifier and its handled states')
    evidence = [[{**row, 'grade': row['evidence_f1']} for row in values] for values in (a, b)]
    return {
        'correct': sum(row['grade'] for row in a), 'mothers': len(a),
        'evidence_F1': [mean(row['evidence_f1'] for row in values) for values in (a, b)],
        'paired_evidence': paired_source_effect(*evidence),
        'improved': sum(new['evidence_f1'] > old['evidence_f1'] for old, new in zip(a, b, strict=True)),
        'regressed': sum(new['evidence_f1'] < old['evidence_f1'] for old, new in zip(a, b, strict=True)),
    }


def completion(bank, support):
    return {'before': bank, 'after': {key: graph.complete(row, support[key]) for key, row in bank.items()}}


def run():
    link_spec, link_sources, _, _, _, _, original = control.materials()
    fixed_parent, cohort, originals, study, fixed_terminal = release.base_actor()
    dev = {source['key']: source for source in cohort if source['dataset'] == DATASET
           and source['project_split'] == 'dev'}
    prior_pointer = read(previous.POINTER)
    last = ROOT / prior_pointer['artifact_root']
    last_binding = read(last / 'binding.json')
    prior_ref = verify(read(last / 'terminal.json'), 'terminal_sha256')
    if (last.name != digest(last_binding) or prior_ref['TEST_opened']
            or prior_ref['terminal_sha256'] != prior_pointer['terminal_sha256']
            or sha(last / 'sealed_predictions.json') != prior_ref['prediction_sha256']
            or last_binding['linked_terminal'] != original['terminal_sha256']):
        raise ValueError('Use the verified same-input reader and most recent evidence comparison')
    linked = {source['key']: source for source in link_sources}
    if len(dev) != 16 or len(linked) != 5 or not linked.keys() <= dev.keys() or len(originals) != 5:
        raise ValueError('Preserve the fixed cohort and its registered five-source comparison')

    original_archive = archive.qualification.archived
    train, archived, train_grade, train_receipts = original_archive.collect(*original_archive.archive_context(), 'train')
    if len(train) != 24 or 'train' not in train_grade.parts:
        raise ValueError('Require all original TRAIN mothers')
    train_paths = {key: source_paths(source) for key, source in train.items()}
    dev_paths = {key: source_paths(source) for key, source in dev.items()}
    previous_bank = read(last / 'sealed_predictions.json')
    fixed_predictions = {
        arm: completion({key: fixed_parent(s, {'arm': arm, 'batch': 8}, 'skill_dev')['native'][TASK]
                         for key, s in dev.items()}, dev_paths)
        for arm in originals
    }
    linked_predictions = {role: completion(previous_bank[role], dev_paths) for role in ROLES}
    train_predictions = {
        arm: completion({key: row['native'][TASK] for key, row in bank.items()}, train_paths)
        for arm, bank in archived.items()
    }
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        train_reads, dev_reads = {}, {}
        for arm, row in train_predictions.items():
            for key in train:
                if row['before'][key] != row['after'][key]:
                    original_archive.checked_result(db, train[key], archived[arm][key], train_reads)
        for arm, (folder, seal, cell) in originals.items():
            for key, source in dev.items():
                rows = fixed_predictions[arm]
                if rows['before'][key] == rows['after'][key]:
                    continue
                saved = read(folder / 'predictions' / f'{digest(key)}.json')
                if (digest(saved) != seal['predictions_sha256'][key] or saved['public_source_sha256'] != digest(source)
                        or saved['library_sha256'] != cell['libraries'][DATASET]):
                    raise ValueError('Only revise the original fixed DEV output')
                original_archive.checked_result(db, source, saved['result'], dev_reads, dev=True)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Require the settled continuous ledger for a source-only replay')

    path = study['grading_paths'][DATASET]
    grade = ROOT / path
    source_hashes = {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
        __file__, graph.__file__, previous.__file__, control.__file__, release.__file__,
    )}
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'source_sha256': source_hashes,
        'reference_filtered_terminal': prior_ref['terminal_sha256'], 'fixed_DEV_terminal': fixed_terminal,
        'linked_scope_hash': link_spec['public_cohort_sha256'], 'source_paths_sha256': digest([train_paths, dev_paths]),
        'TRAIN_receipts': train_receipts, 'TRAIN_grade_sha256': sha(train_grade),
        'DEV_grade_sha256': study['grading_file_sha256'][path],
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, source_hashes)
    immutable_json(out / 'source_paths.json', {'TRAIN': train_paths, 'DEV': dev_paths})
    prediction_sha = immutable_json(out / 'sealed_predictions.json', {
        'TRAIN': train_predictions, 'fixed_DEV': fixed_predictions, 'linked_DEV': linked_predictions,
    })
    if 'dev' not in grade.parts or sha(grade) != binding['DEV_grade_sha256']:
        raise ValueError('Use native DEV labels only after locking the source paths and predictions')
    train_labels, dev_labels = read(train_grade), read(grade)
    all_linked = {role: paired_metrics(linked, dev_labels, rows) for role, rows in linked_predictions.items()}
    comparison = paired_metrics(linked, dev_labels, {
        'direct': linked_predictions[ROLES[2]]['after'], 'M1': linked_predictions[ROLES[1]]['after'],
    })
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
        'coverage': {'TRAIN': sum(bool(x) for x in train_paths.values()), 'TRAIN_mothers': len(train),
                     'fixed_DEV': sum(bool(x) for x in dev_paths.values()), 'fixed_DEV_mothers': len(dev),
                     'linked_DEV': sum(bool(dev_paths[k]) for k in linked)},
        'TRAIN': {arm: paired_metrics(train, train_labels, rows) for arm, rows in train_predictions.items()},
        'fixed_DEV': {arm: paired_metrics(dev, dev_labels, rows) for arm, rows in fixed_predictions.items()},
        'linked_DEV': all_linked, 'M1_after_vs_same_information_direct': comparison,
        'verified_changed_original_physical_reads': {'TRAIN': len(train_reads), 'fixed_DEV': len(dev_reads)},
        'reused_paired_linked_DEV': sum(len(rows['before']) for rows in linked_predictions.values()),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    write_status(out, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
