"""Replay external-recipient permissions on original TRAIN and fixed DEV outputs."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_agreement_disclosure_release as release
from experiments import convergence_revision6_cni_b4_recipient_selection as acquisition
from experiments import convergence_revision6_maud_section_reference as fixed
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import cni_external_recipients as external
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_cni_external_recipients'
POINTER = HANDOFF / f'{STAGE}_current.json'
CNI, TASK = 'ContractNLI', 'nda-7'
archived = release.qualification.archived
ORDINARY = acquisition.ORDINARY


def view(source):
    return next(v for v in source['views'] if v['id'] == TASK)


def proof(source):
    return external.paths(acquisition.roles.employees.links.linked.span_inventory(view(source)))


class ExternalRecipientActor:
    """Apply the same source proof on every fixed DEV arm."""

    def __init__(self, parent, support):
        self.parent = parent
        self.support = support

    def __call__(self, source, library, purpose):
        original = self.parent(source, library, purpose)
        paths = self.support.get(source['key'])
        if not paths:
            return original
        native = original['native']
        return {**original, 'native': {**native, TASK: external.apply(native[TASK], paths)}}


def b3_pair(db, root, study, roster, coverage, spans):
    """Reconstruct all nine original B3 program pairs with identical input data."""
    stage, config, terminal = acquisition.roles.replay.bound.bound_stage(acquisition.fit_pointer(3))
    obs, _, observed = acquisition.roles.replay.bound.bound_stage(acquisition.observe_pointer(3))
    choices = read(stage / 'matched_decisions.json')
    journal = acquisition.TrainingJournal(root, study, roster)
    location = stage / 'candidates' / ORDINARY / CNI
    decision = choices['teacher'][ORDINARY][CNI]
    earlier, current = (read(location / name) for name in ('prior_TRAIN_regression.json', 'measurements.json'))
    programs = {name: journal.library(ORDINARY, n)['programs'][CNI]
                for name, n in (('incumbent', 2), ('proposal', 3))}
    if (terminal['matched_decisions_sha256'] != digest(choices) or decision['selected'] != 'candidate'
            or decision['predictions_sha256'] != digest(current['predictions'])
            or config['observations_terminal_sha256'] != sha(obs / 'terminal.json')
            or decision['earlier_TRAIN_regression']['evidence_sha256'] != digest(earlier)
            or current['candidate'] != programs['proposal']):
        raise ValueError('Require the original accepted B3 update and the exact archived fit bank')
    bank, source_index, verified = {}, {}, {}
    for batch, rows in enumerate(roster[:3], 1):
        for index, source in enumerate(s for s in rows if s['dataset'] == CNI):
            key = source['key']
            if source != coverage[key] or source['project_split'] != 'train':
                raise ValueError('Replay precisely the original chronological TRAIN prefix')
            source_index[key] = [batch, index]
            if batch < 3:
                a, b = earlier['before'][key], earlier['candidate'][key]
            else:
                record = read(journal.directory(ORDINARY, batch) / 'predictions' / f'{digest(key)}.json')
                seal = journal._observations(ORDINARY, batch)
                if (seal['train_observation_sha256'] != observed['observation_receipts'][ORDINARY]
                        or digest(record) != seal['predictions'][key]):
                    raise ValueError('Preserve the actual B3 incumbent observations')
                a, b = record['result'], current['predictions'][key]
            bank[key] = {}
            for name, result in (('incumbent', a), ('proposal', b)):
                program = programs[name]
                wire = acquisition.wire(source, program, config['executor'])
                verified[key, name] = acquisition.archived(db, source, result, program, wire)
                before = acquisition.common(source, result['native'])[TASK]
                bank[key][name] = {'original': result['native'][TASK], 'before': before,
                                   'after': external.apply(before, spans[key])}
    if (len(bank), len(set(verified.values()))) != (9, 18):
        raise ValueError('Keep all 18 original full model responses')
    return bank, source_index, set(verified.values()), sha(stage / 'terminal.json')


def score(sources, variants, labels):
    rows = [[{'source': key, 'view': TASK, **grade_view(CNI, view(sources[key]), labels[key][TASK],
                                                     row[phase]['answer'], row[phase]['evidence_sentence_ids'])}
             for key, row in variants.items()] for phase in ('before', 'after')]
    a, b = rows
    return {
        'correct': [sum(z['grade'] for z in side) for side in rows],
        'evidence_F1': [mean(z['evidence_f1'] for z in side) for side in rows],
        'paired_native': paired_source_effect(a, b),
        'classification_regressed': sum(x['grade'] > y['grade'] for x, y in zip(a, b, strict=True)),
        'evidence_regressed': sum(x['evidence_f1'] > y['evidence_f1'] for x, y in zip(a, b, strict=True)),
        'mothers': len(a),
    }


def run():
    root, original_study, roster = archived.archive_context()
    train, historical, train_grade, train_seals = archived.collect(root, original_study, roster, 'train')
    parent, cohort, originals, study, dev_receipt = fixed.base_actor()
    dev = {s['key']: s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'dev'}
    if (len(train), len(dev), len(originals)) != (24, 16, 5):
        raise ValueError('Use the complete original ContractNLI TRAIN and fixed DEV cohorts')
    support = {name: {key: proof(s) for key, s in bank.items()} for name, bank in (('train', train), ('dev', dev))}
    actor = ExternalRecipientActor(parent, support['dev'])
    banks = {'train': {}, 'dev': {}}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        b3, positions, fit_reads, b3_receipt = b3_pair(db, root, original_study, roster, train, support['train'])
        train_reads, dev_reads = {}, {}
        for arm, rows in historical.items():
            banks['train'][arm] = {}
            for key, source in train.items():
                result = rows[key]
                before = acquisition.common(source, result['native'])[TASK]
                after = external.apply(before, support['train'][key])
                if after != before:
                    archived.checked_result(db, source, result, train_reads)
                banks['train'][arm][key] = {'before': before, 'after': after}
        for arm, (folder, seal, cell) in originals.items():
            banks['dev'][arm] = {}
            library = {'arm': arm, 'batch': 8}
            for key, source in dev.items():
                before = parent(source, library, 'skill_dev')['native'][TASK]
                after = actor(source, library, 'skill_dev')['native'][TASK]
                if after != before:
                    saved = read(folder / 'predictions' / f'{digest(key)}.json')
                    if (digest(saved) != seal['predictions_sha256'][key] or saved['public_source_sha256'] != digest(source)
                            or saved['library_sha256'] != cell['libraries'][CNI]):
                        raise ValueError('Preserve the sealed fixed DEV input, library and predictions')
                    archived.checked_result(db, source, saved['result'], dev_reads, dev=True)
                banks['dev'][arm][key] = {'before': before, 'after': after}
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Use exact settled model outputs')
    dev_ref = study['grading_paths'][CNI]
    dev_grade = ROOT / dev_ref
    dev_hash = study['grading_file_sha256'][dev_ref]
    paths = (__file__, external.__file__, external.recipients.__file__, acquisition.__file__, fixed.__file__)
    binding = {'stage': STAGE, 'test_opened': False, 'fixed_DEV_terminal': dev_receipt,
               'training_observation_terminals': train_seals, 'B3_fit_terminal': b3_receipt,
               'B3_fit_wire_sha256': digest(sorted(fit_reads)), 'source_proofs_sha256': digest(support),
               'TRAIN_grade_sha256': sha(train_grade), 'DEV_grade_sha256': dev_hash,
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in paths},
               'fixed_DEV_analysis': 'exploratory source-linked repair on the previously viewed DEV cohort'}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', support)
    tag = immutable_json(out / 'sealed_predictions.json', {'banks': banks, 'B3': b3})
    if 'train' not in train_grade.parts or 'dev' not in dev_grade.parts or sha(dev_grade) != dev_hash:
        raise ValueError('Score only the original TRAIN and fixed DEV references after sealing')
    labels = {'train': read(train_grade), 'dev': read(dev_grade)}
    scores = {split: {arm: score(sources, bank, labels[split]) for arm, bank in banks[split].items()}
              for split, sources in (('train', train), ('dev', dev))}
    b3_scores = {arm: score(train, {key: row[arm] for key, row in b3.items()}, labels['train'])
                 for arm in ('incumbent', 'proposal')}
    cases = [key for key, row in support['train'].items() if row and key in b3]
    source_conflicts = sum(labels[split][key][TASK]['answer'] != 'Entailment'
                           for split, rows in support.items() for key, support in rows.items() if support)
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'native': scores, 'coverage': {name: [sum(map(bool, rows.values())), len(rows)] for name, rows in support.items()},
        'source_reference_conflicts': source_conflicts, 'B3': {'native': b3_scores, 'source_cases': [
            {'position': positions[key], 'old_proposal_and_entry': {arm: row['original']['answer']
                                                                  for arm, row in b3[key].items()},
             'after_source_rule': {arm: row['after']['answer'] for arm, row in b3[key].items()}}
            for key in cases]},
        'reused_requests': {'fit': len(fit_reads), 'train': len(train_reads), 'dev': len(dev_reads),
                            'distinct': len(set(train_reads) | set(dev_reads) | fit_reads)},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    write_status(out, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
