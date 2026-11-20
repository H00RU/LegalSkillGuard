"""Compare operative-only citations with full termination witnesses on source-bound contracts."""

import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_survival_scope as legacy
from experiments import convergence_revision6_cni_copy_mention_roles as cumulative
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_cni_cumulative_dev import scores as full_scores
from legal_skill_guard.paired_interfaces import cni_survival_triggers as scope
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_survival_trigger_roles'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK = legacy.TASK
archive = cumulative.archive


def view(source):
    return next(row for row in source['views'] if row['id'] == TASK)


def compile_scope(source):
    spans = legacy.normalize(view(source))
    paths = scope.support(spans)
    existing = legacy.bound_proofs(spans)
    return {'paths': paths, 'new_scope': paths if not existing else [],
            'legacy_witness': bool(existing)}


def projection(native, paths, with_trigger):
    previous = native[TASK]
    updated = scope.project(previous, paths, include_antecedent=with_trigger)
    if previous == updated:
        return native
    return {**native, TASK: updated}


def native_rows(bank):
    return {arm: {key: {task: {'answer': row['answer'], 'evidence_sentence_ids': row['evidence_sentence_ids']}
                        for task, row in native.items()}
                  for key, native in rows.items()}
            for arm, rows in bank.items()}


class SurvivalTriggerActor:
    """Reuse the prior DEV actor and apply the same proof to every arm."""

    def __init__(self, parent, sources, proofs):
        self.parent = parent
        self.sources = {key: digest(source) for key, source in sources.items()}
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        original = self.parent(source, library, purpose)
        key = source['key']
        if (source['dataset'] != legacy.DATASET or purpose != 'skill_dev'
                or source['project_split'] != 'dev' or library['batch'] != 8 or key not in self.sources):
            return original
        if digest(source) != self.sources[key]:
            raise ValueError('A compiled survival witness cannot be reused on changed text')
        paths = self.proofs[key]['new_scope']
        if not paths:
            return original
        observed = original['native'][TASK]
        revised = scope.project(observed, paths, include_antecedent=False)
        return {**original, 'native': {**original['native'], TASK: {
            **observed, **revised, 'handled': True, 'reason': None,
        }}}


def prepare_dev():
    base, dev, originals, study, _ = cumulative.common.prior.prepare()
    approved = cumulative.common.CopyApprovalActor(base, {key: hit for key, source in dev.items()
                                                          if (hit := cumulative.common.source_proof(source))})
    parent = cumulative.CopyMentionActor(approved, {key: cumulative.proof(source) for key, source in dev.items()})
    proofs = {key: compile_scope(source) for key, source in dev.items()}
    return parent, SurvivalTriggerActor(parent, dev, proofs), dev, originals, study, proofs


def evaluate(sources, banks, labels):
    views = {key: view(source) for key, source in sources.items()}
    outputs = {}
    for arm, variants in banks.items():
        cells = {}
        for name, values in variants.items():
            rows = []
            for key, source_view in views.items():
                pred = values[key][TASK]
                score = grade_view(legacy.DATASET, source_view, labels[key][TASK],
                                   pred['answer'], pred['evidence_sentence_ids'])
                rows.append({'source': key, 'view': TASK, 'correct': score['grade'],
                             'grounded': score['grade'] * score['evidence_f1']})
            cells[name] = rows
        outputs[arm] = {
            name: {
                'correct': int(sum(row['correct'] for row in rows)),
                'correct_class_evidence_F1': mean(row['grounded'] for row in rows),
                'evidence_improved': sum(a['grounded'] < b['grounded']
                                         for a, b in zip(cells['before'], rows, strict=True)),
                'evidence_regressed': sum(a['grounded'] > b['grounded']
                                          for a, b in zip(cells['before'], rows, strict=True)),
                'paired': {metric: paired_source_effect(
                    *[[{**row, 'grade': row[metric]} for row in side] for side in (cells['before'], rows)]
                ) for metric in ('correct', 'grounded')} if name != 'before' else None,
            }
            for name, rows in cells.items()
        }
    return outputs


def scope_coverage(sources, labels, compiled):
    counts = Counter()
    observed = Counter()
    for key, source in sources.items():
        target = labels[key][TASK]
        if compiled[key]['paths']:
            counts['matched'] += 1
            counts['positive'] += target['answer'] == 'Entailment'
            counts['novel_mothers'] += bool(compiled[key]['new_scope'])
            counts['operative_evidence_in_reference'] += sum(
                path['operative'] in target['evidence'] for path in compiled[key]['paths']
            )
        if target['answer'] == 'Entailment':
            spans = legacy.normalize(view(source))
            observed.update(scope.referenced_events(spans, target['evidence']))
    return {'mothers': len(sources), 'path_coverage': dict(counts), 'annotated_other_timing_events': dict(observed)}


def run():
    parent, actor, dev, originals, study, current_proofs = prepare_dev()
    previous = read(cumulative.POINTER)
    folder = ROOT / previous['artifact_root']
    receipt = verify(read(folder / 'terminal.json'), 'terminal_sha256')
    data = folder / 'sealed_predictions.json'
    if (previous['terminal_sha256'] != receipt['terminal_sha256'] or sha(data) != receipt['predictions_sha256']
            or digest(read(folder / 'binding.json')) != folder.name or receipt['TEST_opened']):
        raise ValueError('Use the latest complete five-arm ContractNLI development outputs')
    train, older, train_grade, observe_seals = archive.collect(*archive.archive_context(), 'train')
    dev_grade = ROOT / study['grading_paths'][cumulative.common.prior.CNI]
    if ('train' not in train_grade.parts or 'dev' not in dev_grade.parts
            or sha(dev_grade) != study['grading_file_sha256'][str(dev_grade.relative_to(ROOT))]
            or (len(train), len(dev), len(originals)) != (24, 16, 5)):
        raise ValueError('Use only the unchanged original TRAIN and fixed DEV cohort')
    sources = {'TRAIN': train, 'DEV': dev}
    proofs = {name: {key: compile_scope(source) for key, source in rows.items()}
              for name, rows in sources.items()}
    if proofs['DEV'] != current_proofs:
        raise ValueError('The formal DEV actor must use the exact shared source proofs')
    banks = {
        'TRAIN': native_rows({arm: {key: row['native'] for key, row in rows.items()} for arm, rows in older.items()}),
        'DEV': native_rows(read(data)['cumulative_DEV']),
    }
    revised, used = {}, {'TRAIN': {}, 'DEV': {}}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
            raise ValueError('Reuse sealed physical requests at a settled experimental boundary')
        for name, by_arm in banks.items():
            revised[name] = {}
            for arm, predictions in by_arm.items():
                paths = {key: row['new_scope'] if name == 'DEV' else row['paths']
                         for key, row in proofs[name].items()}
                revised[name][arm] = {
                    'before': predictions,
                    'operative_only': {key: projection(row, paths[key], False) for key, row in predictions.items()},
                    'full_witness': {key: projection(row, paths[key], True) for key, row in predictions.items()},
                }
                if name == 'DEV':
                    library = {'arm': arm, 'batch': 8}
                    measured = {arm: {key: actor(source, library, 'skill_dev')['native'] for key, source in dev.items()}}
                    original = {arm: {key: parent(source, library, 'skill_dev')['native']
                                      for key, source in dev.items()}}
                    if (native_rows(original)[arm] != predictions
                            or native_rows(measured)[arm] != revised[name][arm]['operative_only']):
                        raise ValueError('Reproduce every released native result through the execution entry')
                for key in predictions:
                    if not paths[key]:
                        continue
                    source = sources[name][key]
                    if name == 'TRAIN':
                        result = older[arm][key]
                    else:
                        cell, seal, grade = originals[arm]
                        saved = read(cell / 'predictions' / f'{digest(key)}.json')
                        if (digest(saved) != seal['predictions_sha256'][key]
                                or saved['library_sha256'] != grade['libraries'][source['dataset']]
                                or saved['public_source_sha256'] != digest(source)):
                            raise ValueError('Bind the source, fixed library and original physical output')
                        result = saved['result']
                    archive.checked_result(db, source, result, used[name], dev=name == 'DEV')
    spec = {
        'stage': STAGE, 'TEST_opened': False, 'source_proofs_sha256': digest(proofs),
        'TRAIN_grade_sha256': sha(train_grade), 'DEV_grade_sha256': sha(dev_grade),
        'TRAIN_observation_terminals': observe_seals, 'previous_fixed_DEV_terminal': receipt['terminal_sha256'],
        'physical_receipts_sha256': {name: digest(sorted(value)) for name, value in used.items()},
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, scope.__file__, cumulative.__file__, legacy.__file__,
        )},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    cumulative.snapshot(out, spec['source_sha256'])
    tag = immutable_json(out / 'sealed_predictions.json', revised)
    immutable_json(out / 'source_proofs.json', proofs)
    labels = {'TRAIN': read(train_grade), 'DEV': read(dev_grade)}
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'TASK': TASK, 'scope_coverage': {name: scope_coverage(rows, labels[name], proofs[name])
                                        for name, rows in sources.items()},
        'survival_paired': {name: evaluate(sources[name], bank, labels[name]) for name, bank in revised.items()},
        'cumulative_DEV': {phase: full_scores({arm: rows[phase] for arm, rows in revised['DEV'].items()},
                                             dev, labels['DEV'])
                           for phase in ('before', 'operative_only', 'full_witness')},
        'reused_physical_requests': {name: len(ids) for name, ids in used.items()},
        'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
