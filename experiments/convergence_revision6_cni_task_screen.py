"""Replay source selection for per-hypothesis B4 updates on bound B5 responses."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_archive_group_guard as previous
from experiments import convergence_revision6_cni_notice_roles as notices
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_task_screen as screen
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_task_screen'
POINTER = HANDOFF / f'{STAGE}_current.json'
scoped, CNI = previous.scoped, previous.CNI
parent = scoped.parent


def proof_for(source):
    proof = previous.proof_scopes(source)
    if witnesses := notices.missing_proofs(source):
        judgment = notices.roles.project({'answer': None, 'evidence_sentence_ids': []}, witnesses)
        if judgment['answer'] is not None:
            proof[notices.TASK] = judgment
    return proof


def fit_bank(programs, expected):
    root, study, roster = previous.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    fit, config, terminal = previous.bound_stage(parent.fit_pointer(4))
    observed, _, end = previous.bound_stage(parent.observe_pointer(4))
    folder = fit / 'candidates' / parent.ORDINARY / CNI
    decision = read(folder / 'decision.json')
    choices = read(fit / 'matched_decisions.json')
    past = read(folder / 'prior_TRAIN_regression.json')
    proposal = read(folder / 'measurements.json')
    if (digest(choices) != terminal['matched_decisions_sha256']
            or choices['teacher'][parent.ORDINARY][CNI] != decision or decision['selected'] != 'candidate'
            or digest(past) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or digest(proposal['predictions']) != decision['predictions_sha256']
            or proposal['candidate'] != programs[screen.PROPOSAL]
            or config['observations_terminal_sha256'] != sha(observed / 'terminal.json')
            or sha(fit / 'terminal.json') != expected['B4_fit_sha256']):
        raise ValueError('Require the original accepted ordinary update and its complete prefix')
    bank, context, ids = {}, {}, set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch, cohort in enumerate(roster[:4], 1):
            sources = [s for s in cohort if s['dataset'] == CNI and s['project_split'] == 'train']
            for position, source in enumerate(sources, 1):
                key = source['key']
                context[key] = {'source': source, 'position': [batch, position]}
                records = ((past['before'][key], past['candidate'][key]) if batch < 4 else
                           (previous.observed(journal, parent.ORDINARY, batch, key, end), proposal['predictions'][key]))
                bank[key] = {}
                for role, record in zip(parent.ROUTES, records, strict=True):
                    wire = parent.wire(source, programs[role], config['executor'])
                    ids.add(parent.archived(db, source, record, programs[role], wire))
                    bank[key][role] = record['native']
    if len(context) != 12 or len(ids) != 24 or digest(sorted(ids)) != expected['calibration_archive_sha256']:
        raise ValueError('Use every original prefix response under its exact wire')
    return bank, context, ids


def apply_proofs(source, native, proof):
    return previous.share(scoped.with_shared_proofs(source, native), proof)


def run():
    point = read(parent.POINTER)
    settled_b5 = ROOT / point['artifact_root']
    lock = read(settled_b5 / 'binding.json')
    prev = verify(read(settled_b5 / 'terminal.json'), 'terminal_sha256')
    prepared, programs, _, _, forward, wires, grade = parent.prepare_materials()
    keys = ('programs', 'B4_fit_sha256', 'calibration_archive_sha256', 'B5_wires_sha256', 'B5_proposal_calls_sha256')
    if (settled_b5.name != digest(lock) or prev['terminal_sha256'] != point['terminal_sha256']
            or any(prepared[key] != lock[key] for key in keys) or prev['TEST_opened']
            or 'train' not in grade.parts or sha(grade) != lock['grade_sha256']
            or sha(settled_b5 / 'sealed_predictions.json') != prev['predictions_sha256']):
        raise ValueError('Reuse the locked original B4-to-B5 exact request pair')
    raw, contexts, fit_ids = fit_bank(programs, lock)
    proofs = {key: proof_for(row['source']) for key, row in contexts.items()}
    fit_labels = {key: value for key, value in read(grade).items() if key in contexts}
    sources = {key: row['source'] for key, row in contexts.items()}
    shared = {key: {role: apply_proofs(sources[key], output, proofs[key]) for role, output in port.items()}
              for key, port in raw.items()}
    fit = previous.score_fit(sources, shared, fit_labels)
    groups = []
    for key, pair in raw.items():
        if not proofs[key]:
            continue
        before, candidate = (pair[role] for role in parent.ROUTES)
        groups.append({'position': contexts[key]['position'],
                       **previous.guard.compatibility(before, candidate, proofs[key]),
                       'disagreements': sorted(task for task in fit
                                               if before[task]['answer'] != candidate[task]['answer'])})
    choices = screen.select(groups, fit)
    routes = {name: value['programs'] for name, value in choices.items()}
    routes.update({screen.INCUMBENT: dict.fromkeys(fit, screen.INCUMBENT),
                   'whole_proposal': dict.fromkeys(fit, screen.PROPOSAL)})
    varied = sorted(task for task in fit if len({roles[task] for name, roles in routes.items()
                                               if name in choices}) > 1)
    files = (__file__, screen.__file__, previous.__file__, previous.guard.__file__, parent.__file__,
             scoped.__file__, notices.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'B4_fit': lock['B4_fit_sha256'],
        'B5_paired_execution_terminal': prev['terminal_sha256'], 'TEST_opened': False,
        'grade_sha256': sha(grade), 'prefix': sha(settled_b5 / 'binding.json'),
        'fit_positions': [row['position'] for row in contexts.values()], 'group_budget': 1,
        'fit_choices_sha256': digest({'groups': groups, 'native_prefix': fit, 'choices': choices}),
        'source_proofs_sha256': digest(proofs),
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    previous.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'fit_choices.json', {'groups': groups, 'native_prefix': fit, 'choices': choices})
    for name, route in routes.items():
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', sealed({
            'binding_sha256': out.name, 'fit_batch': 4, 'hypothesis_programs': {
                task: lock['programs'][role] for task, role in route.items()},
            'physical_screen_budget': choices.get(name, {}).get('physical_screen_budget', 0),
        }, 'snapshot_sha256'))

    existing, ledger = scoped.restore(settled_b5, forward, programs, wires)
    forward_ids = {info[1] for info in existing.values()} | {row['archived_choice'] for row in forward.values()}
    if (len(forward) != 3 or len(forward_ids) != 6 or fit_ids & forward_ids or set(ledger) - {'completed', 'failed'}):
        raise ValueError('Preserve the exact six distinct later TRAIN responses and no in-flight requests')
    public = {key: row['source'] for key, row in forward.items()}
    outputs = {}
    for key, row in forward.items():
        source = row['source']
        proof = proof_for(source)
        outputs[key] = {role: apply_proofs(source, native, proof) for role, native in
                        ((screen.INCUMBENT, existing[key][0]), (screen.PROPOSAL, row['proposal']))}
    predictions = {policy: {key: {task: options[role][task] for task, role in route.items()}
                            for key, options in outputs.items()} for policy, route in routes.items()}
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    labels = read(grade)
    performance = scoped.evaluate(public, predictions, labels)['all']
    per_case = {policy: [[row for row in scoped.native_rows(public[key], labels[key], native)
                          if row['view'] in varied] for key, native in bank.items()] for policy, bank in predictions.items()}
    changed_scope = {policy: [{k: v for k, v in case.items() if k != 'source'} for cells in rows for case in cells]
                     for policy, rows in per_case.items()}
    effects = performance['paired_candidate_driven']
    gain = all(effects[name]['correct']['mean_change'] >= 0
               and effects[name]['grounded']['paired_source_bootstrap_95'][0] > 0
               for name in (*screen.SCREENED[1:], 'native_per_hypothesis'))
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'policies': choices, 'hypotheses_with_different_adoption': varied, 'B5_TRAIN': performance,
        'B5_only_differing_hypotheses': changed_scope, 'supports_later_validation': gain,
        'reused_fit_requests': len(fit_ids), 'reused_forward_requests': len(forward_ids),
        'forward_requests_sha256': digest(sorted(forward_ids)), 'new_executor_requests': 0,
        'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
