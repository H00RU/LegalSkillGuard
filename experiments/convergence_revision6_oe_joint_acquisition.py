"""Test signed EC/EV acquisition on the four original matched TRAIN transitions."""

import argparse
from itertools import product
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision5_oe_assertion_coverage as coverage
from experiments import convergence_revision5_oe_category_scope as category
from experiments import convergence_revision6_ec_general_property as ec
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from experiments import convergence_revision6_oe_forward_acquisition as archive
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_joint_acquisition as joint
from legal_skill_guard.paired_interfaces import convergence_oe_illinois_amount, convergence_oe_pa_monetary
from legal_skill_guard.paired_interfaces import convergence_oe_pa_item_forms as pa_items
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_oe_joint_acquisition'
HOME = BASE / STAGE
POINTER = HANDOFF / f'{STAGE}_current.json'
VALIDATED_STAGE = 'revision6_oe_item_validated_acquisition'
VALIDATED_POINTER = HANDOFF / f'{VALIDATED_STAGE}_current.json'
OE = archive.OE
FORMAL = archive.formal
PORTS = joint.TASKS


def matching_ec(db, source, result, program):
    trace, = (t for row in result['reads'] if set(row['native']) == {'EC'}
              for t in row['execution']['traces'] if 'physical_call_id' in t)
    paid = set()
    answer = ec.native(db, source, {'result': result}, program, paid)
    identity, = paid
    raw, = db.execute('select result from calls where id=?', (identity,)).fetchone()
    raw = json.loads(raw)
    request = read(Path(raw['artifact_directory']) / 'request.json')['payload']
    settings = {**request, 'messages': [m for m in request['messages'] if m['role'] == 'user']}
    status = result['native']['EC']
    assert trace['physical_call_id'] == identity
    if not status['handled'] or status['fallback_executed'] or raw['finish_reason'] != 'stop':
        answer = None
    return answer, identity, digest(settings)


def extract(db, existing):
    identities = {}
    for batch, pair in existing.items():
        fit, spec, end = archive.prior.archive.bound_stage(FORMAL.pointer(batch))
        checkpoint = ROOT / spec['checkpoint_root']
        study = read(checkpoint / 'binding.json')
        roster = FORMAL.load_roster(study)
        journal = archive.exact.TrainingJournal(checkpoint, study, roster)
        proposal = read(fit / 'candidates' / FORMAL.ORDINARY / OE / 'measurements.json')
        assert sha(fit / 'terminal.json') == pair['original_fit_sha256'] and end['batch'] == batch
        carriers = {}
        for arm in ConvergenceEvaluation.arms:
            library = journal.library(arm, batch)
            if library.get('schema_proposals', {}).get(OE) is None:
                carriers.setdefault(digest(library['programs'][OE]), arm)
        for phase, number in (('train', batch), ('forward', batch + 1)):
            for source in (row for row in roster[number - 1] if row['dataset'] == OE):
                key = source['key']
                row = pair[phase][key]
                views = {view['id']: view for view in source['views']}
                assert row['view'] == views['EV'] and source['project_split'] == 'train'
                receipts = []
                answers = {}
                for role, version in pair['programs'].items():
                    if phase == 'train':
                        pred = (proposal['predictions'][key] if role == 'proposal' else
                                archive.raw_prediction(journal, FORMAL.M2, number, key))
                    else:
                        pred = archive.raw_prediction(journal, carriers[version], number, key)
                    ec_answer, identity, wire = matching_ec(db, source, pred, version)
                    if identities.setdefault(identity, (key, version)) != (key, version):
                        raise ValueError('Count EC requests only under their exact archived program')
                    receipts.append((identity, wire))
                    answers[role] = {'EC': ec_answer, 'EV': row['answers'][role]}
                if receipts[0][0] == receipts[1][0] or receipts[0][1] != receipts[1][1]:
                    raise ValueError('Match literal EC input, execution settings and schema')
                row.update(views=views, answers=answers, EC_wire=receipts[0][1])
    return identities


def facts(views):
    aligned = {task: coverage.normalized_scope(view)[0] for task, view in views.items()}
    exact = {}
    for asset, row in category.view_facts(aligned['EC']).items():
        for citation, allowed in row['allowed'].items():
            if not allowed or row['title'] is not None:
                exact[asset, citation] = allowed and row['title']
    for citation in ec.TEXT:
        exact.update({(a, citation): True for a in ec.source_claims(aligned['EC'], citation)})
    return coverage.aligned_titles(aligned), exact, aligned


def common(views, answers, validated):
    result = dict(answers)
    for task, view in views.items():
        native = result[task]
        if native is None:
            continue
        native = coverage.public_controls(view, native)
        native = category.repair(native, task, category.view_facts(view))
        native = convergence_oe_pa_monetary.apply(task, native, convergence_oe_pa_monetary.claims(view))
        if task == 'EC':
            for citation in ec.TEXT:
                for asset in ec.source_claims(view, citation):
                    rows = native.setdefault(asset, [])
                    if citation not in rows:
                        rows.append(citation)
        else:
            native = convergence_oe_illinois_amount.apply(native, convergence_oe_illinois_amount.source_amounts(view))
        if validated:
            native = pa_items.filter_claims(task, native, pa_items.exclusions(view))
        result[task] = native
    return result


def group_evidence(row, validated):
    titles, exact, views = facts(row['views'])
    ev_exclusions = set()
    if validated:
        exact.update(dict.fromkeys(pa_items.exclusions(views['EC']), False))
        ev_exclusions = pa_items.exclusions(views['EV'])
    values, cap = archive.acquisition.public_bounds(views['EV'])
    incoming = joint.route(row['answers'], 'incumbent')
    return {name: joint.evidence(incoming, joint.route(row['answers'], name), titles, exact, values, cap,
                                 require_category=validated, ev_excluded=ev_exclusions)
            for name in joint.ROUTES}


def scored(cases, predictions, labels):
    scored = {policy: [] for policy in next(iter(predictions.values()))}
    for key, answers in predictions.items():
        for policy, ports in answers.items():
            for task, answer in ports.items():
                grade = archive.native_grade(cases[key]['views'][task], labels[key][task], answer)
                scored[policy].append({'source': key, 'view': task, 'grade': grade})
    return scored


def summary(cases, predictions, labels):
    rows = scored(cases, predictions, labels)
    return {
        'F1': {policy: {task: mean(x['grade'] for x in units if x['view'] == task) for task in PORTS}
               for policy, units in rows.items()},
        'paired_candidate_driven': {policy: paired_source_effect(units, rows['candidate_driven'])
                                    for policy, units in rows.items() if policy != 'candidate_driven'},
    }


def prepare_fit(cases, labels, validated):
    candidates = {key: {name: joint.route(row['answers'], name) for name in joint.ROUTES} for key, row in cases.items()}
    fit_scores = {role: mean(r['grade'] for r in rows) for role, rows in scored(cases, candidates, labels).items()}
    gain = {role: score - fit_scores['incumbent'] for role, score in fit_scores.items()}
    groups = {row['position']: group_evidence(row, validated) for row in cases.values()
              if all(answer is not None for native in row['answers'].values() for answer in native.values())}
    return {'group_evidence': groups, 'TRAIN_shared_native_gate': gain, 'choices': joint.select(groups, gain),
            'screening_requests_per_policy': len(PORTS) * len(archive.PROGRAMS) if groups else 0}


def run(validated=False):
    for flags in product((None, False, True), (False, True), (None, False, True), (None, False, True)):
        assert joint.relation_supported(*flags) == joint.direct_supported(*flags)
    previous = ROOT / read(archive.POINTER)['artifact_root']
    previous_end = verify(read(previous / 'terminal.json'), 'terminal_sha256')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, excluded, ev_ids, grade = archive.history(db)
        ec_ids = extract(db, cases)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    filename, expected = grade
    path = ROOT / filename
    assert not previous_end['TEST_opened'] and list(cases) == [3, 4, 6, 7] and not set(ec_ids) & set(ev_ids)
    assert not ledger.get('reserved') and 'train' in path.parts and sha(path) == expected
    assert digest(sorted(ev_ids)) == read(previous / 'binding.json')['requests_sha256']
    paths = (__file__, archive.__file__, archive.acquisition.__file__, joint.__file__, ec.__file__,
             coverage.__file__, category.__file__, convergence_oe_illinois_amount.__file__, convergence_oe_pa_monetary.__file__)
    stage = VALIDATED_STAGE if validated else STAGE
    spec = {'stage': stage, 'previous_EV_comparison': previous_end['terminal_sha256'], 'TEST_opened': False,
            'require_category_proof_for_joined_repairs': validated,
            'partition': 'TRAIN', 'grade_sha256': expected, 'transitions': list(cases), 'excluded': excluded,
            'paired_bank_sha256': digest(cases), 'requests_sha256': digest(sorted(set(ec_ids) | set(ev_ids))),
            'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths}}
    if validated:
        predecessor = ROOT / read(POINTER)['artifact_root']
        result = verify(read(predecessor / 'terminal.json'), 'terminal_sha256')
        old = read(predecessor / 'binding.json')
        assert old['paired_bank_sha256'] == spec['paired_bank_sha256'] and not result['TEST_opened']
        assert all(sha(predecessor / 'source_snapshot' / name) == h for name, h in old['source_sha256'].items())
        spec['prior_joint_screen'] = result['terminal_sha256']
        spec['source_sha256'][str(Path(pa_items.__file__).relative_to(ROOT))] = sha(Path(pa_items.__file__))
    out = (BASE / stage) / digest(spec)
    immutable_json(out / 'binding.json', spec)
    snapshot(out, spec['source_sha256'])
    labels = read(path)
    fit, forwarded = {}, {}
    predictions = {'public_binding': {}, 'shared_category_and_amount_controls': {}}
    for batch, sample in cases.items():
        fit[batch] = prepare_fit(sample['train'], labels, validated)
        for policy, choice in fit[batch]['choices'].items():
            route = joint.ROUTES[choice['route']]
            library = sealed({'batch': batch, 'binding_sha256': out.name, 'choice': choice,
                              'programs': dict(zip(PORTS, (sample['programs'][role] for role in route), strict=True))},
                             'snapshot_sha256')
            immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}' / f'{policy}.json', library)
        for key, row in sample['forward'].items():
            assert key not in forwarded
            forwarded[key] = row
            answers = {'incumbent': joint.route(row['answers'], 'incumbent')}
            answers.update({policy: joint.route(row['answers'], c['route']) for policy, c in fit[batch]['choices'].items()})
            predictions['public_binding'][key] = answers
            predictions['shared_category_and_amount_controls'][key] = {
                p: common(row['views'], a, validated) for p, a in answers.items()}
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    totals = {mode: summary(forwarded, predictions[mode], labels) for mode in predictions}
    by_batch = {batch: {mode: summary(sample['forward'], {k: data[k] for k in sample['forward']}, labels)
                        for mode, data in predictions.items()} for batch, sample in cases.items()}
    result = sealed({'status': f'settled_{stage}', 'binding_sha256': out.name, 'predictions_sha256': tag,
                     'fit': fit, 'forward_TRAIN': by_batch, 'all_forward_TRAIN': totals, 'forward_mothers': len(forwarded),
                     'old_physical_requests_verified': {'EC': len(ec_ids), 'EV': len(ev_ids)},
                     'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger},
                    'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']},
                 VALIDATED_POINTER if validated else POINTER)
    print(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item-validated', action='store_true')
    run(parser.parse_args().item_validated)
