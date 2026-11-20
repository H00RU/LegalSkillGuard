"""Test whether the B7 EV proposal transfers the benchmark's per-item cap."""

from collections import Counter
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_oe_assertion_coverage as archive
from experiments import convergence_revision6_cni_development_release as release
from experiments import convergence_revision6_illinois_pair_amounts as prior_ev
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_federal_item_cap as local
from legal_skill_guard.paired_interfaces import convergence_oe_illinois_amount as illinois
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_oe_joint_item_cap'
POINTER = HANDOFF / 'revision6_oe_joint_item_cap_current.json'
OE = 'OpenExempt'
ROLES = archive.CHOICES


def combined_reference(facts, law):
    return local.expected(facts, law['mode'])


def pick_convention(board, facts, labels):
    """Fit an EV benchmark convention on B7 original labels."""
    domain = set(local.MODES)
    counts = Counter()
    for key in board:
        for asset, public in facts[key].items():
            options = {mode: local.expected(public, mode) for mode in local.MODES}
            if len(set(options.values())) == 1:
                continue
            original = set(local.observed(labels[key]['EV']['answer'], asset))
            counts['discriminating_positions'] += 1
            for mode, value in options.items():
                counts[mode + '_matches'] += original == {value}
            domain.intersection_update(mode for mode, value in options.items() if original == {value})
    if len(domain) != 1:
        raise ValueError('B7 original native training examples do not uniquely bind the cap convention')
    mode, = domain
    return mode, dict(counts)


def group_receipt(key, facts, before, candidate, mode):
    # Only high-value, title-bound assets can distinguish a missing cap.
    # Keep the observed omissions and explicit conflicts separate.
    assets = {name: fact for name, fact in facts.items() if fact['value'] > local.expected(fact, mode)}
    information = {'positions': len(assets), 'candidate_repairs': 0, 'candidate_conflicts': 0,
                   'incumbent_conflicts': 0, 'answer_disagreement': 0}
    if not assets:
        return information
    law = digest([local.CITATION, mode])
    theory = Theory({law: [{'mode': mode}]}, {key: [{}]}, combined_reference, sha(Path(__file__)),
                    provenance=({'kind': 'explicit_source', 'evidence_sha256': digest(assets)},))
    cases = [SourceCase(key + ':' + digest(name), key, law, {}, fact)
             for name, fact in assets.items()]
    shared = allowed_relation(theory, cases)
    expected = [local.expected(fact, mode) for fact in assets.values()]
    if list(shared['signatures'].values()) != [expected]:
        raise ValueError('The fixed TRAIN convention must have one output vector')
    for name, ceiling in zip(assets, expected, strict=True):
        a, b = (set(local.observed(bank, name)) for bank in (before, candidate))
        # Inputs with incompatible amounts for one claim do not establish a scalar.
        va, vb = (next(iter(values)) if len(values) == 1 else None for values in (a, b))
        information['candidate_repairs'] += va is not None and va > ceiling and vb == ceiling
        information['incumbent_conflicts'] += va is not None and va > ceiling
        information['candidate_conflicts'] += vb is not None and vb > ceiling
        information['answer_disagreement'] += a != b
    for bank in (before, candidate):
        measured = [set(local.observed(bank, name)) for name in assets]
        scalar = [next(iter(row)) if len(row) == 1 else None for row in measured]
        # Each reference vector gives upper bounds. Missing claims stay unknown.
        shared_pass = any(
            all(v is None or v <= cap for v, cap in zip(scalar, limits, strict=True))
            for limits in shared['signatures'].values())
        direct_pass = all(v is None or v <= cap for v, cap in zip(scalar, expected, strict=True))
        if shared_pass != direct_pass:
            raise ValueError('Shared screening and the exact-information upper-bound check must agree')
    return information


def select(groups, mode):
    eligible = {i: rows for i, rows in groups.items() if rows['positions']}
    if not eligible:
        return {'position': None, 'decision': 'incumbent'}
    if mode == 'candidate_driven':
        i = max(eligible, key=lambda j: (eligible[j]['candidate_repairs'],
                                         -eligible[j]['candidate_conflicts'], j))
    elif mode == 'answer_disagreement':
        i = max(eligible, key=lambda j: (eligible[j]['answer_disagreement'], j))
    else:
        i = max(eligible)
    chosen = eligible[i]
    decision = 'proposal' if chosen['candidate_repairs'] and not chosen['candidate_conflicts'] else 'incumbent'
    return {'position': i, 'decision': decision}


def bank_for(batch):
    return {arm: {key: prior_ev.property_rules.ev.scopes(views['EV'], batch['raw'][arm][key]['EV'])[
                        'same_public_jurisdiction'] for key, views in batch['original_views'].items()}
            for arm in ROLES}


def run():
    previous_pointer = HANDOFF / 'revision6_indexed_evidence_control_current.json'
    previous = ROOT / read(previous_pointer)['artifact_root']
    prior = verify(read(previous / 'terminal.json'), 'terminal_sha256')
    if prior['TEST_opened'] or prior['terminal_sha256'] != read(previous_pointer)['terminal_sha256']:
        raise ValueError('Keep the current cumulative development result')
    base_actor, cohort, originals, study, _ = release.baseline.base_actor()
    dev_sources = {s['key']: s for s in cohort if s['dataset'] == OE and s['project_split'] == 'dev'}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        bank, refs, programs, source_calls, train_grade = archive.archived_pairs(db)
        account = dict(db.execute('select status,count(*) from calls group by status'))
    if account.get('reserved') or len(dev_sources) != 16:
        raise ValueError('Preserve the original native cohort and settled physical ledger')
    if 'train' not in train_grade.parts:
        raise ValueError('Fit the benchmark convention on TRAIN only')
    views = {b: {key: vv['EV'] for key, vv in info['original_views'].items()} for b, info in bank.items()}
    facts = {batch: {key: local.scope(view) for key, view in source.items()} for batch, source in views.items()}
    labels = read(train_grade)
    mode, calibration = pick_convention(views[7], facts[7], labels)
    before = bank_for(bank[7])
    groups = {i: group_receipt(key, facts[7][key], before['incumbent'][key], before['proposal'][key], mode)
              for i, key in enumerate(views[7])}
    choices = {p: select(groups, p) for p in ('chronological', 'answer_disagreement', 'candidate_driven')}
    fixed = {}
    dev_facts = {k: local.scope(prior_ev.wire.ev_view(s)) for k, s in dev_sources.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        known = set()
        for arm, (folder, seal, cell) in originals.items():
            fixed[arm] = {}
            for key, source in dev_sources.items():
                ev = prior_ev.wire.ev_view(source)
                original = base_actor(source, {'arm': arm, 'batch': 8}, 'skill_dev')['native']['EV']['answer']
                inherited = illinois.apply(original, illinois.source_amounts(ev))
                corrected = local.clip(inherited, dev_facts[key], mode)
                fixed[arm][key] = {'before': inherited, 'after': corrected}
                if corrected == inherited:
                    continue
                record = read(folder / 'predictions' / (digest(key) + '.json'))
                if (digest(record) != seal['predictions_sha256'][key] or record['public_source_sha256'] != digest(source)
                        or record['library_sha256'] != cell['libraries'][OE]):
                    raise ValueError('Preserve each original developer cohort prediction and reader')
                prior_ev.wire.read_ev(db, source, record, known, 'dev')
        if account != dict(db.execute('select status,count(*) from calls group by status')):
            raise ValueError('This experiment reuses archived physical responses')
    forward = bank_for(bank[8])
    b8 = {key: {**{a: forward[a][key] for a in ROLES},
                **{policy: forward[choice['decision']][key] for policy, choice in choices.items()},
                'same_information_direct': local.clip(forward['incumbent'][key], facts[8][key], mode)}
          for key in views[8]}
    grade = ROOT / study['grading_paths'][OE]
    expected_grade = study['grading_file_sha256'][study['grading_paths'][OE]]
    binding = {
        'stage': 'revision6_oe_joint_item_cap', 'prior_B8_DEV': prior['terminal_sha256'],
        'B7_forward_programs': programs, 'B7_B8_native_archives': refs, 'cap_convention': mode,
        'B7_calibration_sha256': digest(calibration), 'source_facts_sha256': digest({'TRAIN': facts, 'DEV': dev_facts}),
        'train_grade_sha256': sha(train_grade), 'dev_grade_sha256': expected_grade, 'TEST_opened': False,
        'source_sha256': {str(Path(name).relative_to(ROOT)): sha(Path(name)) for name in (
            __file__, local.__file__, archive.__file__, prior_ev.__file__,
        )},
    }
    root = HOME / digest(binding)
    immutable_json(root / 'binding.json', binding)
    for name, expected in binding['source_sha256'].items():
        target = root / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as handle:
                handle.write((ROOT / name).read_bytes())
        if sha(target) != expected:
            raise ValueError('Keep the exact cap and group selection implementation')
    for policy, choice in choices.items():
        library = sealed({**choice, 'program_sha256': programs[choice['decision']], 'scope': local.CITATION,
                          'B7_group_receipt_sha256': digest(groups), 'fit_binding': root.name}, 'snapshot_sha256')
        immutable_json(root / 'TRAIN_batch_libraries' / f'{policy}.json', library)
    checksum = immutable_json(root / 'sealed_predictions.json', {'forward_TRAIN': b8, 'fixed_DEV': fixed})
    immutable_json(root / 'source_facts.json', {'TRAIN': facts, 'DEV': dev_facts})
    if 'dev' not in grade.parts or sha(grade) != expected_grade:
        raise ValueError('Use fixed DEV labels only after sealing predictions')
    ref = read(grade)
    native = {arm: prior_ev.score(dev_sources, rows, ref, 'before', 'after') for arm, rows in fixed.items()}
    forward_sources = {key: {'views': [ev]} for key, ev in views[8].items()}
    training = {policy: prior_ev.score(forward_sources, b8, labels, 'incumbent', policy)
                for policy in (*ROLES[1:], *choices, 'same_information_direct')}
    holdout = {i: group_receipt(key, facts[8][key], forward['incumbent'][key], forward['proposal'][key], mode)
               for i, key in enumerate(views[8])}
    check = {}
    for split, facts_by_source, targets in (('B8_forward', facts[8], labels), ('DEV', dev_facts, ref)):
        cells = [(key, name, local.expected(value, mode)) for key, fs in facts_by_source.items()
                 for name, value in fs.items() if value['value'] > local.expected(value, mode)]
        check[split] = {'scoped_mothers': len({key for key, _, _ in cells}), 'scoped_assets': len(cells),
                        'matches': sum(set(local.observed(targets[key]['EV']['answer'], name)) == {value}
                                       for key, name, value in cells)}
    terminal = sealed({'status': 'settled_revision6_oe_joint_item_cap', 'binding_sha256': root.name,
                       'TRAIN_convention': mode, 'B7_calibration': calibration, 'B7_groups': groups,
                       'B7_selection': choices, 'same_information_screening_agrees': True,
                       'B7_comparison_EV_reads_per_policy': 2,
                       'B8_group_transfer': holdout, 'B8_native_forward': training,
                       'scope_reference_checks': check, 'fixed_B8_DEV': native,
                       'archived_reads': {'TRAIN': source_calls, 'DEV': len(known)},
                       'predictions_sha256': checksum, 'new_executor_requests': 0,
                       'new_teacher_requests': 0, 'ledger': account, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(root / 'terminal.json', terminal)
    write_status(root, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(root)


if __name__ == '__main__':
    run()
