"""Finite closure of the existing class-reader operations, plus fair controls.

Functions act on class values, not literal source spans or whole bindings. The
closure, EM and factor control are standard machinery; learned weights alone
are data-dependent. No frozen legacy implementation is changed.
"""
from collections import deque
from functools import lru_cache
from itertools import product
import math
import numpy as np

from .semantic_learning import H, Y, PRIMITIVES, transform

POST = {'negate': (1, 0, 2), 'unknown_as_false': (0, 1, 0),
        'unknown_as_true': (0, 1, 1), 'erase': (2, 2, 2)}


def primitive_functions():
    return [{'table': [transform(h, (name, 'self', 'self', 'self'))[0] for h in H],
             'cost': int(name != 'self'), 'expression': name} for name in PRIMITIVES]


def function_closure():
    original = primitive_functions()
    known = {tuple(f['table']): f for f in original}
    queue = deque(known)
    while queue:
        table = queue.popleft(); f = known[table]
        for name, post in POST.items():
            target = tuple(post[v] for v in table)
            candidate = {'table': list(target), 'cost': f['cost'] + 1,
                         'expression': name + '(' + f['expression'] + ')'}
            if target not in known or candidate['cost'] < known[target]['cost']:
                known[target] = candidate; queue.append(target)
    original_tables = {tuple(f['table']) for f in original}
    extra = sorted((v for k, v in known.items() if k not in original_tables),
                   key=lambda f: (f['cost'], f['expression']))
    return original + extra


def _validate(rows):
    if not rows:
        raise ValueError('Actual fully observed TRAIN trajectories are required')
    for r in rows:
        if len(r['h']) != 2 or len(r['y']) != 4:
            raise ValueError('Expected two truth slots and four observed answer slots')
        if any(type(v) is not int or v not in (0, 1, 2) for v in r['h'] + r['y']):
            raise ValueError('Class2 is observed unknown; None is not a supplied answer')
        if not math.isfinite(r['weight']) or r['weight'] <= 0:
            raise ValueError('Positive finite source weights are required')


def _local_indices(h):
    return [H.index((h[i % 2], h[1 - i % 2])) for i in range(4)]


@lru_cache(maxsize=2)
def _operators(n):
    value = np.array(list(product(range(n), repeat=4)), dtype=np.int16)
    value.setflags(write=False)
    return value


def _em(like, source_weights, prior):
    mixture = prior.copy()
    for _ in range(100):
        posterior = like * mixture[None, :]
        posterior /= posterior.sum(axis=1, keepdims=True)
        mixture = (posterior * source_weights[:, None]).sum(axis=0) + prior
        mixture /= mixture.sum()
    return mixture


def fit_channels(rows, grammar=None):
    _validate(rows)
    grammar = function_closure() if grammar is None else grammar
    tables = np.array([f['table'] for f in grammar], dtype=np.int8)
    costs = np.array([f['cost'] for f in grammar])
    operators = _operators(len(grammar))
    prior = np.exp(-.5 * costs[operators].sum(axis=1)); prior /= prior.sum()
    local_prior = np.exp(-.5 * costs); local_prior /= local_prior.sum()

    def fit(actual):
        weights = np.array([r['weight'] for r in actual])
        predictions = [tables[operators, _local_indices(r['h'])] for r in actual]
        like = .95 * np.array([np.all(p == r['y'], axis=1) for p, r in zip(predictions, actual)]) + .05 / 81
        joint = _em(like, weights, prior)
        factors = []
        for i in range(4):
            l = np.array([[.95 * int(tables[j, _local_indices(r['h'])[i]] == r['y'][i]) + .05 / 3
                           for j in range(len(grammar))] for r in actual])
            factors.append(_em(l, weights, local_prior).tolist())
        return {'joint': joint.tolist(), 'factors': factors}

    contexts = sorted({tuple(r['context']) for r in rows})
    return {'grammar': grammar, 'global': fit(rows),
            'contexts': {''.join(map(str, c)): fit([r for r in rows if r['context'] == list(c)]) for c in contexts},
            'settings': {'iterations': 100, 'residual_mass': .05, 'complexity_rate': .5,
                         'prior_pseudocount_total': 1, 'hyperparameters_scanned': False},
            'training_rows': len(rows), 'training_mothers': sorted({r['mother'] for r in rows})}


def forecasts(model, h, context):
    grammar = model['grammar']; n = len(grammar)
    tables = np.array([f['table'] for f in grammar], dtype=np.int8)
    operators = _operators(n)
    fitted = model['contexts'].get(''.join(map(str, context)), model['global'])
    predictions = tables[operators, _local_indices(h)]
    yi = predictions @ np.array([27, 9, 3, 1])
    joint = np.full(81, .05 / 81)
    joint += .95 * np.bincount(yi, weights=np.array(fitted['joint']), minlength=81)
    local = []
    for i in range(4):
        values = tables[:, _local_indices(h)[i]]
        local.append(.05 / 3 + .95 * np.bincount(values, weights=fitted['factors'][i], minlength=3))
    factor = [math.prod(local[i][y[i]] for i in range(4)) for y in Y]
    prior = np.exp(-.5 * np.array([f['cost'] for f in grammar])[operators].sum(axis=1)); prior /= prior.sum()
    untrained = .05 / 81 + .95 * np.bincount(yi, weights=prior, minlength=81)
    return {'joint': joint.tolist(), 'factorized_same_closure': factor, 'untrained_same_closure': untrained.tolist()}
