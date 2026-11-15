"""Fit the collected complete C language against original TRAIN constraints.

No model client, no changed observations, no DEV/TEST. Cache scores by actual
source output so redundant subsets do not repeat native worker executions.
"""
from copy import deepcopy
from itertools import combinations
import json
import time

from experiments import legal_skill_evolution_source_operator_alignment as aligned
from experiments import legal_skill_evolution_C_owner_scope_repair as owner
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute

current = aligned.current
OUT = current.ROOT / 'artifacts/legal_skill_evolution_C_TRAIN_fit_owner_scope_20261115'


def run():
    before = aligned.ledger()
    assert not any(role == 'executor' and status == 'reserved' for role, status, _ in before)
    p = current.read(current.OUT / 'protocol.json')
    base = current.read(owner.OUT / 'candidate.json')
    observations = {s: current.read(owner.OUT / 'observations' / (digest(s) + '.json')) for s in p['sources']}
    names = [r['id'] for r in base['language']['rules']]
    costs = {r['id']: r['cost'] for r in base['language']['rules']}
    all_rows = {s: current.read(owner.OUT / 'all_rules' / (digest(s) + '.json')) for s in p['sources']}
    cache = {(s, digest(r['source_output'])): r for s, r in all_rows.items()}
    cache.update({(s, digest(r['source_output'])): r
        for s in p['sources'] for r in [current.read(aligned.OUT / 'C/NoFit' / (digest(s) + '.json'))]})
    # Known hard failures are evaluated first. Their exact source constraints
    # remain unchanged; this is fail-fast evaluation, not a changed objective.
    order = sorted(p['sources'], key=lambda s: (all_rows[s]['hard_source_pass'], p['sources'].index(s)))
    output_rules = [r['id'] for r in base['language']['rules']
                    if base['language']['signatures'][r['head']['predicate']]['kind'] == 'output']
    candidates = [names, base['selected_rule_ids'], []]
    permission_rules = [r['id'] for r in base['language']['rules']
                        if r['head']['predicate'] in ('compose_permission', 'compose_embedded_permission')]
    # Several rules can independently reintroduce the same wrong permission.
    # Single deletions cannot establish that no valid G exists. Search this
    # small, actual conflicting output family jointly before other deletions.
    for count in range(1, len(permission_rules) + 1):
        for removed in combinations(permission_rules, count):
            candidates.append([n for n in names if n not in removed])
    candidates += [[n for n in names if n != remove] for remove in output_rules]
    candidates += [[n for n in names if n != remove] for remove in names if remove not in output_rules]
    trials, seen, best = [], set(), None
    started = time.monotonic()
    for ids in candidates:
        key = tuple(sorted(ids))
        if key in seen:
            continue
        if trials and time.monotonic() - started >= p['fitting_wall_time_seconds']:
            break
        seen.add(key)
        library = deepcopy(base)
        library['selected_rule_ids'] = list(key)
        rows = []
        for sid in order:
            output = execute(library, observations[sid])['source_output']
            identity = (sid, digest(output))
            if identity not in cache:
                cache[identity] = current.assess(library, observations[sid], sid)
            rows.append(cache[identity])
            if not rows[-1]['hard_source_pass']:
                break
        valid = len(rows) == len(order) and all(r['hard_source_pass'] for r in rows)
        receipt = {'rule_ids': list(key), 'source_rows_checked': len(rows),
                   'hard_source_pass': valid,
                   'native_correct': sum(r['native_correct'] for r in rows) if valid else None,
                   'first_violation': next((r for r in rows if not r['hard_source_pass']), None)}
        trials.append(receipt)
        immutable_json(OUT / 'trials' / (digest(key) + '.json'), receipt)
        if valid:
            rank = (-receipt['native_correct'], sum(costs[n] for n in key), len(key), key)
            if best is None or rank < best[0]:
                best = rank, deepcopy(library), deepcopy(rows)
                print(json.dumps({'source_valid_candidate': True, 'native_correct': -rank[0],
                                  'selected_rules': len(key), 'trials': len(trials)}), flush=True)
    after = aligned.ledger()
    assert [r for r in after if r[0] == 'executor'] == [r for r in before if r[0] == 'executor']
    receipt = {'trials': trials, 'wall_time_seconds': time.monotonic() - started,
        'optimization_complete': False, 'new_model_calls': 0, 'ledger_before': before,
        'ledger_after': after, 'original_24_TRAIN_only': True, 'DEV_TEST_accessed': False,
        'goal_complete': False}
    if best:
        _, library, rows = best
        immutable_json(OUT / 'selected.json', {'library': library, 'selected_only_on_TRAIN': True})
        immutable_json(OUT / 'source_rows.json', rows)
        receipt.update(native_correct=sum(r['native_correct'] for r in rows), native_total=96,
            unresolved=sum(r['unresolved'] for r in rows), all_partial_source_checks_passed=True,
            not_a_generalization_or_contribution_result=True)
    else:
        receipt['reason'] = 'No fully source-valid G found within existing deterministic fit budget'
    immutable_json(OUT / 'result.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'trials'}), flush=True)


if __name__ == '__main__':
    run()
