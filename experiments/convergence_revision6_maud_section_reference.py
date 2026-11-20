"""Replay source-proven MAUD section references on the original TRAIN and fixed DEV."""

from pathlib import Path
import sqlite3

from experiments import convergence_revision6_cni_agreement_disclosure_release as cni
from experiments import convergence_revision6_maud_parallel_release as parallel
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_section_reference as section
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_section_reference'
POINTER = HANDOFF / 'revision6_maud_section_reference_current.json'
MAUD = parallel.MAUD
TASKS = {'ordinary': parallel.parent_views.ORDINARY, 'negative': parallel.parent_views.NEGATIVE}


def proof(source):
    by_id = {view['id']: view['public']['source_text'] for view in source['views']}
    return section.attachment(by_id[TASKS['ordinary']], by_id[TASKS['negative']])


def apply(native, known):
    if known is None:
        return native
    selected = [TASKS[role] for role in known['targets']]
    return {**native, **{task: {**native[task], 'answer': 'Yes', 'handled': True} for task in selected}}


def train(db):
    prior = parallel.previous
    checkpoint, study, batches = parallel.adoption.archive_context()
    journal = prior.TrainingJournal(checkpoint, study, batches)
    cases, results, receipts, refs = {}, {}, {}, set()
    ids = set()
    for batch, mothers in enumerate(batches, 1):
        source_rows = [s for s in mothers if s['dataset'] == MAUD and s['project_split'] == 'train']
        stage, spec, terminal = prior.bound_stage(prior.FIRST if batch == 1 else prior.observe_pointer(batch))
        path = spec['native_grade_paths'][MAUD]
        refs.add((path, spec['native_grade_sha256'][path]))
        for i, source in enumerate(source_rows):
            found = proof(source)
            if found is None:
                continue
            key = source['key']
            cases[key] = source
            receipts[key] = {**found, 'position': [batch, i], 'archive_terminal_sha256': sha(stage / 'terminal.json')}
            results[key] = {}
            for arm in prior.ARMS:
                obs = journal._observations(arm, batch)
                row = read(journal.directory(arm, batch) / 'predictions' / (digest(key) + '.json'))
                if (digest(row) != obs['predictions'][key]
                        or obs['train_observation_sha256'] != terminal['observation_receipts'][arm]):
                    raise ValueError('Use the original TRAIN request in both source rules')
                response = row['result']
                identity = prior.verify_prediction(db, key, response)
                _, payload = prior.response(db, key, identity)
                parallel.adoption.verify_views(payload, source)
                ids.add(identity)
                results[key][arm] = [response['native'][task]['answer'] for task in TASKS.values()]
    if not any(p['form'] == 'whole_section_override' and len(p['targets']) == 2 for p in receipts.values()):
        raise ValueError('The complete reference must first be supported by original TRAIN source')
    grade, grade_hash = next(iter(refs))
    if len(refs) != 1 or 'train' not in Path(grade).parts or sha(ROOT / grade) != grade_hash:
        raise ValueError('Use the original TRAIN grading source')
    ground = read(ROOT / grade)
    truth = {key: [ground[key][task]['answer'] for task in TASKS.values()] for key in cases}
    for key, p in receipts.items():
        if any(truth[key][i] != 'Yes' for i, role in enumerate(TASKS) if role in p['targets']):
            raise ValueError('A whole-section proof disagrees with the original TRAIN reference')
    return receipts, results, grade_hash, len(ids)


def base_actor():
    qualification = cni.qualification
    base, cohort, originals, study, _, _ = qualification.load_release()
    root, spec, terminal = cni.bound_result(qualification)
    mark = read(root / 'source_effects.json')['DEV']
    if digest(mark) != spec['DEV_source_effects']:
        raise ValueError('Preserve the designation release')
    designated = qualification.QualificationActor(base, mark)
    root, spec, agreement = cni.bound_result(cni)
    scopes = read(root / 'source_proofs.json')['DEV']
    if digest(scopes) != spec['DEV_proofs_sha256'] or spec['previous_cumulative_terminal'] != terminal['terminal_sha256']:
        raise ValueError('Preserve the prior agreement-disclosure release')
    return cni.AgreementDisclosureActor(designated, scopes), cohort, originals, study, agreement['terminal_sha256']


def score(cohort, predictions, lab):
    after = {}
    for arm, rows in predictions.items():
        after[arm] = {}
        for task in TASKS.values():
            paired = [[], []]
            for key, row in rows.items():
                view = next(v for v in cohort[key]['views'] if v['id'] == task)
                for axis, phase in zip(paired, ('before', 'after'), strict=True):
                    value = grade_view(MAUD, view, lab[key][task], row[phase][task])['grade']
                    axis.append({'source': key, 'view': task, 'grade': value})
            old, new = paired
            after[arm][task] = {'correct': [sum(z['grade'] for z in side) for side in paired],
                                'paired': paired_source_effect(old, new),
                                'repairs': sum(b['grade'] > a['grade'] for a, b in zip(old, new, strict=True)),
                                'regressions': sum(b['grade'] < a['grade'] for a, b in zip(old, new, strict=True))}
    return after


def run():
    parent, cohort, original, study, predecessor = base_actor()
    sources = {s['key']: s for s in cohort if s['dataset'] == MAUD and s['project_split'] == 'dev'}
    effects = {key: proof(source) for key, source in sources.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        support, training, train_grade, train_reads = train(db)
        hits = [key for key, receipt in effects.items() if receipt is not None]
        dev_reads = parallel.verify_original_inputs(db, original, sources, hits)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(sources) != 16:
        raise ValueError('Require the complete fixed MAUD cohort and settled continuous ledger')
    grade = study['grading_paths'][MAUD]
    spec = {
        'stage': 'revision6_maud_section_reference', 'previous_cumulative_terminal': predecessor,
        'TRAIN_proofs_sha256': digest(support), 'DEV_proofs_sha256': digest(effects),
        'TRAIN_grade_sha256': train_grade, 'DEV_grade_sha256': study['grading_file_sha256'][grade],
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, section.__file__, parallel.__file__, cni.__file__,
        )}, 'TEST_opened': False,
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, expected in spec['source_sha256'].items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(path) != expected:
            raise ValueError('Preserve the exact source proof artifact')
    predictions = {}
    for arm in parallel.release.ARMS:
        predictions[arm] = {}
        library = {'arm': arm, 'batch': 8}
        for key, source in sources.items():
            old = parent(source, library, 'skill_dev')['native']
            new = apply(old, effects[key])
            if any(old[task] != new[task] for task in old if task not in TASKS.values()):
                raise ValueError('The shared section proof cannot change unrelated tasks')
            predictions[arm][key] = {mode: {task: bank[task]['answer'] for task in TASKS.values()}
                                     for mode, bank in (('before', old), ('after', new))}
    pred_sha = immutable_json(out / 'sealed_predictions.json', predictions)
    immutable_json(out / 'source_proofs.json', {'TRAIN': support, 'DEV': effects})
    grade_path = ROOT / grade
    if 'dev' not in grade_path.parts or sha(grade_path) != spec['DEV_grade_sha256']:
        raise ValueError('Use only the sealed fixed DEV references after recording predictions')
    comparison = score(sources, predictions, read(grade_path))
    label_sets = [tuple(row['after'] for row in bank.values()) for bank in predictions.values()]
    terminal = sealed({
        'status': 'settled_revision6_maud_section_reference', 'binding_sha256': out.name, 'ledger': ledger,
        'TRAIN_proofs': len(support), 'TRAIN_forms': [record['form'] for record in support.values()],
        'TRAIN_archived_outputs': list(training.values()), 'DEV_proofs': len(hits),
        'DEV_forms': [effects[key]['form'] for key in hits],
        'matched_archived_reads': {'TRAIN': train_reads, 'DEV': dev_reads},
        'all_arms_native_equal': all(rows == label_sets[0] for rows in label_sets),
        'same_source_rules_for_all_arms': True, 'score': comparison, 'predictions_sha256': pred_sha,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
