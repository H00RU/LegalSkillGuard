"""Compare B5 group ranks with the same source, screening budget and evidence."""

from pathlib import Path
import sqlite3

from experiments import convergence_revision6_cni_development_release as development
from experiments import convergence_revision6_recipient_acquisition as acquisition
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_development_definition as definitions
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_cni_b5_disagreement'
POINTER = HANDOFF / 'revision6_cni_b5_disagreement_current.json'
CNI, TASK = development.CNI, development.TASK
transfer = development.transfer
selection = transfer.selection


def disagreement(pool):
    """Screen one group with the greatest number of differing native answers."""
    return max(pool, key=lambda row: (sum(a != b for a, b in zip(
        row['before'], row['after'], strict=True)), row['position']))


def training(db):
    batch, arm = 5, transfer.EXTERNAL
    fit, spec, terminal = transfer.bound.bound_stage(acquisition.pointer(batch))
    checkpoint = ROOT / spec['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    roster = selection.retention.load_roster(study)
    journal = transfer.TrainingJournal(checkpoint, study, roster)
    directory = fit / 'candidates' / arm / CNI
    decisions = read(fit / 'matched_decisions.json')
    decision = decisions['teacher'][arm][CNI]
    measured = read(directory / 'measurements.json')
    prior = read(directory / 'prior_TRAIN_regression.json')
    before, after = (journal.library(arm, n) for n in (batch - 1, batch))
    old_reader, new_reader = (lib.get('schema_proposals', {}).get(CNI) for lib in (before, after))
    program = before['programs'][CNI]
    if (terminal['batch'] != batch or digest(decisions) != terminal['matched_decisions_sha256']
            or decision['selected'] != 'candidate' or measured['candidate'] != new_reader
            or program != after['programs'][CNI] or digest(measured['predictions']) != decision['predictions_sha256']
            or digest(prior) != decision['earlier_TRAIN_regression']['evidence_sha256']):
        raise ValueError('Use the original two readers and unchanged B5 acquisition')
    original = journal._observations(arm, batch)
    sources = {s['key']: s for rows in roster[:batch] for s in rows if s['dataset'] == CNI}
    pool = []
    for key, (position, view, audit) in selection.retention.source_material(roster).items():
        if key not in sources:
            continue
        source = sources[key]
        if position[0] == batch:
            row = read(journal.directory(arm, batch) / 'predictions' / (digest(key) + '.json'))
            if digest(row) != original['predictions'][key]:
                raise ValueError('The original B5 entering response changed')
            a, b = row['result'], measured['predictions'][key]
        else:
            a, b = prior['before'][key], prior['candidate'][key]
        left, _, left_wire = acquisition.train_response(db, source, a, old_reader, program)
        right, _, right_wire = acquisition.train_response(db, source, b, new_reader, program)
        if left == right or left_wire != right_wire:
            raise ValueError('Both readers must have distinct matched reads of the same source')
        facts, shared, independent = selection.retention.local_pair(key, (position, audit), view)
        pool.append({'position': position, 'before': [a['native'][t]['answer'] for t in selection.retention.TASKS],
                     'after': [b['native'][t]['answer'] for t in selection.retention.TASKS],
                     'facts': list(facts.values()), 'shared': shared, 'independent': independent,
                     'request_ids': [left, right]})
    return pool, sha(fit / 'terminal.json')


def definition_proof(source):
    view = development.view_of(source)
    return definitions.proof(development.spans_for(view), view['public']['source_text'])


def native_effect(banks, cases, labels, reference, method):
    left, right = (development.grade(banks[role], cases, labels) for role in (reference, method))
    summary = development.agreement.comparison(left, right)
    evidence = paired_source_effect(*[[{**row, 'grade': row['grade'] * row['evidence_f1']} for row in cells]
                                     for cells in (left, right)])
    return {**summary, 'correct_class_evidence_F1_effect': evidence}


def run():
    prior, prior_binding, prior_terminal = development.agreement.bound_result(development)
    bank = read(prior / 'sealed_predictions.json')
    original, original_spec, original_terminal = development.agreement.bound_result(transfer)
    if prior_binding['archived_B5_terminal'] != original_terminal['terminal_sha256']:
        raise ValueError('The public rule must use precisely the original two B5 readers')
    fit = ROOT / read(selection.POINTER)['artifact_root']
    fitted = verify(read(fit / 'terminal.json'), 'terminal_sha256')
    if fit.name != digest(read(fit / 'binding.json')) or fitted['TEST_opened']:
        raise ValueError('Bind the original five source groups and selection receipt')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        pool, training_fit = training(db)
        ids = {request for row in pool for request in row['request_ids']}
        if len(pool) != fitted['source_group_pool'] or len(ids) != fitted['verified_archived_reads']:
            raise ValueError('The strong control must use the same measured TRAIN pool')
        choices = {**selection.choose(pool), 'answer_disagreement': disagreement(pool)}
        decisions = {role: selection.select(row) for role, row in choices.items()}
        for role in transfer.POLICIES:
            inherited = fitted['choices'][role]
            if digest(decisions[role]) != digest(inherited):
                raise ValueError('Both original selections must reproduce')
        readers = {role: verify(read(fit / 'TRAIN_batch_libraries' / f'{role}.json'), 'snapshot_sha256')
                   for role in transfer.POLICIES}
        if any(fitted['library_sha256'][role] != row['snapshot_sha256'] for role, row in readers.items()):
            raise ValueError('Only the fitted versions may be reused')
        policies = {v['decision']['decision']: k for k, v in readers.items()}
        route = policies[decisions['answer_disagreement']['decision']]
        cases, native, grade, _, count, wire_hash = transfer.materials(db, readers)
        if digest(native) != digest(read(original / 'sealed_predictions.json')) or (
                original_spec['matched_public_and_executor_sha256'] != wire_hash):
            raise ValueError('Keep the archived native fixed DEV and matched wire')
        train, train_original, train_grade, archive = development.ARCHIVE.collect(
            *development.ARCHIVE.archive_context(), 'train')
        train_proofs = {key: result for key, source in train.items() if (result := definition_proof(source))}
        dev_proofs = {key: result for key, source in cases.items() if (result := definition_proof(source))}
        train_calls = {}
        for records in train_original.values():
            for key in train_proofs:
                development.ARCHIVE.checked_result(db, train[key], records[key], train_calls)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or not train_proofs or any(
            len(v['after']) != len(cases) for grp in bank.values() for v in grp.values()):
        raise ValueError('Require complete original cohorts and settled physical requests')
    public_proofs = {'TRAIN': train_proofs, 'DEV': dev_proofs}
    names = (__file__, definitions.__file__, development.__file__, selection.__file__, acquisition.__file__)
    binding = {'stage': 'revision6_cni_b5_disagreement', 'TRAIN_fit_terminal': training_fit,
               'TRAIN_selection': fitted['terminal_sha256'], 'TRAIN_pool_sha256': digest(pool),
               'TRAIN_read_ids_sha256': digest(sorted(ids)), 'TRAIN_archives': archive,
               'TRAIN_grade_sha256': sha(train_grade), 'DEV_grade_sha256': grade[1],
               'DEV_archive_terminal': original_terminal['terminal_sha256'], 'DEV_matched_wire_sha256': wire_hash,
               'prior_development_terminal': prior_terminal['terminal_sha256'], 'TEST_opened': False,
               'source_proofs_sha256': digest(public_proofs),
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in names}}
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    for name, tag in binding['source_sha256'].items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(path) != tag:
            raise ValueError('Preserve the scope and comparison implementation')
    fixed = {arm: row['after'] for arm, row in bank['fixed_B8'].items()}
    b5 = {p: row['after'] for p, row in bank['archived_B5'].items()}
    b5['answer_disagreement'] = b5[route]
    patched = {set_name: {arm: {key: development.apply(value, dev_proofs.get(key))
               for key, value in rows.items()} for arm, rows in records.items()}
               for set_name, records in (('fixed', fixed), ('B5', b5))}
    predictions_hash = immutable_json(out / 'sealed_predictions.json', patched)
    immutable_json(out / 'source_proofs.json', public_proofs)
    grade_path = ROOT / grade[0]
    if 'dev' not in grade_path.parts or sha(grade_path) != grade[1] or 'train' not in train_grade.parts:
        raise ValueError('Use only bound TRAIN/DEV references after predictions are sealed')
    train_labels, labels = read(train_grade), read(grade_path)
    if any(train_labels[key][TASK]['answer'] != proof['answer'] for key, proof in train_proofs.items()):
        raise ValueError('The definition scope conflicts with an original TRAIN reference')
    base_all = transfer.score(cases, native, labels)
    fixed_effects = {arm: native_effect({'before': fixed[arm], 'after': rows}, cases, labels, 'before', 'after')
                     for arm, rows in patched['fixed'].items()}
    comparisons = {phase: {control: native_effect(rows, cases, labels, control, 'candidate_driven')
                   for control in ('chronological', 'answer_disagreement')}
                   for phase, rows in (('prior_common_rule', b5), ('with_definition_scope', patched['B5']))}
    terminal = sealed({'status': 'settled_revision6_cni_b5_disagreement', 'binding_sha256': out.name,
                       'TRAIN_group_budget_per_policy': 1, 'TRAIN_selection_reads_per_policy': 2,
                       'TRAIN_archived_selection_reads': len(ids), 'TRAIN_verified_definition_reads': len(train_calls),
                       'TRAIN_group_choices': decisions, 'disagreement_reader': route,
                       'DEV_archived_B5_reads': count, 'DEV_mothers': len(cases),
                       'DEFINITION_source_scope': {key: len(cells) for key, cells in public_proofs.items()},
                       'fixed_B8_definition_effect': fixed_effects,
                       'B5_independent_native_effects': comparisons,
                       'B5_all_native_before_common_rules': {**base_all['all_hypotheses'],
                           'answer_disagreement_identical_to': route},
                       'predictions_sha256': predictions_hash, 'ledger': ledger, 'TEST_opened': False,
                       'new_executor_requests': 0, 'new_teacher_requests': 0}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
