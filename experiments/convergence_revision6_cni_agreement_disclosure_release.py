"""Extend operative agreement-disclosure checks and compare the archived B5 readers."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_agreement_event_attachment as earlier
from experiments import convergence_revision5_cni_retention_controls as absence
from experiments import convergence_revision6_cni_qualification_release as qualification
from experiments import convergence_revision6_retention_group_transfer as transfer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_agreement_disclosure_effect as local
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_cni_agreement_disclosure_release'
POINTER = HANDOFF / 'revision6_cni_agreement_disclosure_release_current.json'
TASK, CNI = earlier.TASK, qualification.CNI
MAJORITY = 'explicit_then_TRAIN_majority'


def view_of(source):
    return next(v for v in source['views'] if v['id'] == TASK)


def effect(view):
    status, strict = earlier.source_proof(view, False)
    if strict:
        return {**strict, 'form': status}
    if status == 'ambiguous':
        return None
    supported = local.explicit_bar(earlier.base.archive.span_inventory(view))
    if supported:
        return supported
    if absence.absence_applies(view, protect_agreement_itself=True):
        return {'form': 'checked_absence', 'answer': 'NotMentioned', 'evidence_sentence_ids': []}
    return None


def patched(old, proof):
    if proof is None:
        return old
    return {**old, 'answer': proof['answer'], 'evidence_sentence_ids': proof['evidence_sentence_ids'], 'handled': True}


class AgreementDisclosureActor:
    def __init__(self, parent, proofs):
        self.parent = parent
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        result = self.parent(source, library, purpose)
        if source['dataset'] != CNI or self.proofs.get(source['key']) is None:
            return result
        return {**result, 'native': {**result['native'],
                TASK: patched(result['native'][TASK], self.proofs[source['key']])}}


def measure(rows, views, labels):
    return [{'source': key, 'view': TASK, **grade_view(CNI, views[key], labels[key][TASK],
                 out['answer'], out['evidence_sentence_ids'])} for key,out in rows.items()]


def comparison(before, after):
    return {
        'correct': [sum(x['grade'] for x in rows) for rows in (before, after)],
        'evidence_F1': [mean(x['evidence_f1'] for x in rows) for rows in (before, after)],
        'paired': paired_source_effect(before, after),
        'improved': sum(y['grade'] > x['grade'] for x,y in zip(before, after, strict=True)),
        'regressed': sum(y['grade'] < x['grade'] for x,y in zip(before, after, strict=True)),
    }


def bound_result(module):
    pointer = read(module.POINTER)
    root = ROOT / pointer['artifact_root']
    spec = read(root / 'binding.json')
    result = verify(read(root / 'terminal.json'), 'terminal_sha256')
    if (digest(spec) != root.name or pointer['terminal_sha256'] != result['terminal_sha256']
            or result['TEST_opened'] or sha(root / 'sealed_predictions.json') != result['predictions_sha256']):
        raise ValueError('Reuse only settled native predictions from their original boundary')
    return root, spec, result


def run():
    prior_actor, cohort, originals, study, _, cells = qualification.load_release()
    q_root, q_spec, q_stop = bound_result(qualification)
    mark_proofs = read(q_root / 'source_effects.json')['DEV']
    if digest(mark_proofs) != q_spec['DEV_source_effects']:
        raise ValueError('Preserve the cumulative designation amendment')
    parent = qualification.QualificationActor(prior_actor, mark_proofs)
    scores_root, old_bind, old_terminal = bound_result(transfer)
    fit, selection, _ = qualification.knowledge.parallel.release.stage(earlier.POINTER)
    # This control already fit a majority to original TRAIN only.
    old_prior = fit / 'dev_TRAIN_prior_predictions.json'
    if sha(old_prior) != selection['prior_predictions_sha256']['dev']:
        raise ValueError('Preserve the already measured explicit and TRAIN-prior control')
    old_prior_predictions = read(old_prior)

    dev = {s['key']: s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'dev'}
    dev_views = {k: view_of(s) for k,s in dev.items()}
    proofs = {k: effect(v) for k,v in dev_views.items()}
    new_cases = {k for k,p in proofs.items() if p and p['form'] in (
        'bar_on_agreement_itself', 'bar_on_participation_in_talks', 'checked_absence',
    )}
    train, original_train, train_grade, train_sources = qualification.archived.collect(
        *qualification.archived.archive_context(), 'train')
    train_views = {k: view_of(s) for k,s in train.items()}
    train_proofs = {k: effect(v) for k,v in train_views.items()}
    measured_transfer = read(scores_root / 'sealed_predictions.json')
    if (set(measured_transfer[transfer.POLICIES[0]]) != set(dev)
            or old_bind['DEV_grade_sha256'] != study['grading_file_sha256'][study['grading_paths'][CNI]]):
        raise ValueError('The archived trained variants must use the same fixed DEV')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        raws = {}
        for reader in original_train.values():
            for key,witness in train_proofs.items():
                if witness and witness['answer'] == 'Entailment':
                    qualification.archived.checked_result(db, train[key], reader[key], raws)
        raw_dev = {}
        for arm, (folder, seal, cell) in originals.items():
            for key in sorted(new_cases):
                saved = read(folder / 'predictions' / (digest(key) + '.json'))
                if (digest(saved) != seal['predictions_sha256'][key]
                        or saved['public_source_sha256'] != digest(dev[key])
                        or saved['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Keep the physical input and model result tied to the original source')
                qualification.archived.checked_result(db, dev[key], saved['result'], raw_dev, dev=True)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if len(dev) != 16 or ledger.get('reserved'):
        raise ValueError('The current ledger and original fixed DEV must be settled')

    actor = AgreementDisclosureActor(parent, proofs)
    before, after = {}, {}
    for arm in qualification.release.ARMS:
        library = {'arm': arm, 'batch': 8}
        before[arm], after[arm] = {}, {}
        for key, source in dev.items():
            a = parent(source, library, 'skill_dev')['native']
            b = actor(source, library, 'skill_dev')['native']
            if {k: v for k,v in a.items() if k != TASK} != {k: v for k,v in b.items() if k != TASK}:
                raise ValueError('Preserve the other sixteen native hypotheses')
            before[arm][key], after[arm][key] = a[TASK], b[TASK]
    replay = {p: {key: patched(cases[key][TASK], proofs[key]) for key in dev}
              for p,cases in measured_transfer.items()}
    majority_native = next(iter(old_prior_predictions.values()))['training_majority']['answer']
    if len({r['training_majority']['answer'] for r in old_prior_predictions.values()}) != 1:
        raise ValueError('The previous TRAIN-fitted fallback must be fixed for DEV')
    direct = {key: patched({'answer': majority_native, 'evidence_sentence_ids': []}, proofs[key]) for key in dev}

    path = study['grading_paths'][CNI]
    spec = {
        'stage': 'revision6_cni_agreement_disclosure_release', 'previous_cumulative_terminal': q_stop['terminal_sha256'],
        'TRAIN_observations': train_sources, 'TRAIN_proofs_sha256': digest(train_proofs),
        'DEV_proofs_sha256': digest(proofs), 'TRAIN_grade': sha(train_grade), 'DEV_grade': study['grading_file_sha256'][path],
        'fixed_DEV_readers': old_terminal['terminal_sha256'], 'TRAIN_prior_control': selection['terminal_sha256'],
        'TEST_opened': False, 'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, local.__file__, qualification.__file__, earlier.__file__, absence.__file__, transfer.__file__,
        )},
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, h in spec['source_sha256'].items():
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(snapshot) != h:
            raise ValueError('Preserve the exact source checks and native comparisons')
    pred = immutable_json(out / 'sealed_predictions.json', {'before':before, 'after':after,
                          'after_common_B5_policies':replay, MAJORITY:direct})
    immutable_json(out / 'source_proofs.json', {'TRAIN':train_proofs, 'DEV':proofs})
    label_path = ROOT / path
    if ('dev' not in label_path.parts or sha(label_path) != spec['DEV_grade']
            or 'train' not in train_grade.parts or sha(train_grade) != spec['TRAIN_grade']):
        raise ValueError('The scoring source must be the exact original split')
    labels, train_labels = read(label_path), read(train_grade)
    scope = [{'form':p['form'], 'native_label':train_labels[key][TASK]['answer'],
              'matches':p['answer'] == train_labels[key][TASK]['answer']}
             for key,p in train_proofs.items() if p]
    by_arm = {a: comparison(measure(before[a], dev_views, labels), measure(after[a], dev_views, labels))
              for a in before}
    predictions = {name: measure(rows, dev_views, labels)
                   for name, rows in {**replay, MAJORITY:direct}.items()}
    result = sealed({
        'status': 'settled_revision6_cni_agreement_disclosure_release', 'binding_sha256': out.name,
        'formal_DEV': by_arm, 'fit_source_proofs':scope, 'DEV_changed_source_proofs':len(new_cases),
        'archived_B5_DEV': {p: comparison(predictions[MAJORITY], predictions[p]) for p in transfer.POLICIES},
        'archived_B5_DEV_matched_reader_positions': len(dev),
        'original_requests_verified': {'train':len(raws), 'dev':len(raw_dev)}, 'predictions_sha256':pred,
        'new_executor_requests':0, 'new_teacher_requests':0, 'TEST_opened':False, 'ledger':ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status':result['status'], 'terminal_sha256':result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
