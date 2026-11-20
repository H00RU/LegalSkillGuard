"""Compare common asset-category proofs on the archived TRAIN and fixed DEV readers."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_oe_arizona_household as arizona
from experiments import convergence_revision6_oe_competing_port as competing
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_oe_residual_acquisition import canonical_claim_order
from legal_skill_guard.paired_interfaces import convergence_oe_item_category as categories
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_item_categories'
POINTER = HANDOFF / f'{STAGE}_current.json'
previous, prior = arizona.previous, competing.prior
archive, portfolio = competing.archive, competing.portfolio
PORTS = portfolio.PORTS


def project(native, proof):
    return {task: categories.apply(task, native[task], proof[task]) for task in PORTS}


def verify_proofs(proofs, labels):
    counts = {'positive': dict.fromkeys(PORTS, 0), 'excluded': dict.fromkeys(PORTS, 0), 'disagreements': []}
    for key, views in proofs.items():
        for task, evidence in views.items():
            native = archive.joint.port_claims(labels[key][task]['answer'], task)
            for asset, values in evidence['add'].items():
                for citation, amount in values.items():
                    counts['positive'][task] += 1
                    claim = (asset, citation) if task == 'EC' else (asset, citation, amount / 100)
                    if claim not in native:
                        counts['disagreements'].append({'source_sha256': digest(key), 'task': task,
                                                        'citation': citation, 'proof': 'positive'})
            excluded = set(map(tuple, evidence['exclude']))
            counts['excluded'][task] += len(excluded)
            for claim in native:
                if claim[:2] in excluded:
                    counts['disagreements'].append({'source_sha256': digest(key), 'task': task,
                                                    'citation': claim[1], 'proof': 'excluded'})
    return counts


def reproduce(db, spec):
    cases, _, ev, grade_ref = archive.archive.history(db)
    ec = archive.extract(db, cases)
    stamps, ext = prior.prior.extend_with_archived_candidates(db, {b: cases[b] for b in prior.prior.BATCHES})
    if (digest(sorted(set(ev) | set(ec) | ext)) != spec['physical_ids_sha256']
            or stamps != {int(k): v for k, v in competing.bound_prior_candidates(spec).items()}):
        raise ValueError('Use the original full set of physical OpenExempt TRAIN reads')
    native = {b: {phase: {key: prior.prior.same_controls(row) for key, row in entry[phase].items()}
                  for phase in ('train', 'forward')} for b, entry in cases.items()}
    return native, grade_ref, len(set(ev) | set(ec) | ext)


def forward_snapshots(cases, fixed, earlier, choices, proof):
    train = {key: row for batches in cases.values() for key, row in batches['forward'].items()}
    earlier_fit = earlier['fit']
    revised = {}
    for batch, pair in cases.items():
        fit = earlier_fit[str(batch)]['selected']
        for key, row in pair['forward'].items():
            raw = row['answers']
            expected = {'incumbent': portfolio.compose(raw, portfolio.BASE), **{
                role: portfolio.compose(raw, [detail['route'][task] for task in PORTS])
                for role, detail in fit.items()}}
            expected = {**expected, 'prior_candidate_driven': expected['candidate_driven'],
                        'candidate_driven': portfolio.compose(raw, choices[str(batch)]['supported_route'])}
            if canonical_claim_order({key: expected}) != canonical_claim_order({key: fixed[key]}):
                raise ValueError(f'Original forward claims differ at batch {batch}, position {row["position"]}')
            revised[key] = {role: project(answer, proof[key]) for role, answer in fixed[key].items()}
    if set(train) != set(revised) or set(train) != set(fixed) or len(train) != 16:
        raise ValueError('Keep the four matched forward transitions and all original training mothers')
    return train, revised


def b7_conflicts(cases, refs):
    position, row = next((key, value) for key, value in cases[7]['train'].items() if value['position'] == 1)
    titles, exact, _ = archive.facts(row['views'])
    raw = row['answers']
    entering = portfolio.compose(raw, portfolio.BASE)
    candidate = portfolio.compose(raw, ('incumbent', 'proposal'))
    first = archive.joint.conflicts(entering, titles, exact)
    issues = archive.joint.conflicts(candidate, titles, exact) - first
    return [{'citation': citation, 'original_EC_reference_has_claim': citation in refs[position]['EC']['answer'].get(asset, []),
             'original_EV_reference_has_claim': any(x['citation'] == citation
                                                    for x in refs[position]['EV']['answer'].get(asset, []))}
            for asset, citation in sorted(issues)]


def run():
    fixed_root, fixed_spec, fixed = previous.archive.bound_result(arizona)
    measured_root, _, measure = prior.checked.bound_result(competing)
    _, fit_spec, fit = prior.checked.bound_result(prior)
    _, _, inherited = previous.archive.bound_result(previous)
    _, cohort, dev_arms, study, _ = previous.release.base_actor()
    _, _, roster = previous.release.parallel.adoption.archive_context()
    train = {s['key']: s for batch in roster for s in batch if s['dataset'] == archive.OE}
    dev = {s['key']: s for s in cohort if s['dataset'] == archive.OE}
    if (len(train), len(dev), len(dev_arms)) != (32, 16, 5) or fixed_spec['fixed_DEV_prior_terminal'] != inherited['terminal_sha256']:
        raise ValueError('Require the original training and all five fixed DEV arms')
    if any(s['project_split'] != 'train' for s in train.values()) or any(s['project_split'] != 'dev' for s in dev.values()):
        raise ValueError('Restrict proofs to original TRAIN and fixed DEV sources')
    indexes = {split: {key: previous.views_of(s) for key, s in sources.items()}
               for split, sources in (('train', train), ('dev', dev))}
    proofs = {split: {key: {task: categories.source_proof(view) for task, view in views.items()}
                      for key, views in sources.items()} for split, sources in indexes.items()}
    old_dev = read(fixed_root / 'sealed_predictions.json')['fixed_DEV']
    old_forward = read(measured_root / 'sealed_predictions.json')
    dev_comparison, verified_dev_reads = {}, set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, (train_grade, train_hash), train_reads = reproduce(db, fit_spec)
        for arm, (folder, seal, cell) in dev_arms.items():
            before = old_dev[arm]['after']
            after = {key: project(answer, proofs['dev'][key]) for key, answer in before.items()}
            dev_comparison[arm] = {'before': before, 'after': after}
            for key in before:
                changed = {task for task in PORTS if before[key][task] != after[key][task]}
                if changed:
                    previous.physical_dev(db, dev[key], folder, seal, cell, verified_dev_reads, changed)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or train_reads != measure['verified_archive_requests'] or set(dev_arms) != set(old_dev):
        raise ValueError('Need all original settled reads and the latest fixed DEV predictions')
    train_forward, revised = forward_snapshots(cases, old_forward, fit, measure['fit_choices'], proofs['train'])
    dev_grade = study['grading_paths'][archive.OE]
    dev_hash = fixed_spec['DEV_grade_sha256']
    if train_hash != fit_spec['grade_sha256'] or sha(ROOT / train_grade) != train_hash or sha(ROOT / dev_grade) != dev_hash:
        raise ValueError('Require the byte-exact original TRAIN and fixed DEV reference files')
    if 'train' not in Path(train_grade).parts or 'dev' not in Path(dev_grade).parts:
        raise ValueError('Preserve the original TRAIN and DEV split boundaries')
    binding = {
        'stage': STAGE, 'prior_fixed_DEV': fixed['terminal_sha256'], 'prior_candidate_comparison': measure['terminal_sha256'],
        'whole_portfolio_fit': fit['terminal_sha256'], 'evidence_sha256': digest(proofs),
        'verified_DEV_read_ids_sha256': digest(sorted(verified_dev_reads)), 'eligibility_scoring_only_after_seal': True,
        'TRAIN_grade_sha256': train_hash, 'DEV_grade_sha256': dev_hash, 'TEST_opened': False,
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, categories.__file__, categories.federal.__file__, categories.pennsylvania.__file__,
            competing.__file__, arizona.__file__, previous.__file__, prior.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    prior.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', proofs)
    tag = immutable_json(out / 'sealed_predictions.json', {'fixed_DEV': dev_comparison, 'TRAIN_forward': revised})
    train_ref, dev_ref = read(ROOT / train_grade), read(ROOT / dev_grade)
    audit = {split: verify_proofs(proofs[split], refs) for split, refs in (('train', train_ref), ('dev', dev_ref))}
    dev_scores = {role: previous.dev_compare(indexes['dev'], dev_ref, answers)
                  for role, answers in dev_comparison.items()}
    before_f1 = archive.summary(train_forward, old_forward, train_ref)
    if before_f1 != measure['all_forward_TRAIN']:
        raise ValueError('Keep the complete previously reported forward comparison unchanged')
    scores = archive.summary(train_forward, revised, train_ref)
    matches = {name: all(row[name] == row['candidate_driven'] for row in revised.values())
               for name in ('chronological', 'answer_disagreement')}
    release = (all(not v['disagreements'] for v in audit.values())
               and all(not x['regressed'] for row in dev_scores.values() for x in row.values())
               and any(x['improved'] for row in dev_scores.values() for x in row.values()))
    end = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'proof_audit': audit, 'fixed_DEV': dev_scores, 'forward_TRAIN_mothers': len(train_forward),
        'forward_TRAIN_before': before_f1, 'forward_TRAIN_with_common_proofs': scores,
        'same_predictions_as_common_controls': matches, 'B7_original_conflict_attribution': b7_conflicts(cases, train_ref),
        'train_mothers': len(train), 'dev_mothers': len(dev), 'supports_common_DEV_release': release,
        'reused_TRAIN_requests': train_reads, 'reused_DEV_requests': len(verified_dev_reads),
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', end)
    write_status(out, {'status': end['status'], 'terminal_sha256': end['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
