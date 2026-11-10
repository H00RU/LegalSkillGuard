"""Direct recovery from scalar queries; no truth model or program enumeration.

The public DSL is GROUP BY an arbitrary subset of feature keys (or record ID),
sum, one C cap, exclusion before/after that cap, and an optional B outer cap.
Known C/B values are an explicit information assumption, not discovered gold.
Only standard-library exact rational arithmetic is used.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations


@dataclass(frozen=True)
class PublicSpec:
    features: tuple
    cap: F = F(7)
    outer_value: F = F(12)
    exclusion_allowed: bool = True
    total_bound: F | None = None

    @property
    def n(self):
        return len(self.features)

    @property
    def d(self):
        return len(self.features[0])


def case(spec, entries):
    out = [(F(0), F(0)) for _ in spec.features]
    for i, t, e in entries:
        out[i] = (F(t), F(e))
    return tuple(out)


def key_partition(spec, keys):
    names = {}
    labels = []
    for features in spec.features:
        value = tuple(features[k] for k in keys)
        names.setdefault(value, len(names))
        labels.append(names[value])
    return tuple(labels)


class UnsupportedDomain(Exception):
    pass


def recover(spec, oracle):
    try:
        return _recover_impl(spec, oracle)
    except UnsupportedDomain as exc:
        return dict(status='unsupported_domain', reason=str(exc),
                    complete_programs_enumerated=0,
                    warning='No illegal oracle call was submitted; any earlier legal '
                            'queries remain charged. This is not successful recovery.')


def _recover_impl(spec, oracle):
    """Receive public schema plus query-only oracle; return partial structure.

    No access to a candidate model list, reference AST, or hidden parameters.
    Arithmetic decision count is reported separately from oracle calls.
    """
    c, b = spec.cap, spec.outer_value
    assert c > 0 and b > 0
    ops = 0
    certificates = []
    unknown = []
    expression = None

    def ask(entries, purpose, isolation):
        nonlocal ops
        x = case(spec, entries)
        if spec.total_bound is not None and sum(t for t, e in x) > spec.total_bound:
            raise UnsupportedDomain(f'{purpose} exceeds declared total bound '
                                    f'{spec.total_bound}; current analytic planner '
                                    'does not search a smaller separating probe.')
        if any(t < 0 or e < 0 or e > t for t, e in x):
            raise UnsupportedDomain('Analytic probe is outside the nonnegative domain.')
        if not spec.exclusion_allowed and any(e for t, e in x):
            raise UnsupportedDomain('Analytic probe requires a forbidden exclusion.')
        ops += 1
        return oracle.query(x, purpose, isolation)

    def done(partition, order, outer, note=None):
        if note:
            certificates.append(note)
        return dict(partition=list(partition), order=order, outer=outer,
                    reusable_key_expression=expression,
                    unresolved=unknown, certificates=certificates,
                    local_decisions=ops, complete_programs_enumerated=0)

    # Public-domain proof, not inferred from absence of a counterexample.
    if spec.total_bound is not None and spec.total_bound <= min(c, b):
        unknown.extend(['scope', 'order', 'outer'])
        return done([0] * spec.n, 'before', False,
                    'On this declared nonnegative bounded domain all caps are inactive; '
                    'all structures equal sum(T-E).')

    outer_known = None
    if spec.exclusion_allowed:
        q = min(c, b) / 2
        e = c - q
        y = ask([(0, c + e, e)], 'identify_order',
                'Only one active record: scope irrelevant. AFTER gives q < B; '
                'BEFORE gives C or B, both > q; no assumptions about hidden scope/order.')
        if y == q:
            order = 'after'
        elif y in (c, min(c, b)):
            order = 'before'
            if b < c:
                outer_known = y == b
        else:
            return dict(status='outside_model_class', response=str(y),
                        complete_programs_enumerated=0, local_decisions=ops)
    else:
        order = 'before'  # Canonical representative of the equivalent orders.
        unknown.append('order: no nonzero exclusions in declared domain')
        if b < c:
            y = ask([(0, c, 0)], 'identify_low_outer',
                    'Single active record and E=0 remove scope and order dependence.')
            if y not in (b, c):
                return dict(status='outside_model_class', response=str(y),
                            complete_programs_enumerated=0, local_decisions=ops)
            outer_known = y == b

    if order == 'before' and outer_known is True and b <= c:
        unknown.append('scope: all partitions are behaviorally equivalent')
        return done([0] * spec.n, order, True,
                    'For E_i<=T_i and B<=C, min(B,sum_g min(C,T_g-E_g)) '
                    '= min(B,sum_i(T_i-E_i)); partition is unobservable.')

    # Scope probes are derived from PUBLIC constants and the observed order.
    # They do not invoke guessed full programs or use the hidden truth.
    if order == 'after':
        q = min(c, b) / 4
        pair_t, pair_e = c, c - q
        same, different = F(0), 2*q
        isolation = ('Observed AFTER order: two records (C,C-q) give 0 if shared, '
                     '2q if separate; 2q<=B/2, so optional outer cap is inactive.')
    else:
        if outer_known is False:
            pair_t = c * F(3, 4)
        elif b > c:
            pair_t = (c + min(b, 2*c)) / 4
        else:  # B=C: either globally capped or uncapped separate groups.
            pair_t = c
        pair_e = F(0)
        same, different = c, 2*pair_t
        isolation = ('E=0 makes order irrelevant. For B>C, C<2a<B; '
                     'for known absent outer, no outer interference. B=C handled '
                     'as an explicit observational equivalence, not assumed isolated.')

    def shared(i, j):
        nonlocal ops
        y = ask([(i, pair_t, pair_e), (j, pair_t, pair_e)],
                f'scope_pair_{i}_{j}', isolation)
        ops += 1
        if y == same:
            return True
        if y == different:
            return False
        raise ValueError(f'Outside model response to scope probe: {y}')

    duplicate = next(((i, j) for i, j in combinations(range(spec.n), 2)
                      if spec.features[i] == spec.features[j]), None)
    selected = []
    if duplicate is not None and not shared(*duplicate):
        partition = tuple(range(spec.n))
        expression = dict(kind='record_id')
        certificates.append('Identical feature tuples split: only record-ID grouping '
                            'in the declared language can do this.')
    else:
        # Fast path for independently manipulable feature keys.
        unit_pairs = []
        for k in range(spec.d):
            pair = next(((i, j) for i, j in combinations(range(spec.n), 2)
                         if [z for z in range(spec.d)
                             if spec.features[i][z] != spec.features[j][z]] == [k]), None)
            unit_pairs.append(pair)
        if all(p is not None for p in unit_pairs):
            for k, pair in enumerate(unit_pairs):
                if not shared(*pair):
                    selected.append(k)
            partition = key_partition(spec, selected)
            expression = dict(kind='group_by_keys', key_indices=selected)
            certificates.append('Independent single-key interventions recover key '
                                'membership directly; no subset enumeration.')
        else:
            # Correlated features: recover the observable record partition;
            # do NOT invent a unique source-level key expression.
            unknown.append('scope-key expression: features are correlated')
            parent = list(range(spec.n))

            def find(i):
                while parent[i] != i:
                    i = parent[i]
                return i

            cache_duplicate = duplicate
            for i, j in combinations(range(spec.n), 2):
                if cache_duplicate == (i, j) or shared(i, j):
                    parent[find(j)] = find(i)
            renumber = {}
            partition_list = []
            for i in range(spec.n):
                root = find(i)
                renumber.setdefault(root, len(renumber))
                partition_list.append(renumber[root])
            partition = tuple(partition_list)

    if order == 'before' and b == c and len(set(partition)) == 1:
        expression = None
        unknown.extend(['scope-or-outer: outer cap masks every partition',
                        'outer: global inner cap already yields the same function'])
        return done(partition, order, False,
                    'All scope probes collapsed at C=B; global/no-outer is a '
                    'canonical behavior equivalent to every partition with outer cap.')
    if order == 'before' and b == c:
        outer_known = False  # A separating response > C certifies no outer cap.

    if outer_known is not None:
        return done(partition, order, outer_known)

    representatives = list(dict.fromkeys(partition))
    group_slots = [partition.index(g) for g in representatives]
    if len(group_slots) * c <= b:
        unknown.append('outer: never active on declared record universe')
        return done(partition, order, False,
                    'Number of possible groups times C <= B; optional outer cap '
                    'cannot alter outputs on this declared universe.')
    count = int(b // c) + 1
    y = ask([(i, c, 0) for i in group_slots[:count]], 'identify_outer',
            'Confirmed distinct groups, E=0; each contributes C. Compare B with k*C.')
    if y == b:
        outer = True
    elif y == count*c:
        outer = False
    else:
        return dict(status='outside_model_class', response=str(y),
                    complete_programs_enumerated=0, local_decisions=ops)
    return done(partition, order, outer)
