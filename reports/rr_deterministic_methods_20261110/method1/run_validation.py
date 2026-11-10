"""Reproduce all deterministic comparisons. Run: python run_validation.py

No third-party dependencies, model calls, network access, or repository edits.
All reference models here are declared synthetic DSL instances, not legal gold.
"""
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import random
import statistics
import time

from direct_recovery import PublicSpec, case, key_partition, recover

ROOT = Path(__file__).resolve().parent
SCALE = 8
EVALUATIONS = Counter()
PHASE = 'learned_and_surviving_program_verification'


@contextmanager
def phase(name):
    global PHASE
    old = PHASE
    PHASE = name
    try:
        yield
    finally:
        PHASE = old


def encode(x):
    ans = []
    for i, (t, e) in enumerate(x):
        t8, e8 = F(t)*SCALE, F(e)*SCALE
        assert t8.denominator == e8.denominator == 1
        if t8 or e8:
            ans.append((i, int(t8), int(e8)))
    return tuple(ans)


def evaluate(partition, order, outer, spec, x):
    """Exact integer-unit DSL semantics; x contains only nonzero records."""
    EVALUATIONS[PHASE] += 1
    groups = {}
    for i, t, e in x:
        g = partition[i]
        a, z = groups.get(g, (0, 0))
        groups[g] = (a+t, z+e)
    c, b = int(spec.cap*SCALE), int(spec.outer_value*SCALE)
    if order == 'before':
        y = sum(min(c, max(0, t-e)) for t, e in groups.values())
    else:
        y = sum(max(0, min(c, t)-e) for t, e in groups.values())
    return min(b, y) if outer else y


@dataclass(frozen=True)
class Model:
    scope: str
    partition: tuple
    order: str
    outer: bool


def language(spec):
    # Public hypothesis language, generated without knowing the hidden model.
    scopes = []
    for bits in product((0, 1), repeat=spec.d):
        keys = tuple(i for i, flag in enumerate(bits) if flag)
        scopes.append(('keys:' + ','.join(map(str, keys)), key_partition(spec, keys)))
    scopes.append(('record', tuple(range(spec.n))))
    return [Model(s, p, order, outer) for s, p in scopes
            for order in ('before', 'after') for outer in (False, True)]


def valid(spec, x):
    if len(x) != spec.n:
        return False
    if any(t < 0 or e < 0 or e > t for t, e in x):
        return False
    if not spec.exclusion_allowed and any(e for t, e in x):
        return False
    return spec.total_bound is None or sum(t for t, e in x) <= spec.total_bound


def make_pool(spec, original_full_grid=False):
    """Fixed legal pool, available equally to every method before observations.

    Original task includes ALL 1296 old finite inputs plus public algebraic
    probes. Extensions include all pairs of the declared numeric signatures,
    singletons, and public scope activation contexts. No truth-dependent pool.
    """
    c, b = spec.cap, spec.outer_value
    q = min(c, b)/2
    a = (c+min(b, 2*c))/4
    small_q = min(c, b)/4
    values = {(F(0), F(0)), (F(4), F(0)), (F(7), F(0)),
              (F(8), F(0)), (F(10), F(4)), (c, F(0)),
              (c+c-q, c-q), (c, c-small_q), (a, F(0)),
              (c*F(3, 4), F(0)), (F(1), F(0)), (F(1), F(1))}
    if not spec.exclusion_allowed:
        values = {(t, e) for t, e in values if e == 0}
    values = sorted(values)
    pool = set()

    def add(x):
        if valid(spec, x):
            pool.add(x)

    add(case(spec, []))
    for i in range(spec.n):
        for t, e in values:
            add(case(spec, [(i, t, e)]))
    for i, j in combinations(range(spec.n), 2):
        for (t, e), (u, v) in product(values, repeat=2):
            add(case(spec, [(i, t, e), (j, u, v)]))
    # A group activation input for every PUBLIC permitted key expression.
    for model in language(spec):
        reps = [model.partition.index(g) for g in dict.fromkeys(model.partition)]
        for count in {len(reps), min(len(reps), int(b//c)+1)}:
            add(case(spec, [(i, c, 0) for i in reps[:count]]))
    if original_full_grid:
        original = ((0, 0), (4, 0), (4, 4), (8, 0), (8, 8), (10, 4))
        for x in product(original, repeat=4):
            add(tuple((F(t), F(e)) for t, e in x))
    if spec.total_bound is not None:
        for x in product(((0, 0), (1, 0), (1, 1)), repeat=spec.n):
            add(tuple((F(t), F(e)) for t, e in x))
    return sorted(pool)


def make_holdout(spec):
    # Fresh deterministic multi-record stress inputs; never passed to learners.
    rng = random.Random(20261110)
    vals = [(F(0), F(0)), (F(2), F(0)), (F(6), F(1)),
            (F(13), F(9)), (F(20), F(3)), (F(5), F(5))]
    if not spec.exclusion_allowed:
        vals = [(t, F(0)) for t, _ in vals]
    if spec.total_bound is not None:
        return [x for x in product(((F(0), F(0)), (F(1), F(0)),
                                    (F(1), F(1))), repeat=spec.n) if valid(spec, x)]
    return [tuple(rng.choice(vals) for _ in range(spec.n)) for _ in range(512)]


class QueryOracle:
    """Query-only capability. Recovery never receives the hidden Model object."""
    __slots__ = ('__fn', 'spec', 'pool_set', 'ledger')

    def __init__(self, fn, spec, pool):
        self.__fn = fn
        self.spec = spec
        self.pool_set = pool if isinstance(pool, frozenset) else frozenset(pool)
        self.ledger = []

    def query(self, x, purpose='baseline', isolation=''):
        assert valid(self.spec, x), 'Illegal probe'
        assert x in self.pool_set, 'Probe outside predeclared common query pool'
        with phase('learner_acquisition_truth'):
            y = self.__fn(encode(x))
        self.ledger.append(dict(number=len(self.ledger)+1, x=x, y=y,
                                purpose=purpose, isolation=isolation))
        return F(y, SCALE)


def json_case(x):
    return [[str(t), str(e)] for t, e in x]


def stringify_ledger(oracle):
    return [dict(number=q['number'], input=json_case(q['x']),
                 output=str(F(q['y'], SCALE)), purpose=q['purpose'],
                 isolation=q['isolation']) for q in oracle.ledger]


def same_probes(models, spec, oracle, transcript):
    keep = list(range(len(models)))
    evaluations = 0
    for entry in transcript:
        y = oracle.query(entry['x'], 'same_probe_constraint') * SCALE
        x = encode(entry['x'])
        new = []
        for i in keep:
            m = models[i]
            evaluations += 1
            if evaluate(m.partition, m.order, m.outer, spec, x) == y:
                new.append(i)
        keep = new
    return keep, evaluations


def greedy_active(class_rows, pool, oracle):
    keep = list(range(len(class_rows)))
    scores = 0
    while len(keep) > 1:
        best = None
        for q in range(len(pool)):
            counts = Counter(class_rows[i][q] for i in keep)
            scores += len(keep)
            # Max expected eliminated class pairs (Gini), then smallest index.
            key = (sum(n*n for n in counts.values()), q)
            if best is None or key < best[0]:
                best = (key, q)
        if best[0][0] == len(keep)**2:
            raise AssertionError('Classes should be distinct on the fixed pool')
        q = best[1]
        y = oracle.query(pool[q], 'max_disagreement') * SCALE
        keep = [i for i in keep if class_rows[i][q] == y]
    return keep[0], scores


def optimal_policy(class_rows):
    """Exact minimax adaptive decision tree on the declared finite pool.

    Distinct behavioral classes, not syntactic variants, have uniform weights.
    Break worst-depth ties by exact expected query count.
    """
    k = len(class_rows)
    tests = {}
    for q in range(len(class_rows[0])):
        buckets = {}
        for i in range(k):
            buckets.setdefault(class_rows[i][q], 0)
            buckets[class_rows[i][q]] |= 1 << i
        signature = tuple(sorted(buckets.values()))
        if len(signature) > 1:
            tests.setdefault(signature, q)
    decisions = {}
    considered = 0

    @lru_cache(None)
    def dp(mask):
        nonlocal considered
        if mask.bit_count() <= 1:
            return 0, F(0)
        best = None
        for parts, q in tests.items():
            children = [part & mask for part in parts if part & mask]
            considered += 1
            if len(children) <= 1:
                continue
            costs = [dp(ch) for ch in children]
            worst = 1+max(v[0] for v in costs)
            expected = 1+sum(F(ch.bit_count(), mask.bit_count())*v[1]
                             for ch, v in zip(children, costs))
            score = worst, expected, q
            if best is None or score < best[0]:
                best = (score, q)
        assert best is not None
        decisions[mask] = best[1]
        return best[0][0], best[0][1]

    full = (1 << k)-1
    optimum = dp(full)
    return decisions, dict(behavioral_classes=k, worst_queries=optimum[0],
                           expected_queries_uniform_class=str(optimum[1]),
                           dp_states=dp.cache_info().currsize,
                           partition_tests_considered=considered,
                           distinct_query_partitions=len(tests))


def follow_optimal(class_rows, decisions, pool, oracle):
    mask = (1 << len(class_rows))-1
    while mask.bit_count() > 1:
        q = decisions[mask]
        y = oracle.query(pool[q], 'optimal_minimax_tree') * SCALE
        mask = sum(1 << i for i in range(len(class_rows))
                   if mask & (1 << i) and class_rows[i][q] == y)
    return mask.bit_length()-1


def audit_isolation(models, spec, transcript):
    keep = list(range(len(models)))
    violations = []
    checks = 0
    explicit_equal_cap_cases = 0
    for entry in transcript:
        x = encode(entry['x'])
        purpose = entry['purpose']
        if purpose.startswith('scope_pair'):
            if spec.outer_value == spec.cap and any(models[i].order == 'before' for i in keep):
                explicit_equal_cap_cases += 1
            else:
                for i in keep:
                    m = models[i]
                    checks += 1
                    with_outer = evaluate(m.partition, m.order, m.outer, spec, x)
                    without = evaluate(m.partition, m.order, False, spec, x)
                    if with_outer != without:
                        violations.append((purpose, i, 'non_target_outer_not_isolated'))
        if purpose == 'identify_order':
            outputs = {z: set() for z in ('before', 'after')}
            for i in keep:
                m = models[i]
                outputs[m.order].add(evaluate(m.partition, m.order, m.outer, spec, x))
            checks += 1
            if outputs['before'] & outputs['after']:
                violations.append((purpose, 'orders_not_separated'))
        keep = [i for i in keep if evaluate(models[i].partition, models[i].order,
                                           models[i].outer, spec, x) == entry['y']]
    return dict(candidate_context_checks=checks, violations=violations,
                explicit_equal_cap_quotient_probes=explicit_equal_cap_cases)


def run_suite(name, spec, original=False):
    start = time.perf_counter()
    count_start = EVALUATIONS.copy()
    models = language(spec)
    pool = make_pool(spec, original)
    pool_set = frozenset(pool)
    encoded_pool = [encode(x) for x in pool]
    holdout = [encode(x) for x in make_holdout(spec)]
    pre_start = time.perf_counter()
    with phase('candidate_precomputation'):
        rows = [tuple(evaluate(m.partition, m.order, m.outer, spec, x) for x in encoded_pool)
                for m in models]
    pre_seconds = time.perf_counter()-pre_start
    rep_by_row = {}
    for i, row in enumerate(rows):
        rep_by_row.setdefault(row, i)
    reps = list(rep_by_row.values())
    class_rows = [rows[i] for i in reps]
    decisions = optimum = None
    dp_seconds = 0
    if len(reps) <= 12:
        tick = time.perf_counter()
        decisions, optimum = optimal_policy(class_rows)
        dp_seconds = time.perf_counter()-tick
    runs = []
    ledgers = []
    for model_id, hidden in enumerate(models):
        def fn(x):
            return evaluate(hidden.partition, hidden.order, hidden.outer, spec, x)

        with phase('reference_stress_scoring'):
            truth_holdout = [fn(x) for x in holdout]
        run = dict(model_id=model_id, hidden=dict(scope=hidden.scope,
                   order=hidden.order, outer=hidden.outer), methods={})
        oracle = QueryOracle(fn, spec, pool_set)
        tick = time.perf_counter()
        learned = recover(spec, oracle)
        direct_seconds = time.perf_counter()-tick
        assert 'status' not in learned, learned
        p = tuple(learned['partition'])
        pred_pool = tuple(evaluate(p, learned['order'], learned['outer'], spec, x)
                          for x in encoded_pool)
        pred_holdout = [evaluate(p, learned['order'], learned['outer'], spec, x) for x in holdout]
        direct_ok = pred_pool == rows[model_id] and pred_holdout == truth_holdout
        with phase('isolation_audit_candidate_simulation'):
            iso = audit_isolation(models, spec, oracle.ledger)
        assert not iso['violations'], iso
        run['methods']['direct'] = dict(correct=direct_ok, queries=len(oracle.ledger),
            seconds=direct_seconds, candidate_evaluations=0,
            local_decisions=learned['local_decisions'], result=learned, isolation=iso)
        transcript = list(oracle.ledger)
        ledgers.append(dict(model_id=model_id, method='direct', queries=stringify_ledger(oracle)))

        oracle = QueryOracle(fn, spec, pool_set)
        tick = time.perf_counter()
        with phase('same_probe_candidate_filtering'):
            keep, calls = same_probes(models, spec, oracle, transcript)
        relation_seconds = time.perf_counter()-tick
        survivor_good = all(rows[i] == rows[model_id] and
             [evaluate(models[i].partition, models[i].order, models[i].outer, spec, x)
              for x in holdout] == truth_holdout for i in keep)
        run['methods']['same_probe_constraints'] = dict(correct=survivor_good,
            queries=len(oracle.ledger), seconds=relation_seconds,
            candidate_evaluations=calls, survivors=len(keep),
            correct_model_retained=model_id in keep)
        ledgers.append(dict(model_id=model_id, method='same_probe_constraints',
                            queries=stringify_ledger(oracle)))

        oracle = QueryOracle(fn, spec, pool_set)
        tick = time.perf_counter()
        winner, cells = greedy_active(class_rows, pool, oracle)
        learner_seconds = time.perf_counter()-tick
        chosen = models[reps[winner]]
        correct = (class_rows[winner] == rows[model_id] and
            [evaluate(chosen.partition, chosen.order, chosen.outer, spec, x)
             for x in holdout] == truth_holdout)
        run['methods']['max_disagreement'] = dict(correct=correct,
            queries=len(oracle.ledger), seconds=learner_seconds,
            table_cells_scored=cells, precomputation_shared=True)
        ledgers.append(dict(model_id=model_id, method='max_disagreement',
                            queries=stringify_ledger(oracle)))
        if decisions is not None:
            oracle = QueryOracle(fn, spec, pool_set)
            tick = time.perf_counter()
            winner = follow_optimal(class_rows, decisions, pool, oracle)
            learner_seconds = time.perf_counter()-tick
            chosen = models[reps[winner]]
            correct = class_rows[winner] == rows[model_id] and all(
                evaluate(chosen.partition, chosen.order, chosen.outer, spec, x) == y
                for x, y in zip(holdout, truth_holdout))
            run['methods']['optimal_tree'] = dict(correct=correct,
                queries=len(oracle.ledger), seconds=learner_seconds,
                precomputation_shared=True)
            ledgers.append(dict(model_id=model_id, method='optimal_tree',
                                queries=stringify_ledger(oracle)))
        runs.append(run)
    summaries = {}
    for method in runs[0]['methods']:
        r = [run['methods'][method] for run in runs]
        summaries[method] = dict(correct=sum(v['correct'] for v in r), total=len(r),
            query_min=min(v['queries'] for v in r), query_mean=statistics.mean(v['queries'] for v in r),
            query_max=max(v['queries'] for v in r),
            seconds_total=sum(v['seconds'] for v in r),
            candidate_evaluations=sum(v.get('candidate_evaluations', 0) for v in r),
            table_cells_scored=sum(v.get('table_cells_scored', 0) for v in r))
    data = dict(name=name, public_spec=dict(features=spec.features, cap=str(spec.cap),
        optional_outer_value=str(spec.outer_value), exclusions=spec.exclusion_allowed,
        total_bound=str(spec.total_bound) if spec.total_bound is not None else None),
        model_count=len(models), behavioral_classes_on_pool=len(reps), query_pool_size=len(pool),
        additional_hidden_stress_inputs=len(holdout),
        common_precomputation=dict(candidate_evaluations=len(models)*len(pool),
            seconds=pre_seconds, used_by=['max_disagreement', 'optimal_tree'],
            not_used_by=['direct', 'same_probe_constraints']),
        exact_minimax=optimum, exact_minimax_seconds=dp_seconds,
        summaries=summaries, runs=runs, suite_seconds=time.perf_counter()-start,
        all_dsl_evaluations_by_category=dict(EVALUATIONS-count_start))
    (ROOT/f'{name}_results.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    (ROOT/f'{name}_ledger.json').write_text(json.dumps(ledgers, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(suite=name, models=len(models), classes=len(reps),
                         pool=len(pool), results=summaries), ensure_ascii=False), flush=True)
    return data


def main():
    suites = [
        ('original12', PublicSpec(((0,), (0,), (1,), (1,))), True),
        ('keys2', PublicSpec(tuple(product((0, 1), repeat=2))+((0, 0),)), False),
        ('keys3', PublicSpec(tuple(product((0, 1), repeat=3))+((0, 0, 0),)), False),
        ('keys4', PublicSpec(tuple(product((0, 1), repeat=4))+((0, 0, 0, 0),)), False),
        ('low_outer', PublicSpec(((0,), (0,), (1,), (1,)), outer_value=F(5)), True),
        ('equal_outer', PublicSpec(((0,), (0,), (1,), (1,)), outer_value=F(7)), True),
        ('high_outer', PublicSpec(((0,), (0,), (1,), (1,)), outer_value=F(100)), True),
        ('correlated_keys', PublicSpec(((0, 0), (0, 0), (1, 1), (1, 1))), True),
        ('no_exclusions', PublicSpec(((0,), (0,), (1,), (1,)),
                                    outer_value=F(5), exclusion_allowed=False), True),
        ('below_all_caps', PublicSpec(((0,), (0,), (1,), (1,)),
                                      outer_value=F(5), total_bound=F(4)), False),
    ]
    results = [run_suite(*suite) for suite in suites]
    boundary_checks = []
    for bound in (F(8), F(12)):
        spec = PublicSpec(((0,), (0,), (1,), (1,)), total_bound=bound)
        pool = frozenset(make_pool(spec))
        for model in language(spec):
            oracle = QueryOracle(lambda x, m=model: evaluate(m.partition, m.order,
                                 m.outer, spec, x), spec, pool)
            result = recover(spec, oracle)
            boundary_checks.append(dict(total_bound=str(bound), scope=model.scope,
                order=model.order, outer=model.outer, result=result,
                queries=stringify_ledger(oracle)))
    assert all(c['result'].get('status') == 'unsupported_domain'
               and len(c['queries']) == 0 for c in boundary_checks if c['total_bound'] == '8')
    (ROOT/'domain_boundary_regressions.json').write_text(
        json.dumps(boundary_checks, indent=2), encoding='utf-8')
    acquisition_total = sum(m['queries'] for r in results for run in r['runs']
                            for m in run['methods'].values())
    acquisition_total += sum(len(c['queries']) for c in boundary_checks)
    assert acquisition_total == EVALUATIONS['learner_acquisition_truth']
    stress_total = sum(r['model_count']*r['additional_hidden_stress_inputs'] for r in results)
    assert stress_total == EVALUATIONS['reference_stress_scoring']
    report = dict(purpose='Deterministic, synthetic, same-information algorithm audit',
        model_calls=0, native_legal_gold_used=False, test_oracle_claim=False,
        tests_are_finite=True, old_project_test_data_read=False,
        exact_all_dsl_evaluations=dict(EVALUATIONS),
        ledger_reconciled_acquisition_calls=acquisition_total,
        independently_counted_reference_stress_evaluations=stress_total,
        intermediate_domain_guard=dict(cases=len(boundary_checks),
            unsupported=sum(c['result'].get('status') == 'unsupported_domain'
                            for c in boundary_checks), illegal_queries_submitted=0),
        source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (ROOT/'direct_recovery.py', ROOT/'run_validation.py')},
        suites=[{k: v for k, v in r.items() if k != 'runs'} for r in results])
    (ROOT/'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert all(s['correct'] == s['total'] for r in results for s in r['summaries'].values())


if __name__ == '__main__':
    main()
