"""Compare four acquisition policies on all archived matched OpenExempt transitions."""

import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision6_candidate_archive_coverage as exact
from experiments import convergence_revision6_candidate_asset_binding as assets
from experiments import convergence_revision6_oe_joint_item_cap as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_bound_acquisition as acquisition
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_oe_forward_acquisition'
POINTER = HANDOFF / 'revision6_oe_forward_acquisition_current.json'
OE = exact.formal.OE
formal = exact.formal
PROGRAMS = ('incumbent', 'proposal')
RANKS = acquisition.POLICIES


def read_matched(db, source, results, programs):
    view = assets.dev_archive.ev_view(source)
    raw = {}
    ids, inputs = [], []
    for role, result, version in zip(PROGRAMS, results, programs, strict=True):
        identity, native = exact.verified_ev(db, source, view, result, version)
        ids.append(identity)
        fact, = db.execute('select result from calls where id=?', (identity,)).fetchone()
        payload = read(Path(json.loads(fact)['artifact_directory']) / 'request.json')['payload']
        inputs.append({**payload, 'messages': [row for row in payload['messages'] if row['role'] == 'user']})
        raw[role] = assets.scopes(view, native)['same_public_jurisdiction']
    if len(set(ids)) != 2 or inputs[0] != inputs[1]:
        raise ValueError('Both programs must see the same physical public source and transport')
    return {'view': view, 'answers': raw, 'wires_sha256': digest(inputs[0])}, ids


def raw_prediction(journal, arm, batch, key):
    row = read(journal.directory(arm, batch) / 'predictions' / (digest(key) + '.json'))
    if digest(row) != journal._observations(arm, batch)['predictions'][key] or row['source'] != key:
        raise ValueError('The original training observation lost its prediction seal')
    return row['result']


def history(db):
    rows, skipped, identities, grade_refs = {}, {}, {}, set()
    for batch in range(2, 8):
        fit, spec, terminal = prior.archive.bound_stage(formal.pointer(batch))
        decisions = read(fit / 'matched_decisions.json')
        directory = fit / 'candidates' / formal.ORDINARY / OE
        proposal = read(directory / 'measurements.json')
        gate = decisions['teacher'][formal.ORDINARY][OE]
        if (digest(decisions) != terminal['matched_decisions_sha256']
                or digest(proposal['candidate']) != decisions['relation'][OE]['matched_proposal_sha256']
                or digest(proposal['predictions']) != gate['predictions_sha256'] or terminal['batch'] != batch):
            raise ValueError('Require the original native TRAIN fit and its actual proposal')
        root = ROOT / spec['checkpoint_root']
        study = read(root / 'binding.json')
        roster = formal.load_roster(study)
        journal = exact.TrainingJournal(root, study, roster)
        program = journal.library(formal.M2, batch - 1)['programs'][OE]
        programs = [digest(program), digest(proposal['candidate'])]
        carriers = {}
        for arm in ConvergenceEvaluation.arms:
            library = journal.library(arm, batch)
            if library.get('schema_proposals', {}).get(OE) is None:
                carriers.setdefault(digest(library['programs'][OE]), arm)
        if len(set(programs)) != 2 or not set(programs) <= carriers.keys():
            skipped[batch] = 'no_matched_exact_next_batch_reader'
            continue
        grade_refs.add(assets.grades_ref(read(ROOT / spec['observations_root'] / 'binding.json')))
        train, forward = {}, {}
        for later, bank in ((False, train), (True, forward)):
            number = batch + int(later)
            cohort = [source for source in roster[number - 1] if source['dataset'] == OE]
            if len(cohort) != 4 or any(s['project_split'] != 'train' for s in cohort):
                raise ValueError('Compare complete four-source original TRAIN batches')
            for slot, source in enumerate(cohort):
                key = source['key']
                if later:
                    measurements = [raw_prediction(journal, carriers[v], number, key) for v in programs]
                else:
                    lead = raw_prediction(journal, formal.M2, number, key)
                    measurements = [lead, proposal['predictions'][key]]
                evidence, physical = read_matched(db, source, measurements, programs)
                for identity, version in zip(physical, programs, strict=True):
                    if identities.setdefault(identity, (key, version)) != (key, version):
                        raise ValueError('A settled request may only be reused under the same source and program')
                bank[key] = {**evidence, 'position': slot}
        rows[batch] = {'train': train, 'forward': forward, 'programs': dict(zip(PROGRAMS, programs, strict=True)),
                       'original_fit_sha256': sha(fit / 'terminal.json')}
    grade, = grade_refs
    if not rows:
        raise ValueError('At least one matched archival transition is required')
    return rows, skipped, identities, grade


def fit_policy(bank, labels):
    groups, grades = {}, {role: [] for role in PROGRAMS}
    for key, row in bank.items():
        values, item_cap = acquisition.public_bounds(row['view'])
        if values and all(row['answers'][role] is not None for role in PROGRAMS):
            groups[row['position']] = acquisition.evidence(*[row['answers'][role] for role in PROGRAMS],
                                                           values, item_cap)
        for role in PROGRAMS:
            prediction = row['answers'][role]
            grades[role].append(native_grade(row['view'], labels[key]['EV'], prediction))
    gain = mean(grades['proposal']) - mean(grades['incumbent']) if groups else 0
    return groups, gain, acquisition.select(groups, gain)


def score(predictions, cases, labels):
    by_role = {role: [] for role in (*PROGRAMS, *RANKS)}
    for key, board in predictions.items():
        for role, answer in board.items():
            native = native_grade(cases[key]['view'], labels[key]['EV'], answer)
            by_role[role].append({'source': key, 'view': 'EV', 'grade': native})
    return {'F1': {role: mean(row['grade'] for row in cells) for role, cells in by_role.items()},
            'paired_candidate_driven': {role: paired_source_effect(by_role[role], by_role['candidate_driven'])
                                       for role in ('incumbent', *RANKS[:-1])}}


def native_grade(view, label, answer):
    if answer is None:
        return 0.0
    value = grade_view(OE, view, label, answer)['grade']
    if value is None:
        raise ValueError('Use the official EV grader for handled native responses')
    return value


def run():
    parent = ROOT / read(prior.POINTER)['artifact_root']
    current = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    if current['TEST_opened'] or current['terminal_sha256'] != read(prior.POINTER)['terminal_sha256']:
        raise ValueError('Keep the latest five-library release binding')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        archive, excluded, physical, grade = history(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    name, expected = grade
    path = ROOT / name
    if ledger.get('reserved') or 'train' not in path.parts or sha(path) != expected:
        raise ValueError('Only original TRAIN grades and settled physical responses are eligible')
    binding = {
        'stage': 'revision6_oe_forward_acquisition', 'prior_DEV': current['terminal_sha256'],
        'fit_and_forward_sha256': digest(archive), 'matched_batches': list(archive),
        'excluded': excluded, 'requests_sha256': digest(sorted(physical)), 'native_grades_sha256': expected,
        'TEST_opened': False, 'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, acquisition.__file__, exact.__file__, assets.__file__,
        )},
    }
    root = HOME / digest(binding)
    immutable_json(root / 'binding.json', binding)
    for filename, tag in binding['source_sha256'].items():
        dst = root / 'source_snapshot' / filename
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            with dst.open('xb') as handle:
                handle.write((ROOT / filename).read_bytes())
        if sha(dst) != tag:
            raise ValueError('Preserve the exact acquisition policy and receipt')
    labels = read(path)
    fit, cases = {}, {}
    predictions = {'matched': {}, 'shared_bound_control': {}}
    for batch, record in archive.items():
        groups, gain, choices = fit_policy(record['train'], labels)
        fit[batch] = {'groups': groups, 'native_EV_gain': gain, 'choices': choices,
                      'screened_EV_calls_per_policy': 2}
        for role, choice in choices.items():
            library = sealed({'fit_batch': batch, 'binding_sha256': root.name,
                              'program_sha256': record['programs'][choice['decision']], **choice}, 'snapshot_sha256')
            immutable_json(root / 'TRAIN_batch_libraries' / f'B{batch}' / f'{role}.json', library)
        for key, row in record['forward'].items():
            if key in cases:
                raise ValueError('Do not count the same source twice in the next-batch comparison')
            cases[key] = row
            raw = {**row['answers'], **{role: row['answers'][choice['decision']] for role, choice in choices.items()}}
            values, cap = acquisition.public_bounds(row['view'])
            predictions['matched'][key] = raw
            predictions['shared_bound_control'][key] = {
                role: acquisition.remove_violations(answer, values, cap) for role, answer in raw.items()}
    p = immutable_json(root / 'sealed_predictions.json', predictions)
    if sha(path) != expected:
        raise ValueError('Forward scoring must use the pinned TRAIN reference')
    by_batch = {batch: {mode: score({key:bank[key] for key in record['forward']}, cases, labels)
                        for mode, bank in predictions.items()} for batch, record in archive.items()}
    cumulative = {mode: score(bank, cases, labels) for mode, bank in predictions.items()}
    terminal = sealed({'status': 'settled_revision6_oe_forward_acquisition', 'binding_sha256': root.name,
                       'fit': fit, 'forward_TRAIN': by_batch, 'all_forward_TRAIN': cumulative,
                       'forward_mothers': len(cases), 'matched_EV_read_uses': len(archive) * 16,
                       'old_physical_requests_verified': len(physical),
                       'unhandled_main_path': {
                           segment: {role: sum(row['answers'][role] is None for section in archive.values()
                                               for row in section[segment].values()) for role in PROGRAMS}
                           for segment in ('train', 'forward')},
                       'same_information_and_budget': True, 'predictions_sha256': p,
                       'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False,
                       'ledger': ledger}, 'terminal_sha256')
    immutable_json(root / 'terminal.json', terminal)
    write_status(root, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(root)


if __name__ == '__main__':
    run()
