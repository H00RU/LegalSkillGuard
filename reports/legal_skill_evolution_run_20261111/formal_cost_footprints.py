"""Measured physical dispatches and deduplicated response use per fixed arm."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
import sqlite3

from experiments.legal_skill_evolution_formal import ARMS, PROFILE as FORMAL_PROFILE
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import unpack

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def used_physical_ids(value, known_ids):
    result = set()
    if isinstance(value, dict):
        for field in ('physical_call_id', 'call_id'):
            if isinstance(value.get(field), str) and value[field] in known_ids:result.add(value[field])
        result.update(v for v in value.get('physical_call_ids', []) if v in known_ids)
        for child in value.values():result.update(used_physical_ids(child, known_ids))
    elif isinstance(value, list):
        for child in value:result.update(used_physical_ids(child, known_ids))
    elif isinstance(value, str):
        # Transport failures keep the charged call identity in the captured
        # exception even when no successful READ event could be emitted.
        result.update(i for i in re.findall(r'legal_skill_evolution_[A-Za-z0-9_]+:[0-9a-f]{64}', value)
                      if i in known_ids)
    return result


def usage(rows):
    counts, tokens, elapsed = Counter(), Counter(), 0.0
    for row in rows:
        counts[(row['role'], row['status'])] += 1
        body = row['result']
        actual = body.get('usage') or body.get('invocation', {}).get('usage') or {}
        tokens.update({row['role'] + ':' + k: v for k, v in actual.items() if isinstance(v, (int, float))})
        elapsed += body.get('elapsed_seconds', 0)
    return {'physical_requests': len(rows), 'statuses': {role + ':' + status: n for (role, status), n in counts.items()},
        'reported_token_fields': dict(tokens), 'sum_reported_generation_latency_seconds': elapsed,
        'cash_invoice_usd': None}


def evidence_batch(path):
    matches = re.findall(r'(?:^|[_/])B([0-8])(?=[_/.]|$)', Path(path).as_posix())
    if len(set(matches)) != 1:raise ValueError('Evidence has no unique fixed batch: ' + str(path))
    return int(matches[0])


def recovered_exception_references(ledger):
    """Use exact-cache replay evidence for calls lost before event emission."""
    path = REPORT / 'recovered_TRAIN_cost_references.json'
    if not path.exists():return []
    receipt = json.loads(path.read_text())
    if (receipt['new_model_calls'] != 0 or not receipt['network_disabled'] or
            not receipt['ledger_read_only'] or not receipt['original_predictions_and_scores_unchanged']):
        raise ValueError('Cost recovery is not read-only original-result evidence')
    for relative, expected in receipt['evidence_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Cost recovery evidence changed: ' + relative)
    for identity, record in receipt['physical_responses'].items():
        if (identity not in ledger or ledger[identity]['status'] != 'completed' or
                digest(ledger[identity]['result']) != record['settled_result_sha256']):
            raise ValueError('Recovered response differs from the continuous ledger')
    rows = []
    for row in receipt['rows']:
        if not row['original_result_equal']:
            raise ValueError('A cost recovery changed an original prediction')
        if row['recovered_physical_ids']:
            rows.append(row)
    if {i for row in rows for i in row['recovered_physical_ids']} != set(receipt['recovered_physical_ids']):
        raise ValueError('Recovered cost references lack actual replay witnesses')
    return rows


def main():
    folder = ROOT / json.loads(FORMAL_PROFILE.read_text())['artifacts']
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        records = db.execute('select id,role,status,result from calls').fetchall()
    ledger = {i: {'id': i, 'role': role, 'status': status, 'result': json.loads(raw) if raw else {}}
              for i, role, status, raw in records}
    teachers_by_folder = {digest(i): i for i, row in ledger.items()
                          if i.startswith('legal_skill_evolution_formal_') and row['role'] == 'teacher'}
    teachers_by_sha = {row['result']['request_sha256']: i for i, row in ledger.items()
        if row['role'] == 'teacher' and row['result'].get('request_sha256')}
    by_arm, teacher_ids = {a: set() for a in ARMS}, {a: set() for a in ARMS}
    by_batch = {a: defaultdict(set) for a in ARMS}
    learning_batch, dev_batch = ({a: defaultdict(set) for a in ARMS} for _ in range(2))
    coverage = Counter()
    for arm in ARMS:
        paths = list((folder / arm).glob('initial_B*.json')) + list((folder / arm).glob('initial_B*/*.json'))
        paths += list((folder / arm).glob('update_context_B*.json'))
        paths += list((folder / arm).glob('B*_candidates/*.json'))
        paths += list((folder / 'dev' / arm).glob('B*.json'))
        for path in paths:
            identities = used_physical_ids(json.loads(path.read_text()), ledger)
            by_arm[arm].update(identities)
            by_batch[arm][evidence_batch(path)].update(identities)
            scope = dev_batch if path.is_relative_to(folder / 'dev') else learning_batch
            scope[arm][evidence_batch(path)].update(identities)
            coverage[arm] += 1
        for path in (folder / arm).glob('teacher_B*.json'):
            response = json.loads(path.read_text())
            identity = teachers_by_sha.get(response['request_sha256'])
            if identity is None:raise ValueError('A preserved teacher response lost its original physical ledger identity')
            teacher_ids[arm].add(identity)
            by_arm[arm].add(identity)
            by_batch[arm][evidence_batch(path)].add(identity)
            learning_batch[arm][evidence_batch(path)].add(identity)
    for request in (folder / 'calls').glob('*/request.json'):
        teacher_id = teachers_by_folder.get(request.parent.name)
        if not teacher_id:continue
        raw = json.loads(request.read_text())
        context = json.loads(raw['user_prompt'])
        if context.get('encoding') == 'lossless_shared_JSON_values_v1':context = unpack(context)
        arm = context['arm']
        if arm not in ARMS:raise ValueError('A teacher request has an unregistered arm')
        teacher_ids[arm].add(teacher_id)
        by_arm[arm].add(teacher_id)
        by_batch[arm][context['batch']].add(teacher_id)
        learning_batch[arm][context['batch']].add(teacher_id)
    recovered = recovered_exception_references(ledger)
    for row in recovered:
        arm, batch = row['arm'], row['batch']
        identities = set(row['recovered_physical_ids'])
        by_arm[arm].update(identities)
        by_batch[arm][batch].update(identities)
        learning_batch[arm][batch].update(identities)
    users = defaultdict(list)
    for arm, identities in by_arm.items():
        for identity in identities:users[identity].append(arm)
    formal = {i for i in ledger if i.startswith('legal_skill_evolution_formal_')}
    trajectories = {}
    for arm in ARMS:
        cumulative, cumulative_learning, cumulative_dev, points = set(), set(), set(), []
        for batch, identities in sorted(by_batch[arm].items()):
            cumulative.update(identities)
            cumulative_learning.update(learning_batch[arm][batch])
            cumulative_dev.update(dev_batch[arm][batch])
            points.append({'batch': batch,
                'batch_observed_response_footprint': usage([ledger[i] for i in sorted(identities)]),
                'cumulative_distinct_response_footprint': usage([ledger[i] for i in sorted(cumulative)]),
                'cumulative_initial_and_learning_response_footprint': usage([ledger[i] for i in sorted(cumulative_learning)]),
                'cumulative_DEV_response_footprint': usage([ledger[i] for i in sorted(cumulative_dev)]),
                'batch_distinct_response_ids': sorted(identities)})
        trajectories[arm] = points
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'actual_formal_dispatches_counted_once': usage([ledger[i] for i in sorted(formal)]),
        'per_arm_consumed_response_footprints': {arm: usage([ledger[i] for i in sorted(ids)]) |
            {'response_ids': sorted(ids), 'teacher_response_ids': sorted(teacher_ids[arm]),
             'settled_evidence_files_scanned': coverage[arm],
             'inherited_responses_outside_formal_run': sum(i not in formal for i in ids)} for arm, ids in by_arm.items()},
        'shared_responses': [{'physical_id': i, 'used_by_arms': arms} for i, arms in sorted(users.items()) if len(arms) > 1],
        'per_batch_observed_response_footprints': trajectories,
        'formal_dispatches_not_yet_associated_with_settled_arm_evidence': sorted(formal - set(users)),
        'recovered_original_exception_cost_references': recovered,
        'interpretation': 'A response used by several arms is charged once in actual dispatch totals. Per-arm footprints describe observed consumed responses, including inherited cache entries, and must not be added or called independent standalone spending. No first-consumer cache advantage is claimed as a method cost gain.',
        'teacher_and_GPU_actual_cash_invoices_unavailable': True,
        'CLI_output_and_reasoning_token_fields_not_added_together': True}
    (REPORT / 'formal_cost_footprints.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'actual_formal_physical': len(formal), 'arms_with_settled_evidence': sum(bool(v) for v in by_arm.values()),
                      'shared_responses': len(result['shared_responses']), 'new_model_calls': 0}))


if __name__ == '__main__':main()
