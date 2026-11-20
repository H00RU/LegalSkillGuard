"""Apply source-proved designation routes in the cumulative fixed B8 evaluation."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_designation_scope as roles
from experiments import convergence_revision5_cni_reverse_engineering as archived
from experiments import convergence_revision6_maud_knowledge_release as knowledge
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_qualification_effect as local
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_cni_qualification_release'
POINTER = HANDOFF / 'revision6_cni_qualification_release_current.json'
CNI = archived.DATASET
TASK = roles.TASK
release = knowledge.parallel.release


def contract_view(source):
    return next(v for v in source['views'] if v['id'] == TASK)


def source_effect(view):
    independent = local.alternative_route(roles.prior.spans_for(view))
    if independent:
        return {**independent, 'answer': 'Contradiction'}
    old = roles.proof(view)
    if old['answer'] is None:
        return None
    return {'form': old['kind'], 'answer': old['answer'],
            'evidence_sentence_ids': old['evidence_sentence_ids']}


class QualificationActor:
    def __init__(self, parent, effects):
        self.parent = parent
        self.effects = effects

    def __call__(self, source, library, purpose):
        baseline = self.parent(source, library, purpose)
        patch = self.effects.get(source['key'])
        if source['dataset'] != CNI or patch is None:
            return baseline
        content = {name: patch[name] for name in ('answer', 'evidence_sentence_ids')}
        native = baseline['native']
        return {**baseline, 'native': {**native, TASK: {**native[TASK], **content, 'handled': True}}}


def load_release():
    historical, standard, spec = release.stage(release.POINTER)
    last = ROOT / read(knowledge.POINTER)['artifact_root']
    saved = verify(read(last / 'terminal.json'), 'terminal_sha256')
    lock = read(last / 'binding.json')
    parallel = ROOT / read(knowledge.parallel.POINTER)['artifact_root']
    parallel_status = verify(read(parallel / 'terminal.json'), 'terminal_sha256')
    parallel_lock = read(parallel / 'binding.json')
    if (digest(lock) != last.name or digest(parallel_lock) != parallel.name
            or saved['terminal_sha256'] != read(knowledge.POINTER)['terminal_sha256']
            or lock['parallel_release'] != parallel_status['terminal_sha256']
            or parallel_lock['original_terminal_sha256'] != standard['terminal_sha256']
            or saved['TEST_opened'] or parallel_status['TEST_opened']):
        raise ValueError('Reuse the exact preceding cumulative release')
    maud = read(last / 'source_effects.json')['DEV']
    covenants = read(parallel / 'source_proofs.json')['dev']
    if digest(maud) != lock['DEV_effects'] or digest(covenants) != parallel_lock['proof_sha256']:
        raise ValueError('Preserve both existing MAUD source repairs')
    cells = release.parent_cells(historical, standard)
    inherited = knowledge.KnowledgeEffectActor(historical, cells, covenants, maud)
    cohort, original, study, _ = release.formal.common.archive()
    if digest(cohort) != spec['DEV_public_sha256']:
        raise ValueError('Current source roster differs from its cumulative release')
    return inherited, cohort, original, study, saved['terminal_sha256'], cells


def reduce_scores(cohort, outputs, grade):
    arms = {}
    for arm, rows in outputs.items():
        data = {'before': [], 'after': []}
        for key, record in rows.items():
            view, reference = contract_view(cohort[key]), grade[key][TASK]
            for mode, other in record.items():
                measured = grade_view(CNI, view, reference, other['answer'], other['evidence_sentence_ids'])
                data[mode].append({'source': key, 'view': TASK, **measured})
        before, after = data['before'], data['after']
        arms[arm] = {
            'correct': {m: int(sum(r['grade'] for r in values)) for m, values in data.items()},
            'evidence_F1': {m: mean(r['evidence_f1'] for r in values) for m, values in data.items()},
            'predictions_changed': sum(p['before'] != p['after'] for p in rows.values()),
            'corrected': sum(a['grade'] < b['grade'] for a,b in zip(before, after, strict=True)),
            'regressed': sum(a['grade'] > b['grade'] for a,b in zip(before, after, strict=True)),
            'classification_effect': paired_source_effect(before, after),
        }
    return arms


def run():
    inherited, cohort, originals, study, previous, cells = load_release()
    train, train_raw, train_grade, train_refs = archived.collect(*archived.archive_context(), 'train')
    dev = {s['key']: s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'dev'}
    if len(dev) != 16:
        raise ValueError('Preserve the original fixed ContractNLI DEV')
    train_effects = {key: source_effect(contract_view(s)) for key,s in train.items()}
    dev_effects = {key: source_effect(contract_view(s)) for key,s in dev.items()}
    fit = {key: effect for key, effect in train_effects.items() if effect and effect['form'] in (
        'unmarked_information_qualifies', 'designation_or_context', 'contextual_definition_subclause',
    )}
    if not fit:
        raise ValueError('Require TRAIN evidence for unmarked qualification')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        train_reads = {}
        for arm in train_raw:
            for key in fit:
                archived.checked_result(db, train[key], train_raw[arm][key], train_reads)
        # The old wire verifier checks the native result and the request against
        # the full public source. No repaired or masked text enters the ledger.
        dev_reads = {}
        for arm, (folder, seal, cell) in originals.items():
            for key, source in dev.items():
                if dev_effects[key] is None:
                    continue
                record = read(folder / 'predictions' / (digest(key) + '.json'))
                if (digest(record) != seal['predictions_sha256'][key]
                        or record['public_source_sha256'] != digest(source)
                        or record['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Development result must keep its original source and wire')
                archived.checked_result(db, source, record['result'], dev_reads, dev=True)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('A running request must first be reconciled')
    grading = study['grading_paths'][CNI]
    spec = {
        'stage': 'revision6_cni_qualification_release', 'prior_cumulative_terminal': previous,
        'TRAIN_source_effects': digest(train_effects), 'DEV_source_effects': digest(dev_effects),
        'TRAIN_archives': train_refs, 'TRAIN_grade': sha(train_grade), 'DEV_grade': study['grading_file_sha256'][grading],
        'TEST_opened': False, 'source_sha256': {str(Path(n).relative_to(ROOT)): sha(Path(n)) for n in (
            __file__, local.__file__, roles.__file__, archived.__file__, knowledge.__file__,
        )},
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, expected in spec['source_sha256'].items():
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(snapshot) != expected:
            raise ValueError('The shared repair uses its bound document grammar')
    actor = QualificationActor(inherited, dev_effects)
    dev_predictions = {}
    grade_rows = {}
    for arm in release.ARMS:
        lib = {'arm': arm, 'batch': 8}
        dev_predictions[arm] = {}
        for key, source in dev.items():
            before = inherited(source, lib, 'skill_dev')['native']
            after = actor(source, lib, 'skill_dev')['native']
            if {k:v for k,v in before.items() if k != TASK} != {k:v for k,v in after.items() if k != TASK}:
                raise ValueError('Only the exact designation hypothesis is rescored')
            dev_predictions[arm][key] = {'before': before[TASK], 'after': after[TASK]}
        grade_rows[arm] = [row for row in cells[arm][1]['source_scores']
                           if row['dataset'] == CNI and row['view'] != TASK]
    pred = immutable_json(out / 'sealed_predictions.json', dev_predictions)
    immutable_json(out / 'source_effects.json', {'TRAIN':train_effects, 'DEV':dev_effects})
    path = ROOT / grading
    if ('dev' not in path.parts or sha(path) != spec['DEV_grade'] or 'train' not in train_grade.parts
            or sha(train_grade) != spec['TRAIN_grade']):
        raise ValueError('Only score original sealed TRAIN and DEV targets')
    target, control = read(path), read(train_grade)
    summaries = reduce_scores(dev, dev_predictions, target)
    for arm, row in summaries.items():
        rest = grade_rows[arm]
        if len(rest) != 256:
            raise ValueError('Keep the prior scores for the other sixteen hypotheses')
        row['all_CNI_correct'] = {mode: int(sum(r['grade'] for r in rest)) + score
                                  for mode, score in row['correct'].items()}
    result = sealed({
        'status': 'settled_revision6_cni_qualification_release', 'binding_sha256': out.name,
        'TRAIN_mothers': len(train), 'TRAIN_unmarked_route_matches': sum(
            control[key][TASK]['answer'] == x['answer'] for key,x in fit.items()),
        'TRAIN_unmarked_routes': len(fit), 'DEV_mothers':len(dev),
        'DEV_scope_proofs': sum(p is not None for p in dev_effects.values()), 'per_arm':summaries,
        'original_requests_verified': {'train':len(train_reads), 'dev':len(dev_reads)},
        'predictions_sha256':pred, 'new_executor_requests':0, 'new_teacher_requests':0,
        'TEST_opened':False, 'ledger':ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status':result['status'], 'terminal_sha256':result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
