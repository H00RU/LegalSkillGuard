"""Replay a source-bound independent-development check on unchanged CNI banks."""

from collections import Counter
from pathlib import Path
import sqlite3

from experiments import convergence_revision6_cni_agreement_disclosure_release as agreement
from experiments import convergence_revision6_maud_section_reference as baseline
from experiments import convergence_revision6_retention_group_transfer as transfer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_independent_direct import spans_for
from legal_skill_guard.paired_interfaces import cni_independent_development as local
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_cni_development_release'
POINTER = HANDOFF / 'revision6_cni_development_release_current.json'
ARCHIVE = agreement.qualification.archived
CNI, TASK = agreement.CNI, 'nda-12'


def view_of(source):
    return next(v for v in source['views'] if v['id'] == TASK)


def proof(source):
    view = view_of(source)
    return local.proof(spans_for(view), view['public']['source_text'])


def apply(answer, witness):
    if witness is None or witness['answer'] == answer['answer']:
        return answer
    return agreement.patched(answer, witness)


def grade(bank, sources, labels):
    return [{'source': key, 'view': TASK, **grade_view(CNI, view_of(source), labels[key][TASK],
            bank[key]['answer'], bank[key]['evidence_sentence_ids'])}
            for key, source in sources.items()]


def run():
    parent, cohort, originals, study, previous = baseline.base_actor()
    sources = {s['key']: s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'dev'}
    train, original_train, train_grade, train_archive = ARCHIVE.collect(*ARCHIVE.archive_context(), 'train')
    training = {k: proof(s) for k, s in train.items()}
    development = {k: proof(s) for k, s in sources.items()}
    if len(train) != 24 or len(sources) != 16:
        raise ValueError('Use all original ContractNLI TRAIN and fixed DEV mothers')

    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        original_train_reads, original_dev_reads = {}, {}
        for arm, bank in original_train.items():
            for key, bound in training.items():
                if bound is not None:
                    ARCHIVE.checked_result(db, train[key], bank[key], original_train_reads)
        for arm, (folder, seal, cell) in originals.items():
            for key, witness in development.items():
                if witness is None:
                    continue
                value = read(folder / 'predictions' / (digest(key) + '.json'))
                if (digest(value) != seal['predictions_sha256'][key]
                        or value['public_source_sha256'] != digest(sources[key])
                        or value['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Use the original bound source and arm response')
                ARCHIVE.checked_result(db, sources[key], value['result'], original_dev_reads, dev=True)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Wait for continuous ledger to settle')

    historical, spec, matched = agreement.bound_result(transfer)
    old = read(historical / 'sealed_predictions.json')
    path = study['grading_paths'][CNI]
    expected_grade = study['grading_file_sha256'][path]
    if (spec['DEV_grade_sha256'] != expected_grade or any(set(rows) != set(sources) for rows in old.values())
            or set(old) != set(transfer.POLICIES)):
        raise ValueError('Compare the exact two archived B5 readers on the same fixed cohort')

    prediction = {}
    for arm in agreement.qualification.release.ARMS:
        native = {key: parent(s, {'arm': arm, 'batch': 8}, 'skill_dev')['native'][TASK]
                  for key, s in sources.items()}
        prediction[arm] = {'before': native, 'after': {k: apply(row, development[k]) for k, row in native.items()}}
    earlier_b5 = {}
    for policy, bank in old.items():
        values = {key: bank[key][TASK] for key in sources}
        earlier_b5[policy] = {'before': values, 'after': {k: apply(v, development[k]) for k, v in values.items()}}

    binding = {
        'stage': 'revision6_cni_development_release', 'prior_CNI_terminal': previous,
        'TRAIN_archives': train_archive, 'TRAIN_grade_sha256': sha(train_grade),
        'DEV_grade_sha256': expected_grade, 'TRAIN_proofs_sha256': digest(training),
        'DEV_proofs_sha256': digest(development), 'archived_B5_terminal': matched['terminal_sha256'],
        'source_sha256': {str(Path(x).relative_to(ROOT)): sha(Path(x)) for x in (
            __file__, local.__file__, agreement.__file__, baseline.__file__, spans_for.__code__.co_filename,
        )}, 'TEST_opened': False,
    }
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    for name, h in binding['source_sha256'].items():
        dst = out / 'source_snapshot' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            with dst.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(dst) != h:
            raise ValueError('Preserve exact source-check implementation')
    pred_hash = immutable_json(out / 'sealed_predictions.json', {'fixed_B8': prediction, 'archived_B5': earlier_b5})
    immutable_json(out / 'source_proofs.json', {'TRAIN': training, 'DEV': development})
    grade_path = ROOT / path
    if ('dev' not in grade_path.parts or 'train' not in train_grade.parts
            or sha(grade_path) != expected_grade or sha(train_grade) != binding['TRAIN_grade_sha256']):
        raise ValueError('Grade only the original TRAIN and DEV after sealing the predictions')
    train_labels, lab = read(train_grade), read(grade_path)
    mismatches = sum(train_labels[k][TASK]['answer'] != p['answer'] for k, p in training.items() if p)
    if mismatches:
        raise ValueError('Resolve original TRAIN source conflicts before applying the rule')
    comparisons = {
        scope: {arm: agreement.comparison(grade(row['before'], sources, lab), grade(row['after'], sources, lab))
                for arm, row in cells.items()}
        for scope, cells in (('fixed_B8', prediction), ('archived_B5', earlier_b5))
    }
    proof_counts = {g: dict(Counter(p['kind'] for p in v.values() if p))
                    for g, v in (('TRAIN', training), ('DEV', development))}
    terminal = sealed({
        'status': 'settled_revision6_cni_development_release', 'binding_sha256': out.name,
        'scope_proofs': proof_counts, 'TRAIN_matching_proofs': sum(proof_counts['TRAIN'].values()),
        'scoped_archive_requests': {'TRAIN': len(original_train_reads), 'DEV': len(original_dev_reads)},
        **comparisons,
        'archived_B5_same_information': {'native_effect': agreement.comparison(*[
            grade(earlier_b5[policy]['after'], sources, lab) for policy in transfer.POLICIES]),
            'reused_matched_requests': matched['original_executor_calls_reused']},
        'predictions_sha256': pred_hash, 'same_public_rule_all_arms': True,
        'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
