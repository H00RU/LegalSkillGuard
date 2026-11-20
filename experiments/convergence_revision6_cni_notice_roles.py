"""Replay source-bound compelled notices on original TRAIN and five fixed DEV arms."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_compelled_notice as original
from experiments import convergence_revision5_cni_notice_coverage as coverage
from experiments import convergence_revision6_cni_external_recipients as cumulative
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import cni_compelled_notice_roles as roles
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_notice_roles'
POINTER = HANDOFF / f'{STAGE}_current.json'
CNI, TASK = original.DATASET, original.TASK
archived = cumulative.archived


def missing_proofs(source):
    view = original.view_for(source)
    existing = original.proof(view)
    if existing['same_clause'] or existing['linked']:
        return []
    return roles.governed([' '.join(s.split()) for s in original.span_inventory(view)])


def project_result(result, proof):
    old = result['native']
    after = roles.project(old[TASK], proof)
    if after == old[TASK]:
        return result
    return {**result, 'native': {**old, TASK: after}}


class CompelledNoticeActor:
    def __init__(self, inner, proofs):
        self.inner = inner
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        original_result = self.inner(source, library, purpose)
        if source['dataset'] != CNI or not (proof := self.proofs.get(source['key'])):
            return original_result
        return project_result(original_result, proof)


def old_coverage_guard(sources, grade_hash):
    view = {key: original.view_for(source) for key, source in sources.items()}
    guard_cases = {key: coverage.possibly_compelled(v) for key, v in view.items()}
    path, = (original.HOME / 'coverage_guard' / 'dev').glob('*/terminal.json')
    lock = read(path.parent / 'binding.json')
    end = read(path)
    prior = sorted(f for f in (original.HOME / 'DEV').glob('*/terminal.json')
                   if sha(f) == lock['archived_terminal_sha256'])
    if not prior:
        raise ValueError('The DEV baseline referenced by the coverage guard is missing')
    baseline_path = prior[0]
    baseline_end = read(baseline_path)
    baseline_file = baseline_path.parent / 'predictions.json'
    baseline = read(baseline_file)
    stored = path.parent / 'predictions.json'
    if (digest(lock) != path.parent.name or end['partition'] != 'dev' or end['new_calls']
            or lock['native_grade_sha256'] != grade_hash
            or digest(guard_cases) != lock['guard_decisions_sha256']
            or sha(baseline_file) != baseline_end['predictions_sha256']
            or sha(stored) != end['predictions_sha256']):
        raise ValueError('Reuse the exact prior coverage-guarded DEV baseline')
    restored = {arm: {key: coverage.guarded(entry, baseline['scope'][key], guard_cases[key])
                      for key, entry in rows.items()} for arm, rows in baseline['predictions'].items()}
    if restored != read(stored) or any(set(rows) != set(sources) for rows in restored.values()):
        raise ValueError('The older coverage guard must reproduce on every original DEV case')
    return {arm: {key: row['coverage_guarded'] for key, row in bank.items()}
            for arm, bank in restored.items()}, sha(path)


def score(sources, labels, outputs):
    by_phase = {}
    for phase in ('before', 'after'):
        rows = outputs[phase]
        if set(rows) != set(sources):
            raise ValueError('Both scoring arms must contain the same original mothers')
        cells = []
        for key in sources:
            record = rows[key]
            outcome = grade_view(CNI, original.view_for(sources[key]), labels[key][TASK],
                                 record['answer'], record['evidence_sentence_ids'])
            cells.append({'source': key, 'view': TASK, 'correct': outcome['grade'],
                          'grounded': outcome['grade'] * outcome['evidence_f1'],
                          'evidence': outcome['evidence_f1']})
        by_phase[phase] = cells
    a, b = by_phase.values()
    return {'correct': [sum(x['correct'] for x in bank) for bank in (a, b)],
            'evidence_F1': [mean(x['evidence'] for x in bank) for bank in (a, b)],
            'correct_class_evidence_F1': [mean(x['grounded'] for x in bank) for bank in (a, b)],
            'classification_improved': sum(v['correct'] > u['correct'] for u, v in zip(a, b, strict=True)),
            'classification_regressed': sum(v['correct'] < u['correct'] for u, v in zip(a, b, strict=True)),
            'evidence_regressed': sum(v['evidence'] < u['evidence'] for u, v in zip(a, b, strict=True)),
            'paired': {name: paired_source_effect(*[[{**row, 'grade': row[name]} for row in bank]
                                                    for bank in (a, b)])
                       for name in ('correct', 'evidence', 'grounded')}}


def run():
    train, train_archive, train_grade, train_origin = archived.collect(*archived.archive_context(), 'train')
    parent, cohort, dev_arms, study, dev_origin = cumulative.fixed.base_actor()
    dev = {s['key']: s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'dev'}
    if (len(train), len(dev), len(dev_arms)) != (24, 16, 5):
        raise ValueError('Use the complete original CNI TRAIN and fixed five-arm DEV populations')
    cohorts = {'TRAIN': train, 'DEV': dev}
    proofs = {split: {key: p for key, s in sources.items() if (p := missing_proofs(s))}
              for split, sources in cohorts.items()}
    actor = CompelledNoticeActor(parent, proofs['DEV'])
    outputs, physical = {'TRAIN': {}, 'DEV': {}}, {'TRAIN': {}, 'DEV': {}}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for arm, bank in train_archive.items():
            before = {key: original.answer(orig['native'][TASK], original.proof(original.view_for(train[key])),
                                           use_links=True) for key, orig in bank.items()}
            after = {key: roles.project(row, proofs['TRAIN'].get(key, ())) for key, row in before.items()}
            outputs['TRAIN'][arm] = {'before': before, 'after': after}
            for key in proofs['TRAIN']:
                archived.checked_result(db, train[key], bank[key], physical['TRAIN'])

        for arm, (folder, seal, cell) in dev_arms.items():
            before, after = {}, {}
            library = {'arm': arm, 'batch': 8}
            for key, source in dev.items():
                entering = parent(source, library, 'skill_dev')
                revised = actor(source, library, 'skill_dev')
                if any(v != revised['native'][h] for h, v in entering['native'].items() if h != TASK):
                    raise ValueError('A notice proof cannot change other hypotheses')
                before[key], after[key] = entering['native'][TASK], revised['native'][TASK]
                if key not in proofs['DEV']:
                    continue
                saved = read(folder / 'predictions' / f'{digest(key)}.json')
                if (digest(saved) != seal['predictions_sha256'][key]
                        or saved['public_source_sha256'] != digest(source)
                        or saved['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Preserve the exact original DEV observation and carrier library')
                archived.checked_result(db, source, saved['result'], physical['DEV'], dev=True)
            outputs['DEV'][arm] = {'before': before, 'after': after}
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if set(ledger) - {'completed', 'failed'}:
        raise ValueError('Only completed exact archive reads may enter this comparison')
    dev_grade_name = study['grading_paths'][CNI]
    dev_grade = ROOT / dev_grade_name
    hashes = {'TRAIN': sha(train_grade), 'DEV': study['grading_file_sha256'][dev_grade_name]}
    if 'train' not in train_grade.parts or 'dev' not in dev_grade.parts or sha(dev_grade) != hashes['DEV']:
        raise ValueError('Use original TRAIN and fixed DEV grades')
    old_guard, old_guard_sha = old_coverage_guard(dev, hashes['DEV'])
    against_guard = {role: {'before': rows, 'after': outputs['DEV'][role]['after']} for role, rows in old_guard.items()}
    files = (__file__, roles.__file__, cumulative.__file__, cumulative.fixed.__file__, original.__file__, coverage.__file__,
             archived.__file__)
    binding = {'stage': STAGE, 'TEST_opened': False, 'prior_DEV_actor': dev_origin,
               'original_TRAIN_observations': train_origin, 'grades_sha256': hashes, 'prior_DEV_coverage_guard': old_guard_sha,
               'source_proofs_sha256': digest(proofs),
               'archive_reads_sha256': {part: digest(sorted(reqs)) for part, reqs in physical.items()},
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in files}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_notice_proofs.json', proofs)
    prediction_sha = immutable_json(out / 'sealed_predictions.json', {**outputs, 'DEV_vs_coverage_guard': against_guard})
    labels = {'TRAIN': read(train_grade), 'DEV': read(dev_grade)}
    scores = {part: {arm: score(cohorts[part], labels[part], bank) for arm, bank in inputs.items()}
              for part, inputs in outputs.items()}
    guarded_scores = {arm: score(dev, labels['DEV'], bank) for arm, bank in against_guard.items()}
    audit = {}
    for part, found in proofs.items():
        checks = {'positive': 0, 'reference_class_conflicts': 0, 'exact_reference_evidence': 0}
        for key, proof in found.items():
            ref = labels[part][key][TASK]
            citations = {p[field] for p in proof for field in ('trigger', 'duty')}
            checks['positive'] += 1
            checks['reference_class_conflicts'] += ref['answer'] != 'Entailment'
            checks['exact_reference_evidence'] += citations == set(ref['evidence'])
        audit[part] = checks
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name,
                       'predictions_sha256': prediction_sha, 'native': scores, 'DEV_vs_coverage_guard': guarded_scores,
                       'proof_audit': audit,
                       'covered_mothers': {part: [len(proofs[part]), len(source)] for part, source in cohorts.items()},
                       'archived_physical_reads': {part: len(rows) for part, rows in physical.items()},
                       'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger},
                      'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
