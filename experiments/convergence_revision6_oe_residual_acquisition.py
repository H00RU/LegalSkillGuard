"""Fit update decisions after the same public rules used for forward scoring."""

from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision6_oe_joint_acquisition as previous
from experiments import convergence_revision6_oe_port_acquisition as ports
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_residual_acquisition'
POINTER = HANDOFF / f'{STAGE}_current.json'
MODES = ('original_port_gate', 'after_controls_native_gate', 'after_controls_native_and_evidence')


def controlled_case(row):
    return {**row, 'answers': {program: previous.common(row['views'], answers, True)
                               for program, answers in row['answers'].items()}}


def fit_native_residuals(cases, labels):
    candidates = {key: {name: previous.joint.route(row['answers'], name) for name in previous.joint.ROUTES}
                  for key, row in cases.items()}
    native = previous.scored(cases, candidates, labels)
    totals = {name: mean(x['grade'] for x in rows) for name, rows in native.items()}
    changes = {name: score - totals['incumbent'] for name, score in totals.items()}
    return changes


def eligible_gains(changes):
    result = dict(changes)
    # A case can support switching both programs only when each single-port
    # replacement has a positive residual native score on the same TRAIN pool.
    if min(result['EC_only'], result['EV_only']) <= 0:
        result['whole_proposal'] = 0.0
    return result


def canonical_claim_order(bank):
    return {key: {name: {port: (None if answer is None else
                                {asset: sorted(claims, key=digest) for asset, claims in answer.items()})
                         for port, answer in native.items()}
                  for name, native in policies.items()} for key, policies in bank.items()}


def summaries(predictions, cases, labels):
    groups = {mode: previous.summary(cases, bank, labels) for mode, bank in predictions.items()}
    rows = {mode: previous.scored(cases, bank, labels) for mode, bank in predictions.items()}
    groups['same_policy_before_and_after_shared_rules'] = {
        mode: {policy: paired_source_effect(rows[MODES[0]][policy], units)
               for policy, units in rows[mode].items() if policy != 'incumbent'}
        for mode in MODES[1:]
    }
    return groups


def archives():
    pointer = read(ports.POINTER)
    root = ROOT / pointer['artifact_root']
    port_end = verify(read(root / 'terminal.json'), 'terminal_sha256')
    port_binding = read(root / 'binding.json')
    validated = ROOT / read(previous.VALIDATED_POINTER)['artifact_root']
    rules = verify(read(validated / 'terminal.json'), 'terminal_sha256')
    binding = read(validated / 'binding.json')
    assert root.name == digest(port_binding) == port_end['binding_sha256'] and not port_end['TEST_opened']
    assert validated.name == digest(binding) == rules['binding_sha256'] and not rules['TEST_opened']
    assert port_binding['prior_joint_acquisition'] == rules['terminal_sha256']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, _, ev, grade = previous.archive.history(db)
        ec = previous.extract(db, cases)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    assert digest(cases) == binding['paired_bank_sha256'] and not set(ev) & set(ec)
    assert digest(sorted(set(ev) | set(ec))) == binding['requests_sha256']
    assert rules['ledger'] == port_end['ledger'] and not ledger.get('reserved')
    assert all(ledger.get(status, 0) >= count for status, count in port_end['ledger'].items())
    grade_path, expected = grade
    grade = ROOT / grade_path
    assert 'train' in grade.parts and sha(grade) == expected == port_binding['grade_sha256']
    return cases, grade, port_end, binding, rules, ledger, root / 'sealed_predictions.json'


def run():
    cases, grade, port_end, previous_binding, rules, ledger, prior_predictions = archives()
    assert sha(prior_predictions) == port_end['predictions_sha256']
    previous_predictions = read(prior_predictions)['shared_category_and_amount_controls']
    labels = read(grade)
    batches, forward = {}, {}
    predictions = {m: {} for m in MODES}
    for batch, bank in cases.items():
        phase = str(batch)
        fit = rules['fit'][phase]
        controlled = {key: controlled_case(row) for key, row in bank['train'].items()}
        gains = fit_native_residuals(controlled, labels)
        eligibility = eligible_gains(gains)
        original_groups = {int(pos): r for pos, r in fit['group_evidence'].items()}
        groups = {row['position']: previous.group_evidence(row, True) for row in controlled.values()
                  if row['position'] in original_groups}
        assert groups.keys() == original_groups.keys()
        original_gate = previous.joint.select(original_groups, fit['TRAIN_shared_native_gate'], require_each_port=True)
        assert original_gate == port_end['fit'][phase]['choices']
        decisions = dict(zip(MODES, (original_gate,
            previous.joint.select(original_groups, eligibility, require_each_port=True),
            previous.joint.select(groups, eligibility, require_each_port=True)), strict=True))
        batches[batch] = {'native_gain_without_shared_rules': fit['TRAIN_shared_native_gate'],
                          'native_gain_with_shared_rules': gains, 'eligible_native_gain': eligibility,
                          'group_evidence_after_shared_rules': groups, 'choices': decisions,
                          'screening_requests_per_policy': fit['screening_requests_per_policy']}
        for key, row in bank['forward'].items():
            assert key not in forward
            forward[key] = row
            controls = controlled_case(row)['answers']
            for name, picks in decisions.items():
                predictions[name][key] = {'incumbent': previous.joint.route(controls, 'incumbent'), **{
                    policy: previous.joint.route(controls, info['route']) for policy, info in picks.items()}}
    if canonical_claim_order(predictions[MODES[0]]) != canonical_claim_order(previous_predictions) or len(forward) != 16:
        raise ValueError('The reproduced original gate must preserve all measured claims and the forward denominator')
    predictions[MODES[0]] = previous_predictions
    paths = (__file__, previous.__file__, previous.joint.__file__, ports.__file__, previous.coverage.__file__,
             previous.ec.__file__, previous.category.__file__, previous.pa_items.__file__,
             previous.convergence_oe_illinois_amount.__file__, previous.convergence_oe_pa_monetary.__file__)
    binding = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False,
               'prior_port_gate_terminal': port_end['terminal_sha256'], 'prior_validated_terminal': rules['terminal_sha256'],
               'same_ARCHIVE_sha256': previous_binding['paired_bank_sha256'],
               'physical_requests_sha256': previous_binding['requests_sha256'],
               'TRAIN_grade_sha256': sha(grade), 'matched_batches': list(cases),
               'forward_rule': 'Use the same locked current public rules on each partition, with no forward labels '
                               'or observations used to choose an update.',
               'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths}}
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    for batch, row in batches.items():
        for mode, choices in row['choices'].items():
            for policy, info in choices.items():
                programs = cases[batch]['programs']
                assignment = {t: programs[p] for t, p in zip(previous.PORTS, previous.joint.ROUTES[info['route']], strict=True)}
                library = sealed({'fit_batch': batch, 'choice': info, 'programs': assignment,
                                  'binding_sha256': out.name}, 'snapshot_sha256')
                immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}' / mode / f'{policy}.json', library)
    pred_sha = immutable_json(out / 'sealed_predictions.json', predictions)
    total = summaries(predictions, forward, labels)
    per_batch = {batch: summaries({mode: {k: b[k] for k in sample['forward']} for mode, b in predictions.items()},
                                  sample['forward'], labels) for batch, sample in cases.items()}
    result = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred_sha,
                     'fit': batches, 'all_forward_TRAIN': total, 'forward_TRAIN': per_batch, 'forward_mothers': len(forward),
                     'original_requests_verified': rules['old_physical_requests_verified'],
                     'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger},
                    'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
