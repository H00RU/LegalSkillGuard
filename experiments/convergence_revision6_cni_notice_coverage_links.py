"""Replay source-bound notice coverage and identify the remaining M1 domain."""

import sqlite3
from collections import Counter
from pathlib import Path

from experiments import convergence_revision6_cni_complement_contractor_control as preceding
from experiments import convergence_revision6_cni_disposition_sequence as previous
from experiments import convergence_revision6_cni_notice_roles as notice
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_notice_coverage_links as links
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_notice_coverage_links'
POINTER = HANDOFF / f'{STAGE}_current.json'
TASK, CNI = notice.TASK, notice.CNI
employee = previous.employee


def trace(source):
    view = notice.original.view_for(source)
    lines = [' '.join(span.split()) for span in notice.original.span_inventory(view)]
    abstract = notice.original.proof(view)
    proof = links.bind(lines, [i for i, text in enumerate(lines) if notice.original.trigger(text)])
    if proof is not None:
        return {'scope': proof['kind'], 'new_proof': proof, 'answer': proof['answer']}
    if abstract['same_clause'] or abstract['linked'] or notice.missing_proofs(source):
        return {'scope': 'existing_notice_witness', 'new_proof': None, 'answer': 'Entailment'}
    if not notice.coverage.possibly_compelled(view):
        return {'scope': 'no_compulsion_trigger', 'new_proof': None, 'answer': 'NotMentioned'}
    return {'scope': 'unresolved', 'new_proof': None, 'answer': None}


def after_notice(native, witness):
    if witness is None:
        return native
    record = native[TASK]
    revised = {**record, 'answer': witness['answer'], 'evidence_sentence_ids': witness['evidence_sentence_ids']}
    if revised == record:
        return native
    return {**native, TASK: {**revised, 'handled': True, 'reason': None}}


class NoticeCoverageActor:
    def __init__(self, baseline, dev, proofs):
        self.baseline = baseline
        self.sources = {key: digest(s) for key, s in dev.items()}
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        current = self.baseline(source, library, purpose)
        key = source['key']
        if (source['dataset'] != CNI or source['project_split'] != 'dev'
                or library['batch'] != 8 or purpose != 'skill_dev' or key not in self.proofs):
            return current
        if digest(source) != self.sources[key]:
            raise ValueError('Bind each notice proof to the exact original source')
        return {**current, 'native': after_notice(current['native'], self.proofs[key]['new_proof'])}


def previous_dev():
    _, shared, dev, original, study, _ = employee.base.prior.prepare_dev()
    own_permission = {key: employee.base.source_proof(source) for key, source in dev.items()}
    access = {key: employee.base.existing.source_paths(source) for key, source in dev.items()}
    configured = employee.EmployeeWitnessActor(employee.base.EmployeePermissionActor(shared, dev, own_permission), dev, access)
    disposal = {key: previous.source_proof(source) for key, source in dev.items()}
    return previous.DispositionSequenceActor(configured, dev, disposal), dev, original, study


def run():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] != preceding.STAGE + '_settled' or state['active_tasks']:
        raise ValueError('Continue only at the existing settled boundary')
    root, old, terminal = previous.previous.b4.terminal(previous)
    _, _, two_group_check = previous.previous.b4.terminal(preceding)
    latest = root / 'sealed_predictions.json'
    if sha(latest) != terminal['predictions_sha256']:
        raise ValueError('Use the last compared formal outputs')
    before = read(latest)['formal']
    baseline, dev, cells, study = previous_dev()
    _, train_conf, roster = notice.archived.archive_context()
    train, observed, graded_train, observed_receipts = notice.archived.collect(
        *notice.archived.archive_context(), 'train',
    )
    graded_dev = ROOT / study['grading_paths'][CNI]
    if (len(train) != 24 or len(dev) != 16 or train_conf['executor'] != study['executor']
            or [sha(graded_train), sha(graded_dev)] != old['reference_hashes']
            or 'train' not in graded_train.parts or 'dev' not in graded_dev.parts):
        raise ValueError('Use the original TRAIN and fixed DEV sources and native labels')
    positions = {row['key']: [batch, index] for batch, cohort in enumerate(roster, 1)
                 for index, row in enumerate((x for x in cohort if x['dataset'] == CNI), 1)}
    groups = {'TRAIN': train, 'fixed_DEV': dev}
    scope = {part: {key: trace(source) for key, source in sources.items()} for part, sources in groups.items()}
    actor = NoticeCoverageActor(baseline, dev, scope['fixed_DEV'])
    comparisons, reads = {}, {part: {} for part in groups}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger != terminal['ledger'] or ledger != two_group_check['ledger'] or ledger.get('reserved'):
            raise ValueError('Use archive-only evaluation under the settled continuous ledger')
        for part, cohort in groups.items():
            comparisons[part] = {}
            for arm, phases in before[part].items():
                original = phases['shared_disposition']
                revised = {key: after_notice(native, scope[part][key]['new_proof']) for key, native in original.items()}
                comparisons[part][arm] = {'before': original, 'after': revised}
                for key, source in cohort.items():
                    if part == 'fixed_DEV':
                        library = {'arm': arm, 'batch': 8}
                        for reader, expected in ((baseline, original[key]), (actor, revised[key])):
                            result = reader(source, library, 'skill_dev')['native']
                            if previous.employee.base.prior.native_rows({arm: {key: result}}) != (
                                previous.employee.base.prior.native_rows({arm: {key: expected}})
                            ):
                                raise ValueError('Reproduce the fixed DEV actor before and after the revision')
                    if original[key] == revised[key]:
                        continue
                    if part == 'TRAIN':
                        record = observed[arm][key]
                    else:
                        directory, seal, grades = cells[arm]
                        saved = read(directory / 'predictions' / f'{digest(key)}.json')
                        assert digest(saved) == seal['predictions_sha256'][key]
                        assert saved['library_sha256'] == grades['libraries'][CNI]
                        assert saved['public_source_sha256'] == digest(source)
                        record = saved['result']
                    notice.archived.checked_result(db, source, record, reads[part], dev=part == 'fixed_DEV')
    files = {str(Path(name).relative_to(ROOT)): sha(Path(name)) for name in
             (__file__, links.__file__, notice.__file__, notice.original.__file__, notice.coverage.__file__, previous.__file__)}
    binding = {
        'stage': STAGE, 'source_sha256': files, 'fixed_DEV_terminal': terminal['terminal_sha256'],
        'previous_TRAIN_attribution': two_group_check['terminal_sha256'], 'source_roles_sha256': digest(scope),
        'grade_sha256': [sha(graded_train), sha(graded_dev)], 'original_TRAIN_observations': observed_receipts,
        'physical_reads_sha256': {part: digest(sorted(values)) for part, values in reads.items()}, 'TEST_opened': False,
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    previous.employee.base.prior.cumulative.snapshot(out, files)
    prediction_sha = immutable_json(out / 'sealed_predictions.json', comparisons)
    immutable_json(out / 'scope.json', scope)
    labels = {'TRAIN': read(graded_train), 'fixed_DEV': read(graded_dev)}
    coverage = {}
    for part, rows in scope.items():
        coverage[part] = {'mothers': len(rows), 'by_scope': dict(Counter(x['scope'] for x in rows.values())),
                          'new_class_matches': sum(row['new_proof'] is not None and row['answer'] == labels[part][k][TASK]['answer']
                                                   for k, row in rows.items()),
                          'known_class_conflicts': sum(row['answer'] is not None and row['answer'] != labels[part][k][TASK]['answer']
                                                       for k, row in rows.items())}
    proposed_m1_cases = [p for key, p in positions.items() if scope['TRAIN'][key]['scope'] == 'unresolved']
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
        'coverage': coverage,
        'native_notice': {part: {arm: notice.score(groups[part], labels[part], {
            phase: {key: native[TASK] for key, native in rows.items()} for phase, rows in subset.items()
        }) for arm, subset in arms.items()} for part, arms in comparisons.items()},
        'fixed_DEV_cumulative': {phase: previous.employee.base.prior.full_scores(
            {arm: rows[phase] for arm, rows in comparisons['fixed_DEV'].items()}, dev, labels['fixed_DEV'],
        ) for phase in ('before', 'after')},
        'unresolved_original_TRAIN_positions': proposed_m1_cases,
        'unresolved_after_fit_cutoff': sum(pos[0] > 4 for pos in proposed_m1_cases),
        'reused_physical_reads': {part: len(values) for part, values in reads.items()},
        'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
