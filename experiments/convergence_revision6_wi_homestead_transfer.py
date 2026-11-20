"""Fit and replay a Wisconsin homestead fragment of the actual B7 proposal."""

from decimal import Decimal
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision5_oe_assertion_coverage as archived
from experiments import convergence_revision6_candidate_dev as dev
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_wi_homestead as local
from legal_skill_guard.paired_interfaces import convergence_ec_inventory, convergence_oe_ev_asset_binding
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation, matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_wi_homestead_transfer'
POINTER = HANDOFF / 'revision6_wi_homestead_transfer_current.json'
TASKS = ('EC', 'EV')
ROLES = ('incumbent', 'proposal', 'scoped_candidate', 'same_information_direct')
CITATION = local.CITATION


def calculate(facts, law):
    return True if facts['task'] == 'EC' else min(facts['stated_cents'], facts['filers'] * law['cap'])


def observation(answer, task, asset):
    if not isinstance(answer, dict):
        return None
    row = answer.get(asset, [])
    if task == 'EC':
        return True if CITATION in row else None
    values = [Decimal(str(entry['claim_value'])) * 100 for entry in row if entry['citation'] == CITATION]
    if len(values) != 1:
        return None
    return int(values[0]) if values[0] == int(values[0]) else str(values[0])


def group_proof(key, views):
    facts = {task: local.supported(views[task]) for task in TASKS}
    names = set(facts['EC']) & set(facts['EV'])
    result = {}
    for name in sorted(names):
        a, b = (facts[task][name] for task in TASKS)
        if any(a[f] != b[f] for f in ('stated_cents', 'filers', 'title')):
            continue
        known = {'EC': True, 'EV': b['expected_cents']}
        signature_scope = digest([CITATION, views['EV']['public']])
        proof = digest([a['source_quote'], b['source_quote'], CITATION])
        theory = Theory(
            {signature_scope: [{'cap': local.SINGLE_CAP_CENTS}]}, {key: [{}]}, calculate, sha(Path(__file__)),
            provenance=({'kind': 'explicit_source', 'evidence_sha256': proof},),
        )
        cases = [SourceCase(key + ':' + task + ':' + digest(name), key, signature_scope,
                            {}, {'task': task, 'stated_cents': b['stated_cents'], 'filers': b['filers']})
                 for task in TASKS]
        shared = allowed_relation(theory, cases)
        independent = allowed_relation(theory, cases, mode='independent_completions')
        if list(shared['signatures'].values()) != [list(known.values())] or shared['signatures'] != independent['signatures']:
            raise ValueError('Use exactly the same title, scope and statutory amounts in both rules')
        result[name] = {'expected': known, 'proof_sha256': proof, 'joint_count': b['filers'],
                        'amount_cents': b['stated_cents'], 'shared': shared['signatures']}
    return result


def exact_role(known, task, values):
    actual = [None if k != task else values for k in TASKS]
    supported = values is not None and any(matches_assertions(actual, signature)
                                           for signature in known['shared'].values())
    direct = values is not None and type(values) is type(known['expected'][task]) \
        and values == known['expected'][task]
    if supported != direct:
        raise ValueError('Same-information screening must agree on the native scoped claim')
    return supported


def banks(board):
    archived.replay(board)
    archived.prepare_routes({0: board})
    controlled, _ = archived.prepare_category(board['views'], board['wildcard'])
    return {
        role: {key: {'EC': convergence_ec_inventory.bind_classification(board['views'][key]['EC'], value['EC']),
                     'EV': convergence_oe_ev_asset_binding.bind_valuation(board['views'][key]['EV'], value['EV'])}
               for key, value in scope.items()} for role, scope in controlled.items()
    }


def fit(board, original):
    support = {}
    for key, views in board['original_views'].items():
        for asset, facts in group_proof(key, views).items():
            record = {'source': facts, 'by_task': {}}
            support.setdefault(key, {})[asset] = record
            for task in TASKS:
                values = {role: observation(original[role][key][task], task, asset) for role in ROLES[:2]}
                qualified = {r: exact_role(facts, task, value) for r, value in values.items()}
                record['by_task'][task] = {'values': values, 'compatible': qualified}
    selected = set()
    for task in TASKS:
        witnessed = [r['by_task'][task]['compatible'] for assets in support.values() for r in assets.values()]
        if all(row['proposal'] for row in witnessed) and any(not row['incumbent'] for row in witnessed):
            selected.add(task)
    return support, selected


def replace_claim(answer, family, asset, proof):
    if not isinstance(answer, dict):
        return answer
    claims = answer.get(asset, [])
    if family == 'EC':
        value = list(dict.fromkeys([*claims, CITATION]))
    else:
        value = [entry for entry in claims if entry['citation'] != CITATION]
        value.append({'citation': CITATION, 'claim_value': proof['expected']['EV'] / 100})
    return {**answer, asset: value}


def apply(board, entering, candidate, selected):
    forward, relative, known = {}, {}, {}
    for key, views in board['original_views'].items():
        routed, shared = dict(entering[key]), dict(entering[key])
        for name, proof in group_proof(key, views).items():
            record = {'facts': proof, 'by_task': {}}
            known.setdefault(key, {})[name] = record
            for task in TASKS:
                measured = {role: observation(bank[key][task], task, name)
                            for role, bank in (('incumbent', entering), ('proposal', candidate))}
                record['by_task'][task] = measured
                if task in selected and exact_role(proof, task, measured['proposal']):
                    routed[task] = replace_claim(routed[task], task, name, proof)
                if not exact_role(proof, task, measured['incumbent']):
                    shared[task] = replace_claim(shared[task], task, name, proof)
        forward[key], relative[key] = routed, shared
    return forward, relative, known


def score(board, bank, labels):
    original = board['original_views']
    rows = {arm: {task: [
        {'source': key, 'view': task, 'grade': grade_view('OpenExempt', views[task], labels[key][task],
                                                        bank[arm][key][task])['grade']}
        for key, views in original.items()] for task in TASKS} for arm in bank}
    means = {arm: {t: mean(row['grade'] for row in cells) for t, cells in tasks.items()}
             for arm, tasks in rows.items()}
    effects = {arm: {t: paired_source_effect(rows['incumbent'][t], tasks[t]) for t in TASKS}
               for arm, tasks in rows.items() if arm != 'incumbent'}
    return {'mothers': len(original), 'F1': means, 'paired_vs_incumbent': effects}


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        original, archives, programs, counts, grade = archived.archived_pairs(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or counts != 32:
        raise ValueError('Require the complete matched native archive at B7–B8')
    train = banks(original[7])
    audit, selected = fit(original[7], train)
    if not audit:
        raise ValueError('The exact housing scope must first be witnessed in original TRAIN')
    binding, _, _, _, development, _, _ = dev.materials()
    fixed_dev = [s for s in development if s['dataset'] == 'OpenExempt' and s['project_split'] == 'dev']
    if len(fixed_dev) != 16 or digest(fixed_dev) != binding['public_DEV_sha256']:
        raise ValueError('Check applicability on the original fixed OpenExempt DEV roster only')
    dev_count = sum(bool(group_proof(s['key'], {v['id']: v for v in s['views']})) for s in fixed_dev)
    frozen = {
        'stage': 'revision6_wi_homestead_transfer', 'partition': 'TRAIN', 'archives': archives,
        'TRAIN_grade_sha256': sha(grade), 'source_proofs_sha256': digest(audit),
        'fitted_tasks': sorted(selected), 'DEV_public_sha256': binding['public_DEV_sha256'],
        'source_sha256': {str(Path(x).relative_to(ROOT)): sha(Path(x)) for x in (
            __file__, local.__file__, archived.__file__,
        )}, 'TEST_opened': False,
    }
    out = HOME / digest(frozen)
    immutable_json(out / 'binding.json', frozen)
    for name, expected in frozen['source_sha256'].items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(path) != expected:
            raise ValueError('Preserve the exact scoped policy implementation')
    library = sealed({'batch': 7, 'source_scope': CITATION, 'active_tasks': sorted(selected),
                      'measured_programs_sha256': programs, 'source_proofs_sha256': digest(audit),
                      'binding_sha256': out.name}, 'snapshot_sha256')
    immutable_json(out / 'TRAIN_batch_libraries' / 'wi_homestead.json', library)
    pred, forward_proofs = {}, {}
    for b, board in original.items():
        prev = train if b == 7 else banks(board)
        route, direct, proofs = apply(board, prev['incumbent'], prev['proposal'], selected)
        pred[b] = {**prev, 'scoped_candidate': route, 'same_information_direct': direct}
        forward_proofs[b] = proofs
    pred_sha = immutable_json(out / 'sealed_predictions.json', pred)
    immutable_json(out / 'source_proofs.json', {'B7_fit': audit, 'forward': forward_proofs})
    if 'train' not in grade.parts or sha(grade) != frozen['TRAIN_grade_sha256']:
        raise ValueError('Use the pinned native TRAIN grade only after sealing both comparisons')
    labels = read(grade)
    for b, support in forward_proofs.items():
        for key, assets in support.items():
            for name, row in assets.items():
                claims = {t: observation(labels[key][t]['answer'], t, name) for t in TASKS}
                if claims != row['facts']['expected']:
                    raise ValueError('Report the scope disagreement before using this proof')
    results = {b: score(original[b], answer, labels) for b, answer in pred.items()}
    table = {b: [{'asset': name, 'by_task': row['by_task'], 'expected': row['facts']['expected']}
                 for assets in cases.values() for name, row in assets.items()]
             for b, cases in forward_proofs.items()}
    terminal = sealed({
        'status': 'settled_revision6_wi_homestead_transfer', 'binding_sha256': out.name,
        'selection': sorted(selected), 'library_sha256': library['snapshot_sha256'],
        'source_bound_homestead_cases': table, 'scores': results, 'archived_requests_verified': counts,
        'B8_candidate_changed_mothers': sum(pred[8]['scoped_candidate'][k] != pred[8]['incumbent'][k]
                                            for k in pred[8]['incumbent']),
        'DEV_mothers': len(fixed_dev), 'DEV_scope_mothers': dev_count, 'DEV_labels_read': False,
        'same_information_screening_matches': True, 'new_executor_requests': 0,
        'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger, 'predictions_sha256': pred_sha,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
