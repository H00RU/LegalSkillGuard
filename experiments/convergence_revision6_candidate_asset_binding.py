"""Test whether asset naming accounts for apparent EV candidate gains."""

from collections import Counter
from decimal import Decimal
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision5_oe_native_amount_bound as dev_archive
from experiments import convergence_revision6_candidate_archive_coverage as archive
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_ev_asset_binding as binder
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


formal = archive.formal
HOME = BASE / 'revision6_candidate_asset_binding'
POINTER = HANDOFF / 'revision6_candidate_asset_binding_current.json'
ROLES = ('incumbent', 'candidate')
MODES = ('original', 'asset_bound', 'same_public_jurisdiction')


def scopes(view, answer):
    bound = binder.bind_valuation(view, answer)
    scope = supplied_jurisdiction_scope(view['public']['original_input'])
    if isinstance(bound, dict) and scope is not None:
        lawful = set(scope['citations'])
        jurisdiction = {asset: [c for c in claims if c['citation'] in lawful] for asset, claims in bound.items()}
    else:
        jurisdiction = bound
    return dict(zip(MODES, (answer, bound, jurisdiction), strict=True))


def grades_ref(spec):
    name = spec['native_grade_paths'][formal.OE]
    return name, spec['native_grade_sha256'][name]


def training(db):
    views, programs, results = {}, [], {role: {} for role in ROLES}
    verified, grade_refs, terminals = set(), set(), {}
    for batch in range(2, 9):
        fit = ROOT / read(formal.pointer(batch))['artifact_root']
        spec, end, decision = (read(fit / name) for name in ('binding.json', 'terminal.json', 'matched_decisions.json'))
        if (fit.name != digest(spec) or end['batch'] != batch or end['TEST_opened']
                or digest(decision) != end['matched_decisions_sha256']):
            raise ValueError('Require the exact original Fit decision')
        terminals[f'B{batch}'] = sha(fit / 'terminal.json')
        grade_refs.add(grades_ref(read(ROOT / spec['observations_root'] / 'binding.json')))
        checkpoint = ROOT / spec['checkpoint_root']
        study = read(checkpoint / 'binding.json')
        roster = formal.load_roster(study)
        journal = archive.TrainingJournal(checkpoint, study, roster)
        prior = journal.library(formal.M2, batch - 1)['programs'][formal.OE]
        candidate = read(fit / 'candidates' / formal.ORDINARY / formal.OE / 'measurements.json')
        before, after = digest(prior), digest(candidate['candidate'])
        decision_record = decision['relation'][formal.OE]
        if (after != decision_record['matched_proposal_sha256'] or digest(candidate['predictions'])
                != decision['teacher'][formal.ORDINARY][formal.OE]['predictions_sha256']):
            raise ValueError('Keep the actual proposal for the original paired measurement')
        programs.append({'batch': batch, 'incumbent': before, 'candidate': after, 'status': decision_record['status']})
        obs = journal._observations(formal.M2, batch)
        for index, source in enumerate(s for s in roster[batch - 1] if s['dataset'] == formal.OE):
            key = source['key']
            saved = read(journal.directory(formal.M2, batch) / 'predictions' / (digest(key) + '.json'))
            if source['project_split'] != 'train' or digest(saved) != obs['predictions'][key]:
                raise ValueError('Only original TRAIN observations')
            view = dev_archive.ev_view(source)
            views[key] = {'view': view, 'position': (batch, index)}
            for role, pred, h in zip(ROLES, (saved['result'], candidate['predictions'][key]), (before, after), strict=True):
                physical, result = archive.verified_ev(db, source, view, pred, h)
                verified.add(physical)
                results[role][key] = scopes(view, result)
    if len(verified) != 56 or len(views) != 28:
        raise ValueError('Preserve both native measurements and all four mothers in each TRAIN batch')
    grade, = grade_refs
    return views, results, grade, terminals, verified, programs


def development(db):
    root = ROOT / read(dev_archive.BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    stage, spec, end = dev_archive.bound_stage(dev_archive.dev_pointer(8))
    data = ROOT / spec['b0_dev_data_root']
    public = read(data / 'public_DEV_sources.json')
    if (digest(study) != spec['checkpoint_binding_sha256']
            or digest(public) != read(data / 'binding.json')['DEV_public_sha256'] or end['TEST_opened']):
        raise ValueError('Keep the original fixed DEV source binding')
    cohort = [s for s in public if s['dataset'] == formal.OE and s['project_split'] == 'dev']
    views = {s['key']: {'view': dev_archive.ev_view(s), 'position': i} for i, s in enumerate(cohort)}
    verified, predictions = set(), {}
    for arm in dev_archive.ARMS:
        directory = root / 'dev' / 'B8' / arm
        score = verify(read(directory / 'scores.json'), 'cell_sha256')
        seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
        if (score['cell_sha256'] != end['cell_sha256'][arm]
                or seal['task_sha256'] != digest(read(directory / 'task.json'))
                or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']):
            raise ValueError('Require the settled fixed DEV arm')
        predictions[arm] = {}
        for source in cohort:
            key = source['key']
            saved = read(directory / 'predictions' / (digest(key) + '.json'))
            if (digest(saved) != seal['predictions_sha256'][key] or saved['library_sha256'] != score['libraries'][formal.OE]
                    or saved['public_source_sha256'] != digest(source)):
                raise ValueError('DEV replay must preserve the exact source and reader')
            result = dev_archive.read_ev(db, source, saved, verified, 'dev')
            fallback = result.get('fallback_executed', saved['result']['fallback_executed'])
            answer = result['answer'] if result['handled'] and not fallback else None
            predictions[arm][key] = scopes(views[key]['view'], answer)
    if len(views) != 16 or len(verified) != 32:
        raise ValueError('Use the exact two sixteen-source fixed DEV arms')
    path = study['grading_paths'][formal.OE]
    return views, predictions, (path, study['grading_file_sha256'][path]), {'B8_DEV': sha(stage / 'terminal.json')}, verified


def claims(answer):
    return {(asset, row['citation'], Decimal(str(row['claim_value']))) for asset, entries in (answer or {}).items()
            for row in entries if row['claim_value'] > 0}


def attributable(views, bank, labels):
    corrected = Counter()
    events = []
    for key, source in views.items():
        reference = claims(labels[key]['EV']['answer'])
        raw_a, raw_b = (claims(bank[role][key]['original']) for role in ROLES)
        norm_a, norm_b = (claims(bank[role][key]['asset_bound']) for role in ROLES)
        if any(bank[role][key]['original'] is None for role in ROLES):
            continue
        for change, observed, bound in (
            ('candidate_gain', (raw_b - raw_a) & reference, (norm_b - norm_a) & reference),
            ('candidate_loss', (raw_a - raw_b) & reference, (norm_a - norm_b) & reference),
        ):
            for state, rows in (('preserved', observed & bound), ('name_only', observed - bound), ('revealed', bound - observed)):
                corrected[f'{change}_{state}'] += len(rows)
                for name, law, amount in sorted(rows):
                    events.append({'position': source['position'], 'asset': name, 'citation': law,
                                   'amount': str(amount), 'raw_change': change, 'after_bind': state})
    return dict(corrected), events


def measurements(views, bank, grade_ref, partition):
    name, expected = grade_ref
    path = ROOT / name
    if partition not in path.parts or sha(path) != expected:
        raise ValueError('Use the native partition scorer after sealing all output modes')
    labels = read(path)
    by_role, scored = {}, {}
    common = {k for k in views if all(source[k]['original'] is not None for source in bank.values())}
    for role, sources in bank.items():
        graded, shifts = {mode: [] for mode in MODES}, Counter()
        for key, responses in sources.items():
            if key not in common:
                continue
            view = views[key]['view']
            points = {mode: grade_view(formal.OE, view, labels[key]['EV'], out)['grade']
                      for mode, out in responses.items()}
            if any(p is None for p in points.values()):
                continue
            for mode, grade in points.items():
                graded[mode].append({'source': key, 'view': 'EV', 'grade': grade})
            old, new = points['original'], points['asset_bound']
            shifts['improved' if new > old else 'regressed' if new < old else 'same'] += 1
        scored[role] = graded
        by_role[role] = {'scored': len(graded['original']), 'asset_keys_changed': sum(
            r['original'] != r['asset_bound'] for r in sources.values()), 'asset_binding_effect_counts': dict(shifts),
            'F1': {mode: mean(row['grade'] for row in vals) for mode, vals in graded.items()},
            'paired_binding_effect': paired_source_effect(graded['original'], graded['asset_bound'])}
    left, right = bank.keys()
    contrasts = {mode: paired_source_effect(scored[left][mode], scored[right][mode]) for mode in MODES}
    return {'by_role': by_role, 'paired_roles': [left, right], 'paired_effect': contrasts}, labels


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        v, p, g, t, r, programs = training(db)
        dv, dp, dg, dt, dr = development(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    spec = {'stage': 'revision6_candidate_asset_binding', 'originals': t | dt, 'programs': programs,
            'native_grades': {'train': g[1], 'dev': dg[1]}, 'TEST_opened': False,
            'source_sha256': {str(Path(name).relative_to(ROOT)): sha(Path(name))
                              for name in (__file__, binder.__file__, archive.__file__, dev_archive.__file__)}}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, expected in spec['source_sha256'].items():
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as file:
                file.write((ROOT / name).read_bytes())
        if sha(target) != expected:
            raise ValueError('Retain the exact replay sources')
    prediction_sha = immutable_json(out / 'sealed_predictions.json', {'train': p, 'dev': dp})
    train_metrics, labels = measurements(v, p, g, 'train')
    dev_metrics, _ = measurements(dv, dp, dg, 'dev')
    event_counts, events = attributable(v, p, labels)
    event_hash = immutable_json(out / 'attributed_train_positions.json', events)
    result = sealed({
        'status': 'settled_revision6_candidate_asset_binding', 'binding_sha256': out.name,
        'TRAIN': train_metrics, 'fixed_DEV': dev_metrics, 'TRAIN_exact_positive_changes': event_counts,
        'attributed_train_positions_sha256': event_hash, 'predictions_sha256': prediction_sha,
        'physical_requests_reused': {'train': len(r), 'dev': len(dr)},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
